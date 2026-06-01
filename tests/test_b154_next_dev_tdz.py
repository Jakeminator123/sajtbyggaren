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


def _spawn_next_dev(
    site_dir: Path, port: int
) -> tuple[subprocess.Popen[str], list[str], threading.Event, threading.Thread]:
    """Spawn ``next dev`` and start a daemon thread that drains stdout
    into a shared output list.

    Returns ``(process, output, ready_event, reader)`` so the caller can:

    - Pass the same ``output`` list into ``_wait_for_dev_ready`` (which
      reads via ``ready_event``) and continue to receive lines into the
      *same* list AFTER the ready signal fires. That is critical for
      B154: the original TDZ error fires during hydration when routes
      are fetched, i.e. *after* the ready line, so the final assertion
      that scans ``output`` for ``Cannot access 'w' before initialization``
      must be able to see lines emitted during route-fetch as well.
    - Capture the Popen handle in the caller's own scope before any
      potentially-raising wait code runs, so the ``finally`` cleanup
      always sees the process.
    - ``reader.join(timeout=...)`` after ``_stop_process`` so any lines
      still in the pipe at termination land in ``output`` before the
      final assertion runs.
    """
    process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=site_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert process.stdout is not None
    output: list[str] = []
    output_lock = threading.Lock()
    ready_event = threading.Event()

    def _drain() -> None:
        assert process.stdout is not None
        for line in iter(process.stdout.readline, ""):
            with output_lock:
                output.append(line)
            if "Ready" in line or "ready" in line:
                ready_event.set()

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()
    return process, output, ready_event, reader


def _wait_for_dev_ready(
    process: subprocess.Popen[str],
    output: list[str],
    ready_event: threading.Event,
    timeout_seconds: float = DEV_READY_TIMEOUT_SECONDS,
) -> None:
    """Wait for the drain thread to report the Next dev ready line.

    Polls ``process.poll()`` so a process that dies before ready aborts
    promptly with the accumulated output. Otherwise sleeps in 0.5s
    intervals to keep the deadline live regardless of whether Next dev
    emits new lines. The drain thread keeps running after this returns,
    so post-ready hydration errors are still captured in ``output``.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if ready_event.is_set():
            return
        if process.poll() is not None:
            raise AssertionError(
                f"`npm run dev` exited early with code {process.returncode}.\n"
                + "".join(output)
            )
        if ready_event.wait(timeout=0.5):
            return
    raise AssertionError(
        f"`npm run dev` did not report Ready within {timeout_seconds:.0f}s.\n"
        + "".join(output)
    )


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    # Defensive cleanup: never crash, even if the process resists termination
    # and never crash if the process exits in one of the platform-specific
    # race windows below.
    #   - Windows race: process may exit between the poll() above and
    #     Popen.terminate(); the underlying Win32 termination call can
    #     return a "process already gone" status which Python raises as
    #     PermissionError (errno 5, access denied). Same applies to
    #     Popen.kill() on Windows.
    #   - Stuck process: Popen.kill() can fail to reap a process that sits
    #     in kernel blockage. The post-kill wait would then raise
    #     subprocess.TimeoutExpired.
    # All exceptions are swallowed silently — if neither terminate nor kill
    # works, the test cannot do more, and surface logs/zombies stay for the
    # operator to triage.
    try:
        process.terminate()
    except PermissionError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except PermissionError:
            return
        try:
            process.wait(timeout=10)
        except (subprocess.TimeoutExpired, PermissionError):
            return


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
    # B157 level 4 Stage A: build() returns the immutable build dir
    # <generated>/<siteId>/builds/<buildId>/, not the flat site root. The
    # build dir is still the correct cwd for `next dev` + chunk inspection.
    assert site_dir.parent == generated_root / B154_SITE_ID / "builds"
    assert site_dir.parent.parent == generated_root / B154_SITE_ID
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
    reader: threading.Thread | None = None
    try:
        process, output, ready_event, reader = _spawn_next_dev(site_dir, port)
        _wait_for_dev_ready(process, output, ready_event)
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
        if reader is not None:
            # Drain thread exits when readline() returns "" after process
            # close. Join so post-ready output (e.g. hydration errors
            # logged during the route fetches above) is fully populated
            # in `output` before the final assertion scans it.
            reader.join(timeout=5)
        assert "Cannot access 'w' before initialization" not in "".join(output)
