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
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from packages.generation.orchestration.section_treatments import (
    load_section_treatments,
)
from packages.generation.orchestration.section_treatments import (
    load_section_treatments_catalogue as load_section_treatments_catalogue,
)

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


_SECTION_OPEN_TAG_RE = re.compile(r"<section(?=[\s>])")
_SECTION_MARKER_ATTR = "data-section-id"

_MAIN_OPEN_TAG_RE = re.compile(r"<main(?=[\s>])")
_ROUTE_MARKER_ATTR = "data-route-id"
# Same shape as scaffold route ids (and the sectionId guard in
# build_site.py) — belt-and-braces against attribute injection from a
# hand-edited Project Input.
_ROUTE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def annotate_route_marker(content: str, route_id: str) -> str:
    """Stamp the page's first ``<main>`` wrapper with its scaffold route id.

    Route-scoping för "Färglägg sektionen" (häver v1-begränsningen i
    ``sectionStyleOverrides``): globals.css-overriden kan selektera
    ``[data-route-id="<routeId>"] [data-section-id="<sectionId>"]`` så
    samma sectionId på två routes kan få OLIKA färger. Stämplas bara på
    routes som faktiskt har en override (write_pages avgör) så sajter
    utan funktionen får byte-identisk markup. Sidor utan ``<main>``
    eller med en redan satt markör passerar orörda; ogiltiga route-ids
    likaså (CSS-emissionen hoppar över samma poster).
    """
    if not content or "<main" not in content:
        return content
    if _ROUTE_MARKER_ATTR in content:
        return content
    if not _ROUTE_ID_RE.match(route_id):
        return content
    return _MAIN_OPEN_TAG_RE.sub(
        f'<main {_ROUTE_MARKER_ATTR}="{route_id}"', content, count=1
    )


def annotate_section_marker(fragment: str, section_id: str) -> str:
    """Stamp every ``<section>`` opening tag in ``fragment`` with its id.

    Preview-markeringskontraktet: varje emitterad sektion bär
    ``data-section-id="<sectionId>"`` så viewser-overlayn kan mappa ett
    klick till det kanoniska sektions-id:t från scaffoldens
    sections.json i stället för att gissa via DOM-heuristik. Renderers
    som emitterar flera ``<section>``-element för ett id (t.ex. hero
    med bildbanner + textblock) får samma id på alla — de är samma
    logiska modul. Fragment utan ``<section>`` (rena div-block som
    sidshims själva wrappar) lämnas orörda; deras shim sätter
    attributet på sin egen wrapper. Tomma fragment passerar orörda så
    runtime-suppression aldrig producerar tomma markörer.
    """
    if not fragment or "<section" not in fragment:
        return fragment
    if _SECTION_MARKER_ATTR in fragment:
        return fragment
    return _SECTION_OPEN_TAG_RE.sub(
        f'<section {_SECTION_MARKER_ATTR}="{section_id}"', fragment
    )


# Section design-treatments — variant-driven visual variation inside a
# single section id. See docs/section-design-treatments-scout.md for
# the three-tier resolution order (operator-pin → variant → section
# default). Phase 1+2 registered the variant tier across five sections;
# Phase 3 (ADR 0032, post-B146; ADR 0031 on origin/main pre-port,
# 2026-05-25) layered operator-pin
# (``dossier.directives.sectionTreatments``) on top via
# ``_treatment_for_section(operator_pin=...)``. kor-3b (2026-06-03)
# then added the blueprint-driven ``visual_direction_pick`` tier
# BETWEEN operator-pin and variant-default (final order:
# operator-pin > visualDirection > variant-default > section-default).
# The pick value is read from the Generation Package
# ``visualDirection.sectionTreatments`` by
# ``blueprint_render.RenderBlueprint.section_treatment_pick`` and threaded
# into ``_treatment_for_section(visual_direction_pick=...)`` by the five
# treatment-dispatch section renderers; it is validated against the
# section's supported treatments here so an unsupported treatment can
# never be chosen.
#
# Renderers that opt in declare ``variant_id: str | None = None`` in
# their signature and call ``_treatment_for_section`` to pick the
# treatment id; ``_call_section_renderer`` already threads
# ``variant_id`` through the dispatcher (Path B native scaffolds
# pass it from ``_render_dispatched_route``).
#
# kor-3a (2026-06-03): the variant->treatment truth used to live in a
# hardcoded Python dict here and was mirrored, by hand, by
# ``_SECTION_TREATMENTS_CATALOGUE`` in ``packages/generation/planning/
# plan.py``. Both tables now read ONE declarative source on disk --
# ``orchestration/scaffolds/<id>/section-treatments.json`` -- so the
# dispatcher and the planning prompt can never drift again.
#
# Pushvakt P1 (2026-06-03): the loaders (``load_section_treatments`` /
# ``load_section_treatments_catalogue``) were moved out of this build
# module into ``packages/generation/orchestration/section_treatments.py``
# so fas-2 ``planning`` no longer imports fas-3 ``build`` (repo-boundaries
# v10). They are imported at the top of this module and re-exported, so
# the resolver, the parity tests and external callers keep the same
# ``packages.generation.build.dispatcher`` import path. The flat
# variant->{section: treatment} view ``_SECTION_TREATMENTS_BY_VARIANT`` is
# still built here from that single source (byte-for-byte parity, asserted
# in ``tests/test_section_treatments_json_parity.py``).


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


