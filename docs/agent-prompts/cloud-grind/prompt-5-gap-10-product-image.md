# Cloud-grind-prompt 5 — Gap 10 (products[].productImage end-to-end)

> **Copy-paste hela detta block som första prompt i en ny Cursor Cloud Agent-session.**
> Agenten ska kunna jobba self-contained utan att läsa andra docs.
>
> **VÄNTA — starta INTE förrän Prompt 4 (Gap 9) är mergad till `origin/jakob-be`.**
> Båda prompter rör `scripts/build_site.py` `copy_operator_uploads`-flödet + schema och vill inte krocka.

---

Du är Builder-agent som kör i en cloud-agent-VM (Ubuntu). Repo: `Jakeminator123/sajtbyggaren`. Arbets-branch: **`jakob-be`** (Jakob-lane). Du touchar bara GitHub-remoten.

## Mission

Stäng **backend-Gap 10** (`products[].productImage`). Detta är **den enda kvarvarande funktionella backend-luckan** — Gap 6/7/9 är finish/datahygien, men Gap 10 betyder att en e-handelsdemo inte visar uppladdade produktbilder. Idag:

- Frontend-types har `productImage?: AssetRef` per produkt (verifierat i `apps/viewser/components/discovery-wizard/wizard-types.ts:78`).
- UI tillåter uppladdning via dropzone i steg 4 content-step.
- **Backend har inget av:** payload-mapping från wizard-produkt-typens `productImage`-fält till Project Input, schema-fält för `products[].productImage`, `copy_operator_uploads()`-kopiering till `public/products/<productId>.<ext>`, eller renderer-stöd för produktbild i produktgrid.

Acceptanskriterium från `docs/backend-handoff.md` Gap 10: *"En e-handelssajt med 4 uppladdade produktbilder ska visa dem på produkt-grid-sidan utan extra konfiguration."*

## Branch + förutsättningar

```bash
git fetch origin --prune
git switch jakob-be
git pull --ff-only origin jakob-be
git status                                                  # ska vara clean
git log --oneline -10
```

Verifiera att Prompt 4 (Gap 9) är inne på `origin/jakob-be` innan du börjar. Om inte: stoppa, "Prompt 4 inte mergad än — väntar".

Stoppa om `git pull --ff-only` failar.

## Tillåtna paths (write-set)

- `governance/schemas/project-input.schema.json` — lägg till `productImage` som additiv property i `$defs.product` (eller motsvarande), pekande på `$ref: "#/$defs/assetRef"`. Verifiera att schemat följer den existerande "additiv direktiv-utbyggnad"-modellen (se ADR 0031 för precedent).
- `scripts/prompt_to_project_input.py` — om wizard-payload-mapping behövs så `productImage` följer med från payload till Project Input.
- `scripts/build_site.py` — utöka `iter_asset_refs` så `products[].productImage` ingår i copy-flödet. Lägg till hjälpfunktion `_copy_product_images(site_id, target, project_input) -> int` som kopierar varje produktbild till `<target>/public/products/<productId>.<ext>` (eller liknande namnstabil path). Pekar `products[].imageUrl` på den genererade URL:en om `productImage` finns och `imageUrl` saknas eller är default.
- `packages/generation/build/renderers.py` — i produktgrid-renderingen (sök `render_section_product_grid` ~rad 5005, eller motsvarande funktion), använd `product["imageUrl"]` (som nu kan komma från `productImage`-mappning) som `<img src>` för produktkortet. Fall tillbaka till befintlig text-input eller en generisk placeholder.
- `apps/viewser/components/discovery-wizard/wizard-payload.ts` — **VIKTIGT scope-leak**: om wizard-payload inte redan mappar `productImage` ned i payloaden, lägg till mappningen där. Detta är Christopher-lane-fil men följer samma scope-leak-precedent som PR #68/#71 (operatör har godkänt liknande utvidgningar tidigare). Verifiera först om fältet redan finns — om ja, ändra inget i UI.
- `tests/test_prompt_to_project_input.py` eller ny `tests/test_product_image_pipeline.py` — regression-tester.

## Off-limits paths (do not touch)

- `apps/viewser/components/discovery-wizard/steps/content-step.tsx` — UI:t har redan dropzone:n.
- `apps/viewser/components/discovery-wizard/wizard-types.ts` — types finns redan.
- `apps/viewser/app/api/upload-asset/route.ts` — Upload-API:t funkar för alla AssetRef-objekt.
- `governance/policies/**`.
- `packages/generation/orchestration/scaffolds/**`.
- Övriga `apps/viewser/components/**` förutom det smala `wizard-payload.ts`-undantaget ovan.

## Acceptanskriterier

