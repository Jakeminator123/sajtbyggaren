"""HTTP smoke test for the Viewser /api/prompt Node -> Python bridge."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
PROMPT = "Skapa en hemsida för en elektriker i Malmö."
CANONICAL_ARTEFACTS = ("input.json", "site-brief.json", "site-plan.json", "generation-package.json", "quality-result.json", "repair-result.json", "build-result.json", "trace.ndjson")


def _require_tools() -> None:
    missing = [name for name in ("node", "npm") if shutil.which(name) is None]
    if missing:
        pytest.skip(f"Missing tool(s): {', '.join(missing)}")


def _ensure_viewser_install() -> None:
    if (VIEWSER_DIR / "node_modules" / "next").exists():
        return
    result = subprocess.run(
        ["npm", "install", "--package-lock=false", "--no-audit", "--no-fund"],
        cwd=VIEWSER_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"Viewser npm install failed:\n{result.stdout[-2000:]}")


def _random_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(port: int, tmp_path: Path) -> subprocess.Popen[str]:
    package_json = json.loads((VIEWSER_DIR / "package.json").read_text(encoding="utf-8"))
    script = "dev:http" if "dev:http" in package_json.get("scripts", {}) else "dev"
    env = os.environ.copy()
    env.update({
        "SAJTBYGGAREN_GENERATED_DIR": str(tmp_path / "generated"),
        "VIEWSER_RUNS_DIR": str(tmp_path / "runs"),
        "VIEWSER_PROMPT_INPUTS_DIR": str(tmp_path / "prompt-inputs"),
        "SAJTBYGGAREN_TEST": "1",
        "VIEWSER_PREVIEW_MODE": "local-next",
    })
    # Force the deterministic mock Site Brief (briefSource=mock-no-key).
    # Popping the key is NOT enough: the Next.js dev server auto-loads
    # apps/viewser/.env.local / .env into the spawned process env, so a real
    # OPENAI_API_KEY on the operator's machine would be reloaded and the
    # bridge would return briefSource="real". Setting an empty string wins
    # because neither Next nor dotenv overrides an already-set env var, and
    # has_openai_api_key() treats empty/whitespace as missing.
    env["OPENAI_API_KEY"] = ""
    env.pop("VERCEL", None)
    # preexec_fn is Unix-only and raises ValueError on Windows
    kwargs = {}
    if sys.platform != "win32":
        kwargs["preexec_fn"] = os.setsid
    process = subprocess.Popen(
        ["npm", "run", script, "--", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=VIEWSER_DIR,
        env=env,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )
    return process


def _wait_for_server(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 90
    url = f"http://127.0.0.1:{port}/api/runs"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("Viewser dev server exited early.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    pytest.fail("Timed out waiting for Viewser dev server.")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    # Defensive cleanup: never crash, even if the process resists every
    # termination signal we try, and never crash if the process exits in
    # one of the platform-specific race windows below.
    #   - POSIX race: process may exit between the poll() above and
    #     os.killpg(); killpg then raises ProcessLookupError (ESRCH).
    #   - Windows race: process may exit between poll() and
    #     Popen.terminate(); the underlying Win32 termination call can
    #     return a "process already gone" status which Python raises as
    #     PermissionError (errno 5, access denied). Same applies to
    #     Popen.kill() on Windows.
    #   - Stuck process: SIGKILL/Popen.kill() can also fail to reap a
    #     process that sits in POSIX D-state (uninterruptible sleep) or
    #     similar kernel blockage. The post-SIGKILL wait would then raise
    #     subprocess.TimeoutExpired.
    # All three exceptions are swallowed silently — if neither SIGTERM nor
    # SIGKILL works, the test cannot do more, and surface logs/zombies
    # stay for the operator to triage. We deliberately do NOT catch the
    # broader OSError to avoid hiding genuine permission failures (e.g.
    # the test runs as a user that cannot signal the spawned process at
    # all — that is a config bug, not a race).
    try:
        if sys.platform != "win32":
            # Unix: use killpg to terminate the process group (preexec_fn=os.setsid created a group)
            os.killpg(process.pid, signal.SIGTERM)
        else:
            # Windows: use terminate() which is cross-platform
            process.terminate()
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            if sys.platform != "win32":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (ProcessLookupError, PermissionError):
            return
        try:
            process.wait(timeout=10)
        except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
            return


def _post_prompt(port: int) -> tuple[int, dict[str, object]]:
    body = json.dumps({"prompt": PROMPT, "mode": "init"}).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/prompt",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=720) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        pytest.fail(f"/api/prompt returned HTTP {exc.code}: {payload}")


@pytest.mark.slow
def test_api_prompt_route_spawns_python_end_to_end(tmp_path: Path) -> None:
    _require_tools()
    _ensure_viewser_install()

    port = _random_port()
    process = _start_server(port, tmp_path)
    try:
        _wait_for_server(process, port)
        status, payload = _post_prompt(port)
    finally:
        _stop_process(process)

    assert status == 200
    assert payload["version"] == 1
    assert payload["briefSource"] == "mock-no-key"
    assert payload["buildStatus"] == "ok"
    assert isinstance(payload["runId"], str) and payload["runId"]
    assert isinstance(payload["siteId"], str) and payload["siteId"]
    assert isinstance(payload["projectId"], str) and payload["projectId"]

    build_result = payload["buildResult"]
    assert isinstance(build_result, dict)
    assert build_result["status"] == "ok"
    assert build_result["engineMode"] == "init"

    run_dir = tmp_path / "runs" / payload["runId"]
    for artefact in CANONICAL_ARTEFACTS:
        assert (run_dir / artefact).is_file(), f"Missing canonical artefact {artefact}"
    assert (run_dir / "generated-files" / "app" / "page.tsx").is_file()
    assert (tmp_path / "prompt-inputs" / f"{payload['siteId']}.project-input.json").is_file()
    # B157 level 4 Stage A: the build is immutable under
    # <generated>/<siteId>/builds/<buildId>/ and published via current.json.
    site_root = tmp_path / "generated" / str(payload["siteId"])
    pointer = json.loads((site_root / "current.json").read_text(encoding="utf-8"))
    active_build_dir = site_root / pointer["buildPath"]
    assert (active_build_dir / ".next").is_dir()
