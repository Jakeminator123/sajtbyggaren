"""B154 regression smoke test for Next dev TDZ hydration chunks.

The bug only showed up in the local ``next dev --webpack`` path for a
deterministic ecommerce-lite / noir-editorial site. Production build/start
was immune, so this test deliberately exercises the development server and
then inspects the emitted webpack chunks for the known TDZ shape.
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


def _run_checked(command: list[str], cwd: Path, timeout: int) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    assert completed.returncode == 0, (
        f"Command {' '.join(command)!r} failed with exit code "
        f"{completed.returncode} in {cwd}.\n{completed.stdout}"
    )


def _reader_thread(stream, output: list[str], lines: queue.Queue[str]) -> None:
    for line in iter(stream.readline, ""):
        output.append(line)
        lines.put(line)


def _start_next_dev(site_dir: Path, port: int) -> tuple[subprocess.Popen[str], list[str]]:
    process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=site_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert process.stdout is not None
    output: list[str] = []
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(
        target=_reader_thread,
        args=(process.stdout, output, lines),
        daemon=True,
    ).start()

    deadline = time.monotonic() + DEV_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"`npm run dev` exited early with code {process.returncode}.\n"
                + "".join(output)
            )
        try:
            line = lines.get(timeout=0.25)
        except queue.Empty:
            continue
        if "Ready" in line or "ready" in line:
            return process, output
    raise AssertionError(
        f"`npm run dev` did not report Ready within "
        f"{DEV_READY_TIMEOUT_SECONDS}s.\n{''.join(output)}"
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
    """Return Next dev chunk files across current and legacy output layouts."""

    chunk_roots = (
        site_dir / ".next" / "dev" / "static" / "chunks",
        site_dir / ".next" / "static" / "chunks",
    )
    chunks: list[Path] = []
    for root in chunk_roots:
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
    """Generated commerce/noir dev chunks must not contain the B154 TDZ trap."""

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
        _run_checked(["npm", "install"], site_dir, timeout=180)

    port = _free_port()
    process: subprocess.Popen[str] | None = None
    output: list[str] = []
    try:
        process, output = _start_next_dev(site_dir, port)
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
