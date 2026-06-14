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
    - READ-ONLY. Prints the payload JSON as the final stdout line behind the
      ``OPENCLAW_BRIDGE_JSON:`` sentinel prefix (B174 contract with
      apps/viewser/lib/openclaw-runner.ts); no disk write, no build, no
      preview, no shell, no ``current.json`` mutation.
    - DETERMINISTIC-FIRST. ``classify_message`` (KÖR-6a) + the pure ``decide``.
      Since 2026-06-11 the router half MAY escalate an ambiguous message
      (unclear / long / complex multi-intent - ``needs_llm_fallback``) to
      ``routerModel`` (KÖR-6b), exactly as the chain in build_site.py already
      does. A confident heuristic decision never calls the LLM, without
      ``OPENAI_API_KEY`` the fallback IS the heuristic (no-key parity), and
      ``OPENCLAW_ROUTER_LLM_FALLBACK=0`` restores the pure-heuristic mode.
      The message is classified ONCE per invocation (the conversation layer
      and Core V0 share the same RouterDecision), so an escalated message
      costs at most ONE model call.
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

# B174: the stable stdout contract line apps/viewser/lib/openclaw-runner.ts
# scans for. With --apply the KÖR-7 chain (scripts/build_site.build) prints
# human progress ("runId: ...", "Copying starter ...", npm output) to the SAME
# stdout BEFORE the payload, so emitting bare JSON made the runner's blind
# JSON.parse throw on every successful apply (-> /api/prompt's B164 recovery
# forced an unearned degraded status). main() therefore emits the payload as
# the FINAL stdout line behind this sentinel prefix; the TS runner looks for
# it first and keeps a backwards bare-JSON line scan for the old format.
# Keep this literal in sync with BRIDGE_SENTINEL_PREFIX in openclaw-runner.ts.
BRIDGE_SENTINEL_PREFIX = "OPENCLAW_BRIDGE_JSON:"

# The conductor conversation kinds the dispatcher answers itself (F1 slice 2).
# ``edit`` keeps the unchanged chain flow and ``other`` falls through to the
# existing OpenClaw Core V0 mapping - only these three stop with an answer.
# Kept as a local literal so this seam stays import-light (the packages import
# is deferred), but it MUST equal ``ANSWER_ONLY_CONVERSATION_KINDS`` in
# packages/generation/orchestration/openclaw/roles.py (the single source of
# truth for ``ConversationDecision.expectsAnswer``); a lockstep test asserts it.
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


# KÖR-6b in the bridge (2026-06-11): the router half may escalate ambiguous
# messages to routerModel. Kill-switch (same off-tokens as the repo's other
# boolean envs); default ON because the chain (run_followup_chain) already
# escalates - the bridge gate staying regex-only just made the two halves
# disagree on exactly the ambiguous messages the fallback exists for.
#
# Resolution order mirrors apps/viewser's openaiEnv + backoffice env_panel:
# process env wins, then the repo-root ``.env`` (single-key parse, never
# mutating os.environ), then the default (on). The .env fallback is what makes
# the backoffice toggle (Dirigentpult flik B) take effect on the NEXT
# follow-up: every follow-up spawns a fresh bridge process, so a .env edit is
# picked up per spawn - UNLESS the variable was already in the spawning
# server's process env (then a dev-server restart is needed; the UI says so).
_ROUTER_FALLBACK_ENV = "OPENCLAW_ROUTER_LLM_FALLBACK"
_ENV_OFF_VALUES = frozenset({"0", "false", "no", "off"})
_REPO_DOTENV_PATH = REPO_ROOT / ".env"


def _read_repo_dotenv_value(name: str, dotenv_path: Path | None = None) -> str | None:
    """Minimal repo-root ``.env`` parse for ONE key (never mutates os.environ).

    Mirrors ``backoffice/env_panel.py:_read_repo_dotenv_value`` (kept local on
    purpose: scripts/ must not import backoffice). Simple KEY=VALUE lines,
    ``#`` comments ignored, surrounding quotes stripped, last assignment wins.
    Never throws: a missing/unreadable file yields None.
    """
    import re

    path = dotenv_path or _REPO_DOTENV_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    value: str | None = None
    pattern = re.compile(r"^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*)\s*$")
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = pattern.match(line)
        if match and match.group(1) == name:
            raw = match.group(2).strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
                raw = raw[1:-1]
            value = raw or None
    return value


