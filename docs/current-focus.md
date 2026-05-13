# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Standard loop steg 7 i
[`docs/agent-handbook.md`](agent-handbook.md) är obligatoriskt: efter
varje merge eller direktpush till `main` ska agenten i samma eller direkt
efterföljande commit:

1. Uppdatera "Current stage" och "Current active sprint" till nya läget.
2. Stryka från "Queue" / "Blocked" det som blev klart.
3. Lägga till nya blockers eller queue-items om något upptäcktes.
4. Bumpa "Last verified state"-SHA:n till nya HEAD.

Operatören (Jakob) **verifierar** att det är gjort. Om operatören
upptäcker att filen är inaktuell är det första instruktionen till nästa
agent: "uppdatera current-focus innan något annat".

Last verified state: `ebc9c09` (2026-05-13, post-PR #21 + fyra mainline-steward-pushar till och med RO-audit Queue update `ebc9c09`; alla guards gröna lokalt; ingen öppen PR)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `09c53b0` efter PR #21 (lucide-react i commerce-base
+ ADR 0020, mergad `04fc2fa` 2026-05-13 19:55 UTC) plus tre
mainline-steward-pushar samma kväll. Full `npm run build` mot
`.generated/atelje-bird/` (eller någon annan ecommerce-lite-
genererad sajt) är nu grön: 11 statiska sidor inkl `/produkter`
plus commerce-base:s egna dynamiska routes prerenderas utan
`Module not found`-fel. Föregående PR #20 (B20 step 2 mapping-flip
+ ADR 0019) squash-mergades samma dag 19:33 UTC och aktiverade
`SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Real
codegenModel-scope är fortsatt låst till `marketing-base` per
ADR 0017 (ingen utvidgning beslutad).

Mainline-steward-pushar efter PR #21 (alla pure docs/governance,
ingen produktkod):

- `0db29e6` — `.cursorignore` ignorerar nu hela `referens/` (inte
  bara binärerna). Operatörspreferens; mappen finns kvar på disk
  så docs-länkar funkar.
- `06a6047` — `docs/handoff.md` refreshad till post-PR-#20/#21-
  state, ny "Bugbot-loop på PR"-sektion med GraphQL-tolkning,
  pre-push checklist utökad med ADR-krav och blocker-vs-followup-
  åtskillnad.
- `09c53b0` — `scripts/check_term_coverage.py:COMMON_WORDS`
  allowlistar `Cursor Bugbot`, `SUCCESS`, `FAILURE`, `COMPLETED`,
  `NEUTRAL`, `Module not found` (citerade Bugbot/GitHub-status-
  strängar och Node-felmeddelanden i handoff.md, inte domänbegrepp).

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

## Current active sprint

Ingen pågående produktimplementation. Sprintstart ska skapa nästa
`backup-N` från synkad `main` och sedan fortsätta arbetet på `main`.

## Next action - direktiv till nästa agent

**Prompt-till-sajt-loopen i Viewser** (RO-audit-rekommendation
2026-05-13). B20 + lucide-fix:en är stängda, ingen aktiv blocker,
och RO-audit identifierar att den största produktluckan nu är
"Prompt i Viewser → riktig sajt: saknas". Övriga kedjor finns
delvis (se Queue prio 1 för läget).

Konkret målbild: operatör skriver fri prompt i Viewser-UI → en
helper konverterar till minimal Project Input → `build_site.py`
körs (i bakgrunden eller via subprocess på samma sätt som
`apps/viewser/lib/build-runner.ts` redan gör för Project-Input-
flödet) → resulterande `runId` dyker upp i `<RunHistory>` och
kan inspekteras i `<RunDetailsPanel>`.

Sannolikt scope (verifiera i sprint-start):

- Ny `apps/viewser/`-route (t.ex. `app/prompt/page.tsx` +
  `app/api/prompt/route.ts`).
- Ny prompt-till-Project-Input-helper. Två alternativ:
  återanvänd `briefModel` direkt (Phase 1 redan gör prompt →
  Site Brief; sedan en deterministisk Site Brief → minimal
  Project Input-mappning), eller en ny tunn helper i
  `packages/generation/brief/` om den existerande shape:n inte
  räcker.
- Eventuell `examples/`-mappning så `assertSafeSiteId`-mönstret
  i `apps/viewser/lib/runs.ts` fortfarande håller path-escape-
  risken borta (siteId blir genererat i bakvägen, så validering
  måste ske före file write).

Arbeta på `main` per `governance/rules/branch-discipline.md`, men skapa
först nästa `backup-N` från synkad `main`. Detta rör `apps/viewser/**`
och troligen `packages/generation/`-gränsen, så håll sprintscope smalt och
låt Scout-agenten göra RO-bugggranskning före push. ADR sannolikt inte krävs
om ingen policy/schema rörs, men kontrollera.

Övrig queue (B13a, write_pages-refactor, BO2/BO4) kvarstår men
är inte produkt-blockerande just nu.

### Pre-push self-review checklist (lärt från B13b + B20)

Innan `git push origin main`:

- Jämför `git diff origin/main..HEAD --stat` rad-för-rad mot sprintens
  deklarerade scope. PR #19-lärdomen kvarstår: ändrade filer som inte
  nämns i scope är ofta scope-läckage.
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
- Om sprinten ändrar `SCAFFOLD_TO_STARTER` eller liknande policy-
  förankrad dict: skapa motsvarande ADR i samma ändringsrunda (lärdom från
  PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019).
- Om sprinten har en informativ post-merge-followup som inte blockerar
  push: lägg den i `docs/current-focus.md`, men håll blocker-listan ren från
  nice-to-have.

## Blocked items

(Inga aktiva blockers just nu — B20 + lucide-fix mergade,
sanity-rundan grön mot `04fc2fa`. Nästa val är operatörsdrivet,
se "Next action" + "Queue".)

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

1. **Prompt-till-sajt-loopen i Viewser** (RO-audit-rekommendation
   2026-05-13: nästa konkreta produktsteg). Kedjeläget:
   - Fri prompt → artefakter: finns delvis via
     `scripts/dev_generate.py`.
   - Project Input → riktig sajt: finns via
     `scripts/build_site.py`.
   - **Prompt i Viewser → riktig sajt: saknas** ← nästa steg.
   - Follow-up prompt → ny version: saknas.
   - Lokal preview: finns manuellt, inte produktigt kopplat.
   Konkret målbild: prompt → minimal Project Input → build_site →
   runId i Viewser. Egen sprint på `main` med ny `backup-N` först. Sannolikt
   kräver det en ny `apps/viewser/`-route + en ny
   prompt-till-Project-Input-helper i `packages/generation/brief/`
   eller liknande.
2. B13a arkitektur-flytt (egen sprint, kräver ADR).
3. `write_pages` icon-bibliotek-agnostisk refactor (förebygger
   lucide-typen av starter-vs-codegen-konflikt; ADR 0020:s
   "INTE beslutar"-sektion).
4. BO2/BO4 backoffice-skuld (round-1-skuld).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → skapa `backup-N` → Builder/Steward jobbar på
`main` → Scout RO-review före push → operatör + extern reviewer beslutar →
final sanity → commit/push till `main` → uppdatera denna fil → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
