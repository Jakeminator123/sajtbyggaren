"""OpenClaw Core V0 - bind router + context into one transient decision (KÖR-o2).

``decide(router, context)`` is the whole of V0: it reads the deterministic
``RouterDecision`` (KÖR-6a) and the read-only ``AssembledContext`` (KÖR-7a)
the caller already produced, and picks exactly one of four actions per the
capability plan in docs/heavy-llm-flow/kor-o1-openclaw-core-contract.md:

    answer_only | clarification | plan_only | patch_plan_request

Hard guarantees (kor-o1 "Mål" + 04 §9), all structurally enforced:
- **Pure function.** ``decide`` takes two objects and returns one object.
  It performs no disk I/O, no build, no preview, no shell, no network - so
  it cannot write a file or touch ``current.json`` even by accident.
- **Mock-safe / deterministic.** No LLM and no ``OPENAI_API_KEY`` are used;
  the same (router, context) pair always yields the same decision. The
  router owns all classification (one router truth, kor-o1) - this module
  never re-classifies the message.
- **Honest.** An ``edit_instruction`` returns ``patch_plan_request`` with
  ``status="action_bridge_missing"`` / ``blockedBy="openclaw-action-bridge"``
  rather than a faked success, and ``appliedVisibleEffect`` is always ``False``.

``toolCalls`` / ``capability`` stay empty / ``None`` in V0 (the model
carries them for the later patch-flow slice; V0 never acts on them).

A thin ``orchestrate(message, ...)`` convenience wires the three tools
(``classify_message`` -> ``assemble_context`` -> ``decide``) for callers
that have a raw message; it is read-only because each tool is.
"""

from __future__ import annotations

from ..context import assemble_context
from ..context.models import AssembledContext
from ..router import RouterContext, classify_message
from ..router.models import RouterDecision
from .models import OpenClawDecision, PatchPlanRequest

__all__ = ["decide", "orchestrate"]


def decide(router: RouterDecision, context: AssembledContext) -> OpenClawDecision:
    """Compose ``router`` + ``context`` into a transient ``OpenClawDecision``.

    The mapping follows the kor-o1 capability plan. Classification is *not*
    redone here - ``router.messageKind`` is taken as the single source of
    truth. The function is pure: it returns a decision and changes nothing.
    """
    kind = router.messageKind

    # unclear, or any kind the router itself flagged as ambiguous, asks back.
    if kind == "unclear" or router.requiresClarification:
        return _clarification(router, context)

    if kind == "edit_instruction":
        return _patch_plan_request(router, context)

    if kind == "multi_intent":
        return _multi_intent(router, context)

    if kind == "component_discovery":
        return _discovery_answer(router, context)

    if kind == "reference_analysis":
        return _reference_plan(router, context)

    if kind == "bug_report":
        return _bug_report_plan(router, context)

    if kind == "site_review":
        return _site_review(router, context)

    # answer_only (and any future read-only kind) -> a plain answer.
    return _answer(router, context)


# ---------------------------------------------------------------------------
# Convenience: wire the three V0 tools together for a raw message.
# ---------------------------------------------------------------------------


def orchestrate(
    message: str,
    *,
    router_context: RouterContext | None = None,
    router: RouterDecision | None = None,
    **context_kwargs: object,
) -> OpenClawDecision:
    """Run ``classify_message`` -> ``assemble_context`` -> ``decide``.

    A read-only front door for callers that start from a raw message rather
    than a pre-built (router, context) pair. Every step is read-only:
    ``classify_message`` never touches disk, ``assemble_context`` only reads,
    and ``decide`` is pure. ``context_kwargs`` are forwarded verbatim to
    ``assemble_context`` (e.g. ``site_id=``, ``run_id=``, ``paths=``); the
    context level is taken from the router so the assembler fetches exactly
    what the router asked for and nothing more.

    ``router`` (additive, KÖR-6b bridge wiring): a caller that ALREADY ran the
    router - e.g. once per CLI invocation, possibly via the routerModel
    fallback - injects its decision here so the message is never classified
    twice (and an escalated message never costs two model calls). ``None``
    keeps the exact previous behaviour (deterministic ``classify_message``).
    One router truth either way: ``decide`` still never re-classifies.
    """
    if router is None:
        router = classify_message(message, context=router_context)
    # Forward an external reference URL so the assembler can fetch reference
    # context: assemble_context("external_reference") needs ``url`` (kor-7a),
    # otherwise an OpenClaw reference plan would be built on empty context.
    if (
        router.reference is not None
        and router.reference.url
        and "url" not in context_kwargs
    ):
        context_kwargs["url"] = router.reference.url
    context = assemble_context(router.contextLevel, **context_kwargs)  # type: ignore[arg-type]
    return decide(router, context)


