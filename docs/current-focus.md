# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-10, natt — MAIN-SYNC KLAR via PR #252)

**Git:** `main = jakob-be = e6a06a5` (identiska träd, verifierat med tom diff).
PR #252 mergade hela merge-tåget (15 PRs) till `main` som ren övertagning
(merge commit, main var förfader — ingen squash-divergens). Steward-auto
bumpade docs på main; `jakob-be` fast-forwardades och pushades.
I går kväll landade PR:arna på `jakob-be` (merge-tåg, ett i taget, alla guards + CI gröna):

- **#238** `refactor(builder)`: render helpers → `packages/generation/build/render_helpers.py`
  (sista megafil-slicen, byte-paritet verifierad).
- **#239** `feat(wizard)`: branschanpassat sidrutnät (bilverkstad får inte meny-förslag).
- **#240** `feat(builder)`: **SYNLIG `section_add`** (ADR 0038, naming v27 Mounted Section):
  `directives.mountedSections` på Project Input + render-seam i `render_home`. Skiva 1:
  `hours` renderas inline på LSB-home med position top/bottom ("överst"/"längst ner");
  faq/team behåller egen-route-vägen. Honesty-gates: registrerad renderare + grundat
  innehåll + ej dubblett + allowlist.
- **#241-#244** test/QG-paket: contact-CTA-routes, followup-versionering, golden-path-smoke
  (riktiga svenska prompts + exakta statusar), placeholder-scan-härdning. #243/#244
  review-fixades FÖRE merge efter extern buggranskning.