def _router_fallback_enabled() -> bool:
    import os

    value = os.environ.get(_ROUTER_FALLBACK_ENV)
    if value is None:
        value = _read_repo_dotenv_value(_ROUTER_FALLBACK_ENV)
    return (value or "").strip().lower() not in _ENV_OFF_VALUES


def _classify_router(message: str, *, site_id: str | None):
    """The ONE router classification per CLI invocation (KÖR-6a/6b).

    Both layers (the conductor conversation labelling and the Core V0
    decision) compose THIS decision, so an escalated message costs at most
    one routerModel call - never one per layer. With the kill-switch off (or
    no ``OPENAI_API_KEY``) this is exactly the deterministic KÖR-6a heuristic.
    """
    from packages.generation.orchestration.router import (
        RouterContext,
        classify_message,
        classify_message_with_llm_fallback,
    )

    router_context = RouterContext(siteId=site_id) if site_id else None
    if _router_fallback_enabled():
        return classify_message_with_llm_fallback(message, context=router_context)
    return classify_message(message, context=router_context)


def _classify_conversation(message: str, *, site_id: str | None, router=None):
    """Run the slice-1 conductor classification (deterministic labelling).

    Deferred import for the same import-light reason as ``_decide``. The
    classification composes the unchanged router; the shared ``router``
    decision from ``_classify_router`` is injected so the message is never
    classified twice. ``model_fallback`` mirrors the bridge switch so the
    decision's ``source`` label reports honestly how routing was produced.
    """
    from packages.generation.orchestration.openclaw import classify_conversation
    from packages.generation.orchestration.router import RouterContext

    router_context = RouterContext(siteId=site_id) if site_id else None
    return classify_conversation(
        message,
        context=router_context,
        model_fallback=_router_fallback_enabled(),
        router=router,
    )


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
        # F1 slice 3 (Scout #262): explicit "expects a chat answer, not a build"
        # signal so /api/prompt + use-followup-build + floating-chat can
        # short-circuit answer-only without inferring it from "no runId".
        "expectsAnswer": conversation.expectsAnswer,
        "source": conversation.source,
        "rationale": conversation.rationale,
    }


def _conversation_answer_decision(
    message: str,
    conversation,
    *,
    site_id: str | None,
    base_run_id: str | None,
    router=None,
):
    """Build the honest answer-only decision for a conversation kind.

    Reuses the unchanged Core V0 seam for router + context (so the payload
    stays schema-stable) and only swaps the action to ``answer_only`` - the
    same honesty-gate pattern as the existing read-only kinds. The decision's
    validator keeps ``appliedVisibleEffect`` forced to False.
    """
    from packages.generation.orchestration.openclaw import OpenClawDecision

    base = _decide(
        message, site_id=site_id, base_run_id=base_run_id, router=router
    )
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


def _latest_run_id(site_id: str) -> str | None:
    """Resolve the site's newest completed run id, read-only (B182).

    /api/prompt normally sends NO ``baseRunId`` (only "Iterera från denna"
    does), so without this lookup a site_opinion/site_review question got an
    EMPTY context payload despite runs on disk - the operator was told "jag
    kan inte se sajten". Reuses the shared stdlib helper from B173
    (``latest_run_dir_for_site``) against ``ContextPaths().runs`` so the
    ``VIEWSER_RUNS_DIR`` override is honoured; only ``build-result.json``
    files are read and nothing is ever written.
    """
    from packages.generation.followup.hero_headline_pin import (
        latest_run_dir_for_site,
    )
    from packages.generation.orchestration.context import ContextPaths

    run_dir = latest_run_dir_for_site(ContextPaths().runs, site_id)
    return run_dir.name if run_dir is not None else None


