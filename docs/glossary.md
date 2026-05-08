# Glossary

Alla begrepp som finns i Sajtbyggarens governance, förklarade i en mänsklig ton. Den maskinläsbara sanningskällan är [`naming-dictionary.v1.json`](../governance/policies/naming-dictionary.v1.json) - här återges samma termer i löpande text och i den ordning de dyker upp i flödet.

Termer i `code` är de kanoniska namnen. Allt annat (synonymer, alias) är förbjudet i kod om det inte uttryckligen står i `aliasesAllowed` på respektive term.

## Stora bilden - en körning

| Term | Vad det är |
|------|------------|
| `Engine Run` | En hel körning från prompt till antingen `Promoted Site` eller `Repair Candidate`. Identifieras med en `runId` och har en mapp under `data/runs/<runId>/` med alla artefakter och en append-only `trace.ndjson`. |
| `Engine Event` | En händelse i en `Engine Run`: fas, status (started/done/failed/degraded), meddelande, ev. payload-sökväg. Skrivs till `trace.ndjson`. |
| `Site Brief` | Output från fas 1 Understand. Strukturerat objekt om sajten: språk, businessType, sidor, ton, capabilities. Det är **ej** löst formulerad text. |
| `Site Plan` | Output från fas 2 Plan. Vald `Scaffold`, `Variant`, `Route Plan`, valda `Dossiers`, och `BuildSpec`. |
| `Generation Package` | Den **enda** nyttolasten som skickas till codegen-LLM. Innehåller `Site Brief` + `Site Plan` + policy-versioner. Inget LLM-anrop får läggas till information utöver detta. |
| `Generated Files` | Filerna codegen-LLM producerade, innan `Repair Pipeline`. Sparas i `data/runs/<runId>/generated-files/`. |
| `Repair Result` | Resultat från `Repair Pipeline`: applicerade fixes, ev. LLM-fix, kvarvarande fel. |
| `Quality Result` | Resultat från `Quality Gate`: per-check pass/fail, summary. |
| `Build Result` | Samlad rapport för fas 3: status, körningstid, modellanvändning. |
| `Promoted Site` | En version som klarat `Quality Gate` och blivit accepterad. |
| `Repair Candidate` | En version som inte klarat gate men där `Repair Pipeline` har producerat ett förslag som väntar på accept eller re-evaluering. |

## Scaffolds och Dossiers

| Term | Vad det är |
|------|------------|
| `Scaffold` | Sajtens **grammatik**. Inte en mall. Innehåller route-struktur, sektionsgrammatik, kvalitetsregler och tillåtna `Dossiers`. 14 primära scaffolds finns registrerade i [`scaffold-contract.v1.json`](../governance/policies/scaffold-contract.v1.json). |
| `Scaffold Variant` | Visuell/personlig variant inom en `Scaffold`: typografi, färgschema, motif. |
| `Scaffold Registry` | Centralt index över giltiga `Scaffold`-id:n. Sanningskälla i `scaffold-contract.v1.json:primaryScaffoldRegistry`. |
| `Selection Profile` | Per-`Scaffold`-fil med embedding-text, semanticSignals, negativeSignals, llmClassificationHints. Det är **denna** som styr `Scaffold Selector`, inte ordmatchning. |
| `Quality Contract` | Per-`Scaffold`-fil med scorecard-vikter, must-pass och avoid. Härleder från `page-quality-traits` men kan justera per `Scaffold`. |
| `Project Input` | Strukturerad tolkning av init-promptens kund-/site-data. Driver vad sajten ska handla om (företagsfakta, ton, tjänster, kontakt). Filer: `examples/<siteId>.project-input.json`. Alias: `Deep Brief`. **Är inte en Dossier.** |
| `Dossier` | Återanvändbar capability/legokloss som kan kopplas på en `Route`/section/slot. Klass: `soft` eller `hard`. Default-kompatibel med alla `Scaffolds`. |
| `Dossier Class` | En av `soft` (frontend/content utan secrets) eller `hard` (kräver env/backend/auth/betalning/extern API). ADR 0012 tog bort `hybrid` - en Dossier som behöver mock i designläge är `hard` med `mockMode`-konfiguration. |
| `Soft Dossier` | Återanvändbar frontend/content capability. Exempel: `pacman-game`, `mouse-reactive-background`, `pricing-calculator`. |
| `Hard Dossier` | Kräver env, secrets, backend, auth, databas, betalning eller extern API. Exempel: `stripe-checkout`, `supabase-auth`, `clerk-auth`, `shopify-cart`. |
| `Compatible Dossier` | Operator- eller selector-rekommenderad koppling. Default-allow: en Dossier är kompatibel med alla Scaffolds tills den deklarerar motsatsen. |

