"""Section dispatcher + treatment-resolution helpers for the Path B builder.

Extracted from ``scripts/build_site.py`` during the B146 port (2026-05-25)
so that Christopher's PR #105 + PR #108 section architecture sits next to
``renderers.py`` instead of re-inflating ``build_site.py`` past 7k rader.

Surface area:

* ``_SECTION_RENDERERS`` — the section-id → renderer registry. Defined
  empty here and populated by ``renderers`` at import time via
  ``_SECTION_RENDERERS.update({...})`` blocks (mirrors how
  ``main:scripts/build_site.py`` did it ord-för-ord, just in a sibling
  module).
* ``_SCAFFOLD_SECTIONS_CACHE`` — per-scaffold-dir cache for
  ``sections.json`` (Path B's deterministic source-of-truth for a
  route's section list).
* ``_SECTION_TREATMENTS_BY_VARIANT`` + ``_treatment_for_section`` +
  ``_operator_pin_for_section`` — the three-tier section-design-treatment
  resolver (Phase 1/2 variant-default → Phase 3 operator-pin per ADR 0032,
  née ADR 0031 on main pre-port).
* ``_load_scaffold_sections``, ``_section_renderer_kwargs``,
  ``_call_section_renderer`` — internal helpers used by
  ``render_route_generic`` and by individual section renderers that opt
  into treatment dispatch.
* ``render_route_generic`` — composes a route's body from the section
  ids declared in a scaffold's ``sections.json``.

ADR pointer: ADR 0032 — section-treatments som additiv directive
(Phase 3 schema-bump). On ``origin/main`` this is ADR 0031; renumbered
to 0032 during the B146 port because jakob-be:s ADR 0031 (Steward
auto-bump, PR #106) was already merged when this work landed.
"""

from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

_SECTION_RENDERERS: dict[str, Callable[..., str]] = {}
"""Section-id → renderer registry.

Populated by ``packages.generation.build.renderers`` at module import
time. Kept empty here so the module has no implicit dependency on the
renderer module; ``render_route_generic`` only looks the registry up at
call time, by which point ``renderers`` has already populated it.
"""


_SCAFFOLD_SECTIONS_CACHE: dict[Path, dict] = {}


def _load_scaffold_sections(scaffold_dir: Path) -> dict:
    """Load and cache ``sections.json`` for a scaffold directory.

    Returns an empty dict if the file is missing so a scaffold without
    a sections.json simply makes the dispatcher a no-op for unknown
    routes (the caller falls back to its specialised renderer).
    """
    cached = _SCAFFOLD_SECTIONS_CACHE.get(scaffold_dir)
    if cached is not None:
        return cached
    sections_path = scaffold_dir / "sections.json"
    if not sections_path.is_file():
        _SCAFFOLD_SECTIONS_CACHE[scaffold_dir] = {}
        return {}
    try:
        loaded = json.loads(sections_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            "Builder failed: scaffold sections.json at "
            f"{sections_path} is not valid JSON ({exc.msg} at "
            f"line {exc.lineno}). Path B requires a parsable "
            "sections.json so render_route_generic can compose the "
            "route's sections deterministically."
        ) from exc
    if not isinstance(loaded, dict):
        raise SystemExit(
            "Builder failed: scaffold sections.json at "
            f"{sections_path} must be a JSON object whose keys are "
            "route ids (e.g. \"home\", \"menu\"). Found "
            f"{type(loaded).__name__}."
        )
    _SCAFFOLD_SECTIONS_CACHE[scaffold_dir] = loaded
    return loaded


@functools.cache
def _section_renderer_kwargs(renderer: Callable[..., str]) -> tuple[str, ...]:
    """Return the keyword-argument names a section renderer accepts.

    Cached because the dispatcher hits each renderer once per route per
    build and ``inspect.signature`` is not cheap. The first positional
    parameter (``dossier``) is always passed positionally and is
    omitted from the returned tuple.
    """
    sig = inspect.signature(renderer)
    return tuple(
        name
        for name in sig.parameters
        if name != "dossier" and sig.parameters[name].kind
        in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    )


def _call_section_renderer(
    renderer: Callable[..., str],
    dossier: dict,
    kwargs: dict[str, Any],
) -> str:
    """Call a section renderer passing only the kwargs it accepts.

    Any extra kwargs in ``kwargs`` are silently dropped so callers can
    pass a uniform context bag to every renderer in a route without
    each renderer having to declare ``**kwargs`` itself.
    """
    accepted = _section_renderer_kwargs(renderer)
    filtered = {name: kwargs[name] for name in accepted if name in kwargs}
    return renderer(dossier, **filtered)


