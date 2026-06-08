# SKILL: section_add

## Mål
Lägg till EN sanktionerad sektion på en befintlig route via apply-kedjan, så en
följdprompt ("lägg till en FAQ-sektion") ger en ny version med sektionen synlig
i preview.

## Sanktionerade sektionstyper (MVP)
team, faq, garantier/trust, recensioner. Återanvänd befintliga
render_section_*-renderare + dossiers; uppfinn ingen ny renderare om en finns.

## Väg
router (section_add, typ-slug på componentIntent) -> `run_followup_chain`
resolverar typ -> capability (`faq`→faq-section, `reviews`→reviews, `team`→
team-section, `trust`→guarantees) med implementerande dossier ->
`apply_patch_plan` (requestedCapabilities + selectedDossiers.required, samma
maskineri som component_add) -> targeted render -> ny immutabel version. Endast
per-sajt Project Input/version ändras; delade mallar rörs aldrig.

## Honesty
Okänd/ostödd sektionstyp -> ärlig no-op (`stage=section_unsupported`) med
anledning. Synlig-effekt-signalen (`appliedVisibleEffect`/
`previewShouldRefresh`) kommer från kedjan, aldrig påhittad.

## Status
supported (2026-06-08) — router + apply-väg + tester + verify_openclaw inne på
`jakob-be` (se `../../action-registry.json`).
