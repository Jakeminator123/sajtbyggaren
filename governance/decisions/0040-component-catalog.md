# ADR 0040 — Component Catalog (komponent-manifest + capability→komponent-mappning)

**Status:** Accepted
**Datum:** 2026-06-10
**Beroenden:** ADR 0006 (term-discipline), ADR 0013 (capability-map.v1 låst),
ADR 0017 (marketing-base som primär active-runtime-starter).
Underlag: [`docs/heavy-llm-flow/komponentkatalog-design-not.md`](../../docs/heavy-llm-flow/komponentkatalog-design-not.md).
Berörda filer:
[`governance/policies/capability-map.v1.json`](../policies/capability-map.v1.json),
[`governance/schemas/component-manifest.schema.json`](../schemas/component-manifest.schema.json),
[`scripts/generate_component_manifests.py`](../../scripts/generate_component_manifests.py),
[`scripts/governance_validate.py`](../../scripts/governance_validate.py).

## Kontext

Starters vendorerar redan shadcn-komponenter (`components.json` per starter, CLI
i devDependencies), och det finns en shadcn-MCP-server som låter en agent slå upp
komponenter, exempel och install-kommandon. Men kedjan brief → plan → codegen är
komponent-blind: den kan inte välja eller referera komponenter, så LLM-flödet kan
aldrig säga "den här sektionen ska använda accordion-komponenten som redan finns
vendorerad i startern".

Designnoten beskriver tre lager. Den här ADR:n täcker hela kedjan men levererar
bara lager 1 och 2 i denna slice; lager 3 markeras som en senare slice. En enda
ADR (i stället för tre) håller motiveringen samlad — de tre lagren är en
sammanhängande design med ett gemensamt varför, och varje lager-slice refererar
samma ADR.

## Beslut

### 1. Component Manifest per starter (lager 1, deterministiskt)

Ett genererat manifest per starter listar de vendorerade shadcn-komponenterna.
Källa: `components.json` + `components/ui/` på disk. Skrivs av
`scripts/generate_component_manifests.py` (inga LLM-anrop, ren disk-scan) och bor
hos startern det beskriver: `data/starters/<starterId>/component-manifest.json`.

Motivering för placeringen (beslutspunkt 1): det är en genererad inventering
härledd ur starterns egna filer (samma katalog som källan), medan `governance/`
bär kontrakt och policys som människor beslutar. En synk-check (`--check` +
`tests/test_component_manifests.py`) ger samma drift-skydd som rules-speglarna
får, utan att blanda genererat innehåll in i governance-trädet.

Manifestet speglar **shadcn-`ui`-konventionen** (`aliases.ui` =
`@/components/ui`): scannen läser bara filer direkt under `components/ui/`.

**Tomma manifest är avsiktliga, inte buggar.** `commerce-base` har komponenter
direkt under `components/` men ingen `components/ui/`-mapp, och `saas-base` saknar
både `components.json` och komponentmappar (den är registrerad placeholder). Båda
får därför ett ärligt tomt `components: []` (och `componentsJsonPresent: false`
för `saas-base`). Det är en tom inventering, inte ett saknat manifest — synk-
checken kräver att alla enabled starters HAR ett manifest, men inte att det är
icke-tomt.

### 2. capability→komponent som valfri nyckel i capability-map (lager 2)

Mappningen capability-slug → komponent(er) är en ny **valfri** nyckel
`components` per capability i `capability-map.v1.json` (additiv schema-bump,
befintliga poster opåverkade; policy v2 → v3, schema additivt).

Motivering (beslutspunkt 2): capability-kartan äger redan capability →
tillgångar-axeln (dossiers), så komponenter är samma slags mappning; planeringen
läser redan filen; en policy-fil till vore mer governance-yta utan motsvarande
separationsvinst.

**Korskontroll (gate, inte tyst fallback):**
`scripts/governance_validate.py` korskontrollerar varje `components`-namn mot
unionen av de enabled starternas manifest. Ett namn som saknas i **alla** enabled
starters manifest är ett gate-fel. Detta är medvetet strängare än `dossiers`-
axelns "tom lista = erkänt glapp" — komponenter får inte vara ett tyst glapp.

**Scope för korskontrollen:** capability-kartan är global (ingen starter-länk), så
regeln är "komponenten måste vara vendorerad i minst en enabled starter".
Per-starter-upplösning (vilken starter som bär komponenten för ett visst bygge)
är ett lager-3-problem och tas inte här.

### 3. Roll-uppslag via shadcn-MCP (lager 3) — senare slice

Rollerna (`section_builder`, `stylist`) får använda shadcn-MCP som
uppslagsverktyg vid byggtid. Tre hårda regler kvarstår från designnoten: MCP är
ett byggtids-/agentverktyg (aldrig runtime-beroende i den genererade sajten);
resultatet materialiseras alltid som deterministiska val i befintliga artefakter;
nya komponenter vendoreras in via granskad PR (CLI-add + manifest-regenerering).
Detta lager kräver att roll-dispatchen är på plats och **byggs i en egen slice**.

### 4. Pilot: faq-section → accordion

Pilot-capability (beslutspunkt 4) = `faq-section → accordion`: minsta yta med
tydligast effekt. `faq-section` är redan en stödd section_add-capability med
`faq-accordion`-dossiern monterad, så piloten testar bara den nya länken
(capability → komponent), inte sektion-mekaniken.

Eftersom korskontrollen är en gate (punkt 2) måste komponenten faktiskt finnas i
ett manifest. Därför vendoreras en minimal `accordion.tsx` i `marketing-base`
(`components/ui/accordion.tsx`), byggd på native `<details>/<summary>` + den redan
vendorerade `cn`-hjälparen. Den tillför **inget nytt beroende** (samma no-JS-
mönster som `faq-accordion`-dossiern) — ett legitimt källfilstillägg, inte ett nytt
lib. Render/codegen-konsumtion av mappningen är lager 3.

### 5. Termer registreras (sanktionerad väg)

Per ADR 0006 registreras de nya begreppen canonical i
`naming-dictionary.v1.json` (v30) med denna ADR som motivering:

- **Component Catalog** (`componentCatalog`) — det komponentmedvetna lagret.
  Svensk prosa-alias: komponentkatalog.
- **Component Manifest** (`componentManifest`) — den genererade per-starter-
  inventeringen. Svensk prosa-alias: komponent-manifest.

## Vad ADR 0040 INTE beslutar

- Ingen render-/codegen-konsumtion av `components`-mappningen (egen slice).
- Inget roll-uppslag/shadcn-MCP-verktyg (lager 3, egen slice).
- Inga nya runtime-libs; `accordion.tsx` tillför inget beroende.
- Ingen capability → lib-mappning (runtime-libs är en annan axel med egen
  design-not).
- Ingen ändring av befintliga capability-poster eller dossier-axeln.

## Verifiering

- `python scripts/generate_component_manifests.py --check` — alla manifest i synk.
- `python scripts/governance_validate.py` — 20 policies + komponent-korskontroll
  grön (`accordion` finns i `marketing-base`s manifest).
- `python scripts/rules_sync.py --check` — speglar i synk (rules orörda).
- `python scripts/check_term_coverage.py --strict` — grön (Component Catalog /
  Component Manifest registrerade).
- `python -m pytest -m core -q` + `python -m pytest tests/test_component_manifests.py -q`
  — gröna.
- ADR 0040 är unikt numrerad (0039 = Golden Path).
