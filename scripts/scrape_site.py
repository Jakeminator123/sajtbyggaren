"""scrape_site.py — discovery-wizard URL-scrape.

Tar en URL och returnerar pre-fyllda fält till Sajtbyggarens
discovery-wizard. Pipelinen:

    Frontend (CompanyStep)
      → POST /api/scrape-site  (apps/viewser/app/api/scrape-site/route.ts)
        → spawn `python3 scripts/scrape_site.py --url <url>`
          → fetcha startsidan + max 5 underlänkar (BeautifulSoup)
          → extrahera meta, kontakt, headings
          → (optional) OpenAI Responses → mappa till WizardAnswers
          → print JSON till stdout

JSON-utdata följer kontraktet som `discovery-wizard/wizard-types.ts`
deklarerar:

    {
      "ok": true,
      "data": {
        "companyName": "...",
        "offer": "...",
        "contact": {...},
        "services": [...],
        ...
        "scrapedFields": {"companyName": "high", ...}
      }
    }

Scriptet är **read-only mot internet** — det skriver inget till
disk och hämtar bara HTML-resurser (text/html). Binär-resurser
(bilder, PDF, etc.) ignoreras.

Säkerhet: vi guardar mot SSRF genom att avvisa privata IP-områden
(`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`,
`169.254.0.0/16`) efter DNS-lookup. Det följer samma princip som
Sajtmaskins `validateSsrfTarget` (`src/lib/ssrf-guard.ts`).
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - install guard
    print(
        json.dumps(
            {
                "ok": False,
                "error": (
                    f"Missing dependency: {exc.name}. "
                    "Install with 'pip install -r requirements.txt'."
                ),
            }
        )
    )
    sys.exit(0)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

USER_AGENT = "Sajtbyggaren-Discovery/1.0 (+https://localhost)"
HTTP_TIMEOUT_SECONDS = 8
MAX_PAGES = 5
MAX_HTML_BYTES = 1_500_000  # 1.5 MB cap per page so a poisoned response cannot OOM the helper.
MAX_TEXT_CORPUS = 60_000  # Cap LLM input regardless of how chatty the site is.
MAX_REDIRECTS = 5  # Cap how many hops fetch_html follows before giving up.

# Length budgets — vi vill inte överraska wizarden med 40-radig "Om oss"
# direkt från en scrapad sida. LLM-syntesen får komprimera senare.
RAW_OFFER_MAX = 600
RAW_ABOUT_MAX = 2000
RAW_VISION_MAX = 600

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


# Prioriterade länk-mönster för att hitta "rätt" undersidor — speglar
# Sajtmaskins `prioritizeLinks` i `src/lib/webscraper.ts`.
LINK_PRIORITY_PATTERNS = [
    (re.compile(r"(?:^|/)(om|about|story|history)(?:/|$|-)", re.IGNORECASE), 10),
    (re.compile(r"(?:^|/)(kontakt|contact)(?:/|$|-)", re.IGNORECASE), 9),
    (re.compile(r"(?:^|/)(tjanster|tjänster|services|behandlingar|tjanst)(?:/|$|-)", re.IGNORECASE), 8),
    (re.compile(r"(?:^|/)(produkter|products|shop|store|meny|menu)(?:/|$|-)", re.IGNORECASE), 8),
    (re.compile(r"(?:^|/)(priser|prices|pricing|prislista)(?:/|$|-)", re.IGNORECASE), 7),
    (re.compile(r"(?:^|/)(team|medarbetare|personal)(?:/|$|-)", re.IGNORECASE), 7),
    (re.compile(r"(?:^|/)(projekt|portfolio|case)(?:/|$|-)", re.IGNORECASE), 6),
    (re.compile(r"(?:^|/)(blogg|blog|nyheter|news)(?:/|$|-)", re.IGNORECASE), 3),
]

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)
# Svenska/internationella telefonnummer — minst 7 siffror, tillåter +, mellanslag, bindestreck, parenteser.
PHONE_REGEX = re.compile(
    r"(?:\+?\d[\d\s\-()]{6,}\d)",
)
# Postnummer på svenskt format för att gissa adressrader.
SWEDISH_POSTAL = re.compile(r"\b\d{3}\s?\d{2}\b")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ScrapePage:
    url: str
    title: str = ""
    headings: list[str] = field(default_factory=list)
    body_text: str = ""


@dataclass
class ScrapedCorpus:
    start_url: str
    pages: list[ScrapePage] = field(default_factory=list)
    meta_description: str = ""
    og_title: str = ""
    emails: set[str] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    addresses: set[str] = field(default_factory=set)
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_url(raw: str) -> str:
    """Add `https://` if scheme saknas och normalisera trailing slash."""
    raw = raw.strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw
    return raw


def validate_ssrf(url: str) -> str | None:
    """Returnera felmeddelande om URL pekar på privat IP/localhost."""
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return "URL saknar host."
    # Reserverade nyckelord direkt
    if host.lower() in {"localhost", "localhost.localdomain"}:
        return "Privata / lokala adresser tillåts inte."
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return f"DNS-lookup misslyckades: {exc}"
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in PRIVATE_NETWORKS:
            if ip in net:
                return "Privata / lokala adresser tillåts inte."
    return None


def fetch_html(url: str) -> tuple[str, str | None]:
    """Returnera (html, error). HTML är tom sträng vid fel.

    Redirects följs manuellt så att varje hop går genom validate_ssrf.
    Att låta requests följa redirects via allow_redirects=True skulle
    annars öppna en SSRF-glipa där en publik URL 302:ar mot intern IP
    (t.ex. http://169.254.169.254/ för AWS metadata eller
    http://127.0.0.1:8501 för en lokal Streamlit-backoffice) och
    requests skulle hämta det utan att validate_ssrf körs igen.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
    }
    current = url
    response = None
    for _hop in range(MAX_REDIRECTS + 1):
        try:
            response = requests.get(
                current,
                headers=headers,
                timeout=HTTP_TIMEOUT_SECONDS,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            return "", f"HTTP-fel: {exc}"
        if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                return "", f"HTTP {response.status_code} utan Location-header"
            next_url = urljoin(current, location)
            scheme = urlparse(next_url).scheme.lower()
            if scheme not in {"http", "https"}:
                return "", f"Redirect-mål använder icke-tillåtet schema: {scheme}"
            ssrf_error = validate_ssrf(next_url)
            if ssrf_error:
                return "", f"Redirect blockerad: {ssrf_error}"
            current = next_url
            continue
        break
    else:
        return "", f"Fler än {MAX_REDIRECTS} redirects, ger upp."
    if response is None:
        return "", "Ingen HTTP-respons mottagen."
    if response.status_code >= 400:
        return "", f"HTTP {response.status_code}"
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return "", f"Icke-HTML svar ({content_type or 'okänd content-type'})"
    # `requests.iter_content` med `stream=True` förbrukar svaret första
    # gången iter:n körs. `apparent_encoding` accessar svaret igen och
    # kraschar med "content already consumed". Vi läser därför raw
    # bytes via `.raw.read()` (med decode_content för gzip) och faller
    # tillbaka på utf-8 om Content-Type inte säger något om charset.
    try:
        raw = response.raw.read(MAX_HTML_BYTES + 1, decode_content=True)
    except Exception as exc:  # pragma: no cover - defensive
        return "", f"Läs-fel: {exc}"
    if len(raw) > MAX_HTML_BYTES:
        raw = raw[:MAX_HTML_BYTES]
    encoding = response.encoding or "utf-8"
    try:
        return raw.decode(encoding, errors="replace"), None
    except Exception as exc:  # pragma: no cover - defensive
        return "", f"Encoding-fel: {exc}"


def _comparable_host(host: str) -> str:
    """Host för intern/extern-jämförelse: gemener + utan ``www.``-prefix.

    B165: operatörer anger ofta apex-domänen (``example.com``) medan sajten
    redirectar till ``www.example.com`` och länkar internt med www-prefix.
    ``fetch_html`` följer redirecten för HTML:en men ``collect_links``
    jämförde host strikt mot ursprungs-URL:en — alla www-länkar
    filtrerades bort som externa och bara startsidan crawlades.
    """
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def collect_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Returnera unika, internt-prioriterade länkar från startsidan."""
    base_host = _comparable_host(urlparse(base_url).hostname or "")
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base_url, href)
        absolute = absolute.split("#")[0].rstrip("/")
        if not absolute or absolute in seen:
            continue
        # Bara interna länkar (samma host; apex och www räknas som samma sajt).
        link_host = _comparable_host(urlparse(absolute).hostname or "")
        if link_host and link_host != base_host:
            continue
        seen.add(absolute)
        score = 0
        for pattern, weight in LINK_PRIORITY_PATTERNS:
            if pattern.search(absolute):
                score = max(score, weight)
                break
        scored.append((score, absolute))
    scored.sort(key=lambda item: (-item[0], item[1]))
    # Returnera URL:erna ordnade på prioritet; första MAX_PAGES-1 läses.
    return [url for _score, url in scored]


def extract_text(soup: BeautifulSoup) -> tuple[str, list[str]]:
    """Returnera (body_text, headings) från soup, utan script/style."""
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    # Joina paragrafer + listpunkter; bevara radbrytningar.
    parts: list[str] = []
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "blockquote"]):
        text = el.get_text(" ", strip=True)
        if text:
            parts.append(text)
    body = "\n".join(parts).strip()
    return body, headings


def find_meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name})
    if not tag and name.startswith("og:"):
        tag = soup.find("meta", attrs={"property": name})
    if not tag:
        return ""
    content = tag.get("content", "")
    return content.strip() if isinstance(content, str) else ""


def crawl(start_url: str) -> ScrapedCorpus:
    corpus = ScrapedCorpus(start_url=start_url)
    visited: set[str] = set()
    pending: list[str] = [start_url]

    while pending and len(corpus.pages) < MAX_PAGES:
        url = pending.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html, error = fetch_html(url)
        if error or not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        body, headings = extract_text(soup)
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        page = ScrapePage(url=url, title=title, headings=headings, body_text=body)
        corpus.pages.append(page)

        # Meta + emails/phones/addresses ackumuleras över alla sidor.
        if not corpus.meta_description:
            corpus.meta_description = find_meta(soup, "description")
        if not corpus.og_title:
            corpus.og_title = find_meta(soup, "og:title")

        plain_text = f"{body}\n{title}"
        for match in EMAIL_REGEX.findall(plain_text):
            corpus.emails.add(match.lower())
        for match in PHONE_REGEX.findall(plain_text):
            digits = re.sub(r"\D", "", match)
            if 7 <= len(digits) <= 15:
                corpus.phones.add(match.strip())
        for line in plain_text.splitlines():
            if SWEDISH_POSTAL.search(line):
                stripped = line.strip()
                if 8 <= len(stripped) <= 120:
                    corpus.addresses.add(stripped)

        # Lägg till länkar från första sidan endast — undvik fan-out.
        if len(corpus.pages) == 1:
            for link in collect_links(soup, start_url):
                if link not in visited and link not in pending:
                    pending.append(link)
            # Liten paus mellan sidor — vi vill inte hamra någons VPS.
            time.sleep(0.2)

    # Bygg ett raw_text-corpus för LLM-syntes (om aktiverad).
    raw_parts: list[str] = []
    if corpus.meta_description:
        raw_parts.append(f"META: {corpus.meta_description}")
    for page in corpus.pages:
        if page.title:
            raw_parts.append(f"# {page.title}")
        if page.headings:
            raw_parts.append("\n".join(page.headings[:8]))
        if page.body_text:
            raw_parts.append(page.body_text[:8000])
    corpus.raw_text = "\n\n".join(raw_parts).strip()[:MAX_TEXT_CORPUS]
    return corpus


# ---------------------------------------------------------------------------
# Deterministic field mapping (no LLM)
# ---------------------------------------------------------------------------


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    cut = value[: limit].rsplit(" ", 1)[0]
    return cut + "…"


def deterministic_fields(corpus: ScrapedCorpus) -> dict[str, Any]:
    """Returnera WizardAnswers-fält som kan utvinnas regex/heuristik."""
    out: dict[str, Any] = {}
    scraped: dict[str, str] = {}

    # Företagsnamn: og:title → första H1 → title → host
    name_candidate = ""
    if corpus.og_title:
        name_candidate = corpus.og_title
    elif corpus.pages and corpus.pages[0].headings:
        name_candidate = corpus.pages[0].headings[0]
    elif corpus.pages and corpus.pages[0].title:
        name_candidate = corpus.pages[0].title
    if name_candidate:
        # Title-fältet ser ofta ut som "Företag | Slogan". Ta första segmentet.
        name_candidate = re.split(r"\s[|–—-]\s", name_candidate, maxsplit=1)[0].strip()
        out["companyName"] = _truncate(name_candidate, 80)
        scraped["companyName"] = "medium"

    # Offer / pitch: meta description är hyggligt deterministisk.
    if corpus.meta_description:
        out["offer"] = _truncate(corpus.meta_description, RAW_OFFER_MAX)
        scraped["offer"] = "high"

    # Kontakt
    contact: dict[str, str] = {}
    if corpus.emails:
        contact["email"] = next(iter(sorted(corpus.emails)))
        scraped["contact"] = "high"
    if corpus.phones:
        contact["phone"] = next(iter(sorted(corpus.phones)))
        scraped["contact"] = "high"
    if corpus.addresses:
        contact["address"] = next(iter(sorted(corpus.addresses)))
        scraped["contact"] = "high"
    if contact:
        out["contact"] = contact

    return {"fields": out, "scraped": scraped}


# ---------------------------------------------------------------------------
# Optional LLM synthesis
# ---------------------------------------------------------------------------


def _llm_synthesize(corpus: ScrapedCorpus) -> dict[str, Any] | None:
    """Försök berika fält via OpenAI Responses API. Returnera None om
    nyckel saknas eller om något går snett — vi vill aldrig fela
    scrape-flödet bara för att LLM:en hostar.

    LLM:en får läsa corpus + returnerar JSON med wizard-fält. Vi kör
    INTE Pydantic-validering här eftersom Sajtbyggaren saknar ett
    schema för WizardAnswers på Python-sidan ännu — istället
    plockar vi bara de fält vi förstår och castar.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not corpus.raw_text:
        return None
    try:
        from openai import OpenAI
    except ImportError:  # pragma: no cover - install guard
        return None

    model = os.environ.get("SAJTBYGGAREN_DISCOVERY_MODEL", "gpt-4o")

    instructions = (
        "Du är Sajtbyggarens discovery-assistent. Du läser HTML-text "
        "från en befintlig svensk företagshemsida och returnerar JSON "
        "med fält som ska förifylla en wizard. Svenska som svar. "
        "Skriv bara JSON, inga kommentarer. Om ett fält inte finns i "
        "texten — utelämna det helt. Korta texter (max 600 tecken per fält)."
    )
    user_message = (
        "Företagshemsida (text):\n\n"
        f"{corpus.raw_text}\n\n"
        "Returnera JSON med valfri delmängd av:\n"
        "  companyName (str), offer (str, max 600 tkn), aboutText (str, max 1500 tkn),\n"
        "  historyText, visionText, contactIntroText,\n"
        "  toneTags (str[]), designStyle (str),\n"
        "  primaryColorHex (#rrggbb), accentColorHex (#rrggbb),\n"
        "  services [{ name, description? }], products [{ name, price?, description? }],\n"
        "  targetAudience (str),\n"
        "  uniqueSellingPoints (str[]).\n"
        "Bara fält du har stöd för i texten."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=20,
        )
        raw = response.choices[0].message.content or ""
        if not raw.strip():
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception:
        return None


def _merge_llm_into_fields(
    deterministic: dict[str, Any], llm_fields: dict[str, Any] | None
) -> dict[str, Any]:
    """LLM fyller bara hål — deterministiska fält vinner alltid."""
    out = dict(deterministic.get("fields", {}))
    scraped = dict(deterministic.get("scraped", {}))
    if not llm_fields:
        return {"fields": out, "scraped": scraped}

    def _set_if_missing(key: str, value: Any, confidence: str) -> None:
        if key in out:
            return
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        if isinstance(value, list) and not value:
            return
        out[key] = value
        scraped[key] = confidence

    _set_if_missing("companyName", llm_fields.get("companyName"), "medium")
    _set_if_missing("offer", llm_fields.get("offer"), "medium")
    _set_if_missing("aboutText", llm_fields.get("aboutText"), "medium")
    _set_if_missing("historyText", llm_fields.get("historyText"), "medium")
    _set_if_missing("visionText", llm_fields.get("visionText"), "medium")
    _set_if_missing("contactIntroText", llm_fields.get("contactIntroText"), "medium")
    _set_if_missing("targetAudience", llm_fields.get("targetAudience"), "medium")
    _set_if_missing("uniqueSellingPoints", llm_fields.get("uniqueSellingPoints"), "medium")

    # Brand-block
    brand: dict[str, Any] = {}
    if isinstance(llm_fields.get("toneTags"), list):
        brand["toneTags"] = [t for t in llm_fields["toneTags"] if isinstance(t, str)]
    if isinstance(llm_fields.get("designStyle"), str):
        brand["designStyle"] = llm_fields["designStyle"]
    if isinstance(llm_fields.get("primaryColorHex"), str):
        brand["primaryColorHex"] = llm_fields["primaryColorHex"]
    if isinstance(llm_fields.get("accentColorHex"), str):
        brand["accentColorHex"] = llm_fields["accentColorHex"]
    if brand:
        out["brand"] = brand
        scraped["brand"] = "medium"

    # Tjänster och produkter — bara om listan finns och har poster med name.
    def _normalize_services(items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            return []
        result: list[dict[str, Any]] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            entry: dict[str, Any] = {"id": f"llm-{idx}", "name": name.strip()}
            desc = item.get("description")
            if isinstance(desc, str) and desc.strip():
                entry["description"] = desc.strip()
            price = item.get("price")
            if isinstance(price, str) and price.strip():
                entry["price"] = price.strip()
            result.append(entry)
        return result

    services = _normalize_services(llm_fields.get("services"))
    if services:
        _set_if_missing("services", services, "medium")
    products = _normalize_services(llm_fields.get("products"))
    if products:
        _set_if_missing("products", products, "medium")

    return {"fields": out, "scraped": scraped}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(url: str, *, company_name: str | None = None) -> dict[str, Any]:
    normalized = normalize_url(url)
    if not normalized:
        return {"ok": False, "error": "URL saknas."}
    ssrf_error = validate_ssrf(normalized)
    if ssrf_error:
        return {"ok": False, "error": ssrf_error}

    corpus = crawl(normalized)
    if not corpus.pages:
        return {"ok": False, "error": "Kunde inte hämta innehåll från sajten."}

    deterministic = deterministic_fields(corpus)
    llm_fields = _llm_synthesize(corpus)
    merged = _merge_llm_into_fields(deterministic, llm_fields)

    fields = merged["fields"]
    scraped = merged["scraped"]
    if company_name and "companyName" not in fields:
        fields["companyName"] = company_name
        scraped["companyName"] = "low"

    # Bygg payloaden i wizardens shape.
    data: dict[str, Any] = {}
    for key, value in fields.items():
        if key == "brand" and isinstance(value, dict):
            # Brand måste merge:as in i wizardens default-brand-shape.
            data["brand"] = {
                "toneTags": value.get("toneTags", []),
                "designStyle": value.get("designStyle", ""),
                "primaryColorHex": value.get("primaryColorHex", ""),
                "accentColorHex": value.get("accentColorHex", ""),
                "wordsToAvoid": "",
            }
        else:
            data[key] = value

    # contact-blocket måste vara komplett shape om vi sätter något fält.
    if "contact" in data and isinstance(data["contact"], dict):
        data["contact"] = {
            "phone": data["contact"].get("phone", ""),
            "email": data["contact"].get("email", ""),
            "address": data["contact"].get("address", ""),
            "openingHours": data["contact"].get("openingHours", ""),
        }

    data["scrapedFields"] = scraped
    return {
        "ok": True,
        "data": data,
        "meta": {
            "pagesCrawled": len(corpus.pages),
            "url": normalized,
            "llmUsed": llm_fields is not None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape en sajt och returnera wizard-fält.")
    parser.add_argument("--url", required=True, help="URL till sajten som ska skrapas.")
    parser.add_argument("--company-name", default=None, help="Operatorns angivna företagsnamn (fallback).")
    args = parser.parse_args()

    result = run(args.url, company_name=args.company_name)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
