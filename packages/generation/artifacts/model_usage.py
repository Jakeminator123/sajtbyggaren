"""Compose ``build-result.json:modelUsage`` from per-role usage data.

Sprint 3C-lite (ADR 0017) introduced ``byRole`` with the three canonical
LLM roles (``briefModel``, ``planningModel``, ``codegenModel``). Roles
that do not yet track usage are represented by ``null`` ("we do not
know") rather than ``0`` ("we ran the model and spent zero tokens"),
which would be a lie.

This helper used to live as ``scripts/build_site.py:_model_usage_from_codegen``
but was promoted to a shared module so ``scripts/dev_generate.py`` can
reuse the same composition logic without importing a private helper
across script boundaries. Both scripts (and any future canonical
artefakt writer) call ``compose_model_usage`` so the shape stays
consistent across runners.

Sprint 3C-full or a separate sprint will widen brief / planning
resolvers to track usage; that change is non-breaking because
``byRole`` slots flip from ``null`` to a usage dict in place.
"""

from __future__ import annotations

from typing import Any

CANONICAL_LLM_ROLES = ("briefModel", "planningModel", "codegenModel")


def compose_model_usage(
    base_source: str,
    codegen_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ``modelUsage`` envelope.

    Parameters
    ----------
    base_source
        The ``briefSource`` value to thread into ``modelUsage.source``.
        It tracks how the OVERALL pipeline ran (e.g. ``mock-no-key``,
        ``real``, ``mock-llm-error``) and is independent of the per-role
        accounting. Keeps the Sprint 2A invariant.
    codegen_summary
        The ``codegen``-shaped dict that ``write_build_result`` /
        ``dev_generate.py:run_phase_build`` is about to embed in
        build-result.json. When ``None`` (or when codegen.source is not
        ``real`` or totalTokens is 0) the codegen role stays ``null``.

    Returns
    -------
    dict
        ``{
            "byRole": {
                "briefModel": null,
                "planningModel": null,
                "codegenModel": null | {promptTokens, completionTokens, totalTokens}
            },
            "totalInputTokens": int,
            "totalOutputTokens": int,
            "totalCostUsd": 0.0,
            "currency": "USD",
            "source": <base_source>
        }``

    Truth-field rules
    -----------------
    - ``byRole.briefModel`` and ``byRole.planningModel`` stay ``null``
      because their resolvers do not track usage yet (ADR 0017 § 3).
    - ``byRole.codegenModel`` is populated only when the real LLM call
      ran AND reported non-zero tokens. ``deterministic-v1`` /
      ``mock-no-key`` / ``mock-llm-error`` paths leave it ``null``.
    - ``totalInputTokens`` / ``totalOutputTokens`` reflect the codegen
      totals only (until Sprint 3C-full sums all three roles).
    - ``totalCostUsd`` stays ``0.0`` because we have no per-model price
      table yet; bumping it requires a price-source policy entry first.
    """
    usage: dict[str, Any] = {
        "byRole": {role: None for role in CANONICAL_LLM_ROLES},
        "totalInputTokens": 0,
        "totalOutputTokens": 0,
        "totalCostUsd": 0.0,
        "currency": "USD",
        "source": base_source,
    }

    if not codegen_summary:
        return usage

    codegen_source = codegen_summary.get("source")
    codegen_usage = codegen_summary.get("usage") or {}
    if codegen_source != "real":
        return usage

    total_tokens = int(codegen_usage.get("totalTokens", 0))
    if total_tokens <= 0:
        return usage

    prompt = int(codegen_usage.get("promptTokens", 0))
    completion = int(codegen_usage.get("completionTokens", 0))
    usage["byRole"]["codegenModel"] = {
        "promptTokens": prompt,
        "completionTokens": completion,
        "totalTokens": total_tokens,
    }
    usage["totalInputTokens"] = prompt
    usage["totalOutputTokens"] = completion
    return usage