# ---------------------------------------------------------------------------
# Per-action builders (deterministic, text derived only from router/context)
# ---------------------------------------------------------------------------


def _answer(router: RouterDecision, context: AssembledContext) -> OpenClawDecision:
    answer = (
        "Detta är en ren fråga som inte kräver någon ändring av sajten. "
        "OpenClaw Core V0 markerar den som answer_only och startar varken "
        "build eller preview; själva svarstexten produceras av svarsmodellen "
        "(ännu inte inkopplad i V0)."
    )
    return OpenClawDecision(
        router=router,
        context=context,
        action="answer_only",
        answer=answer,
        rationale="answer_only: ren fråga, ingen build (kor-o1 capability-plan).",
    )


def _discovery_answer(
    router: RouterDecision, context: AssembledContext
) -> OpenClawDecision:
    options = _available_options(context)
    if options:
        answer = "Tillgängliga val: " + ", ".join(options) + "."
    else:
        answer = (
            "Inga komponentval kunde läsas ur component_registry-kontexten "
            "(tom eller otillgänglig)."
        )
    return OpenClawDecision(
        router=router,
        context=context,
        action="answer_only",
        answer=answer,
        rationale="component_discovery: lista tillgängliga val, ingen build.",
    )


def _reference_plan(
    router: RouterDecision, context: AssembledContext
) -> OpenClawDecision:
    ref = router.reference.url if router.reference else "den angivna referensen"
    plan = [
        f"Analysera referensen {ref} på en hög nivå (struktur/känsla).",
        "Föreslå en egen variant som passar sajtens scaffold och varumärke.",
        "Kopiera aldrig exakt innehåll, layout eller tillgångar från referensen.",
    ]
    return OpenClawDecision(
        router=router,
        context=context,
        action="plan_only",
        plan=plan,
        rationale="reference_analysis: föreslå egen variant, kopiera aldrig exakt.",
    )


def _bug_report_plan(
    router: RouterDecision, context: AssembledContext
) -> OpenClawDecision:
    plan = [
        "Reproducera det rapporterade felet utifrån beskrivningen.",
        "Lokalisera den troliga orsaken i artefakter/manifest (read-only).",
        "Föreslå en åtgärd; faktisk patch/build sker först i patch-flödet.",
    ]
    return OpenClawDecision(
        router=router,
        context=context,
        action="plan_only",
        plan=plan,
        rationale="bug_report: föreslå felsökningsplan, ingen build i V0.",
    )


def _site_review(router: RouterDecision, context: AssembledContext) -> OpenClawDecision:
    # A review is an answer unless the router judged that a change is wanted
    # (buildRequirement beyond "none"), in which case V0 proposes a plan.
    if router.buildRequirement == "none":
        return OpenClawDecision(
            router=router,
            context=context,
            action="answer_only",
            answer=(
                "Granskning av sajten baserad på lästa artefakter (read-only). "
                "Detaljerad bedömning produceras av granskningsmodellen (ej "
                "inkopplad i V0); ingen ändring görs."
            ),
            rationale="site_review: svar/granskning, ingen build.",
        )
    return OpenClawDecision(
        router=router,
        context=context,
        action="plan_only",
        plan=[
            "Sammanfatta granskningens viktigaste observationer.",
            "Föreslå konkreta förbättringar; ingen ändring tillämpas i V0.",
        ],
        rationale="site_review: föreslå förbättringsplan, ingen build.",
    )


