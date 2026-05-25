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


# --------------------------------------------------------------------------
# Source-locks for the PR #88 review-fix round (post-Bugbot/Codex).
#
# These tests lock the specific behaviors the reviewers flagged on the
# initial preview-mode commit so they cannot quietly regress:
#
#   1. Watchdog must use `exitCode === null && signalCode === null` instead
#      of `!child.killed` to detect a still-alive child (Bugbot Medium +
#      Codex P1: `child.killed` flips to true the moment kill() is sent,
#      not when the process exits — making the original `!child.killed`
#      guard always-false dead code).
#
#   2. Shutdown must kill the entire subprocess tree, not just the shell
#      wrapper that `shell: true` spawns (Codex P1: on Windows `cmd.exe`
#      does not forward signals to its child `next dev`; on Unix the
#      shell may also not propagate cleanly).
#
#   3. The .env parser must accept `export VAR=val` and trailing
#      `# comment` (Codex P2: Next.js' own dotenv parsing accepts these
#      forms, so rejecting them in the dispatcher creates a false-positive
#      "Okänt VIEWSER_PREVIEW_MODE" failure for env files that next dev
#      would parse correctly).
# --------------------------------------------------------------------------


def test_dispatcher_watchdog_checks_exit_state_not_killed_flag() -> None:
    """The SIGKILL watchdog must use process-state checks, not `child.killed`.

    Bugbot Medium + Codex P1 on PR #88: Node sets `child.killed = true`
    IMMEDIATELY after a successful `child.kill(signal)` call — it means
    the signal was *sent*, not that the process *terminated*. So by the
    time the watchdog timer fires (5s later), `child.killed` is already
    true, and a naive `if (!child.killed) { kill SIGKILL }` guard makes
    the SIGKILL branch unreachable. That defeats the entire point of the
    watchdog: a hung child that ignores SIGINT/SIGTERM would never get
    the SIGKILL escalation, exactly the failure mode the watchdog exists
    to cover.

    The fix is to inspect process state (`exitCode === null` AND
    `signalCode === null`) — both become non-null only when the OS
    confirms the process actually exited.

    This lock prevents a regression back to `!child.killed`.
    """
    source = _load_dispatcher_source()
    assert "child.exitCode === null" in source, (
        "dev.mjs watchdog must check `child.exitCode === null` to detect "
        "a still-alive child. Using `!child.killed` is dead code because "
        "Node sets `killed` on signal-sent, not on process-exit. See "
        "Bugbot Medium + Codex P1 on PR #88."
    )
    assert "child.signalCode === null" in source, (
        "dev.mjs watchdog must also check `child.signalCode === null` "
        "alongside `exitCode === null`. Both must be null for the child "
        "to be confirmed alive — exitCode covers normal exit, signalCode "
        "covers signal-caused exit. Checking only one misses the other "
        "path."
    )


def test_dispatcher_kills_entire_subprocess_tree() -> None:
    """Shutdown must kill the whole tree (shell + npx + next dev), not just shell.

    Codex P1 on PR #88: spawning `npx next dev` with `shell: true` means
    the actual child is `cmd.exe /c "npx next dev"` (Windows) or
    `sh -c "npx next dev"` (Unix). `child.kill(signal)` kills the shell
    wrapper, but per Node docs the command the shell launched can survive
    — so after Ctrl-C the `next dev` process may keep port 3000 bound,
    breaking subsequent `npm run dev` starts and leaving orphan processes
    in local/CI environments.

    The fix is platform-specific tree-kill:
      - Windows: `taskkill /pid <pid> /T /F` (T = tree, F = force).
      - Unix: `process.kill(-child.pid, signal)` — negative PID = PGID,
        requires `detached: true` on spawn so the child becomes its own
        process group leader.

    This lock pins both halves so a refactor can't quietly drop one and
    re-introduce the orphan-process regression on the affected platform.
    """
    source = _load_dispatcher_source()
    assert "killTree" in source, (
        "dev.mjs must define and use a `killTree(signal)` helper that "
        "handles platform-specific tree-kill. Inlining the logic at each "
        "callsite makes drift between handleParentSignal and the watchdog "
        "almost certain."
    )
    assert "taskkill" in source, (
        "dev.mjs must call `taskkill /pid <pid> /T /F` on Windows so the "
        "entire process tree under the shell wrapper is killed. Without "
        "/T, only the shell dies and `next dev` survives — keeping port "
        "3000 bound and breaking the next `npm run dev`."
    )
    assert "process.kill(-child.pid" in source, (
        "dev.mjs must call `process.kill(-child.pid, signal)` on Unix to "
        "signal the whole process group. The negative PID is the POSIX "
        "convention for 'send to PGID'. Without it the shell dies but "
        "the npx + next dev subprocesses survive."
    )
    assert "detached: !IS_WINDOWS" in source or "detached: !isWindows" in source, (
        "dev.mjs must spawn with `detached: !IS_WINDOWS` so the Unix "
        "child becomes its own process group leader, which is required "
        "for `process.kill(-pid)` to work. Without detached, the child "
        "shares the parent's pgid and `kill(-pid)` would signal the "
        "parent itself."
    )


