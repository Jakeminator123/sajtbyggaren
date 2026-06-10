# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-10 ~06:00 — NATTPASSET STÄNGT, ny orchestrator tar över)

**Git:** `main = jakob-be = 6ea53c0` (rent träd, i sync med origin).
**Main-sync GJORD 2026-06-10 ~10:00** (operatörsbeslut verkställt): `jakob-be`
tog över `main` via merge av mains 3 docs-only commits (#255 AGENTS-dedupe +
steward-bump) + ren fast-forward → tom diff `main↔jakob-be`. Pre-sync-state
sparad som `backup_150_BRA` (= `1560974`). Enda öppna PR: **#156** (parkerad
referens). Alla mergade PR-brancher städade (lokalt + remote).

**Nattens facit (16 PRs mergade, 13 buggar stängda B163–B175):**

- **#252** main-sync (merge-tåget #238–#251+#225 till main, ren övertagning).
- **#254** bug-sweep: B163 stale preview, B165 www-crawl, B167 prune-portar,
  B168/B170/B171 OpenAI-env.
- **#255** (main) AGENTS.md-dedupe. **#256** B166 wizard-Hämta nested merge.
- **#257** hostad Viewser: ärlig 2A-degradering + gatad 2B sandbox-preview.
  Live på jakob-be-previewen bakom SSO (Deployment Protection verifierad
  med 401); prod väntar på main-sync. Sandbox-flaggan ALDRIG utan skydd.
- **#258** backoffice-grind: vy-register-lås, Idag-vy, Loop-bevis.
- **#259+#262** OpenClaw F1 slice 1+2: rollkontrakt + ConversationKind +
  conductor-wiring — **smarta chatten är LIVE** (skämt/omdöme/fråga →
  ärligt chat-svar utan bygge; operatörens skämt-test var beviset).
- **#260** B164 dubbelbygge-recovery + B169 per-site-mutex + B172
  siteId-filtrerad runId. **#267** B175: recoveryn täcker first-run
  (mtime-färskhet när pre-bridge-run saknas).
- **#261** B155-slice: okvoterad literal-ersättning (B155 hålls öppen för
  kvarvarande targets). **#263** sandbox Tier 1: pre-built `.next`-upload
  (~20 s/preview), OIDC-autorefresh, timings i preview-svaret (+ Scout-R1
  trace-katalog-härdning direkt på jakob-be, `472e150`).
- **#264** B173 hero-H1-pinning i BÅDA seams (generate_followup +
  apply_patch_plan) — rubriken slutar drifta vid ombyggen.
- **#265** B174: falska "Quality Gate flaggade något"-varningen —
  rotorsaken var stdout-brus före bridge-JSON; nu sentinel-kontrakt
  (`OPENCLAW_BRIDGE_JSON:`-rad) + robust bakifrån-parsning.
- **#266** prune-on-dev-start: `npm run dev` städar gamla preview-byggen
  automatiskt (port-guard + pointer-skydd + feltolerant, kill-switch
  `VIEWSER_PRUNE_ON_DEV_START=0`).

**Eval-resultat:** real-LLM Golden Path 2026-06-10 = **8.2/10** totalt
(alla 4 case pass, gate go); deterministisk baseline 7.75. Dominant problem
var `contact` i alla fyra case — det styrde B166-prioriteringen.
Operatörens manuella klick-checkar bekräftade live: section_add synlig ✓,
preview byter version ✓ (B163), tema → bara `--primary` (stylist-scope-
fråga), hero-drift (→B173 fixad), falsk QG-varning (→B174 fixad),
skämt byggde version (→#262 fixad).

**Riktning (icke förhandlingsbar):** OpenClaw är en conductor/bridge på den
befintliga in-repo-motorn — inte en ny parallell motor, inte extern Docker/
Gateway i nuvarande fas, inte fri filpatch. In-repo-källan ENBART
(`packages/generation/orchestration/openclaw/`, `scripts/run_openclaw_followup.py`,
`scripts/verify_openclaw.py`, `apps/viewser/lib/openclaw-runner.ts`,
`apps/viewser/app/api/prompt/route.ts`). Plan:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](heavy-llm-flow/openclaw-2.0-conductor.md).
`sajtmaskin` + `C:\Users\jakem\Desktop\openclaw` = strikt read-only (AGENTS.md).

