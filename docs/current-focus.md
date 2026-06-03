# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.
Startpromptar och rollgränser finns i
[`docs/agent-prompts.md`](agent-prompts.md).

## Current objective (2026-06-03 natt — kor-3a/4a/3b inne; våg 2 landar)

`jakob-be` @ `2033282`, rent träd. **Denna session mergade:** #179 (kor-3a:
section-treatments Python→JSON, en deklarativ källa), #180 (kor-4a: deterministisk
quality critic v0 — non-blocking, ingen LLM), och #183 (kor-3a follow-up: flyttar
section-treatments-loadern till `orchestration/` så `planning` inte importerar
`build` — Pushvakt P1; repo-boundaries v10 + fail-closed på trasig JSON + boundary-test
som scannar riktiga imports), och #184 (kor-3b: visualDirection väljer section-treatment,
Option A — verifierad mot kombinerat träd med #183, alla paritets-/pick-tester gröna), och
#186 (CLI-wiring: kor-4a critic + kor-7 follow-up-kedja i build-vägen + E2E).
**Ärlighet:** kor-4a-critic **körs nu i CLI-builds** (#186 trådar in `generation_package` →
`critic` ifylls i quality-result.json; var alltid null). KVAR att wira: `/api/prompt`
(Christopher) + `dev_generate`. kor-3b är aktiv bara när blueprintens `visualDirection` är
satt (annars byte-paritet mot kor-3a). Repair (kor-5) fortsatt dormant (#185).
**Status cloud-builders:** kor-3b INNE (#184); CLI-wiring INNE (#186); kor-5 INNE (#185,
dormant library — repair aktiveras bara när en rerender-callback injiceras). Reviewer-fynd
åtgärdade vid merge (brief-schemavalidering+rollback, "bara befintliga fält", rerender try/except,
blueprintPasses, doc-match, typfix `_combine_status` av orchestrator). **Kvar till rerender-wiring-slicen:**
post-repair-critic ska skrivas till trace FÖRE `critic.evaluated` (annars pre-repair-score i trace
vs post-repair i quality-result.json); per-entry `success` ska bli `false`/ej-materialiserad när rerender failar.
**Justerad ordning (orchestrator + coach, natt):** (1) ✓ kor-3b (#184) → (2) ✓ CLI-wiring inne
(#186): kor-4a critic + kor-7 follow-up-kedja i build-vägen + E2E; KVAR `/api/prompt` +
routerDecision (Christopher #177) → (3) read-only baseline-eval
→ (4) kor-5 (library → wira in) → (5) kor-o2 OpenClaw Core V0 (read-only, spec:as parallellt)
→ (6) design-system-ADR + `next-shadcn-tailwind`-starter *om evalen visar att gapet är
visuellt* (annars copy/trust/kontakt-ärlighet först) → (7) kor-4b verifier + kor-6b
router-fallback. **Princip:** ingen ny LLM-slice utan inkopplingsplan — varje slice når
en användarväg eller taggas dormant + får en wiring-follow-up (#178-trion filad så).
**Öppet (ej vår lane):** #177 (Christopher, väntar på routerDecision i `/api/prompt`),
#181/#182 (docs→main, cloud-env), #156 (parkerad). Main-sync = operatörsbeslut.

### Follow-ups filade (2026-06-03 natt)

- **#186-härdning** (post-merge, reviewer-fynd): validera `--base-run-id` mot siteId (annars
  context från fel sajt); bas-run-val ska vara aktiv/senaste `ok|degraded` med kompletta
  artefakter (ej nyaste mtime oavsett status); lägg `--prompt-inputs-dir`-flagga; överväg
  `applied`→`projectInputApplied`/separat `visibleEffectApplied` i CLI-svaret.
- **kor-5 (#185)** — revisionsrunda hos D före merge: skärp "bara befintliga fält", wrappa
  `rerender` i try/except → partial/no-fix, uppdatera kor-5-doc (high/`trust_missing`),
  ev. `passes`→`blueprintPasses`, rebase ovanpå #186 (delar `repair/orchestration.py`).
- **Megafil-refaktor** (backend, behavior-preserving slices, EFTER wiring/eval):
  `renderers.py` 5518, `build_site.py` 4816, `prompt_to_project_input.py` 3535.
- **Baseline-eval** (read-only, 4 prompter) — bevisa var upplevd kvalitet brister
  (copy/trust/kontakt vs visuellt) innan design-system-investering.
- **Platform-version-baseline** — steg 1-3 INNE på branch (DRAFT-PR mot `jakob-be`,
  `cursor/platform-version-baseline-5e94`): ADR 0037 + `governance/policies/platform-baseline.v1.json`
  (+ schema) som EN sanningskälla för Node/Next/React/UI/tooling-pins, grundad i nuvarande
  viewser+starters-pins, + drift-checker `scripts/check_platform_baseline.py --check/--fix`
  (wirad i guard-sviten + README). `--check` är grön nu (enforced pins uniforma) och failar
  deterministiskt vid drift; engines/volta + `@types/node` `^20`->`^24` + varierande pins
  markerade `pendingPropagation`. Kvar är steg 4 (granskat `--fix` operatören kör senare,
  rör `apps/viewser/package.json` = Christophers lane + starters; kräver operatörs-OK +
  inbox-notis till `christopher-ui`). Ingen workspace/catalog (ADR 0030). Möjliggör
  shadcn/lucide kontrollerat (codegen-allowlist + pinnade versioner).

## Current objective (2026-06-03 kväll — follow-up-bryggan startad: kor-7b inne)

`jakob-be` @ `f4d2a1e`, rent träd. Heavy-LLM-kedjan är synlig (kor-1b→1c→2→7a→1c-copy inne).
**Follow-up-bryggan KOMPLETT + STABILISERAD: 7b ✓ 7c ✓ 7d ✓ + KÖR-7-STAB ✓ (#171/#174/#175/#176/#178).**
En capability-backad följdprompt går hela vägen router→context→patch→apply→targeted render→
current.json-swap→ärlig preview-refresh. **P1 STÄNGD (#178):** apply säkrar nu dossiern i
selectedDossiers.required via filter_capabilities → codegen monterar den. #176-P2:or fixade
(ingen build på applied=false, diff mot aktiv build, route→id via routePlan). **INTEGRATION-GAP:**
bryggan är library-komplett + test-verifierad men INTE inkopplad i `/api/prompt`/CLI — Viewser-följdprompt
använder fortfarande gamla copyDirective-vägen. Nästa riktiga milstolpe = wira chain:en i `/api/prompt`.
**Nästa:** handoff till ny orchestrator (UI-E2E blockerad tills wiringen). Coach-ordning sedan: baseline-eval → #177/routerDecision → kor-4a →
ADR copy_change/inline → kor-o2 → 3a/3b → 5. Main-sync väntar tills STAB + #177 + E2E klara.
**Tidigare (kor-7c-detalj):** kor-7c (#175) applicerar capability-backade
`component_add` → `requestedCapabilities` i ny immutabel v<N+1> (ingen build/current.json).
`copy_change` (rubrik) + inline-komponenter rapporteras `unmapped` (all-or-nothing) → kräver
**ADR/nytt directive-fält** för att helt stänga B155. Nästa: kor-7d (build + current.json-swap).
**Follow-up-bryggan startad** (coach-omprioriterad före kor-4a för att stänga B155): `kor-7b`
artifact patch planner (dry-run) mergad (#171). Även mergat denna runda: #170 (B86 npm-timeout
env-override) och #169 (Christophers UI-överhalning reconcilad på jakob-be runtime — hans lane).
Vercel auto-deploy begränsad till `jakob-be`/`christopher-ui`/`main` (denylist i
`apps/viewser/vercel.json`). `kor-o1` OpenClaw Core-kontrakt skrivet (design); coachens körbara
`openclaw-mvp/`-spike hålls lokal/gitignored tills placeringen är beslutad. Orchestrering +
nästa kort: `docs/heavy-llm-flow/handoff-orchestration.md`.

**Nästa:** follow-up-bryggan `kor-7c` (apply → ny version) → `kor-7d` (targeted rebuild) —
stänger B155. Parallellt (read-only): `kor-o2` OpenClaw Core V0. Därefter `kor-4a` critic →
`3a`/`3b` → `5` → `6b`. Ett steg i taget; operatören mergar med orchestratorn.
**Öppna PR:er (ej vår lane — dokumenterade per focus_check):** #172 (`apps/viewser`, Bug A —
markera stale pending-runs som aborted/`current.json`) och #173 (`apps/viewser`, Bug B — ärligt
layout-no-op-meddelande för follow-ups som inte stöds). Båda Christopher/UI-lane; backend-lanen
mergar dem inte. #156 `/live` parkerad (se nedan).
**Parkerat:** #156 `/live` (P1 security), KÖR-0G renderer naming hygiene (`dossier` =
render-input, ej orchestration `Dossier`), `resume:false`-härdning (apps/viewser),
`jakob-be → main`-sync.

---

## Current objective (2026-06-03 — KÖR-0b state-realign efter heavy-LLM-landning)

Smal Steward-slice (vår lane: docs + governance, ingen `apps/`- eller
`packages/generation/`-kod) som realignar styrning som drev isär när det tunga
LLM-flödet landade. `jakob-be` HEAD = `e30cc15`; `origin/main` = `1d6e069`
(jakob-be 12 commits före, sync = operatörsbeslut). Inne sedan KÖR-0 (#155):

- #160 governance-unblock (heavy-llm-flow-vokabulär allowlistad) — mergad.
- #157 KÖR-1a blueprint schema skeleton (+ ADR 0036) — mergad.
- #159 KÖR-6a deterministisk OpenClaw Router — mergad.
- `docs/heavy-llm-flow/` (README + 00–04 + kor-*-kort + handoff) — inne.

**Vercel-sandbox-adaptern:** verifierad inne + live-bevisad (#146 spike, #147
opt-in-adapter, route-flip i `app/api/preview/[siteId]`). Default kvar `local`;
`vercel-sandbox` är primary/opt-in (ADR 0033). Hostad/publik loop (#156 `/live`)
är parkerad pga säkerhet — separat live-lane, inte vår. Känd P2-härdning kvar:
`resume:false` på stop/get i `vercel-sandbox-runner.ts` (apps/viewser, ej blocker).

**Öppna PR:er nu:** #156 (`/live`, live-lane, parkerad) + #158 (UI-överhalning,
Christopher-lane, split ur stängda #150). Ingen öppen backend/heavy-LLM-PR.

**Nästa:** `kor-1b` (briefModel fyller brief-blueprintet) → `1c → 2 → 4a → 3a →
3b → 5 → 6b → 7a–d`. Orkestrering: `docs/heavy-llm-flow/handoff-orchestration.md`.

---

## Current objective (2026-06-02 NATT — KÖR-0 state alignment / stale-doc cleanup)

Smal Steward-slice (KÖR-0) som städar felpekande/stale styrning INNAN
heavy-LLM-flödet dispatchas — ingen produktfeature. Rör bara docs +
governance-policy + backoffice-copy + en boundary-fix (inga
`packages/generation/`- eller `apps/`-körvägar):

- `governance/policies/preview-runtime-policy.v1.json` (+ schema + nytt
  regressionstest) alignad med ADR 0033: `vercel-sandbox` primär/intended
  primary, men faktisk `default` kvar `local`/local-next tills default-flip
  (Bite C) verifierats, `fly` framtida, `stackblitz` pausad (var: stackblitz
  som default/primary — felpekade agenter mot fel huvudspår).
  `site-plan.schema.json` previewRuntime-enum synkad så `vercel-sandbox`
  accepteras (ingen drift mot policyn).
- Den här filens "öppna PR"-motsägelse löst (se "Pågående/öppna PR:s just nu").
- `docs/handoff.md`: placeholderkontakt-frågan markerad besvarad
  (operatörsval: dölj vid render, ej kräv i wizard).
- `docs/known-issues.md` B155 + `docs/workboard.json`-noteringar uppdaterade
  till faktiskt läge (copyDirective nivå 1-3a är i `main` via PR #153; B157
  nivå 4 Stage A+B landad arkitektoniskt).
- Backoffice: scaffold-skapande skriver kandidat till
  `data/scaffold-candidates/` i stället för canonical `packages/`
  (repo-boundaries); Follow-up-/runtime-copy uppdaterad; System Health får ett
  lättare "Snabb sanity"-läge (focus_check soft-skippar om `gh` saknas) bredvid
  "Kör allt".

Levereras som PR mot `jakob-be`. De TVÅ runtime-buggarna (grå pending-runs;
layout-följdprompt-no-ops) kvarstår oförändrade — egen slice.

## Current objective (2026-06-02 SEN KVÄLL #2 — hela loopen live-bevisad + worktree committad)

Verifieringssession: hela kärnloopen prompt -> preview -> följdprompt -> ny
version är nu LIVE-bevisad end-to-end i vercel-sandbox-läge i Cursor-browsern
(bageriet renderade full-height i preview-iframen med chatten ovanpå; copy-
följdprompten bytte företagsnamnet v6 -> v7 och `current.json` promotades korrekt).
Höjd-fixen i `apps/viewser/components/error-boundary.tsx` (`display:contents`) är
bekräftad nödvändig. Det tidigare okommitterade trädet (fyra ändringsset +
höjd-fix) är nu COMMITTAT + PUSHAT till `jakob-be` som EN sammanhållen commit
(ingen split, ingen PR; full `pytest tests/ -q` ej körd — snabba guards gröna).
Dev-servrar dödade, sandbox stoppad, mergade backup-brancher rensade lokalt;
`docs/heavy-llm-flow/` orörd (annan agent). De TVÅ buggarna kvarstår (A: avbrutna
byggen fastnar grå/`pending`; B: layout-följdprompter är no-ops — bara copy-direktiv
landar synligt). Full detalj överst i [`docs/handoff.md`](handoff.md).

---

## Current objective (2026-06-02 SEN KVÄLL — preview-iframe fixad, två buggar kvar)

Interaktiv felsökningssession: preview-iframen visade ALDRIG sajten trots korrekt
`vercel.run`-URL → rotorsak hittad + fixad (ErrorBoundary-wrappern kollapsade
`.viewer-canvas h-full` till 0 px; fix = `display:contents` i
`apps/viewser/components/error-boundary.tsx`). Sandbox-previewen + reload-loopen är
nu live-verifierad i UI:t. **TVÅ buggar kvar för nästa agent** (full detalj +
start-checklista överst i [`docs/handoff.md`](handoff.md)):
(A) avbrutna följdbyggen fastnar `pending`/grå i Run History och `current.json`
promotas inte → preview visar gammal version; (B) layout-följdprompter ("centrera
hero", "lägg till gallery") är ärliga no-ops (`appliedVisibleEffect:false`) eftersom
deterministisk codegen-v1 inte gör layout-ändringar än (bara copy-direktiv landar
synligt). Allt fortsatt OKOMMITTERAT på `jakob-be` (HEAD `ba11514`), ingen PR.
Dev-servrar dödade.

---

## Current objective (2026-06-02 KVÄLL — Bite C + vercel-sandbox bevisad, OKOMMITTERAT)

En lång interaktiv session byggde + LIVE-verifierade fyra ändringsset som ligger
**okommitterade** i working tree på `jakob-be` (inget pushat, ingen PR):
(1) process-läck-tree-kill-fix, (2) S2 ärlig följdprompt-signal
(`unappliedFollowupIntents`), (3) S3 Fas 1 öppettider i brief, (4) **Bite C —
vercel-sandbox-preview i iframen, end-to-end-bevisad** (`POST /api/preview` i
`vercel-sandbox`-läge → publik `vercel.run`-URL → serverade v2-bagerisajten i
browser). Två Turbopack/term-coverage-buggar hittade + fixade (`turbopack.root` i
`next.config.ts`; allowlist). **Full detalj + commit/PR-plan överst i
[`docs/handoff.md`](handoff.md).**

**Nästa (prioordning):**
1. FULL `pytest tests/ -q` på sammanslaget träd (integrationskoll, ej körd än).
2. Verifiera in-app-iframe-rendering i `vercel-sandbox`-läge + följdprompt-reload till ny version.
3. Dela upp i fyra logiska commits → Scout RO-review → PR (operatörs-OK; `apps/viewser` = Christopher-lane).
4. S3 Fas 2 (wiring i `prompt_to_project_input.py`) — efter att S2 committats.

Default-preview är fortfarande `local-next` (vercel-sandbox EJ flippad). Embeddings PARKERAD.
**Node-städning (Windows):** kör `kill-dev-trees.bat` SOM ADMIN (se AGENTS.md-gotcha).

---

## Current objective (2026-06-02 sen EM — sessionsavslut)

`main` = `1d6e069` (**PR #153 mergad**: copyDirective-modulutbrytning + P2-grounding
+ kontakt-ärlighet). `jakob-be` = `origin/jakob-be`, i sync, rent träd, några docs-
commits före `main` (ADR 0035 + denna städning) — rider med nästa sync-PR. Enda öppna
PR: **#150** (christopher-ui auth/billing) — efter #153 i konflikt (ENBART
`docs/current-focus.md`, ingen kodkonflikt), **hålls per ADR 0035** (operatörs
scope-beslut + villkorlig grind). **Färsk orchestrator-startprompt finns överst i
[`docs/handoff.md`](handoff.md).**

**Nästa konkreta steg (prioordning):**
1. **Testa SKARPT skapande av hemsidor** (rekommenderat): kör verkliga flödet
   (`OPENAI_API_KEY`-brief/plan + riktig build, eller via Viewser) på de fyra
   baseline-prompterna och titta på faktisk render. Golden-path-baseline = 7,75/10
   men `industryFit` 10 / `scaffoldFit` 9 / `mobile` 9,5 (sektionsräkning) drar upp
   medan `copySpecificity` 3,8 + kontakt-äkthet är svagast → siffran överskattar
   upplevd finish. Skyddar kärnflödet + scope:ar nästa slice med bevis.
2. **Trovärdighets-slice** (backend, taste-tungt): branschnära story/tagline/service-
   mallar (`prompt_to_project_input.py` ~950–971) + trust-rendering, sedan kör om
   golden-path för att bevisa lyftet.
3. **Eval-ärlighet** (billig): `mobileFirstFirstImpression` är en sektionsräkning,
   `contactPath` straffar `/kontakta-oss` + läser placeholder-fält i brief/plan trots
   #153:s render-döljning. Få siffran att matcha känslan.
4. Christopher-lane: Bite C + FloatingChat-ärlighet + scope-beslut PR #150 (ADR 0035).
5. **Embeddings = PARKERAD** (ADR 0026). Golden-path bekräftar igen: rätt scaffold/
   variant/starter väljs varje gång (`industryFit` 10) — selection är inte gapet, så
   embeddings lyfter inte upplevd kvalitet.

Vercel-sandbox-spåret är i `main` (#146 spike, ADR 0033, #147 opt-in-adapter via
`VIEWSER_PREVIEW_MODE=vercel-sandbox`); default-preview är fortfarande `local-next`
(inte flippad), adaptern är inte UI-wirad. För lokal `npm run dev`: använd
`VIEWSER_PREVIEW_MODE=local-next` i `apps/viewser/.env.local` (`vercel-sandbox` är
en opt-in adapter, INTE ett dev-dispatcher-läge — dev.mjs kastar by-design på det
tills Bite C + smoke + default-flip-OK).

### Historik denna session (allt i ovanstående 10 commits på `jakob-be`)

**copyDirective-modulutbrytning — KLAR** (`8f2fc1e`, på `jakob-be`, ej i `main`).
Behavior-preserving extraction: copyDirective-delsystemet flyttat ur
`scripts/prompt_to_project_input.py` (4134→~3257 rader) till nytt paket
`packages/generation/followup/` (`text.py` delade hjälpare, `copy_directives.py`
hela systemet verbatim, façade-re-exports i PI). Scout RO-review GO (full
AST-paritet, acyklisk import, 88 copydir-tester + test_prompt_to_project_input
oförändrat gröna, alla guards gröna). `_copy_directive_llm_eligible` kvar i PI.

**P2 grounding-fixar — KLAR** (`65aa733`, på `jakob-be`): (A) extraction-vägen
begränsad till company-name|tagline (about/services bara via planner); (B)
grounding-guarden breddad årtal → alla flersiffriga taltokens, whole-token-
matchning (ej substring); (C) Project DNA-refresh för about-text→story /
tagline när copyDirective ändrar fältet; (D) ADR 0034-städning. Bredare icke-
numerisk grounding (namn/orter/cert) hålls medvetet som systemprompt +
dokumenterad begränsning. 92 copydir-tester, Scout RO-review GO.

**Lovable-gap-audit — KLAR** (read-only, 2026-06-02). Slutsats: golden-path-eval
på disk säger 7,73/10 men mäter struktur/nyckelord, inte upplevd finish → coachens
4–5/10 stämmer. Största hävstångarna mot 9/10 (rangordnat, mest backend/jakob-be):

1. **Platshållarkontakt** (tel `08-000…`, `kontakt@example.se`, "Adress lämnas på
   förfrågan") renderas rakt av → känns fejk. Kräver: tvinga riktig/ärligt minimal
   kontakt från prompt/wizard, eller dölj kanaler tills ifyllt. (backend-input + UI-prominens)
2. **Tomma trust-signaler** (`trustSignals: []`; clinic `credentials` renderas ej
   trots `sections.json`-krav) → brief/plan bör fylla dem. (backend)
3. **Generisk story/tagline/FAQ-mall** (samma copy oavsett bransch) → branschnära
   mallar i `prompt_to_project_input.py` (~950–971). (backend)
4. Tunt erbjudande (1 tjänst/produkt). (backend)
5. **Följdprompt syns inte i UI** för about/services (FloatingChat/AppliedCopyDirective
   bara name|tagline). (christopher-ui)
6. Eval överskattar (contactPath straffar `/kontakta-oss`; mobil = sektionsräkning) →
   billig fix. (backend)
- Hero-CTA/layout/färg/bild via följdprompt = senare (kontraktsbeslut/UI).
- **Embeddings hjälper INTE dessa gap** (alla fyra case träffar rätt scaffold) →
  fortsatt parkerad.

**Trovärdighets-slice steg 1 (kontakt-ärlighet) — KLAR** (`332e08e`). Audit-texten
överskattade: det mesta var redan byggt (`contact_placeholders.py` + B158/B159 +
#144 + eval `route_path_by_id`). Slicen tätade de 3 kvarvarande läckorna
(`render_global_error`, `render_map` /karta, `_faq_pairs` öppettider) med
befintliga `real_*`-helpers + 6 tester. Operatörsval: **dölj** (ej kräv i wizard).

**NÄSTA (operatörsval — produktbeslut delvis fattade):**

1. Trovärdighets-slice steg 2: **trustSignals/credentials via wizard** (operatören
   fyller i riktiga — beslut taget) + **branschnära story/tagline/service-mallar**
   (ersätt generisk mall i `prompt_to_project_input.py` ~950–971). Backend, men
   wizard-delen kräver Christopher-koordinering (UI-fält).
2. Sync-PR `jakob-be → main` (modulutbrytning + P2-grounding + kontakt-ärlighet)
   vid leveransfönster.
3. Christopher-lane: Bite C + FloatingChat-ärlighet (#5), scope-beslut PR #150.

Builder-prompt för modulutbrytningen (genomförd) finns kvar som referens i
[`docs/agent-prompts/copydirective-module-extraction.md`](agent-prompts/copydirective-module-extraction.md).

**copyDirectives-trappa (ADR 0034 väg A) — allt nedan är i `main`:**

- **Slice 2a — KLAR** (`a1e2502`): `about-text` -> `company.story`,
  replace-only. Deterministisk extraktor (kräver explicit värde) +
  copyDirectiveModel-extraktion. Vibe-rewrite utan angivet värde
  ("skriv om om oss så det låter mer personligt") är **honest no-op** i 2a —
  den klassas som tone-shift och äkta innehållsgenerering hör hemma i nivå 3.
- **Slice 2b — `tone`: HOPPAD** (operatörsbeslut 2026-06-02). Den befintliga
  `tone-shift`-semantiska patchen mappar redan "gör tonen mer premium" ->
  `tone.primary`, så en tone-copyDirective hade mest överlappat — lågt
  mervärde, onödig regressrisk. Ingen tone-target byggd.
- **Slice 2c — KLAR** (`a346bd6`): `services` -> `services[].summary`,
  replace-only. Direktiv-objektet fick `targetRef` (service id/label) som
  pekar ut vilken tjänst; matchas case-insensitivt vid apply, ingen träff =
  honest no-op (skapar/hijackar aldrig tjänst). Additiv "ny tjänst" + onamngiven
  "ändra tjänsten till X" = no-op.
- **Nivå 3a — KLAR** (`4d08526`): editPlan-planerare. Vid en rewrite-instruktion
  UTAN angivet värde ("skriv om om oss så det låter mer personligt") läser
  planeraren sajtens site-state och låter copyDirectiveModel **generera** ny copy
  för `about-text`/`services` (replace), via befintlig leak-säker apply.
  Egen eligibility-gate (`_is_content_rewrite_request`); intent/semantic patch
  orörda; name/tagline genereras aldrig; grundnings-guard mot påhittade årtal;
  B155 `appliedVisibleEffect` som synlig-effekt-verifierare. Fortfarande väg A
  (inga `.generated/`-patchar). ADR 0034-not + llm-models v6 + naming-dict v22.
- **Reviewer-härdning — KLAR** (PR #149-review-loopen): (1) vibe-"till"-läcka
  (about/services kräver citerat/kolon-värde); (2) planner no-op-löfte
  (story-snapshot+restore, även no-initial-story-fallet); (3) schema if/then
  (services kräver targetRef, about/services replace-only); (4) P1 scope-leak
  (planeraren låst till `target=rewrite_target`); (5) P1 service-ref-matchning
  (planeraren editar bara den namngivna tjänsten, id-vs-label-säkert); (6) P2
  vibe-tagline (rewrite-verb på name/tagline kräver explicit värde).
- **Slice 2d — PARKERAD: `cta`/hero.** Inget eget fält idag (hero-knappens text är
  en variant-whitelist i `build_site.py`), så detta är en **kontraktsändring**,
  inte bara enum — kräver designbeslut (ny `conversionGoals`-slug vs nytt
  PI-fält vs begränsad replace mot befintliga labels). Tas efter modulutbrytningen.
- **P2-follow-ups** (dokumenterade i `docs/handoff.md`): #1 unquoted service-ref
  utan "till" (no-op-UX), #4 extraction-vägens grounding-guard (designval, tas i
  modulutbrytningen), #3 Viewser `AppliedCopyDirective` (Christopher-lane), #5
  Project DNA-refresh vid about-text.
- **Nivå 3 fortsättning (efter modulutbrytning, eget beslut):** multi-target
  editPlan, separat `verifierModel` (synlig effekt bortom B155-fil-diff), bredare
  grounding-guard (siffror/orter/namn/certifieringar, inte bara årtal), och
  väg B-UI för editPlan (FloatingChat — Christopher). Nivå 4 = väg C (filpatch,
  eget ADR + sandbox).

Hårda regler genom hela trappan: remappa INTE tjänstetext till tagline/about;
generated output förblir vanlig Next.js; rör inte preview-runtime/adaptern;
ingen UI (Christophers lane); rå prompt blir aldrig kundcopy.

Parallellt (Christopher/UI): Bite C — flippa `app/api/preview/[siteId]` till
`currentViewserRuntime()`.

Parkerat (kräver operatörs-OK): default-flip till `vercel-sandbox` (kräver
Bite C klar + smoke), `forbidden`-radering (egen ADR + test-omskrivningar),
optional/lazy `@vercel/sandbox`-dep. (Sync-PR #149 är mergad — copyDirective-
batchen är i `main`.)

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

Last verified state: `029f652` (2026-06-04 natt UTC, `jakob-be` HEAD — #190 kor-4b verifierModel
read-only smak-critic ovanpå kor-4a (mock=4a, dedup, icke-blockerande, llm-models v8). **HELA
KÖR-SEKVENSEN i docs/heavy-llm-flow/ ÄR NU IMPLEMENTERAD** (0/1a/1b/1c/2/3a/3b/4a/4b/5/6a/6b/7a/7b/7c/7d/
STAB/o1/o2). Kvar = INKOPPLING, inte fler kör-kort: rerender-wiring (gör kor-5 verklig),
`/api/prompt`-wiring + routerDecision (gör follow-up verklig för UI, låser #177), baseline-eval.
Föregående: #188 kor-6b router LLM-fallback + #189 kor-o2 OpenClaw Core V0 + #187 platform-baseline.
Föregående: #185 kor-5 repairModel
blueprint-only repair (dormant library; brief-validering+rollback, rerender try/except, blueprintPasses,
typfix). Föregående: #186 CLI-wiring (kor-4a critic + kor-7 follow-up-kedja i build-vägen, E2E). Docs-pass:
system-overview-refresh + current-focus slim-down (Föregående checkpoint → arkiv) +
arkitektur-canvas-bump. Föregående: #184 kor-3b
visualDirection väljer section-treatment (Option A, verifierad mot kombinerat träd) + #179 kor-3a
section-treatments-JSON + #180 kor-4a deterministisk critic + #183 kor-3a planning→build
boundary-fix (Pushvakt P1: loader → orchestration, repo-boundaries v10, fail-closed,
import-scan-test) mergade denna session. Föregående `f4d2a1e` (kväll) — #178 KÖR-7-STAB stabiliserar
apply/targeted-render: P1 stängd (applied capability → selectedDossiers.required via filter_capabilities
→ codegen monterar dossiern), stale provenance rensad, #176-P2:or fixade (ingen build på applied=false,
diff mot aktiv build-snapshot, route→id via routePlan, failed-trace, runs_root). Föregående: #176 KÖR-7d targeted
render + version-build STÄNGER follow-up-bryggan (7b→7c→7d): capability-följdprompt bygger om
påverkad route, swap:ar current.json bara på ok/degraded, ärlig appliedVisibleEffect, gamla runs
orörda, skipped/unmapped loggas i trace. Även inne (Christopher): #172 stale-pending-runs +
#173 ärligt layout-no-op. Föregående: #175 KÖR-7c apply:
validerad capability-patch → ny immutabel Project Input-version v<N+1> (requestedCapabilities),
ingen build/current.json; copy_change+inline = unmapped (ADR-beslut). Ovanpå #174 som härdar KÖR-7b
patch-planeraren: component_add utan namngiven komponent avvisas + _INTENT_CAPABILITY drift-låst.
Ovanpå: #171 KÖR-7b artifact patch planner (dry-run) mergad ovanpå #170 (B86 npm-timeout
env-override) och #169 (Christopher UI-reconcile, hans lane). Plus Vercel deploy-denylist
(`9ba29ce`) och docs-batch (kor-o1 OpenClaw Core-kontrakt + handoff-bump). `origin/main` =
`1d6e069`; jakob-be många commits före, sync = operatörsbeslut).
Nya PRs sedan föregående checkpoint: #169, #170, #171, #172, #173, #174, #175, #176, #178 (alla mergade till `jakob-be`).

## Öppen PR att känna till — #158 (christopher-ui, ersätter stängda #150)

**PR #158** `feat/viewser-ui-overhaul -> main`: "feat(viewser): UI-överhalning
utan auth/billing (split ur #150)". Christophers UI-lane. **#150** (auth + billing
+ Stripe + starters + kärnloop-UX) är **STÄNGD** — den delades upp och
auth/billing lyftes ut per produktkompassen (auth/billing väntar tills operatören
uttryckligen väljer det som scope).

**Operatörs-OBS:** Backend/heavy-LLM-lanen (`jakob-be`) blockeras INTE av #158 —
disjunkt filscope (#158 rör `apps/viewser/**`; vår lane rör `packages/generation/`,
`governance/`, `scripts/`, `docs/heavy-llm-flow/`). Jakob mergar/rör inte #158
(Christophers lane).

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`. Christopher jobbar default på `christopher-ui`.
- `main` är canonical/sanningsbranch. Operatören eller agenten öppnar PR
  från arbets-branchen mot `main` när "en ny officiell version ska in" —
  ingen schemalagd cadence, det är ett beslut per leveransfönster.
- Efter merge: arbets-branchen synkas till `origin/main` (`git reset --hard
  origin/main` + `--force-with-lease`-push), inte via separat PR.
- Detaljerade regler: [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md).

## Pågående/öppna PR:s just nu

**Öppna PRs:** **#156** (`feat/live-preview → jakob-be`, hostad `/live`-loop —
parkerad pga säkerhet, live-lane, INTE vår att merga/fixa) och **#158**
(`feat/viewser-ui-overhaul → main`, UI-överhalning utan auth/billing, split ur
stängda #150, Christopher-lane). Ingen öppen backend/heavy-LLM-PR i `jakob-be`.
KÖR-0 (#155) + #160 + #157 + #159 är mergade till `jakob-be`. **#150 är STÄNGD**
(ersatt av #158).

**Mergade/stängda denna session:**
- **#147** `cursor/vercel-sandbox-adapter → jakob-be` — **mergad** (squash,
  `53301c4`). vercel-sandbox som opt-in PreviewRuntime-adapter (ADR 0033):
  naming v19, `PreviewRuntimeKind` += `vercel-sandbox`, registry + delad
  DI-runner `vercel-sandbox-runner.ts` (`@vercel/sandbox` bara i
  `apps/viewser/lib`, test-låst). Ingen default-flip, ingen UI/Bite C, ingen
  main-sync. Cleanup efter coach-review: spike-runnern extraherad,
  `vercel-sandbox-spike.ts` borttagen.
- **#146** `cursor/vercel-sandbox-spike → jakob-be` — **mergad** (squash,
  `58710ec`). Flag-gated Vercel Sandbox-PoC (spike), **live-verifierad**:
  painter-palma `status: ready`, cold-start ~29 s (install 18 s + build 9 s),
  desktop + mobil render OK utan konsolfel, `stop()`+`delete()` städade rent,
  faktisk kostnad ~52 s active CPU + ~155 MB ingress (≈ ett par ören). INTE
  adapter-promotion: `PreviewRuntimeKind`/registry/ADR/naming orörda; helpern
  ligger bakom `VIEWSER_SANDBOX_SPIKE=1` i `apps/viewser/lib/` (ej route-wirad).
  Nästa runtime-steg: `vercel-sandbox` som opt-in adapter (kräver ADR 0033 +
  naming-bump + DI-wiring per ADR 0030; Bite B DI-grund finns redan i `jakob-be`).
- **#140** `cursor/preview-runtime-bite-b-di → jakob-be` — **mergad** (squash,
  `da5ef7b`). Bite B: `localRuntime`/`stackblitzRuntime` via dependency injection,
  env-styrt, paket→app-lager-regel låst av `test_preview_runtime_di.py`. CI helt
  grön; exakt 9 filers scope. Produktions-route `app/api/preview/[siteId]` ännu
  inte flippad till `currentViewserRuntime()` = Bite C (Christopher/UI).
- **#138 / #141 / #145** (docs, `AGENTS.md`) — **konsoliderade och stängda**.
  Nära-dubbletter; bästa raderna foldade in i `AGENTS.md` på `jakob-be`
  (`48adcde`) och flödar till `main` vid nästa sync.
- **#144** `jakob-be → main` — **mergad** (squash, `fba03d0`). Hela
  hardening-batchen + tre Vercel-Agent-review-fixar (se "Last verified state").
- **#143** `cursor/build-site-py-refaktorering-b2c1 → jakob-be` — mergad
  (`2320e34`, squash). Behavior-preserving npm/subprocess-extraktion.
- **#139** `christopher-ui → main` — mergad tidigare 2026-06-01 (`f22d27a`,
  steward-auto `efbb425`). Tre låg-impact-fynd kvar i Christophers lane
  (`msg-0024` + `msg-0025`).

`jakob-be` får INTE `reset --hard origin/main` mitt i ett pågående flöde; efter
en landad sync mergas `origin/main` in i arbets-branchen (gjordes i `939f684`).

**Christophers `origin/christopher-ui`** — efter PR #117 är hans branch
synkad mot post-#117-main. Han har under operator-OK scope-leak
implementerat hela `GAP-backend-build-trace-endpoint` (3 endpoints + UI +
5 bug-hunt-fixes). Mergad via PR #105 / commit `fe7a9e4`; flyttad till
`completedGaps` i `docs/workboard.json`. Workboardens `owner` är
medvetet kvar på `jakob` så Sprintvakt-lane-policyn passerar.

## Direkt nästa fokus

### Prioordning post-B157-stängning

1. **Manuell B157-end-to-end-verifiering** (operatörsuppgift, ~5 min) —
   kör follow-up på commerce-base-site med lockfile-drift, förvänta
   ingen `PermissionError: [WinError 5]`. Strukturella regression-
   tester finns redan (`tests/test_local_preview_server_b157_followup.py`),
   men en faktisk end-to-end-körning bevisar reap-fixet i naturlig miljö.
2. **Bite B (PreviewRuntime DI-wiring) — KLAR** (PR #140 mergad `da5ef7b`,
   2026-06-01). `localRuntime`/`stackblitzRuntime` delegerar via dependency
   injection; env-styrt; paket→app-lager-regel testlåst. Kvar: Bite C (UI-flip,
   Christopher) + Pushvakt-fynd parkerade som liten slice (DI-state-isolering,
   StackBlitz `about:blank`-kontrakt, PascalCase-handler-typer).
3. **B157 nivå-4 (Windows-safe rebuild, immutable build-dir + pointer-
   swap)** — arkitektur-rätta lösningen, 12-16h. Akut nivå-1 +
   followup-fix räddar 99% av case idag, men anti-patternet "rebuilda
   ovanpå live output-katalog" kvarstår tills nivå-4 landar. Spec i
   `docs/gaps/GAP-windows-safe-rebuild-pipeline.md`.
4. **ADR 0034 — väg (b) "ärlig först"** (B155). FloatingChat markerar
   när följdprompt inte gav synlig effekt. Liten kodändring, kräver
   Christopher-koordinering (UI-yta).
5. **Quality-gate scaffold-routes-discovery** (tech-debt från `0b40b8d`).
   Läs scaffoldens `routes.json` direkt istället för pattern-matching
   `kontakt`/`contact`/`hitta-hit`-fragmenten. Egen sprint, ej akut.
6. **B156 follow-up: browser-hydration-smoke** — headless
   playwright/puppeteer ersätter chunk-heuristik. Egen sprint, ej akut.
7. **Worktree- och städ-cleanup** (operatörsbeslut):
   - Adapter-WIP på `cursor/preview-runtime-adapters` (worktreen
     `C:/Users/jakem/Desktop/sajtbyggaren-worktrees/preview-runtime-adapters`)
     — innehåller vercel-sandbox-adapter-skiss, naming-dict v18-bump,
     fly-stub. Bör snapshot:as till `origin` innan worktreen rensas.
   - `origin/cursor/dossier-intake-v11-review-895d` (3 commits, ingen PR).
   - `origin/cursor/jakob-be-viewser-local-next-preview` (PR #85 stängd,
     innehåll inne via #88/#92/#97/#100/#101).
   - Worktree-mappen `C:/Users/jakem/Desktop/sajtbyggaren-worktrees/
     llm-golden-path-v1` — git har glömt den; stäng Cursor + radera mappen.

## Redan landat (tidigare session-status korrigerad 2026-05-26 PM)

- Lane 2 LLM contract propagation — klar. B137 + B138 stängda
  2026-05-21, B141 stängd 2026-05-21 (PR #52), B139 + B140 stängda
  2026-05-22. Regression-net via PR #84 (`0205212`).
- Lane 4 Golden Path eval — klar. Levererad via PR #110 (`1f8966a`).
  `scripts/run_golden_path_eval.py` är aktiv och användes 2026-05-26 PM
  för att verifiera naprapat-fixen (5.83 → 6.81, gate `no-go` → `go`).
- Naprapat scaffold-routing — klar. Lane 3 embeddings-gate gick från
  `no-go` → `go`. Total Golden Path 7.10 → 7.34.

## Parkerade lanes (väntar trigger)

- Path B / section-driven renderer — kräver Lane 2 mergad först (delar
  `scripts/build_site.py`). Lane 2 är klar; Path B är fortfarande
  operatörsbeslut.
- Christophers `GAP-backend-build-trace-endpoint`-PR — Jakob är reviewer
  när Christopher öppnar PR från `christopher-ui` mot `main`.
- Sajtmaskin inspiration Scout — lokalt-only (kräver `sajtmaskin.rar` på
  operatörens maskin).
- Sprintvakt V1.3, B125 preview-fallback — öppna men ej akuta.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project
DNA V2 tills en sprint är formellt vald.

Startprompt för nya agenter:
[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md).

## Aktiv kö (kort lista)

Detaljerade Queue-/Blocked-block ligger i arkivet
[`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md).
Aktiva spår i prioritetsordning:

1. Manuell B157-end-to-end-verifiering (operatörsuppgift, ~5 min).
2. Bite B (PreviewRuntime DI-wiring) — KLAR (#140 mergad da5ef7b). Nästa
   runtime-steg: Scout sandbox-spike (se "Nästa" överst).
3. B157 nivå-4 (immutable build-dir + pointer-swap, GAP-windows-
   safe-rebuild-pipeline) — eliminerar orphan-process-klassen.
4. ADR 0034 / GAP-followup-prompt-content-passthrough — fri
   follow-up-text når codegen via ``copyDirectives[]``. **Väg A (nivå 1)
   är i `main`** (via #142/#144/#148): ``directives.copyDirectives``
   (target company-name|tagline, operation replace-text|include-token),
   deterministisk extraktor + ``copyDirectiveModel``-roll (llm-models v5),
   25 tester, real-LLM-smoke verifierad. Väg B FloatingChat-UI (Christopher)
   är också i `main` (#139). **Nivå 2 slice 2a (about-text) + 2c (services) +
   nivå 3a (editPlan-generation) + extern-review-härdning landade på `jakob-be`
   (`6c860ec`), ej i `main` (sync-PR nu mergebar). Slice 2b tone HOPPAD; 2d cta
   PARKERAD.** Nästa: copyDirective-modulutbrytning (reviewer-rekommenderad,
   behavior-preserving) — se Nästa-blocket + builder-prompt i `docs/agent-prompts/`.
5. B49 (docs-base page-map sidebar) — låg prio, behövs innan
   `course-education → docs-base` aktiveras.
6. B13a arkitektur-flytt — kvarstår som öppen post, kräver egen sprint
   + sannolikt egen ADR.
7. B53, B47, BO4-followup-cancel — låga, ingen blocker.

(Sync-PR `jakob-be → main` är operatörsbeslut, inte aktivt
agentarbete. `GAP-backend-build-trace-endpoint` är completed via
PR #105 / commit `fe7a9e4`.)

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → arbete på arbets-branch (`jakob-be` eller
`christopher-ui`) → guards gröna → push → vid behov PR mot `main` →
post-merge-sync.

Operatörspreferens: svenska, kort och koncist. Förklara dev-uttryck med
korta parenteser första gången per konversation. Mönstret i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).

## Arkiv

Historiska checkpoints och "Föregående produkt-läge"-kedjan ligger i
[`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md).
Hela "Föregående checkpoint"-kedjan (2026-05-25 → 2026-06-02) flyttades dit
2026-06-03 i en slim-down-pass, så denna fil bara bär aktuell köplan. För djupare
commit-historik: `git log --oneline origin/main` eller `git log --oneline
origin/jakob-be`.

