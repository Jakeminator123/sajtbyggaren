"""Hämta OpenClaw-dokumentationen som Markdown till en lokal spegel.

OpenClaw publicerar docs agentvänligt: varje sida finns som ren Markdown om
man lägger till ``.md`` på URL:en (se https://docs.openclaw.ai/llms.txt). Det
här scriptet läser ``llms.txt``, plockar ut alla docs-sidor och sparar dem
under ``openclaw-docs/`` så att Cursor indexerar dem och agenter kan läsa/grep:a
dem direkt med filverktyg — utan att en MCP-server behöver köras.

Spegeln är gitignored och ligger i ``check_term_coverage`` ``EXCLUDE_DIRS``, så
den påverkar varken git-historiken eller governance-checken.

Körs från repo-roten:

    python scripts/fetch_openclaw_docs.py            # uppdatera spegeln
    python scripts/fetch_openclaw_docs.py --limit 10 # snabb testkörning
"""

from __future__ import annotations

import argparse
import json
import queue
import re
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "openclaw-docs"

DOCS_HOST = "docs.openclaw.ai"
LLMS_TXT_URL = f"https://{DOCS_HOST}/llms.txt"
LLMS_FULL_URL = f"https://{DOCS_HOST}/llms-full.txt"

USER_AGENT = "sajtbyggaren-openclaw-docs-fetch/1.0 (+local mirror)"
TIMEOUT = 30
MAX_WORKERS = 8
RETRIES = 3

# Plocka https://docs.openclaw.ai/... ur markdown-länkar i llms.txt.
LINK_RE = re.compile(r"\((https://docs\.openclaw\.ai/[^)\s]+)\)")

# Resurser som inte är docs-sidor (sitemap/robots osv) hoppas över.
SKIP_SUFFIXES = (".xml", ".txt", ".json", ".png", ".jpg", ".jpeg", ".svg", ".ico")


def fetch_text(url: str) -> str:
    """Hämta en URL som text, med retry och en hygglig user-agent."""
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/markdown, text/plain, */*"})
            with urlopen(request, timeout=TIMEOUT) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except Exception as error:  # noqa: BLE001 - vi vill bara retry:a allt nät-relaterat
            last_error = error
            if attempt < RETRIES:
                time.sleep(0.5 * attempt)
    raise RuntimeError(f"misslyckades hämta {url}: {last_error}")


def page_urls_from_llms(llms_text: str) -> list[str]:
    """Returnera unika docs-sid-URL:er ur llms.txt (i förekommande ordning)."""
    seen: set[str] = set()
    urls: list[str] = []
    for match in LINK_RE.finditer(llms_text):
        url = match.group(1).rstrip("/")
        path = urlparse(url).path
        if path.lower().endswith(SKIP_SUFFIXES) and not path.lower().endswith(".md"):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def markdown_url(page_url: str) -> str:
    """Bygg .md-export-URL:en för en docs-sida."""
    if page_url.endswith(".md"):
        return page_url
    return page_url + ".md"


def output_path_for(page_url: str) -> Path:
    """Mappa en docs-URL till en lokal filsökväg under OUTPUT_DIR."""
    path = urlparse(page_url).path.strip("/")
    if not path:
        path = "index"
    if path.endswith(".md"):
        path = path[: -len(".md")]
    return OUTPUT_DIR / f"{path}.md"


def run_pool(
    items: list[str],
    worker: Callable[[str], tuple[str, bool, str]],
    workers: int,
) -> list[tuple[str, bool, str]]:
    """Kör ``worker`` över ``items`` med en enkel trådpool (stdlib threading/queue)."""
    pending: queue.Queue[str] = queue.Queue()
    for item in items:
        pending.put(item)
    results: list[tuple[str, bool, str]] = []
    lock = threading.Lock()

    def loop() -> None:
        while True:
            try:
                item = pending.get_nowait()
            except queue.Empty:
                return
            result = worker(item)
            with lock:
                results.append(result)

    threads = [threading.Thread(target=loop) for _ in range(max(1, workers))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def fetch_one(page_url: str) -> tuple[str, bool, str]:
    """Hämta en sida som Markdown och skriv den lokalt. Returnerar (url, ok, info)."""
    md_url = markdown_url(page_url)
    try:
        text = fetch_text(md_url)
    except RuntimeError as error:
        return page_url, False, str(error)
    target = output_path_for(page_url)
    target.parent.mkdir(parents=True, exist_ok=True)
    header = f"<!-- source: {md_url} -->\n\n"
    target.write_text(header + text, encoding="utf-8")
    return page_url, True, str(target.relative_to(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Spegla OpenClaw-docs som Markdown lokalt.")
    parser.add_argument("--limit", type=int, default=0, help="Hämta max N sidor (0 = alla). För testkörningar.")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Antal parallella hämtningar.")
    args = parser.parse_args()

    print(f"Läser {LLMS_TXT_URL} ...")
    llms_text = fetch_text(LLMS_TXT_URL)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "llms.txt").write_text(llms_text, encoding="utf-8")
    try:
        (OUTPUT_DIR / "llms-full.txt").write_text(fetch_text(LLMS_FULL_URL), encoding="utf-8")
    except RuntimeError:
        print("  (llms-full.txt saknas eller kunde inte hämtas — hoppar över)")

    urls = page_urls_from_llms(llms_text)
    if args.limit > 0:
        urls = urls[: args.limit]
    print(f"Hittade {len(urls)} docs-sidor. Hämtar som Markdown ...")

    ok = 0
    failures: list[str] = []
    for url, success, info in run_pool(urls, fetch_one, args.workers):
        if success:
            ok += 1
        else:
            failures.append(f"{url} -> {info}")

    manifest = {
        "source": LLMS_TXT_URL,
        "fetchedAt": datetime.now(UTC).isoformat(),
        "pagesRequested": len(urls),
        "pagesWritten": ok,
        "failures": failures,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Klart: {ok}/{len(urls)} sidor skrivna till {OUTPUT_DIR.relative_to(REPO_ROOT)}/")
    if failures:
        print(f"Misslyckade ({len(failures)}):")
        for line in failures[:20]:
            print(f"  - {line}")
        if len(failures) > 20:
            print(f"  ... och {len(failures) - 20} till (se manifest.json)")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
