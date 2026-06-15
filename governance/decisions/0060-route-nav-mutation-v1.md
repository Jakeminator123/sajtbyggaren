# ADR 0060 — Route/Nav Mutation V1 (route_remove: ta bort sida + nav-länk)

**Status:** Accepted (Slice A implementerad 2026-06-15; Slice B —
contact-borttagning + CTA-retarget + länkscan — implementerad 2026-06-15)
**Beroenden:** ADR 0057 (rollkontrakt), ADR 0038 (synlig sektionsrender,
mönstret för `directives`-driven render), ADR 0036 (router-vokabulär), ADR 0034
(följdprompt-väg). Coach + operatör 2026-06-15.
**Berörda filer:**
[`router/models.py`](../../packages/generation/orchestration/router/models.py),
[`router/classify.py`](../../packages/generation/orchestration/router/classify.py),
[`router-decision.schema.json`](../schemas/router-decision.schema.json),
[`project-input.schema.json`](../schemas/project-input.schema.json),
[`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json),
[`route_directives.py`](../../packages/generation/followup/route_directives.py),
[`openclaw/roles.py`](../../packages/generation/orchestration/openclaw/roles.py),
[`apply.py`](../../packages/generation/orchestration/apply/apply.py),
[`scripts/build_site.py`](../../scripts/build_site.py),
[`action-registry.json`](../../docs/openclaw-workspace/action-registry.json).
Slice B berör dessutom:
[`build/renderers.py`](../../packages/generation/build/renderers.py),
[`build/render_helpers.py`](../../packages/generation/build/render_helpers.py),
[`quality_gate/checks.py`](../../packages/generation/quality_gate/checks.py),
[`quality_gate/gate.py`](../../packages/generation/quality_gate/gate.py),
[`quality_gate/models.py`](../../packages/generation/quality_gate/models.py),
[`quality-result.schema.json`](../schemas/quality-result.schema.json).

## Kontext

OpenClaw/följdprompt kunde inte ens TA BORT en sida. "ta bort Kontakt" klassades
som `component_remove` eller föll till `action_bridge_missing` — routern saknade
`route_remove`. Det är basal redigeringsförmåga och det skarpaste "mekaniska"
glappet i kärnloopen (coach + operatör 2026-06-15). Detta är första förmågan i
modellen "en konduktör, fler förmågor": rollerna växer, inte antalet parallella
LLM-kedjor.

`route_remove` är en editor-mutation, INTE en dossier: en dossier är ett
kurerat feature-block (FAQ/galleri/contact-form), medan att ta bort en sida är
en strukturell mutation som den befintliga deterministiska apply/render-kedjan
kan utföra via ett direktiv. Principen (oförändrad): **frihet i förståelsen,
kontroll i appliceringen.**

## Beslut (Slice A — ta bort en icke-obligatorisk sida)

1. **Ny `EditKind` `route_remove`** i router-modellen + router-decision-schemat.
   Routern klassar "ta bort sidan X / radera X-sidan / ta bort Kontakt" som
   `route_remove` (FÖRE `component_remove`, så en widget-borttagning som "ta bort
   knappen" och en sektionstyp som "ta bort recensionerna" förblir
   `component_remove`). Routern resolverar ett best-effort `target.routeId` ur
   sid-etiketten ("om oss"→`about`, "kontakt"→`contact`, "tjänster"→`services`);
   den läser aldrig disk.

2. **Nytt direktiv `directives.disabledRoutes`** (lista med scaffold-routeId) i
   Project Input-schemat. STICKY/kumulativt: till skillnad från `mountedSections`
   (byggs om per version) union:as listan i apply med basversionens, så en
   borttagen sida inte återuppstår vid en senare orelaterad följdprompt.

3. **Ny `route_editor`-roll** (ADR 0057-mönstret) som äger `route_remove`,
   `status="supported"`, skill `skills/route-remove/SKILL.md`, korsvaliderad mot
   action-registret i `tests/test_openclaw_registry_consistency.py`.

4. **Ny resolver `route_directives.resolve_disabled_routes`** (speglar
   `section_directives`) validerar routeId mot DENNA sajts scaffold-`defaultRoutes`
   + required-vakten och returnerar `(disabled, refused)`. Scaffold-agnostisk —
   fungerar på varje starter som har en icke-obligatorisk route, inte en enda.

5. **EN filterpunkt i `build()`:** `activeRoutes = scaffold defaultRoutes −
   disabledRoutes`. Eftersom `all_default_routes`/`required_routes` →
   `routes_to_write`, `_nav_items_from_scaffold`, `_pick_contact_route` och
   route-guards alla läser samma struktur, filtreras sida + nav + guards i ett
   seam. Defense-in-depth: en `required`-route droppas ALDRIG här (även om ett
   handredigerat direktiv skulle innehålla den), så `_pick_contact_route` kan
   aldrig krascha bygget.

## Beslut (Slice B — ta bort `contact` (required) + säker CTA-fallback)

6. **`contact` blir borttagbar, men bara `contact`.** `run_followup_chain` steg
   3e anropar `resolve_disabled_routes(..., allow_required_ids={"contact"})`.
   Resolvern fick en ny parameter `allow_required_ids`: en `required`-route får
   tas bort bara om dess id ligger i den mängden. `home` refuseras alltid (före
   required-checken) och `services` (och alla andra `required`) förblir skyddade.
   Build-seamens `_filter_disabled_routes` speglar detta via en enda
   `_REMOVABLE_REQUIRED_ROUTE_IDS = {"contact"}` så upstream-refusal och
   defense-in-depth-filtret aldrig kan vara oense om vilken obligatorisk sida som
   är borttagbar.

7. **EN kontakt-target-chokepoint + tolerant `_pick_contact_route`.**
   `_pick_contact_route` returnerar `None` i stället för `SystemExit` när ingen
   contact-route finns. `write_pages` löser EN `contact_target` via
   `_contact_cta_target`: contact-routens path när sidan finns (Slice A, byte-
   identiskt), annars `mailto:` en riktig e-post → `tel:` ett riktigt
   telefonnummer → `None` (utelämna). "Riktig" = passerar
   `contact_placeholders`-vakterna (aldrig `+46 8 000 00 00`/`example.se`).

8. **Ny `_contact_href`-hjälpare (släpper igenom `mailto:`/`tel:`).** Till
   skillnad från `_route_href` (som kräver inledande `/` så nav:en aldrig
   emitterar en protokoll-href) släpper `_contact_href` igenom `mailto:`/`tel:`
   och returnerar `None` för allt annat. Varje kontakt-CTA-emittor (lager-header
   + footer, hero, contact-cta-band, service-list ×4, collection, products,
   wizard-CTA, klinik/PS/byrå-länkarna) går nu genom `_contact_href` (via de
   delade `_filled_contact_cta`/`_text_contact_cta`-hjälparna) och utelämnar
   ankaret ärligt när målet är `None`. Ingen renderare hårdkodar `/kontakt` i
   produktion; ett malformerat scaffold-`contact`-path failar fortfarande snabbt
   (`_contact_cta_target` validerar den befintliga routens path).

9. **Quality Gate `internal-link-scan` (soft-blocking → `degraded`).** En ny
   check skannar varje genererad `<a>/<Link href="/...">` och failar på en intern
   länk vars normaliserade path saknar `page.tsx` på disk (en död `/kontakt`-länk
   mot en borttagen sida). Härleds helt från disk (inkluderar wizard-extras
   `/faq`/`/arbeten` och dossier-routes `/spel`), så ett bygge utan borttagna
   routes är en no-op (noll falska positiva, byte-identiskt beteende).

## Vad ADR 0060 INTE beslutar (senare)

- Borttagning av wizard-extra-routes (faq/team/priser via `wizardMustHave`) — de
  är inte scaffold-`defaultRoutes`, så de ger ärlig no-op.
- Ren nav-only ("dölj i menyn men behåll sidan") — coachens `nav_edit`, en
  senare liten förmåga.

## Rails / ärlighet

Deterministisk apply + guards + immutabla versioner. Routern förstår och
föreslår; `route_directives` + `build()` validerar och materialiserar. En okänd
sida (inget routeId i scaffolden) eller en skyddad required-sida (hem/tjänster)
är en ärlig no-op (`stage=route_remove_unsupported`) med konkret anledning —
aldrig en påhittad eller falsk borttagning, aldrig fri filpatch. När `contact`
tas bort (Slice B) retargetas dess CTA:er till en riktig kanal
(`mailto:`/`tel:`) eller utelämnas ärligt, och `internal-link-scan` garanterar
att ingen död `/kontakt`-länk överlever.

## Verifiering (implementerad)

- router-klassning (`route_remove` + routeId; widget/sektion stannar
  `component_remove`), schema-paritet (`tests/test_router_classify.py`,
  `tests/test_router_schema.py`);
- resolver: icke-required → disabled, required/home → refused, okänd → refused,
  `allow_required`-sömmen (`tests/test_route_directives.py`);
- build-emission: med `disabledRoutes=["about"]` skrivs ingen `/om-oss/page.tsx`
  och nav saknar "Om oss" (`tests/test_wizard_route_emission.py`);
- E2E via `run_followup_chain` (`tests/test_followup_route_remove.py`): "ta bort
  sidan Om oss" → ny version utan sidan/nav; okänd → ärlig no-op; `disabledRoutes`
  sticky över en senare restyle;
- Slice B (`tests/test_followup_route_remove.py`): "ta bort sidan Kontakt och
  länkar dit" → ny version utan `/kontakt`, CTA:er retargetade till `mailto:`,
  inga döda interna `/kontakt`-länkar; "ta bort sidan Tjänster" → ärlig no-op
  (skyddad). Resolver-seamen `allow_required_ids` + skyddet av home/services
  (`tests/test_route_directives.py`); build-filter contact-borttagning + skydd
  (`tests/test_wizard_route_emission.py`); `_pick_contact_route`→None +
  CTA-target-fallback (`tests/test_contact_route_cta_targets.py`,
  `tests/test_builder_route_emission.py`); `internal-link-scan` ok/failed/degraded
  (`tests/test_quality_gate.py`); schema/Pydantic-paritet med den nya checken
  (`tests/test_artefact_schema_3c_lite.py`);
- roll/registry-konsistens (`tests/test_openclaw_roles.py`,
  `tests/test_openclaw_registry_consistency.py`); ruff 0; `verify_openclaw` 6/6;
  governance/rules_sync/term-coverage gröna.
