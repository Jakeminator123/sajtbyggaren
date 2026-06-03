"""Declarative section-treatment loaders (kor-3a single source of truth).

The variant->treatment truth lives in
``orchestration/scaffolds/<id>/section-treatments.json``. Both the build
dispatcher (variant->treatment resolution) and the planning prompt catalogue
read from here, so they can never drift apart.

Ownership note (Pushvakt P1, 2026-06-03): kor-3a originally placed this loader
in ``packages/generation/build/dispatcher.py`` and ``planning/plan.py``
imported it from there -- a fas-2 -> fas-3 import that violates
``repo-boundaries.v1`` (planning ``mayImportFrom`` lists ``orchestration`` but
NOT ``build``). The loader belongs to the layer that owns scaffold
definitions, so it now lives under ``orchestration``: planning imports it
directly (allowed) and ``build/dispatcher`` re-exports it for its own runtime
use (``build`` ``mayImportFrom`` gained ``orchestration`` in repo-boundaries
v10).

Each ``section-treatments.json`` block is::

    {"sections": {"<section-id>": {
        "treatments": ["<section-default>", "<variant treatment>", ...],
        "byVariant": {"<variant-id>": "<treatment-id>", ...}}}}

``treatments[0]`` is the section default (what a variant that does not register
the section inherits); the remaining ids are the variant-specific treatments.
Section ids are scaffold-unique, so flattening every file into one
variant-keyed map is unambiguous.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

_SECTION_TREATMENTS_DIR = Path(__file__).resolve().parent / "scaffolds"


@functools.cache
def load_section_treatments() -> dict[str, dict[str, Any]]:
    """Load the declarative section-treatment truth from every scaffold.

    Returns a per-section catalogue keyed by section id::

        {section_id: {"treatments": [...], "byVariant": {variant: treatment}}}

    This is the single on-disk source of truth that both the build dispatcher
    (variant -> treatment resolution, via ``_SECTION_TREATMENTS_BY_VARIANT``)
    and the planning prompt catalogue (section -> treatment list, via
    ``load_section_treatments_catalogue``) consume. A scaffold without a
    ``section-treatments.json`` simply contributes nothing; a scaffold WITH a
    malformed one fails the build (fail-closed -- see below). Result is cached
    because the files are read once per process and never mutate at runtime;
    tests that need a re-read can call ``load_section_treatments.cache_clear()``.
    """
    catalogue: dict[str, dict[str, Any]] = {}
    if not _SECTION_TREATMENTS_DIR.is_dir():
        return catalogue
    for scaffold_dir in sorted(_SECTION_TREATMENTS_DIR.iterdir()):
        treatments_path = scaffold_dir / "section-treatments.json"
        if not treatments_path.is_file():
            continue
        try:
            loaded = json.loads(treatments_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                "Builder failed: scaffold section-treatments.json at "
                f"{treatments_path} is not valid JSON ({exc.msg} at "
                f"line {exc.lineno}). kor-3a requires a parsable "
                "section-treatments.json so the dispatcher and the "
                "planning catalogue can read one declarative truth."
            ) from exc
        # Fail closed (Pushvakt P2, 2026-06-03): a file that EXISTS must be
        # structurally valid. A malformed root or a missing/non-dict
        # ``sections`` is a scaffold authoring error and must stop the build,
        # not silently fall back to default rendering -- this file is kor-3a's
        # single declarative source of truth. A *missing* file stays a
        # legitimate "this scaffold registers no treatments" signal (skipped
        # above).
        sections = loaded.get("sections") if isinstance(loaded, dict) else None
        if not isinstance(sections, dict):
            raise SystemExit(
                "Builder failed: scaffold section-treatments.json at "
                f"{treatments_path} must be a JSON object with a 'sections' "
                "object. kor-3a treats this file as the single declarative "
                "source of truth, so a malformed structure stops the build "
                "instead of falling back to default rendering."
            )
        for section_id, block in sections.items():
            if not isinstance(block, dict):
                continue
            treatments = [
                str(item)
                for item in (block.get("treatments") or [])
                if isinstance(item, str)
            ]
            by_variant = {
                str(variant_id): str(treatment_id)
                for variant_id, treatment_id in (
                    block.get("byVariant") or {}
                ).items()
                if isinstance(variant_id, str) and isinstance(treatment_id, str)
            }
            entry = catalogue.setdefault(
                section_id, {"treatments": [], "byVariant": {}}
            )
            entry["treatments"] = treatments
            entry["byVariant"].update(by_variant)
    return catalogue


def load_section_treatments_catalogue() -> dict[str, list[str]]:
    """Section-id -> ordered treatment-id list (default first).

    The planning prompt (``packages/generation/planning/plan.py``) reads this
    so ``planningModel`` sees the registered treatment ids. Reads the same JSON
    the dispatcher uses, so the catalogue can never drift from the runtime
    variant->treatment table.
    """
    return {
        section_id: list(block["treatments"])
        for section_id, block in load_section_treatments().items()
    }
