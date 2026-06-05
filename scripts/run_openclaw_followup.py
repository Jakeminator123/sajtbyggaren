"""OpenClaw follow-up decision CLI (skiva 1b backend seam for /api/prompt).

Read-only wrapper around
``packages.generation.orchestration.openclaw.orchestrate`` (OpenClaw Core V0).
Given a follow-up message + optional ``siteId`` / ``baseRunId`` it emits a
schema-stable ``OpenClawDecision`` JSON so apps/viewser can shell to
``scripts/`` (repo-boundaries.v1.json) and show the operator an HONEST decision:

    answer_only        -> a plain answer, no build
    clarification      -> a clarifying question, no build
    plan_only          -> a proposed plan, no build
    patch_plan_request -> status=action_bridge_missing (the patch -> apply ->
                          targeted-render action bridge is the NEXT slice; V0
                          never fakes a success)

Guarantees (inherited from OpenClaw Core V0 + classify_message.py):
    - READ-ONLY. Prints JSON to stdout; no disk write, no build, no preview,
      no shell, no network, no ``current.json`` mutation.
    - DETERMINISTIC. ``classify_message`` (KÖR-6a) + the pure ``decide``; no
      LLM, no ``OPENAI_API_KEY``, no per-prompt cost.
    - HONEST. An edit instruction returns ``action_bridge_missing`` rather than
      a faked applied change; ``appliedVisibleEffect`` stays False until the
      action bridge lands.

Two modes:
    - default (read-only): emit the OpenClawDecision only (no build/preview).
    - ``--apply`` (action-bridge): for an ``edit_instruction`` the bridge RUNS
      the existing KÖR-7 follow-up chain (``run_followup_chain`` = router ->
      context -> patch -> apply -> targeted render) and reports the real
      outcome under a separate ``bridge`` object. A read-only kind never builds.
      ``--apply`` is additive + opt-in: it does not change ``/api/prompt``'s
      current behaviour; the route can adopt it when christopher wires the UI.

The chain stays authoritative: ``appliedVisibleEffect`` / ``previewShouldRefresh``
come from it, so a no-op never fakes a change. ``OpenClawDecision`` is never
mutated (its V0 validator forces ``appliedVisibleEffect=False``); the real
outcome lives in ``bridge``.

Usage:
    python scripts/run_openclaw_followup.py -- "vad tycker du om sidan?"
    python scripts/run_openclaw_followup.py --site-id painter-palma -- "byt rubriken till X"
    python scripts/run_openclaw_followup.py --apply --site-id painter-palma -- "byt rubriken till X"

Conventions:
    - Code comments and identifiers in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Make packages/ importable when running this script directly.
sys.path.insert(0, str(REPO_ROOT))


def _decide(message: str, *, site_id: str | None, base_run_id: str | None):
    """Run OpenClaw Core V0 read-only and return the ``OpenClawDecision``.

    Deferred import keeps the package dependency inside the function (mirrors
    ``scripts/classify_message.py`` / ``scripts/dev_generate.py``) so the module
    stays import-light and ruff-clean.
    """
    from packages.generation.orchestration.openclaw import orchestrate
    from packages.generation.orchestration.router import RouterContext

    router_context = RouterContext(siteId=site_id) if site_id else None
    context_kwargs: dict[str, object] = {}
    if site_id:
        context_kwargs["site_id"] = site_id
    if base_run_id:
        # The context level is taken from the router; run_id only matters when
        # the router asks for site/run context. Forwarded verbatim (read-only).
        context_kwargs["run_id"] = base_run_id
    return orchestrate(message, router_context=router_context, **context_kwargs)


def decide_to_json(
    message: str,
    *,
    site_id: str | None = None,
    base_run_id: str | None = None,
) -> str:
    """Return the read-only OpenClaw follow-up decision for ``message`` as JSON."""
    decision = _decide(message, site_id=site_id, base_run_id=base_run_id)
    return json.dumps(decision.model_dump(), ensure_ascii=False)


def apply_followup_to_json(
    message: str,
    *,
    site_id: str,
    base_run_id: str | None = None,
    do_build: bool = True,
    runs_dir: Path | None = None,
    generated_dir: str | Path | None = None,
) -> str:
    """OpenClaw action-bridge: decide, then RUN the chain for an edit.

    This is the action half of skiva 1b. OpenClaw Core V0 is the gate: only an
    ``edit_instruction`` (``action == "patch_plan_request"``) is delegated to the
    existing KÖR-7 follow-up chain (``run_followup_chain`` = router -> context ->
    patch -> apply -> targeted render). A read-only kind (answer/clarification/
    plan_only) NEVER builds.

    The chain stays authoritative + honest: ``appliedVisibleEffect`` /
    ``previewShouldRefresh`` come straight from it, so a no-op (no patchable
    edit, empty/rejected plan, unmapped apply) reports ``applied=False`` instead
    of faking a change. ``OpenClawDecision`` itself is never mutated (its
    validator forces ``appliedVisibleEffect=False`` in V0); the real outcome
    lives in the separate ``bridge`` object.

    Output shape (the seam apps/viewser consumes):
        {"decision": <OpenClawDecision>, "bridge": {status, applied,
         previewShouldRefresh, chain}}
    """
    decision = _decide(message, site_id=site_id, base_run_id=base_run_id)
    bridge: dict[str, object] = {
        "status": "no_build_needed",
        "applied": False,
        "previewShouldRefresh": False,
        "chain": None,
    }
    if decision.action == "patch_plan_request":
        from scripts.build_site import run_followup_chain

        try:
            chain = run_followup_chain(
                site_id,
                message,
                base_run_id=base_run_id,
                do_build=do_build,
                runs_dir=runs_dir,
                generated_dir=generated_dir,
            )
        except SystemExit as exc:
            # The chain raises SystemExit when there is no prior run to build on.
            # Degrade to an honest error rather than crashing the bridge.
            bridge = {
                "status": "error",
                "applied": False,
                "previewShouldRefresh": False,
                "chain": None,
                "error": str(exc),
            }
        else:
            bridge = {
                "status": str(chain.get("stage", "unknown")),
                "applied": bool(chain.get("applied", False)),
                "previewShouldRefresh": bool(chain.get("previewShouldRefresh", False)),
                "chain": chain,
            }
    return json.dumps(
        {"decision": decision.model_dump(), "bridge": bridge},
        ensure_ascii=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Emit a read-only OpenClaw follow-up decision (answer_only / "
            "clarification / plan_only / patch_plan_request) as schema-stable "
            "JSON. Deterministic KÖR-6a router + OpenClaw Core V0; no LLM, no "
            "build, no preview."
        )
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help="Optional siteId for RouterContext + context assembly (metadata).",
    )
    parser.add_argument(
        "--base-run-id",
        default=None,
        help="Optional baseRunId to iterate from; forwarded to context assembly.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Action-bridge: for an edit_instruction, RUN the KÖR-7 follow-up "
            "chain (build) and report the real outcome. Requires --site-id. "
            "Without this flag the script stays read-only (decision only)."
        ),
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="With --apply, skip npm install/build (fast; for testing).",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="The follow-up message. Prefer passing after `--`.",
    )
    args = parser.parse_args()

    if args.message is None:
        print(
            "run_openclaw_followup.py requires a message argument.",
            file=sys.stderr,
        )
        return 1

    if args.apply:
        if not args.site_id:
            print("--apply requires --site-id.", file=sys.stderr)
            return 1
        print(
            apply_followup_to_json(
                args.message,
                site_id=args.site_id,
                base_run_id=args.base_run_id,
                do_build=not args.skip_build,
            )
        )
        return 0

    print(
        decide_to_json(
            args.message,
            site_id=args.site_id,
            base_run_id=args.base_run_id,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
