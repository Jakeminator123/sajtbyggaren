# SKILL: route_remove

## Mål
Ta bort EN hel icke-obligatorisk sida (route) och dess nav-länk via ett
strukturerat direktiv, så en följdprompt ("ta bort sidan Om oss", "radera
kontaktsidan") ger en ny immutabel version där sidan inte längre skrivs, inte
syns i headern/footern och inte krävs av route-guards. Route/Nav Mutation V1,
ADR 0060.

> **INGEN dossier, INGEN fri filpatch.** route_remove är en editor-mutation:
> den skriver routeId till `directives.disabledRoutes`. Den deterministiska
> apply/render-kedjan validerar och applicerar (konduktörsprincipen — rollen
> *förstår och föreslår*, kedjan *validerar och applicerar*).

## Väg
router klassar `route_remove` och resolverar ett best-effort routeId ur
sid-etiketten ("om oss"→`about`, "kontakt"/"kontaktsidan"→`contact`,
"tjänster"→`services`) -> `run_followup_chain` (steg 3e) kör
`packages/generation/followup/route_directives.resolve_disabled_routes`, som
validerar routeId mot DENNA sajts scaffold-`defaultRoutes` + required-vakten ->
`apply_patch_plan(disabled_routes=...)` skriver `directives.disabledRoutes`
(STICKY: union med basversionen, så en borttagen sida inte återuppstår) ->
`build_site.py` beräknar `activeRoutes = scaffold defaultRoutes − disabledRoutes`
i EN filterpunkt, så `_nav_items_from_scaffold`, `routes_to_write`,
`_pick_contact_route` och route-guards alla ser bara aktiva routes -> targeted
render -> ny immutabel version. Endast per-sajt Project Input/version ändras;
delade mallar rörs aldrig. Scaffold-agnostiskt (fungerar på varje starter som
har en icke-obligatorisk route).

## Honesty
En okänd sida (ingen route med det id:t i scaffolden) eller en obligatorisk sida
(Slice A behåller `required`-sidor: hem/tjänster/kontakt) ger ärlig no-op
(`stage=route_remove_unsupported`) med konkret anledning — aldrig en påhittad
borttagning och aldrig en borttagen obligatorisk sida. Synlig-effekt-signalen
(`appliedVisibleEffect`/`previewShouldRefresh`) kommer från fil-diffen i kedjan:
den borttagna sidans fil försvinner och nav:en (delad layout) ändras, så en
verklig borttagning rapporteras ärligt.

## Gränser (Slice A)
- Bara icke-obligatoriska scaffold-`defaultRoutes` (t.ex. `about`).
- Obligatoriska sidor (`required: true`) behålls — att ta bort `contact` och
  retargeta dess CTA:er till `mailto:`/`tel:`/utelämna, plus en Quality
  Gate-länkscan mot aktiva routes, är nästa slice (`allow_required`).
- Wizard-extra-routes (faq/team/priser som ytas via `wizardMustHave`) är inte
  scaffold-`defaultRoutes`, så att ta bort dem är en senare slice — i Slice A
  ger de ärlig no-op ("finns inte bland scaffoldens sidor").

## Status
supported — router (`route_remove` editKind + schema) + route_editor-roll +
route_directives + apply (`directives.disabledRoutes`, sticky) + build-filter +
tester. Se `../../action-registry.json`.
