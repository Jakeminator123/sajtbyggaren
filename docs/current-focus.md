# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.
Startpromptar och rollgränser finns i
[`docs/agent-prompts.md`](agent-prompts.md).

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

Last verified state: `c6e2f1d` (2026-05-14, post-Prompt-till-sajt MVP v1 + review-hotfix: prompt-helpern faller nu tillbaka till mock Site Brief om `extract_site_brief` eller `site_brief_to_artifact` kastar. backup-6 från `504befc` pushad till origin före sprintstart. Alla guards gröna lokalt; ingen öppen PR)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `c6e2f1d` efter Prompt-till-sajt MVP v1 (Builder-
sprint 2026-05-13/14, Scout-RO-godkänd) plus review-hotfix för
prompt-helperns brief-fallback. Operatören kan nu skriva
en fri prompt i Viewser, helpern (`scripts/prompt_to_project_input.py`)
kör briefModel, mappar Site Brief deterministiskt mot en schema-valid
Project Input, skriver den till `data/prompt-inputs/<siteId>.project-input.json`
+ sidecar `<siteId>.meta.json` (projectId/version/originalPrompt/
briefSource), och `apps/viewser/app/api/prompt/route.ts` triggar
`runBuild` med dossier-path-override. RunHistory uppdateras via
samma `fetchRuns`-loop som `/api/build`. backup-6 från `504befc`
ligger på origin som fallback.

