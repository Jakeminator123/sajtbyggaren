"""Source-lock for the viewser dev-dispatcher (`apps/viewser/scripts/dev.mjs`).

Background (ADR 0028 — Runtime Ladder):

`VIEWSER_PREVIEW_MODE` is the single operator-facing knob that controls the
viewser preview pipeline. Three things have to agree on the value:

1. `apps/viewser/next.config.ts` — branches the COEP/COOP headers
   (`local-next` returns no headers, `stackblitz` / `auto` keep them).
2. `apps/viewser/scripts/dev.mjs` — branches `next dev` invocation
   (`local-next` runs http; `stackblitz` / `auto` run `--experimental-https`).
3. `apps/viewser/components/viewer-panel.tsx` — picks the runtime client
   path at request time.

If the dispatcher silently flips back to a hardcoded https or stops reading
the env var, the operator's `.env.local` becomes dead config — exactly the
regression the previous fix on this branch (`12cb770`) was meant to close.
This test source-locks the contract so that regression cannot recur quietly.

These are deliberately textual / substring assertions — we are NOT
exec'ing the dispatcher (cross-platform spawn semantics make that brittle
in CI). The dispatcher itself is small enough that text matches are a
reasonable proxy for behavioral correctness.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = REPO_ROOT / "apps" / "viewser" / "scripts" / "dev.mjs"
PACKAGE_JSON = REPO_ROOT / "apps" / "viewser" / "package.json"


def _load_dispatcher_source() -> str:
    assert DISPATCHER.exists(), (
        f"Expected {DISPATCHER} to exist; if it was renamed or moved, update "
        "package.json's `dev` script and this test in lockstep."
    )
    return DISPATCHER.read_text(encoding="utf-8")


def _load_package_json_source() -> str:
    assert PACKAGE_JSON.exists(), f"Expected {PACKAGE_JSON} to exist."
    return PACKAGE_JSON.read_text(encoding="utf-8")


def test_dispatcher_exists_at_expected_path() -> None:
    """The dispatcher lives at apps/viewser/scripts/dev.mjs.

    `package.json`'s `dev` script targets exactly this path. Renaming the
    file requires updating both ends together.
    """
    assert DISPATCHER.exists(), (
        "apps/viewser/scripts/dev.mjs must exist — it is the entry point for "
        "`npm run dev` and the only place that translates VIEWSER_PREVIEW_MODE "
        "into the right next-dev invocation."
    )


def test_package_json_dev_script_points_at_dispatcher() -> None:
    """`npm run dev` must invoke the dispatcher, not raw `next dev`."""
    source = _load_package_json_source()
    assert '"dev": "node scripts/dev.mjs"' in source, (
        "apps/viewser/package.json's `dev` script must read "
        '`"dev": "node scripts/dev.mjs"`. Reverting it to a raw `next dev` '
        "(or `next dev --experimental-https`) re-breaks the env-driven "
        "preview-mode contract — see ADR 0028 / commit 12cb770."
    )


def test_package_json_keeps_manual_escape_hatches() -> None:
    """`dev:http` and `dev:https` remain available as manual overrides."""
    source = _load_package_json_source()
    assert '"dev:http": "next dev"' in source, (
        "package.json must keep `dev:http` as a manual http escape hatch so "
        "operators can bypass the dispatcher without touching env files."
    )
    assert '"dev:https": "next dev --experimental-https"' in source, (
        "package.json must keep `dev:https` as a manual https escape hatch."
    )


def test_dispatcher_validates_mode_value() -> None:
    """The dispatcher must reject unknown values for VIEWSER_PREVIEW_MODE.

    Accepted: `local-next`, `stackblitz`, `auto`. Anything else gets a
    Swedish error message and a non-zero exit. Without this guard, a typo
    in `.env.local` silently falls through to whatever the runtime
    fallback chooses, which is the exact "dead config" failure mode this
    PR was meant to fix.
    """
    source = _load_dispatcher_source()
    assert "local-next" in source, (
        "dev.mjs must reference the `local-next` mode literal — it is the "
        "default and the LocalRuntime branch."
    )
    assert "stackblitz" in source, (
        "dev.mjs must reference the `stackblitz` mode literal — it is the "
        "WebContainer fallback branch."
    )
    assert "auto" in source, (
        "dev.mjs must reference the `auto` mode literal — it shares the "
        "stackblitz transport (https + COEP) for runtime-fallback safety."
    )
    assert "Okänt VIEWSER_PREVIEW_MODE" in source, (
        "dev.mjs must emit a Swedish error message for unknown modes "
        "(operator-facing strings are Swedish per the language policy). "
        "Removing the validation re-opens the door for typos in .env.local "
        "to be silently ignored."
    )


def test_dispatcher_conditionally_passes_experimental_https() -> None:
    """https is only set for non-local-next modes.

    `--experimental-https` must NOT be passed for `local-next`. The local
    preview iframe runs on plain http (port 4100-4199), and a https host
    would render that as mixed content and refuse to load it.
    """
    source = _load_dispatcher_source()
    assert "--experimental-https" in source, (
        "dev.mjs must reference `--experimental-https` somewhere — "
        "stackblitz/auto modes need it so SharedArrayBuffer is available "
        "inside the embed."
    )
    # The flag must be wrapped in a conditional that depends on the mode.
    # We don't assert the exact JS shape (ternary vs if), just that the
    # mode literal and the flag co-occur with a `local-next` discriminator
    # in the same file.
    assert "useHttps" in source or "mode !==" in source or 'mode === "stackblitz"' in source, (
        "dev.mjs must gate `--experimental-https` on the resolved mode. "
        "Hardcoding the flag re-breaks the local-preview iframe (mixed "
        "content); never passing it re-breaks StackBlitz embed (no SAB)."
    )


def test_dispatcher_exports_preview_mode_to_child_env() -> None:
    """The child `next dev` process must inherit VIEWSER_PREVIEW_MODE.

    `next.config.ts` reads `process.env.VIEWSER_PREVIEW_MODE` to decide
    whether to emit the COEP/COOP headers. If the dispatcher forgets to
    pass the mode through, next.config will see `undefined` and default
    back to the StackBlitz header path — even when the operator picked
    `local-next`, blocking the local-preview iframe.
    """
    source = _load_dispatcher_source()
    assert "VIEWSER_PREVIEW_MODE" in source, (
        "dev.mjs must reference VIEWSER_PREVIEW_MODE — it is the env var "
        "that drives the entire dispatcher."
    )
    assert "VIEWSER_PREVIEW_MODE: mode" in source or 'env: {' in source, (
        "dev.mjs must export VIEWSER_PREVIEW_MODE on the spawned child's env "
        "(via `env: { ..., VIEWSER_PREVIEW_MODE: mode }`). Without it the "
        "child next.js process cannot see the resolved mode and "
        "next.config.ts falls back to the wrong header branch."
    )


def test_dispatcher_reads_env_local_with_precedence() -> None:
    """The dispatcher must read .env.local in addition to .env / process.env.

    Operators put `VIEWSER_PREVIEW_MODE` in `.env.local` (it is gitignored
    so secrets next to it stay out of the repo). If the dispatcher only
    looked at `process.env`, the operator would have to remember to
    `$env:VIEWSER_PREVIEW_MODE = "..."` every shell — which defeats the
    "one source of truth" design of this PR.
    """
    source = _load_dispatcher_source()
    assert ".env.local" in source, (
        "dev.mjs must read `.env.local` so operators can set "
        "VIEWSER_PREVIEW_MODE there once and forget about it."
    )
    assert ".env" in source, (
        "dev.mjs should also read `.env` (lower precedence than .env.local) "
        "to match Next.js' own dev-time env precedence."
    )


def test_dispatcher_uses_shell_true_for_windows_npx() -> None:
    """`spawn(..., { shell: true })` is required for Windows `npx.cmd`.

    Without `shell: true`, Node on Windows resolves `npx` literally and
    fails because the executable is `npx.cmd`. This is the simplest
    cross-platform fix — documented in the dispatcher source.
    """
    source = _load_dispatcher_source()
    assert "shell: true" in source, (
        "dev.mjs must spawn with `shell: true` so `npx` resolves to "
        "`npx.cmd` on Windows. Removing it makes `npm run dev` fail on "
        "Windows with ENOENT."
    )


def test_dispatcher_reads_full_nextjs_env_precedence_chain() -> None:
    """The dispatcher loads all four Next.js dev dotenv files.

    Next.js documents the dev-time env load order (highest precedence
    first) as:

        1. process.env (always wins)
        2. .env.development.local
        3. .env.local
        4. .env.development
        5. .env

    If the dispatcher only loaded `.env` and `.env.local`, an operator
    who put VIEWSER_PREVIEW_MODE in `.env.development.local` (which is
    valid per Next.js semantics) would see the dispatcher pick the
    wrong mode while next.config.ts picked the right one — exactly the
    "two sides of the contract drift" failure mode this PR exists to
    eliminate. See
    https://nextjs.org/docs/app/guides/environment-variables#environment-variable-load-order
    """
    source = _load_dispatcher_source()
    for filename in (".env.development.local", ".env.local", ".env.development", ".env"):
        assert filename in source, (
            f"dev.mjs must reference {filename} so the dispatcher's env "
            "precedence chain matches Next.js' own dev-time chain. "
            "Drift here re-introduces the silent 'dispatcher picks one "
            "mode, next.config.ts picks another' regression."
        )


def test_dispatcher_propagates_signal_exit_to_parent() -> None:
    """The dispatcher must propagate child signals to the parent cleanly.

    Bugbot on the parked PR #85 flagged that when the child `next dev`
    process dies via signal, the parent dispatcher's handler did not
    propagate the exit deterministically and could hang. The fixed
    handler must:

      1. Install handlers for both SIGINT and SIGTERM (one-shot, so
         repeated signals during shutdown don't re-trigger cleanup).
      2. Forward the signal to the child via `child.kill(signal)`.
      3. Arm a watchdog timer (~5s); if the child has not exited within
         the window, escalate to SIGKILL and exit the parent with the
         POSIX-conventional signal exit code (130 for SIGINT, 143 for
         SIGTERM).
      4. On the child `exit` event, inspect the `signal` argument (not
         just `code`) so signal-caused exits translate to 128+signum.

    This test source-locks all four properties as substring assertions.
    Cross-platform spawn semantics make exec'ing the dispatcher in CI
    brittle; the file is small enough that text matches are a reasonable
    proxy for behavioral correctness.
    """
    source = _load_dispatcher_source()

    assert 'process.once("SIGINT"' in source, (
        "dev.mjs must register a SIGINT handler with `process.once` (not "
        "`process.on`) so a second Ctrl-C during shutdown does not re-"
        "enter the cleanup path. Using `process.on` re-opens the original "
        "hang-on-second-signal failure mode."
    )
    assert 'process.once("SIGTERM"' in source, (
        "dev.mjs must register a SIGTERM handler with `process.once` for "
        "the same reason as SIGINT — duplicate cleanup is a known way for "
        "the parent dispatcher to hang."
    )

    assert "child.kill(signal)" in source, (
        "dev.mjs must forward the received signal to the child via "
        "`child.kill(signal)`. Killing without forwarding leaves the "
        "next dev process orphaned."
    )

    assert "SIGKILL" in source, (
        "dev.mjs must escalate to SIGKILL if the child does not exit "
        "within the watchdog window. Without the fallback, a hung "
        "child keeps the parent dispatcher alive indefinitely."
    )
    assert "setTimeout(" in source and "clearTimeout(" in source, (
        "dev.mjs must arm a setTimeout watchdog AND clear it in the exit "
        "path. Forgetting to clear it would leak the timer and (worse) "
        "fire a stale SIGKILL after a clean shutdown."
    )
    assert "SHUTDOWN_WATCHDOG_MS" in source, (
        "The watchdog interval must be a named constant "
        "(SHUTDOWN_WATCHDOG_MS) so it is greppable and easy to tune. "
        "Inlining the magic number obscures the policy."
    )

    assert 'SIGNAL_EXIT_CODES = { SIGINT: 130, SIGTERM: 143 }' in source or (
        "SIGINT: 130" in source and "SIGTERM: 143" in source
    ), (
        "dev.mjs must map SIGINT → 130 and SIGTERM → 143 (POSIX "
        "convention: 128 + signal number). These are the exit codes "
        "shells expect from a process that died via signal; deviating "
        "breaks shell error handling and `$?` checks."
    )

    assert 'child.on("exit", (code, signal)' in source, (
        "The child exit handler must accept BOTH `code` and `signal` "
        "arguments. Reading only `code` (Node passes `null` when the "
        "exit was signal-caused) means a child killed by SIGINT looks "
        "like a clean exit-0, masking the failure."
    )
    assert "128 + sigNum" in source or "128 + signalNumber" in source, (
        "The child exit handler must translate signal-caused exits to "
        "128 + signal number (POSIX convention). Without this the "
        "parent reports the wrong exit code to the shell when the "
        "child died via signal."
    )


def test_dispatcher_documents_dev_only_scope() -> None:
    """The dispatcher must document that it is dev-only (no NODE_ENV)."""
    source = _load_dispatcher_source()
    assert "dev-only" in source.lower() or "dev only" in source.lower(), (
        "dev.mjs must document that it is dev-only and intentionally "
        "does NOT know about NODE_ENV — production goes through "
        "`next build` + `next start`, never through the dispatcher. "
        "The production safety gate lives in next.config.ts where it is "
        "authoritative for COEP/COOP. Duplicating the rule here would "
        "risk the two sides drifting."
    )
