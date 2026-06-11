# SKILL: section_add

## Mål
Lägg till EN sanktionerad sektion på en befintlig route genom att MONTERA dess
capability+dossier via apply-kedjan, så en följdprompt ("lägg till en
FAQ-sektion") ger en ny immutabel version med sektionen monterad.

> **SYNLIGT för faq + team (flippat 2026-06-09), MOUNT-ONLY för resten:**
> section_add MONTERAR alltid capability + dossier i nästa version
> (`requestedCapabilities` + `selectedDossiers.required`).
>
> För `faq` och `team` (på scaffolden local-service-business) ytas sektionen
> dessutom som en *grundad dedikerad route* (`/faq` via render_faq, `/team` via
> render_team) genom den befintliga wizard-extra-route-vägen: apply skriver
> wizard-mustHave-etiketten på nästa versions meta-sidecar, så targeted-bygget
> genererar en ny sida och fil-diffen rapporterar ärligt
> `appliedVisibleEffect=true`/`previewShouldRefresh=true` (på ett shippbart
> bygge). `faq` är grundad per konstruktion; `team` kräver grundad
> `company.team` — en tom lista förblir ärligt mount-only
> (mounted-but-no-content), aldrig en påhittad platshållare. På andra scaffolds
> förblir faq/team mount-only tills deras renderare väljer in wizard-routes.
>
> För de övriga typerna (trust/garantier, recensioner, galleri, priser,
> öppettider, karta, kontaktformulär) gäller fortfarande mount-only: dossiern
> monteras men targeted-rendern visar INTE en ny sektion, så det blir ärligt
> `applied=true` men `appliedVisibleEffect=false`/`previewShouldRefresh=false`.
> galleri/priser/karta kan följa samma dedikerad-route-mönster härnäst.

## Sanktionerade sektionstyper
Originalfyra: team, faq, garantier/trust, recensioner. Breddat 2026-06-08
(commit 4c6ba67): gallery, pricing, öppettider (hours), karta (map),
kontaktformulär (contact-form) — totalt nio. Varje typ har en sektionstyp i
routerns `_SECTION_TYPES` OCH en implementerande dossier i
`SECTION_TYPE_CAPABILITY` (`packages/generation/followup/section_directives.py`).
Återanvänd befintliga `render_section_*`-renderare + dossiers; uppfinn ingen ny.
Ej sanktionerat: `hero`/`services` (sidsektioner, inte add-mål), `cta-banner`
(saknar dossier).

## Förhandsinfo (obligatorisk för dossier-arbete)
Dossier-formatet — manifest-fälten, de fem instructions-sektionerna,
soft/hard-reglerna och konsumtionsvägen — är låst i
`packages/generation/orchestration/dossiers/AGENT-GUIDE.md`. Läs den innan du
monterar eller författar en dossier; schema:
`governance/schemas/dossier.schema.json`.

## Väg
router (section_add, typ-slug på componentIntent) -> `run_followup_chain`
resolverar typ -> capability (`faq`→faq-section, `reviews`→reviews, `team`→
team-section, `trust`→guarantees, `gallery`→gallery, `pricing`→pricing,
`hours`→hours, `map`→location, `contact-form`→contact-form) med implementerande
dossier -> `apply_patch_plan` (requestedCapabilities + selectedDossiers.required,
samma maskineri som component_add) -> targeted render -> ny immutabel version.
Endast per-sajt Project Input/version ändras; delade mallar rörs aldrig.

**Roll-driven dispatch (F1 slice 3):** `run_followup_chain` väljer numera
section-add-handläggningen via den KLASSADE ROLLEN, inte den råa `editKind`:n.
`skill_for_edit_kind(editKind)` slår upp `section_builder`-rollen
(`role_for_edit_kind`) och läser dess `RoleContract.skill`; grinden jämför det
mot `SECTION_ADD_SKILL` (= section_builder-kontraktets skill,
`skills/section-add/SKILL.md`). Det gör rollvalet auktoritativt för dispatch och
gör att `RoleContract.skill` faktiskt läses. Beteende-ekvivalent med den gamla
`editKind == "section_add"`-grinden (bara section_add mappar till denna skill);
stylist/copy behåller sin `editKind`-gating tills de får egna slices.

## Honesty
Okänd/ostödd sektionstyp -> ärlig no-op (`stage=section_unsupported`) med
anledning. Synlig-effekt-signalen (`appliedVisibleEffect`/
`previewShouldRefresh`) kommer från fil-diffen i kedjan, aldrig påhittad: en
synlig route genereras bara när grundat innehåll finns (faq alltid, team bara
med grundad `company.team`), annars förblir det ärligt mount-only. FloatingChat
(`summarizeOpenClawBridge`) grindar success-raden på `previewShouldRefresh`, så
en mount-only-montering rapporteras ärligt som "registrerad men syns inte än"
— aldrig "genomförde ändringen".

## Status
supported — router + apply-väg + 9 typer + tester + verify_openclaw inne på
`jakob-be` (se `../../action-registry.json`). Synlig render landad för `faq` +
`team` på local-service-business (grundad dedikerad route); övriga sju typer är
fortfarande mount-only (följd: galleri/priser/karta nästa).