# Section design-treatments — variant-driven visual variation inside a
# single section id. See docs/section-design-treatments-scout.md for
# the three-tier resolution order (operator-pin → variant → section
# default). Phase 1+2 registered the variant tier across five sections;
# Phase 3 (ADR 0032, post-B146; ADR 0031 on origin/main pre-port,
# 2026-05-25) layered operator-pin
# (``dossier.directives.sectionTreatments``) on top via
# ``_treatment_for_section(operator_pin=...)`` without changing the
# section-renderer signatures. A future Phase 4 (kor-3b) will add an
# LLM-pick step in front of operator-pin; the helper signature is
# designed to absorb that without touching renderers.
#
# Renderers that opt in declare ``variant_id: str | None = None`` in
# their signature and call ``_treatment_for_section`` to pick the
# treatment id; ``_call_section_renderer`` already threads
# ``variant_id`` through the dispatcher (Path B native scaffolds
# pass it from ``_render_dispatched_route``).
#
# kor-3a (2026-06-03): the variant→treatment truth used to live in a
# hardcoded Python dict here and was mirrored, by hand, by
# ``_SECTION_TREATMENTS_CATALOGUE`` in ``packages/generation/planning/
# plan.py``. Both tables now read ONE declarative source on disk —
# ``scaffolds/<id>/section-treatments.json`` — so the dispatcher and
# the planning prompt can never drift again. This module owns the
# loader (``load_section_treatments`` /
# ``load_section_treatments_catalogue``) and exposes the same flat
# variant→{section: treatment} view via ``_SECTION_TREATMENTS_BY_VARIANT``
# that the resolver and the existing tests already expect. No render
# output changed: the JSON encodes the exact pairs the dict used to
# hold (byte-for-byte parity, asserted in
# ``tests/test_section_treatments_json_parity.py``).
#
# Each ``section-treatments.json`` block is::
#
#     {"sections": {"<section-id>": {
#         "treatments": ["<section-default>", "<variant treatment>", ...],
#         "byVariant": {"<variant-id>": "<treatment-id>", ...}}}}
#
# ``treatments[0]`` is the section default (what a variant that does
# not register the section inherits); the remaining ids are the
# variant-specific treatments. Variants absent from ``byVariant``
# (e.g. ``editorial-warm``, ``clinic-calm``, ``midnight-counsel``,
# ``pulse-fit``) deliberately inherit the section default. Section ids
# are scaffold-unique, so flattening every file into one
# variant-keyed map is unambiguous.
_SECTION_TREATMENTS_DIR = (
    Path(__file__).resolve().parents[1] / "orchestration" / "scaffolds"
)


