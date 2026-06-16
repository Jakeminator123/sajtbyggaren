"""Treatment/credential/expertise/practice section renderers.

Extracted verbatim from ``packages.generation.build.renderers`` per the
megafile refactor plan (``docs/refactor/megafiles-plan.md`` Del 1, slice
2): the clinic-healthcare + professional-services
"behandling/credential/expertis/practice" section family
(``render_section_treatment_summary``, ``render_section_treatment_list``,
``render_section_credentials``, ``render_section_expertise_areas`` and
``render_section_practice_grid``) plus the private treatment renderers
and per-section default-treatment constants only these use.

The family self-registers into ``dispatcher._SECTION_RENDERERS`` at
import time via the ``.update({...})`` block at the bottom, exactly as it
did inline in ``renderers.py``. ``renderers.py`` imports this module
(side-effect registration) and re-exports the five public
``render_section_*`` names, so existing
``from packages.generation.build.renderers import render_section_*`` and
``scripts.build_site`` spellings keep working unchanged.

The treatment-resolution helpers (``_treatment_for_section``,
``_operator_pin_for_section``) stay in ``dispatcher`` and are imported
here. The shared formatting/CTA helpers ``_jsx_safe_string`` and
``_text_contact_cta`` now live in ``render_helpers`` (their move there is
megafiles-plan Del 1 slice 5, done) and are imported directly from there.
This module therefore never imports ``renderers`` at module-import time,
so the import graph stays cycle-free.
"""

from __future__ import annotations

from packages.generation.build.blueprint_render import RenderBlueprint
from packages.generation.build.dispatcher import (
    _SECTION_RENDERERS,
    _operator_pin_for_section,
    _treatment_for_section,
)
from packages.generation.build.render_helpers import (
    _jsx_safe_string as _jsx_safe_string,
)
from packages.generation.build.render_helpers import (
    _text_contact_cta as _text_contact_cta,
)