1. `governance/schemas/project-input.schema.json` har `productImage` som additiv optional property på produkter (under `$defs.product` eller motsvarande). Pekar på `$ref: "#/$defs/assetRef"`. Schema-validering passerar fortsatt för existerande Project Inputs utan `productImage`.
2. `wizard-payload.ts` mappar wizard-produkt-typens `productImage` ned till `product.productImage` i payloaden. (Verifiera först — kan redan vara på plats.)
3. `prompt_to_project_input.py` (om den hanterar payload-till-PI-mappning för produkter) propagerar `productImage`-fältet utan att droppa.
4. `iter_asset_refs(project_input)` inkluderar varje `products[i].productImage` som en valid AssetRef.
5. Ny `_copy_product_images(...)` (eller utvidgning av `copy_operator_uploads`) kopierar varje produktbild från disk/sourceUrl till `<target>/public/products/<productId>.<ext>`. Använd samma disk-first / sourceUrl-fallback-logik som existerande copy-flöde.
6. Efter copy-steget mutar build:en `products[i].imageUrl` till `"/products/<productId>.<ext>"` om operatören laddat upp en `productImage` (även om `imageUrl` var en text-input innan). Om både `imageUrl`-text-input OCH `productImage`-upload finns: `productImage` vinner (det är mer specifikt).
7. `render_section_product_grid` (eller motsvarande) renderar `<img src={product.imageUrl}>` med rimliga `alt`, `width`, `height` och Tailwind-klasser konsekventa med övrig produktgrid-styling. Fall tillbaka till en text-only-presentation eller en branded placeholder-SVG (typ `og-fallback`-mönstret) om `imageUrl` saknas.
8. JSX-escape (`_jsx_safe_string`) tillämpas på alt-text för att inte regressera B30-skyddet.
9. Nya tester (minst 5): (a) Project Input med `productImage` validerar mot schemat, (b) `iter_asset_refs` returnerar product-bilder, (c) `_copy_product_images` kopierar fil till rätt path, (d) `imageUrl` muteras korrekt efter copy, (e) renderer skapar `<img>`-tag med rätt `src` (eller fallback om saknas).
10. `python -m pytest tests/ -q` grön. `cd apps/viewser && npx tsc --noEmit` grön (om wizard-payload.ts ändrats).

## Tekniska tips

- Produkt-iteration ligger redan i `iter_asset_refs` (`gallery`-loop) — utvidga med en till loop: `for product in project_input.get("products", []): if _is_valid_asset_ref(product.get("productImage")): refs.append(...)`.
- För kopiering: produkter har `id` (eller `slug`) — använd det som filnamn-prefix istället för asset-id, så path:en blir läsbar (`public/products/sourdough-bread.webp` istället för `public/products/asset-12345.webp`). Verifiera produkternas id/slug-fält i `wizard-types.ts:Product` shape.
- För renderer: kolla först om `render_section_product_grid` redan har en `imageUrl`-check som du bara behöver utöka. Om bildmarkup behöver byggas helt nytt: matcha stilen i `render_section_product_list` eller liknande section för konsistens.
- För wizard-payload.ts scope-leak: rör så lite som möjligt. Helst bara en rad där `productImage` förs över till payload-objektet. Tagga commiten med `[scope-leak] Approved by operator: Gap 10 requires wizard-payload.ts mapping for end-to-end functionality.`

## Final guards (alla ska vara gröna före push)

```bash
python -m ruff check .
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python scripts/sprintvakt_check.py
python -m pytest tests/ -q
( cd apps/viewser && npx tsc --noEmit && npm run lint )
```

## Stoppvillkor

Stoppa och rapportera om:

- Schema-bumpningen kräver ADR och du är osäker. Bättre fråga.
- Wizard-payload.ts scope-leak rör mer än 5 rader UI-kod. Då är scope för stort — backend ska bara mappa det som UI redan skickar.
- Produktgrid-renderern är scaffold-specifik (LSB vs ecommerce-lite vs restaurant) och förändringar krockar med Path B section-dispatcher. I så fall: fokusera på `ecommerce-lite`-grid:en först (den primära e-handelsdemo:n) och flagga övriga som "future scope".
- Tester kräver fil-fixtures du måste skapa under `tests/fixtures/` — det är OK men flagga i commit-body.

## Commit-format

Två-tre atomiska commits:

```
1. feat(schema): add productImage to project-input.schema.json $defs.product
2. feat(build): close Gap 10 — copy product images + mutate imageUrl + render in product grid
3. feat(wizard): map wizard product-image field in wizard-payload.ts [scope-leak]
   (Approved by operator: Gap 10 requires end-to-end product-image-mapping.)
```

## Push

```bash
git push origin jakob-be
```

Ingen PR. Operatörens beslut om sync-PR.

## Rapport tillbaka till operatör

```
Pushed <SHA> till origin/jakob-be.
Gap 10 stängd: products[].productImage end-to-end (schema + payload mapping +
copy_operator_uploads → public/products/ + renderer-stöd).
<N> nya tester. Alla guards gröna.

Backend-Gap-tabellen efter alla fyra Gap-promptar landade:
  Stängda: 11 (alla 11 gaps).
  Delvis: 0.
  Öppen: 0.

Sync-PR-fönster (jakob-be → main): nu är bra läge — operatör beslutar.
Innehåller: B147 host-whitelist + Gap 6/7/9/10 + doc-städ. <N> commits totalt.
```

## Parallellitet

- **Måste vänta på:** Prompt 4 (Gap 9). Båda rör `scripts/build_site.py` `_copy_operator_uploads`-flödet + schema.
- **OK parallellt med:** Prompt 2 (B147), Prompt 3 (doc-städ). Disjunkta scopes.
- **Sista i kedjan.** Efter denna är hela backend-Gap-tabellen stängd och sync-PR till `main` blir det naturliga nästa steget.
