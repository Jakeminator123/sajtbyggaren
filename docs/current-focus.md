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
2. **F1 slice 3 — section_builder-dispatch:** rollvalet ska styra
   skill/prompt i kedjan (inte bara metadata), ärlig roll-rad i
   FloatingChat, dialog-vägens konversationshantering
   (use-followup-build visar generiskt fel för answer-only idag), samt
   `expectsAnswer`-signal i decision-payloaden (Scout-fynd #262).
3. **Stylist-scope-beslut (operatören):** "gör sajten mörkblå" mappar
   bara `--primary` — beslutsunderlag med tre optioner ligger i
   `docs/heavy-llm-flow/openclaw-2.0-conductor.md` (slice 3-kandidat;
   option b möjliggjordes av #262:s answer-only-väg).
4. **Sandbox-mätning + Tier 2:** mät #263:s verkliga tidsvinst (jämför
   `timings` med/utan `VIEWSER_SANDBOX_UPLOAD_BUILT=0`); därefter Tier 2
   (bas-snapshot P3 + sandbox-återanvändning — kräver liten ADR; lärdom
   från #156-boten: `Sandbox.get()` behöver `resume: false` för att inte
   återstarta utgångna sandboxar).
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
   governance-mappning). Börja med kort design-not innan bygge.
7. **Begreppssession (operatör + agent):** blueprint/variant/dossier/DNA
   m.fl. överlappar i dag och ingen av termerna finns i naming-dictionaryn.
   Utgå från ADR 0036 (blueprint-and-router-vocabulary), begrepps-PR:en
   #246 och `governance/policies/naming-dictionary.v1.json`; utfall =
   ADR + dictionary-poster.

**Öppna blockers / att-göra:**

- **Manuella klick-checkar kvar (operatören):** #228 review-summary
  (Ändra→steg-hopp) + #245/#249 modul-dialogen visuellt + manuell
  1–10-score i Backoffice (Idag-vyn). Öppettider-checken är GODKÄND.
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

Last verified state: `6ea53c0` (2026-06-10 ~10:00 UTC+2; `main = jakob-be`
efter main-sync). Vägen hit: PR #268 (`2b970d9`) landade B180 (brief
carry-forward på följdbyggen, slut på copy-drift vid restyle), B181
(hälsningsfras kapar inte längre konversationsklassningen), B182
(OpenClaw-beslut auto-resolvar senaste run när baseRunId saknas) + snabb
core-testlane (`python -m pytest -m core`, ~1 min; `scripts/review_check.py
--core`) och `docs/testing.md`. Därefter main-sync (`6ea53c0`): `jakob-be`
tog över `main` (mains 3 docs-commits absorberade, AGENTS-dubblett borttagen
per #255, ff → tom diff). Pre-sync sparad som `backup_150_BRA`.
Städat tidigare: worktree `sajtbyggaren-wt-fixes` + PR-branchen + lokala
`feat/live-preview` (allt unikt innehåll redan landat).
Öppna buggar kvar: B177 (font-@import i byggd CSS), B178 (falsk framgång
vid icke-applicerad fri-text-ändring, kopplad B155), B155 (literal-replace-
targets). B176/B179 fixade i morgonpasset.

## Öppna PR att känna till

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
