# SKILL: route_editor (route_remove + nav_hide)

> route_editor-rollen äger två route/nav-mutationer: `route_remove` (ta bort en
> hel sida, nedan) och `nav_hide` (dölj en sidas nav-länk men behåll sidan, sist
> i filen). Båda är strukturerade direktiv, aldrig fri filpatch; de delar denna
> skill.

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
En okänd sida (ingen route med det id:t i scaffolden) eller en skyddad
obligatorisk sida (hem/tjänster behålls alltid) ger ärlig no-op
(`stage=route_remove_unsupported`) med konkret anledning — aldrig en påhittad
borttagning och aldrig en borttagen skyddad sida. Synlig-effekt-signalen
(`appliedVisibleEffect`/`previewShouldRefresh`) kommer från fil-diffen i kedjan:
den borttagna sidans fil försvinner och nav:en (delad layout) ändras, så en
verklig borttagning rapporteras ärligt.

## Kontakt-borttagning (Slice B)
`contact` kan tas bort fast den är `required`, eftersom det finns en säker
CTA-fallback. Steg 3e anropar resolvern med `allow_required_ids={"contact"}`
(hem/tjänster förblir skyddade). När contact tas bort:
- `_pick_contact_route` returnerar `None`; `write_pages` löser EN kontakt-target
  via `_contact_cta_target`: `mailto:` en riktig e-post → `tel:` ett riktigt
  telefonnummer → annars `None` (utelämna CTA:n ärligt). Platshållar-värden
  (`+46 8 000 00 00` / `example.se`) räknas aldrig som riktiga.
- Varje kontakt-CTA går genom `_contact_href` (släpper igenom `mailto:`/`tel:`,
  utelämnar ankaret när målet är `None`) — ingen renderare hårdkodar `/kontakt`.
- En Quality Gate-länkscan (`internal-link-scan`, soft-blocking → `degraded`)
  failar på varje kvarvarande död intern `<a>/<Link>`-länk mot en route utan
  `page.tsx`, så ingen död `/kontakt`-länk kan överleva.

## Gränser
- Bara scaffold-`defaultRoutes`: icke-obligatoriska (t.ex. `about`) + den
  borttagbara obligatoriska `contact`. Hem/tjänster (och övriga `required`) är
  skyddade — aldrig borttagbara (resolvern refuserar, och build-filtret droppar
  dem aldrig som försvar på djupet).
- Wizard-extra-routes (faq/team/priser som ytas via `wizardMustHave`) är inte
  scaffold-`defaultRoutes`, så att ta bort dem är en senare slice — de ger ärlig
  no-op ("finns inte bland scaffoldens sidor").

## nav_hide (icke-destruktiv syster)
**Mål:** dölj EN sidas header/footer-nav-länk men BEHÅLL sidan, via en följdprompt
("dölj Om oss i menyn", "ta bort Om oss ur menyn", "ta bort länken till Kontakt").
En länk-/menybegäran kan ALDRIG radera en sida.

**Väg:** router klassar `nav_hide` (en hide/remove-verb + nav-scope — länk/meny
eller en meny-cue — + en resolverad sid-etikett; en uttrycklig sid-substantiv
vinner som `route_remove`) -> `run_followup_chain` (steg 3f) kör
`route_directives.resolve_hidden_nav_routes` (validerar mot scaffold; startsidan
behålls alltid i navet; okänd/redan-dold avvisas) -> `apply_patch_plan(hidden_nav_routes=...)`
skriver `directives.hiddenNavRoutes` (STICKY) -> `build_site.py` trådar id:na till
`write_pages → render_layout → _nav_items_from_scaffold`, som droppar ENBART
nav-posten (href,label) i EN söm.

**Skillnad mot route_remove:** `hiddenNavRoutes` filtreras INTE ur `activeRoutes`.
`page.tsx` skrivs ändå, route-guards/Quality Gate räknar sidan och
`_pick_contact_route` hittar fortfarande kontaktsidan. Synlig effekt kommer från
fil-diffen: den delade `layout.tsx` ändras (nav-posten borta), så `appliedVisibleEffect`
blir sant och preview uppdateras.

**Honesty:** en nav-begäran utan utpekad sida ("ta bort länken") blir en ärlig
`component_remove`-no-op (vi hittar aldrig på vilken sida som ska döljas); en
okänd/startsida eller redan-dold länk ger `stage=nav_hide_unsupported` — aldrig
en påhittad döljning.

## Status
supported — router (`route_remove` + `nav_hide` editKinds + schema) +
route_editor-roll (äger båda) + route_directives (`resolve_disabled_routes` /
`resolve_hidden_nav_routes`) + apply (`directives.disabledRoutes` /
`hiddenNavRoutes`, sticky) + build-filter (`_REMOVABLE_REQUIRED_ROUTE_IDS`) +
nav-söm (`_nav_items_from_scaffold(hidden_nav_route_ids=...)`) +
kontakt-CTA-retarget (`_contact_cta_target`/`_contact_href`) + Quality Gate
`internal-link-scan` + tester. Se `../../action-registry.json`.
