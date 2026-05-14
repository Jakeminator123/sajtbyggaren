# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.
Startpromptar och rollgränser finns i
[`docs/agent-prompts.md`](agent-prompts.md).

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Standard loop steg 8 i
[`docs/agent-handbook.md`](agent-handbook.md) är obligatoriskt: efter
varje merge eller direktpush till `main` ska agenten i samma eller direkt
efterföljande commit:

1. Uppdatera "Current stage" och "Current active sprint" till nya läget.
2. Stryka från "Queue" / "Blocked" det som blev klart.
3. Lägga till nya blockers eller queue-items om något upptäcktes.
4. Bumpa "Last verified state"-SHA:n till nya HEAD.

Steward ska dessutom post-push-verifiera origin/main-SHA, `git status`,
`python scripts/focus_check.py` och om `origin/main` matchar lokal `main`.
Uppdatera `current-focus.md` och/eller `handoff.md` när ny faktisk HEAD
avslutar en sprint, active sprint ändras, next action/queue/blocked ändras,
ett beslut påverkar agentflöde, branchflöde, grindmode eller rollansvar, ny
risk/blocker/nice-to-have blir viktig för nästa agent, eller extern PR/
Grind-agent ändrar vad `main` betyder. Uppdatera inte för ren mikrostatus
som inte ändrar nästa agents arbete.

Operatören (Jakob) **verifierar** att det är gjort. Om operatören
upptäcker att filen är inaktuell är det första instruktionen till nästa
agent: "uppdatera current-focus innan något annat".

Last verified state: `2701b00` (2026-05-14, post-follow-up prompt versions: Builder landade `feat(viewser): add follow-up prompt versions` direkt på `main`, lokal `main` och `origin/main` är synkade på `2701b00`, och `focus_check.py` rapporterar endast lokal `.cursor/settings.json` som ocommittad operatörsinställning. Öppna PRs finns: #22 portfolio-base starter och #23 backoffice trace/playground är båda draft och ska inte mergas förrän respektive base-/Bugbot-status är klar.)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid `2701b00` efter Prompt-till-sajt MVP v1 (Builder-
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
komponent men importeras/renderas inte från `app/page.tsx`. Follow-up
prompt versions är nu landat: operatören kan fortsätta på befintlig
prompt-input/run, behålla `projectId`, bumpa version och få ny build/run
för samma sajtspår. RunHistory uppdateras via samma `fetchRuns`-loop som
`/api/build`. backup-8 finns lokalt efter follow-up-sprinten; backup-7 från
`fb11925` ligger på origin som fallback efter audit-hotfix-sprinten.

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
- `2f0af68` — `docs: bump focus + handoff to e421a00 post-audit-
  hotfix-sprint`. Standard loop steg 7 efter audit-hotfix-sprinten:
  bumpar SHA + uppdaterar Queue/Blocked.
- `c3dcc14` — `docs: correct verified HEAD to 2f0af68 in focus +
  handoff`. Följdfix ovanpå `2f0af68`; lokal `main` och `origin/main`
  är post-push-verifierade på denna SHA.
- `006be38` — `docs(workflow): formalize steward post-push
  verification`. Låser Builder→Steward-post-push-flödet i docs,
  governance-spegeln och `focus_check.py`-remindern.
- `2701b00` — `feat(viewser): add follow-up prompt versions`.
  Follow-up prompt versions landat direkt på `main`: promptflödet kan
  fortsätta på befintligt `projectId`, bumpa version och skriva nya
  prompt-inputs/runs för samma sajtspår.

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

Ingen pågående produktimplementation på `main`. Prompt-till-sajt MVP v1,
mini-sprinten som gjorde PromptBuilder till enda primära promptyta och
follow-up prompt versions är klara. Nästa arbete är PR-/queue-triage:
#22 och #23 är öppna draft-PRs och ska inte mergas förrän respektive
base-/Bugbot-status är klar.

## Next action - direktiv till nästa agent

**PR-/queue-triage efter follow-up prompt versions.**

- #22 `portfolio-base` starter är öppen draft-PR. Den ska inte mergas
  förrän branchen/base-läget är uppdaterat mot senaste `main` och
  operatören uttryckligen vill gå från draft till ready.
- #23 backoffice trace/playground är öppen draft-PR. Den ska inte
  markeras ready eller mergas förrän Bugbot-status/fynd är klara.
- Lokal `.cursor/settings.json` är ändrad av operatörsmiljön och ska
  inte committas utan explicit operatörsbeslut.

När PR-spåren är utredda är nästa produktval åter öppet: B13a,
`write_pages` icon-bibliotek-agnostisk refactor eller nästa Builder UX-
steg.

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

Öppna PRs blockerar inte `main`, men får inte mergas ännu:

- #22 `portfolio-base` starter: draft; uppdatera/verifiera mot senaste
  `main` innan ready/merge.
- #23 backoffice trace/playground: draft; Bugbot-status/fynd måste vara
  klara innan ready/merge.

Lokal `.cursor/settings.json` är ocommittad operatörs-/plugininställning
och ska inte ingå i Steward-commit utan explicit beslut.

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

1. **#22 portfolio-base starter** — draft-PR; uppdatera/verifiera mot
   senaste `main` före ready/merge.
2. **#23 backoffice trace/playground** — draft-PR; invänta/hantera
   Bugbot-status/fynd före ready/merge.
3. B13a arkitektur-flytt (egen sprint, kräver ADR).
4. `write_pages` icon-bibliotek-agnostisk refactor (förebygger
   lucide-typen av starter-vs-codegen-konflikt; ADR 0020:s
   "INTE beslutar"-sektion).
5. BO2/BO4 backoffice-skuld (round-1-skuld; se #23 innan ny separat
   sprint planeras).
6. **PromptBuilder polish (nice-to-have)**: setTimeout för
   stage-transition "thinking" → "building" saknar cleanup vid
   unmount. Låg risk men låt nästa Builder rensa om PromptBuilder
   ändå rörs igen.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → skapa `backup-N` → Builder/Steward jobbar på
`main` → Scout RO-review före push → vid push-OK och clean tree får Builder
pusha direkt → Steward post-push-verifierar → uppdatera denna fil vid faktisk
fokus-/handoff-förändring → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
