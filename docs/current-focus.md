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

Last verified state: `5443d34` (2026-05-13, B13 route-emission PR #19 öppen och inväntar Bugbot-review)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

Post-PR #16 + PR #18. PR #18 (cursor/setup-dev-environment-c32f) har
mergat på `main` som `90856d1` 2026-05-13: `AGENTS.md` har rätt
`python3.12-venv`-paketnamn för Cloud Agent VMs. Vendor-only
commerce-base från PR #16 ligger fortfarande kvar
(`ff3d5124b659b786b0edde5685a857882dcad6c1`, 2026-05-12).

B13 route-emission är **implementerad** på `feat/b13-route-emission`
(commits `6a0a1c5` + `6516c28` + docs-bump `5443d34`).
`scripts/build_site.py:write_pages` läser nu
`scaffold_routes["defaultRoutes"]` och dispatchar per route id i stället
för att hårdkoda `/tjanster`. Smoke-testet
`test_ecommerce_lite_fixture_writes_produkter_and_passes_route_scan`
bekräftar att `examples/atelje-bird.project-input.json`
(`scaffoldId=ecommerce-lite`) genererar `/produkter` och Quality Gate
route-scan blir `status=ok`. Pytest 381 passed, 3 förväntade skips.
Ruff, governance_validate, rules_sync och check_term_coverage.py
--strict gröna. Pre-push ro-review (explore RO-subagent) körd; två
fynd åtgärdade i `6516c28` (död `_ROUTE_RENDERERS`-dict + docstring
för `render_home(listing_route=None)`-fallback).

## Current active PR

**PR #19** (`feat/b13-route-emission` → `main`) - öppen, inväntar
Cursor Bugbot-review. HEAD `5443d34`. Squash-merge när Bugbot är
nöjd och operatör godkänner.

## Next action

Vänta in Bugbot-rapporten på **PR #19**, åtgärda eventuella findings
i en fix-runda, kör `python scripts/review_check.py` lokalt, merge
(squash). Direkt efter merge: bumpa SHA:n här till mergekommiten på
`main`.

## Blocked items

- **Aktivering av `ecommerce-lite -> commerce-base`** - blockerad
  tills **PR #19** är mergad. `SCAFFOLD_TO_STARTER` i
  `packages/generation/planning/plan.py` står kvar med
  `ecommerce-lite: marketing-base` tills B13 ligger på `main` och en
  uppföljande PR flippar mappingen + uppdaterar
  `data/starters/README.md` och `docs/known-issues.md` B20-posten.

## Do not start yet

- **PR #17** (`frontend/christopher-import`) - ligger draft, ska inte
  granskas eller mergeas förrän **PR #19** är mergad.
- StackBlitz-preview, Fly-deploy, PreviewRuntime - inte påbörjat.
- Nya starters utöver `marketing-base` och `commerce-base` (vendor).
- Större Builder UX-utbyggnad.

## Queue

1. Invänta Bugbot på **PR #19**, ev. fix-runda, merge.
2. Aktivera mapping `ecommerce-lite -> commerce-base` (separat PR:
   flippa `SCAFFOLD_TO_STARTER`, uppdatera `data/starters/README.md`
   mappnings-blocket, stryk "B20 step 2 blocked"-noten från
   `docs/known-issues.md`, lägg test som verifierar att
   `atelje-bird` byggs mot `commerce-base` när codegenModel-scope
   utvidgas eller deterministisk fallback duger).
3. Sanity-runda på `main` + uppdatera `docs/known-issues.md` B13 +
   B20-posten (markera B13 som fixad).
4. Därefter: granska **PR #17** eller återgå till prompt-till-sajt-loopen.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: implementation-agent → ro-review-agent → operatör + extern
reviewer beslutar → fix-agent vid behov → final sanity → merge →
uppdatera denna fil → nästa etapp.