def test_dispatcher_env_parser_handles_export_prefix() -> None:
    """The .env parser must strip POSIX-shell `export ` prefixes.

    Codex P2 on PR #88: dotenv files often contain `export VAR=val`
    (it's valid POSIX shell and Next.js' own dotenv parser accepts it).
    The previous custom parser only handled bare `VAR=val`, so a line
    like `export VIEWSER_PREVIEW_MODE=stackblitz` parsed as a key of
    `"export VIEWSER_PREVIEW_MODE"` and a value of `"stackblitz"` —
    failing the mode-validation check and exiting the dispatcher with
    "Okänt VIEWSER_PREVIEW_MODE" even though next dev itself would have
    loaded the value correctly.

    This lock pins the export-prefix stripping in the parser.
    """
    source = _load_dispatcher_source()
    assert 'line.startsWith("export ")' in source, (
        "dev.mjs parseEnvFile must detect lines starting with `export ` "
        "and strip the prefix before splitting on `=`. Skipping this "
        "step re-introduces the false-reject regression on dotenv files "
        "that next dev itself parses correctly."
    )


def test_dispatcher_env_parser_strips_trailing_comments() -> None:
    """The .env parser must strip trailing `# comment` from unquoted values.

    Codex P2 on PR #88: a line like `VIEWSER_PREVIEW_MODE=local-next # foo`
    parsed as `local-next # foo` under the previous custom parser, failing
    the mode validator. Next.js' own dotenv parser strips the inline
    comment cleanly.

    The fix requires whitespace before `#` (so URL fragments like
    `https://x.com#frag` are not mangled) and only applies to unquoted
    values (quoted values may legitimately contain `#`).

    This lock pins the regex used for trailing-comment stripping.
    """
    source = _load_dispatcher_source()
    assert "\\s+#" in source, (
        "dev.mjs parseEnvFile must strip trailing inline comments where "
        "the `#` is preceded by whitespace. The whitespace requirement "
        "protects URL fragments and other legitimate `#` uses inside "
        "values from being mangled."
    )


# --------------------------------------------------------------------------
# Source-locks for the second review-fix round on top of PR #88
# (post-merge follow-up — Cursor Bugbot Medium + Codex P2 edge cases on the
# custom .env-parser).
#
#   1. The quote-grenen must accept an optional trailing `# comment` AFTER
#      the closing quote so a canonical dotenv pattern like
#      `VIEWSER_PREVIEW_MODE="local-next" # note` no longer false-rejects
#      against the mode validator. The previous two-branch shape required
#      `value.startsWith('"') && value.endsWith('"')`, which fails on this
#      input (`"local-next" # note` ends with `e`, not `"`), and the
#      else-branch's `\s+#`-stripping left `"local-next"` with the quotes
#      retained — `next dev` itself (via @next/env) parses this form
#      correctly, so the dispatcher's stricter shape was a regression.
#
#   2. The dispatcher must dotenv-expand `$VAR` / `${VAR}` references in
#      the resolved VIEWSER_PREVIEW_MODE before validation. dotenv-expand
#      (used internally by @next/env) supports both bare and braced
#      references, so a `.env*` file with
#      `VIEWSER_PREVIEW_MODE=$PREVIEW_DEFAULT` is valid for `next dev` —
#      rejecting it in the dispatcher with `Okänt VIEWSER_PREVIEW_MODE:
#      '$PREVIEW_DEFAULT'` is a false-reject.
# --------------------------------------------------------------------------