@functools.cache
def load_section_treatments() -> dict[str, dict[str, Any]]:
    """Load the declarative section-treatment truth from every scaffold.

    Returns a per-section catalogue keyed by section id::

        {section_id: {"treatments": [...], "byVariant": {variant: treatment}}}

    This is the single on-disk source of truth that both the build
    dispatcher (variant → treatment resolution, via
    ``_SECTION_TREATMENTS_BY_VARIANT``) and the planning prompt catalogue
    (section → treatment list, via ``load_section_treatments_catalogue``)
    consume. Scaffolds without a ``section-treatments.json`` simply
    contribute nothing. Result is cached because the files are read once
    per process and never mutate at runtime; tests that need a re-read
    can call ``load_section_treatments.cache_clear()``.
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
        sections = loaded.get("sections") if isinstance(loaded, dict) else None
        if not isinstance(sections, dict):
            continue
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
    """Section-id → ordered treatment-id list (default first).

    The planning prompt (``packages/generation/planning/plan.py``) reads
    this so ``planningModel`` sees the registered treatment ids. Reads the
    same JSON the dispatcher uses, so the catalogue can never drift from
    the runtime variant→treatment table.
    """
    return {
        section_id: list(block["treatments"])
        for section_id, block in load_section_treatments().items()
    }


def _build_section_treatments_by_variant() -> dict[str, dict[str, str]]:
    """Flatten the per-section JSON into the variant→{section: treatment} map.

    Section ids are scaffold-unique and each variant belongs to exactly
    one scaffold, so the flattening is collision-free.
    """
    by_variant: dict[str, dict[str, str]] = {}
    for section_id, block in load_section_treatments().items():
        for variant_id, treatment_id in block["byVariant"].items():
            by_variant.setdefault(variant_id, {})[section_id] = treatment_id
    return by_variant


# Thin module-level wrapper around the JSON read above, kept so the
# resolver (``_treatment_for_section``) and the long-standing tests /
# external callers can keep using the ``_SECTION_TREATMENTS_BY_VARIANT``
# spelling. It is no longer a source of truth — the JSON is.
_SECTION_TREATMENTS_BY_VARIANT: dict[
    str, dict[str, str]
] = _build_section_treatments_by_variant()


def _operator_pin_for_section(dossier: dict, section_id: str) -> str | None:
    """Read the operator's section-treatment pin for ``section_id``.

    Phase 3 (ADR 0032): the wizard's visual-step writes operator pins
    to ``directives.sectionTreatments`` in Project Input. Because
    ``dossier`` is loaded directly from Project Input by ``main()``,
    the same key is available here unchanged.

    Returns ``None`` for an absent or empty pin so callers can keep
    using the simple ``operator_pin or fallback``-style guard.

    The lookup is intentionally lenient: it does NOT validate the
    treatment id against ``_SECTION_TREATMENTS_BY_VARIANT`` because
    the schema enum in ``project-input.schema.json`` already rejects
    typos before the dossier reaches this code path. Defensive
    re-validation here would just duplicate that logic and risk
    drifting out of sync with the schema. ``_treatment_for_section``
    still passes the value through ``operator_pin`` only when it is
    a non-empty string, so a malformed dossier (e.g. a hand-edited
    file that bypassed the schema) cannot crash the renderer; the
    section renderer's own ``if treatment == ...`` chain falls
    through to the section default in that case.
    """
    if not isinstance(dossier, dict):
        return None
    directives = dossier.get("directives")
    if not isinstance(directives, dict):
        return None
    pins = directives.get("sectionTreatments")
    if not isinstance(pins, dict):
        return None
    pin = pins.get(section_id)
    if not isinstance(pin, str):
        return None
    pin = pin.strip()
    return pin or None


def _treatment_for_section(
    variant_id: str | None,
    section_id: str,
    *,
    default: str,
    operator_pin: str | None = None,
) -> str:
    """Resolve which design treatment a section should render.

    Resolution order (Phase 3, ADR 0032):

    1. ``operator_pin`` — explicit per-section treatment pinned by
       the operator in the wizard's visual step
       (``directives.sectionTreatments[section_id]``). Wins over
       everything because the operator has expressed intent.
    2. ``_SECTION_TREATMENTS_BY_VARIANT[variant_id][section_id]`` —
       the variant's curated default. Phase 2 baseline.
    3. ``default`` — the section's own fall-back treatment. Used
       when neither the operator nor the variant has an opinion, or
       when a future variant is introduced before its treatments
       are registered.

    The same ``default`` is returned for an unknown variant or for a
    variant that does not register the requested section so a
    section that opts into treatment dispatch never has to know
    which variants exist.

    The operator pin is treated as opaque here: validation is done
    by ``project-input.schema.json`` before the dossier loads. A pin
    coming from a hand-edited dossier that bypassed the schema may
    therefore route to an unknown treatment id, but that is the
    section renderer's contract to handle (treat unknown ids as the
    section default). We deliberately keep this helper trivial so
    the resolution order stays auditable at a glance.
    """
    if operator_pin:
        return operator_pin
    if not variant_id:
        return default
    bucket = _SECTION_TREATMENTS_BY_VARIANT.get(variant_id)
    if not bucket:
        return default
    treatment = bucket.get(section_id)
    if not treatment:
        return default
    return treatment


def render_route_generic(
    dossier: dict,
    *,
    route_id: str,
    scaffold_sections: dict,
    **kwargs: Any,
) -> str:
    """Compose a route body from its declared sections.

    Reads the section list for ``route_id`` from
    ``scaffold_sections[route_id]`` (a dict with
    ``requiredSections`` and optional ``optionalSections`` lists),
    looks each id up in ``_SECTION_RENDERERS`` and concatenates the
    resulting JSX fragments in declaration order — required sections
    first, optionals after — so a scaffold can extend a route just by
    appending an optional section to its sections.json.

    Returns the concatenated body fragments only. Page shell (icon
    imports, ``export default function``, ``<main>`` wrapper) is the
    caller's responsibility. Cross-section coordination (e.g. a
    testimonials section suppressing the trust-proof block) is also
    the caller's responsibility — the dispatcher itself stays
    deterministic and side-effect free.

    Raises ``SystemExit`` for section ids that have no registered
    renderer so a scaffold cannot silently emit an empty route by
    naming a section that does not exist yet.
    """
    route_block = scaffold_sections.get(route_id) or {}
    section_ids: list[str] = []
    required = route_block.get("requiredSections")
    if isinstance(required, list):
        section_ids.extend(str(item) for item in required if isinstance(item, str))
    optional = route_block.get("optionalSections")
    if isinstance(optional, list):
        section_ids.extend(str(item) for item in optional if isinstance(item, str))
    body_fragments: list[str] = []
    for section_id in section_ids:
        renderer = _SECTION_RENDERERS.get(section_id)
        if renderer is None:
            raise SystemExit(
                "Builder failed: section id "
                f"{section_id!r} (used by route {route_id!r}) has no "
                "renderer in _SECTION_RENDERERS in "
                "packages/generation/build/dispatcher.py. Add a "
                f"render_section_{section_id.replace('-', '_')}() "
                "function in packages/generation/build/renderers.py "
                "and register it, or remove the section from the "
                "scaffold's sections.json."
            )
        body_fragments.append(_call_section_renderer(renderer, dossier, kwargs))
    return "".join(body_fragments)
