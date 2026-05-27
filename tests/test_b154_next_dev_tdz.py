"""B154 regression smoke test for Next dev TDZ hydration chunks.

This is a *chunk heuristic* test, not a full browser-hydration smoke. It
spawns ``next dev``, curls the four canonical routes to confirm the
server is alive, and greps the emitted webpack chunks for the
``let w; ... w.X ...`` pattern that B154's TDZ crash produced. A real
headless-browser hydration check (puppeteer/playwright) that loads ``/``
and asserts no ``Cannot access 'w' before initialization`` error is
tracked as a follow-up bug (B156) and would replace the chunk heuristic
when it lands.
"""

from __future__ import annotations

import json
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_site import build  # noqa: E402

B154_SITE_ID = "b154-noir-editorial-dev"
DEV_READY_TIMEOUT_SECONDS = 90
NPM_INSTALL_TIMEOUT_SECONDS = 300
ROUTE_TIMEOUT_SECONDS = 30
TDZ_WINDOW_CHARS = 12_000
TDZ_LET_W_RE = re.compile(r"\blet\s+w\s*;")
TDZ_ACCESS_RE = re.compile(r"\bw\.[A-Za-z_$][\w$]*")
TDZ_ASSIGN_RE = re.compile(r"\bw\s*=")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_b154_project_input(tmp_path: Path) -> Path:
    source = REPO_ROOT / "examples" / "atelje-bird.project-input.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["siteId"] = B154_SITE_ID
    payload["scaffoldId"] = "ecommerce-lite"
    payload["variantId"] = "noir-editorial"
    payload["language"] = "sv"

    target = tmp_path / "fixtures" / f"{B154_SITE_ID}.project-input.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _spawn_next_dev(site_dir: Path, port: int) -> subprocess.Popen[str]:
    """Spawn ``next dev`` and return the Popen handle immediately.

    Caller is responsible for ``_wait_for_dev_ready`` and ``_stop_process``;
    splitting spawn from wait means the caller can capture the handle in
    its outer scope before any potentially-raising wait code runs, so the
    ``finally`` cleanup always sees the process.
    """
    process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=site_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert process.stdout is not None
    return process


def _wait_for_dev_ready(
    process: subprocess.Popen[str], timeout_seconds: float = DEV_READY_TIMEOUT_SECONDS
) -> list[str]:
    """Drain ``process.stdout`` in a worker thread and wait for the Next
    dev ready-line.

    ``readline`` is blocking, so a previous implementation that called it
    inside a ``while time.monotonic() < deadline`` loop would never reach
    the timeout check if Next dev stopped emitting lines. Draining stdout
    on a background thread and reading via ``queue.get(timeout=...)``
    keeps the deadline enforced.
    """
    line_queue: queue.Queue[str | None] = queue.Queue()

    def _drain() -> None:
        assert process.stdout is not None
        try:
            for line in iter(process.stdout.readline, ""):
                line_queue.put(line)
        finally:
            line_queue.put(None)

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()

    output: list[str] = []
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            while True:
                try:
                    line = line_queue.get(timeout=0.5)
                except queue.Empty:
                    break
                if line is None:
                    break
                output.append(line)
            raise AssertionError(
                f"`npm run dev` exited early with code {process.returncode}.\n"
                + "".join(output)
            )
        try:
            line = line_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        if line is None:
            break
        output.append(line)
        if "Ready" in line or "ready" in line:
            return output
    raise AssertionError(
        f"`npm run dev` did not report Ready within {timeout_seconds:.0f}s.\n"
        + "".join(output)
    )


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _fetch_route(port: int, route: str) -> str:
    url = f"http://127.0.0.1:{port}{route}"
    with urllib.request.urlopen(url, timeout=ROUTE_TIMEOUT_SECONDS) as response:
        assert response.status == 200, f"{url} returned HTTP {response.status}"
        return response.read().decode("utf-8", errors="replace")


def _chunk_files(site_dir: Path) -> list[Path]:
    roots = (
        site_dir / ".next" / "dev" / "static" / "chunks",
        site_dir / ".next" / "static" / "chunks",
    )
    chunks: list[Path] = []
    for root in roots:
        if root.is_dir():
            chunks.extend(sorted(root.rglob("*.js")))
    return chunks


def _find_tdz_chunk(site_dir: Path) -> tuple[Path, str] | None:
    chunks = _chunk_files(site_dir)
    assert chunks, (
        "Next dev produced no inspectable JS chunks under .next/dev/static/chunks "
        "or .next/static/chunks; the B154 smoke test cannot prove the TDZ "
        "pattern is absent."
    )
    for chunk in chunks:
        text = chunk.read_text(encoding="utf-8", errors="ignore")
        for declaration in TDZ_LET_W_RE.finditer(text):
            window = text[declaration.end() : declaration.end() + TDZ_WINDOW_CHARS]
            assignment = TDZ_ASSIGN_RE.search(window)
            access = TDZ_ACCESS_RE.search(window)
            if access is None:
                continue
            if assignment is None or access.start() < assignment.start():
                start = max(declaration.start() - 120, 0)
                end = min(declaration.end() + access.end() + 240, len(text))
                return chunk, text[start:end]
    return None


@pytest.mark.tooling
@pytest.mark.slow
def test_b154_next_dev_chunks_do_not_access_w_before_initialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if shutil.which("npm") is None:
        pytest.skip("npm not available; Next dev TDZ smoke test cannot run.")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = _write_b154_project_input(tmp_path)
    generated_root = tmp_path / "generated"

    site_dir, _ = build(
        project_input,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=generated_root,
    )
    assert site_dir == generated_root / B154_SITE_ID
    assert (site_dir / "package.json").is_file()

    if not (site_dir / "node_modules").is_dir():
        subprocess.run(
            ["npm", "install"],
            cwd=site_dir,
            timeout=NPM_INSTALL_TIMEOUT_SECONDS,
            check=True,
        )

    port = _free_port()
    process: subprocess.Popen[str] | None = None
    output: list[str] = []
    try:
        process = _spawn_next_dev(site_dir, port)
        output = _wait_for_dev_ready(process)
        for route in ("/", "/produkter", "/om-oss", "/kontakt"):
            html = _fetch_route(port, route)
            assert "<html" in html.lower(), f"{route} did not return HTML"

        tdz_match = _find_tdz_chunk(site_dir)
        assert tdz_match is None, (
            "B154 TDZ pattern found in Next dev chunk. "
            f"Chunk: {tdz_match[0].relative_to(site_dir)}\n"
            f"Snippet:\n{tdz_match[1]}"
        )
    finally:
        if process is not None:
            _stop_process(process)
        assert "Cannot access 'w' before initialization" not in "".join(output)