def test_dispatcher_env_parser_handles_quoted_with_trailing_comment() -> None:
    """The .env parser must accept `VAR="value" # comment` (quoted + comment).

    Cursor Bugbot Medium on PR #88: the previous quote-detection required
    the value to BOTH start and end with the same quote character. For a
    canonical dotenv literal like `VIEWSER_PREVIEW_MODE="local-next" # note`
    the raw value is `"local-next" # note` — starts with `"` but ends with
    `e`. It therefore fell through to the unquoted-comment-strip branch,
    which produced `"local-next"` (with quotes retained), failing the mode
    validator with `Okänt VIEWSER_PREVIEW_MODE: '"local-next"'` even though
    `next dev` itself parses the line correctly.

    The fix uses a single anchored regex
    `^(['"])((?:[^\\\\]|\\\\.)*?)\\1\\s*(?:#.*)?$` that captures the inner
    value via a non-greedy match against the same opening quote, then
    tolerates optional trailing whitespace + `# comment` AFTER the closing
    quote. This subsumes the previous `slice(1, -1)` quote-strip and the
    separate trailing-comment-strip, so both
    `VAR="local-next"`, `VAR='local-next'`, and
    `VAR="local-next" # note` reach the same code path.

    This lock pins the trailing-comment-after-closing-quote tolerance so a
    refactor cannot quietly drop it and reopen the false-reject regression.
    """
    source = _load_dispatcher_source()
    assert "(?:#.*)?$" in source, (
        "dev.mjs parseEnvFile must accept an optional trailing `# comment` "
        "AFTER the closing quote of a quoted value. Reverting to the "
        "two-branch shape (`startsWith && endsWith`-quote-strip followed by "
        "a separate comment-strip in the else-branch) re-introduces the "
        "false-reject regression for `VAR=\"value\" # comment` — Cursor "
        "Bugbot Medium on PR #88."
    )
    # The quoted-grenen must capture the inner value via a back-reference to
    # the opening quote so single- and double-quote lines share one path.
    # Without `\\1`, the parser would have to enumerate quote-pairs by hand
    # and risk drift between the single- and double-quote handling.
    assert "(['\"])" in source, (
        "dev.mjs parseEnvFile must use a character-class `(['\"])` to "
        "capture the opening quote. Splitting into separate single-quote "
        "and double-quote regexes invites drift between the two paths "
        "(one fix, two callsites — easy to miss one)."
    )


def test_dispatcher_env_parser_expands_variable_references() -> None:
    """The dispatcher must dotenv-expand `$VAR` / `${VAR}` in the resolved mode.

    Codex P2 on PR #88: a `.env*` file containing
    `VIEWSER_PREVIEW_MODE=$PREVIEW_DEFAULT` was passed through verbatim,
    failing the mode validator with `Okänt VIEWSER_PREVIEW_MODE:
    '$PREVIEW_DEFAULT'` and exiting the dispatcher — even though `next dev`
    itself (via @next/env's dotenv-expand) would have resolved the
    reference and accepted the value. That is a regression vs. running
    `next dev` directly, exactly the failure class the dispatcher was
    rebuilt to avoid.

    The fix is an `expandEnvRefs(value, env)` helper that runs at use-site
    on the resolved VIEWSER_PREVIEW_MODE value. Scope is intentionally
    narrow — the dispatcher only consumes one variable, and a general-
    purpose pre-merge expander would expand its own scope without need.

    The expander mirrors dotenv-expand semantics:
      - both `$VAR` (bare) and `${VAR}` (braced) supported,
      - `\\$` (escaped dollar) → literal `$`,
      - unknown references → empty string (safer than leaving a literal
        `$VAR` that would then false-reject against the mode validator).

    This lock pins both the helper's existence and the dual-form support.
    """
    source = _load_dispatcher_source()
    assert "expandEnvRefs" in source, (
        "dev.mjs must define and call an `expandEnvRefs(value, env)` "
        "helper that dotenv-expands `$VAR` / `${VAR}` references on the "
        "resolved VIEWSER_PREVIEW_MODE before validation. The helper name "
        "is the lock-point future refactors will collide with — renaming "
        "it requires updating this source-lock in lockstep."
    )
    # The dispatcher must call the expander on VIEWSER_PREVIEW_MODE; without
    # it the helper exists but isn't wired in, which is a silent regression.
    assert "expandEnvRefs(mergedEnv.VIEWSER_PREVIEW_MODE" in source, (
        "dev.mjs must invoke `expandEnvRefs(mergedEnv.VIEWSER_PREVIEW_MODE, "
        "mergedEnv)` at the use-site that feeds the mode validator. "
        "Defining the helper without wiring it in re-opens the same "
        "false-reject regression the helper exists to close."
    )
    # Both braced ${VAR} and bare $VAR forms must be supported. The regex
    # literal in the source is the canonical place to lock this — character
    # class `[A-Za-z_]` for the var-name + `\\$\\{...\\}` for the braced
    # alternative.
    assert "\\$\\{" in source, (
        "expandEnvRefs must support the `${VAR}` braced form. dotenv-"
        "expand supports both bare and braced; supporting only one creates "
        "a behavior mismatch with what `next dev` sees in the same .env "
        "file. Look for `\\$\\{` in the regex literal."
    )
    assert "[A-Za-z_]" in source, (
        "expandEnvRefs must restrict variable names to "
        "`[A-Za-z_][A-Za-z0-9_]*` (POSIX shell convention). Without the "
        "character-class anchor, a value like `$1.50` could be treated as "
        "a reference to `$1` and silently mangled."
    )
