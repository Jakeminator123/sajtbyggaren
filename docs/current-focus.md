# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.
Startpromptar och rollgränser finns i
[`docs/agent-prompts.md`](agent-prompts.md).

## Current objective (2026-06-03 natt — kor-3a/4a/3b inne; våg 2 landar)

`jakob-be` @ `5b051b6`, rent träd. **Denna session mergade:** #179 (kor-3a:
section-treatments Python→JSON, en deklarativ källa), #180 (kor-4a: deterministisk
quality critic v0 — non-blocking, ingen LLM), och #183 (kor-3a follow-up: flyttar
section-treatments-loadern till `orchestration/` så `planning` inte importerar
`build` — Pushvakt P1; repo-boundaries v10 + fail-closed på trasig JSON + boundary-test
som scannar riktiga imports), och #184 (kor-3b: visualDirection väljer section-treatment,
Option A — verifierad mot kombinerat träd med #183, alla paritets-/pick-tester gröna).
**Ärlighet:** kor-4a-critic är library-komplett men **dormant i build-vägen** (gaten
anropas utan `generation_package` → `critic` blir null i verkliga runs) tills
`build_site`/`dev_generate` wire:as. kor-3b är likaså aktiv bara när blueprintens
`visualDirection` är satt (annars byte-paritet mot kor-3a).
**Status cloud-builders:** kor-3b INNE (#184). kor-5 pushad på `feat/kor-5-repair-pass`
(ingen PR än; hålls/dormant + no-key-inkonsekvensen kvar att fixa innan den tas).
**Justerad ordning (orchestrator + coach, natt):** (1) ✓ kor-3b inne (#184) → (2) **NU:** wira
critic/repair + follow-up-bryggan i build-vägen/`/api/prompt` (största hävstången; gör
kor-4a/7 verkliga + UPPLÅSER Christophers #177) → (3) minimal E2E + read-only baseline-eval
→ (4) kor-5 (library → wira in) → (5) kor-o2 OpenClaw Core V0 (read-only, spec:as parallellt)
→ (6) design-system-ADR + `next-shadcn-tailwind`-starter *om evalen visar att gapet är
visuellt* (annars copy/trust/kontakt-ärlighet först) → (7) kor-4b verifier + kor-6b
router-fallback. **Princip:** ingen ny LLM-slice utan inkopplingsplan — varje slice når
en användarväg eller taggas dormant + får en wiring-follow-up (#178-trion filad så).
**Öppet (ej vår lane):** #177 (Christopher, väntar på routerDecision i `/api/prompt`),
#181/#182 (docs→main, cloud-env), #156 (parkerad). Main-sync = operatörsbeslut.

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

Last verified state: `5b051b6` (2026-06-03 natt UTC, `jakob-be` HEAD — #184 kor-3b
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

Historiska checkpoints och "Föregående produkt-läge"-kedjan från
2026-05-13 till 2026-05-26 PM ligger i
[`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md).
Den filen växer när vi gör nästa slim-down-pass. För djupare commit-
historik: `git log --oneline origin/main` eller `git log --oneline
origin/jakob-be`.

## Föregående checkpoint

### 2026-05-25 UTC — current-focus.md före `2057241`

Last verified state: feature-branch `b146-port-section-dispatcher`
(2026-05-25 **kväll**, B146-port: Christophers PR #105 + #108
section-arkitektur portad ovanpå jakob-be:s PR #107 split). `main`
HEAD är `84bf842`; `jakob-be` HEAD är `ee2a91e`. PR mot `jakob-be`
öppnas härnäst, följt av en sync-PR `jakob-be → main` när feature
PR:n mergat. Bug-räkning: **19 aktiva / 5 unknown / 114 stängda**
(B146 stängd via denna port).

**Kvällens fönster — B146 + Phase 3 port:**

- `packages/generation/build/dispatcher.py` (ny, ~370 rader):
  section-id registry, `_SECTION_TREATMENTS_BY_VARIANT`,
  `_treatment_for_section`, `_operator_pin_for_section`,
  `_load_scaffold_sections`, `_section_renderer_kwargs`,
  `_call_section_renderer`, `render_route_generic`.
- `packages/generation/build/renderers.py`: utvidgat från 2357 → ~4700
  rader. Alla ~30 nya `render_section_*` + uppdaterade page renderers.
- `scripts/build_site.py`: utökade re-exports + `__getattr__`-shim så
  `from scripts.build_site import render_section_X` fortsätter fungera.
- Phase 3 backend: `_apply_directives_fields` i resolve.py mergar
  `directives.sectionTreatments`; `plan.py` får
  `_SECTION_TREATMENTS_CATALOGUE` och prompt-update; schema-bump.
- ADR 0031 → 0032 renumrerad (jakob-be:s 0031 Steward auto-bump äldre).
- Wizard-UI: `treatment-options.ts`, `wizard-types.ts`,
  `wizard-payload.ts`, `steps/visual-step.tsx`, `demo-answers.ts`,
  `wizard-constants.ts` uppdaterade.
- Tester: 126 nya cases passerar.

**Eftermiddags-fönstret — 4 PRs landade i `jakob-be` + sync-PR #103
till main:** PR #97 (preview-fel mapping), PR #100 (per-siteId build
mutex → B116), PR #101 (StackBlitz embed unblocker), PR #104 (preview
mode end-to-end), PR #103 (sync-merge `jakob-be → main`, 16 commits).

### 2026-05-25 UTC — current-focus.md före `ee31eb1`

Last verified state: `ee31eb1` (2026-05-25 UTC, steward-auto efter
PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime
smoke-lock + golden-path eval (#112, #109, #110)).

Sammanfattning: detta var checkpointen där hela serien PR #55, #59-#68,
#70-#71, #75-#84, #87-#113 mergades till main över loppet av några
dagar. Innehåller bl.a. starter-candidate-auditor (#60), team-parallel-
workflow (#61), wizard-directives Gap 1 + 3 (#63), restaurant-
hospitality Week 1 (#68), Sprintvakt V1+V1.1 (#70 + #75), agent-inbox
(#77), candidate-provenance (#78), B83+B85+B87+B72+B75 grind-PRs
(#79-#83), section-treatments + Path B-refaktor (#107 + #108), B146-
port (#112), golden-path-eval (#110), och sync-PR #113 till main.

### 2026-05-26 UTC — current-focus.md före `858f8e8`

Last verified state: `858f8e8` (post-merge `jakob-be` HEAD, 2026-05-26
~13:15 UTC, merge av PR #117 — `feat(viewser): mobile responsive` + PR
#119 dossier intake model review + docs-hygien T0+T1 ovanpå).

**Sessionens leverans:** 12 buggar stängda (B97, B98, B148, B149,
B150, B90, B91, B92, B93, B151, B152, B153) + PR #116 dossier-intake
mergad + PR #117 mobile responsive mergad (31 commits från
christopher-ui, 100 % UI-only mot merge-base `3bedddd`).

**B147 (Medel-Hög) ny aktiv bugg då** — Vercel preview wizard 403 via
`assertLocalhost` på `*.vercel.app`. Stängd senare i `b3834b3`.

`origin/jakob-be` var då 8+ commits före `origin/main`. Sync-PR
`jakob-be → main` var queued men ej öppnad — Christophers
`christopher-ui` är nu mergad genom #117, så den blockaren var löst.
Kvarvarande blockare då: B147-vägval + Vercel-production-branch-flip.
Båda är åtgärdade 2026-05-26; B147 stängdes i `b3834b3`.

### 2026-05-27 UTC — current-focus.md före `91230b4`

Last verified state: `91230b4be799067ec05beb22ce34046ba6e89e0c` (2026-05-27 early morning UTC, post completed gap-spec cleanup).

Nya commits sedan föregående checkpoint (`0f3bd67`):

- `91230b4` docs(steward): prune completed gap specs before sync.
- `6222627` docs(steward): archive completed gap prompts after Gap 10.
- `3b61c73` feat(build): close Gap 10 product image pipeline (#122).
- `365c1d7` feat(build): close Gap 9 — isolate moodImages to private uploads.
- `0043839` docs(current-focus): update verified SHA and commit count after recent changes.
- `e9c8afa` docs(handoff): update verified SHA and commit count after eval-layout refactor.
- `63656fb` refactor(evals): split data/evals into summaries/ + artifacts/ layout.
- `91990de` docs(steward): bump focus and handoff counts after B147 sync.
- `2a77c07` docs(steward): close B147 after host whitelist merge.
- `d483b7d` docs(steward): bump focus and handoff counts after docs sync commits.
- `b4473ee` docs(known-issues): move B147 to Stängda after b3834b3.
- `b3834b3` feat(viewser): close B147 — add VIEWSER_ALLOWED_HOSTS host-whitelist.
- `88dedf0` docs(steward): sync backend handoff after gap 6 and 7 merge.
- `cb07dbb` docs(steward): sync handoff/focus/workboard with actual code state 2026-05-26.
- `ea6e141` feat(build): close Gap 6 + 7 — multi-size favicon.ico + 1200x630 og-image.png.
- `c002aec` chore(deps): add pillow>=10.0 for build-pipeline image conversion.
- `dbc97d8` docs(agents): add cloud-grind prompt-pack for gaps + B147 + doc-cleanup.
- `1332efd` settingscommit (befintlig branch-commit, ej rörd i detta steward-pass).
- `9d052b9` docs(steward): bump current-focus + handoff + write late-evening handoff.
- `cc1a5aa` chore(viewser): commit vercel.json deploy config.
- `0ed5348` docs(backend-handoff): mark gap 1 + 11 as closed (audit 2026-05-26).
- `3fc187e`, `4cd367c`, `b414c6b`, `ee1751f` — naprapat scaffold-fix + Lane 2/4 stale-correction.
- `d3a2ad6`, `9dbd10a` — reviewer-flagged drift correction.
- `0f3bd67` — C4 audit landed via local merge (PR #121).
- `1721494`, `46d819f` — focus bump + Gap-headings cleanup.
- `6aeec35`, `fdb1fef`, `ff6154e` — evening handoff till nästa orchestrator + term-coverage cleanup.
- `b89a3d2` feat(discovery): persist directives.notesForPlanner into Site Brief (**Gap 5 stängd**).
- `1b91ca6` feat(discovery): merge directives.requestedCapabilities into resolver (**Gap 4 stängd**).
- `1c6d033` docs(focus,handoff): close Gap 4 + Gap 5 in audit table.
- `f7c437e` docs: slim current-focus från 1414→205 rader + skriv om branch-discipline.md för enkel modell (jakob-be/christopher-ui default, PR mot main vid officiell version). Auto-regen .cursor/rules-speglar.

### 2026-05-27 UTC — current-focus.md före `3415e7d`

Last verified state: `3415e7d` (2026-05-27 UTC, steward-auto efter PR #123 — sync(jakob-be -> main): backend gap batch and docs cleanup).
Nya PRs sedan föregående checkpoint: PR #123 — sync(jakob-be -> main): backend gap batch
and docs cleanup.

### 2026-05-27 UTC — current-focus.md före `44bdbdd`

Last verified state: `44bdbdd` (2026-05-27 UTC, steward-auto efter PR #125 — fix(discovery): honor wizard clears across versioned fields).
Nya PRs sedan föregående checkpoint: PR #125 — fix(discovery): honor wizard clears
across versioned fields.

### 2026-05-27 UTC — current-focus.md före `82ce287`

Last verified state: `82ce287` (2026-05-27 UTC, steward-auto efter PR #124 — feat(llm-golden-path): lock v1 + extend with multi-intent chain, real-build smoke, runbook and handoff).
Nya PRs sedan föregående checkpoint: PR #124 — feat(llm-golden-path): lock v1 + extend
with multi-intent chain, real-build smoke, runbook and handoff.

### 2026-05-27 UTC — current-focus.md före `67bd89a`

Last verified state: `67bd89a` (2026-05-27 UTC, post coach-godkänd
sanning-städning av PR #133. Dynamisk count med
`git rev-list --count origin/main..origin/jakob-be` visade **40**
commits framför `origin/main` — inte 29 som tidigare antagits.
PR #133 (öppen, inte draft) är redo för ready-merge).

Nya commits sedan `c9a730b` (i historisk ordning):
- `c67b53f` docs(steward): bump verified state to c9a730b post PR #131
  follow-up.
- `3e660ea` fix(docs): unbacktick Next.js ready output to clear
  term-coverage strict (false positive från föregående steward-bump).
- `bb6ab2e` feat(preview-runtime): Bite A skeleton — types + registry
  + 3 adapter stubs i `packages/preview-runtime/`. Inga callsites bytta;
  Bite B wirear local + stackblitz mot befintliga `apps/viewser/lib/`-
  helpers när tsconfig path-alias eller npm-workspace etableras. Bite C
  (UI-refaktor av `viewer-panel.tsx`) kräver Christopher-koordinering.
  Se ADR 0028 (Runtime Ladder) + ADR 0030 (Preview-Provider Portability).
- `e9e3f32` fix(test): close race condition in /api/prompt smoke
  teardown — `ProcessLookupError` mellan `poll()` och `os.killpg()`.
- `e6f5376` docs(steward): bump verified state to e9e3f32 post Bite A push.
- `6375a60` docs(quality-gate): annotate severity-status mapping per ADR 0015
  (false-positive bot-rapport om `_CHECKS_REGISTRY`).
- `331aaa0` docs(agent-prompts): add PreviewRuntime Bite B builder prompt.
- `cbe1ba9` merge: sync `origin/main` steward-auto-bump (`-X ours`).
- `44ea54b` fix(test): wrap second `wait()` in `/api/prompt` smoke teardown —
  `TimeoutExpired` om SIGKILL inte reapar D-state-process.
- `8358326` fix(preview-runtime): refer to forbidden-aliases list, do not
  copy them — fixade `test_no_legacy_terms` CI-failure på `cbe1ba9`.
- `e60f493` fix(test): catch `PermissionError` on Windows in `/api/prompt`
  smoke teardown — Win32-race där `Popen.terminate()` kastar errno 5.
- `19480dc` feat(preview-runtime): fail loud on unknown VIEWSER_PREVIEW_MODE
  — `currentKind()` kastar Error på explicit men okänt env-värde,
  fortsätter tyst fallback till `local` bara på tomt/osatt env.
- `e2f857c` fix(quality-gate): smala `placeholder-copy-scan` så
  dev-markers (todo/fixme-stil) inte räknas som customer-copy-placeholder
  — de gav brus när check:en skannar både code-comments och
  customer-rendering-strängar.
- `5d5106c` docs(steward): bump verified state to e2f857c post PR #133
  reviewer batch.
- `5d4111f` fix(docs): unbacktick dev-marker words in steward-bump body
  — term-coverage strict false positive på fixme-ordet i förra bumpens body.
- `d60bb58` docs(rules): add bot-report-verification — alwaysApply: true
  rule som säger kolla mot `origin/<branch>` innan fix på cachad
  bot-rapport. Skrevs efter att två stale bot-rundor ledde till
  onödiga rundor.
- `abff654` fix(quality-gate): make TBD + REPLACE_ME case-insensitive in
  placeholder scan — extern reviewer-fynd post #133. `\b`-word-boundaries
  håller kvar mot infix-false-positives.
- `58cfe20` docs(preview-runtime): reconcile fly slot to ADR 0028 level 3
  in README — extern reviewer-fynd post #133. Operatörsbeslut väg (a):
  behåll typunionen, dokumentera att `fly` är slot för production-/deploy-
  check (ej implementerad). Naming-dict v17 oförändrad.
- `f8d0d0b` docs(steward): bump verified state to 58cfe20 + fix open-PR
  contradiction.
- `8fb24e4` docs: file B157 + GAP-windows-safe-rebuild-pipeline (extern
  reviewer-analys 2) — WinError 5 rmtree på live `node_modules` när
  builder rebuildar samma `.generated/<siteId>/` som aktiv preview-
  process. Root cause: arkitektur-anti-pattern (rebuild ovanpå live
  output-katalog), trigger: B154-fixens lockfile-diff-check + commerce-
  base Next-bump. Fix-laddare i gap-spec; ingen kodfix i denna commit.
- `924a1df` docs(steward): bump verified state to 8fb24e4 + B157 in
  next-focus queue.
- `82b9f99` Cursor BugBot suggestion 1: defensive cleanup i
  `tests/test_b154_next_dev_tdz.py:_stop_process` (samma pattern som
  redan finns i `test_api_prompt_smoke.py`). Pushad direkt av BugBot.
- `23b473e` Cursor BugBot suggestion 2: smala `_TEXT_EXTENSIONS` i
  `placeholder-copy-scan` till bara `{".tsx", ".jsx"}` (var: 9 ext
  inkl. `.md`/`.json` som gav false positives på docs/config). Pushad
  direkt av BugBot.
- `f446be1` Cursor BugBot suggestion 3: byt AND till OR i
  `_has_contact_cta` så `tel:`/`mailto:`-länkar accepteras utan att
  body måste matcha CTA-mönster. Pushad direkt av BugBot.
- `0b40b8d` fix(quality-gate): accept scaffold-specific contact-routes
  (kontakta-oss + hitta-hit) — GPT P2 Badge + BugBot suggestion 4.
  Hybrid: pattern-fragments + iterera `app/`-dirs istället för att
  hardcoda `app/kontakt/page.tsx`. Stänger sista reviewer-fyndet på
  PR #133. Egen sprint som tech-debt: läs scaffoldens routes.json
  direkt istället för pattern-matching.
- `a67bc01` docs(steward): bump verified state to 0b40b8d + post-merge-
  133 priolista (Bite B + B157-val + ADR 0034 + städning).
- `f2de33f` chore(term-coverage): allowlist BugBot CamelCase-stavning.
- `86b5782` docs(integrations): fix dead markdown link i
  `webcontainers-notes.md` (pekade på `struktur/PreviewRuntime.ts` som
  aldrig fanns; nu pekar på `packages/preview-runtime/src/types.ts`).
- `ea1e435` fix(quality-gate): contact-CTA href-only check (body-text
  ensamt räcker inte) — GPT-reviewer-fynd post `f446be1` OR-fix där
  `<a href="/products">Ring oss</a>` falskt godkändes som contact-CTA.

PR #133 (`jakob-be → main`) är öppen (inte draft) och uppdateras
automatiskt med varje push. Alla guards gröna lokalt mot HEAD.
Sync-merge till main är operatörsbeslut när reviewer-trådarna är stängda.

Nya PRs sedan föregående checkpoint (i mergeordning):
PR #125 — fix(discovery): honor wizard clears across versioned fields.
PR #127 — fix(viewser): block Python-backed actions on hosted Vercel.
PR #128 — docs(gaps): file followup-prompt-content-passthrough + ADR 0034 draft.
PR #129 — feat(quality-gate): add contact-CTA + placeholder-copy checks (+ follow-up
  summary-severity-fix i `8269800`).
PR #130 — test(api): add HTTP smoke-test for /api/prompt Node->Python bridge.
PR #131 — fix(builder): close B154 — TDZ at dev hydration on deterministic codegen.
  Follow-up `c9a730b` (direct push till `jakob-be` efter merge) refaktorerade
  drain-tråden i `tests/test_b154_next_dev_tdz.py` — tidigare returnerade
  `_wait_for_dev_ready` en fresh list som slutade växa vid Next.js
  ready-raden, så TDZ-fel som trillade ut *efter* ready (precis
  B154-fönstret) syntes inte. Nu äger `_spawn_next_dev` listan och
  drain-tråden skriver direkt in i den.
PR #132 — docs(steward): cleanup pass — archive stale handoffs + completed reports.

### 2026-05-31 UTC — current-focus.md före `8709aae`

Last verified state: `8709aae` (2026-05-31 UTC, B155-backend (#135)
+ quality-gate routes-discovery (#134) + post-merge quality-gate-
härdning mergade/pushade till `jakob-be`). B155: buildern skriver
`appliedVisibleEffect` + `appliedVisibleEffectReason` till
build-result.json och emitterar trace-event `followup.no_op_detected`
för fri-text-följdpromptar utan synlig effekt (hybrid: intent-regel +
cross-run byte-diff av `app/page.tsx`). UI-delen (FloatingChat-signal)
väntar Christopher. Quality-gate: contact-route resolveras via
scaffoldens `routes.json` (`id="contact"`) istället för
fragment-matchning; post-merge-review-härdning (`8709aae`) gör en
oresolverbar contact-route till en synlig warning-finding (ej längre
tyst ok) + robustare fallback mot kända scaffold-contact-paths. Alla
guards gröna (ruff, pytest, governance, rules-sync, term-coverage,
sprintvakt). BO6 (föregående) stängd. **Kärnflödet verifierat
end-to-end via Viewser-browser** 2026-05-28 ~01:40
(måleri-bygg-genberg-07d364 init + tone-shift follow-up, båda byggde
utan WinError 5).

`jakob-be` är synkad med `origin/jakob-be`. `origin/main` ligger på
`4196c17`. Inga öppna PRs. Bug-count: 15 aktiva / 0 misplaced /
5 unknown / 130 stängda. Golden-path-eval baseline: **7.34/10,
embeddings=go** (2026-05-28 00:57, 0 regressioner från natt-batchen).

Natt-batchen 2026-05-27 → 2026-05-28 (alla pushade):

- `4196c17` docs(steward-auto): bump HEAD to acdfad2 via PR #133 sync.
- `adba139` fix(viewser): close B157 acute — stop local preview before
  ``build_site.py`` (Windows file-lock).
- `9c3bad7` chore(docs): archive 4 sprint-handoffs + drop product-
  north-star duplicate.
- `697cf4f` fix(viewser): close B157 followup — wait for actual exit
  after SIGKILL (reap-fix, ``sigkillSent`` + ``REAP_TIMEOUT_MS``).
- `c821b8e` chore(governance): post-B157 cleanup-fixes (alwaysApply,
  GAP-status, workboard.json sync).
- `f46c01a` docs(steward): remove stale post-PR-133 focus drift.
- `9196fa1` docs(steward): complete post-PR-133 drift-fix round 2.
- `ef8745d` **fix(viewser): close B157 round 3 — Windows process-
  tree-kill (taskkill /T /F)**. Diagnostiserad rotorsak: Node.js
  ``ChildProcess.kill()`` på Windows mappar till
  ``TerminateProcess(handle)`` som **bara dödar direct PID, inte
  descendants**. ``npx next start`` → child ``next start`` blev
  orphan med exklusivt fil-lås. Fix: ny ``killProcessTree``-helper
  + Windows-fast-path. 4:e regression-test låser tree-kill-mönstret.
  Full diagnostik fanns i en separat FYND-fil (borttagen 2026-06-02; B157 stängd).
- `7ab5060` docs(agent-prompts): add 2 scout-grind prompts för
  cloud-agent-fixes (backoffice-runtime-scaffolds-stale +
  followup-honest-no-op-detection backend).

**B157-status efter round 3:** verifierat end-to-end. Kvarvarande
edge case: orphan-processer från en TIDIGARE Viewser-session (pre-
698f745d-dev-server). För dessa: kör `python kill-dev-trees.py`
(Windows-only helper i repo-roten) eller dubbelklicka
`kill-dev-trees.bat`. Whitelist:ar bara Sajtbyggaren-relaterade
node-processer (skyddar VS Code language-servers etc.).

**Nivå-4-sprinten** (immutable build-dir + pointer-swap, GAP-windows-
safe-rebuild-pipeline) eliminerar hela klassen anti-pattern
"rebuilda ovanpå live preview-katalog". Egen sprint per gap-spec.

### 2026-05-31 UTC — current-focus.md före `5746419`

Last verified state: `5746419` (2026-05-31 UTC, extern-review-fixar ovanpå Stage A+B: `kill-dev-trees.py` scope:ad så den bara tree-killar Sajtbyggaren-processer (path-token eller `next start`/`next dev` på preview-port 4100-4199, inte vilket Next-projekt som helst) + latent `.generated`-token-bugg fixad, och `read_active_build_dir` (Python + TS-spegel) kryssvaliderar `current.json:buildPath` mot `activeBuildId`. Nya `tests/test_kill_dev_trees.py`. Guards gröna. Föregående: `df640c0`. — B157 level 4 Stage A+B landad på `jakob-be`. Stage A (`34db1c2`): immutable build-dir + atomär pointer-swap. Builder bygger nu till `<generated>/<siteId>/builds/<buildId>/` via ny modul `packages/generation/build/immutable_builds.py` (`new_build_id`/`build_dir_for`/`write_active_pointer`/`read_active_build_dir`) och publicerar aktiv build via atomär tmp+`os.replace` på `current.json`. Swap sker endast på slutstatus ok|degraded; failed/skipped lämnar pekaren orörd. Preview-resolvern i `local-preview-server.ts` läser pekaren med legacy-`.next`-fallback, `verify_run.py` är pointer-medveten, `build-runner.ts` dokumenterar stopAndWait som restart/consistency. WinError-5-klassen (B157) är därmed eliminerad arkitektoniskt — round 1-3-plåstren + build-runner-tree-kill är nu redundanta säkerhetsnät. Alla guards gröna inkl. slow real-builds (golden-path, b154 next dev, api-prompt bridge) + dedikerat B157-repro-test. Föregående verified: `5047ac0`.

Stage B landad ovanpå Stage A i `df640c0`: ny CLI `scripts/gc_old_builds.py` för delayed GC av gamla immutable builds under `<generated>/<siteId>/builds/`. Retention: behåll aktiv build (`current.json`), builds yngre än 24h, samt de 5 senaste per siteId; allt annat är GC-kandidat. Dry-run default, `--apply` krävs för radering. Konservativ vid saknad/korrupt `current.json` (raderar inget för den siteId:n), rör aldrig legacy flat-layout-sajter, robusta deletes (locked build → delete-failed, GC kraschar aldrig, idempotent). Återanvänder Stage A:s helpers (`read_active_build_dir`/`BUILDS_DIRNAME`/`_BUILD_ID_RE`). Alla Stage B-guards gröna (ruff, governance, rules_sync, term_coverage, pytest test_gc_old_builds+test_immutable_builds 31 pass, sprintvakt, focus). GC är operatör-/schemalagt-anropad CLI; inte inwirad i build-flödet. Kvar (framtida): flat-layout-städning + POSIX-tree-kill.)
Nya PRs sedan föregående checkpoint: PR #136 — sync(jakob-be -> main): B157 round 3 +
BO6 + B155 backend + quality-gate routes-discovery.

### 2026-06-01 UTC — current-focus.md före `ee31eb1`

Last verified state: pending (2026-06-01 fm, christopher-ui local — Tier
1 robusthet implementerad: ErrorBoundary + lättviktigt toast-system +
network-failure UX för /api/runs. Tre komplement utan backend-beroende,
alla inom apps/viewser-lanen, för att hindra tysta launch-buggar medan
Jakob sätter upp Vercel-preview-fallback för B125. (A) Ny
``components/error-boundary.tsx`` (klass — React 19 har inget hook-API)
wrappar ViewerPanel + PromptBuilder + BuilderShell i page.tsx så
crash i någon subtree avgränsas; reset-knapp ökar resetKey → React
remountar barnträdet. (B) Nytt ``components/ui/toast.tsx``
(ToastProvider + useToast + viewport, ~250 rader, ingen extern dep,
aria-live polite/assertive per variant). Mountas i providers.tsx. Hookas
in på fyra ställen i page.tsx: /api/runs initial-failure
(error-toast med retry-action), /api/runs follow-up-failure efter build
(warning-toast), handleBuildDone success (success-toast), degraded
(warning), failed (error). Stable retry-callback via loadRunsRef så
toast-actionen inte stänger över sig själv (React 19:s
react-hooks/immutability-regel). (C) Initial /api/runs-loader
extraherad till useCallback ``loadRuns`` så retry kan trigga om utan
duplicerad kod; ny ``RunsLoadErrorCard``-komponent med WifiOff-ikon +
felmeddelande + Försök-igen-knapp visas centrerat över hero när
runsLoadError är satt och builder-mode inte är aktivt. Fyra nya
source-lock-tester (``test_tier1_*``). Pre-existing
test_page_useeffect_guards_success_path uppdaterat så det accepterar
både ``cancelled`` (bool) och ``cancelledRef.current`` (ref-objekt).
ErrorBoundary-/Toast-helpers + TriangleAlert (lucide-ikon) allowlistade
i scripts/check_term_coverage.py. Slutkontroll grön: tsc 0, lint 0,
ruff 0, pytest 1198 passed + 3 skipped, governance 18/18, rules-sync
OK, term-coverage --strict 0 unknowns. Commit: f8f2213. Tidigare
verified state: pending (2026-06-01 fm, christopher-ui local — ADR
0034 väg B (B155 path B) implementerad i FloatingChat. Backend för
path A landade på `jakob-be` (commit 641abc9) men är inte mergad till
`main` än, så UI:t är redo för end-to-end så fort jakob-be → main
mergas. Kontraktet är låst per Jakobs handoff och vi rör inte
backend/generation. apps/viewser/lib/runs.ts: ny export
``readAppliedCopyDirectives(runId)`` som läser ``input.json``
→ ``dossierPath`` → versionens project-input-snapshot och returnerar
schema-strikt validerad ``AppliedCopyDirective[]`` (path-traversal-
skydd vitlistar bara ``data/prompt-inputs/`` + ``examples/`` under
repo-root). apps/viewser/app/api/prompt/route.ts: anropar helpern
efter runBuild och inkluderar ``appliedCopyDirectives`` på top-level
i prompt-svaret. apps/viewser/components/builder/floating-chat.tsx:
ny ``summarizeCopyDirectives`` helper härleder svenska success-rader
("Jag ändrade företagsnamnet till '...'.", "Jag uppdaterade rubriken
till '...'.", "Jag la in '...' i hero-texten.") per direktiv.
``summarizeBuildResult`` success-grenen prioriterar
``applied === false`` (info-variant) före applied===true med
directives före generisk "Klart!"-rad. Säkerhet: payload renderas
som textnod via React auto-escape; regression-test bevakar att
``dangerouslySetInnerHTML`` aldrig används i floating-chat.tsx.
Fyra nya source-lock-tester
(``test_b155_path_b_*``). ``AppliedCopyDirective`` allowlistad i
``scripts/check_term_coverage.py`` — lokal UI/server-helper-typ
(canonical term registreras av jakob-be när path A → main).
Slutkontroll grön: tsc 1306, ruff 0, pytest pass + 3 skipped,
governance 18/18, rules-sync OK, term-coverage --strict 0 unknowns.
PR #139 uppdaterad. Tidigare verified state: pending (2026-06-01 fm,
christopher-ui local — merge
av `origin/main` (PR #136 backend-batch: B157, BO6, B155-backend, quality-
gate) klar. 11 merge-konflikter lösta: 7 i kod (FloatingChat,
BuilderActions, ComparePreviewModal, DiscoveryWizard, wizard-types,
PromptBuilder, ViewerPanel) + 4 i docs (agent-inbox, current-focus,
known-issues, workboard). Code-conflicts prioriterade `christopher-ui`s
minimalist-UI/UX där backend-fixar från `main` ändå behölls (B151
matchMedia-listener, B152 snap-x-bredd, B153-providern). B155 UI
implementerad i `floating-chat.tsx`: `summarizeBuildResult` läser nu
`payload.buildResult.appliedVisibleEffect` (auktoritativ källa per
Jakobs PR #136) och flippar success-bubblan till en ärlig info-rad
("Ingen synlig ändring fångades — prova en mer specifik följdprompt")
när motorn rapporterar `applied=false`. Två nya regressionstester
låser kontraktet (`test_b155_floating_chat_reads_applied_visible_effect`
+ `test_b155_floating_chat_no_op_does_not_claim_success`) plus uppdaterat
`test_b153_device_preset_*`-testet pekar nu på providern istället för
viewer-panel.tsx. Slutkontroll grön: tsc 1306 filer, ruff 0 findings,
pytest 1300+ pass / 3 skipped, 18 governance-policies, rule-mirrors i
synk, term-coverage --strict 0 unknowns. Sync-PR `christopher-ui` →
`main` öppnas härnäst. Tidigare verified state: `7b6fb6c` (2026-05-27
natt, christopher-ui local — B122
stängd. `/api/prompt` exponerar nu NDJSON-stream på `Accept: application/
x-ndjson` med två events: `{stage:"building"}` exakt mellan Phase 1 och
Phase 2, samt `{stage:"done", ...result}` som slutevent. PromptBuilder
läser body-strömmen via `response.body.getReader()` och flippar stage på
riktig signal istället för den gamla `setTimeout(1500)`-gissningen som
gav falsk "Bygger sajt" vid snabba svar och falskt "thinking" vid hängda
prompter. `floating-chat.tsx`/`use-followup-build.ts` skickar inte
Accept-headern → fortfarande synkron JSON, ingen regression. Två nya
regressionstester. Term-coverage utökad med TextEncoder/TextDecoder.
Tidigare verified state: `15efae0` (2026-05-26 sen kväll, christopher-ui
local — scout-pass över hela toolbar/wizard-batchen sedan PR #117 mergades.
Tre P1-regressioner åtgärdade i ett sammanhängande pass:
A) DevicePresetProvider hydration race — persist-effekten skrev "full"
till sessionStorage före hydration läste, så valet nollställdes vid
reload. Fix: hasHydratedRef gate:ar persist tills hydration är klar.
B) Toolbar-pillen utanför viewport vid default-position — clampToViewport
räknade bara PANEL_HEIGHT (460) och inte toolbar-radens ~36-40px nedanför.
Fix: ny PANEL_FOOTPRINT_HEIGHT-konstant används i alla 4 clamp-anrop.
C) Functions-step bevarade restaurang-sidor vid byte till e-handel.
Fix: family-switch räknar nu diff mellan föregående och nya familjs
defaults, byter ut defaults men behåller operatorns custom-tillägg.
Plus 4 P2-cleanups parkade som non-blocking i scout-batchen. Lint +
typecheck + term-coverage --strict passerar.).

Aktuell christopher-ui-lane (lokala commits sedan `3bedddd`/main):

- `15efae0` fix(viewser): scout-pass P1 — device-preset persist,
  toolbar clamp, family-switch resync. DevicePresetProvider: hasHydratedRef
  gating för persist-effekten. FloatingChat: PANEL_FOOTPRINT_HEIGHT
  inkluderar TOOLBAR_ROW_HEIGHT (40px) i alla clampToViewport-anrop.
  functions-step: useEffect hanterar previousFamily ≠ null separat —
  byter ut föregående familjs defaults, behåller operatorns tillägg.
  lastAppliedFamilyRef typad om till BusinessFamilyId|null.
- `23a5c16` style(viewser/builder): unified toolbar pill — format +
  Verktyg ihopkopplade i EN container med samma `bg-card/95` som chat-
  panelen + subtil vertikal divider mellan device-knapparna och
  Verktyg-knappen. BuilderActions inline-knappen rensad från egen
  border/shadow så den smälter in.
- `481593d` fix(viewser/builder): flat Verktyg-grid + Versioner-text.
  Dialog-modalen rendar nu alla actions i en enda `grid-cols-2 sm:grid-
  cols-3` istället för per grupp. Versioner-description statisk
  "Bläddra tidigare bygg" (var dynamisk runId).
- `46a54cd` style(viewser/builder): Verktyg-grid 3-per-rad på desktop
  (`sm:grid-cols-3`, var `sm:grid-cols-4`).
- `3829260` feat(viewser/builder): Verktyg-menyn som modal grid med
  backdrop. BuilderActions inline-variant: dropdown-listan ersatt av
  Dialog-modal (Base UI). Backdrop dimmer sajt + chat; klick utanför
  stänger via Dialog default.
- `aa934cc` refactor(viewser/builder): Verktyg-pill in i FloatingChat-
  toolbar-raden. BuilderActions: ny `variant: "fixed" | "inline"` (default
  "fixed"). FloatingChat: ny `tools?: ReactNode`-slot — toolbar-raden
  under chatten blir nu en flex-row med device-toggle + tools, fortsatt
  centrerad mot panel-mittpunkten via translateX(-50%). builder-shell
  passerar BuilderActions via tools={...} med variant="inline".
- `0296fad` style(viewser): centrera device-toggle under chatt utan gap.
  DevicePresetToggleBar i FloatingChat: `left: position.x + PANEL_WIDTH/2`
  + `transform: translateX(-50%)` centrerar; `top: position.y + PANEL_HEIGHT`
  (utan +8) gör att toggle-baren hänger ihop kant-i-kant med chat-rutan.
- `362a24c` refactor(viewser): ta bort "Foundation-beslut"-panelen från
  Stil-tabben (visual-step). MetadataPanel + selectedVibe useMemo + ContextChips
  helpers raderade — operatorn behöver inte se "Family → scaffold → default-
  vibe"-meta.
- `57a56c6` refactor(viewser): wizard popup-revision — 5 smala flikar, ta bort
  Specialisering. Foundation-step: Specialiserings-disclosure med sub-kategori-
  chips raderad helt. MoreInfoDialog: max-w 720px (var 960), 4 flikar → 5 flikar
  (Innehåll splittad i Om oss + Innehåll), header pt-4 pb-2 sm:pt-5 sm:pb-3 så
  content börjar högre upp, DialogDescription hidden sm:inline, tab-bar med
  overflow-x-auto + snap-x snap-mandatory för 5 flikar på 375px. Backend oändrad
  (validateDiscoveryCategoryIds([]) godkänner tom siteType, branchForFamily()
  fallback finns redan).
- `3843a80` fix(viewser): wizard texter visade rå \uXXXX-kod — decoda till
  svenska bokstäver. JSX text-content tolkar inte JS unicode-escape-syntax —
  operatören såg "Forts\u00e4tt", "\u00e5t dig", "fr\u00e5gor" osv i klartext.
  239 escapes decodade i discovery-wizard.tsx (80), more-info-dialog.tsx (85),
  wizard-types.ts (45), assets-step.tsx (20), foundation-step.tsx (9).
- `1ab516c` feat(viewser): GPT Vision auto-hero-pick från mediamaterial-galleri.
  AssetsStep gallery-dropzone promoteras till hero automatiskt om operatorn
  inte explicit valt en — picks bästa kandidaten via `pickHeroFromGallery`
  (placement+visionConfidence). Klassificering finns redan i upload-asset/api.
- `b1e92ca` feat(viewser): wizard popup utvidgning + logo/mediamaterial på tab 3.
  MoreInfoDialog: 4 flikar (Innehåll/Kontakt/Media/Avancerat) som återanvänder
  ContentOrchestratorStep + nya ContactBlock/MediaExtrasBlock/AdvancedBlock.
  Tab 3 (functions) får AssetsStep direkt. Kontakt-disclosure flyttad från
  foundation-step.
- `1c1a9fb` feat(viewser): wizard total-minimalism — 3 tabs överst + Mer
  information-popup. WIZARD_STEP_ORDER 5→3 (foundation/visual/functions).
  Sidebar borttagen, tabs på desktop+mobile. Inga proaktiva tips/varningar.
  Foundation: bara offer + businessFamily är hard-required; alla andra fält
  och steg är skip-bara.
- `4442aea` feat(viewser): device-preset-context + iframe-mounted-during-build.
  DevicePresetProvider för delad state mellan FloatingChat (toggle-bar under
  panelen) + ViewerPanel. Iframen behålls mountad under build (BuildProgressCard
  med backdrop-blur) så ingen vit canvas mellan iterationer.

- `a1d1a1f` docs(inbox): ack msg-0008 (scope-process-PR-105) + msg-0009 (b146-port).
- `ea62e45` docs(gap): open GAP-viewser-mobile-responsive-foundation. Pausar tillfälligt
  `GAP-viewser-pipeline-status-polling` + `GAP-viewser-side-by-side-preview` (samma owner,
  samma kärnfiler) till queuedGaps. Återöppnas efter denna mobil-PR landar.
- `31a888a` feat(viewser/ui): mobile foundation — `pb-safe`/`pt-safe`/`px-safe`,
  `min-tap` (44px Apple HIG), `touch-visible` (motsatsen till hover-only),
  `bottom-sheet-handle` + `sheet.tsx` bottom-sheet-stöd (`max-h-[90dvh]`,
  `rounded-t-3xl`, `pb-safe` automatiskt under `data-[side=bottom]`).
- `3b2420d` feat(viewser/wizard): mobile pass — `validationError` alltid synlig
  (tidigare `hidden sm:inline-flex` dolde förklaringen till disabled primärknapp),
  close-knapp + konsol-knapp + popover-close får min-tap mobile, wizard-padding
  `px-5 sm:px-10`, footer `pb-safe-or-4`, `PayloadAlignmentPopover`
  `w-[min(340px,calc(100vw-2rem))]` (tidigare fast 340px overflowade),
  moodboard/produktbild-delete använder `touch-visible` (tidigare osynlig på touch),
  `site-header` `pt-safe`.
- `9593769` feat(viewser/builder): mobile pass — `FloatingChat` bottom-sheet på
  mobil med drag-handle + pb-safe (tidigare fast 360×460 blockerade hela viewporten);
  minimerat tillstånd = 56×56 FAB nederst höger på mobil (sidotab-mönstret hamnar
  mitt på 375px); composer-textarea `text-base sm:text-[13px]` (förhindrar iOS
  Safari auto-zoom); `BuilderActions` `hidden md:flex` (verktygsmenyn skulle
  hamna under bottom-sheet:n); `SiteInspectorSheet` bottom-sheet på mobil
  (`max-md:!inset-x-0 max-md:!bottom-0 max-md:!h-[90dvh] max-md:!rounded-t-3xl`)
  + tabs `overflow-x-auto scrollbar-hidden` så 7 triggers kan scrolla horisontellt.
- `fb87699` docs(focus): bump current-focus till 9593769 + governance fixes
  (fidelity-term ut, FloatingChat-syntax i kommentar).
- `b0140b1` docs(inbox): notify jakob-be om PR #117 + pausade gaps (msg-0010).
- `62437de` docs(gap): open GAP-viewser-mobile-responsive-polish (fas 2).
- `d7ca301` fix(viewser/prompt): mobile-friendly composer tap-targets + iOS-zoom-fix
  (PromptBuilder textarea text-base sm:text-[15px], submit min-tap, ModePill px-3).
- `6b2d68c` fix(viewser/wizard,builder): systematic tap-target upgrade — utility
  buttons (InlineHelpButton, AssetDropzone "Välj fil", DirectivesPreview Copy,
  QuickPromptButton — alla min-tap sm:min-tap-0).
- `64445bb` fix(viewser/canvas): hero typography scale + console-drawer safe-area
  (ViewerPanel text-3xl sm:text-4xl md:text-5xl + px-5 sm:px-12, ConsoleDrawer
  pt-safe + pb-safe-or-4).
- `712a3c2` fix(viewser/dialogs): mobile-friendly grids + iOS-zoom-fix på inputs
  (ai-image-generator grid-cols-1 sm:grid-cols-2 + max-h-[90dvh], asset-uploader
  grid-cols-2 sm:grid-cols-3, color-picker grid-cols-4 sm:grid-cols-6 + min-tap
  per swatch, alla inputs text-base sm:text-[X]).

Inga off-limits-paths rörda i fas 1 (`scripts/`, `packages/generation/`,
`apps/viewser/app/api/`, `apps/viewser/lib/`, `middleware.ts`, `next.config.ts`,
`package.json` — alla intakta).

Fas 2 (polish/P1) — completed (in-review). `GAP-viewser-mobile-responsive-polish`
adresserade: PromptBuilder textarea iOS-zoom-fix + min-tap-submit, `InlineHelpButton`
min-tap, `ViewerPanel` hero typografi `text-3xl sm:text-4xl` + padding `px-5
sm:px-12`, `ai-image-generator-dialog` mobile bottom-sheet-stack + grid-cols-1,
asset/color-dialog-grids responsiva, `ConsoleDrawer` flexibel höjd,
`AssetDropzone` + `DirectivesPreview` + `QuickPromptButton` tap-targets.

Fas 3 (final polish) — completed (in-review). `GAP-viewser-mobile-responsive-final-polish`
landat 4 commits ovanpå fas 1 + 2 i samma PR #117:
- `e05c443` docs(gap): complete fas 1+2 (in-review), open fas 3 — final polish.
- `18d84f5` fix(viewser): mobile responsive height + compare-modal swipe A/B.
  - `run-history.tsx` ScrollArea `h-[26rem]` → `h-[min(26rem,50dvh)]` (333px på 667px-skärm).
  - `compare-preview-modal.tsx` mobil snap-x swipe + A/B-pills + scroll-position-detection.
- `f850882` feat(viewser/canvas): device-toggle desktop preview + edge-pulse motion.
  - `viewer-panel.tsx` 4-knappars toggle 375/768/1024/Full med sessionStorage-persistence.
  - `globals.css` `.animate-fc-edge-pulse` 2.6s ease-out → 3s ease-in-out.
- `8724798` chore(viewser): term-coverage compliance.
  - Typ-namn slimmat (preset-suffix borttaget), laptop-jargong rensad, observer-API utbytt mot scroll-pos detection.

Scout-fixes (3 P0 + 12 P1) — completed (in-review). `GAP-viewser-mobile-scout-fixes`
adresserade alla högre-prioriterade fynd från scout-rapport `95f73fbf`
(composer-2.5-fast, read-only bug-hunt på diff `ea62e45^..8724798`). Landar
som 3 commits ovanpå fas 3 i samma PR #117:

- `6d0c896` docs(gap): complete fas 3 (in-review), open scout-fixes GAP.
- `cb6f43d` fix(viewser): scout P0 batch.
  - **P0 #1** — `pb-safe-or-3` utility lades till i `globals.css` (refererad i
    `ai-image-generator-dialog.tsx` sedan fas 2 men aldrig definierad → footer
    föll tillbaka till `py-3` på iPhone home-indicator-enheter).
  - **P0 #2** — iOS Safari auto-zoom-fix i hela wizarden. Alla `TextField`/
    textarea-fält i `step-primitives.tsx` + inline input/textarea/raw
    `<input>` i `content-step.tsx` (16 träffar), `foundation-step.tsx` (1) och
    `company-step.tsx` (1) gick från `text-[13px]` → `text-base md:text-[13px]`.
    Tidigare bara `prompt-builder` + dialogs adresserade i fas 2.
  - **P0 #3** — Mobile steg-chips i `discovery-wizard.tsx`. Tidigare `h-5 w-5`
    (20px) utan `min-tap`; nu `min-tap sm:min-tap-0` + `h-7 w-7` +
    `active:scale-95` + `aria-current="step"`.
  - **P1 #7** — Wizard footer-knappar (Tillbaka, Hoppa över, Fortsätt, Skapa
    sajt) fick `min-tap sm:min-tap-0`.
- `6e06129` fix(viewser): scout P1 batch.
  - **P1 #4** — `viewer-panel.tsx` hydration mismatch. `useState`-initializer
    läste sessionStorage SYNC → server "full"/klient "mobile" missmatch. Nu
    useState init = "full", async-IIFE-effect läser storage post-mount, en
    `deviceHydratedRef`-flagga förhindrar default-skrivning över sparad preset.
  - **P1 #5** — `FloatingChat` layout-flash. `useIsMobileViewport` startade
    false → desktop-placeholder syntes 1 frame innan effect. Nu
    `useIsomorphicLayoutEffect` (useLayoutEffect klient/useEffect server) +
    matchMedia-läsning innan paint.
  - **P1 #6** — iOS keyboard överlappar bottom-sheet composer. Ny
    `useKeyboardInset`-hook via `window.visualViewport`. Mobile aside får
    `style={{ bottom: inset, transition: "bottom 0.18s ease-out" }}` så
    panelen glider ovanför tangentbordet.
  - **P1 #8 + #15** — `ModePill` i prompt-builder min-tap + `aria-label`
    "Ny sajt-läge" för konsistens med "Följdprompt"-pillen.
  - **P1 #9** — compare-modal A/B-pill desync. `goToPane` anropar nu
    `setActivePane(target)` SYNC före `scrollIntoView`.
  - **P1 #10** — Ingen focus-flytt FAB → öppen chat. Ny `expandAndFocus`-
    callback + `composerRef` på composer-textarean. Båda FAB-onClick använder den.
  - **P1 #11** — Site Inspector saknade bottom-sheet drag-handle på mobil
    trots kommentar. Manuell `<div className="bottom-sheet-handle md:hidden" />`
    direkt i SheetContent + `max-md:pt-2` på SheetHeader.
  - **P1 #12** — Inspector refresh-knapp + alla `FloatingChat` mikro-kontroller
    (iterera-X, förslag-toggle, quick-prompt chips, bilaga-X) fick
    `min-tap sm:min-tap-0` + `active:scale-95`.
  - **P1 #14** — `sm:text-[15/13px]` zoom-risk på iPad portrait. `prompt-builder`
    hero-textarea + `floating-chat` composer + `color-picker` hex-input bytta
    till `md:text-[...]` (768px-breakpoint säkrare än 640px).

Inga off-limits-paths rörda i någon av faserna eller scout-fixes-passet.
Komplett check-svit grön (sprintvakt, focus, governance, rules-sync,
term-coverage --strict, ruff, tsc, ESLint, pytest 540+).

Mobile hero-flow — completed (in-review). `GAP-viewser-mobile-hero-flow`
adresserade tre fynd från manuell test på iPhone 14 Pro-viewport (393×852)
som scout-rapporten inte täckte. Operatör-driven post-scout-fix:

- `viewer-panel.tsx` mobile hero stacked layout. SM_hero.mp4 hade
  `[object-position:78%_center]` (designat för desktop bredd) → 3D-objektet
  hamnade bakom rubriken på mobil. Operatören levererade SM-mobile.mp4
  (960×960 fyrkantig, 1.1MB, off-white #f0f2ed) som mobile top-banner.
  Container blev `flex flex-col md:flex-row` med `bg-[#f0f2ed]
  md:bg-background` när hero visas så filmens bakgrund flyter sömlöst in
  i canvasen. Hero-text staplad under videon på mobil (centrerad), absolute
  overlay vänsterställd på desktop (oförändrat).
- Hero-rubriken hade hårdkodad `<br />` + `max-w-lg` → radbröts till
  "Beskriv / din sajt / så bygger / vi den" på 393px. `<br />` borttagen;
  texten flödar nu naturligt via text-balance.
- `wizard-types.ts` foundation-validering: företagsnamn-min-längd-kollen
  borttagen på operatör-begäran så snabb-test av wizarden går smidigare.
  Övriga foundation-validations (offer.length ≥ 3, businessFamily required)
  kvarstår som signal till pipeline.

Scout pass 4 — `GAP-viewser-mobile-hero-safe-zone` (in-progress). Operatören
körde fjärde scout-bug-hunt (composer-2.5-fast, read-only) på de tre senaste
commits innan PR-update. Inga P0 men tre konkreta P1:

- `viewer-panel.tsx` mobile hero safe zone. På iPhone SE (375×667) räckte
  inte 667px för video~300px + text~200px + PromptBuilder~150px → hero-
  underrad döljdes bakom composern. Container fick `md:overflow-hidden`
  + `overflow-y-auto bg-[#f0f2ed]` när `showHero=true` (desktop oförändrad).
  Hero-text container fick `pb-40 md:pb-0` så composer-overlap aldrig sker
  vid normal text. Desktop absolute-overlay-layout intakt.
- `foundation-step.tsx` + `company-step.tsx` Wizard-asterisk. Båda visade
  "Företagsnamn *" trots att validering togs bort i 59eed4c → WCAG 2.2-brott
  (visuellt obligatoriskt fält som går att lämna tomt). Label nu enbart
  "Företagsnamn" med `optional`-prop som FieldLabel renderar som "(valfritt)".
- `prompt-builder.tsx` composer safe-area. `pb-5 sm:pb-7` saknade safe-area-
  koll → composer-knappar 0px från iPhone X+ home-indicator. Bytt till
  `pb-safe-or-4 sm:pb-7` (samma standard som wizard-footer och FloatingChat).

P1 #4 (StackBlitz containerRef-höjd) parkerad eftersom default-mode
`local-next` inte påverkas — bara aktuell vid `VIEWSER_PREVIEW_MODE=auto`
eller `stackblitz` (icke-default operatör-val).

Nya PRs sedan föregående checkpoint: PR #114 — chore(gitignore): re-ignore
`__pycache__/` under `packages/generation/build/` (B146 fallout); PR #115 —
sync(jakob-be -> main): #114 gitignore hygiene (post-#113 cleanup);
PR #135 (B155 backend — applied-effect-detektion + trace-event för fri
follow-up); PR #136 (B157 + BO6 + B155-backend + quality-gate routes-discovery);
PR #137 (B157 level 4 immutable build-dir + pointer-swap + GC). Main-HEAD
nu `40b7d29` (post-merge in i christopher-ui via merge-commit pending push).

Öppen PR utanför vår lane:

- **#116** (`cursor/dossier-candidate-intake-895d`) — `feat(backoffice): add dossier
  candidate intake from local files`. Backoffice-feature, ägs av jakob-be-lane.
  Do not start yet från christopher-ui's perspektiv.

### 2026-06-01 UTC — current-focus.md före `efbb425`

Last verified state: `efbb425` i `main` (2026-06-01 UTC, steward-auto efter PR #139 — sync: christopher-ui → main, UI/UX-batch + B155 UI + ADR 0034 väg B-UI). `jakob-be` har mergat in `origin/main` och bär de 10 backend-commitsen (topp `f62bd40`: ADR 0034 väg A copyDirectives, contact-route eval-fix, placeholder-contact-suppression) ovanpå — sync-PR `jakob-be → main` är nästa steg (kräver operatörs-OK + ev. live-test). Tre read-only scouts 2026-06-01 PM: backend-diff grön, PR-triage + #139-djupgranskning utan blocker. Alla guards gröna (governance, rules_sync, term_coverage --strict, ruff, sprintvakt) + 25 nya copydir-tester. **Riktigt LLM-anrop verifierat** (copyDirectiveModel, ej mock).
Nya PRs sedan föregående checkpoint: PR #139 — sync: christopher-ui → main (UI/UX-batch + B155 UI + ADR 0034 väg B-UI), mergad. Öppna nu: #140 (`cursor/preview-runtime-bite-b-di → jakob-be`, draft, Bite B via dependency-injection), #138 + #141 (docs Cloud-setup till `main`, draft; #141 har en term-coverage-enradsfix kvar). Kommande: sync-PR `jakob-be → main`.

Aktuell priordning + färsk orchestrator-handoff: se
[`docs/handoff.md`](handoff.md) toppblocket. Kort: #139 (UI-batch inkl. B155
FloatingChat-no-op + copyDirectives väg B-UI) är mergad till `main`. Nästa:
(a) sync-PR `jakob-be → main` för backend väg A + eval-/placeholder-fixar
(operatörs-OK); (b) Bite B (#140) mergas in i `jakob-be`, helst före sync-PR;
(c) tre låg-impact UI-fynd kvar i Christophers lane. B157 nivå 4 (Stage A+B)
ligger redan i `main`.

### 2026-06-01 UTC — current-focus.md före `4c473cb`

Last verified state: `4c473cb` (2026-06-01 kväll UTC, `jakob-be` hardening +
PR #143 + Codex-review-fixar (B161/B162), ovanpå PR #142-synken `fb3b1f8`; EJ i
`main` än — sync-PR **#144** öppen och väntar leveransfönster-OK). `origin/main`
(`48d5ca0`) är fullt innehållen i `jakob-be` → sync-PR är konfliktfri (jakob-be
10 commits före, 0 efter). Bug-scope nu: **15 aktiva / 135 stängda**.
Nya commits sedan föregående checkpoint (alla på `jakob-be`, opushad mot `main`):
- `74ed629` fix(dev): kill-dev-trees fångar orphan preview/dev node-processer
  (föräldraträd-matchning + TCP-port-lyssnare 3000-3001/4100-4199 + `--dry-run`/
  `--verbose`).
- `2e0c55f` fix(hardening): B158 (hero släpper placeholder-`tel:`), B159
  (kontaktsida/`/hitta-hit` får ärlig kontakt-CTA), copyDirective-edge-cases
  (namn-scope / reject-ord-boundary / trailing-instruktion), Streamlit-floor
  `>=1.49`. Fulltestad, 7 explicita filer.
- `a90215e` fix(discovery): B120 stad-extraktion läser alla addressLines +
  flerordiga orter.
- `d036067` docs(steward): known-issues stänger B158/B159, B120-progress + ny
  B160 (logo-Image, Christopher-lane), B155-hardening-not, GAP-annotation,
  Christopher-handoff (`msg-0025`). Bug-scope: **15 aktiva / 133 stängda**.
- `a3c47a7` docs(focus): dokumenterade PR #143 + markerade #139 mergad.
- `2320e34` refactor(build): **PR #143 mergad** (squash, base `jakob-be`) —
  npm/subprocess-helpers flyttade till `packages/generation/build/subprocesses.py`;
  `scripts.build_site` behåller facade + re-export `run_npm` (monkeypatchbar).
  Behavior-preserving (AST-verifierad), Scout-grön, full pytest exit 0. PR-branch +
  duplikat `cursor/refactor-build-site-slice-1` raderade.
- `63e4758` fix(codex-review): B161 (okvoterad include-token "inkludera
  TEST-JAKOB i hero" → ej längre tyst no-op) + B162 (TS/Python-paritet i
  `local-preview-server.ts:readActiveBuildDir` — avvisar närvarande icke-string
  buildPath). tsc grön; nya tester. (B-IDs registrerade i steward-commit denna.)
Nästa: #140 Bite B-review (in i `jakob-be`), docs-PR #138/#141-konsolidering,
sedan sync-PR `jakob-be -> main` för hela batchen när operatören ger OK.

### 2026-06-01 UTC — current-focus.md före `53301c4`

Last verified state: `53301c4` (2026-06-01 sen kväll UTC, **PR #147
vercel-sandbox-adapter mergad till `jakob-be`** ovanpå **PR #140 Bite B
mergad till `jakob-be`** — `localRuntime`/`stackblitzRuntime` wirade via dependency
injection, env-styrt via `VIEWSER_PREVIEW_MODE`, paket→app-lager-regeln låst av
`test_preview_runtime_di.py`). Ovanpå PR #144-synken (hela hardening-batchen i
`main`, `origin/main` = `8f7dea5`) + docs-PR-konsolidering (#138/#141/#145 foldade
in i `AGENTS.md` `48adcde` och stängda). `jakob-be` innehåller hela `main`.
Bug-scope: **15 aktiva / 135 stängda**. Ovanpå detta är #146 Vercel
Sandbox-spike mergad (`58710ec`) som live-verifierad bevis-PoC (painter-palma
ready, cold-start ~29 s, desktop+mobil render OK, ~ett par ören; `stop()`+
`delete()` städade rent) — INTE adapter-promotion, ingen `PreviewRuntimeKind`/
registry/ADR/naming-ändring. Spike-helper bakom `VIEWSER_SANDBOX_SPIKE=1`.
Nästa (prioriteringsändring 2026-06-01 kväll, operatörsbeslut — INTE en ny
produktstrategi): multi-adapter/provider har varit riktningen länge (se
`runtime-adapter-plan.md` + ADR 0028/0030); vi **aktiverar nu Vercel-sandbox-
spåret före nivå 2 copyDirectives**. Spiken är nu gjord, live-verifierad och
mergad (#146) — väg (D) flag-gated PoC valdes och bevisade "kan vi skapa/visa
en isolerad preview stabilt?" (painter-palma, ~29 s cold-start, desktop+mobil
OK). Operatörsbeslut 2026-06-01: `vercel-sandbox` blir PRIMÄR preview-runtime,
`local-next` fallback, `stackblitz` pausad — se
[ADR 0033](../governance/decisions/0033-vercel-sandbox-primary-preview.md).
Adapter-slicen är nu mergad till `jakob-be` (#147, `53301c4`): `vercel-sandbox`
finns som opt-in PreviewRuntime-adapter (naming v19, `PreviewRuntimeKind`
utökad, delad DI-runner `vercel-sandbox-runner.ts` för spike-CLI + adapter;
`@vercel/sandbox` bara i `apps/viewser/lib`). Default-mode är fortfarande
`local-next` (inte flippad). Nästa: (a) sync-PR `jakob-be → main` (öppnad,
kräver operatörs-OK för själva main-merge) så Christopher kan pulla; (b) Bite C
— flippa UI-routen `app/api/preview/[siteId]` till `currentViewserRuntime()`
(Christopher). Prior skiss finns på `cursor/preview-runtime-adapters`.
Köat (efter sandbox-riktningen satts, ej parkerat): 4-case live Golden Path
(elektriker Malmö / frisör Göteborg / naprapat Stockholm / liten keramik-e-handel;
prompt → preview → följdprompt → ny version) och nivå 2 copyDirectives
(hero/services/about/CTA/ton; remappar INTE tjänstetext till tagline). Nivå 2
copyDirectives är **pausad** tills sandbox-riktningen är satt. Embeddings + fler
starters längre fram. Refaktor av stora Python-filer = max en liten
behavior-preserving slice som 20%-sidospår, aldrig huvudspår. Bite C (flippa
produktions-route `app/api/preview/[siteId]` till `currentViewserRuntime()`) =
Christopher/UI.

> Branchmodell-OBS (motsägelse att lösa): `docs/agent-prompts.md` säger ännu
> "vi jobbar på `main` + `backup-N`", medan denna fil + `branch-discipline.md`
> säger att Jakob default jobbar på `jakob-be` och Christopher på
> `christopher-ui` (PR mot `main` per leveransfönster). `jakob-be`/
> `christopher-ui` är den gällande modellen; `agent-prompts.md` behöver
> uppdateras (operatörsbeslut — ej ändrad i detta pass).

### 2026-06-02 UTC — current-focus.md före `093b31a`

Last verified state: `093b31a` (2026-06-02 UTC, `jakob-be` — extern-review-härdning ovanpå nivå 3a, inkl. P1 scope-leak-fix: planeraren låses nu till det target operatören bad om (`_plan_copy_directives_via_llm(target=rewrite_target)`), så en about-rewrite aldrig applicerar en services-directive eller tvärtom. Tidigare i denna härdning: vibe-"till"-läcka stängd, planner no-op-löfte (story-snapshot+restore), schema if/then. 9 nya regressionstester totalt; alla near-blockers stängda → sync-PR mergebar. EJ i `main` (väntar operatörs-OK). `main` = `2d636b0`. Föregående steward-checkpoint: `6c860ec`).
Nya PRs sedan föregående checkpoint: inga (#148 var senaste sync till `main`).

### 2026-06-02 UTC — current-focus.md före `8a86593`

Last verified state: `8a86593` (2026-06-02 EM UTC, `jakob-be` = `8a86593`, i sync, rent träd, 10 commits före `main` = `619454c`. Hela copyDirective-batchen (nivå 1→3a + modulutbrytning + P2-grounding + kontakt-ärlighet) + docs-PR #151/#152 in-mergade. Enda öppna PR: #150 (christopher-ui, hålls). Sessionsavslut — handoff till nästa orchestrator ligger överst i docs/handoff.md. Nästa: sync-PR jakob-be→main (operatörsbeslut) + trust/branschcopy-slice).
Nya PRs sedan föregående checkpoint: PR #149 (mergad). **Öppen nu: PR #150**
(christopher-ui) — se nedan.
