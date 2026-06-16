"""Restaurang/hospitality-familjens sektion- och route-renderers.

Utbruten ur ``packages.generation.build.renderers`` under megafiles-
refaktorn (Del 1, slice A — restaurang/hospitality). Modulen samlar
``menu``- och ``booking``-routernas sektionsrenderare plus de tunna
route-shimmarna ``render_menu`` / ``render_booking`` som ``write_pages``
anropar direkt.

Självregistrering: modulen kör sitt eget
``_SECTION_RENDERERS.update({...})`` vid import, precis som de övriga
registreringsblocken i ``renderers``. ``renderers`` importerar den här
modulen högst upp, vilket dels triggar registreringen, dels
re-exporterar varje flyttat namn så att ``scripts.build_site`` (som
re-exporterar från ``renderers``) och paritetstesterna behåller sina
befintliga import-stavningar.

Söm mot ``renderers``: bara tre bakåtberoenden behövs vid körning —
``_jsx_safe_string``, ``_phone_href`` och ``render_section_contact_cta``.
De nås lazy via :func:`_renderers` så att ``renderers`` kan importera
den här modulen vid sin egen import utan en cirkulär import. De två
förstnämnda är i sin tur tunna shims i ``renderers`` mot
``scripts.build_site`` (``_call_build_site``), så kedjan landar i samma
funktioner som före utbrytningen och utdata blir byte-identisk.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from packages.generation.build.blueprint_render import RenderBlueprint
from packages.generation.build.contact_placeholders import (
    real_email,
    real_opening_hours,
    real_phone,
)
from packages.generation.build.dispatcher import (
    _SECTION_RENDERERS,
    _load_scaffold_sections,
    annotate_section_marker,
    render_route_generic,
)
from packages.generation.build.render_helpers import (
    _jsx_safe_string as _jsx_safe_string,
)
from packages.generation.build.render_helpers import (
    _phone_href as _phone_href,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _renderers() -> ModuleType:
    """Return the fully-initialised ``renderers`` module lazily.

    Imported at call time rather than module top so ``renderers`` can
    import this module during its own import without a cycle: by the
    time any renderer below actually runs (build time), ``renderers``
    is complete and in ``sys.modules``, so this is a cheap cache hit.
    """
    from packages.generation.build import renderers

    return renderers


def _menu_items(dossier: dict) -> list[dict]:
    """Return menu items for a restaurant project input.

    The project-input schema's ``services[]`` is structurally identical
    to a menu item (``id`` + ``label`` + ``summary``), and the schema's
    top-level ``additionalProperties: false`` forbids adding a separate
    ``menu`` field. Restaurant operators therefore put menu items in
    the ``services`` array; ``render_menu`` reads them back here.

    The fallback returns a short sample so the page still has visible
    content for projects that pin restaurant-hospitality without
    supplying any items — that is rare in production but useful when
    the planner picks the scaffold from a thin prompt.
    """
    items = dossier.get("services") or []
    cleaned: list[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id") and item.get("label"):
                cleaned.append(item)
    if cleaned:
        return cleaned
    return [
        {
            "id": "house-special",
            "label": "Dagens rätt",
            "summary": (
                "Vår kock väljer en huvudrätt utifrån säsongens råvaror. "
                "Fråga personalen vad som serveras idag."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Path B step 7 — restaurant-hospitality section renderers.
#
# Each helper renders a single section from the restaurant scaffold's
# sections.json. They are deliberately self-contained ``<section>``
# blocks so render_route_generic can compose them in any order (for
# example: hero + menu-preview + book-table-cta on home, then
# menu-intro + menu-list + dietary-key on /menu). All customer text is
# routed through ``_jsx_safe_string`` so JSX-special characters in
# operator-supplied copy never break ``next build``.
#
# Optional sections (large-party-note, cancellation-policy) return an
# empty string when the dossier has no content for them so a scaffold
# can list them in optionalSections without forcing every site to
# render an empty card.
# ---------------------------------------------------------------------------


def render_section_menu_intro(dossier: dict) -> str:
    """Header section for the restaurant /meny route.

    Eyebrow + heading + lead paragraph using the wizard idiom so the
    section visually matches the existing about/services pages.
    Customer text from the dossier is not interpolated here yet — the
    copy is deterministic and operator-safe per the restaurant
    scaffold contract.
    """
    eyebrow = _jsx_safe_string("Meny")
    heading = _jsx_safe_string("Vad vi serverar just nu")
    intro = _jsx_safe_string(
        "Menyn växlar med säsongen och tillgången på råvaror. "
        "Be gärna personalen om dagens rekommendation eller hör av dig "
        "i förväg om du har önskemål eller allergier."
    )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_menu_list(dossier: dict) -> str:
    """Card grid of menu items for the restaurant /meny route.

    Reads ``services`` from the dossier via ``_menu_items`` (project
    input schema reuses the services array for menu items). Each card
    shows the item label and an optional summary. Empty dossiers fall
    back to a "Dagens rätt" placeholder via ``_menu_items`` so the
    page never renders an empty grid.
    """
    items = _menu_items(dossier)
    card_fragments: list[str] = []
    for item in items:
        key_attr = _jsx_safe_string("menu-" + str(item["id"]))
        label_attr = _jsx_safe_string(str(item["label"]))
        summary_value = item.get("summary")
        summary_fragment = ""
        if isinstance(summary_value, str) and summary_value.strip():
            summary_attr = _jsx_safe_string(summary_value)
            summary_fragment = (
                '              <p className="mt-2 text-sm '
                'text-[color:var(--muted)] leading-relaxed">'
                f"{summary_attr}</p>\n"
            )
        card_fragments.append(
            f"            <article key={key_attr} "
            'className="rounded-xl border border-[color:var(--border)] '
            "bg-[color:var(--card,var(--background))] p-6 transition-all "
            "duration-300 hover:-translate-y-0.5 "
            'hover:border-[color:var(--primary)] hover:shadow-md">\n'
            f'              <h2 className="text-lg font-semibold">{label_attr}</h2>\n'
            f"{summary_fragment}"
            "            </article>"
        )
    cards = "\n".join(card_fragments)
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_dietary_key(dossier: dict) -> str:
    """Optional dietary-marker key for the /meny route.

    Renders a small panel listing common Swedish dietary markers
    (vegetariskt, veganskt, glutenfritt, laktosfritt) so visitors can
    scan the menu legend at a glance. Empty when no menu item refers
    to a marker; the dispatcher includes the section because the
    restaurant scaffold's sections.json marks it as required, but the
    panel itself stays minimal so it does not dominate the page.
    """
    markers: list[tuple[str, str]] = [
        ("V", "Vegetariskt"),
        ("VG", "Veganskt"),
        ("GF", "Glutenfritt"),
        ("LF", "Laktosfritt"),
    ]
    rows = "\n".join(
        '            <li className="inline-flex items-center gap-2 rounded-full '
        "border border-[color:var(--border)] px-3 py-1 text-xs "
        'text-[color:var(--muted)]">'
        f'<span className="font-semibold text-[color:var(--foreground)]">{_jsx_safe_string(short)}</span>'
        f"<span>{_jsx_safe_string(label)}</span>"
        "</li>"
        for short, label in markers
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kostmarkeringar</p>\n'
        '          <ul className="flex flex-wrap gap-2">\n'
        f"{rows}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_booking_intro(dossier: dict) -> str:
    """Header section for the restaurant /bokning route.

    Mirrors render_section_menu_intro's structure with reservation-
    flavoured copy. Per Issue #90 we do NOT embed a third-party
    booking provider — the operator's preferred provider lands via the
    ``booking-cta`` dossier in a separate compositional pass — so this
    intro frames the contact-driven booking flow.
    """
    eyebrow = _jsx_safe_string("Boka bord")
    heading = _jsx_safe_string("Boka en plats hos oss")
    intro = _jsx_safe_string(
        "Just nu tar vi bokningar via telefon och e-post. Ring eller "
        "skriv så bekräftar vi tid och antal personer. För större "
        "sällskap, hör av dig minst två dagar i förväg."
    )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_booking_form_or_embed(dossier: dict) -> str:
    """Booking-form placeholder card for the /bokning route.

    The MVP intentionally has no embedded reservation widget so the
    section renders a copy block explaining that the operator handles
    bookings via phone or email. A future scaffold variant can swap
    this renderer for a Resoo / Tablefy / Quandoo embed without
    touching the dispatcher.
    """
    body = _jsx_safe_string(
        "Vi tar bokningar manuellt så att vi kan stämma av specialönskemål, "
        "allergier och större sällskap. Använd kontaktuppgifterna nedan "
        "eller hör av dig på sociala medier."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Bokningsförfrågan</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_hours_summary(dossier: dict) -> str:
    """Opening-hours summary card for /bokning and /hitta-hit.

    Reads ``contact.openingHours`` from the dossier and renders a
    single card. Returns an empty string when no hours are set so the
    section is invisible rather than rendering an empty placeholder.
    """
    contact = dossier.get("contact") or {}
    # Suppress the dummy "Mån-Fre 09:00-17:00" fallback so the card never
    # presents placeholder hours as if they were the real schedule.
    opening = real_opening_hours(contact)
    if opening is None:
        return ""
    safe_hours = _jsx_safe_string(opening.strip())
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-8">\n'
        '          <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Öppettider</p>\n'
        f'            <p className="mt-2 text-base">{safe_hours}</p>\n'
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_fallback_phone(dossier: dict) -> str:
    """Phone + email fallback cards for /bokning.

    Reads ``contact.phone`` and ``contact.email``. Renders cards only
    for the channels the operator actually staffs so the visitor does
    not see "Boka via e-post" links pointing nowhere. Returns empty
    when neither channel is configured.
    """
    contact = dossier.get("contact") or {}
    # Only surface channels the operator actually staffs — placeholder
    # phone/email are suppressed so /bokning never shows a dummy number
    # or address as a bookable channel.
    phone = real_phone(contact)
    email = real_email(contact)
    cards: list[str] = []
    if isinstance(phone, str) and phone.strip():
        cards.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via telefon</p>\n'
            f"              <a href={_jsx_safe_string('tel:' + _phone_href(phone))} "
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(phone)}</a>\n'
            "            </div>"
        )
    if isinstance(email, str) and email.strip():
        cards.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via e-post</p>\n'
            f"              <a href={_jsx_safe_string('mailto:' + email.strip())} "
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(email.strip())}</a>\n'
            "            </div>"
        )
    if not cards:
        return ""
    grid = "\n".join(cards)
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-8">\n'
        '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{grid}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_large_party_note(dossier: dict) -> str:
    """Optional 'larger party' guidance for /bokning.

    Static text encouraging visitors with bigger groups to call ahead.
    The MVP keeps the copy generic; a future scaffold variant can
    wire this to a per-restaurant max-party-size from the dossier.
    """
    body = _jsx_safe_string(
        "För sällskap över sex personer ber vi dig kontakta oss direkt så "
        "vi kan reservera plats och förbereda menyn. Boka helst minst "
        "två dagar i förväg."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Större sällskap</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_cancellation_policy(dossier: dict) -> str:
    """Optional cancellation-policy block for /bokning.

    Static placeholder text matching the MVP's manual-booking flow.
    A scaffold variant or operator override can replace this with the
    operator's actual policy via a future dossier field.
    """
    body = _jsx_safe_string(
        "Behöver du avboka eller ändra antalet personer? Hör av dig så "
        "snart du kan, så hjälper vi nästa gäst som står på väntelistan."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Avbokning</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def _restaurant_optional_section_stub(dossier: dict) -> str:
    """No-op renderer for optional restaurant sections without bespoke copy.

    Returned by ``render_section_wine_pairings``,
    ``render_section_lunch_rotation_note`` and
    ``render_section_menu_download_cta`` so a future operator-driven
    fix can add real copy by simply replacing the renderer with a
    section-shaped function. Until then these slots stay empty so
    the page does not render placeholder marketing copy that the
    operator did not approve.
    """
    return ""


def render_section_wine_pairings(dossier: dict) -> str:
    """Optional wine-pairing recommendations panel for /meny.

    Empty MVP stub: a future scaffold variant or operator override
    will populate this section with a curated list pulled from a
    new dossier field. Returning empty keeps the page slim until
    real content is wired.
    """
    return _restaurant_optional_section_stub(dossier)


def render_section_lunch_rotation_note(dossier: dict) -> str:
    """Optional lunch-rotation note for /meny.

    Empty MVP stub: weekday lunch rotations require a structured
    schedule the project-input schema does not yet model. The
    section is still registered so a scaffold listing it in
    optionalSections does not raise SystemExit at build time.
    """
    return _restaurant_optional_section_stub(dossier)


def render_section_menu_download_cta(dossier: dict) -> str:
    """Optional menu-PDF download CTA for /meny.

    Empty MVP stub: file uploads are routed through
    ``public/uploads`` only for hero/gallery/logo today. A future
    scaffold can wire a menu PDF upload through the same path and
    swap this stub for a real download button.
    """
    return _restaurant_optional_section_stub(dossier)


# Restaurant section renderers register here so render_route_generic
# can dispatch on the section ids declared in
# packages/generation/orchestration/scaffolds/restaurant-hospitality/sections.json.
# Optional sections without bespoke copy register a no-op stub so the
# dispatcher can include them without raising SystemExit; operators or
# scaffold variants can replace each stub with a real renderer when
# the corresponding dossier fields land.
_SECTION_RENDERERS.update(
    {
        "menu-intro": render_section_menu_intro,
        "menu-list": render_section_menu_list,
        "dietary-key": render_section_dietary_key,
        "wine-pairings": render_section_wine_pairings,
        "lunch-rotation-note": render_section_lunch_rotation_note,
        "menu-download-cta": render_section_menu_download_cta,
        "booking-intro": render_section_booking_intro,
        "booking-form-or-embed": render_section_booking_form_or_embed,
        "hours-summary": render_section_hours_summary,
        "fallback-phone": render_section_fallback_phone,
        "large-party-note": render_section_large_party_note,
        "cancellation-policy": render_section_cancellation_policy,
    }
)


_RESTAURANT_SCAFFOLD_DIR = (
    REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds" / "restaurant-hospitality"
)


def _render_restaurant_route(
    dossier: dict,
    *,
    route_id: str,
    page_function_name: str,
    contact_path: str | None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Compose a restaurant route via the section dispatcher.

    Loads ``restaurant-hospitality/sections.json`` for the section
    list, dispatches each id through ``render_route_generic``, then
    appends the standard contact-CTA section so the visitor always
    has a path back to opening hours and phone. The page shell
    (icon import + ``<main>`` wrapper + closing tags) is added
    here so the renderer remains a drop-in replacement for the
    previous specialised implementation.

    ``page_function_name`` controls the name of the exported React
    component (``MenuPage`` / ``BookingPage``) so a future scaffold
    can reuse this helper for any new route.
    """
    sections = _load_scaffold_sections(_RESTAURANT_SCAFFOLD_DIR)
    body = render_route_generic(
        dossier,
        route_id=route_id,
        scaffold_sections=sections,
        contact_path=contact_path,
        blueprint=blueprint,
    )
    # kor-2: thread the blueprint so the trailing contact CTA follows
    # conversion.primaryCta (e.g. "Boka bord") instead of the generic
    # "Kontakta oss", consistent with the rest of the default-route set.
    cta_section = annotate_section_marker(
        _renderers().render_section_contact_cta(
            dossier, contact_path=contact_path, blueprint=blueprint
        ),
        "contact-cta",
    )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        f"export default function {page_function_name}() {{\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + body
        + cta_section
        + "    </main>\n"
        + "  );\n"
        + "}\n"
    )


