# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Standard loop steg 7 i
[`docs/agent-handbook.md`](agent-handbook.md) är obligatoriskt: efter
varje merge eller direktpush till `main` ska agenten i samma eller direkt
efterföljande commit:

1. Uppdatera "Current stage" och "Current active PR" till nya läget.
2. Stryka från "Queue" / "Blocked" det som blev klart.
3. Lägga till nya blockers eller queue-items om något upptäcktes.
4. Bumpa "Last verified state"-SHA:n till nya HEAD.

Operatören (Jakob) **verifierar** att det är gjort. Om operatören
upptäcker att filen är inaktuell är det första instruktionen till nästa
agent: "uppdatera current-focus innan något annat".

## Last verified

Last verified state: `1d6aae1` (2026-05-13, post-PR #16 + lightweight loop + focus_check tolerance)

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
- PR #18 (`cursor/setup-dev-environment-c32f`) - Cursor BG-agent-fix
  för `python3.12-venv`-paketnamn i `AGENTS.md`. Liten och säker,
  men operatör beslutar om merge. Inte i agentens kö.
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
