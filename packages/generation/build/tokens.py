"""Färg- och token-systemet för den deterministiska byggaren.

Extraherat ordagrant ur ``scripts/build_site.py`` enligt
``docs/refactor/megafiles-plan.md`` (Del 2, slice 1), beteendebevarande.
Modulen är medvetet stdlib-only och har INGEN koppling tillbaka till
``scripts/`` — färg-/typografi-helpers och ``variant_css`` bygger bara
rena strängar/dictar ur en variant + project-input.

``patch_globals_css``/``patch_package_json`` ligger kvar i
``scripts/build_site.py`` tills io-helpers (``write``/``load_json``)
flyttas i en senare slice; de anropar namnen härifrån via byggarens
re-export.
"""

from __future__ import annotations

import re
from typing import Any

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_TONE_COLOR_TOKENS: dict[str, dict[str, str]] = {
    "grön": {"primary": "#166534", "accent": "#dcfce7"},
    "green": {"primary": "#166534", "accent": "#dcfce7"},
    "blå": {"primary": "#1d4ed8", "accent": "#dbeafe"},
    "blue": {"primary": "#1d4ed8", "accent": "#dbeafe"},
    "varm": {"primary": "#9a3412", "accent": "#fed7aa"},
    "warm": {"primary": "#9a3412", "accent": "#fed7aa"},
    "premium": {"primary": "#312e81", "accent": "#ddd6fe"},
}


def _normalise_hex_color(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not _HEX_COLOR_RE.fullmatch(cleaned):
        return None
    return cleaned.lower()


def _foreground_for_background(hex_color: str) -> str:
    """Return a high-contrast foreground token for a validated #RRGGBB color."""
    red = int(hex_color[1:3], 16) / 255
    green = int(hex_color[3:5], 16) / 255
    blue = int(hex_color[5:7], 16) / 255

    def linearise(channel: float) -> float:
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linearise(red)
        + 0.7152 * linearise(green)
        + 0.0722 * linearise(blue)
    )
    dark_contrast = (luminance + 0.05) / 0.05
    light_contrast = 1.05 / (luminance + 0.05)
    return "#1c1c1a" if dark_contrast >= light_contrast else "#fafaf9"


def _hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """Konvertera ``#RRGGBB`` till HSL.

    Returnerar ``(h, s, l)`` där ``h ∈ [0, 360]`` och ``s, l ∈ [0, 100]``.
    Anropare ska redan ha validerat ``hex_color`` mot ``_HEX_COLOR_RE``.

    Implementationen följer standard HSL-formeln (samma som CSS
    ``hsl()``-funktionen och Tailwinds palette-generator). Vi använder
    den för att bygga skalor (``_build_color_scale``) där vi bevarar
    hue + saturation och justerar lightness.
    """
    red = int(hex_color[1:3], 16) / 255
    green = int(hex_color[3:5], 16) / 255
    blue = int(hex_color[5:7], 16) / 255

    cmax = max(red, green, blue)
    cmin = min(red, green, blue)
    delta = cmax - cmin
    lightness = (cmax + cmin) / 2

    if delta == 0:
        hue = 0.0
        saturation = 0.0
    else:
        if lightness in (0.0, 1.0):
            saturation = 0.0
        else:
            saturation = delta / (1 - abs(2 * lightness - 1))
        if cmax == red:
            hue = ((green - blue) / delta) % 6
        elif cmax == green:
            hue = (blue - red) / delta + 2
        else:
            hue = (red - green) / delta + 4
        hue *= 60

    return (hue, saturation * 100, lightness * 100)


