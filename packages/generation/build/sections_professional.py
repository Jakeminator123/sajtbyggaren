"""Professional-services + agency-studio section renderers.

Extracted verbatim from ``packages/generation/build/renderers.py`` per
``docs/refactor/megafiles-plan.md`` (Del 1, slice 3 — the
"professional-services + agency" family). Beteendebevarande: funktions-
kropparna är ordagrant kopierade (inkl. kommentarer och ``# noqa``-rader)
och samma section-id → renderer-poster registreras i
``dispatcher._SECTION_RENDERERS`` på exakt samma sätt.

Familjen täcker de PS-/studio-specifika sektionerna:
``industries-served``, ``partners-grid``, ``insights-list``,
``selected-work-preview`` (+ dess tre privata treatment-renderare),
``selected-work-grid``, ``capabilities-row``, ``manifesto-block``,
``process-steps`` och ``client-roster``.

Self-registrering: ``renderers`` importerar denna modul vid sin egen
import-svans, vilket kör ``_SECTION_RENDERERS.update({...})`` nederst i
filen och fyller registret innan någon anropare använder det. ``renderers``
re-exporterar dessutom varje publikt ``render_section_*``-namn så att
``from packages.generation.build.renderers import ...`` (och
``scripts.build_site``-fasaden) fortsätter resolva oförändrat.

Tvärberoenden: ``_treatment_for_section`` / ``_operator_pin_for_section``
hämtas från ``dispatcher`` och ``RenderBlueprint`` från
``blueprint_render`` (deras nuvarande hem). De delade format-/CTA-hjälparna
``_jsx_safe_string`` och ``_text_contact_cta`` bor fortfarande i
``renderers.py`` (deras flytt till ett delat hjälpar-hem är megafiles-plan
Del 1 slice 5, en separat lane); de nås här via en CALL-TIME-shim
(``_renderers()``) så import-grafen förblir cykelfri — den här modulen
importerar aldrig ``renderers`` vid modul-laddning.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from packages.generation.build.blueprint_render import RenderBlueprint
from packages.generation.build.dispatcher import (
    _SECTION_RENDERERS,
    _operator_pin_for_section,
    _treatment_for_section,
)


def _renderers() -> ModuleType:
    """Return the fully-imported ``renderers`` module at CALL time.

    The section renderers below reach two shared format-/CTA-helpers
    (``_jsx_safe_string``, ``_text_contact_cta``) that still live in
    ``packages.generation.build.renderers``. Resolving the module lazily
    at call time — never at import time — keeps the import graph acyclic:
    ``renderers`` imports this module at its tail to self-register, and
    this module never imports ``renderers`` while it is loading.
    """
    module = sys.modules.get("packages.generation.build.renderers")
    if module is not None:
        return module
    from packages.generation.build import renderers

    return renderers


def _jsx_safe_string(text: str) -> str:
    return _renderers()._jsx_safe_string(text)


def _text_contact_cta(*args: Any, **kwargs: Any) -> str:
    return _renderers()._text_contact_cta(*args, **kwargs)


def render_section_industries_served(dossier: dict) -> str:
    """Render an industries-served row for professional-services scaffolds.

    Reads ``location.serviceAreas`` (which for a professional-
    services firm is the natural place to declare served markets
    or industries — a multi-office advokatbyrå already uses this
    field for its office cities or covered regions, an audit firm
    might list industries served) and emits a compact pill row
    under a "Branscher och marknader vi arbetar inom" eyebrow.
    Visually identifiable as PS — uppercase eyebrow, monospace
    pill labels, no icons — and structurally separate from the
    LSB service-area block which renders the same field as a
    travel-distance trust message.

    Returns "" when the field is empty so the dispatcher does
    not emit an empty pill row.
    """
    location = dossier.get("location") or {}
    areas = location.get("serviceAreas") or []
    cleaned: list[str] = [item.strip() for item in areas if isinstance(item, str) and item.strip()]
    if not cleaned:
        return ""
    pills = "\n".join(
        f'            <li key={_jsx_safe_string(area)} className="rounded-sm border border-[color:var(--border)] bg-[color:var(--background)] px-4 py-2 text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(area)}</li>'
        for area in cleaned
    )
    return (
        '      <section className="border-t border-[color:var(--border)] bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/10">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.7)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Branscher och marknader vi arbetar inom</p>\n'
        '          <ul className="flex flex-wrap gap-2">\n'
        f"{pills}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_partners_grid(dossier: dict) -> str:
    """Render a formal partners grid for professional-services scaffolds.

    Reads ``company.team`` and presents each named member as a
    formal partner card with their role on a separate eyebrow
    line — the visual convention of an advokatbyrå or
    revisionsbyrå roster. Bigger cards than the clinic
    ``team-block``, more typographic restraint than the LSB
    team renderer; the layout is designed so that bar
    admissions, audit registrations or "delägare sedan ÅÅÅÅ"
    dates read as the primary attribute.

    Returns "" when no team is declared so the dispatcher does
    not emit a hollow grid.
    """
    company = dossier.get("company") or {}
    team = company.get("team") or []
    members: list[dict] = [m for m in team if isinstance(m, dict) and m.get("name") and m.get("role")]
    if not members:
        return ""
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(member["name"])} className="flex flex-col gap-2 border-t border-[color:var(--border)] pt-6">\n'
        f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(member["role"])}</p>\n'
        f'              <h3 className="text-2xl font-semibold tracking-tight">{_jsx_safe_string(member["name"])}</h3>\n'
        "            </article>"
        for member in members
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Partners och rådgivare</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Vårt team</h2>\n'
        "          </header>\n"
        '          <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_insights_list(dossier: dict) -> str:  # noqa: ARG001 — dossier reserved for future insights schema
    """Render an insights / publications row for professional-services.

    The current project-input schema does not carry a structured
    ``insights`` collection, so this renderer is intentionally a
    no-op — it returns ``""`` until a future schema extension lets
    a dossier declare publications. Registering it now means PS
    sections.json can list ``insights-list`` as an optional
    section without crashing the dispatcher; once the schema
    grows the renderer can be filled in without touching the
    contract.
    """
    return ""


_SELECTED_WORK_PREVIEW_TREATMENT_DEFAULT = "editorial-stack"


def render_section_selected_work_preview(
    dossier: dict,
    *,
    contact_path: str | None = "/kontakta-oss",  # noqa: ARG001 — included for kwarg-call symmetry; preview uses /arbeten as the explicit follow link
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the home-page Selected Work preview for agency-studio.

    Section design-treatments (Phase 1 pilot + Phase 2 expansion):
    the section resolves a treatment id via
    ``_treatment_for_section`` and routes the same dossier data
    through one of three private renderers:

    * ``editorial-stack`` — the byte-identical default that preserves
      pre-pilot snapshots. Vertical 2-col grid, every card sits on
      the same baseline with a thin top border and a "Case 01"
      eyebrow.
    * ``asymmetric-grid`` — offset 2-col grid where every other card
      is vertically translated by ``md:translate-y-12`` and rendered
      as an enclosed surface card with a "Studio nº 01" eyebrow.
      Same services, deliberately broken rhythm.
    * ``marquee-row`` — horizontal scroll-snap rail with six tight
      cards, "Studio reel"-eyebrow and a gradient fade hint on the
      right edge. No auto-animation in Phase 2; reduced-motion users
      get the same browseable rail. Mapped to ``bold-electric``.

    The variant-to-treatment mapping lives in
    ``_SECTION_TREATMENTS_BY_VARIANT`` so the section renderer itself
    does not have to know about variants — only about treatments.

    Returns "" when no work is declared so the dispatcher does not
    emit an empty grid regardless of treatment.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "selected-work-preview",
        default=_SELECTED_WORK_PREVIEW_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(
            dossier, "selected-work-preview"
        ),
        visual_direction_pick=(
            blueprint.section_treatment_pick("selected-work-preview")
            if blueprint is not None
            else None
        ),
    )
    if treatment == "asymmetric-grid":
        return _render_selected_work_preview_asymmetric_grid(services)
    if treatment == "marquee-row":
        return _render_selected_work_preview_marquee_row(services)
    return _render_selected_work_preview_editorial_stack(services)


def _render_selected_work_preview_editorial_stack(services: list[dict]) -> str:
    """Vertical 2-col grid where every card sits on a shared baseline.

    The default treatment for ``selected-work-preview``. Kept
    byte-identical to the pre-pilot output of the section renderer
    so existing snapshots (editorial-warm, bold-electric) are not
    invalidated by the introduction of treatment dispatch.
    """
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-4 border-t border-[color:var(--border)] pt-8">\n'
        f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Case {idx:02d}")}</p>\n'
        f'              <h3 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        '              <a href={"/arbeten"} className="mt-2 inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se case<ArrowRight className="size-4" /></a>\n'
        "            </article>"
        for idx, svc in enumerate(services[:4], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-12 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Selected work</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Senaste arbeten</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-12 md:grid-cols-2">\n'
        f"{cards}\n"
        "          </div>\n"
        '          <a href={"/arbeten"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Hela arbets-arkivet<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_selected_work_preview_asymmetric_grid(services: list[dict]) -> str:
    """Offset 2-col grid where every other card is vertically translated.

    Visually breaks the editorial baseline by pushing every odd-
    indexed card down with ``md:translate-y-12`` and rendering each
    card as a self-contained surface (``bg-[color:var(--card)]`` +
    ``rounded-[var(--radius-lg)]`` + generous padding) instead of
    the flat top-border card used in ``editorial-stack``. The
    eyebrow is reframed as "Studio nº NN" so the visual identity
    reads as a curated studio index rather than a project log.

    Same data as ``editorial-stack``; only the spatial rhythm and
    surface treatment differ.
    """
    cards = "\n".join(
        (
            f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[color:var(--border)] bg-[color:var(--card)] p-8 md:p-10'
            + (' md:translate-y-12' if idx % 2 == 0 else '')
            + '">\n'
            f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Studio nº {idx:02d}")}</p>\n'
            f'              <h3 className="text-2xl font-semibold tracking-tight md:text-4xl">{_jsx_safe_string(svc["label"])}</h3>\n'
            f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            '              <a href={"/arbeten"} className="mt-auto inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se case<ArrowRight className="size-4" /></a>\n'
            "            </article>"
        )
        for idx, svc in enumerate(services[:4], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-16 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Selected work</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Senaste arbeten</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-x-10 gap-y-12 md:grid-cols-2 md:gap-x-16 md:pb-16">\n'
        f"{cards}\n"
        "          </div>\n"
        '          <a href={"/arbeten"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Hela arbets-arkivet<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_selected_work_preview_marquee_row(services: list[dict]) -> str:
    """Horizontal scroll-snap rail with up to six tight cards.

    Reads as a "studio reel" — six cards (vs four in editorial-stack
    and asymmetric-grid) packed into a horizontal scroll container
    with ``snap-x snap-mandatory`` so each card snaps into view.
    Cards have a fixed minimum width so they do not collapse on
    narrow viewports, and the right edge has a gradient mask
    suggesting "more to scroll". The eyebrow becomes "Studio reel"
    to telegraph the motion-led identity bold-electric leans into.

    Phase 2 deliberately does NOT auto-animate the rail. Reduced-
    motion users get the same browseable scroll-snap experience as
    everyone else; only the user's own scroll input drives the row.
    Phase 3 may add a ``prefers-reduced-motion: no-preference``-
    gated CSS animation if operator feedback wants it.
    """
    cards = "\n".join(
        (
            f'              <article key={_jsx_safe_string(svc["id"])} className="flex w-[18rem] shrink-0 snap-start flex-col gap-3 rounded-[var(--radius-lg)] border border-[color:var(--border)] bg-[color:var(--card)] p-6 md:w-[22rem] md:p-8">\n'
            f'                <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Studio reel · {idx:02d}")}</p>\n'
            f'                <h3 className="text-xl font-semibold tracking-tight md:text-2xl">{_jsx_safe_string(svc["label"])}</h3>\n'
            f'                <p className="text-sm text-[color:var(--muted)] leading-relaxed line-clamp-4">{_jsx_safe_string(svc["summary"])}</p>\n'
            '                <a href={"/arbeten"} className="mt-auto inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se case<ArrowRight className="size-4" /></a>\n'
            "              </article>"
        )
        for idx, svc in enumerate(services[:6], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-12 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Studio reel</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Senaste arbeten</h2>\n'
        "          </div>\n"
        '          <div className="relative -mr-[max(0px,calc((100vw-var(--container-width))/2))]">\n'
        '            <div className="flex snap-x snap-mandatory gap-6 overflow-x-auto pb-6 pr-[max(2rem,calc((100vw-var(--container-width))/2))] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">\n'
        f"{cards}\n"
        "            </div>\n"
        '            <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-[color:var(--background)] to-transparent" />\n'
        "          </div>\n"
        '          <a href={"/arbeten"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Hela arbets-arkivet<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_selected_work_grid(
    dossier: dict,
    *,
    contact_path: str | None = "/kontakta-oss",
) -> str:
    """Render the full Selected Work catalogue for agency-studio /arbeten.

    Iterates the entire ``dossier.services`` array as case studies
    and emits a single-column editorial layout — large project
    label, generous reading width on the summary, and a quiet
    "Diskutera projekt"-link at the bottom of each entry pointing
    at the contact route. Distinct from the LSB ``service-list``
    (vertical, icon-led, USP bullets), the clinic ``treatment-list``
    (clinical menu) and the PS ``practice-grid`` (3-col counsel
    cards) — agency work pages read as a magazine spread, not a
    services catalogue.

    Returns "" when no work is declared so the dispatcher does
    not emit an empty list scaffold.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    items = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-5 border-t border-[color:var(--border)] py-12 first:border-t-0 first:pt-0 last:pb-0">\n'
        f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Case {idx:02d}")}</p>\n'
        f'              <h2 className="max-w-3xl text-3xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="max-w-3xl text-base text-[color:var(--muted)] leading-relaxed md:text-lg">{_jsx_safe_string(svc["summary"])}</p>\n'
        + _text_contact_cta(
            contact_path,
            "Diskutera projekt",
            indent="              ",
        )
        + "            </li>"
        for idx, svc in enumerate(services, start=1)
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-12 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Arkivet</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">Selected work</h1>\n'
        "          </header>\n"
        '          <ul className="flex flex-col">\n'
        f"{items}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_capabilities_row(dossier: dict) -> str:
    """Render a horizontal capabilities row for agency-studio.

    Reads ``dossier.tone.secondary`` (the studio's secondary tone
    descriptors are the most natural place to lift discipline
    keywords like 'Brand identity', 'Motion', 'Web' until the
    project-input schema grows a structured capabilities array)
    and renders them as a single horizontal row of monospace
    pills under a "What we make"-eyebrow. Distinct from the LSB
    services-summary block (cards) and the PS industries-served
    block (uppercase pills under a different framing) — agency
    capabilities read as a one-liner taxonomy, not a card grid.

    Returns "" when no tone descriptors are declared so the
    dispatcher does not emit a hollow row.
    """
    tone = dossier.get("tone") or {}
    secondary = tone.get("secondary") or []
    cleaned: list[str] = [item.strip() for item in secondary if isinstance(item, str) and item.strip()]
    if not cleaned:
        return ""
    pills = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="text-sm font-mono uppercase tracking-widest">{_jsx_safe_string(label)}</li>'
        for label in cleaned
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.6)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">What we make</p>\n'
        '          <ul className="flex flex-wrap gap-x-10 gap-y-3">\n'
        f"{pills}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_manifesto_block(dossier: dict) -> str:
    """Render a manifesto statement for agency-studio.

    Lifts ``dossier.company.tagline`` and reads it as the studio's
    point of view, presented as a single full-width oversized
    typographic statement. No icons, no decoration — the section
    is the studio's voice. Distinct from the LSB hero (CTA-led)
    and the PS about story (multi-paragraph) — a manifesto is
    one sentence done loud.

    Returns "" when the dossier carries no tagline so the
    dispatcher does not emit a hollow section.
    """
    company = dossier.get("company") or {}
    tagline = company.get("tagline")
    if not isinstance(tagline, str) or not tagline.strip():
        return ""
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--background)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*1.2)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Manifest</p>\n'
        f'          <p className="max-w-4xl text-3xl font-semibold leading-tight tracking-tight md:text-5xl lg:text-6xl">{_jsx_safe_string(tagline.strip())}</p>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_process_steps(dossier: dict) -> str:  # noqa: ARG001 — dossier reserved for studio-supplied process descriptions
    """Render a four-step studio-process block for agency-studio.

    Renders a fixed four-step process (Discovery → Concept →
    Production → Launch) as a numbered horizontal flow. Each step
    has a Roman-style numeric label, a step name and a short
    descriptor pulled from the studio's voice manual rather than
    the dossier — the names are the actual stages a producer
    would recognise from any well-run studio engagement, so the
    section can render even when the dossier carries no
    structured process data.

    Once project-input.schema.json grows a structured
    ``process[]`` array the renderer can be extended to read it;
    until then the fixed step names are a deliberate, non-mock
    studio convention.
    """
    steps = (
        ("01", "Discovery", "Vi lyssnar, läser och kartlägger så att vi vet vad arbetet faktiskt ska göra."),
        ("02", "Concept", "Skriver, skissar och visar riktning. Vi visar val, inte färdiga lösningar."),
        ("03", "Production", "Designar, kodar, animerar — det praktiska arbetet där studion bygger sakerna."),
        ("04", "Launch", "Vi sjösätter med er och stannar kvar för att se hur arbetet beter sig i världen."),
    )
    cells = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="flex flex-col gap-3 border-l border-[color:var(--border)] pl-6">\n'
        f'              <span className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(idx)}</span>\n'
        f'              <h3 className="text-xl font-semibold tracking-tight">{_jsx_safe_string(label)}</h3>\n'
        f'              <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(blurb)}</p>\n'
        "            </li>"
        for idx, label, blurb in steps
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Process</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Så jobbar vi</h2>\n'
        "          </header>\n"
        '          <ol className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">\n'
        f"{cells}\n"
        "          </ol>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_client_roster(dossier: dict) -> str:
    """Render a text-only client roster for agency-studio.

    Reads ``dossier.trustSignals`` (the same field LSB uses for
    trust bullets) and renders each entry as a discreet pill —
    no logos, just names — under a "Selected clients"-eyebrow.
    Studios usually decline to publish actual logos for
    procurement reasons; a text roster captures the recognition
    signal without the image-rights complication. Visually
    distinct from the clinic credentials block (badges) and the
    PS credentials block (registrations) — agency rosters read as
    a casually arranged list, not a regulated certification panel.

    Returns "" when no entries are declared so the dispatcher
    does not emit a hollow section.
    """
    trust_raw = dossier.get("trustSignals") or []
    entries: list[str] = []
    for item in trust_raw:
        if isinstance(item, str) and item.strip():
            entries.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label")
            if isinstance(label, str) and label.strip():
                entries.append(label.strip())
    if not entries:
        return ""
    pills = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="text-sm text-[color:var(--muted)]">{_jsx_safe_string(label)}</li>'
        for label in entries
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.7)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Selected clients</p>\n'
        '          <ul className="grid gap-x-10 gap-y-2 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{pills}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


_SECTION_RENDERERS.update(
    {
        "industries-served": render_section_industries_served,
        "partners-grid": render_section_partners_grid,
        "insights-list": render_section_insights_list,
        "selected-work-preview": render_section_selected_work_preview,
        "selected-work-grid": render_section_selected_work_grid,
        "capabilities-row": render_section_capabilities_row,
        "manifesto-block": render_section_manifesto_block,
        "process-steps": render_section_process_steps,
        "client-roster": render_section_client_roster,
    }
)
