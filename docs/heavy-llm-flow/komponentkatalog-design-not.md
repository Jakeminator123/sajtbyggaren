# Design-not: komponentmedvetet LLM-flöde (komponentkatalog + shadcn-uppslag)

> Status: design-not, plan-only — ingen kod i denna not. Första steget av
> köpunkt 6 i `docs/current-focus.md` ("börja med kort design-not innan
> bygge"). Beslutspunkterna längst ner är operatörens.

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

- Inga LLM-anrop; ren disk-scan.
- Manifestet är ett kontrakt: planen får bara referera komponenter som finns.

### 2. Governance-mappning: capability → komponent(er)

En deterministisk mappning från capability-slug till komponent(er) som
renderaren/codegen får använda för den capabilityn (t.ex. faq-section →
accordion). Bor som ny nyckel i `capability-map.v1.json` eller som egen
policy + schema — operatörsbeslut. Valideras av `governance_validate` mot
manifestet i lager 1 (en mappning till en komponent som saknas i startern är
ett gate-fel, inte en tyst fallback).

### 3. Roll-uppslag via shadcn-MCP (byggtid, aldrig runtime)

Rollerna (`section_builder`, `stylist`) får använda shadcn-MCP-servern som
uppslagsverktyg när de planerar en ändring: söka registryt, hämta exempel,
få add-kommandon. Tre hårda regler:

- MCP-uppslaget är ett byggtids-/agentverktyg. Den genererade sajten får
  aldrig ett runtime-beroende på MCP:n.
- Resultatet materialiseras alltid som deterministiska val i befintliga
  artefakter (plan/manifest/direktiv) — aldrig som fri filpatch
  (`governance/rules/09-openclaw-and-site-mutations.md` gäller).
- Nya komponenter vendoreras in i startern via en granskad PR (CLI-add +
  manifest-regenerering), inte on-the-fly under ett kundbygge.

## Avgränsningar

- Runtime-libs (three.js m.fl.) är en ANNAN axel: capability → lib-mappning
  med egen dossier/komponent per capability. Tas inte i denna slice — kräver
  egen design-not när komponentkatalogen är på plats.
- Inga nya canonical-termer utan ADR. "komponentkatalog"/"komponent-manifest"
  hålls som prosa tills ADR:n landar.
- Roll-dispatchen (köpunkt 2, F1 slice 3) är en förutsättning för lager 3 —
  rollvalet måste styra beteende innan rollen kan ges verktyg.

## Beslutspunkter (operatören)

1. Var manifestet bor: under `data/starters/<id>/` (nära källan) eller under
   `governance/` (nära kontrakten)?
2. Mappningen i lager 2: ny nyckel i `capability-map.v1.json` (minst ny yta)
   eller egen policy-fil + schema (renare separation)?
3. ADR-omfång: en ADR för hela kedjan (manifest + mappning + roll-uppslag)
   eller en per lager?
4. Första capability att pilota (förslag: faq-section → accordion, minsta
   yta med tydlig synlig effekt).
