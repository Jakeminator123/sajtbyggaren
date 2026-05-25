# GAP-section-design-treatments

```yaml
id: GAP-section-design-treatments
type: Gap/Builder
owner: jakob
title: Section design-treatments — visuell unikhet inom samma section-id
whyNow: |
  Path B (GAP-backend-path-b-section-renderer) löste strukturell
  unikhet: clinic-healthcare, professional-services, agency-studio
  och local-service-business komponerar nu olika section-listor och
  ser därför strukturellt olika ut. Det vi inte löste är *visuell*
  unikhet inom samma section-id. Två agency-studio-sajter med samma
  sections.json-komposition ser i dag identiska ut bara för att
  ``render_section_selected_work_preview`` har en hårdkodad layout.

  ``_HERO_STYLE_BY_VARIANT`` är en första lösning på samma problem
  för hero-sektionen — varje variant pekar mot
  ``gradient | centered | split`` och ``_render_hero_block``
  dispatchar till tre olika hero-implementationer. Section design-
  treatments generaliserar mönstret: varje treatment-aware section
  läser ``_SECTION_TREATMENTS_BY_VARIANT`` (operator-pin /
  variant-default / section-default i den ordningen) och dispatchar
  till en privat ``_render_<section>_treatment_<treatment-id>``-
  funktion.

  Phase 1 (denna PR) levererar piloten:
    * ``_SECTION_TREATMENTS_BY_VARIANT`` + ``_treatment_for_section``
      i scripts/build_site.py
    * ``selected-work-preview`` får två treatments
      (editorial-stack / asymmetric-grid)
    * ``studio-monochrome`` mappas mot ``asymmetric-grid``;
      ``editorial-warm`` + ``bold-electric`` ärver
      ``editorial-stack`` (default)
    * 8 nya tester i tests/test_section_renderer_registry.py
    * docs/section-design-treatments-scout.md beskriver mekanik +
      Phase 2/3-roadmap.

  Phase 2 utökar selected-work-preview med ``marquee-row`` (motion-
  aware), introducerar treatments för ``treatment-list``,
  ``practice-grid``, ``expertise-areas`` och ``service-list``,
  och mappar dem mot resterande variants så LSB / clinic / PS /
  agency-studio var och en får tre visuellt distinkta varianter.

  Phase 3 öppnar mekaniken för operatör + LLM:
    * ``dossier.directives.sectionTreatments`` exponeras i
      project-input.schema.json så wizard / overlay kan binda en
      treatment till en specifik build.
    * Planeringsfasen (briefModel + planningModel) får tone-baserade
      heuristiker för att picka treatment efter ``tone`` +
      ``selectedDossiers``, samma plats som variant pickas idag.
    * Treatment-registry exporteras till discovery-payload så
      scaffold-selection-probe kan utvärdera tone→treatment-
      matchning.

scope: |
  - scripts/build_site.py (treatment-helper + per-section dispatch)
  - tests/test_section_renderer_registry.py (treatment-tester)
  - docs/section-design-treatments-scout.md (mekanik + roadmap)
  - docs/gaps/GAP-section-design-treatments.md (denna fil)
  - docs/workboard.json (note + completedGaps-flytt när Phase 1
    landat)

acceptanceCriteria:
  - "_treatment_for_section returnerar default för okänd variant"
  - "_treatment_for_section returnerar default för variant utan
    section-mappning"
  - "_treatment_for_section returnerar variant-pinnade treatment
    när mappning finns"
  - "render_section_selected_work_preview med variant_id=None
    levererar byte-identisk pre-pilot-output (editorial-stack)"
  - "render_section_selected_work_preview med
    variant_id='editorial-warm' levererar editorial-stack
    (default-inheritance)"
  - "render_section_selected_work_preview med
    variant_id='studio-monochrome' levererar asymmetric-grid
    (Studio nº-eyebrow + md:translate-y-12 + card-yta)"
  - "studio-bjork build (variant: studio-monochrome) genererar
    asymmetric-grid på /home; visuellt distinkt från editorial-warm
    + bold-electric builds av samma scaffold"
  - "Phase 1-changeset bryter inga existerande snapshots eller
    smoke-tester"

phases:
  - id: phase-1
    title: Pilot — selected-work-preview + studio-monochrome (Phase 1)
    status: completed
    note: |
      Pilot landade i sprint 2026-05-25 (commit 303eb33) och
      inkluderade treatment-helper, två treatments för
      selected-work-preview, variant-mappning och tester. PR #105
      öppen som Draft mot main.
  - id: phase-2
    title: Bredd — fem section-typer × fjorton treatments
    status: completed
    note: |
      Levererades i samma sprint 2026-05-25 som Phase 1.
        * selected-work-preview fick tredje treatment marquee-row
          (horisontellt scroll-snap-rail). Mappning: bold-electric.
        * treatment-list (clinic) fick split-cards (warm-care) +
          numbered-stack (modern-precision). minimal-rows behålls
          som default för clinic-calm.
        * practice-grid (PS) fick tabular (legal-classic) + grouped
          (accounting-trust). dense-grid behålls som default för
          consulting-modern.
        * expertise-areas (PS home) fick tag-cluster
          (consulting-modern). numbered-2col behålls som default
          för legal-classic + accounting-trust.
        * service-list (LSB) fick alternating-rows (warm-craft) +
          icon-strip (clinical-calm) + tabular (nordic-trust).
          card-grid behålls som default för midnight-counsel +
          pulse-fit.
      Tests: 49 nya assertions i tests/test_section_renderer_-
      registry.py. test_renderers_use_jsx_safe_string_for_-
      customer_text uppdaterades med fyra nya service-list-
      treatment-helpers så B30-skyddet hänger med.
  - id: phase-3a
    title: Operator-pin + schema + planning-prompt + wizard-UI
    status: completed
    completedAt: 2026-05-25
    note: |
      Levererat:
        * Schema: directives.sectionTreatments-block i
          governance/schemas/project-input.schema.json (per-section
          enum, additionalProperties:false). Backward-compat
          verifierad — directives är optional, gamla fixturer
          fortsätter validera.
        * ADR 0032 i governance/decisions/ förklarar resolve-ordning
          (operator-pin > variant-default > section-default) och
          varför briefModel hålls utanför scope.
        * Backend: scripts/build_site.py får
          _operator_pin_for_section + _treatment_for_section(
          operator_pin=...). Fem renderer-callsites uppdaterade
          (service-list, treatment-list, expertise-areas,
          practice-grid, selected-work-preview).
        * Resolver: packages/generation/discovery/resolve.py
          (_apply_directives_fields) merge-istället-för-overwrite
          för directives, sectionTreatments propagerar till
          project_input.directives.sectionTreatments.
        * Planning prompt: packages/generation/planning/plan.py
          får _SECTION_TREATMENTS_CATALOGUE + system-instructions-
          clause så planningModel kan resonera om visuell struktur
          utan att försöka pinna treatments själv (PlanningChoice
          orörd).
        * Wizard-UI: visual-step disclosure med Auto/per-treatment-
          knappar; treatment-options.ts speglar schema-enum +
          variant-defaults.
        * Tester: tests/test_section_treatments_resolve.py,
          tests/test_section_treatments_propagation.py,
          tests/test_section_treatments_prompts.py,
          tests/test_project_input_schema.py-utökningar.
  - id: phase-3b
    title: LLM-pick i planningModel
    status: planned
    note: |
      När briefModel/planningModel-output-shapen utökas så
      planeraren kan picka treatments själv (baserat på tone +
      selectedDossiers + brand-fingerprint), kommer LLM-tier ligga
      MELLAN operator-pin och variant-default. Helper-signaturen
      (_treatment_for_section) är förberedd för det utan att kräva
      renderer-ändringar.
  - id: phase-3c
    title: Treatment-registry export
    status: planned
    note: |
      Export `_SECTION_TREATMENTS_BY_VARIANT` till
      data/runs/<runId>/treatment-registry.json så scaffold-
      selection-probe kan utvärdera tone→treatment-matchning.
      Beror inte på 3b.
  - id: phase-3d
    title: Wizard-UI för operator-pin
    status: completed
    completedAt: 2026-05-25
    note: |
      Levererat tillsammans med 3a — disclosure i visual-step,
      treatment-options.ts, payload-mapping till
      directives.sectionTreatments. Christopher-lane som
      [scope-leak] under operatör-OK (paired med 3a-backend GAP).

reservedPaths:
  - scripts/build_site.py
  - tests/test_section_renderer_registry.py
  - docs/section-design-treatments-scout.md

collisionRisk: low
laneCheck: |
  Builder-only förändring i scripts/build_site.py + tester +
  docs. Ingen viewser/wizard-yta påverkas i Phase 1.

relatesTo:
  - GAP-backend-path-b-section-renderer
  - GAP-backend-restaurant-activation
```
