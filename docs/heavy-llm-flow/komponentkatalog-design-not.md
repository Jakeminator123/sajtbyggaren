# Design-not: komponentmedvetet LLM-flöde (komponentkatalog + shadcn-uppslag)

> Status: design-not, plan-only — ingen kod i denna not. Första steget av
> köpunkt 6 i `docs/current-focus.md` ("börja med kort design-not innan
> bygge"). Alla fyra beslutspunkter är avgjorda (operatörens delegation
> 2026-06-10) — noten är därmed redo som underlag för lager 1-slicen
> (manifest + ADR) så snart roll-dispatch-slicen landat.

## Problemet

Starters vendorerar redan shadcn-komponenter (`components.json` per starter,
CLI i devDependencies), och det finns en shadcn-MCP-server som låter en agent
slå upp komponenter, exempel och install-kommandon. Men kedjan brief → plan →
codegen är komponent-blind: den kan inte välja eller referera komponenter,
så LLM-flödet kan aldrig säga "den här sektionen ska använda accordion-
komponenten som redan finns vendorerad i startern".

## Tre lager (i ordning, varje lager är en egen slice)

### 1. Komponent-manifest per starter (deterministiskt)

Ett genererat manifest per starter som listar vendorerade komponenter
(källa: `components.json` + `components/ui/`-mappen på disk). Skrivs av ett
skript (samma mönster som rules-speglarna: källa på disk, genererad artefakt,
synk-check i CI). Exponeras för planeringen via starter-registryt så
`produce_site_plan` kan läsa vilka komponenter målstartern faktiskt har.

Beslutad placering (beslutspunkt 1, avgjord på operatörens delegation
2026-06-10): manifestet bor under `data/starters/<id>/component-manifest.json`
— hos startern det beskriver, inte under `governance/`. Motivering: det är en
genererad inventering härledd ur starterns egna filer (samma katalog som
källan), medan `governance/` bär kontrakt och policys som människor beslutar.
Synk-checken i CI (manifest matchar disk) ger samma drift-skydd som
rules-speglarna får, utan att blanda genererat innehåll in i governance-trädet.

- Inga LLM-anrop; ren disk-scan.
- Manifestet är ett kontrakt: planen får bara referera komponenter som finns.

### 2. Governance-mappning: capability → komponent(er)

En deterministisk mappning från capability-slug till komponent(er) som
renderaren/codegen får använda för den capabilityn (t.ex. faq-section →
accordion). **Beslutad placering (beslutspunkt 2, avgjord på operatörens
delegation 2026-06-10): ny valfri nyckel per capability i
`capability-map.v1.json`**, inte en egen policy-fil. Motivering:
capability-kartan äger redan capability → tillgångar-axeln (dossiers), så
komponenter är samma slags mappning; planeringen läser redan den filen, så
ingen ny lässökväg behövs; och en policy-fil till vore mer governance-yta
utan motsvarande separationsvinst. Konsekvens: additiv schema-bump för
capability-map (valfritt fält, befintliga poster opåverkade). Valideras av
`governance_validate` mot manifestet i lager 1 (en mappning till en komponent
som saknas i startern är ett gate-fel, inte en tyst fallback).

### 3. Roll-uppslag via shadcn-MCP (byggtid, aldrig runtime)

Rollerna (`section_builder`, `stylist`) får använda shadcn-MCP-servern som
uppslagsverktyg när de planerar en ändring: söka registryt, hämta exempel,
få add-kommandon.

> Konceptbevis finns (operatörens lokala labb, gitignorat:
> `övrigt/shadcn-mcp-lab/`): en GPT-agent med shadcn-MCP:ns verktyg
> (`search_items_in_registries` → `view_items_in_registries` →
> `get_item_examples_from_registries`) hämtar RIKTIG komponentkod ur
> registryt och levererar ett strukturerat artefakt-objekt (pydantic-typad
> TSX + metadata om använda registry-items) — 5 lyckade körningar
> 2026-06-10 (produktkort, countdown, diagram m.m.). Labbet bevisar
> verktygs-flödet; produktifieringen MÅSTE dock gå genom reglerna nedan
> (vendorering via granskad PR + capability-mappning), aldrig labbet
> mönster "agent skriver TSX direkt" mot en kundsajt.

Fyra hårda regler:

- MCP-uppslaget är ett byggtids-/agentverktyg. Den genererade sajten får
  aldrig ett runtime-beroende på MCP:n.
- Resultatet materialiseras alltid som deterministiska val i befintliga
  artefakter (plan/manifest/direktiv) — aldrig som fri filpatch
  (`governance/rules/09-openclaw-and-site-mutations.md` gäller).
- Nya komponenter vendoreras in i startern via en granskad PR (CLI-add +
  manifest-regenerering), inte on-the-fly under ett kundbygge.
- Separata MCP-instanser (operatörskrav 2026-06-10): motorn spawnar sin
  EGEN MCP-serverprocess (stdio, t.ex. `npx shadcn@latest mcp`) med egen
  konfiguration när rollen behöver uppslaget. `.cursor/mcp.json` är
  IDE-lokal (Cursor-agenternas verktyg) och får ALDRIG läsas av motorn —
  verifierat 2026-06-10: ingen kod i `packages/`/`scripts/` refererar den
  i dag, och så ska det förbli.

## Avgränsningar

- Runtime-libs (three.js m.fl.) är en ANNAN axel: capability → lib-mappning
  med egen dossier/komponent per capability. Tas inte i denna slice — kräver
  egen design-not när komponentkatalogen är på plats.
- Inga nya canonical-termer utan ADR. "komponentkatalog"/"komponent-manifest"
  hålls som prosa tills ADR:n landar.
- Roll-dispatchen (köpunkt 2, F1 slice 3) är en förutsättning för lager 3 —
  rollvalet måste styra beteende innan rollen kan ges verktyg.

## Beslutspunkter — alla avgjorda (operatörens delegation 2026-06-10)

1. Beslutad: manifestet bor under `data/starters/<id>/component-manifest.json`
   (nära källan det genereras ur; `governance/` hålls till kontrakt/policys —
   se motivering under lager 1).
2. Beslutad: mappningen i lager 2 = ny valfri nyckel i
   `capability-map.v1.json` (se motivering under lager 2).
3. Beslutad: EN ADR för hela kedjan (manifest + mappning + roll-uppslag).
   Motivering: de tre lagren är en sammanhängande design med ett gemensamt
   varför — tre separata ADR:er skulle splittra motiveringen och tvinga
   korsreferenser. Varje lager-slice refererar samma ADR; ADR:n skrivs i
   lager 1-slicen och registrerar samtidigt termerna (komponentkatalog,
   komponent-manifest) i naming-dictionaryn.
4. Beslutad: pilot-capability = faq-section → accordion. Motivering: minsta
   yta med tydligast synlig effekt — faq-section är redan en stödd
   section_add-capability med faq-accordion-dossiern monterad, så piloten
   testar bara den NYA länken (capability → komponent → render), inte
   sektion-mekaniken i sig.
