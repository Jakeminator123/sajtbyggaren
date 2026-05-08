---
description: Disciplinen för bygg-kedjan - Project Input, Starter, Scaffold, Variant, Dossier, Policy. Init vs follow-up. Embeddings före ordmatchning.
alwaysApply: true
---

# Bygg-kedjans disciplin

Den här regeln finns för att Sajtbyggaren ska slippa det namnkaos som dödade gamla `Jakeminator123/sajtmaskin`. Den kompletterar [`governance-first.md`](governance-first.md) (JSON är sanning), [`term-discipline.md`](term-discipline.md) (inga nya namn utan naming-dictionary), [`vocabulary-discipline.md`](vocabulary-discipline.md) (en namn per begrepp, ADR krävs för nya termer) och [`project-direction.md`](project-direction.md) (varför vi alls bygger om).

## Det enda flödet

```
Init Prompt
  ↓
Project Input (Deep Brief)
  ↓
Starter
  ↓
Scaffold
  ↓
Variant
  ↓
Dossier
  ↓
Generation Package
  ↓
Build
```

Det är operator-modellen. Inga andra ord, inga mellanstationer, inga parallella axlar.

## Byggklossarna får aldrig blandas ihop

| Roll | Vad det är | Var det bor |
|------|------------|-------------|
| **Project Input** | Konkret kundprojekt: företagsfakta, ton, tjänster, kontakt. Driver vad sajten ska handla om. | `examples/<siteId>.project-input.json` |
| **Starter** | Körbar Next.js-kodbas (`npm install` + `npm run build` går igenom). Tom på företagsspecifik logik. | `data/starters/<starterId>/` |
| **Scaffold** | Sajtens grammatik: routes, sektionsslots, kvalitetsregler. **Inte** en sida, **inte** ett repo, **inte** en mall. | `packages/generation/orchestration/scaffolds/<scaffoldId>/` |
| **Variant** | Sajt-wide visuellt uttryck: tokens, typografi, motif. Bestämmer **inte** struktur eller innehåll. | `.../scaffolds/<scaffoldId>/variants/<variantId>.json` |
| **Dossier** | Återanvändbar capability/legokloss. Default-kompatibel med alla Scaffolds. | `packages/generation/orchestration/dossiers/<class>/<dossierId>/` |
| **Policy** | JSON under [`governance/policies/`](../policies/) som styr hur något får göras. | `governance/policies/` |

Mental modell:

> Project Input beskriver. Starter bygger. Scaffold formar. Variant stylar. Dossier kopplas på. Policy styr.

Förbjudna sammanblandningar: en Scaffold är inte en sida (en `Route`/`Page` är en sida; en Scaffold definierar vilka). En Starter är inte en mall. En Variant väljer inte routes. En Dossier är inte en sida och inte en komponent. Vercel templates är **Reference Templates** under `data/reference-templates/`, aldrig produktens skelett.

## Project Input vs Dossier - lås det

- **Project Input** = ett konkret kundprojekt. Exempel: `painter-palma`. Filändelse `*.project-input.json`. Bestämmer att sajten handlar om en målare i Palma.
- **Dossier** = en återanvändbar legokloss. Exempel: `pacman-game`, `stripe-checkout`. Kan kopplas på vilken sajt som helst om den är kompatibel.

Förväxla aldrig. `painter-palma` är aldrig en Dossier. `pacman-game` är aldrig ett Project Input.

## Dossier-klasser: bara soft eller hard

| Klass | Innebörd | Exempel |
|---|---|---|
| `soft` | Återanvändbar frontend/content capability. Inga secrets eller externa API:er. | `pacman-game`, `mouse-reactive-background`, `pricing-calculator`, `before-after-slider`. |
| `hard` | Kräver env, secrets, backend, auth, databas, betalning eller extern API. | `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart`. |

`hybrid` är borttaget i ADR 0012. En Dossier som behöver mock i designläge men integration i live-läge är `hard` med en `mockMode`-konfiguration.

Tidigare typer (`Site Dossier`, `Feature Dossier`, `Integration Dossier`, `Data Dossier`) är borttagna i ADR 0012. De ligger i `naming-dictionary.v1.json:globallyForbidden`.

## Init är inte follow-up

