---
description: Disciplinen för bygg-kedjan - Starter, Scaffold, Variant, Dossier, Policy. Init vs follow-up. Embeddings före ordmatchning.
alwaysApply: true
---

# Bygg-kedjans disciplin

Den här regeln finns för att Sajtbyggaren ska slippa det namnkaos som dödade gamla `Jakeminator123/sajtmaskin`. Den kompletterar [`governance-first.md`](governance-first.md) (JSON är sanning), [`term-discipline.md`](term-discipline.md) (inga nya namn utan naming-dictionary) och [`project-direction.md`](project-direction.md) (varför vi alls bygger om).

## De fem byggklossarna får aldrig blandas ihop

| Roll | Vad det är | Var det bor |
|------|------------|-------------|
| **Starter** | Körbar Next.js-kodbas (`npm install` + `npm run build` går igenom). Tom på företagsspecifik logik. | `data/starters/<starterId>/` |
| **Scaffold** | Sajtens grammatik: routes, sektionsslots, kvalitetsregler, kompatibla dossiers. **Inte** en mall, **inte** ett repo. | `packages/generation/orchestration/scaffolds/<scaffoldId>/` |
| **Scaffold Variant** | Visuell/personlig riktning: tokens, typografi, motif. Bestämmer **inte** struktur eller innehåll. | `.../scaffolds/<scaffoldId>/variants/<variantId>.json` |
| **Dossier** | Återanvändbar capability- eller innehållsmodul (klass + typ nedan). | `packages/generation/orchestration/dossiers/<class>/<dossierId>/` |
| **Policy** | JSON under [`governance/policies/`](../policies/) som styr hur något får göras. | `governance/policies/` |

Mental modell:

> Starter bygger. Scaffold formar. Variant stylar. Dossier fyller. Policy styr.

Förbjudna sammanblandningar: en Scaffold är inte ett repo, en Starter är inte en mall, en Variant väljer inte routes, en Dossier är inte en komponent. Vercel templates är **Reference Templates** under `data/reference-templates/`, aldrig produktens skelett.

## Dossier har två oberoende axlar

**Klass** (vad som krävs tekniskt, från [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json)):

- `Soft Dossier` - påverkar bara content/layout
- `Hybrid Dossier` - mock i designläge, backend/env i integrationsläge
- `Hard Dossier` - kräver env, backend, databas, auth, betalning eller extern API

**Typ** (vad den levererar, registrerad i naming-dictionary v6):

- `Site Dossier` - unikt kund-/sajtinnehåll (företagsfakta, brandfärg, team)
- `Feature Dossier` - återanvändbar funktion (pacman-spel, ROI-räknare, before/after-slider)
- `Integration Dossier` - extern koppling (Stripe, Supabase, Shopify, Clerk)
- `Data Dossier` - återanvändbar kunskap (kommunlistor, branschsvarslistor)

Exempel:

| Sak | Klass | Typ |
|-----|-------|-----|
| Pacman-spel | `soft` | `feature` |
| Stripe Checkout | `hard` | `integration` |
| Företagsfakta för en målare | `soft` | `site` |
| Företagets faktiska brandfärg | `soft` | `site` (varianten konsumerar) |
| Kontaktformulär | `hybrid` | `feature` |
| Branschspecifik FAQ | `soft` | `data` |

Variant ändrar **hur** något känns. Dossier lägger till **vad** något är, vet eller kan göra. Det är gränsen.

## Init är inte follow-up

- **Init** skapar `Project DNA`. Scaffold låses (`Scaffold Lock`), Variant mjuk-låses (`Variant Lock`), språk låses.
- **Follow-up** läser DNA. Klassificerar `FollowUp Intent` enligt [`project-dna.v1.json`](../policies/project-dna.v1.json): `text-edit`, `section-add`, `section-remove`, `page-add`, `page-remove`, `restyle`, `redesign`, `clarify`.
- Endast `redesign` får byta `scaffoldId` - och då via `Project Fork` som skapar ny DNA-version med länk till föregående.
- Agenten får **aldrig** "passa på" att byta scaffold eller variant under en `text-edit` eller `section-add`. Det är exakt så sajtmaskin smög ut sig.

