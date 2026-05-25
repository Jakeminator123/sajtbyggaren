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
    status: in-flight
    note: |
      Pilot landar i sprint 2026-05-25 och inkluderar treatment-helper,
      två treatments för selected-work-preview, variant-mappning och
      tester. När Phase 1 mergas flyttas GAP:en till completedGaps
      och Phase 2 öppnar.
  - id: phase-2
    title: Bredd — fyra section-typer × tre treatments
    status: planned
    note: |
      selected-work-preview får marquee-row.
      treatment-list får minimal-rows / split-cards / numbered-stack.
      practice-grid får dense-grid / tabular / grouped.
      expertise-areas får numbered-2col / tag-cluster.
      service-list (LSB) får card-grid / alternating-rows /
      icon-strip / tabular.
      Variant-mappningar utökas så varje aktiv scaffold får tre
      visuellt distinkta varianter.
  - id: phase-3
    title: Operator-pin + LLM-pick
    status: planned
    note: |
      project-input.schema.json får
      dossier.directives.sectionTreatments. briefModel +
      planningModel pickar treatment per tone +
      selectedDossiers. discovery-payload exporterar treatment-
      registry.

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
