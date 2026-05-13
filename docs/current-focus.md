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

Last verified state: `e421a00` (2026-05-14, post-Prompt-till-sajt MVP v1 + audit-hotfix-sprint: ZodError -> 400 i `/api/prompt`, whitespace-trim före `.min(1)`, `--`-separator i Python-spawn så dash-prefixade prompts inte tolkas som CLI-options av argparse, stale viewer-panel fallback-copy uppdaterad till PromptBuilder-flödet, prompt-helperns brief-imports flyttade till modulnivå så test-monkeypatch faktiskt biter, plus allowlist av `ZodError` i `check_term_coverage`. backup-7 från `fb11925` pushad till origin före hotfix-sprinten. Alla guards gröna lokalt; ingen öppen PR)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `e421a00` efter Prompt-till-sajt MVP v1 (Builder-
sprint 2026-05-13/14, Scout-RO-godkänd), review-hotfix för
prompt-helperns brief-fallback, Viewser mini-sprint som tog bort
gamla ChatPanel från home och en audit-hotfix-sprint som städade
fyra Scout-fynd i prompt-flödet. Operatören kan nu skriva
en fri prompt i Viewser, helpern (`scripts/prompt_to_project_input.py`)
kör briefModel, mappar Site Brief deterministiskt mot en schema-valid
Project Input, skriver den till `data/prompt-inputs/<siteId>.project-input.json`
+ sidecar `<siteId>.meta.json` (projectId/version/originalPrompt/
briefSource), och `apps/viewser/app/api/prompt/route.ts` triggar
`runBuild` med dossier-path-override. PromptBuilder är nu den enda
primära promptytan på Viewser-home; legacy ChatPanel finns kvar som
komponent men importeras/renderas inte från `app/page.tsx`. RunHistory
uppdateras via samma `fetchRuns`-loop som `/api/build`. backup-7 från `fb11925`
ligger på origin som fallback efter audit-hotfix-sprinten; backup-6 från
`504befc` ligger kvar som fallback för MVP-pushen.

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
- `ea4b165` — `fix(viewser): isolate StackBlitz preview mount`.
  StackBlitz SDK embed mountas nu i en unmanaged child-node istället
  för att ersätta React-ägda preview-shellen. Cleanup använder
  `replaceChildren()`. Source-lock uppdaterad i `test_viewser_files.py`.
- `fd67fbd` — `refactor(viewser): remove legacy chat panel from home`.
  `app/page.tsx` importerar/renderar inte längre `ChatPanel`; nya
  `test_viewser_prompt_primary.py` låser att PromptBuilder är canonical
  promptyta på Viewser-home.

Audit-hotfix-sprint (2026-05-14, post-Scout-bug-audit):

- `fe56344` — `fix(prompt-helper): hoist brief imports to module level
  for monkeypatching`. Lyfter `detect_language`,
  `extract_site_brief`, `site_brief_to_artifact` och
  `resolve_brief_model` från function-scope till modulnivå så
  fallback-tester faktiskt patchar lookup-namnen som
  `prompt_to_project_input.generate` använder. Tidigare patch mot
  `packages.generation.brief.*` no-opp:ade tyst.
- `cb54ca9` — `docs(agent-prompts): expand role catalog with parallel-
  agent rules`. Utökar Scout/Builder/Steward-startprompter och låser
  parallell-agent-disciplinen.
- `1033bf6` — `fix(prompt-route): return 400 on Zod errors and trim
  whitespace at API edge`. Splitt:ar try/catch så `ZodError` -> 400
  med valideringsmeddelandet, lägger `.trim()` före `.min(1)` i
  payload-schemat så whitespace-only prompts fångas vid API-gränsen
  istället för att slinka ned till helperns 500-gren. Två nya
  source-lock-tester i `tests/test_viewser_files.py`.
- `e067006` — `fix(prompt-runner): pass -- to argparse so dashed
  prompts spawn cleanly`. `spawn(...,[scriptPath, "--", trimmed])` så
  en prompt som börjar med `-` eller `--` (vanlig punktlista) inte
  tolkas som CLI-option av argparse i `prompt_to_project_input.py`.
- `c039ebd` — `fix(viewer-panel): refresh stale fallback copy after
  legacy chat panel removal`. 404-fallback och tip-block hänvisar nu
  till promptfältet istället för den borttagna Build-knappen i
  ChatPanel.
- `e421a00` — `chore(check_term_coverage): allowlist ZodError TS
  symbol`. Speglar Pydantic `ValidationError`-behandlingen så
  `ZodError` (extern lib-symbol från `zod`) inte räknas som
  okänt domänbegrepp i strict-läget.

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
pushad till origin före Prompt-till-sajt-sprinten. `backup-7` (från
`fb11925`) skapad och pushad till origin före audit-hotfix-sprinten.
Kvar lokalt: `main`, `backup-1`, `backup-4`, `backup-5`, `backup-6`,
`backup-7`. Remote har även äldre `backup-2` och `backup-3`.
`frontend/christopher-import` (PR #17, stängd) ska inte röras i
nästa sprint.

## Current active sprint

Ingen pågående produktimplementation. Prompt-till-sajt MVP v1 och
mini-sprinten som gjorde PromptBuilder till enda primära promptyta är
klara. Nästa Builder-sprint blir "Follow-up prompt → ny version"
(läs `data/prompt-inputs/<siteId>.meta.json`, bumpa version,
generera ny build från följdprompt). Sprintstart ska skapa nästa
`backup-N` från synkad `main` och sedan fortsätta arbetet på `main`.

## Next action - direktiv till nästa agent

**Builder-sprint: "Follow-up prompt → ny version".**
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

Steward får gärna uppdatera `docs/handoff.md` innan eller efter
follow-up-sprinten, men det blockerar inte nästa Builder-pass.

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
mergad direktpush `4d5b4de`, audit-hotfix-sprint klar till
`e421a00`. Nästa val är operatörsdrivet, se "Next action" + "Queue".)

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
2. B13a arkitektur-flytt (egen sprint, kräver ADR).
3. `write_pages` icon-bibliotek-agnostisk refactor (förebygger
   lucide-typen av starter-vs-codegen-konflikt; ADR 0020:s
   "INTE beslutar"-sektion).
4. BO2/BO4 backoffice-skuld (round-1-skuld).
5. **PromptBuilder polish (nice-to-have)**: setTimeout för
   stage-transition "thinking" → "building" saknar cleanup vid
   unmount. Låg risk men låt nästa Builder rensa om PromptBuilder
   ändå rörs i Follow-up-sprinten.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → skapa `backup-N` → Builder/Steward jobbar på
`main` → Scout RO-review före push → operatör + extern reviewer beslutar →
final sanity → commit/push till `main` → uppdatera denna fil → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