## Embeddings först, ordmatchning sist

Scaffold- och Dossier-val sker enligt [`scaffold-selection.v1.json`](../policies/scaffold-selection.v1.json) och [`dossier-selection.v1.json`](../policies/dossier-selection.v1.json):

1. **Compatibility Filter** (Dossier-val): bara dossiers som scaffolden listar i `compatible-dossiers.json` är kandidater.
2. **Embedding top-K**: recall via curerad `embeddingText` per `Selection Profile`. Domäner enligt [`embedding-policy.v1.json`](../policies/embedding-policy.v1.json) - ett index per domän, aldrig blandat.
3. **Small LLM rerank**: semantiskt omdöme med `mustReturnReasons: true`.
4. **Policy Gate**: hårda spärrar (`notFor`, `minConfidence`, `Hard Dossier` kräver explicit signal).
5. **Selection Trace**: kandidater + scores + skäl skrivs till `data/runs/<runId>/`.

`Word Matching` får sitta i baksätet med säkerhetsbälte: svag signal, guardrail (`utan bokningsformulär`, `läkare`), debug-kommentar, fallback om embedding misslyckas. **Aldrig** primär selector. Mönstret `if prompt.includes("elektriker") return "local-service-business"` är förbjudet och fångas av `tests/evals/scaffold-selection/` (regression-testerna i scaffold-selection.v1.json).

## Sex hårda spärrar som alltid gäller

1. Inga LLM-anrop utanför registrerade `Model Role` i [`llm-models.v1.json`](../policies/llm-models.v1.json). Mock Mode markeras explicit med `briefSource=mock-no-key` eller `briefSource=mock-llm-error`.
2. `Repair Pipeline` finns på **exakt en** plats: `packages/generation/repair/`. Inga fixar implementeras utanför `Fix Registry` ([`fix-registry.v1.json`](../policies/fix-registry.v1.json)).
3. `Quality Gate` finns på **exakt en** plats: `packages/generation/quality-gate/`. **En** gate, inte F2/F3-tier (förbjudet i `globallyForbidden`).
4. `Preview Runtime` är en abstraktion. Produktkoden talar bara om `Preview Runtime`, aldrig om implementationsnamnen `VM`, `sandbox`, `webcontainer`, `preview-host`, `vercelSandbox`. Default är `StackBlitzRuntime`.
5. Ingen kod implementerar Fix, Gate, Selector eller Runtime utanför sin ägar-path i [`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json).
6. `Vercel templates` är `Reference Templates` under `data/reference-templates/` - inspirations- och struktur-corpus, aldrig produktens skelett. Codegen får ta `Section Pattern` och `Style Signature` ur dem, inte filer rakt av.

## 60-sekunders-checklista innan kod skrivs

1. Finns begreppet i [`naming-dictionary.v1.json`](../policies/naming-dictionary.v1.json)? Om inte - stop, lägg till termen först (se [`term-discipline.md`](term-discipline.md)).
2. Är ägar-pathen klar enligt [`repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json)?
3. Är jag i rätt fas enligt [`engine-run.v1.json`](../policies/engine-run.v1.json) (`understand` / `plan` / `build`)?
4. Vid val: går jag via embedding + small LLM rerank + Policy Gate + Selection Trace, eller fuskar jag med Word Matching?
5. Vid follow-up: respekterar jag Scaffold Lock och Variant Lock i `Project DNA`?
6. Vid runtime: pratar jag om `Preview Runtime` (abstraktionen), inte den specifika implementationen?

Stanna och fråga operatören om någon punkt är otydlig. Det är billigare än att importera sajtmaskins namnskuggor.
