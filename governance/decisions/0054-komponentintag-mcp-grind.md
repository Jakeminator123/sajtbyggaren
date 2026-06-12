# ADR 0054 — Komponentintag via kurerad shadcn-MCP-grind

**Status:** Accepted
**Datum:** 2026-06-12
**Beroenden:** ADR 0040 (Component Catalog — capability→komponent-mappning +
per-Starter component-manifest, lager 3 markerades som senare slice), ADR 0006
(term-disciplin), ADR 0017 (marketing-base som primär active-runtime-starter).
Berörda filer:
[`scripts/component_intake.py`](../../scripts/component_intake.py),
[`scripts/candidate_generation_metadata.py`](../../scripts/candidate_generation_metadata.py),
[`requirements.txt`](../../requirements.txt),
[`.gitignore`](../../.gitignore) (oförändrad — kandidater är committbara),
[`governance/policies/repo-boundaries.v1.json`](../policies/repo-boundaries.v1.json).

## Kontext

ADR 0040 byggde Component Catalog lager 1 (per-Starter `component-manifest.json`)
och lager 2 (capability→komponent i `capability-map.v1.json`) men lämnade lager 3
— roll-uppslag via shadcn-MCP + intagsvägen — som en senare slice. Designnoten
beskriver tre hårda regler för det lagret: MCP är ett byggtids-/agentverktyg
(aldrig runtime-beroende i den genererade sajten), resultatet materialiseras
alltid som deterministiska val i befintliga artefakter, och nya komponenter
vendoreras in via granskad PR.

Det fanns ett standalone-lab (`övrigt/shadcn-mcp-lab/shadcn_lab_agent.py`,
gitignorad referens) som visade mönstret: spawna en egen `npx shadcn@latest mcp`
över stdio (OpenAI Agents SDK), kör verktygsflödet `search_items_in_registries →
view_items_in_registries → get_item_examples_from_registries` och leverera en
komponent. Den här ADR:n produktifierar labbet som en operatörs-grind.

## Beslut

### 1. Intake-CLI:t `scripts/component_intake.py` (operatörsverktyg)

En CLI som spawnar sitt **eget** `npx shadcn@latest mcp` stdio-MCP via OpenAI
Agents SDK-mönstret (`agents.mcp.MCPServerStdio`), kör tool-flödet
`search → view → examples` och syntetiserar en **pydantic-typad** kandidat via en
structured-output-modell. Kandidaten skrivs till
`data/component-candidates/<slug>/`:

- `component.tsx` — kandidatens källa,
- `intake-info.json` — `prompt`, `model`, `shadcnItemsUsed`, `contentHash`
  (sha256 av `component.tsx`), `requiredNpmDeps`, härkomst,
- `README.md` — operatörens gransknings- och kureringsinstruktion.

### 2. Hårda separationsregler (grinden)

1. **Egen MCP-server.** CLI:t läser ALDRIG `.cursor/mcp.json`; det äger sina
   egna server-parametrar (`npx shadcn@latest mcp`).
2. **Skriver aldrig i ägar-pathar.** CLI:t skriver ALDRIG i `data/starters/`
   eller `packages/generation/orchestration/` (dossiers/scaffolds). En
   guard (`guard_candidate_output_dir`, delad med dossier-/variant-generatorerna)
   vägrar varje skrivning under de kanoniska träden. Promotering in i en Starter
   är ett **operatörsbeslut via granskad PR**.
3. **Ärligt fel utan nyckel.** Utan `OPENAI_API_KEY` faller CLI:t med ett ärligt
   fel — INGEN mock-fallback (ett kurerat intag utan modell vore en påhittad
   kandidat).
4. **Operatörslager, inte byggkedja.** CLI:t är ett operatörsverktyg; LLM-anropet
   sker vid intag, aldrig i byggkedjan eller i den genererade sajtens runtime.
5. **Inga nya npm-beroenden smygs in.** Kandidatens `requiredNpmDeps` är ett
   granskningsfält; en Starter får inte dra in ett nytt npm-beroende utan policy
   + operatörsgodkännande (om beroendet saknas i mål-Startern behålls det native
   mönstret).

### 3. Kandidater är committbara (ingen gitignore-post)

Till skillnad från `data/dossier-candidates/` och `data/scaffold-candidates/`
(gitignorade) ska `data/component-candidates/` INTE gitignoreras — poängen med ett
granskat intag är att kandidaten (inkl. den verkliga intag-körningens
`intake-info.json`) checkas in som bevis och granskas i PR:en. repo-boundaries
får en ägar-post för katalogen (speglar `data/dossier-candidates`-mönstret men med
committbar policy).

### 4. Python-beroende `openai-agents` (pinnat)

`openai-agents` läggs i `requirements.txt` pinnat exakt (`==0.17.5`). Det är
operatörens Python-lager — TOOLS.md:s npm-förbud gäller användarsajternas
beroenden, inte operatörsverktygen. Importen är lazy i CLI:t (snabb start + ärligt
fel utanför venv); CI-testerna mockar MCP-sessionen och importerar aldrig SDK:n
eller anropar nätet.

## Vad ADR 0054 INTE beslutar

- Ingen automatisk montering av en intagen komponent i en sajt (component_add är
  fortsatt partial/mount-only, se ADR 0057).
- Ingen ändring av capability-axeln eller dossier-axeln.
- Inga nya runtime-libs i någon Starter.

## Verifiering

- `python scripts/component_intake.py --prompt "accordion …" --slug accordion` —
  verklig körning mot shadcn-registret (npx shadcn@latest mcp), kandidat skriven
  med `requiredNpmDeps: []` (modellen valde native `<details>`-mönster, noll nya
  beroenden) — incheckad som bevis i `data/component-candidates/accordion/`.
- `tests/test_component_intake.py` — hela orkestreringen mot mockad MCP-session +
  modell (offline, ingen npx/nyckel i CI), inkl. guarderna mot `data/starters/`
  och orchestration-trädet samt det ärliga felet utan nyckel.
- `python scripts/governance_validate.py`, `rules_sync --check`,
  `check_term_coverage --strict`, `ruff check .` — gröna.
