# Scout-rapport — wizard-overlay, pageCount, tone propagation

Run-ID studerad: 20260519T190606.540Z-51cef6dd-skoldpaddssoppa-karlsson-099d5c
HEAD vid kartläggning: 369036f

## Fråga 1 — company.tagline-kodvägen

- Fil: apps/viewser/components/discovery-wizard/steps/company-step.tsx:160-164; apps/viewser/components/discovery-wizard/wizard-payload.ts:168-170; packages/generation/discovery/resolve.py:609-628
- Funktion: CompanyStep -> composeMasterPrompt -> resolve_discovery._apply_company_fields
- Kodutdrag:

```tsx
      <TextareaField
        label="Beskriv din verksamhet *"
        value={answers.offer}
        onChange={(value) => onChange({ offer: value })}
        placeholder="Vad gör ni? Vilka är era kunder? Vad gör er unika?"
        rows={4}
      />
```

```ts
  const companyLines: string[] = [];
  if (answers.companyName.trim()) companyLines.push(`Namn: ${answers.companyName.trim()}`);
  if (answers.offer.trim()) companyLines.push(`Vad vi gör: ${answers.offer.trim()}`);
  if (answers.existingSite.trim()) companyLines.push(`Befintlig hemsida: ${answers.existingSite.trim()}`);
```

```py
    offer = answers.get("offer")
    if isinstance(offer, str) and offer.strip():
        first_sentence = offer.strip().split(". ")[0][:140]
        company["tagline"] = first_sentence
        field_sources["company.tagline"] = "wizard"
    elif company.get("tagline"):
        field_sources["company.tagline"] = "brief"
```

- Förklaring: Steg 1-fältet "Beskriv din verksamhet" sparas som `answers.offer`. `composeMasterPrompt()` skickar samma text till briefModel som raden `Vad vi gör: ...`, men `buildDiscoveryPayload()` skickar också hela `answers` separat som discovery-payload. Efter att `scripts/prompt_to_project_input.py` har byggt en brief-baserad Project Input körs `resolve_discovery()`, och `_apply_company_fields()` låter wizardens `offer` vinna över briefens tagline och markerar `fieldSources.company.tagline = "wizard"`. Därför hamnar fältet direkt som `company.tagline` i stället för att bara fungera som rådata till briefen.
- Builder-tips: Minimal fix-yta är `packages/generation/discovery/resolve.py:_apply_company_fields`. Byt inte bara `_derive_tagline`; den grenen har redan passerats när discovery-payloaden skriver över tagline. Kandidatfix: behandla `offer` som verksamhetsbeskrivning/input till tjänster eller story, och skapa tagline via kort postprocessad fras när texten innehåller sidantal/färg/instruktioner.

## Fråga 2 — brief.pageCount → routePlan

- Fil: packages/generation/planning/plan.py:561-567, 728-741, 802-920
- Funktion: produce_site_plan -> _route_plan_from_scaffold -> _assemble_site_plan
- Kodutdrag:

```py
def _route_plan_from_scaffold(scaffold: dict[str, Any]) -> list[dict[str, str]]:
    routes = scaffold.get("routes") or {}
    defaults = routes.get("defaultRoutes") or []
    return [
        {"id": r["id"], "path": r["path"], "purpose": r["purpose"]}
        for r in defaults
    ]
```

```py
    created_at = _utc_now_iso()
    route_plan = _route_plan_from_scaffold(scaffold)
    site_plan = _assemble_site_plan(
        run_id=run_id,
        choice=choice,
        scaffold=scaffold,
        starter_id=starter_id,
```

```py
        "starterId": starter_id,
        "routePlan": route_plan,
        "pageIntentWarnings": page_intent_warnings,
        "selectedDossiers": _selected_dossiers_payload(choice),
        "buildSpec": {
            "qualityTarget": 9.0,
```

