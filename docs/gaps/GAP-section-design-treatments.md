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
  - id: phase-3
    title: Operator-pin + LLM-pick
    status: blocked
    note: |
      Blockers innan start:
        1. PR #105 (Phase 1 + Phase 2) måste mergas till main så
           Phase 3 bygger på en clean baseline.
        2. GAP-backend-path-b-section-renderer måste flyttas till
           completedGaps (Phase 1 + 2 landade som [scope-leak] under
           Path B; Phase 3 är för bred för samma manöver).
        3. governance/schemas/project-input.schema.json får
           dossier.directives.sectionTreatments som valfritt objekt.
           Backward-compat verifieras mot alla 8 fixturer.
        4. briefModel + planningModel uppdateras för att picka
           treatment per tone + selectedDossiers. Mock-fallback +
           OPENAI_API_KEY-pathen verifieras båda.
        5. Wizard-UI för operator-pin per scaffold-relevant sektion
           designas (Christopher-lane).

      Delsteg när blockers är lösta:
        * 3a — schema-utökning + operator-pin
          (dossier.directives.sectionTreatments). Treatment-pin tar
          precedens över variant-default.
        * 3b — LLM-pick i planningModel.
        * 3c — treatment-registry export till discovery-payload.
        * 3d — wizard-UI för operator-pin.

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
