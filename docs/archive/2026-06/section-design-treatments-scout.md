---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

# Section Design Treatments — Scout

> **Arkivnot (lane A, 2026-06):** Historisk scout-rapport (Phase 1+2+3a shipped,
> ADR 0032). Flyttad från `docs/section-design-treatments-scout.md`. En
> runtime-kommentar i `packages/generation/build/dispatcher.py` pekar fortfarande
> på den gamla sökvägen (icke-blockerande; lämnas till backend-lane). Sanningskälla
> för nuläget: `docs/current-focus.md`. Se `docs/archive/README.md`.

Status: **Phase 1 + Phase 2 + Phase 3a implemented (ADR 0032)**
— operator-pin, schema, planning-prompt och wizard-UI shipped
2026-05-25. Återstår: Phase 4 (LLM-pick) och en eventuell Phase 3c
(treatment-registry export i `_treatment_registry.json`).
Owner: jakob (backend) — Christopher körde pilot + Phase 2 + Phase 3
under 2026-05-25 som [scope-leak] med operatör-OK.
Tracks: GAP-section-design-treatments-phase-3-backend (closed),
GAP-section-design-treatments-phase-3-ui (closed)

## Problemet

Path B (`GAP-backend-path-b-section-renderer`) löste **strukturell**
unikhet — vilka sektioner som komponeras per scaffold (clinic ≠ PS ≠
agency-studio ≠ LSB). Det vi inte löste är **visuell** unikhet inom
samma section-id. Två agency-studio-sajter med samma section-
komposition ser i dag identiska ut bara för att `render_section_-
selected_work_preview` har en hårdkodad layout.

`_HERO_STYLE_BY_VARIANT` är en första, smal lösning på samma
problem för hero-sektionen — varje variant pekar mot
`gradient | centered | split` och `_render_hero_block` dispatchar
till tre olika hero-implementationer. Section design-treatments
generaliserar mönstret.

## Mekaniken

Tre lager, samma hierarki som `_hero_style_for`:

1. **Operator-pin** via `dossier.directives.sectionTreatments`
   — operatören kan binda en specifik treatment till en specifik
   section-id för en specifik build (tex `selected-work-preview:
   asymmetric-grid`). Inte i pilot.
2. **Variant-default** via `_SECTION_TREATMENTS_BY_VARIANT`
   — varje variant deklarerar sina default-treatments per section-
   id. Det är där pilotens mappningar landar.
3. **Section-default** — varje section-renderer definierar sin
   "current" treatment som fallback när varken operatör eller
   variant pekar mot något.

Renderer-signatur utökas med `treatment: str | None = None` och
en intern dispatcher (`_render_<section>_treatment_<treatment-id>`).
Renderern själv slås upp via `_treatment_for_section(variant_id,
section_id, default)` som speglar `_hero_style_for`-helperns
mönster.

`render_route_generic` skickar redan `variant_id` till varje
section-renderer via `_section_renderer_kwargs` + `_call_section_-
renderer`, så ingen ny dispatch-infrastruktur krävs på den nivån
— vi lägger bara `treatment` på de renderers som faktiskt
implementerar treatment-dispatch.

## Pilot-scope (Phase 1, denna PR)

* En sektion: `selected-work-preview` (agency-studio /home).
* Två treatments:
  * `editorial-stack` — current implementation, 2-col card
    layout med `border-t` och numeric eyebrow. Behålls som
    section-default så befintliga builds är byte-identiska.
  * `asymmetric-grid` — offset-grid där varannan card är
    vertikalt förskjuten med `md:translate-y-12`, kopplad
    till `studio-monochrome`-varianten. Samma data, helt
    annan visuell rytm.
* Variant-mappning:
  * `studio-monochrome` → `asymmetric-grid` (pilot demo)
  * `editorial-warm` → `editorial-stack` (default)
  * `bold-electric` → `editorial-stack` (default i pilot,
    väntar på `marquee-row` som Phase 2-treatment)

Effekt: `studio-bjork`-fixturen (variant: studio-monochrome)
renderar nu en visuellt distinkt selected-work-preview
jämfört med editorial-warm / bold-electric. Vi har för
första gången två agency-studio-sajter som ser markant
olika ut även med samma section-komposition.

