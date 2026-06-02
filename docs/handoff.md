# Handoff – Sajtbyggaren

**Datum:** 2026-06-02 UTC. `jakob-be` = `65aa733` (copyDirective-modulutbrytning
+ P2 grounding-härdning). `main` = `b027b70` (PR #149: 2a/2c + 3a + härdning).
`jakob-be` är 3 commits före `main` (modulutbrytning + P2 + steward).
**Öppen PR: #150 (christopher-ui)** — stor auth/billing/starters/UX-batch,
CONFLICTING, operatörs-scope-beslut (se current-focus). Backend-lanen blockeras ej.

## Lovable-gap-audit 2026-06-02 (read-only) — var 4–5/10 → 9/10-gapet sitter

Statisk Scout-audit mot de fyra baseline-casen (elektriker Malmö / frisör
Göteborg / naprapat Stockholm / keramik-e-handel). **Kalibrering:** senaste
golden-path på disk (`golden-path-20260601T084107Z`) = **7,73/10, embeddings-gate
go**, men mäter scaffold/routes/nyckelord/sektionsantal — INTE upplevd finish.
Subjektiv "vill jag fortsätta?" landade på **2/5** för alla fyra → coachens 4–5/10
är rätt. `copySpecificity` 4,5–5,5 är svagast i eval; `mobileFirstFirstImpression`
9,5 är en sektionsräkning (ej riktig mobilpreview).

**Topp-gap (rangordnat, mest backend):**
1. Platshållarkontakt renderas rakt av (`prompt_to_project_input.py` default-input;
   `render_section_contact`) → flaggas men lätt att missa. **jakob-be + UI.**
2. Tomma `trustSignals` + clinic `credentials` renderas ej (`renderers.py`
   ~1062–1097; `trust-proof` returnerar "" på tom lista). **jakob-be (brief/plan).**
3. Generisk story/tagline/FAQ-mall (`prompt_to_project_input.py` ~950–971;
   `_render_home_faq_section`). **jakob-be.**
4. Tunt erbjudande (1 tjänst/produkt). **jakob-be.**
5. Hero-CTA = 3-stryks whitelist (`build_site.py` ~2350–2479), ej följdbar. **jakob-be (kontrakt).**
6. Följdprompt osynlig i UI för about/services (`floating-chat.tsx` ~349–410;
   `build-changes.ts` = prompt-heuristik). **christopher-ui.**
7. Visuell finish (gradient/blob, få riktiga bilder). **jakob-be + UI media-steg.**
8. Eval överskattar: `contactPath` straffar `/kontakta-oss`, mobil = sektionsräkning
   (`run_golden_path_eval.py`). **jakob-be (eval-fix, billig).**

**Embeddings:** parkerad bekräftad — alla fyra case träffar rätt scaffold, så
selection är inte problemet; embeddings hjälper inte placeholder-kontakt/tom trust.

**Öppna produktfrågor till operatören (måste besvaras innan trovärdighets-slicen):**
1. Ska placeholderkontakt vara kvar (demo) eller döljas tills wizard/scrape fyllt?
2. Var ska trust/recensioner/credentials komma från — briefModel, hårdkodade
   branschsnippets, eller wizard-steg?
3. Naprapat: acceptera `/kontakta-oss` + "Boka tid" (eval-fix) eller normalisera till `/kontakt`?
4. Mäta Lovable-gap med samma golden-path eller lägga till ett manuellt human-scorecard?
5. Nästa sprint: backend trovärdighets-slice vs christopher-ui FloatingChat-synlighet — eller parallellt?

## Session 2026-06-02 em (forts) — P2 grounding-härdning

Ovanpå modulutbrytningen (`8f2fc1e`) landade P2-batchen `65aa733` (Scout-plan ->
self-Builder -> Scout RO-review GO -> push):
- **(A)** `_extract_copy_directives_via_llm` begränsad till company-name|tagline;
  about/services-generering bara via planner-vägen (stänger hålet där en vag
  icke-rewrite-prompt kunde applicera ogrundad genererad about/service-copy).
- **(B)** Grounding-guarden breddad: `_PLANNED_NUMBER_RE` ((?<!\d)\d{2,}...) fångar
  årtal/priser/antal/procent; **whole-token-matchning** mot tokeniserad grounding
  (ej substring → "500" grundas inte av "5000"). Endast planner-vägen. Namn/orter/
  certifieringar = systemprompt + dokumenterad begränsning.
- **(C)** Project DNA-refresh: `_copy_directive_dna_refresh` markerar story/tagline
  `source=followup` när ett copyDirective ändrat fältet trots no-semantic-change-
  intent; gated på faktisk värdeskillnad (byte-stable-kontraktet intakt).
- **(D)** ADR 0034: "Nuvarande kontrakt"-stycke + historik-märkning.
- 92 copydir-tester (2 omskrivna → no-op + 5 nya), full pytest grön, alla guards.
- **Kvarvarande icke-blockerande P2-noteringar** (Scout): test för DNA-refresh
  vid no-op token-directive + tagline-DNA-refresh under no-semantic-change saknas
  (täckta i kod, ej testade); namn/ort/cert-grounding är medveten begränsning.

## Session 2026-06-02 em — copyDirective-modulutbrytning integrerad

Builder-agent (separat) körde `docs/agent-prompts/copydirective-module-extraction.md`
och committade `8f2fc1e` lokalt på `jakob-be` (opushad). Orchestrator tog emot:
Scout RO-review (GO — full AST-paritet, 4-fils-scope, acyklisk import, façade
komplett, grounding-guard oförändrad, `_copy_directive_llm_eligible` kvar i PI) +
integrations-gate (ruff 0, governance 18/18, rules-sync, term-coverage,
test_followup_copy_directives 88 + test_prompt_to_project_input gröna) -> pushad
till `origin/jakob-be`.

- copyDirective-delsystemet bor nu i `packages/generation/followup/`
  (`text.py` delade lågnivåhjälpare inkl. `_customer_safe_planner_note`-klustret;
  `copy_directives.py` hela systemet verbatim; `__init__.py`).
  `scripts/prompt_to_project_input.py` slimmad (~1158 rader bort), behåller
  follow-up-orkestrering + intent + `_MISSING_STORY` + façade-re-exports.
- **Nästa (coach-rekommenderad ordning):** (1) P2 grounding-fixar (extraction-väg
  #4 + bredare guard + Project DNA-refresh #5 + ADR 0034-städning); (2) Lovable-
  gap-audit + Golden Path på fyra baseline-case (read-only, parallellt);
  (3) embeddings = nästa-NÄSTA (ej nu). Christopher-lane: Bite C + FloatingChat/
  AppliedCopyDirective-ärlighet (#3), och scope-beslut om PR #150.

## Tillägg 2026-06-02 — sync-PR #149 + review-loop (Codex/Vercel)

Sync-PR **#149** (`jakob-be -> main`) öppnad. Review-loopen (Codex code review +
Vercel Agent Review + ai-bug-review) körde flera rundor; alla **P1 åtgärdade**,
P2 nedan kvar som follow-ups.

Åtgärdade i PR #149 (efter öppning):
- Codex-review (prio 1, `dd2be86`): planner-services-rewrite måste peka på den
  namngivna tjänsten — `_plan_copy_directives_via_llm(target=...)` + service-
  identitets-matchning (id-vs-label-säker); fel/okänd tjänst → no-op.
- Vercel-review (`2e121a2`): no-op-löftet vid avsaknad initial story — story
  snapshottas med `_MISSING_STORY`-sentinel och återställs exakt (tar bort
  semantisk tilllaggning om story saknades).
- Codex-review (prio 2, vibe-läcka tagline): rewrite-verb (skriv om/förbättra/...) på
  name/tagline kräver nu citerat/kolon-värde (plain set-verb behåller löst
  trailing) — "skriv om hero till mer premium" publicerar inte längre
  "mer premium" som tagline.

**Kvarvarande P2 (icke-blockerande, follow-ups):**

1. **Unquoted service-ref utan "till"** (`förbättra tjänsten Örhängen så ...`)
   → no-op idag (kräver citat eller "till"). UX-förbättring; medveten
   leak-säker default. Tas ev. i modulutbrytningen/efteråt.
2. **Generation via extraktions-vägen:** `_extract_copy_directives_via_llm`
   accepterar about-text/services-targets utan grounding-guard, så en vag prompt
   ("fixa om oss-texten lite") skulle kunna applicera modell-genererad copy
   utan planner-guarden. Designbeslut: antingen begränsa extraktions-vägen till
   company-name/tagline (gör vaga icke-rewrite-prompter till no-op — ändrar
   2a/2c LLM-testerna) eller applicera grounding-guarden även där. Rekommenderas
   tas i copyDirective-modulutbrytningen.
3. **Viewser `AppliedCopyDirective`** (`apps/viewser/lib/runs.ts`) känner bara
   company-name|tagline + droppar payloads >200 tecken → about-text/services/
   planerade rewrites visas inte i FloatingChat. **Christopher-lane.**
4. **Project DNA-refresh:** en about-text-replace uppdaterar `company.story` men
   prompten klassas no-semantic-change (om oss ∉ story-keywords), så DNA-
   snapshotten markerar inte story som followup-uppdaterad. Versionsnyans; tas
   med modulutbrytningen.

## Tillägg 2026-06-02 — P1 scope-leak-fix (extern-review-runda 2)

Coach-review fann en P1 ovanpå härdningen: `_plan_copy_directives_via_llm`
filtrerade inte planner-output mot det target operatören bad om, så en
about-rewrite kunde applicera en services-directive (eller tvärtom) om
copyDirectiveModel returnerade fel target. Fix (`093b31a`): planeraren tar nu
`target=rewrite_target` och droppar varje directive vars target inte matchar.
2 nya regressionstester (about-rewrite droppar planner-service-directive +
omvänt). Scope-leak låst i kod, inte bara systemprompt. Alla guards gröna.

## Session 2026-06-02 fm (forts) — extern-review-härdning + nästa-fas-handoff

Två externa reviewers (operatören bad uttryckligen om buggjakt) gav ~8/10 med
två near-blockers före sync-PR. Båda åtgärdade på `jakob-be` (`6c860ec`):

- **Vibe-"till"-läcka (near-blocker):** about-text/services krävde tidigare bara
  ett fritt trailing "till <rest>" som värde. "skriv om om oss till mer
  personligt" hade då satt `company.story = "mer personligt"` (instruktion som
  kundcopy). Fix: `_extract_explicit_replace_value` (endast citat/kolon) används
  för about-text/services och i `_has_explicit_copy_value`; sådana vibe-prompter
  går nu till planeraren eller blir no-op. company-name/tagline behåller löst
  trailing (korta labels).
- **Planner no-op-löfte (near-blocker):** när planeraren är på men ger `[]`
  (saknad nyckel / dropp) får en about-rewrite INTE falla tillbaka på en generisk
  story-emphasize-append. `merge_followup_project_input` snapshottar story före
  `_apply_semantic_patch` och **återställer** den om ingen about-text-directive
  applicerades (`_content_rewrite_target` exponerar målet; bara aktiv när planner
  enabled). `_apply_semantic_patch`/`classify_followup_intent` orörda.
- **Schema if/then (governance-härdning):** `directives.copyDirectives`-items
  fick `allOf` med if/then — target=services kräver `targetRef`; about-text/
  services låsta till `replace-text`. Speglar Python-kontraktet.
- 7 nya regressionstester (vibe-läcka, strikt trailing no-op, planner-[]-no-op
  för både tone-shift- och story-emphasize-prompt, schema-avvisning). Alla guards
  gröna; full pytest grön (orphan dev-trees rensade före).

**Reviewer-noterade follow-ups (ej blockers):**

1. **copyDirective-modulutbrytning (NÄSTA, reviewer-rekommenderad):**
   `scripts/prompt_to_project_input.py` är för central. Bryt ut
   copyDirective-delsystemet till egen modul innan fler targets byggs.
   Behavior-preserving. Builder-prompt:
   [`docs/agent-prompts/copydirective-module-extraction.md`](agent-prompts/copydirective-module-extraction.md).
2. **Bredare grounding-guard:** editPlan-grundnings-guarden skyddar bara mot
   ogrundade årtal idag; bredda till siffror/priser/orter/personnamn/
   certifieringsord innan LLM-genererad about-copy litas på i skarp demo.
3. **UI-gap (Christopher-lane):** FloatingChat/`AppliedCopyDirective` ger
   heuristisk prompt-summary, inte faktisk applied-directive-diff, och känner
   bara company-name|tagline. Synka about-text/services/planerade rewrites där.
4. **ADR 0034 dokumentationsdrift:** dokumentet blandar "first slice"/nivå 2/3a;
   städa status + kontrakt så det matchar faktisk implementation.
5. **Sync-PR `jakob-be -> main`** (2a + 2c + 3a + härdning) — nu mergebar,
   operatörsbeslut.

## Session 2026-06-02 fm — copyDirectives nivå 3a (editPlan-planerare)

Orchestrator-pass (Scout -> self-Builder -> Scout RO-review -> Steward), branch
`jakob-be` direkt, ingen main-sync.

- **Nivå 3a (`4d08526`):** editPlan-planerare. Vid en **rewrite-instruktion utan
  angivet värde** ("skriv om om oss så det låter mer personligt") läser
  `_plan_copy_directives_via_llm` sajtens site-state
  (`_build_site_state_for_copy_planning`) och låter copyDirectiveModel
  **generera** ny copy för `about-text` (company.story) och `services`
  (services[].summary). Detta är första gången modellen genererar kundcopy
  (tidigare bara extraherade explicit copy). Fortfarande **väg A** (strukturerade
  fält före render), INTE väg C (ingen `.generated/`-patch).
- **editPlan = planeringssteg** som producerar vanliga validerade
  `copyDirectives[]` via befintlig leak-säker apply. Inget nytt schemafält,
  `source="llm"`, **schema oförändrat**.
- **Eligibility (egen gate):** `_is_content_rewrite_request` = rewrite-verb
  (`_COPY_CONTENT_REWRITE_VERBS`: skriv om/formulera om/omformulera/förbättra/
  snygga till/rewrite/reword/improve) + INGET explicit värde
  (`_has_explicit_copy_value`) + target about-text|services + (services)
  namngiven tjänst (targetRef). Körs i egen `if/elif`-gren i
  `merge_followup_project_input` FÖRE extraction-eligibility.
- **Ingen regress:** `classify_followup_intent` + `_apply_semantic_patch` är
  OFÖRÄNDRADE. about/services (planner) och tone/tagline (semantic patch) är
  olika fält → "skriv om om oss ..." kan ge BÅDE en ton-shift och en
  story-rewrite utan klobbning. Alla 2a/2c + tone-shift-tester gröna.
- **Skydd:** generation-scope dubbel-enforced (systemprompt + kod-dropp av
  targets utanför {about-text, services} — name/tagline genereras aldrig); samma
  `_safe_copy_payload`-guards på genererad payload + grundnings-guard
  `_planned_payload_grounded` (dröppar payload med 4-siffrigt årtal som inte finns
  i site-state/prompt → mot påhittade grundningsår).
- **Verifierare:** B155 `appliedVisibleEffect` (fil-diff). Separat `verifierModel`
  parkerad till nivå 3-fortsättning.
- **extract.py refaktorerad:** delad `_build_copy_directive_context` +
  `_run_copy_directive_model`; `extract_copy_directives_llm` (extraction,
  `_COPY_DIRECTIVE_SYSTEM`) + ny `plan_copy_directives_llm` (generation,
  `_COPY_DIRECTIVE_PLAN_SYSTEM`).
- **Governance:** llm-models v5->v6 (copyDirectiveModel-purpose breddad till
  editPlan-generering), naming-dictionary v21->v22, ADR 0034 implementationsnot
  2026-06-02 (väg A nivå 2 + 3a; tydligt skild från väg C). 17 nya tester.
- **Verifiering:** Scout RO-review GO (ingen scope-läcka; leak-kedja,
  gren-separation, generation-scope, grundnings-guard, governance-paritet OK).
  Guards: ruff 0, governance 18/18, rules-sync OK, term-coverage --strict 0, full
  pytest grön (orphan dev-trees rensade före körningen). 74 copydir-tester gröna.

### Nästa (copyDirectives-trappa)

1. **Nivå 3-fortsättning (NÄSTA, operatörsbeslut):** (a) multi-target editPlan
   (flera säkra edits i ett svar — befintlig dedupe på `(target, targetRef)`
   stödjer det redan i apply, planeraren kan returnera flera); (b) separat
   `verifierModel` som kontrollerar synlig effekt bortom B155-fil-diff; (c) väg
   B-UI för editPlan (FloatingChat visar planen + ärlig feedback — Christopher).
2. **Slice 2d cta/hero — PARKERAD:** kontraktsbeslut (hero-label är variant-
   whitelist), tas efter nivå 3-mönstret sitter.
3. **Sync-PR `jakob-be -> main`** (slice 2a + 2c + 3a) = operatörsbeslut.
4. **Christopher-lane-följd (växande):** Viewser `AppliedCopyDirective` i
   `apps/viewser/lib/runs.ts` + FloatingChat-summary känner bara company-name|
   tagline. about-text (2a), services+targetRef (2c) och planerade rewrites (3a)
   bör synkas där för ärliga FloatingChat-rader. Ej backend-blocker.

## Session 2026-06-02 morgon — copyDirectives slice 2c (services) + 2b-beslut

Orchestrator-pass (Scout -> self-Builder -> Scout RO-review -> Steward), branch
`jakob-be` direkt, ingen main-sync.

- **Slice 2b (`tone`) — HOPPAD** (operatörsbeslut). Den befintliga
  `tone-shift`-semantiska patchen mappar redan "gör tonen mer premium" ->
  `tone.primary`, så en tone-copyDirective hade mest överlappat: lågt mervärde,
  onödig regressrisk. Ingen tone-target byggd.
- **Slice 2c (`a346bd6`):** nytt target **`services` -> `services[].summary`**,
  replace-text only. Disambiguering via nytt optional **`targetRef`** (service
  id eller label) på copyDirective-objektet. Extraktorn fångar tjänst-referensen
  (quoted efter service-ankare, eller unquoted mellan ankare och "till") + det
  explicita nya värdet; `_apply_copy_directives` matchar `targetRef` mot
  `merged["services"]` (case-insensitiv NFKC på id ELLER label) och sätter
  `service["summary"] = payload`. **Ingen match = honest no-op** (skapar aldrig
  ny tjänst, hijackar aldrig annan tjänst). Filer: `prompt_to_project_input.py`
  (`_COPY_DIRECTIVE_SERVICES_KEYWORDS`, `_COPY_DIRECTIVE_NEW_SERVICE_GUARD`,
  `_extract_service_target_ref`, `_match_service_by_ref`, services-grenar i
  classify/extract/validate/apply, LLM-dedupe på `(target, targetRef)`),
  `brief/extract.py` (target += services, `targetRef`-fält, services-lista i
  context, systemprompt: matcha befintlig tjänst, skapa aldrig ny), schema
  (target-enum += services, nytt optional `targetRef` maxLength 80), naming-
  dictionary v20 -> v21, 13 nya tester.
- **Skydd/no-op verifierat:** services-grenen fyrar bara utan explicit
  företagsnamn-keyword (så "ändra företagsnamnet (inte tjänsten) till X" förblir
  company-name — befintligt test grönt); additiv "ny tjänst" -> no-op; onamngiven
  "ändra tjänsten till X" -> no-op; okänd tjänst -> no-op.
- **Verifiering:** Scout RO-review GO (ingen scope-läcka; leak-säkerhet, hijack/
  no-op, merge-ordning efter `_merge_services`, schema/policy/Pydantic-paritet
  OK). Guards: ruff 0, governance 18/18, rules-sync OK, term-coverage --strict 0,
  full pytest grön (orphan dev-trees rensade med `kill-dev-trees.py` före
  körningen så api-smoke-flaken inte slog till). 57 copydir-tester gröna.

### Nästa (copyDirectives-trappa)

1. **Slice 2d — `cta`/hero (NÄSTA).** Kräver designbeslut innan Builder:
   hero-knappens text är en variant-whitelist i `build_site.py`, inte fri text,
   så detta är en kontraktsändring (ny `conversionGoals`-slug vs nytt PI-fält
   vs begränsad replace mot befintliga labels). Operatörsbeslut.
2. **Nivå 3:** site-state reader + edit planner -> multi-target editPlan +
   verifierModel + ärlig chatt. "Förstår hela sidan"-känslan. Stegvis, inte fri
   kodpatchare. Nivå 4 = patch/diff med rollback.
3. **Sync-PR `jakob-be -> main`** (slice 2a + 2c) = operatörsbeslut (ej öppnad).
4. **Christopher-lane-följd:** Viewser `AppliedCopyDirective`-typen i
   `apps/viewser/lib/runs.ts` + FloatingChat-summary känner bara till
   company-name|tagline. about-text (2a) och services+targetRef (2c) bör synkas
   där så FloatingChat kan visa ärliga rader ("Jag uppdaterade tjänsten ..."). Ej
   backend-blocker (direktiven appliceras ändå vid bygget); UI-lane.

## Session 2026-06-02 natt — copyDirectives slice 2a (about-text) landad på jakob-be

Orchestrator-pass (Scout -> self-Builder -> Scout RO-review -> Steward), branch
`jakob-be` direkt enligt operatörsval, ingen main-sync.

- **Steg 0 (steward, `061dc1c`):** återinförde Nästa-blocket i
  `current-focus.md` (auto-bumpen hade tagit bort det) och rättade stale
  påstående om att copyDirectives väg A inte var i `main` (den är, via
  #142/#144/#148). Guards gröna.
- **Slice 2a (`a1e2502`):** ADR 0034 väg A nivå 2, första slicen.
  Nytt copyDirective-target **`about-text` -> `company.story`** (om oss-/
  berättelse-copy), **replace-text only** (ingen include-token). Filer:
  `scripts/prompt_to_project_input.py` (`_COPY_DIRECTIVE_ABOUT_KEYWORDS`,
  about-gren i `_classify_copy_target`/`_extract_copy_directives`,
  per-target maxLength + include-token-dropp i
  `_validate_copy_directive_candidate`, apply -> `company.story`, nya
  rewrite-verb skriv om/formulera om/omformulera/rewrite/reword som bara
  aktiveras med explicit värde), `packages/generation/brief/extract.py`
  (copyDirectiveModel-target += about-text + story-kontext + systemprompt
  som inte genererar copy ur en vibe), schema (target-enum += about-text,
  payload maxLength 200 -> 600), naming-dictionary (v19 -> v20), 12 nya
  tester.
- **Operatörsbeslut (slice 2a = about-only):** ingen tone/services/cta i 2a.
  Tone togs bort ur 2a eftersom det krockar med befintlig `tone-shift`-
  semantisk patch (dubbel effekt + leak-risk i `tone.primary`).
- **Viktig gräns (nivå-3-avgränsning):** en vibe-rewrite utan angivet värde,
  t.ex. "skriv om om oss så det låter mer personligt", är **honest no-op** i
  2a. Den klassas dessutom som `tone-shift` av `classify_followup_intent`
  (för att "mer personlig(t)" matchar en ton-fras), så den deterministiska
  about-vägen fyrar inte. Äkta innehållsgenerering ("LLM skriver om
  sektionen") hör hemma i nivå 3 (site-state reader + edit planner), inte i
  denna deterministiska slice — peta INTE i intent-klassificeraren för att
  tvinga fram det (regressionsrisk mot tone-shift).
- **Verifiering:** Scout RO-review GO (ingen scope-läcka, leak-säkerhet +
  schema/policy/Pydantic-paritet + merge-ordning OK). Guards: ruff 0,
  governance 18/18, rules-sync OK, term-coverage --strict 0, full pytest
  grön. Enda röda i full-körningen var den dokumenterade miljö-flaken
  `test_api_prompt_route_spawns_python_end_to_end` (orphan `next dev`-
  processer blockerade porten) — `python kill-dev-trees.py` städade 3 orphan-
  träd, testet grönt isolerat efteråt.

### Nästa (copyDirectives-trappa — se current-focus.md Nästa-blocket)

1. **Slice 2b — `tone`.** Beslut innan Builder: (a) tone-copyDirective fyrar
   bara på explicit citerat värde -> `tone.primary`, luddigt lämnas åt
   befintlig semantisk `tone-shift`-patch (rekommenderat, inget regress),
   eller (b) ingen tone-copyDirective alls. Operatörsbeslut.
2. **Slice 2c — `services`** (services[].summary): kräver vilken-tjänst-
   disambiguering + starka scope-keywords (tjänstetext får aldrig bli
   tagline/about).
3. **Slice 2d — `cta`/hero:** kontraktsändring (hero-label är variant-
   whitelist i `build_site.py`), inte bara enum. Sist.
4. **Nivå 3:** site-state reader + edit planner -> multi-target editPlan +
   verifierModel + ärlig chatt. "Förstår hela sidan"-känslan börjar här.
   Byggs stegvis, inte som fri kodpatchare. Nivå 4 = patch/diff med rollback.
5. **Sync-PR `jakob-be -> main`** för slice 2a är operatörsbeslut (ej öppnad).

## Session 2026-06-01 sen kväll — Vercel Sandbox-spike + ADR 0033 (runtime-riktning)

- **#146 mergad till `jakob-be`** (`58710ec`, squash): flag-gated Vercel
  Sandbox-PoC, **live-verifierad** (painter-palma `ready`, ~29 s cold-start,
  desktop+mobil render OK, `stop()`+`delete()` rent, ~ett par ören). Helper bakom
  `VIEWSER_SANDBOX_SPIKE=1`; ingen route/UI-wiring, ingen adapter-promotion.
- **Operatörsbeslut (ADR 0033):** `vercel-sandbox` blir PRIMÄR preview-runtime,
  `local-next` fallback, `stackblitz` pausad (får finnas kvar, blockerar inte, ej
  default, ej testkrav). Allt via `PreviewRuntime`-adapter; ADR 0030:s hårda regler
  står kvar (vanilla Next.js-output, inga `@vercel/*` i generation/starters,
  non-Vercel-fallback inwirad, Sajtbyggaren äger `data/runs`-sanningen, sandbox kör
  bara en ephemeral kopia).
- **Detta pass = governance/docs-slice** (ADR 0033 + current-focus + handoff +
  product-operating-context + `.env.example` + `commands.txt`). INTE adaptern:
  naming v18→v19, `PreviewRuntimeKind`-utökning, registry,
  `adapters/vercel-sandbox.ts` och ev. `preview-runtime-policy`-justering landar i
  en separat adapter-slice efter operatörs-OK (de är kopplade till
  cross-policy-tester, så blast-radius hålls utanför denna slice).
- `cursor/vercel-sandbox-spike`-branchen kvar; `apps/viewser/.env.vercel.local`
  (OIDC-token) är gitignored, ej committad. Ingen main-sync.

## Session 2026-06-01 kväll — #144 mergad till main + jakob-be synkad

Detta steward-pass: tog den gröna `jakob-be`-batchen officiellt in i `main` och
synkade tillbaka. Ingen ny feature startad.

- **CI-avblockning före merge:** sync-PR #144 var i själva verket RÖD —
  governance-testet `test_preview_runtime_forbidden_terms_are_in_globally_forbidden`
  failade för att hardening-batchen låste upp `VM`/`sandbox`/`Vercel Sandbox` som
  tillåtna alias i naming-dictionary men inte speglade det i
  `preview-runtime-policy.v1.json:forbiddenTerms`. Fix `d03dadd` tog bort
  `VM`/`sandbox`/`vercelSandbox` ur policyns forbidden-lista. (OBS: vill man
  behålla `vercelSandbox` som spärrad kodidentifierare, lägg tillbaka den i
  `previewRuntime.aliasesForbidden` — prosa-aliaset "Vercel Sandbox" är ändå
  tillåtet.)
- **Tre Vercel-Agent-review-fixar** (`e0e56ce`), var och en regressionstäckt:
  (a) `renderers.py:render_section_contact_info` fast-path filtrerar nu
  placeholder-adressrader i blandade adresser (`real_address_lines()`,
  byte-identiskt för helt riktiga adresser); (b) `pyproject.toml` streamlit-floor
  `>=1.39` → `>=1.49` (paritet med requirements.txt); (c) `kill-dev-trees.py`
  `matches_sajtbyggaren` faller tillbaka till cmdline på tom `scope_text` (var
  `is not None`). Tester: `test_contact_page_fast_path_drops_placeholder_address_line`,
  `test_pyproject_streamlit_floor_matches_requirements`,
  `test_empty_scope_text_falls_back_to_cmdline`.
- **#144 squash-mergad** till `main` (`fba03d0`) efter att CI var helt grön
  (governance, builder-smoke, GitGuardian, Vercel, Vercel Agent Review — alla
  SUCCESS, `mergeStateStatus: CLEAN`). `jakob-be` deletades INTE.
- **Sync:** `git merge origin/main` in i `jakob-be` (`939f684`) — konfliktfritt,
  trädet identiskt med `origin/main`. Medvetet merge, inte `reset --hard`, mitt i
  flödet. Pushad till `origin/jakob-be`.
- **Sanity:** full pytest grön (~2027 passerade; den enda röda i en mellankörning
  var en miljöflake — `test_api_prompt_route_spawns_python_end_to_end` mot en
  orphan dev-server, städad med `kill-dev-trees.py`, passerar isolerat). ruff
  rent, governance 18/18, rules-sync OK, term-coverage `--strict` rent.

**Nästa orchestrator:** (1) #140 Bite B — rebasa mot nya `jakob-be`, skala ned
till äkta PreviewRuntime-DI-scope (PR-diffen är uppblåst av stale base), review →
in i `jakob-be`. (2) Konsolidera docs-PR #138/#141/#145 (alla `AGENTS.md`
Cloud-setup) till EN, stäng övriga som duplicate. (3) Vercel preview-adapter
(operatörsval): egen ADR per ADR 0030 + naming-bump (`vercel` i
`PreviewRuntimeKind`) + `normalizePreviewMode`-mappning för sandbox/vercel + ny
`adapters/vercel.ts` + tester; börja med Vercel-sandbox-spåret. Ingen Vercel-kod
i `packages/generation/` (adapter-checklistan).

## Mini-handoff 2026-06-01 sen eftermiddag — copyDirective fix + runtime-ordval

- Verifierad och åtgärdad bug i
  `scripts/prompt_to_project_input.py:_extract_copy_directives`:
  `has_replace`/`has_include` använder nu ordgräns-matchning i stället för
  substring. Resultat: "Jag bytte företagsnamnet till X" triggar inte längre
  felaktig rename-directive, medan imperativformen "byt företagsnamnet till X"
  fortsatt fungerar.
- Ny regression i `tests/test_followup_copy_directives.py` låser scenariot
  "Jag bytte företagsnamnet till Ny Namn" => `[]`.
- Dokumentationsförskjutning för Preview Runtime: StackBlitz är inte ett hårt
  förkrav före VM-/Sandbox-adapter. Adapter-spår kan gå parallellt så länge
  canonical `Preview Runtime`-kontrakt och adapter-kind/fallback hålls.
- Naming-policy upplåst för ordbruk i prosa:
  `sandbox`/`VM`/`Vercel Sandbox`/`Vercel VM` är nu tillåtna alias för
  `Preview Runtime` (naming-dictionary uppdaterad); globalt förbud mot
  `vercel-sandbox` borttaget.
- Term-coverage uppdaterad så `Sandbox`/`Vercel Sandbox`/`Vercel VM` inte
  felklassas som nya domänbegrepp i docs/prosa.

## Session 2026-06-01 kväll — hardening landad + PR #143 refactor mergad

`jakob-be`-commits denna session (alla pushade, EJ i `main`):

- `74ed629` **kill-dev-trees**: fångar nu orphan preview/dev node-processer
  (föräldraträd-matchning + TCP-portlyssnare 3000-3001/4100-4199, `--dry-run`/
  `--verbose`). Validerad live: städade en orphan `next dev` (PID 9420) som
  blockerade `test_api_prompt_smoke` — testet blev grönt efteråt.
- `2e0c55f` **fix(hardening)**: B158 (hero släpper placeholder-`tel:`-CTA), B159
  (`render_contact`/`/hitta-hit` får ärlig kontakt-route-CTA), tre
  copyDirective-edge-cases (generiskt namn-scope → ingen company-rename vid
  tjänst/produkt/sida; reject-verb ord-boundary så "Changemakers" applicerar;
  okvoterad trailing "till/to" fångar ej instruktioner som copy), Streamlit-floor
  `>=1.49`. 7 explicita filer, fulltestad.
- `a90215e` **fix(discovery)**: B120 stad-extraktion läser alla `addressLines` +
  flerordiga orter (intl-format medvetet kvar = säker fallback).
- `d036067` **docs(steward)**: known-issues stänger B158/B159, B120-progress, ny
  B160 (logo aspect-ratio-varning i `next/image`, Christopher-lane), B155-hardening-not,
  GAP-annotation. Christopher-handoff
  `msg-0025` (B160 + #139-fynd + B155-honesty-koordinering).
- `a3c47a7` **docs(focus)**: dokumenterade PR #143, markerade #139 mergad.
- `2320e34` **refactor(build) — PR #143 mergad** (squash, base `jakob-be`):
  npm/subprocess-helpers (`run_npm`, `_sanitized_npm_env`, `_coerce_subprocess_text`,
  `_npm_step_result`, NPM_*_TIMEOUT) flyttade till
  `packages/generation/build/subprocesses.py`. `scripts.build_site` behåller
  facade + `run_npm = _subprocess_exports.run_npm` (call-sites använder bart
  modulglobalt namn → `monkeypatch.setattr("scripts.build_site.run_npm", …)`
  fungerar). Operatörens cloud-agent-arbete, rebasead mot senaste `jakob-be`,
  Scout-granskad GRÖN (behavior-preserving, AST-verifierad, scope = 3 filer,
  base `jakob-be`), full pytest exit 0. Branch + duplikat
  `cursor/refactor-build-site-slice-1` raderade.
- `63e4758` **fix(codex-review)**: två read-only-review-fynd stängda. B161
  (Låg-Medel): `_extract_include_token` extraherade bara citerade tokens →
  "inkludera TEST-JAKOB i hero" (okvoterat) var tyst no-op; nu fångas okvoterade
  token-lika ord (versal/siffra, ej keyword). B162 (Låg): TS
  `local-preview-server.ts:readActiveBuildDir` speglar nu Python exakt — avvisar
  närvarande icke-string buildPath (tidigare typeof-string-gate). tsc grön.
  Falskt larm i samma review: `_DISPATCHED_ICON_PATTERN` "saknas" — finns på
  `renderers.py:4983`, sviten grön. Bug-scope nu **15 aktiva / 135 stängda**.

**Lane-disciplin hölls:** all kod i backend/generation/scripts/docs.
`apps/viewser/lib/local-preview-server.ts` (B162) är run-shape = Jakob-owned per
`docs/gaps/README.md`. `apps/viewser/**` UI-presentationslager rördes inte
(Christopher-lane); UI-fynd (B160 logo, #139-trio, B155-honesty) handades av
via `msg-0025`.

**Branch-städ denna session:** raderade merged PR-branch
`cursor/build-site-py-refaktorering-b2c1` + duplikat `cursor/refactor-build-site-slice-1`.
Behållna (medvetet): backups (`backup-25/26-VIKTIG`, `backup-43/44/45`,
`backup-pre-christopher-ui-merge`), `christopher-ui`, öppna-PR-branchar
(`#140`/`#138`/`#141`), WIP-snapshots (`cursor/preview-runtime-adapters`,
`cursor/dossier-intake-v11-review-895d`).

**Nästa:** (1) #140 Bite B-review → in i `jakob-be`. (2) docs-PR #138/#141
konsolidering. (3) sync-PR `jakob-be → main` för hela batchen när operatören ger
OK (`jakob-be` får EJ `reset --hard origin/main` i mellanläget — merge/rebase in
`main`, lös docs-konflikter, öppna sync-PR). (4) Vercel/Sandbox = fortfarande senare.

## Orchestrator-pass 2026-06-01 PM — tre scouts gröna, #139 mergad

Tre read-only scouts kördes (ingen produktkod rörd):

- Backend-diff `jakob-be → main` (10 commits) bedöms grön. copyDirectives väg A
  (`641abc9`), contact-route eval-fix (`0ff7657` + `0cc146c`) och placeholder-
  contact-suppression (`f62bd40`) är säkra; noll scope-läcka mot Bite B eller
  Christopher. En gul copy-kvalitetsnot: okvoterad multi-clause-rename kan få med
  svansord i `company.name`; kvoterad form undviker den.
- PR-triage: fyra öppna PRs (#138–#141). Rekommenderad main-ordning är #139
  först, sedan sync-PR `jakob-be → main`.
- #139-djupgranskning: ready/clean, alla checks gröna. Bär både B155-no-op-signal
  och copyDirectives väg B-UI. Förbehåll: ingen godkänd review än (bekräfta
  bugbot-trådar), och additiv scope-läcka i `apps/viewser/app/api/prompt/route.ts`,
  `apps/viewser/lib/runs.ts` och `scripts/check_term_coverage.py` utan
  `[scope-leak]`-tagg (operatörsbeslut).

Status i sekvensen: (1) #139 mergad till `main` (`f22d27a`, steward-auto
`efbb425`). (2) `christopher-ui` resynkad till `origin/main` via
`--force-with-lease` (efbb425). (3) `jakob-be` har mergat in `origin/main` och
löst docs-konflikterna (`current-focus.md` + `handoff.md`). Kvar: öppna sync-PR
`jakob-be → main` (väntar operatörs-OK + ev. live-test). Bite B (#140) mergas
helst in i `jakob-be` före sync-PR så den följer med samma main-leverans.
Live-checkar före sync-merge: okvoterad rename i Viewser, sajt utan
kontaktuppgifter (inga dummyvärden men äkta data byte-identisk), och
`copyDirectiveModel` fyrar bara i Viewser-produktionsflödet med nyckel.

## Status (2026-06-01) — ADR 0034 väg A first slice landad på jakob-be

**Det riktiga LLM-flödet är igång (nivå 1).** Fri följdprompt → validerade
`directives.copyDirectives[]` → synlig, spårbar sajt-ändring, utan att rå
prompt läcker som kundcopy. Detta är "LLM-driven intent → säker deterministisk
applicering", inte direkt modell-patch av genererad kod (väg C, parkerad).

- `641abc9` `feat(followup)`: copyDirectives first slice. Schema
  `directives.copyDirectives` (strikt enum: target `company-name | tagline`,
  operation `replace-text | include-token`, payload validerad maxLength 200,
  source). Deterministisk läck-säker extraktor + dedikerad
  **`copyDirectiveModel`-roll** (llm-models v5, EJ återanvänd briefModel) +
  resolver; LLM-output genom samma copy-validator som deterministiska direktiv,
  aktiv bara i produktions-CLI:t (Viewser `--followup-site-id`).
  Naming-dict v18 (Copy Directive). 25 nya tester. Real-LLM-smoke verifierad:
  "kalla firman X istället" → `company.name`-rename, `source=llm`,
  `appliedVisibleEffect=true`, token i `app/page.tsx`.
- `0be2f42` `docs(agent-prompts)`: Christopher-handoff för väg B.

**Kvar på copyDirectives-gapet (förblir öppet):** väg B ärlig
FloatingChat-feedback (Christopher/UI — handoff finns), bredare targets
(story/services/about/all-copy = nivå 2), väg C (modell patchar `.generated/`
direkt — kräver sandbox/diff/rollback/Quality Gate, egen ADR).

## Priorordning nu (2026-06-01)

1. **Operatör-review / live-test** av `641abc9` i Viewser, sen beslut om
   sync-PR `jakob-be → main`. (Coach-rekommendation: review/Scout före PR.)
2. **Christopher: väg B** FloatingChat honest-feedback. Oblockerad. Prompt:
   [`docs/agent-prompts/christopher-followup-honest-feedback.md`](agent-prompts/christopher-followup-honest-feedback.md).
3. **Grind/Cloud Builder: Bite B** (PreviewRuntime wiring via DI) — se
   "Parallellt Grind-arbete" nedan.
4. Nivå 2 copyDirectives (bredare targets) — backend-agent, efter att slice 1
   är reviewad/mergad.

## Parallellt Grind-arbete (Bite B PreviewRuntime DI) — 2026-06-01

Operatören startar en Grind/Cloud Builder-agent som kör **vid sidan om**
detta arbete. Den agenten:

- skapar branch `cursor/preview-runtime-bite-b-di` från `origin/jakob-be`,
  jobbar EJ direkt på `main` eller `jakob-be`, PR:ar mot `jakob-be`;
- implementerar Bite B: `packages/preview-runtime` får dependency-injected
  handlers från `apps/viewser/lib` (ingen package→app-import), `PreviewResult`
  bär StackBlitz file-payload via ett `files`-fält, `localRuntime` delegerar
  till local-preview-server-logiken, `stackblitzRuntime` returnerar payload,
  `flyRuntime` förblir unsupported;
- **får INTE röra** copyDirectives-spåret:
  `scripts/prompt_to_project_input.py`, `packages/generation/brief/**`,
  `governance/schemas/project-input.schema.json`,
  `governance/policies/llm-models.v1.json`,
  `governance/policies/naming-dictionary.v1.json`,
  `governance/decisions/0034-*`,
  `docs/gaps/GAP-followup-prompt-content-passthrough.md`,
  `tests/test_followup_copy_directives.py`;
- **får INTE röra** Christopher/UI-paths (`apps/viewser/components/**`,
  `apps/viewser/app/**/*.tsx`, `apps/viewser/app/**/*.css`,
  `apps/viewser/public/**`) och bygger ingen Vercel/Fly/static-export-adapter.

**Konfliktrisk är låg:** Bite B rör `packages/preview-runtime/**` +
`apps/viewser/lib/**`; copyDirectives rör generation/brief + governance-
scheman. Ingen filöverlapp. När Bite-B-PR:n mergats till `jakob-be` synkar
nästa backend-pass med `git reset --hard origin/jakob-be` innan nivå 2.

## Tidigare checkpoint (#139 christopher-ui → main)

**Datum:** 2026-06-01 UTC, steward-auto efter PR #139 — sync: christopher-ui → main (UI/UX-batch + B155 UI + ADR 0034 väg B-UI). Verifierad `main` är `f22d27a` (steward-auto `efbb425`).

Nya PRs sedan föregående checkpoint: PR #114 — chore(gitignore): re-ignore __pycache__/
under packages/generation/build/ (B146 fallout); PR #118 — sync(jakob-be -> main): PR
#117 mobile responsive + PR #116 dossier-intake + 12 closed bugs + B147 new +
audit-report; PR #120 — sync(jakob-be -> main): repo hygiene 2026-05-26 (4 commits,
docs-only); PR #123 — sync(jakob-be -> main): backend gap batch and docs cleanup; PR
#125 — fix(discovery): honor wizard clears across versioned fields; PR #127 —
fix(viewser): block Python-backed actions on hosted Vercel; PR #133 — sync(jakob-be ->
main): PreviewRuntime Bite A skeleton + race-fix + governance comments + builder prompt;
PR #135 — feat(builder): close B155 backend — applied-effect-detektion + trace-event för
fri follow-up; PR #134 — refactor(quality-gate): resolve contact-route via routes.json;
PR #139 — sync: christopher-ui → main (UI/UX-batch + B155 UI).

## Tidigare checkpoint (B157 level 4)

**Datum:** 2026-05-31 UTC, steward-auto efter PR #137 — sync(jakob-be -> main): B157 level 4 immutable build-dir + pointer-swap + GC. Verifierad `main` är `40b7d29`.

Nya PRs sedan föregående checkpoint: PR #137 — sync(jakob-be -> main): B157 level 4
immutable build-dir + pointer-swap + GC.

**MCP-server-status:** Sprintvakt-servern exponerar 14 tools efter
PR #77 (`get_workboard`, `list_gaps`, `create_gap`, `activate_gap`,
`complete_gap`, `reserve_paths`, `detect_collisions`, `suggest_next_gaps`,
`generate_agent_prompt`, `validate_workboard`, `post_merge_sync_instructions`,
`post_message`, `list_messages`, `ack_message`). Agent-inbox-tools är
bakade av append-only `docs/agent-inbox.jsonl` med deterministisk
message-id + idempotent ack. Operatörens `.cursor/mcp.json` är
konfigurerad med `PYTHONPATH` så `python -m tooling.sprintvakt_mcp.server`
startar utan ModuleNotFoundError. Editable install (`pip install -e .`)
krävs en gång per venv enligt ADR 0029.

**Status (2026-05-31 PM):** `main` == `jakob-be` == `9e1a025`. Stor batch
landad via PR #136 + #137. **B157 är arkitektoniskt stängd**: nivå 4
(immutable build-dir + atomär `current.json`-pointer-swap, Stage A) + delayed
GC (`scripts/gc_old_builds.py`, Stage B) ligger i `main`. Round 1-3-plåstren
+ build-runner-tree-kill är kvar som redundanta säkerhetsnät. Övrigt landat
denna omgång: B155-backend (ärlig no-op-detektion via `appliedVisibleEffect`
i build-result + trace-event), BO6 (backoffice runtime-scaffolds dynamiska
från resolvern), quality-gate contact-route via `routes.json` + härdning,
api-smoke env-isolering, samt extern-review-fixar (`kill-dev-trees.py`
scope:ad + `buildPath`-kryssvalidering). Golden-path eval baseline 7.34/10.
Inga öppna PRs.

**Pre-flight för nästa orchestrator:**
1. `docs/current-focus.md` (Last verified `40b7d29`/`9e1a025`).
2. `python scripts/focus_check.py` — ska ge OK.
3. Vid orphan-processer (Windows): `python kill-dev-trees.py` eller dubbelklicka
   `kill-dev-trees.bat`. Helpern är nu **scope:ad** — tree-killar bara
   Sajtbyggaren-processer (repo/output-path-token ELLER `next start`/`next dev`
   på preview-port 4100-4199), inte främmande Next-projekt på maskinen.

**Priorordning nu:**
1. **Christopher-koordinering (kärnloopen).** Två backend-halvor väntar på
   UI: B155-signalen (`appliedVisibleEffect` i `build-result.json` →
   FloatingChat "ingen synlig ändring"-rad) och — störst — `copyDirectives[]`
   (ADR 0034 väg A) som gör fri-text-följdprompt → synlig sajt-ändring. Bara
   Christopher kan UI-delen. Sync-PR `christopher-ui → main` rekommenderas.
2. **Bite B (PreviewRuntime wiring).** OBS: naiv wiring ger lager-violation
   (paket→app); rätt väg = dependency-injection + ett `files`-fält på
   `PreviewResult`. Egen builder-uppgift; unblockar Christophers Bite C.
3. **Mät bygg-fart.** Immutable builds kör full `npm install` per bygge (varm
   cache mildrar). Vid seg iteration: `node_modules`-seeding från föregående
   build (valfri optimering).
4. **B157-uppföljare (Linux-verifierade, POSIX-only):** flat-layout-GC i
   `gc_old_builds.py` + POSIX-tree-kill (`detached`-spawn + `killpg`) i
   `local-preview-server.ts` / `build-runner.ts`. Windows opåverkad.

**Branch-läge (städat 2026-05-31 PM):** raderade
`cursor/jakob-be-viewser-local-next-preview` (superseded via #88-#101).
Behållna: alla `backup-*` (operatörens keepsakes), `origin/christopher-ui`
(aktiv), `origin/cursor/preview-runtime-adapters` (medveten WIP-snapshot för
framtida vercel-adapter), `origin/cursor/dossier-intake-v11-review-895d`
(**49 omergrade commits — operatörsbeslut om radering, auto-raderas EJ**).

**Ignore-config:** tunga data-/genererade kataloger (`data/runs/`,
`.generated/`, `data/evals/*` m.fl.) är index-ignorerade via
`.cursorindexingignore` (läsbara vid behov, bara inte indexerade).
`.cursorignore` är agent-skyddad (kan ej editeras av agent) — orörd.

**Parkerade lanes (väntar trigger):**

- **Path B / section-driven renderer** — dokumenterad i `docs/scaffold-runtime-extension-needed.md` + `docs/path-b-backend-scout.md` (~22-28h). Lane 2 är klar (B137-B141 stängda 2026-05-22) så Path B är inte längre tekniskt blockad — väntar bara på operatörsbeslut om sprint.
- **Christophers `GAP-backend-build-trace-endpoint`** — completed via PR #105 / commit `fe7a9e4` (2026-05-25T16:41:27Z). Verifierad 2026-05-27: `apps/viewser/app/api/runs/[runId]/trace/route.ts` implementerar specat kontrakt. Flyttad till `docs/workboard.json::completedGaps` i `c821b8e`. Owner `jakob` bibehållen så Sprintvakt-lane-policy passerar (precedent från PR #68).
- **Sprintvakt V1.3 (potential)** — tvåvägs-sync workboard.json ↔ gap-filer. Flaggat som follow-up i `docs/sprintvakt-mcp.md`.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project DNA
V2 tills sprinten är formellt vald. Rör inte B125 om det inte uttryckligen
väljs.

**Andra cloud-agenters obesegrade arbete (operatörens uppmärksamhet):**

- `origin/cursor/jakob-be-contact-route-regression` — 2 commits. Innehåll inne via recovery #76.
- `origin/cursor/jakob-be-followup-versioning-regression-5fb4` — 3 commits. Innehåll inne via recovery #76.
- `origin/cursor/candidate-generation-safety-provenance` — 1 commit `07aca96`. Sibling-PR-branch till #78 som inte städades vid merge. Innehåll inne via #78.
- Alla tre kan raderas på operatörens OK (`git push origin --delete <branch>`). Nästa Jakob-agent ska inte röra dem utan instruktion.

**Filosofi B (parallellt arbete) är nu fullt operativ:**

- `jakob-be` är **permanent arbets-branch** för backend/generation/
  governance/scripts/runtime/merge-review. Solo-ägd, `--force-with-lease`
  efter varje main-merge är OK enligt `governance/rules/branch-scope-ui-ux.md`.
- `christopher-ui` är **permanent arbets-branch** för UI/frontend/viewser/
  visual-polish. Reserverade paths: `apps/viewser/components/**`,
  `apps/viewser/app/**/*.tsx`, `apps/viewser/app/**/*.css`,
  `apps/viewser/public/**`.
- PR går alltid mot `main`, aldrig mot motpartens arbets-branch. Efter
  squash-merge synkar respektive ägare med `git reset --hard origin/main`
  + `git push --force-with-lease`. Pulla aldrig en redan squash-mergad
  branch — gör `reset --hard origin/main` i stället.
- Workboard (`docs/workboard.json`) säger vem som äger vad.
  `python scripts/sprintvakt_check.py` ska vara grönt innan nytt arbete
  startar.

**Inga öppna PRs.** PR #133 mergad till `main` (senaste merge före
denna handoff). PR #69 stängd, PR #120 (2026-05-26 PM) tidigare merge.

**Öppna gaps på workboarden:** 2 queued gaps + 0 active +
1 completed-i-detta-pass.

- `queued`: `GAP-windows-safe-rebuild-pipeline` (immutable build-dir +
  pointer-swap, B157 nivå-4-spår)
- `queued`: `GAP-followup-prompt-content-passthrough` (fri text når
  codegen, kärnflödes-fix)
- `completed`: `GAP-backend-build-trace-endpoint` — Christopher-
  implementerat under operator-OK scope-leak, mergat via PR #105
  (commit `fe7a9e4`, 2026-05-25T16:41:27Z). Verifierad 2026-05-27.

**Christopher-scope-leak-precedent från PR #68:** två backend-commits
(`acc6265` planner-fix i `plan.py`, `a44740a` resolver-fix i `resolve.py`)
togs på `christopher-ui` med `[scope-leak] Approved by operator`-tag
eftersom de var rena dispatch-tabell-tillägg utan runtime-beroende. Detta
är **operator-approved engångsundantag, inte permanent norm**. Framtida
backend-kontrakt-ändringar ska gå via separat backend-PR på `jakob-be`,
om inte operatören explicit godkänner ett scope-leak i förväg.

**Startprompt för ny agent:**

[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md)
har en färdig första prompt med läs-ordning, sanity-kommandon, och
gränser för vad agenten får göra utan att fråga. För Sprintvakt-agent
finns separat prompt i [`docs/agent-prompts/sprintvakt.md`](agent-prompts/sprintvakt.md).

**Senaste landade spår sedan c0b59fbe (PR #60), nyast först:**

- `2a5d2e5` PR #83 / `docs(grind): close B72 + B75 status-sync to Stängda`. Båda buggarna var fixade i `885431b` (PR #28) men entries glömdes kvar i Öppna under Steward-städning 2026-05-18. Cloud-grind round 4 verifierade båda regression-tester passar mot HEAD (`tests/test_viewser_security_1b.py` + `tests/test_project_input_schema.py`), uppdaterade summary-rad till 19/112 aktiva.
- `2821e5f` docs(steward) / Sprintvåg 1 stängd, bumpade verified state till `7654573` med fyra PRs dokumenterade.
- `7654573` PR #79 / `fix(grind): close B87 model fallback warning`. `resolve_brief_model`-fallback loggar nu högt på stderr per B87 fix-direktivet (`known-issues.md:138-139`). Cloud-grind round 3, rebasad och pushad efter #80-merge med uppdaterad bugräkning 22→21 aktiva.
- `4d4a27b` PR #80 / `fix(grind): close B85 stdout contract drift`. Source-lock-test `test_prompt_helper_docstring_matches_stdout_contract` låser `scripts/prompt_to_project_input.py`-docstringen mot stdout-nycklar. Cloud-grind round 2.
- `0ea3f3d` PR #82 / `docs(scout): embedding readiness audit 2026-05-25`. Lane 3 Scout-rapport (No-Go-dom, modellval, Go-villkor, B-IDer för schema-bumpar, 386 rader docs).
- `86c01fa` PR #81 / `fix(grind): close B83 service slug collision`. Status-only-stängning från Cloud-grind round 1.
- `74e74f2` docs(steward) / parallell-sprint-plan committad, last verified state bumpad till `b12c164`, mcp tools 11→14, lane-strukturen dokumenterad.
- `b12c164` post-merge grind / `_load_gap_from_file` unescapes markdown backslash-escapes så `sanitize_repo_path` inte producerar korrupta paths. 80 rader, ny regression-test, ren cloud-grind-fix mot `jakob-be`.
- `a0b06b5` docs-fix / escape `[runId]` i gap-frontmatter så markdown-linter inte klagar (matchar `_MARKDOWN_ESCAPE_RE`-konvention i `core.py`).
- `e2574af` PR #78 / candidate generation provenance + helpers (`scripts/candidate_generation_metadata.py`) + sidecar `.meta.json` per kandidat + Backoffice-default `use_llm=False`. 9 filer, ~562 additions.
- `d3f51ee` PR #77 / Sprintvakt agent inbox (post/list/ack) + 5 reviewfynd-fixar i samma squash (symlink-resistens, deterministic id, idempotent ack, ordinal > 9999, UTC-aware since-filter). 5 filer, ~1399 additions (varav 752 är tester).
- `dc1d53f` docs(steward) / closing-round sync 2026-05-25 04:30 efter recovery #76 — post-merge docs-bump utan kod.
- `92df12c` PR #76 / recovery av tappade #73/#74-regressionstester + Industry Coverage catch-all-fix. Mergad till `jakob-be` (inte `main` än). 4 filer, 531 additions / 3 deletions.
- `6649b51` docs(steward) / closing-round sync på `jakob-be` efter PR #75 (post-merge docs-bump utan kod-ändringar).
- `84bf9dd` PR #75 / Sprintvakt V1.1+V1.2+V1.2.1 + CI hardening + Backoffice industry coverage + Path B scout + ADR 0029 + docs sync (16 commits squashade till en). Tackled fyra legitima external review-fynd före merge (status-enum-validering, collision-recheck i `activate_gap`, gap-md vs workboard "workboard wins"-dokumentation, stale "next"-claim-cleanup).
- `7e21b49` PR #71 / Christophers Front 1-4 + wizard minimalism. Levererar 5 nya UI-gaps (4 in-review/completed + 1 aktivt: `GAP-viewser-live-build-sync` + 1 queued backend-spec åt Jakob: `GAP-backend-build-trace-endpoint`).
- `cb5c837` PR #70 / Sprintvakt V1 koordineringsserver + MCP (path-overlap-fix i `419d3f1`). 14 sprintvakt-tester gröna.
- `839d0c8` PR #68 / restaurant-hospitality Week 1 declarative expansion (11 soft dossiers + 14 variants). Inkluderade två `[scope-leak]`-commits från Christopher i `plan.py` + `resolve.py`.
- `7e900d2` PR #67 / AI bug review-workflow-steg i CI (`gpt-5.4` + repo-specifik prompt).
- `d709864` PR #66 / sourceUrl-asset-uploads med stream-safe fetch (PR #65 stängd och supersededad).
- `89f14a1` PR #64 / branch-naming-konventioner för parallellt teamarbete. Permanenta arbets-branches `jakob-be` + `christopher-ui` formaliserade i `docs/ownership-map.md`.
- `f9312ec` PR #63 / wizard-directives `useCustomColors` + `scaffoldHint` (backend-Gap 1 + 3 stängda).
- `7240fcd` PR #62 / viewser-christopher-ui builder-workflow-integration.
- `a32152d` PR #61 / team parallel workflow + ownership map.
- `c0b59fb` PR #60 / Starter Candidate Auditor v1, read-only — utgångspunkten för denna spårserie.

För djupare commit-historik före c0b59fbe (PR #60), se
`git log --oneline origin/main` eller
[`docs/current-focus.md`](current-focus.md):s "Föregående produkt-läge"-block.

## Hur agenten jobbar — Filosofi B + branch-policy

Standardflödet definieras i tre källor:

- [`docs/ownership-map.md`](ownership-map.md) — vem äger vad, branch-konventioner, livscykel för arbets-branch.
- [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md) — Steward/Scout/Builder-roller, fyra guards, push-disciplin, multi-line commits på Windows.
- [`governance/rules/branch-scope-ui-ux.md`](../governance/rules/branch-scope-ui-ux.md) — off-limits-paths på `christopher-*`/`frontend/*`/`ui/*`/`ux/*`-branches.

**Tre nivåer:**

1. **`main`** är sanningen. Pushas aldrig med `--force`. Inga direkta pushes utan operator-OK när det är produktkod — bara docs-/governance-/steward-pushes är OK direkt enligt `branch-discipline.md` "Mainline-steward"-sektion.
2. **Permanenta arbets-branches** (`jakob-be`, `christopher-ui`) är solo-ägda. PR till `main` när det är dags att släppa. Efter merge: `reset --hard origin/main` + `--force-with-lease`-push.
3. **Tillfälliga feature-branches** (`jakob/<x>`, `frontend/<x>`, `cursor/<x>`, `tooling/<x>`) startas från `main`, PR:as till `main`, raderas efter merge.

**Sprintvakt V1 som koordinationslager:**

- `docs/workboard.json` håller `people`, `reservedPaths`, `queuedGaps`, `activeGaps`, `completedGaps`.
- `scripts/sprintvakt_check.py` (CLI + `--json`/`--strict`) körs som lokal collision-guard.
- `tooling/sprintvakt_mcp/server.py` är en dependency-free MCP-kompatibel stdio JSON-RPC-server med nio tools (`get_workboard`, `list_gaps`, `create_gap`, `reserve_paths`, `detect_collisions`, `suggest_next_gaps`, `generate_agent_prompt`, `validate_workboard`, `post_merge_sync_instructions`).
- Mutationer kräver `dryRun:false` + `confirm:true`. Skrivning är begränsad till `docs/workboard.json`, `docs/gaps/**`, `docs/sprintvakt-log.md`.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator för småföretagare. Mål: stabilt kärnflöde
`prompt → företagshemsida → preview → följdprompt → ny version`.
Sanningskällan är `governance/` (JSON-policies + JSON-Schemas + ADR).
Runtime + kund-UI ligger i `packages/` + `apps/`. Streamlit-backoffice
i `backoffice/`. Se
[`docs/product-operating-context.md`](product-operating-context.md) för
produktkompass.

## Vad funkar idag (post `cb5c837` / Sprintvakt V1)

### Governance + guards

- 18 policies + matchande schemas under `governance/schemas/`. Validering via `python scripts/governance_validate.py`.
- Fem automatiska checks körs på push + PR via GitHub Actions: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift (AGENTS.md ruff-baseline + dossier README-status).
- Ruff baseline = **0 findings**. Inga `noqa`-tillägg utan ADR.
- Cursor Bugbot (`.cursor/BUGBOT.md`) granskar PRs och postar trådar; autofix är **av**. PR #67 lade till en separat `@sajtbyggaren-ai-bug-review`-workflow (gpt-5.4 + repo-specifik prompt) som postar topp-3-fynd som vanlig PR-kommentar.

### Brief, plan, build

- **briefModel** via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- **planningModel** via shared `packages.generation.planning.produce_site_plan`. Både `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper.
- **codegenModel** (scope: `marketing-base` + `commerce-base` via deterministic-v1) i `packages/generation/codegen/` med Quality Gate (typecheck / route-scan / build-status / policy-compliance) och Repair Pipeline. Real codegen för andra starters är V2-scope (ADR 0017).

### Scaffolds, dossiers, variants

- **3 scaffolds:** `local-service-business` + `ecommerce-lite` (fullt runtime-aktiva via `_RUNTIME_SCAFFOLD_HINTS`), `restaurant-hospitality` (planner-aktiv via PR #68; runtime aktiveras när Path B / section-renderer landar — se [`docs/scaffold-runtime-extension-needed.md`](scaffold-runtime-extension-needed.md)).
- **11 soft dossiers** efter PR #68 Week 1-expansion. Wizard-page-label → capability-map är fullt wired efter PR #68 + PR #63 (Gap 1 + 3 stängda).
- **18 variants** över LSB + ecommerce-lite + restaurant-hospitality. Wizard step-2 exponerar alla via `vibesForScaffold()`.
- **5 starters på disk**, 2 mappade i `SCAFFOLD_TO_STARTER` (`marketing-base`, `commerce-base`). `restaurant-hospitality` återanvänder `marketing-base` (PR #68).

### Prompt-till-sajt + follow-up versions

- `/api/prompt` i Viewser tar fri prompt → spawnar `scripts/prompt_to_project_input.py` → `runBuild` med whitelisted dossier-path-override → svar med `buildStatus` (ok/degraded/failed).
- Follow-up versions: immutable `<siteId>.vN.project-input.json` + `<siteId>.vN.meta.json`-snapshots i `data/prompt-inputs/`. `projectId` + `version` bevaras. PromptBuilder är enda promptytan i Viewser-home.
- StackBlitz preview fungerar för Chromium-baserade browsers; Safari/Firefox behöver server-byggd fallback (B125, ADR 0025 — parkerad, se nedan).

### Sprintvakt V1 (PR #70)

- Lokal workboard + collision-checker + MCP-server (se "Hur agenten jobbar" ovan).
- 14 tester gröna. Path-overlap fixad (`paths_overlap("docs/workboard.json", "docs/sprintvakt-mcp.md") is False`).

## Vad är parkerat

- **B59 / B125 — embedded StackBlitz-preview för Safari/Firefox.** WebContainer-runtime kräver iframe-attributet `credentialless` som bara finns i Chromium. ~25-35 % av svenska SMB-kunder behöver server-byggd fallback. ADR 0025 + B125-rapport finns; väntar på operatörens implementations-OK (Vercel preview-deployments, lokal `next dev` same-origin iframe eller static export embed är kandidater). Rör inte `apps/viewser/lib/stackblitz-files.ts`, `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts` eller `tests/test_viewser_files.py` utan separat sprintbeslut.
- **Embeddings, SNI-runtime-konsumtion, variant-promotion, nya starters/starter-importer, Project DNA V2** — alla parkerade tills explicit sprint vald. SNI 2025-taxonomin finns under `data/taxonomies/sni/` och konsumeras read-only av Backoffice-diagnostik (ingen runtime-koppling än).

## Nästa konkreta uppgift

Se [`docs/current-focus.md`](current-focus.md) → **"Direkt nästa fokus"**.
Kort: backend-Gap 1-11 är stängda och nästa naturliga steg är sync-PR
`jakob-be → main`. Därefter är Christophers
`GAP-backend-build-trace-endpoint`-PR nästa review-spår när den öppnas.

## Operatörspreferenser

- **Språk:** alltid svenska. Riktiga svenska tecken (`å`, `ä`, `ö`). Se [`governance/rules/always-swedish.md`](../governance/rules/always-swedish.md).
- **Reply-style:** kort + koncist. Förklara dev-uttryck med korta parenteser första gången per konversation (operatören är inte utvecklare i grunden). Se [`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
- **Backup-branches:** kvar i historisk practice för sprint-flöde på `main`. För `jakob-be`/`christopher-ui`-passen är det inte längre standard — Filosofi B är operatörens explicit-valda alternativ.
- **Create-PR-knappen i Cursor:** användaren kan av misstag trycka den. Standard är att inte öppna PR; fråga operatören om PR verkligen är avsikten.
- **PowerShell + git commit multi-line:** Här-string piped till `git commit -F -` är primär lösning (skapar ingen disk-fil). Fallback är temp-fil under `$env:LOCALAPPDATA\Temp` — aldrig `$env:TEMP` (resolveras till `C:\WINDOWS\TEMP` i elevated agent-shell). Aldrig `.commit-msg.tmp` i repo-roten (race med `git add -A`). Detaljerat i `governance/rules/branch-discipline.md`.
- **Cursor IDE git-editor pipe error på Windows** är vanligt (`ENOENT \\\\.\\pipe\\vscode-git-...sock`). Fall tillbaka till `git commit -F` från shell direkt.

## Bugbot + AI bug review

Två oberoende automatiska reviewers körs på alla PRs:

- **Cursor Bugbot** (`.cursor/BUGBOT.md`). Trigger: varje push till PR + draft-PRs. Autofix är **av** — Bugbot postar PR-kommentarer som review-trådar. Manuell granskning + fix krävs. Vanligt fall: nya commits flyttar inte tidigare trådar till "outdated" — verifiera mot senaste commit-SHA innan slutsats om fynd kvarstår.
- **`@sajtbyggaren-ai-bug-review`** (PR #67, gpt-5.4 + repo-specifik prompt). Postar topp-3-fynd som vanlig PR-kommentar med probability + impact-score.

Vid PR-merge: kontrollera (a) check `SUCCESS`/`NEUTRAL` med 0 aktiva trådar,
(b) `mergeStateStatus == "CLEAN"`, (c) ingen oadresserad HIGH-severity. För
direkt-`main`-flöde (steward-pushes på docs/governance): inga
Bugbot-iterationer, men Scout-agent kan göra RO-review före push.

Full PR-loop-rutin: [`governance/rules/bugbot-pr-loop.md`](../governance/rules/bugbot-pr-loop.md).

## Pre-push self-review checklist

Innan `git push origin <branch>` (alla branches):

1. `git diff origin/<branch>..HEAD --stat` — jämför mot deklarerat scope.
2. Sök efter samma hardcoded-pattern som sprinten säger sig fixa (klassiskt blindspot på nya filer).
3. Log-/print-meddelanden i present tense ska komma FÖRE handlingen, inte efter, så operatören ser vad som är i flygt vid crash.
4. Nya renderers/komponenter som tar `dossier` — kontrollera om de länkar via scaffolden (`_pick_*_route`) eller dossiern.
5. Ändringar i `SCAFFOLD_TO_STARTER` eller `data/starters/<starter>/` kräver ADR i samma PR.
6. Sprintvakt: `python scripts/sprintvakt_check.py` ska vara grönt; `detect_collisions` på sprintens paths ska vara `green` (eller dokumenterad `yellow` med operator-OK).

## Standard loop (referens)

Full rutin i [`docs/agent-handbook.md`](agent-handbook.md). Tio steg; steg 8
(Steward post-push-verifierar och uppdaterar `current-focus.md` +
`handoff.md` vid faktisk fokusförändring) är agentens ansvar, inte
operatörens.

```text
0. Drift-check (python scripts/focus_check.py).
1. Sprintvakt-check (python scripts/sprintvakt_check.py) — collision-guard.
2. Skapa nästa backup-N från synkad main vid main-arbete;
   för jakob-be/christopher-ui hoppas detta steg.
3. Builder/Steward jobbar på arbets-branchen.
4. Scout-agent RO-review före push vid produktkod.
5. Operatör + extern reviewer beslutar vid stora ändringar.
6. Final sanity: governance + rules_sync + term-coverage + sprintvakt-check.
7. Commit + push.
8. Steward verifierar pushed SHA, git status, focus_check,
   origin == local, och docs-beslut. Uppdatera current-focus/handoff när
   HEAD, active sprint, risk/blocker eller arbetsflöde ändras.
9. Nästa etapp.
```

## Tidigare djup-historik

Detaljerade session-narrativ från perioden före 2026-05-25 har städats ur
denna fil för att hålla den hanterbar (tidigare 1086 rader, nu ~270).
Källor för bakgrund:

- `git log --oneline origin/main` för full commit-historik.
- [`docs/current-focus.md`](current-focus.md) "Föregående produkt-läge"-block för verified-state-progression.
- [`docs/known-issues.md`](known-issues.md) för B-ID-historik (aktiva, misplaced, unknown, stängda).
- [`governance/decisions/`](../governance/decisions/) för ADR-spår.

## Föregående checkpoint

### 2026-05-25 UTC — handoff.md före `2057241`

**Datum:** 2026-05-25 kväll. Verifierad feature-branch
`b146-port-section-dispatcher` (B146 stängd: Christophers PR #105 + #108
section-arkitektur portad ovanpå PR #107-splitten). `jakob-be` HEAD är
`ee2a91e`; `main` HEAD är `84bf842`. **Öppen PR:** feature →
`jakob-be` följt av sync-PR `jakob-be → main`. Bug-räkning på
feature-branchen: **19 aktiva / 5 unknown / 114 stängda** (B146 +
B116 båda stängda).

**Kvällens fönster (B146 + Phase 3 port):**

- Ny fil `packages/generation/build/dispatcher.py` (~370 rader) med
  section-id registry, treatment-resolution-helpers, `render_route_generic`.
- `packages/generation/build/renderers.py` växte från 2357 → ~4710 rader
  med ~30 nya `render_section_*` + uppdaterade page renderers från
  Christophers main-versioner. Initial sektion-registrering vid filslut.
- `scripts/build_site.py` ~3162 → ~3650 rader: utökade re-exports +
  `__getattr__`-shim som proxar okända namn till
  renderers/dispatcher/static_assets. `from scripts.build_site import
  render_section_X` fortsätter fungera.
- ADR 0031 (section-treatments från main:PR #108) renumrerad till **0032**
  eftersom jakob-be:s 0031 (Steward auto-bump, PR #106) var äldre.
  Renumber-not överst i ADR + uppdaterade referenser i alla
  source-/test-/doc-filer.
- Phase 3 backend: `_apply_directives_fields` additivt-mergar
  `directives.sectionTreatments` i resolve.py; `_SECTION_TREATMENTS_CATALOGUE`
  + planning-prompt-update i plan.py; schema-bump i project-input.schema.json.
- Wizard-UI: `treatment-options.ts` (ny), `wizard-types.ts`/
  `wizard-payload.ts`/`steps/visual-step.tsx`/`demo-answers.ts` uppdaterade,
  `wizard-constants.ts` fick 113 nya rader (deriveEffectiveScaffoldHint +
  4 restaurant-vibes).
- Tester: 5 nya/uppdaterade testfiler portade,
  `tests/test_section_treatments_{prompts,propagation,resolve}.py` +
  `test_section_renderer_registry.py` + `test_project_input_schema.py` (utökat).
  126 nya cases passerar. `test_builder_audit_post_3b_next.py` fick utökad
  JSX-escaping-lista (sätter `render_section_hero`, treatment-helpers etc.).

**Eftermiddags-fönstret (4 produkt-PRs + sync-PR till main):**

- PR #97 — pedagogiskt preview-fel i local-next mode (404/missing_artifacts mapping)
- PR #100 — per-siteId build mutex (Map ersätter global inFlight) → stänger B116
- PR #101 — StackBlitz embed unblocker (cross-origin-isolated permissions policy)
- PR #104 — honor preview mode end-to-end + mode-aware progress copy
- PR #103 — sync-merge `jakob-be → main` (16 commits totalt: 6 produkt + 6 härdning + 2 docs + 2 sync)

**Christopher-koord:** `origin/christopher-ui` är `399cf39` (idag) och
ligger **21 commits framför `origin/main`** — har inte pullat sync-PR
#103. Senaste commit `[scope-leak]`-taggad av honom själv (gick in i
`scripts/build_site.py:render_home`-territoriet, utanför hans branch-scope).
Meddelande postat till hans Sprintvakt-inbox 2026-05-25
(`msg-0007-ae0ac0`) om rebase-behov. PR mot main blockerad tills han
har merge:at + löst konflikter i `apps/viewser/components/viewer-panel.tsx`.

**Föregående checkpoint samma dag (morgon):** Sprintvåg 1+2 stängd — fem
PRs landade på `jakob-be` på 2 timmar (#81 + #82 + #80 + #79 + #83).
Verifierad `jakob-be` var då `2a5d2e5`, `main` på `6649b51`,
bug-räkning 19/112.

**ÄRLIG BEDÖMNING (extern reviewer + orchestrator-self-audit):** Av
dagens fem PRs är endast **#79 en substantiell produktkodsförändring**
(stderr-warning vid `briefModel`-fallback). #80 = docstring-source-lock-
test (intern kvalitet, ingen runtime-effekt). #81 + #83 = docs-
flyttar av redan-fixed B-IDer i `known-issues.md`. #82 = read-only
scout-rapport för embeddings-readiness. Dagens energi gick åt
**koordinationslager** (Sprintvakt-inbox, lane-disciplin, worktree-
isolering, multitask-räddningsoperation) snarare än till kärnflödet
`prompt → brief → plan/build → preview → följdprompt`. Verklig
produktlyft denna session: minimal. `main` rör sig inte alls. Detta
är acceptabelt OM nästa session prioriterar Lane 2 LLM contract
propagation (B137-B141) och `jakob-be → main`-sync.

`origin/christopher-ui` är på `9f63f15` med Christophers
scope-leak-implementation av `GAP-backend-build-trace-endpoint` plus en
versions-tab-fix, ej PR:ad än. Hon är hård blocker för `jakob-be → main`-
sync eftersom hennes branch behöver hanteras innan main rör sig.

Health på `jakob-be` är grön: governance (18 policies), rules-sync,
strict term coverage, sprintvakt-check `--strict`, ruff 0 findings,
hela pytest-suiten (25 sprintvakt-tester + 14 industry-coverage + 2
workflow-regression + 30+ övriga + nya #76-recovery-tester körda lokalt
i ren worktree från `origin/jakob-be` innan PR).

### 2026-05-25 UTC — handoff.md före `ee31eb1`

**Datum:** 2026-05-25 UTC, steward-auto efter PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime smoke-lock + golden-path eval (#112, #109, #110). Verifierad `main` är `ee31eb1`.

Nya PRs sedan föregående checkpoint: PR #55 — fix(viewser): stale run-following och
artefakt-panel; PR #59 — feat(backoffice): add read-only asset graph lens; PR #60 —
tooling: Starter Candidate Auditor v1 (read-only); PR #61 — docs: add team parallel
workflow and ownership map; PR #62 — feat(viewser): integrate christopher-ui builder
workflow; PR #63 — feat(discovery): respect wizard directives — useCustomColors +
scaffoldHint (Gap 1 + 3); PR #64 — docs(ownership): add branch-naming conventions for
parallel team work; PR #66 — fix(assets): sourceUrl uploads with stream-safe fetch
(supersedes #65); PR #67 — ci: add AI bug review workflow step; PR #68 — feat(week1):
restaurant-hospitality scaffold + 11 soft dossiers + 14 variants (fantastic sites W1);
PR #70 — feat(tooling): add Sprintvakt V1 coordination guard; PR #71 — feat(viewser):
Front 1-3 + wizard minimalism — preview, iteration & polish; PR #75 — feat: Sprintvakt
V1.1+V1.2 + CI hardening + industry coverage + docs sync (post-PR70 batch); PR #76 —
fix(backoffice): recover regression tests and catch-all coverage status; PR #77 —
feat(tooling): add Sprintvakt agent inbox (post/list/ack); PR #78 — fix(backoffice):
harden candidate generation provenance and defaults; PR #81 — fix(grind): close B83
service slug collision; PR #82 — docs(scout): embedding readiness audit 2026-05-25; PR
#80 — fix(grind): close B85 stdout contract drift; PR #79 — fix(grind): close B87 model
fallback warning; PR #83 — docs(grind): close B72 + B75 status-sync to Stängda; PR #84 —
test(generation): contract regression net for B137-B141 + extend B139 tone fallback; PR
#87 — feat(backoffice): add one-click eval smoke runs; PR #89 — feat(eval-probe): add
scaffold-selection probe + docs; PR #88 — fix(viewser): make preview mode drive local
iframe headers; PR #92 — fix(viewser): handle quoted-with-comment + $VAR expansion in
dev-dispatcher .env-parser; PR #93 — feat(builder): wire menu+booking renderers so
restaurant-hospitality builds; PR #94 — docs(dossiers): import-readiness scope-doc for
Sajtmaskin material; PR #95 — feat(evals): add cafe-bistro to FULL_CASES so full suite
covers all 3 on-disk scaffolds; PR #97 — fix(viewser): pedagogical preview-error in
local-next mode + soft transport-mismatch warning; PR #99 — docs(adr): 0030
preview/deploy-providers are adapters, not canonical runtime; PR #98 — chore(tooling):
lucide-react cross-policy lock + ADR 0021 upstream-issue recheck + B145 entry; PR #100 —
fix(viewser): per-siteId build mutex so unrelated sites can build in parallel; PR #101 —
fix(viewser): cross-origin-isolated permissions policy + dispatcher https signal; PR
#102 — fix(evals): cherry-pick timeout-hardening + helper API from #96; PR #104 —
fix(viewser): honor preview mode end-to-end + mode-aware progress copy; PR #103 —
sync(jakob-be -> main): 5 produkt + 6 härdning + 2 docs (13 commits); PR #105 — Live
Build Sync + Restaurant Path A + Wizard polish + Side-by-side preview; PR #106 —
feat(steward): auto-bump current-focus + handoff on PR merge to main (ADR 0031); PR #107
— refactor(builder): extract page renderers from build_site.py to
packages/generation/build (B13a step C); PR #108 — Phase 3 — section-treatments
operator-pin + scout-driven polish; PR #112 — feat(b146): port Christopher's
section-arkitektur ovanpå PR #107-splitten; PR #109 — test(builder): lock runtime
scaffold smoke coverage on jakob-be; PR #110 — feat(evals): add deterministic golden
path scorecard and embeddings gate; PR #111 — fix(agents): correct python3-venv package
name for Ubuntu Noble; PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime
smoke-lock + golden-path eval (#112, #109, #110).

### 2026-05-26 UTC — handoff.md före `858f8e8`

**Datum:** 2026-05-26 ~14:05 UTC, post-merge bump efter PR #117 + B151-B153 + sync-PR #118 öppnad. Verifierad `jakob-be` HEAD är `05a84bb`. `origin/main` är fortsatt `50217e3` (12 commits efter `jakob-be`); **sync-PR #118 är ÖPPEN** (`jakob-be → main`, OPEN/MERGEABLE/UNSTABLE-CI) och väntar på operatörens granskning + merge.

Nya PRs / direkta commits till `jakob-be` sedan föregående checkpoint (`50217e3`):

- `a337f01` audit-rapport `docs/archive/pr113-ours-conflict-audit-2026-05-26.md` (PR #113 `--ours`-resolution är clean).
- `f2e84b0` + `e6a23a3` — B148 (nav `/kontakt`-hardcode), B149 (Intent Guard substring), B150 (`_normalize_business_type` multi-word) stängda + 14 regression-tester.
- `c85ae70` + `3b5a798` — B97 (kontakt-page hero body per CTA-variant), B98 (`Områden vi arbetar i` suppress för ecommerce-lite) stängda + 9 regression-tester.
- `6d4a096` + `49f5513` — B90 (ENGLISH_HINTS "a"/"an" false positives), B91 (English-exonym → svensk endonym), B92 (`naprapat` ≠ `naprapatklinik`), B93 (22 nya multi-word slugs) stängda + ~20 regression-tester.
- `8c057b1` **PR #116 mergad** — `feat(backoffice): add dossier candidate intake from local files` (1453 inser / 21 del, 8 filer, ny `scripts/dossier_candidate_intake.py` + tester).
- `2319ef9` **PR #117 mergad** — `feat(viewser): mobile responsive — foundation + polish + final (fas 1+2+3 + scout passes)`. 31 commits från `christopher-ui`, 100 % UI-only mot merge-base `3bedddd`. Konflikter på `docs/agent-inbox.jsonl` + `docs/current-focus.md` lösta med kombinerade versioner.
- `4a6243a` + `1471d16` — **B151+B152+B153 stängda** direkt efter PR #117-merge (per operatörs-momentum-beslut, inte väntat på Christopher-följ-PR). Floating-chat iOS Safari <14 compat, compare-modal w-full overflow, viewer-panel `'full'`-preset hydration. 3 source-lock regression-tester i `tests/test_viewser_files.py`.
- `05a84bb` inbox msg-0017-c3f924 till christopher-ui (rapport om merge + att vi tog AI-fynden).

Ny aktiv då: **B147 Medel-Hög** (Vercel preview wizard 403 via `assertLocalhost`). Stängd senare i `b3834b3`. Bug-räkning då: **14 aktiva / 0 misplaced / 5 unknown / 126 stängda** (från 19/0/5/114 vid sessionsstart — netto 5 färre aktiva, 12 stängda, 1 ny tracked).

**Öppen PR just nu:**

- **#118 sync(jakob-be → main)** — OPEN, MERGEABLE, mergeStateStatus UNSTABLE (CI pågår). 45 commits / 56 filer / +5158/-328. Innehåller hela sessionens leverans. Operatörsbeslut då: granska body + checks, sedan merge. Vercel production branch-flippen är åtgärdad 2026-05-26; B146-blockaren är borta.

### 2026-05-27 UTC — handoff.md före `91230b4`

**Datum:** 2026-05-27 tidig morgon UTC, steward-pass efter `91230b4` — completed gap-spec cleanup + B147 closure sync. Verifierad `jakob-be` är `91230b4be799067ec05beb22ce34046ba6e89e0c`.

Nya PRs sedan föregående checkpoint: PR #118 — sync(jakob-be -> main): PR #117 mobile
responsive + PR #116 dossier-intake + 12 closed bugs + B147 new + audit-report; PR #120
— sync(jakob-be -> main): repo hygiene 2026-05-26 (4 commits, docs-only).

### 2026-05-27 UTC — handoff.md före `3415e7d`

**Datum:** 2026-05-27 UTC, steward-auto efter PR #123 — sync(jakob-be -> main): backend gap batch and docs cleanup. Verifierad `main` är `3415e7d`.

Nya PRs sedan föregående checkpoint: PR #123 — sync(jakob-be -> main): backend gap batch
and docs cleanup.

### 2026-05-27 UTC — handoff.md före `44bdbdd`

**Datum:** 2026-05-27 UTC, steward-auto efter PR #125 — fix(discovery): honor wizard clears across versioned fields. Verifierad `main` är `44bdbdd`.

Nya PRs sedan föregående checkpoint: PR #125 — fix(discovery): honor wizard clears
across versioned fields.

### 2026-05-27 UTC — handoff.md före `82ce287`

**Datum:** 2026-05-27 UTC, steward-auto efter PR #124 — feat(llm-golden-path): lock v1 + extend with multi-intent chain, real-build smoke, runbook and handoff. Verifierad `main` är `82ce287`.

Nya PRs sedan föregående checkpoint: PR #124 — feat(llm-golden-path): lock v1 + extend
with multi-intent chain, real-build smoke, runbook and handoff.

### 2026-05-27 UTC — handoff.md före `67bd89a`

**Datum:** 2026-05-27 UTC, post cloud-grind-batch (7 PRs mergade på
~2h fm: #125, #127, #128, #129, #130, #131, #132) + PR #131-follow-up
(`c9a730b`, smoke-test drain-thread refaktor) + PreviewRuntime Bite A
skeleton (`bb6ab2e`) + tre runda reviewer-fynd-fixar (`3e660ea`,
`e9e3f32`, `44ea54b`, `e60f493` på smoke-test cleanup;
`8358326` `test_no_legacy_terms`-fix; `19480dc` fail-loud i
`currentKind()`; `e2f857c` narrow placeholder-copy-scan) + sync-merge
mot `origin/main` (`cbe1ba9`) + steward-bumps + extern-reviewer-
cleanup-batch 2026-05-27 efm (`d60bb58` bot-report-verification-regel,
`abff654` placeholder-scan case-insensitive, `58cfe20` fly-slot-
reconciliation till ADR 0028 nivå 3 i README) + extern-reviewer-
analys 2 (`8fb24e4` B157 + GAP-windows-safe-rebuild-pipeline registrerad
— WinError 5 rmtree på live `node_modules`, arkitektur-anti-pattern att
rebuilda ovanpå aktiv preview-katalog; ingen kodfix i denna batch) +
Cursor BugBot suggestions 1-3 (`82b9f99` defensive cleanup i b154-test,
`23b473e` smala placeholder-scan till `.tsx`/`.jsx` only, `f446be1` AND
→ OR i `_has_contact_cta`, pushade direkt av BugBot) + GPT P2 Badge
fix (`0b40b8d` accept scaffold-specific contact-routes inkl.
`/kontakta-oss` + `/hitta-hit`) + GPT-reviewer-fynd 2 (`ea1e435`
contact-CTA href-only) + post-coach-cleanup (`a67bc01` steward-bump,
`f2de33f` BugBot allowlist, `86b5782` markdown-link-fix) + sanity-
drift-cleanup-runda 1 (`67bd89a` post-coach-bump). Verifierad `jakob-be`
är `67bd89a`. `origin/main` ligger kvar på `4d879177` (**40 commits**
efter `jakob-be`, verifierat med `git rev-list --count`; tidigare
``25 / 29``-räkningar var stale-antaganden). PR #133 (`jakob-be → main`)
är öppen (inte draft), ready-for-review-läge — väntar på operatörens
slutgodkända merge. Bug-count: 16 aktiva (B157 ny).

**PreviewRuntime Bite A (`bb6ab2e`):** typkontrakt + registry + 3
adapter-stubs i `packages/preview-runtime/`. Skelett bara — alla
adaptrar returnerar `unsupported` med tydlig "Bite B-wiring saknas"-
text. Inga existerande filer ändrade. ADR 0028 + ADR 0030 är de
canonical-källor som Bite A följer; `PreviewRuntimeKind` är låst till
naming-dictionary v17 (`stackblitz | local | fly`). Bite B wirear
local + stackblitz mot `apps/viewser/lib/local-preview-server.ts` resp.
`apps/viewser/lib/stackblitz-files.ts` när tsconfig path-alias eller
npm-workspace etableras. Bite C (`viewer-panel.tsx` UI-refaktor) kräver
Christopher-koordinering eftersom `apps/viewser/components/**` är hans
lane per `governance/rules/branch-scope-ui-ux.md`.

**Nya PRs sedan föregående checkpoint (i mergeordning):**

- PR #125 — fix(discovery): honor wizard clears across versioned fields.
- PR #127 — fix(viewser): block Python-backed actions on hosted Vercel
  (501 på `/api/prompt`, `/api/build`, `/api/scrape-site` när VERCEL=1).
- PR #128 — docs(gaps): file followup-prompt-content-passthrough + ADR
  0034 draft (nya B155, operatör-beslut väg (b) ärlig först).
- PR #129 — feat(quality-gate): add contact-CTA + placeholder-copy
  checks som non-blocking warnings. Follow-up `8269800` separerade
  blocking/warning i summary efter reviewer-fynd.
- PR #130 — test(api): add HTTP smoke-test för `/api/prompt`-bron
  (Bite 2 från LLM Golden Path handoff).
- PR #131 — fix(builder): close B154 — TDZ at dev hydration on
  deterministic codegen. Lockfile-alignment + chunk-heuristik-smoke
  + `_npm_install_inputs_changed` diffar nu lockfile-bytes. B156
  registrerad för browser-hydration follow-up. Follow-up `c9a730b`
  (direct push till `jakob-be` efter merge): drain-tråden i
  `tests/test_b154_next_dev_tdz.py` skriver nu direkt in i en delad
  `output`-lista istället för att queue:a, så assertionen ser TDZ-fel
  som dyker upp *efter* Next.js ready-raden (precis B154-fönstret).
- PR #132 — docs(steward): cleanup pass — 8 filer arkiverade till
  `docs/archive/` (5 dated handoffs + 3 completed reports, ~78 KB).

### 2026-05-31 UTC — handoff.md före `8709aae`

**Datum:** 2026-05-27 UTC, post PR #133-merge + B157 akut-fix
(``adba139`` ``fix(viewser): close B157 acute — stop local preview
before build_site.py``). Verifierad `jakob-be` är `adba139`;
`origin/main` är `4196c17` (1 commit efter). Inga öppna PRs.

B157 akut-fix (nivå 1 per gap-spec):
``apps/viewser/lib/local-preview-server.ts`` exporterar nu
``stopAndWaitPreviewServer(siteId, timeoutMs=5000)`` som
SIGTERM:ar live ``next start`` för siteId, väntar in ``exit``-event,
fallback SIGKILL + 200ms file-lock-release-wait på Windows.
``apps/viewser/lib/build-runner.ts:runBuildOnce()`` anropar helpern
INNAN Python spawnas så ``shutil.rmtree(node_modules)`` aldrig kör
mot låsta native ``.node``-binaries. Manual operator-verification:
kör follow-up på commerce-base-site med lockfile-drift, förvänta
ingen ``PermissionError: [WinError 5]``.

Kvarvarande tech-debt: nivå 4 immutable build-dir + manifest-
pointer-swap (egen sprint per
``docs/gaps/GAP-windows-safe-rebuild-pipeline.md``).

Bug-count: **15 aktiva** / 0 misplaced / 5 unknown / 129 stängda
(B157 ny stängd).

Nya PRs sedan föregående checkpoint: PR #133 — sync(jakob-be -> main):
PreviewRuntime Bite A skeleton + race-fix + governance comments +
builder prompt.

### 2026-05-31 UTC — handoff.md före `5746419`

**Datum:** 2026-05-31 UTC, steward-auto efter PR #136 — sync(jakob-be -> main): B157 round 3 + BO6 + B155 backend + quality-gate routes-discovery. Verifierad `main` är `e786618`.

Nya PRs sedan föregående checkpoint: PR #136 — sync(jakob-be -> main): B157 round 3 +
BO6 + B155 backend + quality-gate routes-discovery.

### 2026-06-01 UTC — handoff.md före `ee31eb1`

**Datum:** 2026-05-31 UTC, steward-auto efter PR #137 — sync(jakob-be -> main): B157 level 4 immutable build-dir + pointer-swap + GC. Verifierad `main` är `40b7d29`.

Nya PRs sedan föregående checkpoint: PR #137 — sync(jakob-be -> main): B157 level 4
immutable build-dir + pointer-swap + GC.

### 2026-06-01 UTC — handoff.md före `efbb425`

**Datum:** 2026-06-01 UTC. PR #139 (christopher-ui UI/UX-batch + B155 UI +
ADR 0034 väg B-UI) är mergad till `main`; `origin/main` är `efbb425`
(steward-auto efter `f22d27a`). `jakob-be` har mergat in `origin/main` och bär
de 10 backend-commitsen (topp `f62bd40`) ovanpå — sync-PR `jakob-be → main` är
nästa steg (kräver operatörs-OK).

### 2026-06-01 UTC — handoff.md före `4c473cb`

**Datum:** 2026-06-01 kväll UTC. `jakob-be` HEAD = `2320e34` (hardening-batch +
PR #143 refactor-merge). `main` = `fb3b1f8` (oförändrad sedan PR #142).
`jakob-be` är **inte** synkad till `main` än — väntar operatörs-OK för sync-PR.

### 2026-06-01 UTC — handoff.md före `53301c4`

**Datum:** 2026-06-01 kväll UTC. `main` = `fba03d0` (**PR #144 mergad**).
`jakob-be` HEAD = `939f684` (sync-merge av `origin/main`, trädet identiskt med
`origin/main`), i sync med origin.

### 2026-06-02 UTC — handoff.md före `093b31a`

**Datum:** 2026-06-02 UTC. `jakob-be` = `093b31a` (copyDirectives 2a + 2c +
nivå 3a + extern-review-härdning inkl. P1 scope-leak-fix). `main` = `2d636b0`,
oförändrad. `jakob-be` är 11 commits före `main`; **sync-PR nu mergebar** (alla
near-blockers + P1 stängda), öppnas på operatörsbeslut. Inga öppna PR:er.
