"""Deterministic, honest Swedish follow-up report (no LLM, no I/O).

Every follow-up turn - an applied edit, an honest no-op, an answer-only chat -
should leave the operator with a short Swedish line that (a) reflects how the
conductor interpreted the prompt and (b) states what it did or why it did not.
Today that natural-language line is produced ONLY by the Viewser chat helper
(``lib/openai.ts``), so without ``OPENAI_API_KEY`` (or on a timeout) an applied
edit / honest no-op falls back to bare deterministic status rows with no
grounded sentence - the experience is uneven (operator finding 2026-06-16).

This module gives the seam a DETERMINISTIC floor: a report derived ENTIRELY
from the existing ``OpenClawDecision`` payload + the action-bridge result. It
honours SOUL.md's honesty contract - a no-op is an honest no-op stating what
was understood and why it could not be applied, never a faked "klart" - and
talks about VISIBLE effect, never about version creation (the legacy fallback
path may still mint an invisible version, so a "no new version" claim would be
dishonest there).

Pure + side-effect-free, like ``core.decide`` / ``unapplied`` : it reads the
two already-built mappings and returns a string. It never calls an LLM, never
invents customer copy or facts, and never claims an applied change the bridge
did not report (``appliedVisibleEffect`` / ``previewShouldRefresh`` stay
authoritative). Conventions: identifiers/comments in English, operator-facing
text in Swedish (governance/rules/code-in-english.md + language policy).
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["build_followup_report"]

# Operator-facing Swedish phrasing for what an edit was understood to be, keyed
# by the router ``editKind``. Mirrors the role table in ``roles.py`` so the
# interpretation line names the same surface the conductor maps.
_EDIT_INTERPRETATION: dict[str, str] = {
    "visual_style": "en stil- eller temaändring (färg, ton)",
    "section_add": "att du vill lägga till en sektion",
    "copy_change": "en textändring",
    "component_add": "att du vill lägga till en komponent",
    "route_remove": "att du vill ta bort en sida",
    "nav_hide": "att du vill dölja en sida i menyn",
    "component_remove": "att du vill ta bort en komponent",
    "layout_change": "en layoutändring",
    "route_add": "att du vill lägga till en ny sida",
}

# Interpretation line for a conversation turn the dispatcher answers in chat.
_CONVERSATION_INTERPRETATION: dict[str, str] = {
    "small_talk": "Jag tolkar det här som småprat, inte en ändring.",
    "site_opinion": "Jag tolkar det här som en fråga om din sajt, inte en ändring.",
    "question": "Jag tolkar det här som en fråga, inte en ändring.",
}

# Honest Swedish reason per chain no-op ``stage`` (build_site.run_followup_chain).
# Derived from the stage rather than the raw chain note so the line stays
# operator-friendly (the raw notes carry technical "messageKind=..." context).
_NO_OP_REASON_BY_STAGE: dict[str, str] = {
    "router_no_edit": "jag kunde inte tolka den till en konkret, byggbar ändring",
    "plan_empty": "jag kunde inte tolka den till en konkret, byggbar ändring",
    "apply_empty": "jag kunde inte tolka den till en konkret, byggbar ändring",
    "apply_unmapped": "jag kunde inte tolka den till en konkret, byggbar ändring",
    "plan_rejected": "ändringen stoppades av säkerhetskontrollerna",
    "apply_rejected": "ändringen stoppades av säkerhetskontrollerna",
    "section_unsupported": "den sektionstypen stöds inte ännu som en sanktionerad sektion",
    "route_remove_unsupported": "sidan kunde inte tas bort (okänd eller skyddad sida)",
    "nav_hide_unsupported": "sidan kunde inte döljas i menyn (okänd sida)",
    "generative_unsupported": "det komponentreceptet stöds inte ännu",
}

_DEFAULT_NO_OP_REASON = "jag kunde inte göra den ändringen automatiskt ännu"

# Bound the report so a long compound prompt can never smuggle oversized strings
# through the seam into the chat surface.
_MAX_DETAIL_LENGTH = 200
_MAX_ROUTES = 4


def build_followup_report(
    decision: Mapping[str, object],
    bridge: Mapping[str, object] | None = None,
) -> str:
    """Return a short, honest, grounded Swedish report for one follow-up turn.

    ``decision`` is the emitted ``OpenClawDecision`` payload (model_dump + the
    additive ``conversation`` block); ``bridge`` is the action-bridge result
    (``{status, applied, previewShouldRefresh, chain}``) or ``None`` for the
    read-only decision path (no apply attempted). The string reflects how the
    prompt was interpreted and states what was done or why it was not - never a
    faked success.
    """
    action = _as_str(decision.get("action"))
    conversation = decision.get("conversation")
    conversation = conversation if isinstance(conversation, Mapping) else {}
    conversation_kind = _as_str(conversation.get("conversationKind"))

    if action == "answer_only":
        lead = _CONVERSATION_INTERPRETATION.get(
            conversation_kind,
            "Jag tolkar det här som en fråga, inte en ändring.",
        )
        return f"{lead} Jag svarar i chatten och rör inte sajten."

    if action == "clarification":
        return (
            "Jag är inte säker på vad du vill ändra, så jag ber om ett "
            "förtydligande i stället för att gissa. Sajten är oförändrad."
        )

    if action == "plan_only":
        return (
            "Jag uppfattar det här som något som behöver en plan först, så jag "
            "föreslår en plan i stället för att ändra sajten direkt. Sajten är "
            "oförändrad."
        )

    if action == "patch_plan_request":
        return _edit_report(decision, bridge)

    # Any unexpected/forward action: stay honest and minimal.
    return (
        "Jag tog emot din följdprompt men gjorde ingen ändring i den här "
        "turen. Sajten är oförändrad."
    )


def _edit_report(
    decision: Mapping[str, object],
    bridge: Mapping[str, object] | None,
) -> str:
    """Compose the report for an edit_instruction (patch_plan_request)."""
    understood = _edit_interpretation(decision)

    if not bridge:
        # Read-only decision path: no apply was attempted this turn.
        return (
            f"{understood}. Det skulle kunna byggas, men jag gjorde ingen "
            "ändring i den här turen, så sajten är oförändrad."
        )

    applied = bridge.get("applied") is True
    preview_refresh = bridge.get("previewShouldRefresh") is True
    chain = bridge.get("chain")
    chain = chain if isinstance(chain, Mapping) else {}

    if applied and preview_refresh:
        outcome = (
            f"jag byggde en ny version{_version_label(chain)} och previewen "
            f"visar ändringen{_changed_routes_label(chain)}"
        )
        return f"{understood}. Så här gjorde jag: {outcome}.{_unapplied_label(chain)}"

    if applied:
        return (
            f"{understood}. Jag registrerade ändringen{_version_label(chain)}, "
            "men den syns inte i previewen ännu (montering utan synlig effekt)."
            f"{_unapplied_label(chain)}"
        )

    # Not applied -> an honest no-op. State what was understood and why it could
    # not be applied (grounded in the chain stage / the bridge error reason).
    reason = _no_op_reason(bridge, chain)
    return (
        f"{understood}, men {reason}, så ingen synlig ändring gjordes - sajten "
        "ser likadan ut."
    )


def _edit_interpretation(decision: Mapping[str, object]) -> str:
    """The "Jag uppfattar ..." line, derived from the router edit kind."""
    router = decision.get("router")
    edit_kind = ""
    if isinstance(router, Mapping):
        edit_kind = _as_str(router.get("editKind"))
    phrase = _EDIT_INTERPRETATION.get(edit_kind)
    if phrase:
        return f"Jag uppfattar {phrase}"
    return "Jag uppfattar en ändring av sajten"


def _no_op_reason(bridge: Mapping[str, object], chain: Mapping[str, object]) -> str:
    """The honest reason an edit was not applied (stage- or error-derived)."""
    error = _as_str(bridge.get("error"))
    if error:
        return f"det fanns inget att bygga vidare på ({_truncate(error)})"
    status = _as_str(bridge.get("status"))
    stage = _as_str(chain.get("stage")) or status
    return _NO_OP_REASON_BY_STAGE.get(stage, _DEFAULT_NO_OP_REASON)


def _version_label(chain: Mapping[str, object]) -> str:
    version = chain.get("version")
    if isinstance(version, int) and not isinstance(version, bool):
        return f" (v{version})"
    return ""


def _changed_routes_label(chain: Mapping[str, object]) -> str:
    raw = chain.get("changedRoutes")
    if not isinstance(raw, list):
        return ""
    routes = [r for r in raw if isinstance(r, str) and r.strip()]
    if not routes:
        return ""
    shown = ", ".join(routes[:_MAX_ROUTES])
    return f" (ändrade sidor: {shown})"


def _unapplied_label(chain: Mapping[str, object]) -> str:
    """Append an honest "these parts could not be done" note for a compound."""
    raw = chain.get("unappliedFollowupIntents")
    if not isinstance(raw, list):
        return ""
    targets: list[str] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            target = _as_str(entry.get("target"))
            if target and target not in targets:
                targets.append(target)
    if not targets:
        return ""
    shown = ", ".join(targets[:_MAX_ROUTES])
    return f" Delar kunde inte göras: {shown}."


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _truncate(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _MAX_DETAIL_LENGTH else text[: _MAX_DETAIL_LENGTH - 1] + "…"