**Operatörsbeslut tagna i natt:** Vercel Sandbox = primär preview-adapter
lokalt; eval-först-strategin genomförd; prod-env väntar på main-sync.

**Nästa prioriteringar (för nästa orchestrator, i ordning):**

1. **Main-sync-beslut (operatören):** `jakob-be` (16 PRs före `main`) är
   helgrön och stabil — bra fönster. Efter sync: Vercel-agenten sätter
   prod-env (`VIEWSER_ALLOWED_HOSTS` = prod-aliaset; sandbox-flaggan
   ENDAST bakom Deployment Protection).
2. **F1 slice 3 — section_builder-dispatch (IMPLEMENTERAD på en cloud-grind
   PR-branch, väntar review/merge):** `run_followup_chain` väljer numera
   section-add via den klassade rollen (`skill_for_edit_kind ==
   SECTION_ADD_SKILL`, läser `RoleContract.skill`) i stället för rå `editKind`
   — beteende-ekvivalent, bara section_add berörs. `ConversationDecision` bär
   en `expectsAnswer`-signal (Scout-fynd #262) som /api/prompt +
   use-followup-build + FloatingChat kortsluter answer-only på, och FloatingChat
   renderar en ärlig roll-rad ur `payload.conversation`. Stylist/copy lämnades
   medvetet utanför (egna slices; ekvivalensbeviset gäller bara section_add).
   Dialog-vägens answer-only-hantering landade redan i #270 (use-followup-build
   ytlägger svaret i stället för "HTTP 200 misslyckades"); roll-raden visas
   ENDAST i FloatingChat (dialog-vägen saknar meddelandetråd). OBS koordinering:
   Christophers #269 (toolIntent-pilot, UI-halva) rör samma söm
   (use-followup-build + /api/prompt-dispatch) — denna slice höll
   use-followup-build-ändringen minimal/additiv — se "Öppna PR" nedan.