- Förklaring: `produce_site_plan()` tar emot hela `site_brief`, men läser aldrig `site_brief["pageCount"]`. Route-planen skapas i stället genom `_route_plan_from_scaffold(scaffold)`, som okritiskt returnerar `routes.defaultRoutes` från scaffolden. För `local-service-business` är defaults fyra routes: `/`, `/tjanster`, `/om-oss`, `/kontakt`, så `pageCount=2` kan inte påverka `site-plan.json`.
- Builder-tips: Minimal fix-yta är `packages/generation/planning/plan.py`, inte renderer eller Viewser. För att faktiskt respektera `pageCount` behövs både trim/kurering av `route_plan` i `produce_site_plan()` och en warning när scaffold-defaults reduceras eller när sidantalet inte går att uppfylla säkert. Warning-only är minsta risk, men stänger inte beteendegapet.

## Fråga 3 — tone.primary-kodvägen

- Fil: scripts/build_site.py:701-737; scripts/build_site.py:2107-2136; packages/generation/codegen/codegen.py:151-184
- Funktion: variant_css / patch_globals_css; project_input_to_brief_prompt; _summarise_generation_package
- Kodutdrag:

```py
def variant_css(variant: dict) -> str:
    tokens = variant["tokens"]
    color = tokens["color"]
    radius = tokens["radius"]
    spacing = tokens["spacing"]
    return (
        ":root {\n"
        f"  --background: {color['background']};\n"
        f"  --foreground: {color['foreground']};\n"
        f"  --muted: {color['muted']};\n"
        f"  --border: {color['border']};\n"
        f"  --primary: {color['primary']};\n"
```

```py
        f"Tone primary: {tone.get('primary')}\n"
        f"Tone secondary: {_join_values(tone.get('secondary', []))}\n"
        f"Tone avoid: {_join_values(tone.get('avoid', []))}\n"
        f"Conversion goals: {_join_values(dossier.get('conversionGoals', []))}\n"
```

```py
    site_brief = generation_package.get("siteBrief") or {}
    scaffold = generation_package.get("scaffoldId", "?")
    variant = generation_package.get("variantId", "?")
    business_type = site_brief.get("businessTypeGuess")
    tone = site_brief.get("tone") or []
```

- Förklaring: Project Input `tone.primary` passerar in i briefModel-prompten via `project_input_to_brief_prompt()` och kan också hamna i Site Brief som `tone`. Den praktiska CSS-token-skrivningen sker däremot i `variant_css()`, som bara läser `variant["tokens"]`; `patch_globals_css()` skickar bara in `variant`, inte dossier/tone/brand. `packages/generation/codegen/codegen.py` kan nämna `tone` i codegenModel-rationale om `generation_package` innehåller `siteBrief`, men den helpern skriver inte CSS och har ingen möjlighet att översätta `grön` till `--primary`.
- Builder-tips: Minimal fix-yta för färgpropagation är `scripts/build_site.py:variant_css` / `patch_globals_css`, t.ex. genom att låta helpern ta `dossier` eller ett token-override-objekt och mappa `tone.primary` eller `brand.primaryColorHex` före CSS skrivs. `packages/generation/codegen/` är inte rätt första fixpunkt för renderad färg; där syns temat bara som manifest/rationale-yta.

## Bonus — Intent Guard-yta

- Jämförelsepunkten bör ligga i `scripts/build_site.py:build_plan_artefakts` runt anropet till `produce_site_plan()` eftersom funktionen samtidigt har `site_brief` (`businessTypeGuess`) och `prompt_meta` (`discoveryDecision.categoryIds` från wizardens kategori).
- Emissionspunkten för `site-plan.json` är `packages/generation/planning/plan.py:produce_site_plan` / `_assemble_site_plan`, där `pageIntentWarnings` redan skapas och läggs i plan-artefakten.

## Eventuella ytterligare fynd

- `scripts/build_site.py:variant_css()` ignorerar även explicit `brand.primaryColorHex`, trots att `packages/generation/discovery/resolve.py:_apply_brand_and_assets()` kan skriva `brand.primaryColorHex` från wizardens hex-fält.
- `packages/generation/planning/plan.py:_assemble_generation_package()` skriver bara `siteBriefRef`, inte `siteBrief`; därför är `packages/generation/codegen/codegen.py:_summarise_generation_package()`s `tone`-läsning inte aktiv i builderns normala generation package.
