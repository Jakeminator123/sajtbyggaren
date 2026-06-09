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

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
ROUTER_DECISION_SCHEMA = (
    REPO_ROOT / "governance" / "schemas" / "router-decision.schema.json"
)
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


# Substrings Next.js prints when a SECOND `next dev` tries to start in a
# project dir that already has a dev server running. The dev-lock lives inside
# the shared `.next` distDir, so a viewser dev server the operator left running
# in apps/viewser (or an orphaned one from a previous run) makes this test's own
# `next dev` refuse to start and exit early. That is an ENVIRONMENT collision,
# not a code regression (documented in AGENTS.md + agent-inbox msg-0049), so we
# skip rather than fail on it. We match Next's own message rather than guessing
# at process state, and ONLY this exact signal is treated as skippable — any
# other early exit still fails the test, so its end-to-end coverage is intact.
DEV_LOCK_COLLISION_MARKERS = (
    "Another next dev server is already running",
    "dev server is already running",
)


def _start_server(
    port: int, tmp_path: Path, log_path: Path
) -> subprocess.Popen[str]:
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
    # Capture the dev server's output to a file (instead of DEVNULL) so an
    # early exit can be classified: a `.next` dev-lock collision with an
    # already-running viewser dev server skips (env issue, msg-0049); any
    # other early exit still fails. The child gets its own duplicated handle,
    # so the parent closes its copy immediately after spawn — the file is then
    # read only after the child has exited, avoiding cross-process file locks.
    log_handle = open(log_path, "w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            ["npm", "run", script, "--", "--port", str(port), "--hostname", "127.0.0.1"],
            cwd=VIEWSER_DIR,
            env=env,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
    finally:
        log_handle.close()
    return process


def _skip_if_dev_lock_collision(log_path: Path) -> None:
    """Skip (don't fail) if the dev server exited from a `.next` dev-lock clash.

    Called only after the spawned `next dev` has exited. Reads the captured
    output and, if it carries Next's "another dev server is already running"
    signal, raises ``pytest.skip`` with operator guidance. Returns normally
    for every other early-exit reason so the caller still fails the test.
    """
    try:
        output = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if any(marker in output for marker in DEV_LOCK_COLLISION_MARKERS):
        pytest.skip(
            "A viewser dev server is already running in apps/viewser, so this "
            "test's own `next dev` could not acquire the shared `.next` "
            "dev-lock and exited early. Stop the existing dev server before "
            "running the slow suite (see AGENTS.md + agent-inbox msg-0049). "
            "Skipping rather than red-flagging the suite on an environment "
            "collision."
        )


def _wait_for_server(
    process: subprocess.Popen[str], port: int, log_path: Path
) -> None:
    deadline = time.monotonic() + 90
    url = f"http://127.0.0.1:{port}/api/runs"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _skip_if_dev_lock_collision(log_path)
            pytest.fail("Viewser dev server exited early.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    pytest.fail("Timed out waiting for Viewser dev server.")


def _stop_process(process: subprocess.Popen[str]) -> None:
    """Terminate the dev server *and every descendant*.

    The Popen target is the ``npm`` launcher, which spawns ``next dev``,
    which spawns Turbopack worker processes. ``Popen.terminate()`` /
    ``Popen.kill()`` only signal the launcher, so on Windows the
    grandchildren are orphaned: they keep running and keep holding the
    shared ``.next`` dev-lock. That is doubly bad here — an orphaned
    ``next dev`` from a previous run is exactly what makes a later run of
    this same test hit the dev-lock collision (msg-0049) and skip, and
    B154 documented the same leak eventually breaking a ``npm ci`` in
    apps/viewser with an access-denied unlink error on the locked
    ``next-swc-*.node``. Reap the whole tree, not just the launcher.

    Cleanup must never crash, even if the process resists every
    termination we try or exits in a platform-specific race window:
      - POSIX race: the process may exit between the poll() above and
        os.killpg(); killpg then raises ProcessLookupError (ESRCH).
      - Windows: taskkill /T /F itself handles the "already gone" race,
        so only the launch + wait are guarded (PermissionError for the
        access-denied race, TimeoutExpired for a stuck process).
      - Stuck process (POSIX): SIGKILL can fail to reap a process in
        D-state (uninterruptible sleep); the post-SIGKILL wait then
        raises subprocess.TimeoutExpired.
    These are swallowed silently — if nothing reaps the process, the
    test cannot do more, and surface logs/zombies stay for the operator
    to triage. We deliberately do NOT catch the broader OSError to avoid
    hiding genuine permission failures (e.g. the test runs as a user that
    cannot signal the spawned process at all — a config bug, not a race).
    """
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        # /T reaps the child tree, /F forces it. taskkill handles the
        # "already gone" race itself, so we only guard the launch + wait.
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                check=False,
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.wait(timeout=10)
        except (subprocess.TimeoutExpired, PermissionError):
            pass
        return

    # POSIX: signal the whole process group created by preexec_fn=os.setsid.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
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
@pytest.mark.requires_node
def test_api_prompt_route_spawns_python_end_to_end(tmp_path: Path) -> None:
    _require_tools()
    _ensure_viewser_install()

    port = _random_port()
    # Capture the dev server log under tmp_path so a `.next` dev-lock collision
    # with an already-running viewser dev server skips cleanly instead of
    # red-flagging the suite (agent-inbox msg-0049). tmp_path is per-test, so
    # this leaves nothing behind in the repo tree.
    dev_log = tmp_path / "viewser-dev-server.log"
    process = _start_server(port, tmp_path, dev_log)
    try:
        _wait_for_server(process, port, dev_log)
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

    # KÖR-6a (Fas 1, skiva 1a): the response carries a schema-valid, read-only
    # routerDecision alongside runId/siteId/buildStatus. The init prompt is not
    # a follow-up edit, so it is never suppressed by the honesty gate.
    router_decision = payload["routerDecision"]
    assert isinstance(router_decision, dict), "routerDecision must be present."
    schema = json.loads(ROUTER_DECISION_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(router_decision)
    # Read-only metadata never asks to start a build/preview from this surface.
    assert router_decision["shouldStartPreview"] is False

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