3. **Stylist-scope-beslut (operatören):** "gör sajten mörkblå" mappar
   bara `--primary` — beslutsunderlag med tre optioner ligger i
   `docs/heavy-llm-flow/openclaw-2.0-conductor.md` (slice 3-kandidat;
   option b möjliggjordes av #262:s answer-only-väg).
4. **Tier 2 LANDAD (PR #276, ADR 0041):** opt-in warm-sandbox-
   återanvändning (`VIEWSER_SANDBOX_REUSE=1` i `apps/viewser/.env.local`,
   default AV → noll regression), inkl. route-grinden (stop-before-create
   hoppas i reuse-läge), namn-kollisionsstrategin (ren miss →
   deterministiskt namn; funnen-men-död/transient fel → tidsstämplat,
   Vercel-bot-fyndet fixat i `a5f66c6`) och typad `reused`-flagga i
   timings. KVAR (operatören): live-mätning med flaggan på — kör en
   följdprompt två gånger, bekräfta `reused: true` utan `createMs`.
5. **Starter-hygien-slice (kräver operatörs-OK, plattform-pins):**
   `engines`-fält (Node, matcha Vercels 24), `allowScripts`-godkännande
   för sharp (npm-varningar i genererade sajter), spåra transitiva
   msw/unrs-resolver, samt beslut om docs-base/portfolio-base ska mappas
   in i runtime (idag medvetet omappade i scaffold-kontraktet).
6. **Komponent-medvetet LLM-flöde via shadcn (operatörsprio 2026-06-10):**
   starters vendorerar redan shadcn-komponenter (CLI i devDependencies,
   `components.json` per starter), men brief/plan/codegen-kedjan är inte
   komponent-medveten — LLM-flödet kan inte välja/referera komponenter.
   Slice: exponera komponentkatalogen för kedjan (registry/manifest +
   governance-mappning). **Design-noten är skriven:**
   [`docs/heavy-llm-flow/komponentkatalog-design-not.md`](heavy-llm-flow/komponentkatalog-design-not.md)
   (tre lager: starter-manifest → capability-mappning → roll-uppslag via
   shadcn-MCP). **Lager 1+2 LANDADE via PR #275** (ADR 0040): manifest per
   starter + `--check`-synk, additivt components-fält i capability-map v3
   med gate-korskontroll, pilot faq-section → accordion (vendorerad nativ
   accordion i marketing-base, noll nya beroenden), termerna registrerade
   (naming-dictionary v30). **Lager 3 (roll-uppslag via shadcn-MCP) är nu
   HELT oblockerat** — båda förutsättningarna klara (roll-dispatch #274 +
   katalogen #275). OBS: ADR 0040 är taget — nästa lediga är 0041
   (Tier 2-slicen i cloud-grind är instruerad att använda 0041).
7. **Begreppssession (operatör + agent):** blueprint/variant/dossier/DNA
   m.fl. överlappar i dag och ingen av termerna finns i naming-dictionaryn.
   Utgå från ADR 0036 (blueprint-and-router-vocabulary), begrepps-PR:en
   #246 och `governance/policies/naming-dictionary.v1.json`; utfall =
   ADR + dictionary-poster. Underlag finns nu som interaktiva canvases i
   `docs/canvases/` (begreppskarta + openclaw-flöde, Steward-ägda; se
   `docs/canvases/README.md`).

**Öppna blockers / att-göra:**

- **Manuella klick-checkar PENSIONERADE (operatörsbeslut 2026-06-10):**
  i stället för manuell verifiering är beteendena nu test-låsta —
  #228 Ändra→steg-hopp via
  `tests/test_viewser_wizard.py::test_review_summary_andra_links_are_wired_to_step_jump`,
  #245/#249 modul-dialogens ärliga synlighets-badges via
  `tests/test_viewser_floating_chat.py::test_add_module_dialog_renders_honest_effect_badges`
  (+ befintliga katalog-ärlighetslåset). Det manuella 1–10-scorecardet i
  Backoffice är en VALFRI journalfunktion (inget i motorn/evals-gaten
  beror på att det fylls i — kvalitetssignalen är den automatiska
  Golden Path-evalen); funktionen finns kvar men nags inte längre.
  Öppettider-checken var redan GODKÄND.
- **Operatören bör starta om sin dev-server** så nattens fixar gäller
  (B163/B164/B174-kedjan + prune-on-dev-start aktiveras vid omstart).
- Branch-rester för operatörsbeslut (oförändrat): Christophers stängda
  `feat/viewser-ui-overhaul`/`feat/viewser-router-decision-readiness`,
  `cursor/gap-3a-offer-service-guard`, `cursor/dossier-intake-v11-review-895d`,
  `feat/kor-5-repair-pass`, `cursor/preview-runtime-adapters` (avsiktlig
  snapshot). Lokala `rescue/openclaw-f1-d76ad9c` är RADERAD (innehållet
  verifierat landat via #259+#260).
- B155 hålls öppen (kvarvarande targets: tjänst-label-rename, bredare
  multi-field, route/element-targeting). B169-uppföljning för Christopher
  noterad i msg-0061.
- **Delade canvases:** efter pull av canvas-PR:en kör båda operatörerna
  `python scripts/sync_canvases.py` en gång så att begreppskartan och
  openclaw-flödet dyker upp i Cursor (rutin i `docs/canvases/README.md`).

Last verified state: `c1b9c43`+granskningsfixar (2026-06-10 ~14:45 UTC+2).
Extern granskning (read-only-agent F1–F10 + GPT-agent) processad: SEX
buggar fixade + stängda i samma commit-svit — B186 (baseRunId vinner över
latest i brief-reuse), B187 (frågeformade section_add-edits byggde inte:
infinitivverb saknades i routerns `_ADD_VERBS`), B188 (cross-site-guard
hoppades över vid overifierbar baseRunId), B189 (removed-notes-guard
substring → onödig regen), B190 (route-gaten hedrar nu `expectsAnswer`),
B191 (`_metadata_int` "--5"-krasch). B192 ÖPPEN (dialog-vägens
answer-only renderas rött — medvetet deferrad bakom Christophers
#269-rebase, samma fil). Avfärdade med motivering: F1 (medveten
substring-design), F6 (latent, täcks av test vid PR), F7 (by design),
F9 (sync_canvases --check är lokal, ej i CI — verifierat). Granskningen
arkiverad i operatörens `övrigt/`. Tidigare i dag: PR #276 (Tier 2
warm-sandbox-reuse, ADR 0041, inkl. babysit-fix `a5f66c6`).
Tidigare i dag: #274 (roll-dispatch), #275 (komponentkatalog lager 1+2,
ADR 0040), hygien-fix `58aec36` (add-module-låsen → egen testfil),
design-notens lager 3 har konceptbevis (operatörens shadcn-mcp-lab) +
hård MCP-separationsregel. Christopher aviserad `msg-0063`/`msg-0064`.
Ev. pågående: lager 3-slicen (komponent-förslag, ADR 0042) om operatören
skickat prompten. Dagens facit efter main-syncen (`6ea53c0`, pre-sync
sparad som `backup_150_BRA`):

- **#270** slice 3-delar: B178 stängd (ociterad demonstrativ fri-text-replace
  → ärlig no-op i stället för falsk "Klart!"), B155-framsteg (ankar-ledd
  ociterad replace appliceras), B177 stängd (variantfont via `<link>` i
  layout-head i stället för bundle-ignorerad CSS-import), answer-only-svar
  i dialoger (use-followup-build).
- **#271** backoffice-grafvyn Arrow-krasch fixad (sourceFileCount
  int|None i stället för blandad int/tomsträng).