def _clarification(
    router: RouterDecision, context: AssembledContext
) -> OpenClawDecision:
    question = (
        "Jag är inte säker på vad du vill ändra eller fråga om. Kan du "
        "förtydliga vilken del av sajten det gäller och vad du vill uppnå?"
    )
    return OpenClawDecision(
        router=router,
        context=context,
        action="clarification",
        clarifyingQuestion=question,
        rationale="unclear: be om förtydligande, ingen build.",
    )


def _patch_plan_request(
    router: RouterDecision, context: AssembledContext
) -> OpenClawDecision:
    summary = _target_summary(router)
    return OpenClawDecision(
        router=router,
        context=context,
        action="patch_plan_request",
        # Novel-intent planeringssvar (coach-beslut 2026-06-15, ADR 0059-anda):
        # a clear edit V0 cannot auto-apply yet now gets a grounded, honest
        # "sa har skulle det kunna byggas" plan instead of a bare missing-bridge
        # dead-end. Derived ONLY from the router (decide stays pure, no LLM/I/O)
        # and it never claims the change was applied - patchPlanRequest stays the
        # honest action_bridge_missing marker and appliedVisibleEffect stays
        # False (#313). Replaces the curt special-case with conductor intelligence.
        plan=_edit_plan_steps(router, summary),
        patchPlanRequest=PatchPlanRequest(
            targetSummary=summary,
            status="action_bridge_missing",
            blockedBy="openclaw-action-bridge",
        ),
        rationale=(
            "edit_instruction: patch-planner -> apply -> targeted render finns "
            "(kor-7b/7c/7d), men OpenClaw-action-bryggan som kör dem från ett "
            "OpenClaw-beslut saknas - ärlig flagga + grundad plan, ingen falsk "
            "success."
        ),
    )


def _multi_intent(
    router: RouterDecision, context: AssembledContext
) -> OpenClawDecision:
    # Per-subtask handling, aggregated to one V0 action.
    plan = [_subtask_line(i, s) for i, s in enumerate(router.subtasks, start=1)]
    # Reference-gated multi_intent: if the router flagged an external reference,
    # a do-not-copy risk, or already chose plan_only, propose a reference/plan
    # first instead of jumping to a patch - kor-6a routes a reference multi-intent
    # to plan_only/do_not_copy_exact and OpenClaw must respect that gate so a
    # "lägg X som på example.com och ändra rubriken" goes to analysis first.
    if (
        router.reference is not None
        or router.risk == "do_not_copy_exact"
        or router.buildRequirement == "plan_only"
    ):
        return OpenClawDecision(
            router=router,
            context=context,
            action="plan_only",
            plan=plan,
            rationale=(
                "multi_intent med referens/plan_only: analysera referensen och "
                "föreslå en plan först, kopiera aldrig exakt (ingen patch)."
            ),
        )
    # Otherwise: if any subtask is an edit, the whole request needs the (still-
    # unbridged) patch path, so V0 is honest and returns patch_plan_request.
    has_edit = any(s.editKind != "none" for s in router.subtasks)
    if has_edit:
        return OpenClawDecision(
            router=router,
            context=context,
            action="patch_plan_request",
            plan=plan,
            patchPlanRequest=PatchPlanRequest(
                targetSummary=_target_summary(router),
                status="action_bridge_missing",
                blockedBy="openclaw-action-bridge",
            ),
            rationale=(
                "multi_intent med minst en ändring: aggregerat till "
                "patch_plan_request (OpenClaw-action-bryggan saknas)."
            ),
        )
    return OpenClawDecision(
        router=router,
        context=context,
        action="plan_only",
        plan=plan,
        rationale="multi_intent utan ändring: aggregerat till plan_only.",
    )


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------


