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

Last verified state: `75c980b` (2026-05-13, B20 step 2 mapping-flip mergad via PR #20 + ADR 0019; bugbot-pr-loop-regel tillagd `bba8e36`; branch `feat/b20-step-2-mapping-flip` städad lokalt + remote)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `75c980b` efter att PR #20 (B20 step 2 mapping-flip
+ ADR 0019) squash-mergades 2026-05-13 19:33 UTC.
`SCAFFOLD_TO_STARTER["ecommerce-lite"]` är nu `commerce-base`;
ecommerce-lite-fixturen `examples/atelje-bird.project-input.json`
producerar `app/produkter/page.tsx` (inte `/tjanster`) genom
`source=deterministic-v1` codegen och passerar Quality Gate
route-scan + policy-compliance med `--skip-build`. Real
codegenModel-scope är fortsatt låst till `marketing-base` per
ADR 0017 (ingen utvidgning beslutad).

Mainline-steward-pushar som också ligger på main:
- `bba8e36` - ny `bugbot-pr-loop`-regel (8-min poll + 10-iter
  fix-loop + nödläge-eskalering) under `governance/rules/`.
- `af8b337` - refresh av `docs/handoff.md` för main-as-default-
  policy + post-B13b-state.
- `61f9f69` - `reply-style`-regel (kort+koncis svenska med
  parens-förklaringar för dev-uttryck) under `governance/rules/`.
- `b4fe4a8` + `1c2227b` - `.gitignore`/`.cursorignore` pre-allokerar
  `packages/generation/build/` (B13a-destinationen) och blockar
  `.cursor/mcp.json`.

Branches städade 2026-05-13: feat/b20-step-2-mapping-flip raderad
lokalt + remote efter merge. Kvar: `main`, `backup-{1..4}` och
`frontend/christopher-import` (PR #17, stängd men branch behållen
per operatörsbeslut).

## Current active PR

Ingen pågående feature-PR.

## Next action - direktiv till nästa agent

**Sanity-runda på `main` efter B20-merge + (om operatör vill)
plocka lucide-react-konflikten som ny B-ID.**

Sanity-rundan: kör `python scripts/focus_check.py` (ska visa OK
mot `75c980b`), kör `python scripts/review_check.py` om du vill
ha hela kedjan på en gång, och verifiera artefakter med
`python scripts/build_site.py --dossier
examples/atelje-bird.project-input.json --skip-build` och
`python scripts/build_site.py --dossier
examples/painter-palma.project-input.json --skip-build` så att
ingen scaffold-driven path har drivit.

Lucide-react-konflikten (introducerad som synlig av PR #20):
full `npm run build` mot `.generated/atelje-bird/` faller på
`Module not found: lucide-react` eftersom
`scripts/build_site.py:write_pages` hardcodar lucide-imports per
renderer (`render_home`, `render_about`, `render_contact`,
`render_layout`, `render_products`) men `commerce-base/package.json`
bara har `@heroicons/react`. Marketing-base har `lucide-react` så
det syns inte där. Två fix-vägar:

- Lägg `lucide-react` i `commerce-base/package.json` med
  `package-lock.json`-uppdatering. Snabbast, men starter-doktrinen
  i `data/starters/README.md` rad 105 säger att nya deps i en
  starter kräver operatörsgodkännande.
- Gör `write_pages` icon-bibliotek-agnostisk per starter (mappa
  ikoner via en starter-config eller använd inline SVG). Bredare
  refactor av deterministic-v1 codegen.

När operatör har valt väg: lägg upp som nytt B-ID i
`docs/known-issues.md` och plocka som egen PR enligt
`governance/rules/branch-discipline.md` + `bugbot-pr-loop.md`.

### Pre-push self-review checklist (lärt från B13b + B20)

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
- Om PR ändrar `SCAFFOLD_TO_STARTER` eller liknande policy-
  förankrad dict: skapa motsvarande ADR i samma PR (lärdom från
  PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019).
- Om PR har en informativ post-merge-followup som inte blockerar
  merge: lägg den under "Post-merge sanity needed", INTE under
  "Known risks / blockers". Bugbot tolkar varje rad i blocker-
  sektionen som hård gate (lärdom från PR #20:s Bugbot-iteration 1).

## Blocked items

(Inga aktiva blockers just nu — B20 step 2 är mergad och
sanity-rundan är nästa konkreta arbete; lucide-react-konflikten
väntar på operatörsbeslut om fix-väg.)

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

1. Sanity-runda på `main` efter B20-merge (se "Next action" ovan).
2. Lucide-react fix-väg när operatör valt riktning (eget B-ID).
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