## Phase 2-implementation (denna PR — landar 2026-05-25)

Phase 2 utökar treatment-katalogen från 1 sektion × 2 treatments
till **5 sektioner × 14 treatments**, alla via samma
`_treatment_for_section`-mekanik som piloten lade. Ingen ny
infrastruktur — bara fler renderers + variant-mappningar.

* `selected-work-preview` får tredje treatment `marquee-row`
  — horisontellt scroll-snap-rail med 6 tighta cards och
  gradient-edge-mask. Phase 2 lämnar autoanimation åt sidan
  (reduced-motion-användare får exakt samma scroll-able rail).
  Mappad till `bold-electric`.
* `treatment-list` (clinic-healthcare) får tre treatments:
  * `minimal-rows` (default, byte-identical) →
    `clinic-calm` (default-keep)
  * `split-cards` → `warm-care`
  * `numbered-stack` → `modern-precision`
* `practice-grid` (professional-services /expertis) får tre
  treatments:
  * `dense-grid` (default, byte-identical) →
    `consulting-modern` (default-keep)
  * `tabular` → `legal-classic`
  * `grouped` → `accounting-trust`
* `expertise-areas` (PS home) får två treatments:
  * `numbered-2col` (default, byte-identical) →
    `legal-classic` + `accounting-trust` (default-keep)
  * `tag-cluster` → `consulting-modern`
* `service-list` (LSB /tjanster) får fyra treatments:
  * `card-grid` (default, byte-identical) →
    `midnight-counsel` + `pulse-fit` (default-keep)
  * `alternating-rows` → `warm-craft`
  * `icon-strip` → `clinical-calm`
  * `tabular` → `nordic-trust`

Effekt: varje scaffold (clinic, PS, agency-studio, LSB) har
nu minst 2 visuellt distinkta variants utöver toner + tokens
— operatören kan se identiska sektioner men diametralt olika
sajter.

Tester: `tests/test_section_renderer_registry.py` lockar
treatment-dispatchen för alla fem sektionerna med 49 assertions
(per-treatment markup-markers + byte-identical default-fallback
+ empty-fallback per variant). `test_renderers_use_jsx_safe_-
string_for_customer_text` förlängdes med fyra service-list-
treatment-helpers så B30 inte regresserar.

## Phase 3-roadmap (status 2026-05-25)

Phase 3 lägger operator-pin via `dossier.directives.section-
Treatments` och LLM-pick i planeringsfasen så att treatment-
valen kan styras från wizard / brief / plan istället för
hårdkodad variant-mappning.

**Blockers (alla lösta 2026-05-25):**

1. ✅ Phase 1 + Phase 2 mergades till `main` via PR #105
   (commit `fe7a9e4`).
2. ✅ `GAP-backend-path-b-section-renderer` (Path B-paraplyet)
   flyttades till `completedGaps`. Phase 3-arbetet körs som ny
   GAP-`GAP-section-design-treatments-phase-3-backend` (closed
   2026-05-25 efter ADR 0032).
3. ✅ Schema-utökning: `directives.sectionTreatments`-block med
   per-section `additionalProperties: false`-enum landade i
   `governance/schemas/project-input.schema.json` (commit
   `45955dd`). Drift mot runtime-tabellen vaktas av
   `tests/test_project_input_schema.py`.
4. ✅ LLM-prompts: `_SECTION_TREATMENTS_CATALOGUE` + system-
   instructions clause i `packages/generation/planning/plan.py`
   (commit `2364b17`). Mock-fallback bevarad — pinned/mock
   plan-paths lämnar payloaden orörd (per `test_section_-
   treatments_prompts.py`). `briefModel` rörs inte (ADR 0032
   §5: brief har ingen `directives`-slot).
5. ✅ Wizard-UI: section-treatments-disclosure i visual-step
   med Auto/per-treatment-knappar (commit `f9f26a4`).

**Phase 3-delsteg:**