- **#272** delade canvases (begreppskarta + openclaw-flöde, Steward-ägda)
  + sync-skript + steward-workflow-steg. Operatörens lokala kopior var
  byte-identiska och städades; `sync_canvases.py` körd (redan i synk).
  Canvas-worktreet `sajtbyggaren-wt-canvases` borttaget.
- **#273** B183–B185 stängda (failed-run som följdbas, borttagna
  operator-noter i brief-reuse, cross-site baseRunId); B186 öppen
  (brief-reuse nycklar på senaste run, inte explicit baseRunId).

Alla mergade brancher städade (lokalt + remote). **Main-sync nr 2 GJORD
2026-06-10 ~12:10** (operatörsbeslut): `main` fast-forwardad till `jakob-be`
igen — förmiddagens fyra merges (#270–#273) + docs-commits (canvases-bump,
design-not med alla 4 beslutspunkter avgjorda, inbox msg-0063) är nu på
`main`. Tom diff `main↔jakob-be` verifierad. OBS: steward-auto-bump-
workflowet på `main` kan lägga en auto-commit (canvas-fakta/HEAD-bump) —
nästa agent ff-synkar i så fall `jakob-be` mot den. Roll-dispatch-slicen
(köpunkt 2) kör i cloud-grind (operatörens GO ~12:00; justeringar skickade:
färsk bas, None-säker skill-lookup, minimal use-followup-build-yta).
Christopher aviserad via inbox `msg-0063` (#269-rebase + ordning +
utbrytningsförslag). Öppna buggar kvar: B155 (kvarvarande targets), B186 +
misplaced-poster som väntar Steward-flytt (B176–B179-rundan, B183–B185).

## Öppna PR att känna till