- **#245** `feat(builder)`: AddModuleDialog ärliga synlighets-badges (UI-halvan av #240).
- **#246** docs/governance: `Golden Path` registrerad som canonical term (ADR 0039, naming
  v28) + begreppskarta + backoffice-statusvy; rebasad + versionsfixad (v27-kollision med
  #240) före merge.
- **#247** `fix(wizard)`: canonical capability-sluggar (menu/team-section/reviews/gallery) +
  scaffold-nyans i öppettider-badgen (Christophers svar på inbox msg-0057).
- **#248** `fix(builder)`: Codex-review-fixar — (1) intent-gate: bara section_add SKAPAR
  inline-placering, component_add kan högst BEVARA; (2) render-time-allowlist
  (`_INLINE_SECTION_ALLOWLIST`, paritetslåst mot resolverns); (3) `{company}`-false-positive
  borta ur placeholder-scan; (4) golden-path-smoke kräver route-scan exakt `ok`.

Plus inbox-trafik: msg-0057 (svar till Christopher: punkt 1 tas först, canonical sluggar,
section_add synlig) + hans ack/uppföljning (#247). Sync `jakob-be → main` är **GENOMFÖRD**
(operatörsbeslut 2026-06-10, PR #252) — Christophers action: synka `christopher` mot
`origin/main` (inbox msg-0059).

**Riktning (icke förhandlingsbar):** OpenClaw är en conductor/bridge på den
befintliga in-repo-motorn — inte en ny parallell motor, inte extern Docker/
Gateway i nuvarande fas, inte fri filpatch. In-repo-källan ENBART
(`packages/generation/orchestration/openclaw/`, `scripts/run_openclaw_followup.py`,
`scripts/verify_openclaw.py`, `apps/viewser/lib/openclaw-runner.ts`,
`apps/viewser/app/api/prompt/route.ts`). Plan:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](heavy-llm-flow/openclaw-2.0-conductor.md).
`sajtmaskin` + `C:\Users\jakem\Desktop\openclaw` = strikt read-only (AGENTS.md).

**Live-loop-bevis (2026-06-09): GRÖNT.** Manuell /studio-körning på `bil-ab-17331b`:
följdprompt "gör sajten grönvit" → ny version (v6→v9), bygge + alla quality gates ok, och
preview-iframen renderade automatiskt nya versionen utan krasch (local-next). Data-/
versionslagret grönt (`themeApplied: true`, stabilt `projectId`). **Caveat:** färgskiftet
syntes knappt — sajten var redan grön (lågkontrast-testfall, ingen loop-bugg). Verifiera
tema-applicering med en kontrastfärg (t.ex. "gör sajten mörkblå") i eval-fasen.

**Nästa prioriteringar (operatörsbeslut 2026-06-10: eval-runda FÖRST, sedan agentroller):**

1. **Golden Path-eval på 4 branscher + manuell score (extern granskning + prio-beslut):**
   elektriker, frisör, naprapat, keramik-shop. Kör
   `scripts/run_golden_path_eval.py --mode deterministic` + `scripts/run_eval_suite.py quick`,
   sätt manuell 1–10 i Backoffice. Inkludera kontrastfärg-testet ("gör sajten mörkblå") OCH
   den manuella section_add-checken: "lägg till en öppettider-sektion överst" på LSB-sajt med
   riktiga öppettider → block efter hero + ärlig toast (deterministiskt bevisat; klicket kvar).
   Utfallet styr om nästa sprint blir copy/design-output, följdprompt-effekt eller motor.
2. **OpenClaw 2.0 / agentroller i llm-flödet — AVBLOCKAT:** F1-readiness var gated på
   synlig `section_add`, som nu är inne (#240/#248). Plan:
   `docs/heavy-llm-flow/openclaw-2.0-conductor.md` + `openclaw-f1-readiness.md`.
   Strukturera rollerna (router/section_builder/stylist/copy) på den befintliga motorn.
   Detta är också vägen till operatörens "smarta chat" (skämt/omdöme/3d-banner =
   messageKind-routing i dirigenten, inte ett separat projekt).
3. **Punkt 2 till Christopher (businessFamily-ankare):** governance-slice (ADR +
   family-fält per kategori i discovery-taxonomy) så UI:ts 8 familjer slutar vara UI-påhitt.
   (Punkt 1 LEVERERAD: #251 exponerar `recommendedPages` i `/api/discovery-options`;
   taxonomin saknar `recommendedCapabilities` — eget taxonomi-fält om det önskas, se
   msg-0058.) Därefter: section_add skiva 2+ (fler typer/routes/scaffolds), fler starters
   i runtime, följdprompt copy literal-replace.
   Två cloud-agent-prompter är skrivna och redo (backoffice-grind A/B + Vercel-hosted
   sandbox-preview) — se chatlogg 2026-06-09 sen kväll.

**Öppna blockers / att-göra:**

- **Manuella klick-checkar kvar:** #228 review-summary (Ändra→steg-hopp) + #240 öppettider-
  inline i /studio + #245/#249 modul-dialogen (badges, en-modul-per-bygge, inaktiva sidzoner).
  Täcks inte av automatiska tester.
- Följdprompt copy: "ändra X till Y" parafraserar i stället för literal replace; ärlig
  no-op-feedback saknas (UI). Rotorsak i docs/gaps/GAP-followup-prompt-content-passthrough.md.
- Branch-städning gjord (21 mergade/täckta remote-brancher raderade). Kvar för operatörsbeslut:
  `feat/viewser-ui-overhaul`/`feat/viewser-router-decision-readiness` (Christophers stängda,
  ej mergade), `cursor/gap-3a-offer-service-guard`, `cursor/dossier-intake-v11-review-895d`,
  `feat/kor-5-repair-pass` (ingen PR), `cursor/preview-runtime-adapters` (avsiktlig snapshot).

**Cloud-lanes (status):**

| Lane | Vad | Status |
| --- | --- | --- |
| A — docs-honesty-cleanup | architecture/glossary-honesty + arkivflytt + frontmatter + checker | **inne** på `jakob-be` via merge `76b5ae4` |
| B — FloatingChat-split | split `floating-chat.tsx` → syskonmoduler (behavior-preserving) | **inne** på `jakob-be` via #217 (`2ffce4a`); #216 mot `christopher` redundant |
| C — backend-refaktorplan | megafil-refaktorplan (docs-only) | **inne** via #215 (`2dadf09`) — ingen refaktor körd, gated |
| Regel-konsolidering | Cursor-regler 29→12 (docs/governance) | **inne** via #218 (`11b4f19`); hygien-regeln bor nu i `governance/rules/07-docs-focus-handoff.md` |

**OpenClaw F1-readiness (separat lokal lane):** readiness-/install-planen har
landat plan-only och gated i `docs/heavy-llm-flow/openclaw-f1-readiness.md`
(`6e08ce9`; ingen runtime-kod; gated på synlig section_add + refaktor-beslut).

Last verified state: `e6a06a5` (2026-06-10 natt UTC+2; `main` = `jakob-be` = `e6a06a5`
efter PR #252-sync + steward-auto-docs-bump + jakob-be fast-forward. Tom diff
main↔jakob-be verifierad. CI grönt på #252: governance, builder-smoke, ai-bug-review).
Nya PRs sedan föregående checkpoint: PR #252 — sync(jakob-be->main): merge-taget
2026-06-09/10 - synlig section_add (ADR 0038), golden-path-smoke, auto_prune opt-in,
recommendedPages-API m.m. (15 PRs).

## Öppna PR att känna till

- **#156** (`feat/live-preview → jakob-be`): hostad `/live`-loop. **Parkerad pga säkerhet**
  (publik POST utan auth/rate-limit kan starta sandboxar). Behålls som arkitektur-referens;
  görs om på färsk bas med auth/rate-limit designat från start när runtime-spåret väljs aktivt.
- **#253** (`cursor/dev-env-setup-2e12`): docs-PR från cloud-lane (Cloud VM
  preview-mode env-override-not). Granskas/mergas när cloud-agenterna landar sina lanes.

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

### 2026-06-09 UTC — current-focus.md före `79bedef`

Last verified state: `79bedef` (2026-06-10 strax efter midnatt UTC+2, `jakob-be` HEAD —
kvällens/nattens merge-tåg, FEMTON PR:ar: #238 (`d7b87a4`), #239 (`924f1d3`),
#241 (`8faeb90`), #242 (`b5d6ec2`), #243 (`e63d46d`), #244 (`a645699`), #240 (`72f5563`),
#245 (`4b85469`), #246 (`647eb9e`), #247 (`c67a7af`), #248 (`16e3ae6`),
#249 (`b03770f`, granskningsrunda 2), #225 (`9dce32a`, testsvit-split 186=186),
#250 (`dbfb905`, auto_prune default OFF i hela API-kedjan — #237-fällan stängd) och
#251 (`79bedef`, recommendedPages i /api/discovery-options, msg-0056 punkt 1 levererad);
`main` = `16278c1`, sync till main väntar operatörsbeslut — deltat är MYCKET STORT,
en main-sync bör övervägas snarast). Post-merge-sanity: governance 19/19, rules_sync OK,
ruff 0, sviter gröna. Encoding-skan repo-brett (995 textfiler): inga UTF-8-fel/BOM/mojibake.