* ✅ 3a — schema-utökning + operator-pin (`dossier.directives.-
  sectionTreatments`). Treatment-pin tar precedens över
  variant-default.
* ⏳ 3b — LLM-pick i `planningModel` baserat på `tone` +
  `selectedDossiers`. (Catalogue + prompt clause levererat
  i prep-steget; faktisk pick implementeras separat när
  briefModel/planningModel-output-shapen utökas.)
* ⏳ 3c — treatment-registry export till discovery-payload så
  `scaffold-selection-probe` kan utvärdera tone→treatment-
  matchning.
* ✅ 3d — wizard-UI för operator-pin per scaffold-relevant
  sektion. Christopher-lane.

Återstår alltså 3b + 3c + en eventuell Phase 4 (LLM-pick som
kommer FÖRE operator-pin i resolve-ordningen).

## Quality / regression

* Befintliga snapshots ska vara byte-identiska för varianter
  som mappar till section-default-treatment. Verifieras genom
  att `editorial-warm` och `bold-electric` builds är diff-
  nollade mot pre-pilot output.
* `studio-bjork` ändras eftersom dess variant byter treatment
  — det är den medvetna effekten av piloten och ska bekräftas
  i testen `test_section_renderer_registry::test_selected_work_-
  preview_treatment_dispatch`.
* `_treatment_for_section` har egna unit-tester för fallback-
  kedjan (variant → section-default).

## Naming dictionary

selected-work-preview (agency-studio):

* `editorial-stack` (treatment-id) — en redaktionell,
  vertikalt staplad treatment där varje case-card sitter på
  samma baseline-rad. Default för selected-work-preview.
* `asymmetric-grid` (treatment-id) — varje udda card är
  vertikalt offset så grid:en bryter sin rytm. Pilot-mappning:
  studio-monochrome.
* `marquee-row` (treatment-id, Phase 2) — horisontellt
  scroll-snap-rail med 6 tighta cards och gradient-edge-mask.
  Phase 2-implementation lämnar autoanimation åt sidan;
  reduced-motion-användare får samma rail. Mappning:
  bold-electric.

treatment-list (clinic-healthcare):

* `minimal-rows` (treatment-id) — vertikal lista av rounded-
  card-rows med tunn typ-header. Default. Mappning: clinic-calm.
* `split-cards` (treatment-id, Phase 2) — 2-col grid av varma
  cards med accent-tinted left-rail. Mappning: warm-care.
* `numbered-stack` (treatment-id, Phase 2) — sekvens med
  stora mono-numerals och tunna horisontella separatorer.
  Mappning: modern-precision.

practice-grid (professional-services):

* `dense-grid` (treatment-id) — 3-col compact card-grid.
  Default. Mappning: consulting-modern.
* `tabular` (treatment-id, Phase 2) — formell row-listing utan
  card-chrome, kolumnheader, tunna border-b-separators.
  Mappning: legal-classic.
* `grouped` (treatment-id, Phase 2) — 2-col feature-kolumner
  med numrerade eyebrows. Mappning: accounting-trust.

expertise-areas (professional-services /home):

* `numbered-2col` (treatment-id) — 2-col-grid med numrerade
  eyebrows och left-rail-borders. Default. Mappning:
  legal-classic, accounting-trust.
* `tag-cluster` (treatment-id, Phase 2) — pill-cluster där
  varje practice är en kompakt rounded pill, summary-line
  under clustret. Mappning: consulting-modern.

service-list (local-service-business):

* `card-grid` (treatment-id) — 3-col gradient-headered
  card-grid med icon-bubble. Default. Mappning:
  midnight-counsel, pulse-fit.
* `alternating-rows` (treatment-id, Phase 2) — vertikal
  sekvens där udda rader har icon-tile vänster, jämna rader
  flippar via flex-row-reverse. Mappning: warm-craft.
* `icon-strip` (treatment-id, Phase 2) — kompakt horisontellt
  pill-band med summaries på en quiet grid under. Mappning:
  clinical-calm.
* `tabular` (treatment-id, Phase 2) — formell row-listing med
  icon / label / summary-kolumner och tunn border-b. Mappning:
  nordic-trust.
