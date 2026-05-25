# Section Design Treatments — Scout

Status: **draft, in-flight (Phase 1 pilot)**
Owner: jakob (backend) — Christopher tar pilot 2026-05-25 som
[scope-leak] under operatör-OK.
Tracks: GAP-section-design-treatments

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

## Phase 2-roadmap (inte i denna PR)

* `selected-work-preview` får tredje treatment `marquee-row`
  (horisontell scroll, motion-aware). Kopplas till
  `bold-electric`.
* `treatment-list` (clinic-healthcare) får
  `minimal-rows | split-cards | numbered-stack`. Mappa mot
  `clinic-calm | warm-care | modern-precision`.
* `practice-grid` (PS) får `dense-grid | tabular | grouped`.
* `expertise-areas` (PS home) får `numbered-2col | tag-cluster`.
* `service-list` (LSB) får `card-grid | alternating-rows |
  icon-strip | tabular`.

## Phase 3-roadmap (operator-pin + LLM-pick)

* `dossier.directives.sectionTreatments` — wizard / overlay
  exponerar treatment-val per scaffold-relevant sektion.
* LLM pickar treatment baserat på `tone` + `selectedDossiers`
  i planeringsfasen (samma plats som variant pickas idag).
* Treatment-registry exporteras till discovery-payload så
  scaffold-selection-probe kan utvärdera tone→treatment-
  matchning.

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

* `editorial-stack` (treatment-id) — en redaktionell,
  vertikalt staplad treatment där varje case-card sitter på
  samma baseline-rad. Default för selected-work-preview.
* `asymmetric-grid` (treatment-id) — varje udda card är
  vertikalt offset så grid:en bryter sin rytm. Pilot-mappning:
  studio-monochrome.
* `marquee-row` (treatment-id, Phase 2) — horisontellt
  scrollande rad av case-cards. Motion-aware; render-time
  fallback till editorial-stack om motion-policy är `subtle`
  eller `none`.