def _target_summary(router: RouterDecision) -> str:
    """A best-effort, honest description of what an edit targets.

    A ``visual_style`` restyle changes the site's STYLE/THEME (colour, tone) -
    not a content field - so describing it as a
    ``contentBlocks.<route>.<section>.<field>`` path mislabels the intent (the
    chat row renders this string verbatim). That kind gets an honest style/theme
    summary instead. ``copy_change`` / ``component_add`` keep the contentBlocks
    path, where it correctly names the targeted content field. Honest about what
    is unknown: an unresolved section/field is rendered as a ``<section>`` /
    ``<field>`` placeholder rather than invented.
    """
    if router.editKind == "visual_style":
        return "stil/tema (färg, ton)"
    target = router.target
    route = (target.routeId if target and target.routeId else None) or "home"
    section = "<section>"
    if target is not None:
        if target.sectionId:
            section = target.sectionId
        elif target.sectionOrdinal is not None:
            section = f"section[{target.sectionOrdinal}]"
    return f"contentBlocks.{route}.{section}.<field>"


def _edit_plan_steps(router: RouterDecision, summary: str) -> list[str]:
    """A grounded, honest "sa har skulle det kunna byggas" plan for an edit.

    Novel-intent planeringssvar (coach-beslut 2026-06-15): instead of a bare
    action_bridge_missing flag, V0 explains what it understood and the concrete
    path, so a clear-but-not-yet-bridged edit reads as conductor intelligence,
    not a dead-end. Derived ONLY from the router (no LLM, no I/O - decide stays a
    pure deterministic function) and it never claims the change was applied: the
    last step is always the honest "no automatic change yet" line (#313). The
    per-kind path names the role that WOULD own it (stylist/section_builder/
    component_builder/copy), so the plan also documents the conductor's own map.
    """
    edit = router.editKind
    if edit == "visual_style":
        understood = "en stil-/tema-ändring (färg, ton)"
        path = (
            "stylisten tolkar den till en validerad tema-mutation "
            "(brand.primaryColorHex / tone) som tema-utföraren applicerar"
        )
    elif edit == "section_add":
        understood = f"att lägga till en sektion ({summary})"
        path = (
            "section_builder monterar sektionens capability + dossier via den "
            "befintliga apply-kedjan"
        )
    elif edit == "component_add":
        understood = f"att lägga till en komponent ({summary})"
        path = (
            "component_builder skulle montera en känd katalog-komponent "
            "(ADR 0059); en okänd komponent stannar som ärligt ej-stödd, aldrig "
            "påhittad"
        )
    elif edit == "copy_change":
        understood = f"en textändring ({summary})"
        path = (
            "copy-rollen skriver en validerad copyDirective som apply-kedjan "
            "tillämpar"
        )
    else:
        understood = f"en ändring ({summary})"
        path = "patch-planeraren -> apply -> riktad render skulle utföra den"
    return [
        f"Jag uppfattar {understood}.",
        f"Så skulle det kunna byggas: {path}.",
        "Ingen automatisk ändring görs ännu - OpenClaw-action-bryggan som kör "
        "kedjan från ett konduktörsbeslut saknas (ingen falsk success, #313).",
    ]


def _subtask_line(index: int, subtask: object) -> str:
    edit_kind = getattr(subtask, "editKind", "none")
    instruction = (getattr(subtask, "instruction", "") or "").strip()
    constraint = getattr(subtask, "constraint", None)
    if constraint:
        return f"{index}. constraint: {constraint}"
    label = instruction or edit_kind
    return f"{index}. {edit_kind}: {label}"


def _available_options(context: AssembledContext) -> list[str]:
    """List the discoverable options from a component_registry payload.

    Read-only: it only projects the already-assembled payload (no disk I/O).
    Prefers dossier labels, falls back to capability slugs; order is stable.
    """
    payload = context.payload or {}
    labels: list[str] = []
    for dossier in payload.get("dossiers", []) or []:
        if isinstance(dossier, dict):
            label = dossier.get("label") or dossier.get("id")
            if label and label not in labels:
                labels.append(str(label))
    if labels:
        return labels
    caps: list[str] = []
    for cap in payload.get("capabilities", []) or []:
        if isinstance(cap, dict):
            slug = cap.get("capability")
            if slug and slug not in caps:
                caps.append(str(slug))
    return caps