- **Init** skapar `Project DNA`. Scaffold låses (`Scaffold Lock`), Variant mjuk-låses (`Variant Lock`), språk låses.
- **Follow-up** läser DNA. Klassificerar `FollowUp Intent` enligt [`project-dna.v1.json`](../policies/project-dna.v1.json): `text-edit`, `section-add`, `section-remove`, `page-add`, `page-remove`, `restyle`, `redesign`, `clarify`.
- Endast `redesign` får byta `scaffoldId` - och då via `Project Fork` som skapar ny DNA-version med länk till föregående.
- Agenten får **aldrig** "passa på" att byta scaffold eller variant under en `text-edit` eller `section-add`. Det är exakt så sajtmaskin smög ut sig.

## Embeddings först, ordmatchning sist

Scaffold- och Dossier-val sker enligt [`scaffold-selection.v1.json`](../policies/scaffold-selection.v1.json) och [`dossier-selection.v1.json`](../policies/dossier-selection.v1.json):

1. **Compatibility Filter** (Dossier-val): default-kompatibel med alla Scaffolds; en Dossier kan ha explicit `incompatibleScaffolds`-lista om den verkligen inte funkar.
2. **Embedding top-K**: recall via curerad `embeddingText` per `Selection Profile`. Domäner enligt [`embedding-policy.v1.json`](../policies/embedding-policy.v1.json) - ett index per domän, aldrig blandat.
3. **Small LLM rerank**: semantiskt omdöme med `mustReturnReasons: true`.
4. **Policy Gate**: hårda spärrar (`notFor`, `minConfidence`, `Hard Dossier` kräver explicit signal).
5. **Selection Trace**: kandidater + scores + skäl skrivs till `data/runs/<runId>/`.

`Word Matching` får sitta i baksätet med säkerhetsbälte: svag signal, guardrail (`utan bokningsformulär`, `läkare`), debug-kommentar, fallback om embedding misslyckas. **Aldrig** primär selector. Mönstret `if prompt.includes("elektriker") return "local-service-business"` är förbjudet och fångas av `tests/evals/scaffold-selection/` (regression-testerna i scaffold-selection.v1.json).

## Sex hårda spärrar som alltid gäller

1. Inga LLM-anrop utanför registrerade `Model Role` i [`llm-models.v1.json`](../policies/llm-models.v1.json). Mock Mode markeras explicit med `briefSource=mock-no-key` eller `briefSource=mock-llm-error`.
2. `Repair Pipeline` finns på **exakt en** plats: `packages/generation/repair/`. Inga fixar implementeras utanför `Fix Registry` ([`fix-registry.v1.json`](../policies/fix-registry.v1.json)).
3. `Quality Gate` finns på **exakt en** plats: `packages/generation/quality_gate/`. **En** gate, inte F2/F3-tier (förbjudet i `globallyForbidden`).
4. `Preview Runtime` är en abstraktion. Produktkoden talar bara om `Preview Runtime`, aldrig om implementationsnamnen `VM`, `sandbox`, `webcontainer`, `preview-host`, `vercelSandbox`. Default är `StackBlitzRuntime`.
5. Ingen kod implementerar Fix, Gate, Selector eller Runtime utanför sin ägar-path i [`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json).
6. `Vercel templates` är `Reference Templates` under `data/reference-templates/` - inspirations- och struktur-corpus, aldrig produktens skelett. Codegen får ta `Section Pattern` och `Style Signature` ur dem, inte filer rakt av.

## 60-sekunders-checklista innan kod skrivs

1. Finns begreppet i [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json)? Om inte - stop, lägg till termen först (se [`term-discipline.md`](term-discipline.md)) och dokumentera ADR (se [`vocabulary-discipline.md`](vocabulary-discipline.md)).
2. Är ägar-pathen klar enligt [`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json)?
3. Är jag i rätt fas enligt [`engine-run.v1.json`](../policies/engine-run.v1.json) (`understand` / `plan` / `build`)?
4. Vid val: går jag via embedding + small LLM rerank + Policy Gate + Selection Trace, eller fuskar jag med Word Matching?
5. Vid follow-up: respekterar jag Scaffold Lock och Variant Lock i `Project DNA`?
6. Vid runtime: pratar jag om `Preview Runtime` (abstraktionen), inte den specifika implementationen?
7. Är det jag bygger ett **Project Input** (kundprojekt), en **Dossier** (capability) eller en **Scaffold** (grammatik)? Om jag är osäker - stoppa, fråga.

Stanna och fråga operatören om någon punkt är otydlig. Det är billigare än att importera sajtmaskins namnskuggor.
