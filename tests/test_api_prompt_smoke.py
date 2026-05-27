"""HTTP smoke test for the Viewser /api/prompt Node -> Python bridge."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
PROMPT = "Skapa en hemsida för en elektriker i Malmö."
CANONICAL_ARTEFACTS = (
    "input.json",
    "site-brief.json",
    "site-plan.json",
    "generation-package.json",
    "quality-result.json",
    "repair-result.json",
    "build-result.json",
    "trace.ndjson",
)


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


def _start_server(port: int, tmp_path: Path) -> tuple[subprocess.Popen[str], list[str]]:
    package_json = json.loads((VIEWSER_DIR / "package.json").read_text(encoding="utf-8"))
    script = "dev:http" if "dev:http" in package_json.get("scripts", {}) else "dev"
    env = os.environ.copy()
    env.update(
        {
            "SAJTBYGGAREN_GENERATED_DIR": str(tmp_path / "generated"),
            "VIEWSER_RUNS_DIR": str(tmp_path / "runs"),
            "VIEWSER_PROMPT_INPUTS_DIR": str(tmp_path / "prompt-inputs"),
            "SAJTBYGGAREN_TEST": "1",
            "VIEWSER_PREVIEW_MODE": "local-next",
        }
    )
    env.pop("OPENAI_API_KEY", None)
    env.pop("VERCEL", None)
    process = subprocess.Popen(
        ["npm", "run", script, "--", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=VIEWSER_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    lines: list[str] = []

    def read_lines() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line.rstrip())

    threading.Thread(target=read_lines, daemon=True).start()
    return process, lines


def _wait_for_server(process: subprocess.Popen[str], port: int, logs: list[str]) -> None:
    deadline = time.monotonic() + 90
    url = f"http://127.0.0.1:{port}/api/runs"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Viewser dev server exited early. Logs:\n{chr(10).join(logs[-80:])}")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    pytest.fail(f"Timed out waiting for Viewser dev server. Logs:\n{chr(10).join(logs[-80:])}")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


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
    process, logs = _start_server(port, tmp_path)
    try:
        _wait_for_server(process, port, logs)
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
    assert (tmp_path / "generated" / str(payload["siteId"]) / ".next").is_dir()
