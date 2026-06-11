"""LLM fallback for the message router (KÖR-6b).

This is the optional second layer on top of the deterministic OpenClaw Router
(``classify_message`` in ``classify.py``, KÖR-6a). The heuristic owns the common
cases and the clock examples; this module only steps in when the heuristic is
genuinely low-confidence:

- the heuristic returned ``unclear``, or
- the message is long, or
- it is a complex ``multi_intent`` (>= 3 actionable edits).

In every other case the heuristic decision is returned unchanged, so KÖR-6a
keeps owning the cases it already classifies well ("LLM rör dem inte i onödan").

Hard guarantees of this slice (mirroring 04-builder-profil + KÖR-6b):

- **Mock without a key is identical to KÖR-6a.** Without ``OPENAI_API_KEY`` the
  fallback returns ``classify_message(...)`` verbatim - no regression, no
  network call, no import of ``openai``.
- **The LLM never starts a build or preview it should not.** Whatever the model
  returns, ``shouldStartPreview`` is recomputed deterministically from
  ``buildRequirement`` + builder coexistence (02 §8), so an ``answer_only`` /
  ``plan_only`` decision can never actuate a preview.
- **Same output contract as KÖR-6a.** The model is parsed straight into the
  ``RouterDecision`` Pydantic model that mirrors
  ``governance/schemas/router-decision.schema.json`` (generateObject-style,
  schema-validated). Any parse/validation/network error falls back to the
  heuristic decision.
- **No new runtime contract / canonical artefakt.** This reads the existing
  ``governance/policies/llm-models.v1.json`` (``routerModel`` role) and the
  existing ``OPENAI_API_KEY`` env var, exactly like the brief/repair resolvers.

Boundary note: ``packages/generation/orchestration/router`` must stay
import-clean (it may not import ``packages/generation/brief``), so the tiny
policy lookup + env check are re-implemented locally here, the same way
``packages/generation/repair/model_resolver.py`` does for ``repairModel``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from packages.policies.llm_model_params import resolve_role_params, responses_kwargs

from .classify import _should_start_preview, classify_message
from .models import RouterContext, RouterDecision

logger = logging.getLogger("sajtbyggaren.router")

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

ROUTER_ROLE_ID = "routerModel"
EXPECTED_PROVIDER = "openai"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# Fallback trigger thresholds. A message is "long" when it crosses either the
# word or the character bound; a multi_intent only escalates to the LLM when it
# carries several actionable edits (the two-edit clock example E stays with the
# heuristic). Kept conservative so the common, confidently-classified cases
# never reach the model.
LONG_WORD_THRESHOLD = 25
LONG_CHAR_THRESHOLD = 180
MULTI_INTENT_MIN_ACTIONABLE = 3

# Per-messageKind allowlist for buildRequirement (kor-6a / 02 §2). A non-edit
# kind must never escalate to a build; an edit kind must do at least a patch.
# routerModel can return a schema-valid but semantically inconsistent pair, so an
# LLM decision is clamped to the least-action value its kind allows before
# shouldStartPreview is recomputed. The deterministic heuristic is already
# consistent, so in practice the clamp only ever rewrites a bad model output.
_BUILD_RANK: dict[str, int] = {
    "none": 0,
    "plan_only": 1,
    "artifact_patch_only": 2,
    "targeted_rebuild": 3,
    "full_rebuild": 4,
}
_ALLOWED_BUILD_BY_KIND: dict[str, tuple[str, ...]] = {
    "answer_only": ("none",),
    "component_discovery": ("none",),
    "site_review": ("none", "plan_only"),
    "reference_analysis": ("plan_only",),
    "bug_report": ("plan_only",),
    "unclear": ("none",),
    "edit_instruction": ("artifact_patch_only", "targeted_rebuild", "full_rebuild"),
    "multi_intent": ("plan_only", "targeted_rebuild", "full_rebuild"),
}


def has_openai_api_key() -> bool:
    """True when OPENAI_API_KEY is set to a non-whitespace value.

    Whitespace-only values (e.g. ``"   "``, ``"\\n"``) are treated as missing -
    same semantics as ``packages/generation/brief/models.py`` and
    ``packages/generation/repair/model_resolver.py`` (re-implemented here to keep
    the router boundary-clean). Without this guard a stray newline pasted into a
    shell profile would route through the real-LLM path and surface as a
    confusing OpenAI auth error instead of cleanly falling back to KÖR-6a.
    """
    value = os.environ.get(OPENAI_API_KEY_ENV)
    if value is None:
        return False
    return bool(value.strip())


class RouterModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json does not declare a usable routerModel."""


