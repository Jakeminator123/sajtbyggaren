---
description: Heavy LLM-flödet är ett lager ovanpå den deterministiska rälsen, inte en ersättare. Förbjud canonicalisering, inte ord.
globs: docs/heavy-llm-flow/**,packages/generation/**
alwaysApply: false
---

# Heavy LLM-flöde: räls vs intelligens

När du arbetar i det tunga LLM-flödet eller i generatorn gäller två-motor-modellen
från [`docs/heavy-llm-flow/00-malbild-och-lager.md`](../../docs/heavy-llm-flow/00-malbild-och-lager.md).
Läs även [README](../../docs/heavy-llm-flow/README.md) och builderprofilen
[`04-builder-profil.md`](../../docs/heavy-llm-flow/04-builder-profil.md).

## Två motorer

- **Rälsen (finns, deterministisk):** `Scaffold` / `Variant` / `Dossier` / starters /
  routes / renderers / `Quality Gate` / repair / versioner / `Preview Runtime`. Den
  svarar på "vad får systemet bygga, hur valideras det, hur körs det?".
- **Intelligensen (byggs):** förståelse, positionering, copy, struktur-intent,
  designriktning, intent-routing, self-critique. Den svarar på "vilken sida borde just
  den här användaren få?".

LLM:en **fyller** rälsen med bättre beslut — den ersätter den inte.

## Manual/wizard-vägen är förstaklass

Klick-/wizard-flödet är en **förstaklassväg**, inte en fallback. En användare ska
fortsatt kunna skapa en helt eller semi-deterministisk startsajt genom wizard/UI-val
(välja eller härleda `Scaffold`, `Variant`, starter, `Dossier`). Alla ingångar — fri
prompt, wizard, starter-/scaffold-/variant-/dossier-val, follow-up, asset-upload,
scrape — matar in i **samma** kedja: `Project Input` → `Site Brief` → `Site Plan` →
`Generation Package` → renderer/`build_site`. LLM-flödet får berika, reparera och
personalisera samma kedja — aldrig kringgå eller dubblera den.

## LLM:en får / får inte

- **Får:** välja avsikt, vinkel, copy, prioritet, förslag; skriva in i **befintliga**
  artefakter (`Site Brief` / `Site Plan` / `Generation Package` / `Project Input`).
- **Får inte:** skriva fria Next.js-filer, hitta på claims/recensioner/placeholder-
  kontakt, mounta en dossier som inte finns, byta starter utan resolver, skapa en ny
  scaffold på egen hand.

## Förbjud canonicalisering, inte ord

Arbetsnamn (blueprint, OpenClaw Router, LLM Orchestrator) är tillåtna i docs/körplan.
Det som kräver operatörsbeslut + ADR är att göra dem till **sparade canonical
artefakter, nya typer eller runtime-kontrakt** — t.ex. en ny `site-blueprint.json`
eller en parallell generation engine bredvid pipelinen. Utöka hellre befintliga
artefakter additivt. Nya canonical fältnamn registreras i `naming-dictionary.v1.json`.

## OpenClaw

OpenClaw är routern **ovanpå** init/follow-up som väljer answer / plan / site change.
Den står ovanför pipelinen och väljer hur den ska användas — den kapar den inte.
Rör inte `PreviewRuntime`-adaptrar eller `current.json`-kontraktet i blueprint-/
codegen-skivorna (ADR 0030/0033).