def render_section_treatment_summary(
    dossier: dict,
    *,
    contact_path: str | None = "/kontakta-oss",
) -> str:
    """Render a compact home-page treatments preview for clinic-healthcare.

    Picks the first three services from the dossier (clinics use
    the services array as their treatment catalogue), renders each
    as a plain card with the treatment name and a short
    plain-language summary, and ends with a "Boka tid"-CTA pointing
    at the contact route. Visually calmer than the LSB
    services-summary block (no hover-lift, softer borders) so it
    sits well next to the credentials section a clinic home depends
    on for trust.

    Returns "" when the dossier carries no services so a generic
    landing page does not emit an empty grid.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    cards = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6">\n'
        f'              <h3 className="text-lg font-semibold">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services[:3]
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vård vi erbjuder</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Våra behandlingar</h2>\n'
        "          </div>\n"
        '          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </ul>\n" + _text_contact_cta(contact_path, "Boka tid") + "        </div>\n"
        "      </section>\n"
        "\n"
    )


_TREATMENT_LIST_TREATMENT_DEFAULT = "minimal-rows"


def render_section_treatment_list(
    dossier: dict,
    *,
    contact_path: str | None = "/kontakta-oss",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the full treatment list for the clinic /behandlingar route.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of three private renderers:

    * ``minimal-rows`` — the byte-identical default. Vertical list
      of rounded-2xl border-cards with a quiet typographic header.
      Mapped to ``clinic-calm`` so the calm clinic keeps the
      pre-Phase-2 menu feel.
    * ``split-cards`` — two-column grid of warmer cards where each
      treatment card carries a soft accent-tinted left rail and
      slightly bigger label typography. Mapped to ``warm-care``.
    * ``numbered-stack`` — sequence with large monospaced
      "01 / 02 / 03"-numerals and thin horizontal separators
      between rows. Reads as a clinical sequence rather than a
      menu of options. Mapped to ``modern-precision``.

    Returns "" when no services are declared so the dispatcher
    does not emit an empty list scaffold regardless of treatment.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "treatment-list",
        default=_TREATMENT_LIST_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "treatment-list"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("treatment-list") if blueprint is not None else None
        ),
    )
    if treatment == "split-cards":
        return _render_treatment_list_split_cards(services, contact_path)
    if treatment == "numbered-stack":
        return _render_treatment_list_numbered_stack(services, contact_path)
    return _render_treatment_list_minimal_rows(services, contact_path)


def _treatment_list_header() -> str:
    """Shared header markup for every treatment-list treatment.

    Kept as a single source so the eyebrow + h1 + supporting copy
    stay in lockstep across all three treatments. The Phase 3
    operator-pin tier (ADR 0032) only changes which treatment
    renderer dispatches; it does not (yet) override the header copy.
    """
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Behandlingar</p>\n'
        '            <h1 className="max-w-2xl text-4xl font-semibold tracking-tight md:text-5xl">Det här hjälper vi dig med</h1>\n'
        '            <p className="max-w-2xl text-base text-[color:var(--muted)] leading-relaxed">Beskrivningarna är skrivna i klarspråk. Är du osäker på vilken behandling som passar — ring eller skicka ett mejl så hjälper vi dig.</p>\n'
        "          </header>\n"
    )


def _render_treatment_list_minimal_rows(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """Vertical list of rounded border-cards (the default treatment).

    Kept byte-identical to the pre-Phase-2 output so existing
    snapshots and any clinic build that did not pin a variant in
    Phase 1 are not invalidated by introducing treatment dispatch.
    """
    items = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--background)] p-8">\n'
        f'              <h2 className="text-xl font-semibold tracking-tight md:text-2xl">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="mt-3 text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _treatment_list_header()
        + '          <ul className="flex flex-col gap-4">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + _text_contact_cta(contact_path, "Boka tid")
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_treatment_list_split_cards(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """Two-column grid of warm cards with an accent-tinted left rail.

    Reads as a warmer brochure than ``minimal-rows`` — slightly
    larger label typography, a soft accent-coloured left rail
    (``border-l-4 border-[color:var(--accent)]``) and card-surface
    background instead of a flat panel. Mapped to ``warm-care``.
    """
    items = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-3 rounded-2xl border border-[color:var(--border)] border-l-4 border-l-[color:var(--accent)] bg-[color:var(--card)] p-8">\n'
        f'              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _treatment_list_header()
        + '          <ul className="grid gap-6 md:grid-cols-2">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + _text_contact_cta(contact_path, "Boka tid")
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_treatment_list_numbered_stack(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """Sequence with monospaced numerals and thin horizontal separators.

    Reads as a clinical sequence: a large mono "01 / 02 / 03"
    numeral on the left, the treatment name and description on the
    right, and a thin ``border-b`` separator between rows. No card
    chrome — the eye runs straight down the numeral column. Mapped
    to ``modern-precision``.
    """
    items = "\n".join(
        (
            f'            <li key={_jsx_safe_string(svc["id"])} className="grid gap-6 border-b border-[color:var(--border)] py-8 md:grid-cols-[6rem_1fr]">\n'
            f'              <p className="font-mono text-3xl tracking-tight text-[color:var(--muted)] md:text-4xl">{_jsx_safe_string(f"{idx:02d}")}</p>\n'
            '              <div className="flex flex-col gap-3">\n'
            f'                <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'                <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            "              </div>\n"
            "            </li>"
        )
        for idx, svc in enumerate(services, start=1)
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _treatment_list_header()
        + '          <ul className="flex flex-col border-t border-[color:var(--border)]">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + _text_contact_cta(contact_path, "Boka tid")
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def render_section_credentials(dossier: dict) -> str:
    """Render a credentials / certifications row for clinic-healthcare.

    Reads ``dossier.trustSignals`` (the same array LSB uses for
    trust bullets) and renders it as a compact inline row of badge-
    cards under a "Legitimerade och certifierade"-eyebrow. This is
    what surfaces a clinic's regulated status (Sveriges Tand-
    läkarförbund, Vårdgivarregistret, etc.) on the home and
    treatments pages where a patient is deciding whether the
    practitioner is real.

    Returns "" when the dossier has no trust signals so the
    dispatcher does not emit a hollow section.
    """
    trust_raw = dossier.get("trustSignals") or []
    trust: list[str] = []
    for item in trust_raw:
        if isinstance(item, str) and item.strip():
            trust.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label")
            if isinstance(label, str) and label.strip():
                trust.append(label.strip())
    if not trust:
        return ""
    badges = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="flex items-center gap-3 rounded-full border border-[color:var(--border)] bg-[color:var(--background)] px-5 py-2 text-sm font-medium">\n'
        '              <Check className="size-4 text-[color:var(--primary)]" />\n'
        f"              <span>{_jsx_safe_string(label)}</span>\n"
        "            </li>"
        for label in trust
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.7)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Legitimerade och certifierade</p>\n'
        '          <ul className="flex flex-wrap gap-3">\n'
        f"{badges}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


_EXPERTISE_AREAS_TREATMENT_DEFAULT = "numbered-2col"


def render_section_expertise_areas(
    dossier: dict,
    *,
    contact_path: str | None = "/kontakta-oss",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render a structured expertise-area grid for professional-services home.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of two private renderers:

    * ``numbered-2col`` — the byte-identical default. 2-col grid with
      numeric eyebrows (``01``..``06``) and a left-rail border on
      each card. Calm, court-filing-style restraint. Mapped to
      ``legal-classic`` and ``accounting-trust`` (default-keep).
    * ``tag-cluster`` — pill cloud where each practice area is a
      compact rounded pill with the label inside and the scope
      revealed on the row directly below. Reads as an associative
      "what we do"-cloud rather than a numbered index. Mapped to
      ``consulting-modern``.

    Returns "" when the dossier carries no services so the
    dispatcher does not emit an empty grid. Caps at six entries
    on the home; the full list belongs on the practice-grid
    section that runs the /expertis route.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "expertise-areas",
        default=_EXPERTISE_AREAS_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "expertise-areas"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("expertise-areas") if blueprint is not None else None
        ),
    )
    if treatment == "tag-cluster":
        return _render_expertise_areas_tag_cluster(services, contact_path)
    return _render_expertise_areas_numbered_2col(services, contact_path)


def _expertise_areas_header() -> str:
    """Shared header markup for every expertise-areas treatment."""
    return (
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Verksamhetsområden</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Vår expertis</h2>\n'
        "          </div>\n"
    )


def _render_expertise_areas_numbered_2col(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """2-col grid with numbered eyebrows and left-rail borders.

    Kept byte-identical to the pre-Phase-2 output so existing
    snapshots and any PS build that did not pin a variant in Phase 1
    are not invalidated by introducing treatment dispatch.
    """
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-3 border-l border-[color:var(--border)] pl-6">\n'
        f'              <span className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"{idx:02d}")}</span>\n'
        f'              <h3 className="text-xl font-semibold tracking-tight">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </article>"
        for idx, svc in enumerate(services[:6], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _expertise_areas_header()
        + '          <div className="grid gap-10 md:grid-cols-2">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + _text_contact_cta(contact_path, "Boka introduktionssamtal")
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_expertise_areas_tag_cluster(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """Pill cloud where practice areas read as an associative tag cluster.

    Each practice area renders as a compact rounded pill carrying
    its label; the scope follows on a separate row beneath the
    cluster as a single line of running text joined by middots.
    The shape — pills + summary line — reads as "what we do" rather
    than a numbered index, which suits the modern consulting tone.
    Mapped to ``consulting-modern``.
    """
    pills = "\n".join(
        f'              <li key={_jsx_safe_string(svc["id"])} className="rounded-full border border-[color:var(--border)] bg-[color:var(--card)] px-5 py-2 text-sm font-medium tracking-tight">{_jsx_safe_string(svc["label"])}</li>'
        for svc in services[:6]
    )
    summary_line = " · ".join(
        str(svc.get("summary", "")).strip()
        for svc in services[:6]
        if isinstance(svc.get("summary"), str) and svc.get("summary", "").strip()
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _expertise_areas_header()
        + '          <ul className="flex flex-wrap gap-3">\n'
        + f"{pills}\n"
        + "          </ul>\n"
        + f'          <p className="max-w-3xl text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(summary_line)}</p>\n'
        + _text_contact_cta(contact_path, "Boka introduktionssamtal")
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


_PRACTICE_GRID_TREATMENT_DEFAULT = "dense-grid"


def render_section_practice_grid(
    dossier: dict,
    *,
    contact_path: str | None = "/kontakta-oss",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the full practice-area catalogue for professional-services /expertis.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of three private renderers:

    * ``dense-grid`` — the byte-identical default. 3-col compact
      grid of small cards with formal restraint. Mapped to
      ``consulting-modern`` so the modern consulting variant keeps
      the pre-Phase-2 expertise menu.
    * ``tabular`` — formal row listing (no card chrome) with thin
      ``border-b`` separators between rows and a column header.
      Reads as a court-filing index. Mapped to ``legal-classic``.
    * ``grouped`` — 2-col feature columns with large numbered
      eyebrows (``Område 01`` / ``Område 02``…) and richer
      typography. Mapped to ``accounting-trust``.

    Returns "" when no services are declared so the dispatcher
    does not emit an empty grid scaffold regardless of treatment.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "practice-grid",
        default=_PRACTICE_GRID_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "practice-grid"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("practice-grid") if blueprint is not None else None
        ),
    )
    if treatment == "tabular":
        return _render_practice_grid_tabular(services, contact_path)
    if treatment == "grouped":
        return _render_practice_grid_grouped(services, contact_path)
    return _render_practice_grid_dense_grid(services, contact_path)


def _practice_grid_header() -> str:
    """Shared header markup for every practice-grid treatment.

    Locks the eyebrow + h1 + supporting copy across all three
    treatments. The Phase 3 operator-pin tier (ADR 0032) only
    swaps the treatment renderer; copy overrides via dossier
    directives are out of scope and left for a future iteration.
    """
    return (
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Verksamhetsområden</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Praktikgrupper</h1>\n'
        '            <p className="text-base text-[color:var(--muted)] leading-relaxed">Vår verksamhet är organiserad i specialiserade praktikgrupper. Välj det område som ligger närmast ert ärende — vi kopplar in den partner som har relevant precedent.</p>\n'
        "          </header>\n"
    )


def _render_practice_grid_dense_grid(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """3-col compact card grid (the default treatment).

    Kept byte-identical to the pre-Phase-2 output so existing
    snapshots and any PS build that did not pin a variant in Phase 1
    are not invalidated by introducing treatment dispatch.
    """
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-4 rounded-lg border border-[color:var(--border)] bg-[color:var(--background)] p-7">\n'
        f'              <h2 className="text-lg font-semibold tracking-tight">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        + _text_contact_cta(
            contact_path,
            "Diskutera ärende",
            indent="              ",
            class_name="mt-auto inline-flex items-center gap-2 text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline",
            icon_size="size-3",
        )
        + "            </article>"
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _practice_grid_header()
        + '          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_practice_grid_tabular(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """Formal row listing with thin separators (no card chrome).

    Reads as a court-filing index: a header row labels the columns,
    each practice area is a single row with a label / scope / link
    layout and a thin ``border-b`` separator. No surface chrome —
    the eye runs straight down the column. Mapped to
    ``legal-classic`` so the classic law firm reads as a structured
    filing index rather than a marketing brochure.
    """
    rows = "\n".join(
        (
            f'              <li key={_jsx_safe_string(svc["id"])} className="grid items-baseline gap-4 border-b border-[color:var(--border)] py-6 md:grid-cols-[14rem_1fr_auto] md:gap-8">\n'
            f'                <h2 className="text-base font-semibold tracking-tight md:text-lg">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'                <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            + _text_contact_cta(
                contact_path,
                "Diskutera ärende",
                indent="                ",
                class_name="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline",
                icon_size="size-3",
            )
            + "              </li>"
        )
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _practice_grid_header()
        + '          <div className="flex flex-col">\n'
        + '            <div className="grid gap-4 border-b border-[color:var(--border)] pb-3 text-xs font-mono uppercase tracking-widest text-[color:var(--muted)] md:grid-cols-[14rem_1fr_auto] md:gap-8">\n'
        + "              <span>Praktikområde</span>\n"
        + "              <span>Omfång</span>\n"
        + '              <span className="hidden md:inline">Kontakt</span>\n'
        + "            </div>\n"
        + '            <ul className="flex flex-col">\n'
        + f"{rows}\n"
        + "            </ul>\n"
        + "          </div>\n"
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_practice_grid_grouped(
    services: list[dict],
    contact_path: str | None,
) -> str:
    """2-col feature columns with numbered eyebrows.

    Each practice area becomes a richer feature card with a large
    monospace ``Område NN`` eyebrow, slightly bigger heading
    typography and more vertical breathing room. Mapped to
    ``accounting-trust`` so the audit / advisory variant reads as a
    structured "this is how we organise our practice" rather than a
    dense menu.
    """
    cards = "\n".join(
        (
            f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-8">\n'
            f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--accent)]">{_jsx_safe_string(f"Område {idx:02d}")}</p>\n'
            f'              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            + _text_contact_cta(
                contact_path,
                "Diskutera ärende",
                indent="              ",
                class_name="mt-auto inline-flex items-center gap-2 text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline",
                icon_size="size-3",
            )
            + "            </article>"
        )
        for idx, svc in enumerate(services, start=1)
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _practice_grid_header()
        + '          <div className="grid gap-6 md:grid-cols-2">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


_SECTION_RENDERERS.update(
    {
        "treatment-summary": render_section_treatment_summary,
        "treatment-list": render_section_treatment_list,
        "credentials": render_section_credentials,
        "expertise-areas": render_section_expertise_areas,
        "practice-grid": render_section_practice_grid,
    }
)