def resolve_router_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for ``routerModel`` in the policy.

    Strict: raises ``RouterModelResolutionError`` when the policy file is
    missing, malformed, missing the role, the provider is not openai, or the
    model field is empty. We prefer a hard failure over a silent default because
    the policy is the Model Role contract (llm-models.v1, ADR 0009).
    """
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise RouterModelResolutionError(f"llm-models.v1.json missing at {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RouterModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != ROUTER_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise RouterModelResolutionError(
                f"{ROUTER_ROLE_ID} provider must be {EXPECTED_PROVIDER!r}, "
                f"got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise RouterModelResolutionError(
                f"{ROUTER_ROLE_ID} role is missing a non-empty model value"
            )
        return model

    raise RouterModelResolutionError(f"{ROUTER_ROLE_ID} role missing from {path.name}")


def _is_long(message: str) -> bool:
    text = (message or "").strip()
    return len(text) >= LONG_CHAR_THRESHOLD or len(text.split()) >= LONG_WORD_THRESHOLD


def needs_llm_fallback(decision: RouterDecision, message: str) -> bool:
    """Decide whether the heuristic decision should be re-checked by the LLM.

    Only ``unclear`` / long / complex ``multi_intent`` messages qualify. An empty
    message is left to the heuristic (there is nothing for the model to resolve),
    so the LLM is never consulted for a blank prompt even though it classifies as
    ``unclear``.
    """
    if not (message or "").strip():
        return False
    if decision.messageKind == "unclear":
        return True
    if _is_long(message):
        return True
    if decision.messageKind == "multi_intent":
        actionable = sum(1 for s in decision.subtasks if s.editKind != "none")
        if actionable >= MULTI_INTENT_MIN_ACTIONABLE:
            return True
    return False


def _clamp_build_requirement(decision: RouterDecision) -> RouterDecision:
    """Clamp ``buildRequirement`` to the set allowed for ``messageKind``.

    Defensive normalisation of an LLM-produced decision (KÖR-6b): routerModel can
    return a schema-valid but semantically inconsistent pair - e.g. messageKind
    ``answer_only`` with buildRequirement ``targeted_rebuild``. Left unclamped, the
    deterministic ``shouldStartPreview`` recompute would then actuate a build for a
    pure question. We clamp to the least-action value the kind allows so a non-edit
    kind can never start a build/preview (kor-6a / 02 §2). Mutates and returns
    ``decision``; a value already in the allowed set is left untouched.
    """
    allowed = _ALLOWED_BUILD_BY_KIND.get(decision.messageKind)
    if allowed and decision.buildRequirement not in allowed:
        decision.buildRequirement = min(allowed, key=lambda b: _BUILD_RANK[b])
    return decision


_SYSTEM_INSTRUCTIONS = (
    "You are routerModel, the LLM fallback for Sajtbyggaren's OpenClaw Router. "
    "A deterministic heuristic already runs first and only hands you messages it "
    "found ambiguous (unclear), long, or a complex multi-intent. Classify the "
    "single user message into the SAME structured decision the heuristic uses; "
    "do not invent fields. "
    "messageKind is one of: answer_only (a pure question unrelated to the site), "
    "site_review (a question/opinion about the current site), edit_instruction "
    "(one concrete change), component_discovery ('which X are available?'), "
    "reference_analysis ('like on example.com'), bug_report ('the button does "
    "not work'), multi_intent (two or more changes), unclear (cannot act - set "
    "requiresClarification true and ask). "
    "editKind is the concrete edit when messageKind is edit_instruction "
    "(component_add, component_remove, visual_style, copy_change, layout_change, "
    "route_add) and 'none' otherwise. "
    "buildRequirement is how much the system must do: none (just answer), "
    "plan_only (propose/analyse, no build - use it for reference_analysis and "
    "bug_report), artifact_patch_only (copy_change), targeted_rebuild (rebuild "
    "only the affected route/section), full_rebuild (rare, whole-site redesign). "
    "A pure question, discovery, review or reference must NEVER require a build: "
    "use none or plan_only. "
    "contextLevel is how much context a downstream handler should assemble: "
    "none, project_dna, artifacts, artifacts_plus_sections, manifest, "
    "selected_files, preview_dom, external_reference (for reference_analysis) or "
    "component_registry (for component_discovery). "
    "For a multi_intent, fill subtasks with one entry per actionable change "
    "(editKind + a short instruction) and add any cross-cutting constraint such "
    "as 'preserve_copy' to constraints. For an external reference fill reference "
    "{url, object} and set risk to 'do_not_copy_exact'. Resolve a placement "
    "target {routeId, sectionId, sectionOrdinal, position} only when the message "
    "states one. Always write a short rationale that explains why a build was or "
    "was not required. Leave shouldStartPreview false; the router recomputes it "
    "deterministically."
)


def _build_user_message(message: str, ctx: RouterContext) -> str:
    """Compact, read-only context for the model (no disk access)."""
    lines = [f"User message: {message}"]
    if ctx.siteId:
        lines.append(f"siteId: {ctx.siteId}")
    if ctx.hasActiveUserSession:
        lines.append("A live user session is active on this site (builder coexistence).")
    if ctx.routeSections:
        known = ", ".join(sorted(ctx.routeSections))
        lines.append(f"Known routes: {known}")
    return "\n".join(lines)


def _real_router_decision(
    message: str, *, model: str, context: RouterContext
) -> RouterDecision | None:
    """Call routerModel with structured output. Requires OPENAI_API_KEY.

    Returns the parsed ``RouterDecision`` (generateObject-style, schema-validated
    via the Pydantic model that mirrors router-decision.schema.json), or ``None``
    when the model returns nothing. Network/SDK errors propagate to the caller,
    which falls back to the heuristic.
    """
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": _build_user_message(message, context)},
        ],
        text_format=RouterDecision,
        **responses_kwargs(resolve_role_params("routerModel")),
    )
    return response.output_parsed


def classify_message_with_llm_fallback(
    message: str,
    *,
    context: RouterContext | None = None,
    model: str | None = None,
    policy_path: Path | None = None,
) -> RouterDecision:
    """Classify a message, escalating ambiguous cases to routerModel (KÖR-6b).

    Runs the KÖR-6a heuristic first. If the heuristic is confident (not unclear,
    not long, not a complex multi_intent) the heuristic decision is returned
    unchanged. Otherwise, when ``OPENAI_API_KEY`` is set, routerModel re-checks
    the message and returns the same ``RouterDecision`` contract; without a key
    (or on any error) the heuristic decision is returned verbatim - identical to
    KÖR-6a, no regression.

    ``shouldStartPreview`` is always recomputed from the (heuristic or LLM)
    ``buildRequirement`` plus builder coexistence, so the model can never start a
    build/preview for ``answer_only`` / ``plan_only`` and never override the
    live-session guard.
    """
    ctx = context or RouterContext()
    heuristic = classify_message(message, context=ctx)

    if not needs_llm_fallback(heuristic, message):
        return heuristic
    if not has_openai_api_key():
        return heuristic

    try:
        model_name = model or resolve_router_model(policy_path)
        decision = _real_router_decision(message, model=model_name, context=ctx)
    except Exception as exc:  # noqa: BLE001
        # Routing must never fail because the optional fallback did; fall back
        # to the deterministic decision (KÖR-6a) and surface the error to logs.
        message_text = f"routerModel error: {type(exc).__name__}: {exc}"
        logger.warning(message_text)
        sys.stderr.write(f"[routerModel] {message_text}\n")
        sys.stderr.flush()
        return heuristic

    if decision is None:
        return heuristic

    # Clamp a semantically inconsistent model pairing (e.g. answer_only +
    # targeted_rebuild) BEFORE recomputing the actuation flag, so a non-edit kind
    # can never escalate to a build/preview (kor-6a / 02 §2).
    _clamp_build_requirement(decision)
    # The router owns shouldStartPreview as the single actuation flag: recompute
    # it deterministically so the LLM can never actuate a preview it should not.
    decision.shouldStartPreview = _should_start_preview(decision.buildRequirement, ctx)
    return decision