- **#269** (`christopher → jakob-be`): toolIntent v1-pilot (strukturerad
  specialist-intent från färgväljaren, UI-halva). **Vänta med merge:** (a) PR:en
  är hela `christopher`-branchen (23 filer, +2805 — bär även en hel
  preview-inspector-lane + playwright-beroende utöver de ~4 toolIntent-filerna),
  (b) den blev CONFLICTING efter förmiddagens merges (#272 rör samma
  `docs/agent-inbox.jsonl`, #270 rör samma `use-followup-build.ts`) och behöver
  Christophers rebase, (c) backend-halvan (schema-fält + dispatch-bypass i
  `/api/prompt`) finns inte än och samma söm byggs JUST NU av
  roll-dispatch-slicen i cloud-grind — landa den först, sedan rebasar
  Christopher och toolIntent-dispatchen läggs OVANPÅ roll-dispatchen
  (toolIntent = deterministisk genväg in i samma specialist-/rollmappning).
- **#156** (`feat/live-preview → jakob-be`): hostad `/live`-loop. **Parkerad pga säkerhet**
  (publik POST utan auth/rate-limit kan starta sandboxar). Behålls som arkitektur-referens;
  görs om på färsk bas med auth/rate-limit designat från start när runtime-spåret väljs aktivt.
  OBS: Vercel-botens accepterade fixar ligger på branchen (ofarligt; lärdomen
  `Sandbox.get({resume:false})` är värdefull för Tier 2).

Christophers UI-arbete sker på `christopher` (gamla `christopher-ui` är fryst legacy).

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Efter varje merge/sync som ändrar nästa agents
arbete: bumpa SHA:n på "Last verified state"-raden, uppdatera de tre
prioriteringarna + blockers, och flytta utgånget innehåll till arkivet (se hygien-regeln). Steward
post-push-verifierar `origin`-SHA, `git status` och `python scripts/focus_check.py`.
Uppdatera inte för ren mikrostatus som inte ändrar nästa agents arbete.

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`; Christopher på `christopher`. `main` är
  canonical/sanningsbranch.
- PR från arbets-branch → `main` när "en ny officiell version ska in" (beslut
  per leveransfönster, ingen cadence). Efter merge synkas arbets-branchen mot
  `origin/main`.
- Detaljer: [`governance/rules/04-branch-and-team.md`](../governance/rules/04-branch-and-team.md).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) ("Standard loop"). Kort: Scout
vid behov → arbete på arbets-branch → guards gröna → push → vid behov PR mot
`main` → post-merge-sync. Orkestrering över längre pass:
[`docs/orchestrator-playbook.md`](orchestrator-playbook.md).

Operatörspreferens: svenska, kort och koncist, gärna matris/tabell. Förklara
dev-uttryck med korta parenteser första gången per konversation. Mönstret i
[`governance/rules/01-language-and-reply.md`](../governance/rules/01-language-and-reply.md).

## Arkiv

Historiska statusblock + checkpoint-kedjan ligger i arkivet:

- [`docs/archive/current-focus-2026-06-08-pre-slim.md`](archive/current-focus-2026-06-08-pre-slim.md)
  (full snapshot precis före denna slimning).
- [`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md)
  (äldre checkpoint-kedja).

För commit-historik: `git log --oneline origin/main` eller
`git log --oneline origin/jakob-be`.

## Föregående checkpoint

Tidigare "Last verified state"-block och äldre "Current objective"-block är
flyttade till arkivet ovan (per `governance/rules/07-docs-focus-handoff.md`).
Auto-bump-verktyget lägger nya korta checkpoint-block här vid main-sync; håll
högst ett kvar och flytta resten till arkivet.

### 2026-06-10 UTC — current-focus.md före `3674475`

Last verified state: `e6a06a5` (2026-06-10 natt UTC+2; `main` = `jakob-be` =
`e6a06a5` efter PR #252-sync — merge-tåget med 15 PR:ar #238-#251 + #225
(synlig section_add ADR 0038, golden-path-smoke, auto_prune opt-in,
recommendedPages-API m.m.) togs över till `main` som ren övertagning, tom
diff main↔jakob-be verifierad, CI grönt). Därefter landade #255 på `main`
(docs-dedupe, `7486145`) och nattens fem PR:ar #254/#256/#257/#259/#260 på
`jakob-be`. Äldre checkpoint-kedja: arkivet ovan + `git log --follow`.
