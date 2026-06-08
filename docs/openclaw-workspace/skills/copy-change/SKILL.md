# SKILL: copy_change

## Mål
Ändra textinnehåll via följdprompt: företagsnamn, hero-rubrik/tagline, om-oss,
tjänstetexter. T.ex. "byt hero-rubriken till X" eller "gör herotexten X istället
för Y".

## Väg
router (copy_change) -> copyDirective {target, value} -> apply till per-sajt
Project Input -> ny version. Förståelsen är modell-driven (copyDirectiveModel);
deterministiska guards validerar (leak-guard, grounding, schema, honesty).

## Gränser
Bara company-name | tagline | about-text | services. Rå instruktion blir aldrig
kundcopy. Inget värde extraheras -> ärlig no-op.

## Hero/copy-fältkontrakt (LÅST — fixat i commit fb9692d)

Tre fält styr hero-texten. Blanda dem ALDRIG ihop. Misstaget som lagades i
fb9692d var att en tagline-följdprompt landade i `company.tagline`, men den stora
hero-H1:an renderades från den regenererade blueprint-rubriken — så ändringen
syntes inte. Kontraktet nedan är nu sant och får inte omtolkas av en agent.

- `company.heroHeadline` = hero-H1-override. Sätts av en `tagline`-copyDirective
  (`_apply_copy_directives` speglar `company.tagline` in i detta fält, cappat till
  140 tecken i kod). Renderaren FÖREDRAR detta fält över den genererade
  blueprint-rubriken. Lever i det carried-forward company-blocket, så ändringen
  överlever ett ombygge. Optionellt — saknas på init och de flesta byggen. Ett
  `company-name`-direktiv rör ALDRIG fältet (namnet hör hemma i nav-header/footer,
  inte hero-H1).
- `company.tagline` = underrubrik/subheadline + meta-description + footer.
  Matar hero-subheadline (som blueprint kan skriva över), site-metadatans
  description och footer-raden. Är INTE hero-H1.
- `blueprint.contentBlocks.home.hero.headline` = genererad fallback. Härleds ur
  briefModel `positioning.oneLiner` och REGENERERAS varje bygge. Detta är INTE
  följdpromptens sanning — den skrivs över av en ny modell-körning varje build.
  Använd den aldrig som lagringsplats för en operatörsändring.

Renderarens precedens för hero-H1 (se `render_section_hero` i
`packages/generation/build/renderers.py`):

1. `company.heroHeadline` (operatörens override) om satt och icke-tom.
2. annars `blueprint.contentBlocks.home.hero.headline` (genererad fallback).
3. annars `company.name`.

Implementationsankare:

- mirror: `_apply_copy_directives` i
  `packages/generation/followup/copy_directives.py` (tagline-grenen sätter
  `company.heroHeadline`).
- render-preferens: hero-override-blocket i `render_section_hero`,
  `packages/generation/build/renderers.py`.
- schema: `company.heroHeadline` i
  `governance/schemas/project-input.schema.json` (optionell, maxLength 200;
  koden cappar snävare till 140 som tagline).

## Status
supported (LLM-förståelse som primärlager, deterministik som validator).