def render_menu(
    dossier: dict,
    *,
    contact_path: str | None = "/hitta-hit",
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the restaurant /meny route via the section dispatcher.

    Path B step 8 thin shim. The actual section composition lives
    in ``render_section_menu_intro`` / ``render_section_menu_list``
    / ``render_section_dietary_key`` and is dispatched through
    ``render_route_generic`` based on the section list declared in
    ``restaurant-hospitality/sections.json``. A future scaffold can
    extend the route by appending an optional section (for example
    ``wine-pairings``) to its sections.json without editing this
    file.

    The trailing contact CTA is added here as a deliberate page-
    level affordance — the scaffold's sections.json keeps the
    /menu route lean (intro + list + dietary key) and the CTA is
    surfaced by the page wrapper so a hungry visitor always has a
    path back to opening hours and phone.

    ``contact_path`` defaults to ``/hitta-hit`` to match the
    scaffold's ``contact`` route slug.
    """
    return _render_restaurant_route(
        dossier,
        route_id="menu",
        page_function_name="MenuPage",
        contact_path=contact_path,
        blueprint=blueprint,
    )


def render_booking(
    dossier: dict,
    *,
    contact_path: str | None = "/hitta-hit",
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the restaurant /bokning route via the section dispatcher.

    Path B step 8 thin shim. The actual section composition lives
    in ``render_section_booking_intro`` /
    ``render_section_booking_form_or_embed`` /
    ``render_section_hours_summary`` /
    ``render_section_fallback_phone`` and is dispatched through
    ``render_route_generic`` based on the section list declared in
    ``restaurant-hospitality/sections.json``.

    Per Issue #90 we still do NOT embed a third-party booking
    provider — the dispatcher composes a static reservation page
    where the operator handles bookings via phone and email. A
    scaffold variant can swap
    ``render_section_booking_form_or_embed`` for an embedded
    widget without touching the dispatcher.
    """
    return _render_restaurant_route(
        dossier,
        route_id="booking",
        page_function_name="BookingPage",
        contact_path=contact_path,
        blueprint=blueprint,
    )
