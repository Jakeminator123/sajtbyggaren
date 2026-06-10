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

F1 slice 2 (conductor wiring, additive): BEFORE the existing flow runs, the
message is classified with ``classify_conversation`` (the slice-1 conductor
layer) and the owning role is looked up via ``role_for_edit_kind``:

    - An edit keeps the EXACT same flow as before; the role (stylist /
      section_builder / copy) is attached to the emitted decision payload as
      ``conversation`` METADATA only - it never changes the chain's behaviour.
    - A conversation kind (small_talk / site_opinion / question) stops BEFORE
      any build with an honest answer-only decision - the same honesty-gate
      pattern as the existing read-only kinds. No version is written, no
      render runs, ``previewShouldRefresh`` stays False. The actual chat
      answer text is produced by the Viewser chat helper (TS half), never
      faked here.

``ConversationKind`` stays a conductor-layer concept (slice-1 design):
``governance/schemas/router-decision.schema.json`` is untouched and the
embedded router decision keeps its locked eight-kind contract verbatim.

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

# The conductor conversation kinds the dispatcher answers itself (F1 slice 2).
# ``edit`` keeps the unchanged chain flow and ``other`` falls through to the
# existing OpenClaw Core V0 mapping - only these three stop with an answer.
_ANSWER_ONLY_CONVERSATION_KINDS = ("small_talk", "site_opinion", "question")

# Honest per-kind answer placeholders for the emitted decision. The REAL chat
# answer text is produced by the Viewser chat helper (lib/openai.ts) on the TS
# side - this seam stays deterministic and never fakes a conversation.
_CONVERSATION_DECISION_ANSWERS = {
    "small_talk": (
        "Det här är småprat - sajten behöver inte ändras. Ingen build "
        "startas; själva svarstexten produceras av chat-hjälpen i Viewser."
    ),
    "site_opinion": (
        "Det här är en fråga om omdöme på sajten - ingen ändring behövs. "
        "Ingen build startas; själva svarstexten produceras av chat-hjälpen "
        "i Viewser."
    ),
    "question": (
        "Det här är en ren fråga som inte kräver någon ändring av sajten. "
        "Ingen build startas; själva svarstexten produceras av chat-hjälpen "
        "i Viewser."
    ),
}


def _classify_conversation(message: str, *, site_id: str | None):
    """Run the slice-1 conductor classification (deterministic, no LLM).

    Deferred import for the same import-light reason as ``_decide``. The
    classification composes the unchanged router; ``model_fallback`` stays
    False so this seam never costs an ``OPENAI_API_KEY`` call.
    """
    from packages.generation.orchestration.openclaw import classify_conversation
    from packages.generation.orchestration.router import RouterContext

    router_context = RouterContext(siteId=site_id) if site_id else None
    return classify_conversation(message, context=router_context)


def _conversation_metadata(conversation) -> dict[str, object]:
    """The additive ``conversation`` block attached to the decision payload.

    Pure metadata: for an edit it carries the owning role
    (``role_for_edit_kind`` already resolved it inside the classification);
    for a conversation it explains why the dispatcher answers. It never
    mutates ``OpenClawDecision`` itself (the Pydantic contract is untouched).
    """
    return {
        "conversationKind": conversation.conversationKind,
        "role": conversation.role,
        "source": conversation.source,
        "rationale": conversation.rationale,
    }


def _conversation_answer_decision(
    message: str,
    conversation,
    *,
    site_id: str | None,
    base_run_id: str | None,
):
    """Build the honest answer-only decision for a conversation kind.

    Reuses the unchanged Core V0 seam for router + context (so the payload
    stays schema-stable) and only swaps the action to ``answer_only`` - the
    same honesty-gate pattern as the existing read-only kinds. The decision's
    validator keeps ``appliedVisibleEffect`` forced to False.
    """
    from packages.generation.orchestration.openclaw import OpenClawDecision

    base = _decide(message, site_id=site_id, base_run_id=base_run_id)
    return OpenClawDecision(
        router=base.router,
        context=base.context,
        action="answer_only",
        answer=_CONVERSATION_DECISION_ANSWERS[conversation.conversationKind],
        rationale=(
            f"conversation/{conversation.conversationKind}: dispatchern "
            "(router-rollen) svarar i chatten, ingen build (F1 slice 2)."
        ),
    )


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
    """Return the read-only OpenClaw follow-up decision for ``message`` as JSON.

    F1 slice 2 (additive): the payload carries a ``conversation`` metadata
    block (conversationKind + owning role), and a conversation kind
    (small_talk / site_opinion / question) is emitted as an honest
    answer-only decision instead of e.g. a clarification. Everything else -
    edits included - keeps the exact same decision as before.
    """
    conversation = _classify_conversation(message, site_id=site_id)
    if conversation.conversationKind in _ANSWER_ONLY_CONVERSATION_KINDS:
        decision = _conversation_answer_decision(
            message, conversation, site_id=site_id, base_run_id=base_run_id
        )
    else:
        decision = _decide(message, site_id=site_id, base_run_id=base_run_id)
    payload = decision.model_dump()
    payload["conversation"] = _conversation_metadata(conversation)
    return json.dumps(payload, ensure_ascii=False)


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
        {"decision": <OpenClawDecision + conversation metadata>,
         "bridge": {status, applied, previewShouldRefresh, chain}}

    F1 slice 2 (conductor wiring): the conversation classification runs FIRST.
    A conversation kind (small_talk / site_opinion / question) stops here with
    an honest answer-only decision - the chain is never imported, no version
    is written, no render runs (the same honesty gate as the read-only kinds).
    An edit keeps the EXACT flow below unchanged; its owning role is attached
    as ``conversation`` metadata only.
    """
    conversation = _classify_conversation(message, site_id=site_id)
    bridge: dict[str, object] = {
        "status": "no_build_needed",
        "applied": False,
        "previewShouldRefresh": False,
        "chain": None,
    }
    if conversation.conversationKind in _ANSWER_ONLY_CONVERSATION_KINDS:
        decision = _conversation_answer_decision(
            message, conversation, site_id=site_id, base_run_id=base_run_id
        )
        decision_payload = decision.model_dump()
        decision_payload["conversation"] = _conversation_metadata(conversation)
        return json.dumps(
            {"decision": decision_payload, "bridge": bridge},
            ensure_ascii=False,
        )

    decision = _decide(message, site_id=site_id, base_run_id=base_run_id)
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
    decision_payload = decision.model_dump()
    decision_payload["conversation"] = _conversation_metadata(conversation)
    return json.dumps(
        {"decision": decision_payload, "bridge": bridge},
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
