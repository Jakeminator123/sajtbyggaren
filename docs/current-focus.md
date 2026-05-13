# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.

Uppdatera filen i samma commit som ändrar köläget. Filen ska alltid vara
färsk - om den inte stämmer ska du fixa den, inte hoppa över den.

## Last verified

Last verified state: `3f7487e` (2026-05-13, post-PR #16 + lightweight loop)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

Post-PR #16. Vendor-only commerce-base är landad på `main` (merge commit
`ff3d5124b659b786b0edde5685a857882dcad6c1`, 2026-05-12). Post-merge sanity
är grön (governance + rules_sync + term_coverage + ruff + pytest 368
passed, 3 förväntade skips).

## Current active PR

Ingen pågående feature-PR. PR för denna workflow-uppdatering går direkt
på `main` enligt mainline-steward-regeln.

## Next action

**B13 route-emission för ecommerce-lite.**

`scripts/build_site.py` är hårdkodad mot `local-service-business`-routes
(`/tjanster`, `/om-oss`, `/kontakt`) och respekterar inte `routes.json`
från andra scaffolds. Det blockerar aktivering av
`ecommerce-lite -> commerce-base`. B13 är spårat i `docs/known-issues.md`.

## Blocked items

- **Aktivering av `ecommerce-lite -> commerce-base`** - blockerad av B13.
  `SCAFFOLD_TO_STARTER` i `packages/generation/planning/plan.py` står
  kvar med `ecommerce-lite: marketing-base` tills route-emission är löst.

## Do not start yet

- PR #17 (`frontend/christopher-import`) - ligger draft, ska inte
  granskas eller mergeas förrän B13 är klar.
- StackBlitz-preview, Fly-deploy, PreviewRuntime - inte påbörjat.
- Nya starters utöver `marketing-base` och `commerce-base` (vendor).
- Större Builder UX-utbyggnad.

## Queue

1. B13 route-emission (scaffold-driven page-generation i `build_site.py`).
2. Aktivera mapping `ecommerce-lite -> commerce-base`.
3. Sanity-runda på main + uppdatera `docs/known-issues.md` B20-posten.
4. Därefter: granska PR #17 eller återgå till prompt-till-sajt-loopen.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: implementation-agent → ro-review-agent → operatör + extern
reviewer beslutar → fix-agent vid behov → final sanity → merge →
uppdatera denna fil → nästa etapp.
