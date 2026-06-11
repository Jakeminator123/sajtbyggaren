"""kor-4b: verifierModel critic (read-only taste lane on top of kor-4a).

The deterministic critic (``critic.py``) catches *measurable* defects
(placeholder contact, thin offer, missing CTA). This module wires the
``verifierModel`` role as a **read-only** smell critic that reads the
blueprint (Generation Package ``contentBlocks`` + Site Brief positioning /
honesty fields) plus a bounded excerpt of the generated output and returns
judgement-call findings a heuristic cannot make:

- ``fake_or_ungrounded_trust`` - trust signals (reviews, certifications,
  "marknadens bästa") that the brief did not ground in a real fact.
- ``weak_hero`` - a hero that does not say what the business does / for whom.
- ``too_template_like`` - copy that would fit any business in the industry.
- a refined ``generic_copy`` beyond the deterministic phrase list.

Contract (``docs/heavy-llm-flow/kor-4b-verifier-model-critic.md``):

- Same ``critic`` section, ``source: "verifierModel"`` (or ``mock-no-key`` /
  ``mock-llm-error``).
- LLM findings are **merged** with the deterministic ones and **deduplicated**
  per ``(type, target)`` - the deterministic finding wins on a collision so the
  cheap, stable guard is never overwritten by a model finding.
- **Non-blocking.** The result NEVER feeds ``QualityResult.status``; it is the
  same warning lane as kor-4a.
- **Mock without OPENAI_API_KEY** falls back to exactly the deterministic
  findings (no regression vs kor-4a), with ``source = "mock-no-key"``. Any LLM
  error falls back the same way with ``source = "mock-llm-error"``.

Boundary note (repo-boundaries.v1: ``packages/generation/quality_gate`` may
import only ``packages/policies`` / ``packages/shared`` / ``packages/
preview-runtime``). The brief package already owns a near-identical model
resolver, but quality_gate must NOT import brief - so this module re-implements
the tiny policy lookup + env check locally (same pattern as
``packages/generation/repair/model_resolver.py``). It introduces **no new
runtime contract**: same ``llm-models.v1.json`` policy file and same
``OPENAI_API_KEY`` env var the rest of the pipeline already uses.

Repair application (kor-5) and any change to ``status`` aggregation are
deliberately out of scope here.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.policies.llm_model_params import resolve_role_params, responses_kwargs

from .critic import (
    CriticIssue,
    CriticResult,
    _score_for,
    run_deterministic_critic,
)

logger = logging.getLogger("sajtbyggaren.quality_gate.verifier")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

VERIFIER_ROLE_ID = "verifierModel"
EXPECTED_PROVIDER = "openai"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# How much of the blueprint / generated output we hand the model. Bounded so a
# huge generated tree cannot blow up the prompt; the critic only needs a
# representative excerpt to make taste calls.
_MAX_CONTENT_BLOCKS_CHARS = 6000
_MAX_GENERATED_CHARS = 4000

# Taste finding types the verifierModel is allowed to emit. Deliberately a
# subset of CriticIssueType: the mechanical types (thin_offer,
# placeholder_leakage, missing_cta, missing_local_context) stay owned by the
# deterministic lane, so the model focuses on judgement calls and we never let
# it second-guess a cheap heuristic.
VerifierIssueType = Literal[
    "generic_copy",
    "fake_or_ungrounded_trust",
    "weak_hero",
    "too_template_like",
]


def has_openai_api_key() -> bool:
    """True when OPENAI_API_KEY is set to a non-whitespace value.

    Whitespace-only values (e.g. ``"   "``, ``"\\n"``) are treated as missing -
    same semantics as ``packages/generation/brief/models.py:has_openai_api_key``
    (re-implemented here to keep the quality_gate boundary clean). Without this
    guard a stray newline pasted into a shell profile would route through the
    real-LLM path and surface as a confusing OpenAI auth error instead of
    cleanly falling back to the deterministic findings with ``mock-no-key``.
    """
    value = os.environ.get(OPENAI_API_KEY_ENV)
    if value is None:
        return False
    return bool(value.strip())


class VerifierModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json does not declare a usable verifierModel."""