## Selection (hur Scaffold och Dossiers väljs)

| Term | Vad det är |
|------|------------|
| `Embedding Index` | Sökbar embedding-baserad index. Ett per domän: scaffolds, dossiers, reference-templates, section-patterns, style-signatures. Inte ett stort gemensamt index. |
| `Capability Embedding Query` | Embedding-fråga som söker top-K `Dossier`-kandidater för aktuell `Site Brief`. |
| `Compatibility Filter` | Hård filtrering av `Dossier`-kandidater mot `Selected Scaffold`. Kandidater som inte är `Compatible Dossier` faller bort innan rerank. |
| `Word Matching` | Direkt strängmatchning mot promptens innehåll. Tillåtet **endast** som svag signal eller guardrail; aldrig som primär selector. Förbjudet att direkt välja `Scaffold` på ord. |
| `Policy Gate` | Filtersteg som avvisar val som bryter mot policies, även om embedding och LLM rekommenderar dem. |
| `Selection Trace` | Strukturerad logg över `Scaffold`-/`Dossier`-val: kandidater, scores, LLM-reasons, accept/reject. Sparas under `data/runs/<runId>/`. |
| `Reference Template` | Externt material (t.ex. Vercel templates) som används som inspirations- och struktur-corpus, inte som produktens skelett. |
| `Section Pattern` | Återkommande sektionsstruktur extraherad från `Reference Templates` (hero-with-product-shot, logo-cloud, pricing-table). |
| `Style Signature` | Visuellt fingeravtryck (typografi, färg, motif, depth) extraherat från `Reference Template` eller `Scaffold Variant`. |

## Build, Repair och Quality Gate

| Term | Vad det är |
|------|------------|
| `Repair Pipeline` | Centraliserad reparationskedja: normalize → mechanical fixes → typecheck/syntax → optional LLM fix → re-check → final. Får bo på exakt **EN** plats: `packages/generation/repair/`. Det löser den utspridda fix-rörran från sajtmaskin. |
| `Quality Gate` | Mätbar acceptansgräns. **EN** gate på `packages/generation/quality-gate/`. Inte en F2/F3-tier-uppdelning. |
| `Code Contract` | Per-`Dossier`-fil (`code-contract.json`) som listar must/avoid för den kod LLM:en får producera när `Dossier`n aktiveras. |
| `Env Contract` | Per-`Dossier`-fil (`env-contract.json`) för hybrid/hard-Dossiers. Listar requires + designModeBehavior + integrationModeBehavior. |

## Plan, Routes, Specs

| Term | Vad det är |
|------|------------|
| `Route Plan` | Lista över sidor/rutter som ska finnas i den genererade sajten med ordning och syfte. |
| `Contract Plan` | Tekniska krav: auth, betalning, databas, env-variabler, integrationer som sajten behöver. |
| `BuildSpec` | Körnings- och kvalitetspolicy: changeScope, qualityTarget, contextPolicy, verificationPolicy, tokenBudgets. |
| `Resolved Policy` | Output från fas 1 policy_resolution: `page-quality-traits` + naming + repo-boundaries + generation-constraints sammanvägda för aktuell `Site Brief`. |

## Preview Runtime

