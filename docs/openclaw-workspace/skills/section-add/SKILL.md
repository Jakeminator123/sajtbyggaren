# SKILL: section_add

## Mål
Lägg till EN sanktionerad sektion på en befintlig route via apply-kedjan, så en
följdprompt ("lägg till en FAQ-sektion") ger en ny version med sektionen synlig
i preview.

## Sanktionerade sektionstyper (MVP)
team, faq, garantier/trust, recensioner. Återanvänd befintliga
render_section_*-renderare + dossiers; uppfinn ingen ny renderare om en finns.

## Väg
router (section_add) -> patch/plan -> apply_patch_plan -> targeted render -> ny
immutabel version. Endast per-sajt Project Input/version ändras; delade mallar
rörs aldrig.

## Honesty
Okänd/ostödd sektionstyp -> ärlig no-op med anledning. Synlig-effekt-signalen
kommer från kedjan, aldrig påhittad.

## Status
planned — nästa Builder-slice (se `../../action-registry.json`).