def resolve_verifier_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for ``verifierModel`` in the policy.

    Strict: raises ``VerifierModelResolutionError`` when the policy file is
    missing, malformed, missing the role, the provider is not openai, or the
    model field is empty. The policy is the Model Role contract (llm-models.v1),
    so we prefer a hard failure over a silent default - ``run_verifier_critic``
    catches it and falls back to the deterministic findings so the gate stays
    non-blocking.
    """
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise VerifierModelResolutionError(f"llm-models.v1.json missing at {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerifierModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != VERIFIER_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise VerifierModelResolutionError(
                f"{VERIFIER_ROLE_ID} provider must be {EXPECTED_PROVIDER!r}, "
                f"got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise VerifierModelResolutionError(
                f"{VERIFIER_ROLE_ID} role is missing a non-empty model value"
            )
        return model

    raise VerifierModelResolutionError(
        f"{VERIFIER_ROLE_ID} role missing from {path.name}"
    )


# ---------------------------------------------------------------------------
# Structured output contract
# ---------------------------------------------------------------------------


class VerifierFinding(BaseModel):
    """One taste finding proposed by the verifierModel.

    Mirrors ``CriticIssue`` but constrains ``type`` to the taste subset the
    model owns. Re-mapped to a ``CriticIssue`` before merge so the merged
    result stays a single, uniform shape.
    """

    severity: Literal["high", "medium", "low"] = Field(
        description=(
            "high for honesty violations (fake/ungrounded trust), medium for a "
            "weak hero or template-like copy, low for a minor smell."
        )
    )
    type: VerifierIssueType = Field(
        description=(
            "fake_or_ungrounded_trust = a trust claim not grounded in a stated "
            "fact; weak_hero = hero does not say what the business does/for "
            "whom; too_template_like = copy that fits any business in the "
            "industry; generic_copy = filler/superlatives without substance."
        )
    )
    target: str = Field(
        description=(
            "The <route>.<section> address from the provided contentBlocks "
            "(e.g. 'home.hero'), or 'global.<section>' for a site-wide finding. "
            "Use an address that actually appears in the blueprint."
        )
    )
    message: str = Field(
        description="Short, concrete description of the smell in the prompt's language."
    )
    repairHint: str = Field(
        description=(
            "A concrete, non-applied suggestion for how to ground/sharpen the "
            "copy. Advice only - never invent a fact to fix it."
        )
    )


class VerifierFindings(BaseModel):
    """Structured output: zero or more taste findings, empty when none."""

    findings: list[VerifierFinding] = Field(default_factory=list)


_VERIFIER_SYSTEM = (
    "You are the verifierModel for Sajtbyggaren: a read-only taste critic for a "
    "small-business website. You are given the website blueprint "
    "(contentBlocks keyed by <route>.<section>), the Site Brief positioning and "
    "honesty fields, and an excerpt of the generated pages. Find quality smells "
    "a mechanical checker cannot: "
    "fake_or_ungrounded_trust (a review, certification, award or superlative "
    "like 'marknadens bästa' that the brief did NOT ground in a stated fact - "
    "anything in businessFacts.unknowns must never appear as a claim), "
    "weak_hero (the hero does not make clear what the business does and for "
    "whom), too_template_like (copy that could belong to any business in the "
    "industry), and generic_copy (empty filler or superlatives). "
    "Rules: you NEVER write or apply copy - you only report findings. Each "
    "finding's target MUST be an address that appears in the provided "
    "contentBlocks (or global.<section>). Do not flag missing CTAs, thin offers "
    "or placeholder contact details - those are handled elsewhere. Be "
    "conservative: if the copy is grounded and specific, return an empty list. "
    "Write message and repairHint in the language of the copy (Swedish unless "
    "the copy is clearly English). Never invent facts."
)


def _bounded_json(value: Any, limit: int) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    if len(text) > limit:
        return text[:limit] + "\n… (truncated)"
    return text


def _brief_excerpt(site_brief: dict[str, Any]) -> dict[str, Any]:
    """Pull only the positioning / honesty fields the taste critic needs."""
    keys = (
        "businessTypeGuess",
        "locationHint",
        "positioning",
        "contentStrategy",
        "businessFacts",
        "conversion",
        "tone",
    )
    return {key: site_brief[key] for key in keys if key in site_brief}


def _build_verifier_context(
    *,
    content_blocks: dict[str, Any],
    site_brief: dict[str, Any],
    generated_excerpt: str,
) -> str:
    parts = [
        "Blueprint contentBlocks (keyed by <route>.<section>):",
        _bounded_json(content_blocks, _MAX_CONTENT_BLOCKS_CHARS),
        "",
        "Site Brief (positioning + honesty fields):",
        _bounded_json(_brief_excerpt(site_brief), _MAX_CONTENT_BLOCKS_CHARS),
    ]
    if generated_excerpt:
        parts += ["", "Generated page excerpt:", generated_excerpt]
    return "\n".join(parts)


def _generated_excerpt(target_dir: Path | None) -> str:
    """Best-effort, bounded text excerpt of the generated App Router pages."""
    if target_dir is None:
        return ""
    app_dir = target_dir / "app"
    if not app_dir.exists():
        return ""
    skip = {"node_modules", ".next", ".git", "out", ".turbo"}
    chunks: list[str] = []
    used = 0
    for page in sorted(app_dir.rglob("page.*")):
        if page.suffix not in {".tsx", ".jsx"}:
            continue
        if any(part in skip for part in page.parts):
            continue
        try:
            content = page.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        remaining = _MAX_GENERATED_CHARS - used
        if remaining <= 0:
            break
        snippet = content[:remaining]
        chunks.append(f"--- {page.name} ---\n{snippet}")
        used += len(snippet)
    return "\n".join(chunks)


def _run_verifier_model(*, system: str, context: str, model: str) -> list[CriticIssue]:
    """Call the verifierModel with structured output. Requires OPENAI_API_KEY.

    Raises on any failure so ``run_verifier_critic`` can record
    ``mock-llm-error`` and fall back to the deterministic findings. The caller
    is the boundary that keeps the gate non-blocking.
    """
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": context},
        ],
        text_format=VerifierFindings,
        **responses_kwargs(resolve_role_params("verifierModel")),
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("verifierModel returned no structured output")
    return [
        CriticIssue(
            severity=finding.severity,
            type=finding.type,
            target=finding.target,
            message=finding.message,
            repairHint=finding.repairHint,
        )
        for finding in parsed.findings
    ]


def _merge_dedup(
    deterministic: list[CriticIssue], llm: list[CriticIssue]
) -> list[CriticIssue]:
    """Merge deterministic + LLM findings, deduped per ``(type, target)``.

    Deterministic findings come first and win on a collision: a model finding
    with the same ``(type, target)`` as a deterministic one is dropped so the
    cheap, stable guard is never overwritten (and there is never a double
    ``generic_copy`` on the same target). LLM findings keep their relative
    order otherwise.
    """
    merged = list(deterministic)
    seen: set[tuple[str, str]] = {(i.type, i.target) for i in deterministic}
    for issue in llm:
        key = (issue.type, issue.target)
        if key in seen:
            continue
        seen.add(key)
        merged.append(issue)
    return merged


def run_verifier_critic(
    *,
    generation_package: dict[str, Any] | None = None,
    site_brief: dict[str, Any] | None = None,
    target_dir: Path | None = None,
    model: str | None = None,
    policy_path: Path | None = None,
) -> CriticResult:
    """Run the deterministic critic and merge verifierModel taste findings.

    Always runs ``run_deterministic_critic`` first (kor-4a). Then:

    - No usable API key -> return the deterministic findings unchanged with
      ``source = "mock-no-key"`` (identical findings to kor-4a, no regression).
    - Key present -> call the verifierModel, merge + dedup its findings with the
      deterministic ones per ``(type, target)``, recompute the score over the
      merged set, ``source = "verifierModel"``.
    - Any LLM / resolution error -> deterministic findings with
      ``source = "mock-llm-error"`` (still non-blocking).

    The result is the same warning-lane shape kor-4a produced; it NEVER feeds
    ``QualityResult.status``.
    """
    deterministic = run_deterministic_critic(
        generation_package=generation_package,
        site_brief=site_brief,
        target_dir=target_dir,
    )

    if not has_openai_api_key():
        return CriticResult(
            score=deterministic.score,
            issues=deterministic.issues,
            source="mock-no-key",
        )

    gp = generation_package if isinstance(generation_package, dict) else {}
    brief = site_brief if isinstance(site_brief, dict) else {}
    content_blocks = gp.get("contentBlocks")
    content_blocks = content_blocks if isinstance(content_blocks, dict) else {}

    try:
        resolved_model = model or resolve_verifier_model(policy_path)
        context = _build_verifier_context(
            content_blocks=content_blocks,
            site_brief=brief,
            generated_excerpt=_generated_excerpt(target_dir),
        )
        llm_issues = _run_verifier_model(
            system=_VERIFIER_SYSTEM, context=context, model=resolved_model
        )
    except Exception as exc:  # noqa: BLE001
        # The verifier must never break the gate: log to stderr and fall back to
        # the deterministic findings only.
        message = f"verifierModel error: {type(exc).__name__}: {exc}"
        logger.warning(message)
        sys.stderr.write(f"[verifierModel] {message}\n")
        sys.stderr.flush()
        return CriticResult(
            score=deterministic.score,
            issues=deterministic.issues,
            source="mock-llm-error",
        )

    merged = _merge_dedup(deterministic.issues, llm_issues)
    return CriticResult(
        score=_score_for(merged),
        issues=merged,
        source="verifierModel",
    )
