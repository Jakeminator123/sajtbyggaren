"""codegenModel: produce a structured manifest of generated files.

Sprint 3A v1 was deterministic - the manifest adapted what
``scripts/build_site.py`` had already written. Sprint 3B-next (ADR 0017)
adds a *minimal real LLM call* that ENRICHES the manifest with
``rationale`` and ``riskNotes`` while keeping the file list
deterministic. The LLM cannot inject files in this slice; that
contract widens once Quality Gate + Repair Pipeline have proven they
catch drift end-to-end.

Code paths:

- ``OPENAI_API_KEY`` set + ``starter_id == "marketing-base"``:
  call codegenModel via OpenAI structured output; ``source="real"``.
- ``OPENAI_API_KEY`` set + LLM call raises: log + fall back;
  ``source="mock-llm-error"``, ``error`` populated.
- ``OPENAI_API_KEY`` missing: skip LLM; ``source="mock-no-key"``.
- ``starter_id`` not in real-codegen scope: skip LLM;
  ``source="deterministic-v1"`` (Sprint 3A heritage). Sprint 3B-next
  is intentionally limited to ``marketing-base`` per reviewer scope.

Files are produced deterministically in all four code paths:

- One ``page`` entry per route written (scaffold + Dossier-contributed).
- One ``component`` entry per Dossier-mounted component.
- One ``layout`` entry for ``app/layout.tsx`` (always written).
- Two ``starter-patched`` entries for ``package.json`` and
  ``app/globals.css`` (always patched).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from packages.generation.brief import has_openai_api_key

from .models import (
    CodegenFile,
    CodegenLLMResponse,
    CodegenResult,
    CodegenUsage,
    resolve_codegen_model,
)

logger = logging.getLogger("sajtbyggaren.codegen")

# Sprint 3B-next is intentionally limited to marketing-base.
# B20 harmonised data/starters/commerce-base as a buildable starter, but
# real codegenModel support still stays scoped to marketing-base until a
# separate codegen widening sprint confirms e-commerce route semantics.
# Adding more starters to this set requires:
#   1. The starter to actually exist with content under data/starters/.
#   2. A separate sprint that confirms codegenModel can reason about
#      the starter's structure (e.g. e-commerce-specific routes).
_REAL_CODEGEN_STARTERS: set[str] = {"marketing-base"}


def _route_to_page_path(route: str) -> str:
    """Convert a route string ('/', '/tjanster') into a Next.js App Router
    page path ('app/page.tsx', 'app/tjanster/page.tsx').

    Mirrors the path layout that scripts/build_site.py:write_pages already
    writes. Kept here so the manifest can be produced without importing
    builder internals.
    """
    if route == "/":
        return "app/page.tsx"
    cleaned = route.strip("/")
    return f"app/{cleaned}/page.tsx"


def _build_deterministic_files(
    routes_written: list[str],
    dossier_components: list[str],
) -> list[CodegenFile]:
    """Produce the canonical CodegenFile list. Same in all four code
    paths so the LLM cannot widen the manifest by hallucinating files.
    """
    files: list[CodegenFile] = []

    for route in routes_written:
        files.append(
            CodegenFile(
                path=_route_to_page_path(route),
                source="codegen",
                role="page",
            )
        )

    for component_path in dossier_components:
        files.append(
            CodegenFile(
                path=component_path,
                source="dossier-mount",
                role="component",
            )
        )

    files.append(
        CodegenFile(
            path="app/layout.tsx",
            source="codegen",
            role="layout",
        )
    )
    files.append(
        CodegenFile(
            path="package.json",
            source="starter-patched",
            role="config",
        )
    )
    files.append(
        CodegenFile(
            path="app/globals.css",
            source="starter-patched",
            role="theme",
        )
    )

    return files


def _deterministic_rationale(
    routes_written: list[str],
    dossier_components: list[str],
    starter_id: str,
) -> str:
    return (
        f"Deterministic codegen v1: {len(routes_written)} routes, "
        f"{len(dossier_components)} dossier components, starter="
        f"{starter_id}. Real codegenModel skipped (no API key, "
        f"unsupported starter, or LLM error)."
    )


_SYSTEM_INSTRUCTIONS = (
    "You are the codegenModel for Sajtbyggaren. You receive a Generation "
    "Package describing a marketing-base Next.js site that has just been "
    "scaffolded (routes, dossier components, starter patches). You return "
    "a CodegenLLMResponse with two fields: a one-paragraph rationale "
    "explaining the codegen strategy for this specific site, and 0-3 "
    "short risk notes the operator should watch for. You do NOT propose "
    "file paths, scaffolds, or starter changes - those are decided by "
    "earlier phases. Be specific to the supplied Generation Package; do "
    "not generalise. Stay under 600 characters total. Match the language "
    "of the Site Brief (typically Swedish for the Sajtbyggaren corpus)."
)


def _summarise_generation_package(
    generation_package: dict[str, Any],
    routes_written: list[str],
    dossier_components: list[str],
    starter_id: str,
) -> str:
    """Compress the Generation Package into a short prompt body.

    The full Generation Package can be large (full Site Brief +
    selected Scaffold + Variant + Dossiers + BuildSpec). For Sprint
    3B-next we feed only the fields the rationale actually depends on
    so token cost stays bounded.
    """
    site_brief = generation_package.get("siteBrief") or {}
    scaffold = generation_package.get("scaffoldId", "?")
    variant = generation_package.get("variantId", "?")
    business_type = site_brief.get("businessTypeGuess")
    tone = site_brief.get("tone") or []
    conversion_goals = site_brief.get("conversionGoals") or []
    services = site_brief.get("servicesMentioned") or []
    dossier_ids = generation_package.get("selectedDossiers") or []
    if isinstance(dossier_ids, dict):
        dossier_ids = (
            dossier_ids.get("recommended", [])
            + dossier_ids.get("operatorSelected", [])
        )

    return (
        "Generation Package summary:\n"
        f"- starter: {starter_id}\n"
        f"- scaffold: {scaffold} (variant: {variant})\n"
        f"- businessType: {business_type or 'unknown'}\n"
        f"- tone: {', '.join(tone) or '-'}\n"
        f"- conversionGoals: {', '.join(conversion_goals) or '-'}\n"
        f"- servicesMentioned: {', '.join(services) or '-'}\n"
        f"- routes ({len(routes_written)}): {', '.join(routes_written)}\n"
        f"- dossierComponents ({len(dossier_components)}): "
        f"{', '.join(dossier_components) or 'none'}\n"
        f"- dossierIds: {', '.join(dossier_ids) or 'none'}"
    )


def _call_real_codegen_model(
    *,
    generation_package: dict[str, Any],
    routes_written: list[str],
    dossier_components: list[str],
    starter_id: str,
    model: str,
) -> tuple[CodegenLLMResponse, CodegenUsage]:
    """Call OpenAI with the narrow CodegenLLMResponse schema.

    Returns the parsed response plus a CodegenUsage record. Raises any
    OpenAI error so the caller can structure the fallback path.
    """
    from openai import OpenAI

    client = OpenAI()
    user_message = _summarise_generation_package(
        generation_package, routes_written, dossier_components, starter_id
    )

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_message},
        ],
        text_format=CodegenLLMResponse,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("codegenModel returned no structured output")

    usage_obj = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage_obj, "input_tokens", 0) or 0)
    completion_tokens = int(getattr(usage_obj, "output_tokens", 0) or 0)
    usage = CodegenUsage(
        promptTokens=prompt_tokens,
        completionTokens=completion_tokens,
        totalTokens=prompt_tokens + completion_tokens,
    )

    return parsed, usage


def produce_codegen_artefakt(
    generation_package: dict[str, Any],
    *,
    routes_written: list[str],
    dossier_components: list[str],
    starter_id: str,
) -> CodegenResult:
    """Build a CodegenResult for fas 3.

    Sprint 3B-next routes through one of four paths (see module
    docstring). Files are deterministic in ALL paths; only rationale,
    riskNotes, source, modelUsed, usage and error vary.
    """
    if not isinstance(generation_package, dict):
        raise TypeError("generation_package must be a dict from produce_site_plan")

    files = _build_deterministic_files(routes_written, dossier_components)

    if starter_id not in _REAL_CODEGEN_STARTERS:
        return CodegenResult(
            files=files,
            source="deterministic-v1",
            modelUsed="deterministic",
            rationale=_deterministic_rationale(
                routes_written, dossier_components, starter_id
            ),
        )

    if not has_openai_api_key():
        return CodegenResult(
            files=files,
            source="mock-no-key",
            modelUsed="mock",
            rationale=_deterministic_rationale(
                routes_written, dossier_components, starter_id
            ),
        )

    try:
        model = resolve_codegen_model()
    except Exception as exc:  # noqa: BLE001
        message = f"codegenModel resolver error: {type(exc).__name__}: {exc}"
        logger.warning(message)
        sys.stderr.write(f"[codegenModel] {message}\n")
        sys.stderr.flush()
        return CodegenResult(
            files=files,
            source="mock-llm-error",
            modelUsed="mock",
            rationale=_deterministic_rationale(
                routes_written, dossier_components, starter_id
            ),
            error=f"{type(exc).__name__}: {exc}",
        )

    try:
        parsed, usage = _call_real_codegen_model(
            generation_package=generation_package,
            routes_written=routes_written,
            dossier_components=dossier_components,
            starter_id=starter_id,
            model=model,
        )
    except Exception as exc:  # noqa: BLE001
        message = f"codegenModel error: {type(exc).__name__}: {exc}"
        logger.warning(message)
        sys.stderr.write(f"[codegenModel] {message}\n")
        sys.stderr.flush()
        return CodegenResult(
            files=files,
            source="mock-llm-error",
            modelUsed=model,
            rationale=_deterministic_rationale(
                routes_written, dossier_components, starter_id
            ),
            error=f"{type(exc).__name__}: {exc}",
        )

    return CodegenResult(
        files=files,
        source="real",
        modelUsed=model,
        rationale=parsed.rationale,
        riskNotes=list(parsed.riskNotes),
        usage=usage,
    )