def _hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    """Konvertera ``(h, s, l)`` till ``#rrggbb``-sträng.

    ``hue ∈ [0, 360]``, ``saturation, lightness ∈ [0, 100]``. Inverterar
    ``_hex_to_hsl`` med tolerans för flyttalsavrundning (alla tre
    värden klampas innan multiplikation till 0-255).
    """
    s = max(0.0, min(100.0, saturation)) / 100
    lum = max(0.0, min(100.0, lightness)) / 100
    h = hue % 360

    c = (1 - abs(2 * lum - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = lum - c / 2

    if h < 60:
        r, g, b = c, x, 0.0
    elif h < 120:
        r, g, b = x, c, 0.0
    elif h < 180:
        r, g, b = 0.0, c, x
    elif h < 240:
        r, g, b = 0.0, x, c
    elif h < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x

    red = max(0, min(255, round((r + m) * 255)))
    green = max(0, min(255, round((g + m) * 255)))
    blue = max(0, min(255, round((b + m) * 255)))
    return f"#{red:02x}{green:02x}{blue:02x}"


# Tailwind-liknande lightness-skala. Värdena valda så att 500-bandet
# ligger nära Tailwind v3:s default-palette (där t.ex. blue-500 har
# L≈53%, slate-500 har L≈48%). 50/100 är extremt ljusa (subtila
# bakgrundstinter), 800/900 är mörka nog för text på ljus bakgrund.
# Saturation-cap används så att hög-mättade input (#ff0000) inte
# producerar neon-aktig 500-band i CTAs — vi vill ha "brand-aware"
# palettes, inte "screaming"-palettes.
_BRAND_SCALE_LIGHTNESS: tuple[tuple[str, float], ...] = (
    ("50", 97.0),
    ("100", 94.0),
    ("200", 86.0),
    ("300", 76.0),
    ("400", 66.0),
    ("500", 56.0),
    ("600", 48.0),
    ("700", 38.0),
    ("800", 28.0),
    ("900", 18.0),
)
_BRAND_SCALE_MAX_SATURATION = 85.0


def _build_color_scale(hex_color: str) -> dict[str, str]:
    """Bygg en 10-stegs Tailwind-liknande palett från en bas-färg.

    Bevarar ``hue`` och ``saturation`` (cap:ad vid 85% för att undvika
    neon-känsla på fullt mättade input som ``#ff0000``), ersätter
    lightness med ``_BRAND_SCALE_LIGHTNESS``. Returnerar en dict
    ``{ "50": "#...", "100": "#...", ..., "900": "#..." }`` som
    ``variant_css`` emitterar som ``--primary-50`` .. ``--primary-900``
    CSS-tokens. Generated render-funktioner kan sedan referera dem
    för subtila bakgrunder (50/100), borders (200/300), accenter
    (500/600) och text på ljus bg (800/900) — utan att hårdkoda hex
    i varje sektion.

    Anropare måste ha validerat ``hex_color`` mot ``_HEX_COLOR_RE``.
    """
    hue, saturation, _lightness = _hex_to_hsl(hex_color)
    capped_saturation = min(saturation, _BRAND_SCALE_MAX_SATURATION)
    return {
        step: _hsl_to_hex(hue, capped_saturation, lightness)
        for step, lightness in _BRAND_SCALE_LIGHTNESS
    }


def _token_overrides_from_project_input(
    project_input: dict[str, Any] | None,
) -> tuple[dict[str, str], list[str]]:
    """Return safe CSS token overrides derived from explicit brand/tone fields."""
    if not isinstance(project_input, dict):
        return {}, []

    overrides: dict[str, str] = {}
    warnings: list[str] = []
    brand = project_input.get("brand") if isinstance(project_input.get("brand"), dict) else {}
    primary_hex_provided = bool(brand.get("primaryColorHex"))
    accent_hex_provided = bool(brand.get("accentColorHex"))
    primary_hex = _normalise_hex_color(brand.get("primaryColorHex"))
    accent_hex = _normalise_hex_color(brand.get("accentColorHex"))
    if primary_hex_provided and primary_hex is None:
        warnings.append("brand.primaryColorHex invalid; variant primary token kept")
    if accent_hex_provided and accent_hex is None:
        warnings.append("brand.accentColorHex invalid; variant accent token kept")

    if primary_hex:
        overrides["primary"] = primary_hex
        overrides["primaryForeground"] = _foreground_for_background(primary_hex)
    if accent_hex:
        overrides["accent"] = accent_hex
        overrides["accentForeground"] = _foreground_for_background(accent_hex)

    if "primary" not in overrides and not primary_hex_provided:
        tone = project_input.get("tone") if isinstance(project_input.get("tone"), dict) else {}
        tone_tokens: dict[str, str] | None = None
        tone_primary = tone.get("primary")
        if isinstance(tone_primary, str):
            tone_tokens = _TONE_COLOR_TOKENS.get(tone_primary.strip().lower())
        # B139 fallback: när tone.primary saknar color-signal (t.ex.
        # generiska wizard-tags som "professionell" / "lugn och
        # förtroendeingivande") får tone.secondary fungera som
        # color-token-källa. Annars läcker en färgsignal som operatören
        # angett i sekundär-position tyst på vägen till variant_css.
        # Primary vinner alltid när den har en signal — secondary
        # fungerar bara som fallback, aldrig som override.
        if tone_tokens is None:
            secondary = tone.get("secondary")
            if isinstance(secondary, list):
                for entry in secondary:
                    if not isinstance(entry, str):
                        continue
                    candidate = _TONE_COLOR_TOKENS.get(entry.strip().lower())
                    if candidate is not None:
                        tone_tokens = candidate
                        break
        if tone_tokens is not None:
            overrides["primary"] = tone_tokens["primary"]
            overrides["primaryForeground"] = _foreground_for_background(
                tone_tokens["primary"]
            )
            if "accent" not in overrides and not accent_hex_provided:
                overrides["accent"] = tone_tokens["accent"]
                overrides["accentForeground"] = _foreground_for_background(
                    tone_tokens["accent"]
                )

    return overrides, warnings


"""Typography palette per variant.

Maps ``variant.id`` to a (display-font, body-font, google-fonts-query)
tuple. Each variant gets a distinct visual character beyond color alone:
warm serif for craft, tight editorial for noir, geometric sans for fit,
classic Georgia-style for trust, etc.

Fallback: when variant.id is not in the table, both fonts fall back to
``Inter`` which matches the starter's pre-typography baseline (Geist
replacement) without breaking the cascade.

`google_query` is the path part after ``css2?`` in the Google Fonts URL
(`family=Fraunces:wght@400;600;700&display=swap`). We assemble the full
URL at emit time so the value remains URL-safe and reviewable in
governance diffs.
"""
_VARIANT_TYPOGRAPHY: dict[str, dict[str, str]] = {
    # local-service-business variants
    "nordic-trust": {
        "display": "'Inter', system-ui, -apple-system, sans-serif",
        "body": "'Inter', system-ui, -apple-system, sans-serif",
        "google_query": "family=Inter:wght@400;500;600;700&display=swap",
        "display_tracking": "-0.02em",
    },
    "warm-craft": {
        "display": "'Fraunces', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.015em",
    },
    "clinical-calm": {
        "display": "'Source Sans 3', system-ui, sans-serif",
        "body": "'Source Sans 3', system-ui, sans-serif",
        "google_query": (
            "family=Source+Sans+3:wght@400;500;600;700&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "midnight-counsel": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "pulse-fit": {
        "display": "'Manrope', system-ui, sans-serif",
        "body": "'Manrope', system-ui, sans-serif",
        "google_query": "family=Manrope:wght@400;500;700;800&display=swap",
        "display_tracking": "-0.03em",
    },
    # ecommerce-lite variants
    "clean-store": {
        "display": "'Inter', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": "family=Inter:wght@400;500;600;700&display=swap",
        "display_tracking": "-0.02em",
    },
    "earth-wellness": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "mono-tech": {
        "display": "'JetBrains Mono', ui-monospace, monospace",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=JetBrains+Mono:wght@500;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.04em",
    },
    "noir-editorial": {
        "display": "'Bodoni Moda', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Bodoni+Moda:opsz,wght@6..96,500;6..96,700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "street-vivid": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
}

_TYPOGRAPHY_FALLBACK: dict[str, str] = {
    "display": "'Inter', system-ui, sans-serif",
    "body": "'Inter', system-ui, sans-serif",
    "google_query": "family=Inter:wght@400;500;600;700&display=swap",
    "display_tracking": "-0.02em",
}


# Fas 4 — tone-driven typography overlay.
#
# Mappar ``tone.primary`` (en fri sträng från Site Brief / project-input)
# till en typografi-palett som överrider variantens default. Detta är
# additivt och OPT-IN: när ``tone.primary`` saknas eller inte matchar
# någon nyckel här används variantens egen typografi exakt som idag.
#
# Designprincip — vi mappar bara på TONE-NYCKLAR som är tydligt
# kopplade till en visuell karaktär. Generiska ord som "professional"
# eller "trustworthy" lämnar vi orörda — de skulle göra mappningen
# luddig (snart sagt varje sajt kallar sig professional) och variant-
# defaultsen är redan tunade för "trustworthy" som baseline.
#
# Nyckeln matchas case-insensitive efter ``.strip().lower()``. Svenska
# och engelska former listas separat så vi inte hash-collision:ar med
# fel mapping.
# Wizard-strängar (``TONE_OPTIONS`` i
# ``apps/viewser/components/discovery-wizard/wizard-constants.ts``) är
# på svenska och kan vara multi-word ("Lugn och förtroendeingivande").
# ``_TONE_TYPOGRAPHY`` använder semantiska engelska single-word-keys
# ("calm", "playful"). Utan översättning matchar wizard-tags aldrig
# → Sprint A.2:s typografi-overlay triggas inte för svenska operatörer.
#
# Den här tabellen är översättningslagret. Keys är ``.strip().lower()``-
# normaliserade wizard-strängar; values är semantiska keys i
# ``_TONE_TYPOGRAPHY``. Att hålla dessa separata (istället för att
# duplicera font-paletten 7 gånger) gör att framtida paletter-tweaks
# bara behöver göras på ett ställe.
#
# Synkronisera den här tabellen med ``TONE_OPTIONS`` i wizard-
# constants när nya ton-alternativ läggs till. ``tests/test_builder_smoke``
# har en täckningskoll som garanterar att varje wizard-tag mappar till
# en känd ``_TONE_TYPOGRAPHY``-key.
_TONE_KEY_ALIASES: dict[str, str] = {
    # Wizard ``TONE_OPTIONS`` (svenska multi-word) → semantiska keys.
    "professionell": "modern",
    "varm och personlig": "warm",
    "lekfull": "playful",
    "exklusiv / lyxig": "luxury",
    "rak och enkel": "modern",
    "modern och teknisk": "tech",
    "lugn och förtroendeingivande": "calm",
    # Vanliga briefModel-output på engelska som tydligt mappar mot en
    # specifik palett. ``professional`` och ``trustworthy`` lämnas
    # MEDVETET bort — de är generiska och får bättre resultat med
    # variant-defaulten (befintlig kontrakt-test i test_builder_smoke).
    "calm and trustworthy": "calm",
    "warm and personal": "warm",
    "playful and energetic": "playful",
    "exclusive": "luxury",
    "luxurious": "luxury",
    "clean and simple": "modern",
    "modern and technical": "tech",
}


_TONE_TYPOGRAPHY: dict[str, dict[str, str]] = {
    # CALM / WELLNESS — elegant serif för rubriker, neutral sans för
    # body. Passar hudvård, spa, terapi, yoga, mindfulness.
    "calm": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "lugn": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "wellness": {
        "display": "'Cormorant Garamond', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Cormorant+Garamond:wght@400;500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    # BOLD / TECH — geometrisk sans med tight tracking. Passar SaaS,
    # konsult, byggteknik, modern e-handel.
    "bold": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
    "modern": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
    "tech": {
        "display": "'Space Grotesk', system-ui, sans-serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Space+Grotesk:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.035em",
    },
    # PLAYFUL / WARM — rundad sans + mjukare body. Passar barn-
    # verksamhet, café, kreativa småföretag.
    "playful": {
        "display": "'Quicksand', system-ui, sans-serif",
        "body": "'Nunito', system-ui, sans-serif",
        "google_query": (
            "family=Quicksand:wght@500;600;700"
            "&family=Nunito:wght@400;500;600&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "warm": {
        "display": "'Quicksand', system-ui, sans-serif",
        "body": "'Nunito', system-ui, sans-serif",
        "google_query": (
            "family=Quicksand:wght@500;600;700"
            "&family=Nunito:wght@400;500;600&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    "friendly": {
        "display": "'Quicksand', system-ui, sans-serif",
        "body": "'Nunito', system-ui, sans-serif",
        "google_query": (
            "family=Quicksand:wght@500;600;700"
            "&family=Nunito:wght@400;500;600&display=swap"
        ),
        "display_tracking": "-0.01em",
    },
    # PREMIUM / EDITORIAL — high-contrast display serif. Passar lyx,
    # arkitektur, gallerier, fine dining.
    "premium": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "editorial": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
    "luxury": {
        "display": "'Playfair Display', Georgia, serif",
        "body": "'Inter', system-ui, sans-serif",
        "google_query": (
            "family=Playfair+Display:wght@500;600;700"
            "&family=Inter:wght@400;500&display=swap"
        ),
        "display_tracking": "-0.025em",
    },
}


def _typography_for_variant(variant: dict) -> dict[str, str]:
    """Return the typography palette for a variant, with a safe fallback.

    Unknown variant IDs degrade gracefully to Inter so an experimental
    variant added without a typography entry still renders, just without
    the bespoke font pairing.
    """
    return _VARIANT_TYPOGRAPHY.get(variant.get("id", ""), _TYPOGRAPHY_FALLBACK)


def _normalize_tone_key(raw: str) -> str:
    """Normalisera en tone-sträng till en semantisk ``_TONE_TYPOGRAPHY``-key.

    Pipelinen är:
      1. ``.strip().lower()`` så case/whitespace inte spelar roll
      2. Slå upp i ``_TONE_KEY_ALIASES`` (wizard-strängar → semantiska
         keys, t.ex. ``"lekfull"`` → ``"playful"``)
      3. Returnera resultatet — om ingen alias matchar returneras den
         normaliserade strängen oförändrad (så engelska keys som redan
         är semantiska, t.ex. ``"calm"``, fortsatt fungerar direkt)

    Den här funktionen är single source of truth för "är denna tone-
    sträng matchbar?" — använd den i alla nya konsumenter (Sprint B/3
    hero-routing m.fl.) istället för att duplicera alias-tabellen.
    """
    key = raw.strip().lower()
    return _TONE_KEY_ALIASES.get(key, key)


def _typography_overlay_for_tone(
    project_input: dict[str, Any] | None,
) -> dict[str, str] | None:
    """Returnera en typografi-palett baserad på ``tone.primary`` om den
    matchar en känd nyckel i ``_TONE_TYPOGRAPHY``, annars ``None``.

    När ``None`` returneras använder ``variant_css`` variant-defaulten
    från ``_VARIANT_TYPOGRAPHY`` — så vi lägger ALDRIG på en font-
    override när vi inte har en stark anledning. Detta gör Sprint A.2
    opt-in: existerande projekt utan tone.primary får exakt samma
    output som idag.

    Wizard-strängar (svenska multi-word, t.ex. "Lugn och
    förtroendeingivande") normaliseras via ``_TONE_KEY_ALIASES`` så
    Sprint A.2:s overlay triggas även när operatören väljer ton via
    chips istället för att skriva engelska keys manuellt.
    """
    if not isinstance(project_input, dict):
        return None
    tone = project_input.get("tone")
    if not isinstance(tone, dict):
        return None
    primary = tone.get("primary")
    if not isinstance(primary, str):
        return None
    key = _normalize_tone_key(primary)
    return _TONE_TYPOGRAPHY.get(key)


def _motion_css_block(level: str) -> str:
    """Return a CSS block that applies subtle entry animations on the
    first paint of every ``<section>``. The block is empty for
    ``level == "none"``.

    All animations are gated behind ``prefers-reduced-motion: no-preference``
    so operators on reduced-motion settings see a static page. The
    stagger uses ``nth-of-type`` so the sequence reads top-to-bottom
    without any JavaScript or scroll-observer.

    Levels:

    - ``none``     : no animations emitted
    - ``subtle``   : 600ms fade-in only, 80ms stagger across the first
                     six sections. Reads as "polished but quiet" — fits
                     trust, clinical, calm vibes.
    - ``expressive``: 700ms fade-up + 12px translate, 120ms stagger.
                     Suits warm-craft, pulse-fit, noir, street vibes
                     where a hint of motion reinforces the brand.
    """
    if level == "none":
        return ""

    if level == "expressive":
        duration_ms = 700
        translate_y = "12px"
        stagger_ms = 120
    else:
        # default to subtle for unknown values (e.g. "normal" from older
        # variants) so we never crash on unexpected enum values.
        duration_ms = 600
        translate_y = "0"
        stagger_ms = 80

    stagger_rules = "\n".join(
        f"  main > section:nth-of-type({i}) {{ animation-delay: {stagger_ms * (i - 1)}ms; }}"
        for i in range(1, 7)
    )

    # Fas 2.2 — utöka motion-blocket med scroll-driven animations. När
    # browser:n stödjer ``animation-timeline: view()`` (Chrome/Edge 115+,
    # Opera 101+) får varje sektion utöver de första sex en mjuk fade-in
    # vid scroll, utan JavaScript. Safari + Firefox ignorerar @supports-
    # block och visar sektionerna direkt — degraderar snyggt.
    #
    # ``view()``-axeln binder animationen till element-positionen i
    # viewporten: 0% = ovan viewport, 100% = nedanför. Vi spelar bara
    # animationen i första 30%-fönstret (entering bottom) så sektionen
    # är fullt synlig innan animationen är klar.
    scroll_translate = translate_y if translate_y != "0" else "8px"
    scroll_block = (
        "  @supports (animation-timeline: view()) {\n"
        "    @keyframes sajtbyggaren-section-scroll-enter {\n"
        f"      from {{ opacity: 0; transform: translateY({scroll_translate}); }}\n"
        "      to { opacity: 1; transform: translateY(0); }\n"
        "    }\n"
        "    main > section:nth-of-type(n+7) {\n"
        "      animation: sajtbyggaren-section-scroll-enter linear both;\n"
        "      animation-timeline: view();\n"
        "      animation-range: entry 0% entry 30%;\n"
        "    }\n"
        "  }\n"
    )

    return (
        "@media (prefers-reduced-motion: no-preference) {\n"
        "  @keyframes sajtbyggaren-section-enter {\n"
        f"    from {{ opacity: 0; transform: translateY({translate_y}); }}\n"
        "    to { opacity: 1; transform: translateY(0); }\n"
        "  }\n"
        "  main > section {\n"
        f"    animation: sajtbyggaren-section-enter {duration_ms}ms cubic-bezier(0.16, 1, 0.3, 1) both;\n"
        "  }\n"
        f"{stagger_rules}\n"
        f"{scroll_block}"
        "}\n"
    )


def variant_css(
    variant: dict,
    token_overrides: dict[str, str] | None = None,
    *,
    typography_overlay: dict[str, str] | None = None,
) -> str:
    tokens = variant["tokens"]
    color = dict(tokens["color"])
    if token_overrides:
        for token_name in (
            "primary",
            "primaryForeground",
            "accent",
            "accentForeground",
        ):
            override = token_overrides.get(token_name)
            if override:
                color[token_name] = override
    radius = tokens["radius"]
    spacing = tokens["spacing"]
    # Fas 4 — tone-driven typography overlay. När anroparen har
    # extraherat en känd ``tone.primary`` via ``_typography_overlay_
    # for_tone`` ersätter vi variantens default-typografi med den.
    # Annars (vanligaste fallet, inkl. alla befintliga tester) faller
    # vi tillbaka till ``_typography_for_variant`` och CSS-outputen
    # blir byte-identisk med innan denna kwarg infördes.
    typography = typography_overlay if typography_overlay else _typography_for_variant(variant)
    # Google Fonts import — placed in @import at the top of the variant
    # block. `&display=swap` ensures the page renders with fallback fonts
    # while the webfont loads, avoiding FOIT. We use Google's HTTPS CDN
    # which is reliable enough for the MVP; a future iteration may swap
    # to `next/font/google` for self-hosting + zero FOUC.
    font_import = (
        f"@import url('https://fonts.googleapis.com/css2?{typography['google_query']}');\n"
    )
    motion_level = (
        tokens.get("motion", {}).get("level", "subtle")
        if isinstance(tokens.get("motion"), dict)
        else "subtle"
    )
    motion_block = _motion_css_block(motion_level)
    # Fas 4 — brand color scales (Tailwind-liknande 10-stegs palettes
    # genererade från primary/accent). Vi emitterar dem som CSS-tokens
    # så render_*-funktionerna kan referera ``var(--primary-50)`` för
    # subtila sektion-bakgrunder, ``var(--primary-100)`` för card-
    # hovers, ``var(--primary-600)`` för CTAs och ``var(--primary-900)``
    # för text — istället för att hårdkoda en enda mid-tone "primary"
    # överallt och få "alla sajter ser ut likadana"-effekten oavsett
    # brand. Skalan tar hue + (cap:ad) saturation från base-färgen och
    # varierar bara lightness deterministiskt. Generated css-output är
    # additiv: existerande ``--primary`` / ``--accent`` ligger kvar
    # exakt som idag så render-funktioner som inte uppgraderats än
    # fortsätter rendera identiskt.
    primary_scale = _build_color_scale(color["primary"]) if _HEX_COLOR_RE.fullmatch(color["primary"]) else None
    accent_scale = _build_color_scale(color["accent"]) if _HEX_COLOR_RE.fullmatch(color["accent"]) else None
    scale_block = ""
    if primary_scale:
        scale_block += "".join(
            f"  --primary-{step}: {value};\n" for step, value in primary_scale.items()
        )
    if accent_scale:
        scale_block += "".join(
            f"  --accent-{step}: {value};\n" for step, value in accent_scale.items()
        )

    return (
        font_import
        + ":root {\n"
        f"  --background: {color['background']};\n"
        f"  --foreground: {color['foreground']};\n"
        f"  --muted: {color['muted']};\n"
        f"  --border: {color['border']};\n"
        f"  --primary: {color['primary']};\n"
        f"  --primary-foreground: {color['primaryForeground']};\n"
        f"  --accent: {color['accent']};\n"
        f"  --accent-foreground: {color['accentForeground']};\n"
        + scale_block
        + f"  --radius-sm: {radius['sm']};\n"
        f"  --radius-md: {radius['md']};\n"
        f"  --radius-lg: {radius['lg']};\n"
        f"  --section-spacing: {spacing['section']};\n"
        f"  --container-width: {spacing['container']};\n"
        f"  --font-display: {typography['display']};\n"
        f"  --font-body: {typography['body']};\n"
        f"  --display-tracking: {typography['display_tracking']};\n"
        "}\n"
        # Apply font families at the element level so existing render_*
        # functions don't need a className change — body inherits the
        # body font; headings inherit the display font with bespoke
        # letter-spacing per variant.
        #
        # Fas 3.1 — typografiska OpenType-features per kontext:
        #   * body  : ``ss01`` (stylistic set 1 — Inter:s grotesque-alts),
        #             ``cv02`` ``cv03`` ``cv11`` (open digit + bättre kolon),
        #             ``cv05`` ``cv10`` (alternativa l/L),
        #             ``ss03`` (curl-alternativ), ``calt`` (contextual
        #             alternates för auto-ligature i webfonts).
        #   * h1-h4 : ``ss02`` (display-orienterad stylistic-set när
        #             tillgänglig), ``cv11``. Headlines håller
        #             tab-alignment med rubrik-siffror så "2026" och
        #             "1 999 kr" radas snyggt.
        #   * pris/data: ``.font-tabular`` utility-class (tabular-nums +
        #             lining-nums) som render_*-helpers kan applicera
        #             på pristext, statistik, datum.
        #
        # Browsers som inte stödjer en feature ignorerar den tyst.
        # Google Fonts levererar alla features ovan för Inter, DM Sans,
        # Manrope och Plus Jakarta Sans (våra defaults).
        "body {\n"
        "  font-family: var(--font-body);\n"
        "  font-feature-settings: \"ss01\", \"ss03\", \"cv02\", \"cv03\", \"cv05\", \"cv10\", \"cv11\", \"calt\";\n"
        "  font-variant-ligatures: common-ligatures contextual;\n"
        "}\n"
        "h1, h2, h3, h4 {\n"
        "  font-family: var(--font-display);\n"
        "  letter-spacing: var(--display-tracking);\n"
        "  font-feature-settings: \"ss02\", \"cv11\";\n"
        "  font-variant-numeric: lining-nums;\n"
        "}\n"
        ".font-tabular {\n"
        "  font-variant-numeric: tabular-nums lining-nums;\n"
        "  font-feature-settings: \"tnum\", \"lnum\";\n"
        "}\n"
        # Fas 3.3 — CSS-only parallax. Bilden zoomas 1.0 → 1.08 över
        # hero-exit-fönstret när browser:n stödjer animation-timeline.
        # ``contain``-fönstret startar när bilden börjar lämna viewporten
        # (cover 50%) och slutar när den lämnar helt (cover 100%).
        # Detta gör att zoomen sker när användaren scrollar förbi hero
        # — exakt som Apple och Stripe-sajter, men utan JavaScript.
        # Safari + Firefox ignorerar @supports och visar statisk bild.
        "@supports (animation-timeline: view()) {\n"
        "  @media (prefers-reduced-motion: no-preference) {\n"
        "    @keyframes sajtbyggaren-hero-parallax {\n"
        "      from { transform: scale(1.0); }\n"
        "      to { transform: scale(1.08); }\n"
        "    }\n"
        "    .parallax-hero {\n"
        "      animation: sajtbyggaren-hero-parallax linear both;\n"
        "      animation-timeline: view();\n"
        "      animation-range: cover 0% cover 100%;\n"
        "      will-change: transform;\n"
        "    }\n"
        "  }\n"
        "}\n"
        # Sprint 1.4 — print-styles. Småföretagssajter skrivs ofta ut
        # (offert-sidor, om-oss, kontakt). Default Tailwind print:n är
        # plain-white men släpper igenom flera hög-impact-element som
        # förstör utskriften:
        #
        #   * sticky header + footer dyker upp på varje sida-sida
        #   * background-gradienter slukar svart-bläck
        #   * scroll-animations triggas inte i print men reserverar
        #     ändå space (de börjar med opacity:0)
        #   * hover-shadows ger spöktryck längs kortets kanter
        #
        # Vi nollar dessa explicit. Ingen branch-specifik logik —
        # samma regler funkar för alla sajter eftersom de matchar
        # generiska klasser (sticky, scroll-anim, bg-gradient).
        "@media print {\n"
        "  *, *::before, *::after {\n"
        "    background: transparent !important;\n"
        "    color: black !important;\n"
        "    box-shadow: none !important;\n"
        "    text-shadow: none !important;\n"
        "  }\n"
        "  header, footer, nav { display: none !important; }\n"
        "  a, a:visited { text-decoration: underline; color: black !important; }\n"
        "  a[href]::after { content: \" (\" attr(href) \")\"; font-size: 80%; }\n"
        "  a[href^=\"#\"]::after, a[href^=\"javascript:\"]::after { content: \"\"; }\n"
        "  img { max-width: 100% !important; page-break-inside: avoid; }\n"
        "  .scroll-anim, .scroll-anim-stagger > * {\n"
        "    opacity: 1 !important;\n"
        "    transform: none !important;\n"
        "    animation: none !important;\n"
        "  }\n"
        "  .parallax-hero { animation: none !important; transform: none !important; }\n"
        "  h2, h3 { page-break-after: avoid; }\n"
        "  p, blockquote { orphans: 3; widows: 3; }\n"
        "  blockquote, pre { page-break-inside: avoid; }\n"
        "}\n"
        + motion_block
    )
