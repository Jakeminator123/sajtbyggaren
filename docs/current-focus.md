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

Last verified state: `b4fe4a8` (2026-05-13, mainline-steward gitignore-pre-allow för B13a-destination + .cursor/mcp.json-precaution; PR #19 öppen)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Notes on B13 naming (2026-05-13)

B13 i `docs/known-issues.md` har splittats i B13a (arkitektur-
flytt av produktlogik från `scripts/build_site.py` till
`packages/generation/build/` — fortfarande öppen) och B13b
(route-emission, kod klar, inväntar merge av PR #19). När den här
filen nämner "B13b" är det route-emission-spåret; den större
arkitektur-flytten kvarstår som B13a oavsett vad som händer med
PR #19.

## Current stage

Post-PR #16 + PR #18. PR #18 (cursor/setup-dev-environment-c32f) har
mergat på `main` som `90856d1` 2026-05-13: `AGENTS.md` har rätt
`python3.12-venv`-paketnamn för Cloud Agent VMs. Vendor-only
commerce-base från PR #16 ligger fortfarande kvar
(`ff3d5124b659b786b0edde5685a857882dcad6c1`, 2026-05-12).

Mainline-steward direktpush `b4fe4a8` (2026-05-13) städar två footguns
som dök upp under B13-arbetet: `.gitignore` + `.cursorignore` matchar
inte längre `packages/generation/build/` (den blivande destinationen
för B13a-arkitektur-flytten); `.cursor/mcp.json` är gitignored så
MCP-OAuth-tokens inte kan slinka in i en commit. Existerande
`packages/generation/build/.gitkeep` är nu spårad (den var tyst
ignorerad sedan 2026-05-11).

B13b route-emission ligger på feature-branchen `feat/b13-route-emission`
som **PR #19** (HEAD `7f670b8` inkluderar Bugbots print-order-fix).
Den fullständiga statusen för B13b och alla detaljer om PR #19 lever
på branchen; den merge:n återställer denna fil till sin uppdaterade
form.

## Current active PR

**PR #19** (`feat/b13-route-emission` → `main`) — öppen, inväntar
Cursor Bugbot-re-run efter print-order-fix-pushen `7f670b8`. Squash-
merge när Bugbot är nöjd och operatör godkänner.

## Next action

Vänta in Bugbot-rapporten på **PR #19** (Bugbot-fyndet
"Writing pages-print kör efter write_pages" är fixat i `7f670b8` med
två source-level regression-tests). Eventuell ny fix-runda → merge
(squash). Direkt efter merge: bumpa SHA:n här till mergekommiten på
`main` och flytta B13b från "Öppna" till "Stängda" i
`docs/known-issues.md`.

## Blocked items

- **Aktivering av `ecommerce-lite -> commerce-base`** — blockerad
  tills **PR #19** är mergad. `SCAFFOLD_TO_STARTER` i
  `packages/generation/planning/plan.py` står kvar med
  `ecommerce-lite: marketing-base` tills B13b ligger på `main` och en
  uppföljande PR flippar mappingen + uppdaterar
  `data/starters/README.md` och `docs/known-issues.md` B20-posten.

## Do not start yet

- **PR #17** (`frontend/christopher-import`) — ligger draft, ska inte
  granskas eller mergeas förrän **PR #19** är mergad.
- StackBlitz-preview, Fly-deploy, PreviewRuntime — inte påbörjat.
- Nya starters utöver `marketing-base` och `commerce-base` (vendor).
- Större Builder UX-utbyggnad.
- B13a arkitektur-flytt (`scripts/build_site.py` produktlogik →
  `packages/generation/build/`) — kvarstår som öppen post men kräver
  egen sprint + sannolikt egen ADR; destinationen är nu pre-allokerad
  i `.gitignore` + `.cursorignore`.

## Queue

1. Invänta Bugbot på **PR #19**, ev. fix-runda, merge.
2. Aktivera mapping `ecommerce-lite -> commerce-base` (separat PR:
   flippa `SCAFFOLD_TO_STARTER`, uppdatera `data/starters/README.md`
   mappnings-blocket, stryk "B20 step 2 blocked"-noten från
   `docs/known-issues.md`, lägg test som verifierar att
   `atelje-bird` byggs mot `commerce-base` när codegenModel-scope
   utvidgas eller deterministisk fallback duger).
3. Sanity-runda på `main` + uppdatera `docs/known-issues.md` B13b +
   B20-posten (markera B13b som fixad; B13a är arkitektur-skuld,
   kvarstår).
4. Därefter: granska **PR #17** eller återgå till prompt-till-sajt-loopen.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: implementation-agent → ro-review-agent → operatör + extern
reviewer beslutar → fix-agent vid behov → final sanity → merge →
uppdatera denna fil → nästa etapp.