def _supported_treatments_for_section(section_id: str) -> tuple[str, ...]:
    """Return the treatment ids the renderer supports for ``section_id``.

    Reads the same declarative JSON truth (kor-3a,
    ``scaffolds/<id>/section-treatments.json``) that the variant table and the
    planning catalogue consume, via :func:`load_section_treatments`. Because
    every consumer reads one source on disk, the "supported set" used to gate
    the kor-3b visual-direction pick can never drift from what the renderers
    can actually emit. Returns an empty tuple for a section that declares no
    treatments — then no visual-direction pick is ever accepted for it.
    """
    block = load_section_treatments().get(section_id)
    if not isinstance(block, dict):
        return ()
    treatments = block.get("treatments")
    if not isinstance(treatments, list):
        return ()
    return tuple(item for item in treatments if isinstance(item, str))


def _visual_direction_pick_for_section(
    section_id: str, candidate: str | None
) -> str | None:
    """Validate a blueprint visual-direction treatment pick for ``section_id``.

    kor-3b: the Generation Package ``visualDirection.sectionTreatments`` may
    name the treatment a section should render (see
    ``blueprint_render.RenderBlueprint.section_treatment_pick`` for how the
    address-keyed map is read). The pick is honoured ONLY when it is a
    treatment the renderer actually supports for THAT section — i.e. it is in
    the section-specific ``treatments`` list of the kor-3a JSON. A candidate
    that is empty, unknown, or only valid for a *different* section (e.g.
    ``tag-cluster`` belongs to ``expertise-areas``, never ``service-list``) is
    rejected by returning ``None`` so the resolver falls through to the
    variant/section default.

    This is the runtime half of the "an unsupported treatment can never be
    chosen" guarantee; the ``generation-package.schema.json``
    ``visualDirection.sectionTreatments`` enum is the static half (it rejects
    treatment ids unknown to every section before the artefakt is even built).
    """
    if not isinstance(candidate, str):
        return None
    candidate = candidate.strip()
    if not candidate:
        return None
    if candidate not in _supported_treatments_for_section(section_id):
        return None
    return candidate


def _treatment_for_section(
    variant_id: str | None,
    section_id: str,
    *,
    default: str,
    operator_pin: str | None = None,
    visual_direction_pick: str | None = None,
) -> str:
    """Resolve which design treatment a section should render.

    Resolution order (kor-3b, layered on Phase 3 / ADR 0032):

    1. ``operator_pin`` — explicit per-section treatment pinned by
       the operator in the wizard's visual step
       (``directives.sectionTreatments[section_id]``). Wins over
       everything because the operator has expressed intent.
    2. ``visual_direction_pick`` — the blueprint's
       ``visualDirection.sectionTreatments`` choice (from kor-1c),
       validated against the section's supported treatments via
       :func:`_visual_direction_pick_for_section`. This is where the
       same scaffold+variant gets a different feel from a different
       blueprint without any new CSS. An unsupported / unknown pick is
       ignored here (it never shadows the variant default).
    3. ``_SECTION_TREATMENTS_BY_VARIANT[variant_id][section_id]`` —
       the variant's curated default. Phase 2 baseline.
    4. ``default`` — the section's own fall-back treatment. Used
       when none of the above has an opinion, or when a future
       variant is introduced before its treatments are registered.

    The same ``default`` is returned for an unknown variant or for a
    variant that does not register the requested section so a
    section that opts into treatment dispatch never has to know
    which variants exist.

    Regression guarantee (kor-3a parity): with ``visual_direction_pick``
    left at its default ``None``, this function behaves byte-identically
    to the pre-kor-3b resolver — operator-pin → variant-default →
    section-default — so a build without a blueprint is unchanged.

    The operator pin is treated as opaque here: validation is done
    by ``project-input.schema.json`` before the dossier loads. A pin
    coming from a hand-edited dossier that bypassed the schema may
    therefore route to an unknown treatment id, but that is the
    section renderer's contract to handle (treat unknown ids as the
    section default). The visual-direction pick, by contrast, IS
    validated against the supported set here because it originates from
    a model-produced artefakt rather than an explicit operator choice.
    """
    if operator_pin:
        return operator_pin
    vd_pick = _visual_direction_pick_for_section(section_id, visual_direction_pick)
    if vd_pick:
        return vd_pick
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
        fragment = _call_section_renderer(renderer, dossier, kwargs)
        body_fragments.append(annotate_section_marker(fragment, section_id))
    return "".join(body_fragments)
