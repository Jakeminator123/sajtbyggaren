"""codegenModel v1: deterministic CodegenResult emission.

Sprint 3A v1 does not call any LLM. It adapts what scripts/build_site.py
already writes (pages, dossier-mounted components, patched starter
files) into a structured CodegenResult so Quality Gate and Repair
Pipeline have a typed manifest to inspect.

Later sprints (3B+) replace the body with a real codegenModel call that
emits CodegenFile entries before files are written. At that point the
builder becomes a thin writer of CodegenFile entries and B13 (product
logic in scripts/build_site.py) closes naturally.
"""

from __future__ import annotations

from typing import Any

from .models import CodegenFile, CodegenResult


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


def produce_codegen_artefakt(
    generation_package: dict[str, Any],
    *,
    routes_written: list[str],
    dossier_components: list[str],
    starter_id: str,
) -> CodegenResult:
    """Build a CodegenResult that describes the files fas 3 emits.

    Sprint 3A v1 is deterministic and adapts the actual builder output:

    - One ``page`` entry per route in ``routes_written`` (covers both
      scaffold-derived routes and Dossier-contributed routes).
    - One ``component`` entry per path in ``dossier_components`` (these
      are paths the builder already copied from Dossiers'
      ``components/`` directories).
    - Two ``starter-patched`` entries for ``package.json`` and
      ``app/globals.css`` because the builder always patches them.

    Parameters mirror what scripts/build_site.py already computes during
    fas 3, so the manifest faithfully reflects the on-disk output without
    duplicating any product logic. ``generation_package`` is accepted for
    future LLM-driven v2 implementations even though v1 only reads
    ``starter_id`` from it indirectly (via the ``starter_id`` argument
    that scripts/build_site.py already extracted).
    """
    if not isinstance(generation_package, dict):
        raise TypeError("generation_package must be a dict from produce_site_plan")

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

    rationale = (
        f"Sprint 3A v1 deterministic codegen: {len(routes_written)} routes, "
        f"{len(dossier_components)} dossier components, starter={starter_id}. "
        f"Real codegenModel LLM call lands in Sprint 3B per ADR 0015."
    )

    return CodegenResult(
        files=files,
        source="deterministic-v1",
        modelUsed="deterministic",
        rationale=rationale,
        error=None,
    )