def _decide(
    message: str,
    *,
    site_id: str | None,
    base_run_id: str | None,
    router=None,
):
    """Run OpenClaw Core V0 read-only and return the ``OpenClawDecision``.

    Deferred import keeps the package dependency inside the function (mirrors
    ``scripts/classify_message.py`` / ``scripts/dev_generate.py``) so the module
    stays import-light and ruff-clean. The shared ``router`` decision from
    ``_classify_router`` is injected into ``orchestrate`` so the message is
    never classified twice per invocation.
    """
    from packages.generation.orchestration.openclaw import orchestrate
    from packages.generation.orchestration.router import RouterContext

    router_context = RouterContext(siteId=site_id) if site_id else None
    context_kwargs: dict[str, object] = {}
    if site_id:
        context_kwargs["site_id"] = site_id
    if base_run_id is None and site_id:
        # B182: auto-resolve the latest completed run (read-only) so a
        # site-scoped question without an explicit baseRunId still gets a
        # populated context. No runs on disk -> the assembler keeps today's
        # honest empty context + missing-run_id note.
        base_run_id = _latest_run_id(site_id)
    if base_run_id:
        # The context level is taken from the router; run_id only matters when
        # the router asks for site/run context. Forwarded verbatim (read-only).
        context_kwargs["run_id"] = base_run_id
    return orchestrate(
        message, router_context=router_context, router=router, **context_kwargs
    )


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
    router = _classify_router(message, site_id=site_id)
    conversation = _classify_conversation(
        message, site_id=site_id, router=router
    )
    if conversation.conversationKind in _ANSWER_ONLY_CONVERSATION_KINDS:
        decision = _conversation_answer_decision(
            message,
            conversation,
            site_id=site_id,
            base_run_id=base_run_id,
            router=router,
        )
    else:
        decision = _decide(
            message, site_id=site_id, base_run_id=base_run_id, router=router
        )
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
    router = _classify_router(message, site_id=site_id)
    conversation = _classify_conversation(
        message, site_id=site_id, router=router
    )
    bridge: dict[str, object] = {
        "status": "no_build_needed",
        "applied": False,
        "previewShouldRefresh": False,
        "chain": None,
    }
    if conversation.conversationKind in _ANSWER_ONLY_CONVERSATION_KINDS:
        decision = _conversation_answer_decision(
            message,
            conversation,
            site_id=site_id,
            base_run_id=base_run_id,
            router=router,
        )
        decision_payload = decision.model_dump()
        decision_payload["conversation"] = _conversation_metadata(conversation)
        return json.dumps(
            {"decision": decision_payload, "bridge": bridge},
            ensure_ascii=False,
        )

    decision = _decide(
        message, site_id=site_id, base_run_id=base_run_id, router=router
    )
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
    # Deferred import keeps this module import-light; scripts.cli_text only
    # pulls in pathlib.
    from scripts.cli_text import resolve_cli_text

    parser = argparse.ArgumentParser(
        description=(
            "Emit a read-only OpenClaw follow-up decision (answer_only / "
            "clarification / plan_only / patch_plan_request) as schema-stable "
            "JSON. Deterministic-first KÖR-6a router (ambiguous messages may "
            "escalate to routerModel, KÖR-6b; OPENCLAW_ROUTER_LLM_FALLBACK=0 "
            "disables) + OpenClaw Core V0; no build, no preview."
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
        "--message-file",
        default=None,
        help=(
            "Path to a UTF-8 file holding the follow-up message. Preferred "
            "over the positional arg so a non-ASCII leading character survives "
            "the viewser→CLI boundary intact (B204). Mutually exclusive with "
            "the positional message."
        ),
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="The follow-up message. Prefer --message-file (B204) or `--`.",
    )
    args = parser.parse_args()

    # B204: the message arrives via --message-file (a UTF-8 temp file) so a
    # non-ASCII leading character survives the viewser→CLI boundary. The
    # positional arg stays supported for back-compat (tests, the hosted
    # sandbox env path, `--` callers).
    try:
        message = resolve_cli_text(args.message, args.message_file, label="message")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.apply:
        if not args.site_id:
            print("--apply requires --site-id.", file=sys.stderr)
            return 1
        payload = apply_followup_to_json(
            message,
            site_id=args.site_id,
            base_run_id=args.base_run_id,
            do_build=not args.skip_build,
        )
        # B174: the chain above may have printed build progress to stdout;
        # the sentinel line marks which line IS the contract payload.
        print(f"{BRIDGE_SENTINEL_PREFIX} {payload}")
        return 0

    payload = decide_to_json(
        message,
        site_id=args.site_id,
        base_run_id=args.base_run_id,
    )
    print(f"{BRIDGE_SENTINEL_PREFIX} {payload}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
