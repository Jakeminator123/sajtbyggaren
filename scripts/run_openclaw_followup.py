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

This is the DECISION half of skiva 1b. The action bridge that actually runs
``patch -> apply -> targeted render`` from a ``patch_plan_request`` is the next
slice (docs/handoff.md skiva 1b / GAP-followup-prompt-content-passthrough). The
deterministic copyDirective path in ``scripts/prompt_to_project_input.py`` keeps
applying name/tagline/about/services edits today; this script only exposes the
router+OpenClaw OPINION so the UI can be honest about what was understood.

Usage:
    python scripts/run_openclaw_followup.py -- "vad tycker du om sidan?"
    python scripts/run_openclaw_followup.py --site-id painter-palma -- "byt rubriken till X"

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


def decide_to_json(
    message: str,
    *,
    site_id: str | None = None,
    base_run_id: str | None = None,
) -> str:
    """Return the OpenClaw follow-up decision for ``message`` as one-line JSON.

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
    decision = orchestrate(message, router_context=router_context, **context_kwargs)
    return json.dumps(decision.model_dump(), ensure_ascii=False)


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
