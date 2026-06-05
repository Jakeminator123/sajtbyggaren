"""NPM subprocess helpers for the deterministic Builder.

Extracted from ``scripts.build_site`` as a behavior-preserving refactor
slice. ``scripts.build_site`` still imports and re-exports these symbols so
existing tests, monkeypatches and operator scripts can keep using the old
facade path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


def _coerce_subprocess_text(stream: object) -> str:
    """Return a subprocess stdout/stderr capture as a string, regardless of
    whether the runtime gave us ``None``, ``bytes`` or ``str``.

    ``subprocess.TimeoutExpired`` and ``subprocess.run(...).{stdout,stderr}``
    are typed as ``str | bytes | None`` depending on whether ``text=True``
    was set and how far the process got before the timeout fired. Callers
    that want to surface the partial output to the operator must handle
    all three branches; this helper centralises that so each callsite
    cannot drop one stream silently.
    """
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return str(stream)


NPM_INSTALL_TIMEOUT_ENV = "SAJTBYGGAREN_NPM_INSTALL_TIMEOUT_SECONDS"
NPM_BUILD_TIMEOUT_ENV = "SAJTBYGGAREN_NPM_BUILD_TIMEOUT_SECONDS"

_DEFAULT_NPM_INSTALL_TIMEOUT_SECONDS = 600
_DEFAULT_NPM_BUILD_TIMEOUT_SECONDS = 300


def _timeout_seconds_from_env(env_var: str, default: int) -> int:
    """Resolve an npm-step timeout (seconds), honouring an env override.

    Slow Cloud Agent VMs regularly exceed the baked-in 600 s / 300 s
    budgets and fail builds for reasons unrelated to site correctness
    (B86). Operators can raise the ceiling via ``env_var`` without a code
    change. An unset, blank, non-integer or non-positive value falls back
    to ``default`` so CI, tests and local runs keep the documented
    behaviour when nothing is set.
    """
    raw = os.environ.get(env_var)
    if raw is None:
        return default
    try:
        parsed = int(raw.strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


NPM_INSTALL_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    NPM_INSTALL_TIMEOUT_ENV, _DEFAULT_NPM_INSTALL_TIMEOUT_SECONDS
)
NPM_BUILD_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    NPM_BUILD_TIMEOUT_ENV, _DEFAULT_NPM_BUILD_TIMEOUT_SECONDS
)


def _sanitized_npm_env() -> dict[str, str]:
    """Return a sanitized environment for child npm subprocesses.

    When ``apps/viewser`` runs ``next dev`` and spawns this builder via
    ``POST /api/sites``, the child inherits the viewser dev-server's
    environment. Next.js 16 enables Turbopack by default and exports
    ``TURBOPACK=1`` (plus ``__NEXT_*`` internals) to every descendant.
    Inside the generated site that env collides with the ``--webpack``
    flag in the starter scripts (added to side-step the Next 16
    ``/_global-error`` Turbopack prerender bug), and ``next build``
    aborts with "Multiple bundler flags set: TURBOPACK=1, --webpack".

    The viewser also propagates ``NODE_ENV=development`` to its
    children. That triggers Next.js' "non-standard NODE_ENV" warning
    inside ``next build`` and disables production optimisations.
    Stripping ``NODE_ENV`` lets the generated site's ``next build``
    pick the correct default ("production") for itself.
    """
    env = os.environ.copy()
    for key in list(env.keys()):
        if (
            key == "TURBOPACK"
            or key.startswith("TURBO_")
            or key == "NEXT_RUNTIME"
            or key.startswith("__NEXT_")
        ):
            env.pop(key, None)
    env.pop("NODE_ENV", None)
    return env


def run_npm(
    command: list[str],
    cwd: Path,
    *,
    timeout: float | None = None,
) -> tuple[bool, float, str]:
    """Run an npm command and return (ok, seconds, last_lines).

    Uses ``shutil.which`` to resolve ``npm`` (or ``npm.cmd`` on Windows) so the
    subprocess is invoked with ``shell=False``. ``shell=True`` with a list
    silently drops every argument after the first on POSIX, which made
    ``npm install`` collapse to a bare ``npm`` invocation in CI and exit 1
    after printing the help screen.

    A ``timeout`` (seconds) is required for long-running steps - without it
    a hung npm install/build would block the builder forever and leave the
    run directory half-written. ``subprocess.TimeoutExpired`` is caught so
    the caller still gets a deterministic ``(False, elapsed, message)``
    tuple instead of an uncaught exception.

    The subprocess environment is sanitized via ``_sanitized_npm_env`` to
    remove Next.js dev-server env vars (``TURBOPACK``, ``__NEXT_*``,
    ``NODE_ENV``) that would otherwise leak from the viewser dev server
    into the generated site's build and break it.
    """
    npm_path = shutil.which("npm")
    if npm_path is None:
        return False, 0.0, "npm executable not found on PATH"

    full_command = (
        [npm_path, *command[1:]] if command and command[0] == "npm" else [npm_path, *command]
    )
    child_env = _sanitized_npm_env()
    start = time.monotonic()
    try:
        proc = subprocess.run(
            full_command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        # exc.stdout / exc.stderr are independently None | bytes | str. The
        # earlier implementation only built partial_text from one of them
        # and silently dropped the other when the type-check on stdout
        # mismatched - in particular stdout=None + stderr="<error log>"
        # would lose the only diagnostic the operator has. Decode each
        # stream individually and concatenate.
        partial_text = _coerce_subprocess_text(exc.stdout) + _coerce_subprocess_text(exc.stderr)
        last_lines = "\n".join(partial_text.splitlines()[-25:]) if partial_text else ""
        cmd_str = " ".join(command)
        message = f"timeout: '{cmd_str}' did not finish within {timeout:.0f}s"
        return False, elapsed, f"{message}\n{last_lines}".strip()
    elapsed = time.monotonic() - start
    output = (proc.stdout or "") + (proc.stderr or "")
    last_lines = "\n".join(output.splitlines()[-25:])
    return proc.returncode == 0, elapsed, last_lines


def _npm_step_result(name: str, ok: bool, seconds: float, log_excerpt: str) -> dict:
    step: dict[str, object] = {"name": name, "ok": ok, "seconds": round(seconds, 1)}
    if not ok and log_excerpt.strip():
        step["logExcerpt"] = log_excerpt.strip()
    return step
