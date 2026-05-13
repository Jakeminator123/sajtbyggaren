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

Last verified state: `fda1464` (2026-05-13, B13b route-emission mergad via PR #19; branches städade; PR #17 stängd)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `fda1464` efter att PR #19 (B13b route-emission)
squash-mergades 2026-05-13 18:38 UTC. `scripts/build_site.py:write_pages`
är nu scaffold-drivet: `ecommerce-lite` genererar `/produkter` och
ecommerce-lite-fixturen `examples/atelje-bird.project-input.json`
passerar Quality Gate route-scan.

Pre-PR #19 mainline-steward-pushar som också ligger på main:
- `61f9f69` - ny `reply-style`-regel (kort+koncis svenska med
  parens-förklaringar för dev-uttryck) under `governance/rules/`.
- `b4fe4a8` + `1c2227b` - `.gitignore`/`.cursorignore` pre-allokerar
  `packages/generation/build/` (B13a-destinationen) och blockar
  `.cursor/mcp.json`.

Branches städade 2026-05-13: lokala `feat/b13-route-emission` och
`review/builder-ux-mvp-86068f7` raderade; remotes
`cursor/setup-dev-environment-c32f` och `fix/b20-commerce-base`
raderade. Kvar: `main`, `backup-{1..4}` och
`frontend/christopher-import` (PR #17, stängd men branch behållen
per operatörsbeslut).

## Current active PR

Ingen pågående feature-PR.

## Next action - direktiv till nästa agent

**B20 step 2: aktivera `ecommerce-lite -> commerce-base`-mappningen.**

Förutsättningar är redan på plats: B13b route-emission är mergad
(`fda1464`), `commerce-base`-starter är vendoriserad sedan PR #16
(`ff3d512`), `examples/atelje-bird.project-input.json` finns som
ecommerce-lite-fixture, `_pick_contact_route` + scaffold-driven
nav/listing är på plats.

Konkret att göra på egen branch `feat/b20-step-2-mapping-flip`:

1. Kör `python scripts/focus_check.py` först. Adresera varningar
   innan du börjar.
2. Ändra i `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER`:
   `"ecommerce-lite": "marketing-base"` -> `"ecommerce-lite": "commerce-base"`.
3. Uppdatera `data/starters/README.md` scaffold-starter-mapping-blocket:
   stryk `(B20: temporary; ...)`-noten från `ecommerce-lite`-raden.
4. Kör `python -m pytest tests/test_starter_scaffold_mapping.py -v`.
   `test_b20_temporary_mapping_is_explicit` ska nu klara sig själv
   (den triggar bara när mappningen är `marketing-base`).
5. Kör `python scripts/build_site.py --dossier
   examples/atelje-bird.project-input.json --skip-build` och bekräfta:
   - `build-result.json` har `starterId: commerce-base`.
   - `quality-result.json` har `status: ok` (eller `degraded` med en
     known cause - inte route-scan failure).
   - `app/produkter/page.tsx` emitteras, `app/tjanster/page.tsx`
     emitteras INTE.
6. Risk: real-codegenModel i
   `packages/generation/codegen/codegen.py:_REAL_CODEGEN_STARTERS` är
   låst till `marketing-base` (ADR 0017). För ecommerce-lite faller
   den tillbaka till `deterministic-v1`. Det är OK för B20 step 2;
   utvidgning av real-codegen-scope är separat sprint som kräver
   ADR-utökning ovanpå 0017.
7. Försök att köra full `npm run build` på en
   genererad `.generated/atelje-bird/` (utan `--skip-build`). Om det
   misslyckas pga Shopify-env eller liknande externa beroenden:
   dokumentera under "Known risks" i PR-beskrivningen och be
   operatören välja om B20 stängs på `--skip-build`-nivå eller om
   commerce-base behöver mer guarding först.
8. Standard loop: branch -> commit -> push -> PR -> invänta Bugbot ->
   åtgärda fynd -> merge.
9. Post-merge Standard loop steg 7: flytta B20-posten i
   `docs/known-issues.md` till "Stängda - regression-test säkrar
   fixet"-avsnittet med merge-SHA, och bumpa "Last verified"-SHA:n
   här.

### Pre-push self-review checklist (lärt från B13b)

Innan `git push` på en feature-branch:

- Jämför `git diff origin/main..HEAD --stat` rad-för-rad mot din PR-
  beskrivnings "What changed"-lista. Bugbot fångade på PR #19 att
  `docs/known-issues.md` ändrades utan att stå i listan.
- Sök efter samma sorts hardcoded-pattern som PR:n säger sig fixa.
  PR #19 fixade hardcoded `/tjanster`/`/om-oss`/`/kontakt`, men en
  ny `render_products` introducerade hardcoded `/kontakt` igen.
  Klassiskt blindspot på nya filer.
- Om printar/loggar har present tense ("Writing X"): placera dem
  FÖRE handlingen, inte efter. Operatör ska se vad som är i flygt
  vid crash.
- För varje ny renderer som tar `dossier`: kontrollera om den
  länkar någonstans och om den pathen ska komma från scaffolden
  (`_pick_*_route`) eller bara från dossiern.

## Blocked items

(Inga aktiva blockers just nu — B20 step 2 är nästa PR och dess
förutsättningar är på plats.)

## Do not start yet

- StackBlitz-preview, Fly-deploy, PreviewRuntime - inte påbörjat.
- Nya starters utöver `marketing-base` och `commerce-base` (vendor).
- Större Builder UX-utbyggnad.
- B13a arkitektur-flytt (`scripts/build_site.py` produktlogik ->
  `packages/generation/build/`) - kvarstår som öppen post men kräver
  egen sprint + sannolikt egen ADR. Destinationen är pre-allokerad i
  `.gitignore` + `.cursorignore` (kommit `b4fe4a8`).
- Pre-existing hardcoded `/kontakt`-CTAs i
  `render_home/render_services/render_layout` (predaterar PR #19).
  Migrera till `_pick_contact_route` när tillfälle ges; ingen aktiv
  B-ID skriven på det än.

## Queue

1. B20 step 2 mapping-flipp (se "Next action" ovan).
2. Sanity-runda på `main` efter B20-merge.
3. B13a arkitektur-flytt (egen sprint, kräver ADR).
4. Återgå till prompt-till-sajt-loopen eller plocka upp någon av
   BO2/BO4 (Backoffice-skuld från round 1).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: implementation-agent → ro-review-agent → operatör + extern
reviewer beslutar → fix-agent vid behov → final sanity → merge →
uppdatera denna fil → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
