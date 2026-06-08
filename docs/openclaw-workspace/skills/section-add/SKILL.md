# SKILL: section_add

## Mål
Lägg till EN sanktionerad sektion på en befintlig route genom att MONTERA dess
capability+dossier via apply-kedjan, så en följdprompt ("lägg till en
FAQ-sektion") ger en ny immutabel version med sektionen monterad.

> **MOUNT-ONLY (viktigt — undvik falsk success):** section_add MONTERAR
> capability + dossier i nästa version (`requestedCapabilities` +
> `selectedDossiers.required`), men de soft-dossiers är instruktioner-only och
> den deterministiska targeted-rendern visar INTE automatiskt en ny sektion på
> sidan. Resultatet är ärligt `applied=true` (version skriven) men
> `appliedVisibleEffect=false`/`previewShouldRefresh=false` (inget syns ännu).
> Synlig render av en monterad sektion + exakt sida/position-placering är en
> separat render-path-follow-up (Sprint 3B-spåret), inte denna skill.

## Sanktionerade sektionstyper
Originalfyra: team, faq, garantier/trust, recensioner. Breddat 2026-06-08
(commit 4c6ba67): gallery, pricing, öppettider (hours), karta (map),
kontaktformulär (contact-form) — totalt nio. Varje typ har en sektionstyp i
routerns `_SECTION_TYPES` OCH en implementerande dossier i
`SECTION_TYPE_CAPABILITY` (`packages/generation/followup/section_directives.py`).
Återanvänd befintliga `render_section_*`-renderare + dossiers; uppfinn ingen ny.
Ej sanktionerat: `hero`/`services` (sidsektioner, inte add-mål), `cta-banner`
(saknar dossier).

## Väg
router (section_add, typ-slug på componentIntent) -> `run_followup_chain`
resolverar typ -> capability (`faq`→faq-section, `reviews`→reviews, `team`→
team-section, `trust`→guarantees, `gallery`→gallery, `pricing`→pricing,
`hours`→hours, `map`→location, `contact-form`→contact-form) med implementerande
dossier -> `apply_patch_plan` (requestedCapabilities + selectedDossiers.required,
samma maskineri som component_add) -> targeted render -> ny immutabel version.
Endast per-sajt Project Input/version ändras; delade mallar rörs aldrig.

## Honesty
Okänd/ostödd sektionstyp -> ärlig no-op (`stage=section_unsupported`) med
anledning. Synlig-effekt-signalen (`appliedVisibleEffect`/
`previewShouldRefresh`) kommer från kedjan, aldrig påhittad. FloatingChat
(`summarizeOpenClawBridge`) grindar success-raden på `previewShouldRefresh`, så
en mount-only-montering rapporteras ärligt som "registrerad men syns inte än"
— aldrig "genomförde ändringen".

## Status
supported (mount-only) — router + apply-väg + 9 typer + tester + verify_openclaw
inne på `jakob-be` (se `../../action-registry.json`). Synlig render = follow-up.
