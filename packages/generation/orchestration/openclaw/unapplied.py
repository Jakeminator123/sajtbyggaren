"""Honest reporting of compound follow-up parts no executor applied (B155 follow-up).

A compound follow-up ("gör den coolare och ta bort kontaktformuläret") fans out
into a router decision with one or more subtasks. The KÖR-7 capability chain
(``scripts/build_site.py:run_followup_chain``) only OWNS three editing roles -
``stylist`` (``visual_style`` -> theme), ``section_builder`` (``section_add`` ->
mounted capability) and the patch planner (``component_add`` / ``copy_change``
against a named section). Router subtask edit kinds with NO executor
(``component_remove``, ``layout_change``, ``route_add``) - and edits whose owner
materialised nothing (a ``visual_style`` with no parseable colour/font/tone, an
unsupported ``section_add``, a ``component_add`` / ``copy_change`` with no target
section) - used to vanish SILENTLY while the build still reported a success.

This module is a pure, side-effect-free OBSERVER. Given the router decision plus
what the chain actually materialised, it returns a bounded
``[{"target": ..., "reason": ...}]`` list for the EXISTING
``unappliedFollowupIntents`` channel (already consumed by FloatingChat from
``build-result.json``). It never mutates the decision, never remaps an intent,
never fabricates an applied effect, and never introduces a new mechanism: the
chain threads the result onto the new version's meta sidecar and the deterministic
builder surfaces it exactly like the v1 follow-up path's
``compute_unapplied_followup_intents``.

Honesty contract (mirrors the role-ownership table in ``roles.py``): the three
unowned router edit kinds are always reportable; the owned kinds are reportable
only when their executor produced nothing for the version that was built.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..router.models import RouterDecision

__all__ = ["compute_unapplied_followup_chain_intents"]

# Bounds so a long compound prompt can never smuggle oversized strings into the
# meta sidecar / build-result.json. ``build_site._prompt_meta_unapplied_followup_intents``
# re-bounds on read too; these keep the producer side honest as well.
_TARGET_MAX_LENGTH = 80
_REASON_MAX_LENGTH = 400
_MAX_ITEMS = 20
_INSTRUCTION_SNIPPET_MAX_LENGTH = 120

# Short, operator-facing slug per router edit kind. FloatingChat renders the post
# as ``• <target>: <reason>``, so the target is a brief Swedish label and the
# reason carries the honest explanation. Stable per kind so the reader's
# target-dedupe keeps exactly one line per kind.
_UNAPPLIED_CHAIN_TARGET_LABEL: dict[str, str] = {
    "component_remove": "borttagning",
    "layout_change": "layout",
    "route_add": "ny sida",
    "component_add": "komponent",
    "copy_change": "text",
    "visual_style": "stil",
    "section_add": "sektion",
}

# Honest Swedish reason per kind (the operator's own instruction snippets are
# appended for context). These name WHY the part was not applied without
# promising a future capability or faking a success.
_UNAPPLIED_CHAIN_REASON: dict[str, str] = {
    "component_remove": (
        "Den här delen ville ta bort något, men ingen utförare äger borttagning "
        "av komponenter i en följdprompt ännu, så den hoppades över"
    ),
    "layout_change": (
        "Den här delen ville ändra layout eller struktur, men ingen utförare "
        "äger layoutändringar i en följdprompt ännu, så den hoppades över"
    ),
    "route_add": (
        "Den här delen ville lägga till en ny sida, men ingen utförare äger nya "
        "sidor i en följdprompt ännu, så den hoppades över"
    ),
    "component_add": (
        "Den här komponenten kunde inte placeras eftersom ingen sektion pekades "
        "ut, så den hoppades över"
    ),
    "copy_change": (
        "Den här textändringen kunde inte placeras eftersom ingen sektion "
        "pekades ut, så den hoppades över"
    ),
    "visual_style": (
        "Den här stildelen kunde inte tolkas till en konkret färg, font eller "
        "ton, så ingen stiländring gjordes"
    ),
    "section_add": (
        "Den här sektionstypen stöds inte ännu som en sanktionerad sektion, så "
        "den hoppades över"
    ),
}


def _edit_is_covered(
    edit_kind: str,
    component_intent: str | None,
    target: object,
    *,
    theme_applied: bool,
    applied_section_capabilities: set[str],
    section_capability_for_intent: Mapping[str, str],
    applied_generative: bool = False,
) -> bool:
    """True when the chain actually materialised this edit for the built version.

    Coverage proxies reuse the chain's own gates and are only sound in the
    ``built`` branch (apply is all-or-nothing, so every collected patch was
    applied there):

    - ``visual_style`` -> covered iff a theme directive with values was applied;
    - ``section_add`` -> covered iff the section type resolved to a mounted
      capability;
    - ``component_add`` -> covered iff the router gave a target section (the patch
      planner only collects edits that carry one) OR the chain materialised a
      generative component (ADR 0061: a recipe component_add carries no target but
      IS applied, so it must not be falsely reported as unapplied);
    - ``copy_change`` -> covered iff the router gave a target section;
    - ``component_remove`` / ``layout_change`` / ``route_add`` -> never covered
      (no executor owns the directive in this slice);
    - anything else (incl. ``none``) -> treated as covered (not reportable).
    """
    if edit_kind == "visual_style":
        return theme_applied
    if edit_kind == "section_add":
        capability = section_capability_for_intent.get(component_intent or "")
        return bool(capability) and capability in applied_section_capabilities
    if edit_kind == "component_add":
        return target is not None or applied_generative
    if edit_kind == "copy_change":
        return target is not None
    if edit_kind in ("component_remove", "layout_change", "route_add"):
        return False
    return True


def _build_reason(edit_kind: str, instructions: list[str]) -> str:
    """Compose the honest reason for an uncovered edit kind + its snippets."""
    base = _UNAPPLIED_CHAIN_REASON.get(edit_kind, "Den här delen kunde inte utföras")
    snippet = "; ".join(instructions).strip()[:_INSTRUCTION_SNIPPET_MAX_LENGTH].strip()
    reason = f"{base} (berörda delar: {snippet})." if snippet else f"{base}."
    return reason[:_REASON_MAX_LENGTH]


def compute_unapplied_followup_chain_intents(
    decision: RouterDecision,
    *,
    theme_applied: bool,
    applied_section_capabilities: Iterable[str],
    section_capability_for_intent: Mapping[str, str],
    applied_generative: bool = False,
) -> list[dict[str, str]]:
    """Return bounded ``unappliedFollowupIntents`` posts for a built follow-up.

    ``decision`` is the router decision the chain ran; ``theme_applied`` is True
    when a ``visual_style`` directive with values was applied; ``applied_section_capabilities``
    are the section capabilities the chain mounted; ``section_capability_for_intent``
    maps a router section-type slug to its capability (``SECTION_TYPE_CAPABILITY``).
    ``applied_generative`` (ADR 0061) is True when the chain materialised a
    generative component, so a targetless ``component_add`` that was actually
    applied is treated as covered instead of falsely reported as unapplied.

    Enumerates the actionable edits (the top-level ``editKind`` plus every subtask
    with ``editKind != "none"``), drops the ones the chain covered, and emits ONE
    post per remaining edit kind (grouped, so multiple same-kind subtasks collapse
    to a single honest line whose reason joins their instructions). Returns ``[]``
    when everything the router found was applied - no false positives for a clean
    single-intent follow-up.
    """
    applied_caps = {
        cap for cap in applied_section_capabilities if isinstance(cap, str) and cap.strip()
    }

    actionable: list[tuple[str, str | None, object, str]] = []
    if decision.editKind != "none":
        # A single top-level edit carries no per-subtask instruction text; the
        # whole prompt is the instruction (not available here). Leave the snippet
        # empty rather than leak the router rationale as if it were operator copy.
        actionable.append((decision.editKind, decision.componentIntent, decision.target, ""))
    for subtask in decision.subtasks:
        if subtask.editKind != "none":
            actionable.append(
                (
                    subtask.editKind,
                    subtask.componentIntent,
                    subtask.target,
                    (subtask.instruction or "").strip(),
                )
            )

    uncovered: dict[str, list[str]] = {}
    order: list[str] = []
    for edit_kind, component_intent, target, instruction in actionable:
        if _edit_is_covered(
            edit_kind,
            component_intent,
            target,
            theme_applied=theme_applied,
            applied_section_capabilities=applied_caps,
            section_capability_for_intent=section_capability_for_intent,
            applied_generative=applied_generative,
        ):
            continue
        if edit_kind not in uncovered:
            uncovered[edit_kind] = []
            order.append(edit_kind)
        snippet = instruction.strip()
        if snippet and snippet not in uncovered[edit_kind]:
            uncovered[edit_kind].append(snippet)

    posts: list[dict[str, str]] = []
    for edit_kind in order:
        target_label = _UNAPPLIED_CHAIN_TARGET_LABEL.get(edit_kind, edit_kind)[
            :_TARGET_MAX_LENGTH
        ]
        posts.append({"target": target_label, "reason": _build_reason(edit_kind, uncovered[edit_kind])})
        if len(posts) >= _MAX_ITEMS:
            break
    return posts
