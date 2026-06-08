# SKILL: restyle

## Mål
Ändra sajtens visuella ton (färg/typsnitt/tema) via en följdprompt, t.ex.
"gör sajten grönvit" eller "gör den lyxigare".

## Väg
router (visual_style) -> theme_directive (brand.primaryColorHex /
accentColorHex / tone.primary) -> apply -> targeted render -> ny version.
Fria/sammansatta färger löses via color_lexicon + stylist-rollen
(extract_style_directive_llm) med deterministisk validering.

## Gränser
Ingen fri CSS, ingen per-element-styling (global tema). Bar färg utan stil-
kontext ("vad betyder rosa?") är ingen edit. "lägg till en blå knapp" är
component_add, inte restyle.

## Status
supported (A1/stylist landade 2026-06-08).
