"""Conductor agent-role contracts + conversation classification (F1, slice 1).

This module gives the OpenClaw conductor two things, as data + code, on top
of the existing in-repo engine. It adds no new engine, no Docker/gateway and
no free file patching: a role *understands and proposes*; the deterministic
apply chain *validates and applies* (conductor principle from
docs/heavy-llm-flow/openclaw-2.0-conductor.md).

1. Role contracts (``ROLE_CONTRACTS`` + ``RoleContract``)
   The conductor roles the plan names - ``router``, ``section_builder``,
   ``stylist``, ``copy`` and ``component_builder`` - locked as immutable, typed
   dataclasses. Each contract states, as data, which router ``EditKind`` values
   the role consumes (input) and which directive kinds it may emit (output):
   ``section_add`` -> ``section_builder``, ``visual_style`` -> ``stylist``,
   ``copy_change`` -> ``copy``, ``component_add`` -> ``component_builder`` (ADR
   0057, partial/mount-only). The ``router`` role is the dispatcher and produces
   a routing decision, never a directive.

2. Conversation classification (``classify_conversation``)
   An ADDITIVE, conductor-level extension of the router's ``messageKind``. It
   runs the deterministic router first, keeps every existing edit
   classification verbatim (``conversationKind == "edit"`` whenever the router
   found an edit), and additionally labels non-edit conversation intents
   (small talk / jokes, site opinions, plain questions) so the conductor can
   answer chit-chat without a build. It never mutates the router's locked
   eight-kind contract or ``governance/schemas/router-decision.schema.json``;
   it composes the router, exactly like ``core.decide`` does.

No-key parity (same pattern as briefModel): classification is deterministic
and works with ``OPENAI_API_KEY`` absent. The optional ``model_fallback`` flag
routes only the router half through the existing ``routerModel`` fallback
(``classify_message_with_llm_fallback``, which is itself identical to the
heuristic without a key); the conversation mapping always stays deterministic.
``ConversationDecision.source`` reports ``mock-no-key`` when no key is set,
mirroring briefModel's ``briefSource=mock-no-key`` marker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..router import (
    classify_message,
    classify_message_with_llm_fallback,
    has_openai_api_key,
)
from ..router.models import (
    ContextLevel,
    EditKind,
    MessageKind,
    RouterContext,
    RouterDecision,
)

__all__ = [
    "ANSWER_ONLY_CONVERSATION_KINDS",
    "ConversationDecision",
    "ConversationKind",
    "ROLE_CONTRACTS",
    "Role",
    "RoleContract",
    "RoleDirectiveKind",
    "SECTION_ADD_SKILL",
    "classify_conversation",
    "contract_for_role",
    "role_for_edit_kind",
    "skill_for_edit_kind",
]

# ---------------------------------------------------------------------------
# Role contract types (data, not behaviour)
# ---------------------------------------------------------------------------

# The conductor roles named in the conductor plan. ``router`` dispatches; the
# editing roles each own exactly one editing directive. ``component_builder``
# (ADR 0057) owns ``component_add`` as a partial, mount-only role: it answers
# from the Component Catalog or does an honest no-op pointing at the intake CLI;
# it mounts nothing and writes no files in this slice. ``route_editor`` (Route/
# Nav Mutation V1, ADR 0060) owns ``route_remove``: it removes a whole
# non-required page + its nav link via a structured directive (disabledRoutes),
# no dossier and no free file patch.
Role = Literal[
    "router", "section_builder", "stylist", "copy", "component_builder",
    "route_editor",
]

# Directive kinds a role may produce. These mirror the editing ``EditKind``
# values an owning role exists for; the router role itself emits no directive.
RoleDirectiveKind = Literal[
    "section_add", "visual_style", "copy_change", "component_add", "route_remove"
]


@dataclass(frozen=True)
class RoleContract:
    """Immutable input/output contract for one conductor agent role.

    The contract is data, not an executor: it locks what a role is allowed to
    consume (``acceptsEditKinds`` - the router ``EditKind`` values it handles)
    and produce (``producesDirectives`` - the directive kinds it may emit),
    plus the minimum context level it needs and an honest maturity status.
    Frozen so a caller can read the contract but never mutate it at runtime.

    ``mountOnly`` means mount-only BY DEFAULT; ``visibleTypes`` lists the
    exceptions that render visibly. Both mirror the operational truth in
    ``docs/openclaw-workspace/action-registry.json`` and are cross-validated
    by ``tests/test_openclaw_registry_consistency.py`` so the two surfaces
    can never drift apart again (audit 2026-06-11).
    """

    role: Role
    acceptsEditKinds: tuple[EditKind, ...]
    producesDirectives: tuple[RoleDirectiveKind, ...]
    contextLevel: ContextLevel
    status: Literal["supported", "partial", "planned"]
    mountOnly: bool
    skill: str
    summary: str
    visibleTypes: tuple[str, ...] = ()

    def accepts(self, edit_kind: str) -> bool:
        """True when this role handles ``edit_kind`` as input."""
        return edit_kind in self.acceptsEditKinds

    def produces(self, directive_kind: str) -> bool:
        """True when this role is allowed to emit ``directive_kind``."""
        return directive_kind in self.producesDirectives


# The locked registry of conductor role contracts. Grounded in the existing
# action registry (docs/openclaw-workspace/action-registry.json) and the
# conductor plan's role table; reuses the engine, invents no new capability.
ROLE_CONTRACTS: dict[Role, RoleContract] = {
    "router": RoleContract(
        role="router",
        acceptsEditKinds=(),
        producesDirectives=(),
        contextLevel="none",
        status="supported",
        mountOnly=False,
        skill="",
        summary=(
            "Conductor dispatcher: classifies a follow-up into a router "
            "messageKind and a conductor conversationKind, and selects the "
            "editing role for an edit. Produces a routing decision, never a "
            "directive."
        ),
    ),
    "section_builder": RoleContract(
        role="section_builder",
        acceptsEditKinds=("section_add",),
        producesDirectives=("section_add",),
        contextLevel="artifacts_plus_sections",
        status="supported",
        mountOnly=True,
        skill="skills/section-add/SKILL.md",
        summary=(
            "Mounts a sanctioned section's capability + dossier through the "
            "existing apply chain. Mount-only by default; the types in "
            "visibleTypes (mirrored from action-registry.json, the "
            "operational truth) render visibly on the local-service-business "
            "scaffold via a grounded dedicated route. An unknown type is an "
            "honest no-op, never an invented section."
        ),
        visibleTypes=("faq", "team"),
    ),
    "stylist": RoleContract(
        role="stylist",
        acceptsEditKinds=("visual_style",),
        producesDirectives=("visual_style",),
        contextLevel="artifacts",
        status="supported",
        mountOnly=False,
        skill="skills/restyle/SKILL.md",
        summary=(
            "Interprets a free or compound style follow-up into a validated "
            "theme mutation (brand colour, accent, font, tone) via "
            "theme_directives + the shared colour lexicon."
        ),
    ),
    "copy": RoleContract(
        role="copy",
        acceptsEditKinds=("copy_change",),
        producesDirectives=("copy_change",),
        contextLevel="artifacts",
        status="supported",
        mountOnly=False,
        skill="skills/copy-change/SKILL.md",
        summary=(
            "Rewrites name/tagline/about/services copy via copyDirective - "
            "LLM-understood, with deterministic grounding/leak/schema guards."
        ),
    ),
    "component_builder": RoleContract(
        role="component_builder",
        acceptsEditKinds=("component_add",),
        producesDirectives=("component_add",),
        contextLevel="component_registry",
        status="partial",
        mountOnly=True,
        skill="skills/component-add/SKILL.md",
        summary=(
            "Owns the component_add edit kind (ADR 0057), grounded in the "
            "Component Catalog (ADR 0040: capability-map components + per-Starter "
            "component-manifest). In this slice it is PARTIAL and mount-only: a "
            "component_add follow-up gets a catalog-grounded answer or an HONEST "
            "no-op that points at the curated shadcn intake CLI "
            "(scripts/component_intake.py). It mounts nothing and writes no files; "
            "the existing chain reports the honest no-op via "
            "unappliedFollowupIntents. Vendoring a new component stays an operator "
            "PR (intake -> review -> Starter), never a runtime mount."
        ),
    ),
    "route_editor": RoleContract(
        role="route_editor",
        acceptsEditKinds=("route_remove",),
        producesDirectives=("route_remove",),
        contextLevel="artifacts_plus_sections",
        status="supported",
        mountOnly=False,
        skill="skills/route-remove/SKILL.md",
        summary=(
            "Owns the route_remove edit kind (Route/Nav Mutation V1, ADR 0060). "
            "Removes a whole non-required page + its header/footer nav link via a "
            "structured directive (directives.disabledRoutes), NOT a dossier and "
            "NOT a free file patch. route_directives validates the routeId against "
            "THIS site's scaffold + the required-page guard; apply records the "
            "STICKY disabledRoutes list; build_site computes activeRoutes = "
            "scaffold defaultRoutes minus disabledRoutes in one seam. An unknown "
            "or required page is an HONEST no-op, never a faked removal. Slice A "
            "keeps required pages (home/services/contact); contact removal + "
            "CTA-retarget is Slice B."
        ),
    ),
}

# Router EditKind -> the role that owns its directive. The editing roles plus
# component_builder (ADR 0057, partial/mount-only) and route_editor (ADR 0060,
# route_remove) are mapped; the remaining router edit kinds (component_remove,
# layout_change, route_add, none) are not owned by a role in this slice.
_ROLE_BY_EDIT_KIND: dict[EditKind, Role] = {
    "section_add": "section_builder",
    "visual_style": "stylist",
    "copy_change": "copy",
    "component_add": "component_builder",
    "route_remove": "route_editor",
}


def contract_for_role(role: Role) -> RoleContract:
    """Return the locked ``RoleContract`` for ``role``."""
    return ROLE_CONTRACTS[role]


def role_for_edit_kind(edit_kind: str) -> Role | None:
    """Return the role that owns ``edit_kind``'s directive, or None.

    Honest about the current surface: section_add -> section_builder,
    visual_style -> stylist, copy_change -> copy, component_add ->
    component_builder (ADR 0057, partial/mount-only), route_remove ->
    route_editor (ADR 0060). Any other edit kind (component_remove,
    layout_change, route_add, none) returns None because no role in this slice
    produces its directive yet.
    """
    return _ROLE_BY_EDIT_KIND.get(edit_kind)  # type: ignore[arg-type]


# F1 slice 3: the skill the section_builder role runs, read FROM the locked
# contract (not hardcoded) so the chain's dispatch key can never drift from
# ``ROLE_CONTRACTS``. ``run_followup_chain`` selects the section-add handling by
# comparing ``skill_for_edit_kind(edit_kind)`` against this value, which is what
# makes the classified ROLE (not the raw editKind) authoritative for dispatch.
SECTION_ADD_SKILL: str = ROLE_CONTRACTS["section_builder"].skill


def skill_for_edit_kind(edit_kind: str | None) -> str | None:
    """Return the SKILL.md path the owning role runs for ``edit_kind``.

    The conductor's bridge from a router ``EditKind`` to the skill that handles
    it: it resolves the owning role via ``role_for_edit_kind`` and reads that
    role's ``RoleContract.skill``. The role *selects* the skill; the
    deterministic apply chain still validates and applies (conductor principle).

    Returns ``None`` when ``edit_kind`` is missing/``"none"``, when no role owns
    the kind (component_remove, layout_change, route_add), or when the owning
    role declares no skill (the router dispatcher). ``component_add`` resolves to
    the ``component_builder`` skill (ADR 0057); ``route_remove`` resolves to the
    ``route_editor`` skill (ADR 0060). Defensive on purpose: ``decision.editKind``
    can be ``"none"``, so this accepts ``str | None`` and never raises.
    """
    if not edit_kind or edit_kind == "none":
        return None
    role = role_for_edit_kind(edit_kind)
    if role is None:
        return None
    skill = ROLE_CONTRACTS[role].skill
    return skill or None


# ---------------------------------------------------------------------------
# Conversation classification (additive extension of router messageKind)
# ---------------------------------------------------------------------------

# Conductor-level conversation intents. Distinct from the router's locked
# eight-kind ``MessageKind`` on purpose: this never edits that enum or its
# schema. ``edit`` is the passthrough that preserves every router edit verbatim.
ConversationKind = Literal[
    "small_talk",
    "site_opinion",
    "question",
    "edit",
    "other",
]

# The conversation kinds the dispatcher (router role) answers in chat WITHOUT a
# build - the honest answer-only gate. ``ConversationDecision.expectsAnswer`` is
# True iff ``conversationKind`` is one of these. This is the single source of
# truth mirrored by ``_ANSWER_ONLY_CONVERSATION_KINDS`` in
# scripts/run_openclaw_followup.py and ``CONVERSATION_ANSWER_KINDS`` in
# apps/viewser/app/api/prompt/route.ts. ``edit`` keeps the unchanged chain flow
# and ``other`` falls through to the existing OpenClaw Core V0 mapping.
ANSWER_ONLY_CONVERSATION_KINDS: tuple[ConversationKind, ...] = (
    "small_talk",
    "site_opinion",
    "question",
)

# Small talk / jokes / greetings / chit-chat. Swedish-first, a few English cues.
_SMALL_TALK_CUES = (
    "skämt", "skämta", "skoja", "skojar", "dra ett skämt", "berätta ett skämt",
    "något roligt", "nåt roligt", "rolig grej", "haha", "hahaha", "lol",
    "hej", "hejsan", "tjena", "tjenare", "tja", "hallå", "god morgon",
    "godmorgon", "läget", "hur är läget", "hur mår du", "hur går det",
    "vad heter du", "vem är du", "småprata", "snacka lite", "prata lite",
    "kul att prata", "trevligt att", "hello", "joke", "tell me a joke",
)

# Opinion / omdöme cues (paired with a site word below to mean site_opinion).
_OPINION_CUES = (
    "tycker", "tycka", "tänker du", "åsikt", "åsikter", "omdöme", "omdömen",
    "feedback", "vad tror du", "gillar du", "anser du", "betygsätt", "betyg",
    "snygg", "snyggt", "ful", "fult", "bra ut", "dålig", "dåligt", "intryck",
)

# Words that mean "the current site" for the opinion branch (broader than the
# router's _SITE_REFS so an indefinite "min hemsida" / "det här" also counts).
_SITE_WORDS = (
    "sajt", "sajten", "sida", "sidan", "hemsida", "hemsidan", "webbplats",
    "webbplatsen", "webbsida", "webbsidan", "site", "den här", "det här",
    "designen", "layouten", "startsidan",
)


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip().lower())


def _contains_word(text: str, phrase: str) -> bool:
    return (
        re.search(r"(?<![\wåäö])" + re.escape(phrase) + r"(?![\wåäö])", text)
        is not None
    )


def _any_word(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_word(text, p) for p in phrases)


def _primary_edit_kind(router: RouterDecision) -> EditKind | None:
    """Return the edit kind to preserve, or None for a non-edit message.

    A single edit_instruction reports its own ``editKind``; a multi_intent
    reports its first actionable subtask's editKind. Anything else (questions,
    reviews, references, discovery, unclear) is not an edit here, so the
    conversation layer is free to label it - existing edit classifications are
    never reinterpreted as conversation.
    """
    if router.messageKind == "edit_instruction" and router.editKind != "none":
        return router.editKind
    if router.messageKind == "multi_intent":
        for subtask in router.subtasks:
            if subtask.editKind != "none":
                return subtask.editKind
    return None


def _source_label(model_fallback: bool) -> str:  # noqa: FBT001
    """Report the classification source, mirroring briefModel's marker.

    ``mock-no-key`` when no usable ``OPENAI_API_KEY`` is set (same string
    briefModel writes as ``briefSource``); otherwise ``heuristic`` for the
    pure deterministic path, or ``router-llm-fallback`` when the router half
    was allowed to escalate to ``routerModel``.
    """
    if not has_openai_api_key():
        return "mock-no-key"
    return "router-llm-fallback" if model_fallback else "heuristic"


@dataclass(frozen=True)
class ConversationDecision:
    """Conductor classification that EXTENDS the router's messageKind.

    Additive only: ``messageKind`` and ``editKind`` are carried straight from
    the deterministic router (the single classification truth), and
    ``conversationKind`` is the conductor's added label. ``role`` is the
    editing role for an edit (or None when no role owns it), and ``router`` for
    a conversation the dispatcher answers itself. ``expectsAnswer`` is the
    explicit "this turn expects a chat answer, not a build" signal (True iff
    ``conversationKind`` is one of ``ANSWER_ONLY_CONVERSATION_KINDS``) that the
    seam threads to /api/prompt + the UI so they can short-circuit answer-only
    without a build (Scout #262). ``source`` reports no-key parity;
    ``rationale`` is a short trace line, never customer copy.
    """

    conversationKind: ConversationKind
    role: Role | None
    messageKind: MessageKind
    editKind: EditKind
    expectsAnswer: bool
    source: str
    rationale: str


def classify_conversation(
    message: str,
    *,
    context: RouterContext | None = None,
    model_fallback: bool = False,  # noqa: FBT001, FBT002
    router: RouterDecision | None = None,
) -> ConversationDecision:
    """Classify a follow-up into a conductor ``ConversationDecision``.

    Runs the deterministic router first and preserves every edit verbatim
    (an edit -> ``conversationKind == "edit"`` with the owning role). For a
    non-edit message it adds a conversation label - small talk/jokes,
    site opinions, plain questions, or ``other`` - so the conductor can answer
    chit-chat without a build. Pure and deterministic; identical with or
    without ``OPENAI_API_KEY`` (the optional ``model_fallback`` only lets the
    router half consult ``routerModel``, which is itself no-key safe).

    ``router`` (additive, KÖR-6b bridge wiring): a caller that ALREADY ran the
    router injects its decision so the message is never classified twice (and
    an escalated message never costs two model calls). The conversation
    labelling on top stays deterministic either way; ``model_fallback`` then
    only reports HOW the injected decision was produced (the ``source`` label).

    Branch order matters (B181): a ``bug_report`` / ``reference_analysis``
    is guarded to ``other`` right after the edit passthrough (those kinds
    have their own downstream handling and must never be relabelled by a
    greeting or a trailing question mark), and the site-opinion branch runs
    BEFORE the small-talk branch so a polite "hej, vad tycker du om sajten?"
    keeps its site context instead of being answered as chit-chat.
    """
    ctx = context or RouterContext()
    if router is None:
        router = (
            classify_message_with_llm_fallback(message, context=ctx)
            if model_fallback
            else classify_message(message, context=ctx)
        )

    raw = message or ""
    text = _normalize(raw)
    source = _source_label(model_fallback)

    # 1. Edit wins: a real edit is never reinterpreted as conversation.
    edit_kind = _primary_edit_kind(router)
    if edit_kind is not None:
        role = role_for_edit_kind(edit_kind)
        return ConversationDecision(
            conversationKind="edit",
            role=role,
            messageKind=router.messageKind,
            editKind=edit_kind,
            # An edit is built (or honestly no-op'd) by the chain, never a chat
            # answer - so the dispatcher does not expect to answer it.
            expectsAnswer=False,
            source=source,
            rationale=(
                f"Router edit ({router.messageKind}/{edit_kind}) preserved as "
                f"conversationKind=edit"
                + (f", role={role}." if role else ", no role owns it yet.")
            ),
        )

    # 2. Guard (B181): bug_report / reference_analysis have their own
    #    downstream handling (plan_only in OpenClaw Core V0) and must never be
    #    relabelled as chit-chat or a plain question just because the operator
    #    greeted ("hallå, sidan funkar inte") or ended with a question mark.
    if router.messageKind in ("bug_report", "reference_analysis"):
        return _conversation(
            "other", router,
            f"Non-edit router kind ({router.messageKind}) with dedicated "
            "downstream handling - never relabelled by greeting/question mark.",
            source,
        )

    # 3. Opinion / omdöme about the site. Checked BEFORE small talk (B181) so
    #    a greeting + opinion ("hej, vad tycker du om sajten?") keeps its site
    #    context instead of being answered as chit-chat.
    if router.messageKind == "site_review" or (
        _any_word(text, _OPINION_CUES) and _any_word(text, _SITE_WORDS)
    ):
        return _conversation(
            "site_opinion", router,
            "Opinion/omdöme about the current site - answer from artefacts, "
            "no build.",
            source,
        )

    # 4. Small talk / jokes / greetings.
    if _any_word(text, _SMALL_TALK_CUES):
        return _conversation(
            "small_talk", router,
            "Chit-chat/joke - the dispatcher answers, no build.",
            source,
        )

    # 5. Plain question (router answer/discovery, or a literal '?').
    if router.messageKind in ("answer_only", "component_discovery") or raw.strip().endswith("?"):
        return _conversation(
            "question", router,
            "Question - the dispatcher answers, no build.",
            source,
        )

    # 6. Other (unclear, ...).
    return _conversation(
        "other", router,
        f"Non-edit, non-conversational router kind ({router.messageKind}) - "
        "handled outside the conversation labels.",
        source,
    )


def _conversation(
    kind: ConversationKind,
    router: RouterDecision,
    rationale: str,
    source: str,
) -> ConversationDecision:
    """Build a non-edit ``ConversationDecision`` (answered by the dispatcher)."""
    return ConversationDecision(
        conversationKind=kind,
        role="router",
        messageKind=router.messageKind,
        editKind=router.editKind,
        # The dispatcher answers small_talk/site_opinion/question in chat (no
        # build); ``other`` (bug_report/reference/unclear) has its own
        # downstream handling and is not a chat answer here.
        expectsAnswer=kind in ANSWER_ONLY_CONVERSATION_KINDS,
        source=source,
        rationale=rationale,
    )