Föregående: PR #21 (lucide-react i commerce-base + ADR 0020,
mergad `04fc2fa` 2026-05-13 19:55 UTC) gjorde full `npm run build`
mot `.generated/atelje-bird/` grön (11 statiska sidor + commerce-
base:s dynamiska routes utan `Module not found`). PR #20 (B20 step 2
mapping-flip + ADR 0019, samma dag 19:33 UTC) aktiverade
`SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Real
codegenModel-scope är fortsatt låst till `marketing-base` per
ADR 0017 (ingen utvidgning beslutad).

Prompt-till-sajt MVP v1-pushen (2026-05-14):

- `afaa8a8` — `docs(workflow): formalize progress estimate + scout
  model level`. Operatörs-supplied: Builder slutrapport ska ge en
  grov progress-procent + bedömning av nästa etapp; Scout föreslår
  modell-/insatsnivå 1-10; Steward verifierar att current-focus +
  handoff fortfarande pekar rätt.
- `4d5b4de` — `feat(viewser): prompt-till-sajt MVP v1`. Ny
  `scripts/prompt_to_project_input.py` (briefModel + Site Brief →
  schema-valid Project Input + sidecar meta i `data/prompt-inputs/`),
  ny `/api/prompt` route med localhost-guard + Zod-payload (1-4000
  tecken), ny PromptBuilder-UI-panel, `runBuild` får
  dossier-path-override bakom ALLOWED_DOSSIER_ROOTS-whitelist
  (examples/ + data/prompt-inputs/), 11 nya helper-tester + 2 nya
  viewser-guards. Ingen ADR/policy-bump (sidecar-meta undviker
  project-input.schema.json-migration).
- `c6e2f1d` — `fix(viewser): fall back when prompt brief extraction
  raises`. Review-hotfix: `extract_site_brief` och
  `site_brief_to_artifact` ligger nu i fallback-try/catch så
  promptflödet skriver schema-valid mock Project Input även vid
  oväntade LLM-/serialiseringsfel. Regressions täcker båda grenarna.

Mainline-steward-pushar efter PR #21 (pure docs/governance):

- `0db29e6` — `.cursorignore` ignorerar nu hela `referens/`.
- `06a6047` — `docs/handoff.md` refreshad till post-PR-#20/#21-state.
- `09c53b0` — `check_term_coverage.py` allowlistar Bugbot/GitHub-
  statussträngar.
- `ebc9c09` — `current-focus.md` Queue/Next action efter RO-audit.
- `2aafa41` — agentflödet formaliseras (3 fasta roller +
  backup-N-disciplin + Scout som RO-bugggranskare).
- `504befc` — `agent-prompts.md` flyttad in i `docs/`.

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

Branches städade 2026-05-13/14: feat/b20-step-2-mapping-flip raderad
lokalt + remote efter merge. `backup-6` (från `504befc`) skapad och
pushad till origin före Prompt-till-sajt-sprinten. Kvar lokalt:
`main`, `backup-1`, `backup-4`, `backup-5`, `backup-6`. Remote har
även äldre `backup-2` och `backup-3`. `frontend/christopher-import`
(PR #17, stängd) ska inte röras i nästa sprint.

## Current active sprint

Ingen pågående produktimplementation. Prompt-till-sajt MVP v1 är
klar; nästa Builder-sprint blir "Follow-up prompt → ny version"
(läs `data/prompt-inputs/<siteId>.meta.json`, bumpa version,
generera ny build från följdprompt). Sprintstart ska skapa nästa
`backup-N` från synkad `main` och sedan fortsätta arbetet på `main`.

## Next action - direktiv till nästa agent

**Steward-pass först:** uppdatera `docs/handoff.md` så det
reflekterar den nya promptdrivna loopen (Prompt-till-sajt MVP v1
landad `4d5b4de`). Överväg också om den experimentella
chat-panel-prompten i `apps/viewser/components/chat-panel.tsx`
ska markeras deprecated eller tas bort - den var tänkt som
platshållare för exakt det flöde som nu är byggt; den nya
`PromptBuilder` är canonical promptyta. Builder lät den ligga
för scope-disciplin under MVP v1-sprinten.

**Sedan Builder-sprint: "Follow-up prompt → ny version".**
Konkret målbild: operatör väljer en befintlig run (eller siteId
under `data/prompt-inputs/`) → skriver en följdprompt → helpern
läser sidecar-meta, bumpar `version`, genererar ny Project Input
(diff-applicerad eller helt ny baserad på följdpromptens
intentioner) → `build_site.py` körs → ny runId med samma
`projectId` syns i Run History.

Sannolikt scope (verifiera i sprint-start):

- Utöka `scripts/prompt_to_project_input.py` (eller lägg
  syskon-script `scripts/follow_up_prompt.py`) som tar
  `--project-id` + `--prompt` och bumpar `meta.version`.
- Ny `/api/prompt/follow-up`-route (eller utökad `/api/prompt`
  med `mode: "init" | "followup"`).
- UI-utökning av `PromptBuilder` så operator kan välja
  "ny sajt" vs "följdprompt på senaste run".
- Tester som låser version-bump och projectId-stabilitet
  över N follow-ups.

ADR sannolikt inte krävs i denna sprint heller om sidecar-meta
fortsatt håller. Om det visar sig att Project Input-schemat
behöver ett `projectId`/`version`-fält - då krävs ADR.

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
sanity-rundan grön mot `04fc2fa`, Prompt-till-sajt MVP v1
mergad direktpush `4d5b4de`. Nästa val är operatörsdrivet,
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
- PR #17 / `frontend/christopher-import` - behåll som design-/copy-
  referens only. Återöppna inte PR #17 och starta inte `apps/web` förrän
  Prompt-till-sajt MVP fungerar.

## Queue

1. **Follow-up prompt → ny version** (nästa konkreta produktsteg
   efter Prompt-till-sajt MVP v1, 2026-05-14). Kedjeläget:
   - Fri prompt → artefakter: finns via `scripts/dev_generate.py`.
   - Project Input → riktig sajt: finns via `scripts/build_site.py`.
   - Prompt i Viewser → riktig sajt: **finns** via Prompt-till-sajt
     MVP v1 (`/api/prompt`, `PromptBuilder`, helper i
     `scripts/prompt_to_project_input.py`).
   - **Follow-up prompt → ny version: saknas** ← nästa steg.
   - Lokal preview: finns manuellt, inte produktigt kopplat.
   Sidecar-meta `data/prompt-inputs/<siteId>.meta.json` har redan
   `projectId` + `version` så ingen schema-migration behövs i
   första iterationen. Se "Next action" för scope-skiss.
2. **Steward: deprecate eller ta bort experimentella chat-prompten**
   i `apps/viewser/components/chat-panel.tsx`. PromptBuilder är
   nu canonical promptyta. Builder lät den ligga för
   scope-disciplin; Steward kan rensa.
3. B13a arkitektur-flytt (egen sprint, kräver ADR).
4. `write_pages` icon-bibliotek-agnostisk refactor (förebygger
   lucide-typen av starter-vs-codegen-konflikt; ADR 0020:s
   "INTE beslutar"-sektion).
5. BO2/BO4 backoffice-skuld (round-1-skuld).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → skapa `backup-N` → Builder/Steward jobbar på
`main` → Scout RO-review före push → operatör + extern reviewer beslutar →
final sanity → commit/push till `main` → uppdatera denna fil → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