| Term | Vad det är |
|------|------------|
| `Preview Runtime` | Abstraktion för var en genererad sajt körs. Implementationer: `LocalRuntime`, `StackBlitzRuntime`, `FlyRuntime`. Produktkoden talar bara om `Preview Runtime`. |
| `LocalRuntime` | Implementation som kör genererade filer på utvecklarens egen Node. Implementationsordning: byggs först (lättast att felsöka). |
| `StackBlitzRuntime` | Implementation som kör genererade Next.js-sajter via `WebContainer` i browserfliken. Default i policy. Byggs efter `LocalRuntime`. |
| `FlyRuntime` | Implementation som kör genererade sajter på Fly.io VM. Används bara när `StackBlitz` inte räcker (hard-Dossiers, Stripe, DB). |
| `WebContainer` | Browser-baserad Node.js-runtime (StackBlitz-tekniken). Underliggande för `StackBlitzRuntime`. Inte en produktterm utanför det paketet. |
| `Preview Session` | Aktiv session från en `Preview Runtime`: id, url, kind, createdAt. Returneras av `PreviewRuntime.start()`. |
| `Preview File` | En fil i den filuppsättning som monteras i `Preview Runtime`: path + content. |

## LLM-modeller och roller

| Term | Vad det är |
|------|------------|
| `Model Role` | En plats där en LLM får anropas. Mappas mot konkret modell i [`llm-models.v1.json`](../governance/policies/llm-models.v1.json). Ingen kod får anropa LLM utan att en registrerad `Model Role` driver anropet. |
| `briefModel` | Fas 1 - extrahera `Site Brief` från raw prompt. |
| `planningModel` | Fas 2 - reasoning där det behövs (route-hints, dossier-rationale). |
| `rerankModel` | `Scaffold Selector` och `Dossier Selector` rerank av top-K kandidater. |
| `codegenModel` | Fas 3 - generera filerna utifrån `Generation Package`. |
| `repairModel` | `Repair Pipeline` - LLM-fix när mekaniska fixes inte räcker. |
| `verifierModel` | Read-only granskning av `Generated Files` som producerar findings till `Quality Gate`. |
| `embeddingModel` | `Embedding Index` för Scaffold-/Dossier-/Section Pattern-/Style Signature-index. |

I [`llm-models.v1.json`](../governance/policies/llm-models.v1.json) pekar alla generation-roller just nu på `gpt-5.4`, embedding på `text-embedding-3-small`. Det är medvetet en linje av modeller; vi optimerar per roll först när användning kräver det.

## Governance och styrning

| Term | Vad det är |
|------|------------|
| `Policy` | JSON-fil under `governance/policies/`. Sanningskälla för en domän (kvalitet, namn, gränser, flöde, runtime, scaffold-/dossier-kontrakt, m.m.). |
| `Schema` | JSON Schema-fil under `governance/schemas/` som validerar en motsvarande `Policy`. Ett schema per policy. |
| `Rule` | Mänsklig instruktion under `governance/rules/` som speglas till `.cursor/rules/`. Beskriver beteende, inte data. |
| `Backoffice` | `backend.py` Streamlit-app för att redigera governance, scaffolds, dossiers, evals, telemetri. **INTE** i användarens runtime. |

## Globalt förbjudna termer

Det finns en lista över termer som **aldrig** får återinföras i produkt-texter, kod eller policy-värden (utöver i fält som uttryckligen listar förbjudet, t.ex. `aliasesForbidden`, `forbiddenTerms`).

Sanningskällan ligger i [`naming-dictionary.v1.json`](../governance/policies/naming-dictionary.v1.json) under fältet `globallyForbidden`. Den listan upprätthålls automatiskt av [`tests/test_no_legacy_terms.py`](../tests/test_no_legacy_terms.py) som blockerar varje commit som återinför någon av termerna.

Termerna som står där var källan till namnskuggor och förvirring i sajtmaskin (tier-uppdelad gate, dubbla preview-namn, gamla AI-gateway-koncept). Att repetera dem i klartext här skulle bryta mot själva regeln, så vi gör inte det.

## Mappstruktur

Var varje term hör hemma styrs av [`repo-boundaries.v1.json`](../governance/policies/repo-boundaries.v1.json). Brott mot ägarskap är blockerande review.
