# ADR 0005: Scaffold-/Dossier-modell med embedding-driven selection

- Status: accepterat
- Datum: 2026-05-07

## Kontext

Två centrala begrepp i Sajtbyggaren behövde definieras innan generation-runtime byggs: **Scaffold** (sajtens grammatik) och **Dossier** (capability-modul). I gamla `sajtmaskin` blandades dessa med `template`, `starter`, `pack`, `package`, `plugin`, `feature` om vartannat, och scaffold-val skedde delvis via ordmatchning (`if prompt.includes("restaurant") return "restaurant"`).

Reviewerns underlag (`referens/scaffolds-dossiers/konversation.txt` och `referens/scaffolds-dossiers/konversation_2.txt`, borttagna i #191, finns i git-historiken) föreslår en strikt separation, tre dossier-klasser och embedding-driven selection.

## Beslut

Sajtbyggaren använder följande modell, kodifierad i fyra policies under `governance/policies/`:

- [`scaffold-contract.v1.json`](../policies/scaffold-contract.v1.json) - filstruktur och fältkrav per Scaffold; primärregister med 14 Scaffolds.
- [`dossier-contract.v1.json`](../policies/dossier-contract.v1.json) - filstruktur per klass (soft/hybrid/hard) och fältkrav per Dossier.
- [`scaffold-selection.v1.json`](../policies/scaffold-selection.v1.json) - val-pipeline: embedding -> small LLM rerank -> Policy Gate -> Selection Trace.
- [`dossier-selection.v1.json`](../policies/dossier-selection.v1.json) - val-pipeline: Compatibility Filter -> Capability Embedding Query -> small LLM rerank -> Policy Gate.

Centrala regler:

1. **Scaffold är sajtens grammatik.** Få och välvalda (10-14), inte 50.
2. **Dossier är portabel; realiseringen är scaffold-specifik.** `contact-form` används i flera Scaffolds men har olika UI/fält/route per Scaffold.
3. **Word matching är degraderad till svag signal.** Embedding ger recall, small LLM ger semantiskt omdöme, Policy Gate stoppar dumma val.
4. **Hard Dossiers kräver explicit eller stark semantisk signal.** Inte bara semantisk närhet.
5. **Inga Dossiers injiceras automatiskt i alla Scaffolds.** Compatibility-listan i Scaffolden styr.
6. **Vercel templates är Reference Templates, inte produktens skelett.** De normaliseras till embeddings, Section Patterns och Style Signatures.

## Konsekvenser

- `packages/generation/orchestration/scaffolds/` får 14 mappar, en per Scaffold.
- `packages/generation/orchestration/dossiers/` delas i `soft/`, `hybrid/`, `hard/`.
- `packages/generation/orchestration/selection/` äger Scaffold Selector och Dossier Selector.
- `packages/generation/orchestration/embedding/` äger flera Embedding Index, ett per domän.
- `data/reference-templates/` används för Vercel-corpus, men normaliseras innan användning.
- `tests/evals/scaffold-selection/` och `tests/evals/dossier-selection/` får regression-tester med exempelprompts som tvingar systemet att skilja `local-service-business` från `saas-product` när prompten har samma branschord.

## Förhållande till tidigare beslut

- Bygger vidare på [ADR 0001](0001-policies-as-source-of-truth.md): JSON är sanningskälla.
- Bygger vidare på [ADR 0003](0003-preview-runtime-stackblitz-first.md): EN quality gate, ingen tier-uppdelning.
- Förfinas av [ADR 0006](0006-term-discipline.md): nya begrepp (`Selection Profile`, `Compatibility Filter`, `Capability Embedding Query`, `Selection Trace`, `Reference Template`, m.fl.) registreras i `naming-dictionary.v1.json` v2.
