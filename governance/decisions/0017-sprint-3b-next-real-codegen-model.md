# ADR 0017 - Sprint 3B-next: minimal real codegenModel v1

**Status:** accepted
**Datum:** 2026-05-09
**Beroenden:** ADR 0009 (Engine Run + Model Roles), ADR 0013 (schema-
lock), ADR 0015 (Sprint 3A codegen + Quality Gate + Repair skeleton),
ADR 0016 (Sprint 3B mekanisk repair + sandwich-loop, plus v1.1 audit-
fixar och term-disciplin).

## Kontext

Sprint 3B v1 + v1.1 levererade Repair Pipeline med en riktig mekanisk
fix (`ensure-default-export`) och sandwich-loopen som re-kör Quality
Gate efter mutation. `codegenModel` var dock fortfarande
**deterministisk** — inga LLM-anrop. Reviewer-rundan efter `628c865`
godkände att Sprint 3B-next aktiverar **det första riktiga
codegenModel-anropet** men höll scope smal:

- bara `marketing-base` (de andra starters är inte produktionsklara)
- bara på befintligt Generation Package
- structured fallback om LLM failar
- Quality Gate → Repair Pipeline → final Quality Gate ska behållas
- inga nya lanes / StackBlitz / Backoffice / starter-harmonisering /
  B13-storrefactor

## Beslut

### 1) LLM kallas via narrow structured output

`packages/generation/codegen/codegen.py:_call_real_codegen_model`
anropar `OpenAI.responses.parse` med en specifik Pydantic-typ —
`CodegenLLMResponse` — som **endast** innehåller två fält:

- `rationale: str` — en paragraf som förklarar codegen-strategin för
  just denna sajt (vilka konverteringsmål driver routes, varför en
  Dossier mountas på en specifik sida, etc.).
- `riskNotes: list[str]` — 0-3 korta riskpunkter som operatören eller
  Quality Gate / Repair Pipeline bör vara uppmärksam på.

LLM får **inte** välja file-paths, scaffolds eller starter-ändringar.
Filerna i `CodegenResult.files` produceras deterministiskt i alla
fyra code paths. Det är bevisad disciplin: en hallucinerande LLM kan
inte injicera filer som bryter route- eller Dossier-policyn som
scaffold + plan redan har låst. Sprint 3C eller senare kan vidga
kontraktet när vi har bevis på att Quality Gate + Repair Pipeline
fångar drift end-to-end.

`riskNotes` cappas till 3 (`max_length=3` på Pydantic-fältet) så en
pratglad LLM inte kan blåsa upp `build-result.json`.

### 2) Fyra distinkta `CodegenSource`-värden

`CodegenSource` literal håller samma fyra strängar som ADR 0015 låste,
men semantiken förfinas:

| `source` | Trigger |
|---|---|
| `real` | `OPENAI_API_KEY` satt + `starter_id == "marketing-base"` + LLM-anrop lyckas |
| `mock-llm-error` | `OPENAI_API_KEY` satt + `starter_id == "marketing-base"` + LLM-anrop kastar (eller resolver kastar) |
| `mock-no-key` | `OPENAI_API_KEY` saknas + `starter_id == "marketing-base"` |
| `deterministic-v1` | `starter_id` inte i `_REAL_CODEGEN_STARTERS` (Sprint 3A heritage; medvetet skip) |

Det följer samma mönster som `briefSource` och `planSource` från
Sprint 2A/2B. `deterministic-v1` är inte längre default — det är
explicit "scope-uteslutet" så Sprint 3B-next aldrig påstår att riktig
codegen körts på en starter den inte stöder.

`_REAL_CODEGEN_STARTERS = {"marketing-base"}` är en hårdkodad set i
`packages/generation/codegen/codegen.py`. Att lägga till en starter
kräver två saker: (1) starter-mappen ska faktiskt finnas på disk
med innehåll, (2) en separat sprint som verifierar att
`codegenModel` kan resonera om starter-strukturen.

### 3) Token-användning spåras på `CodegenResult.usage`

Real-LLM-pathen lagrar `promptTokens`, `completionTokens` och
`totalTokens` i en ny `CodegenUsage`-Pydantic-typ. Mock- och
deterministic-paths lämnar fältet zeroed (ärligt — inga tokens
spenderades).

`build-result.json:codegen` får två nya nycklar:

- `riskNotes: string[]` (alltid present; tom på icke-real)
- `usage: {promptTokens, completionTokens, totalTokens}` (alltid
  present; zeroed på icke-real)

`build-result.json:modelUsage` aggregeras INTE i Sprint 3B-next; det
är fortfarande ett zeroed stub. Sprint 3C lägger till
brief + planning + codegen-sammanslagning. Operatören som vill se
codegen-kostnad läser `build-result.json:codegen.usage` direkt.

### 4) Resolver följer samma mönster som brief och planning

`packages/generation/codegen/models.py:resolve_codegen_model` läser
`governance/policies/llm-models.v1.json:roles[id="codegenModel"]` och
returnerar `model`-strängen. Strict: kastar
`CodegenModelResolutionError` när rollen saknas, providern inte är
openai, eller model-fältet är tomt — samma kontrakt som
`resolve_brief_model` och `resolve_planning_model`.

Resolver-fel kastas inom samma `try/except` som LLM-anropet så ett
trasigt policy-läge ger `source="mock-llm-error"` istället för en
crash. Build-pipelinen fortsätter med deterministisk fallback.

### 5) Quality Gate → Repair Pipeline → final Quality Gate behålls

Phase 3-orderingen från ADR 0016 v1.1 är oförändrad. `produce_codegen_artefakt`
returnerar samma `CodegenResult`-shape (utökad med `riskNotes` och
`usage`); det betyder att `scripts/build_site.py:run_phase3_quality_and_repair`
inte rörts och fortfarande är 33-rad tunn wiring. Repair Pipeline har
inte heller rörts; `ensure-default-export` adresserar fortfarande
samma route-scan-findings.

### 6) `dev_generate.py` rörs inte

Mock-pipelinen anropar `produce_codegen_artefakt` med `routes_written=
[]` och `dossier_components=[]`, vilket genererar 3 deterministiska
filer. Med ny logik och `starter_id="marketing-base"` blir source
`mock-no-key` (eller `real` om operatören kör med nyckel). Det är
samma signatur så ingen ändring behövs i `scripts/dev_generate.py`.

### 7) ADR 0015 § 6 + B13 är fortfarande öppna

Sprint 3B-next aktiverar real LLM-call men flyttar inte `write_pages`
/ `mount_dossier_components` / `patch_globals_css` ur scripts/. B13
kvarstår som dokumenterad skuld i ADR 0015 §6. Real codegenModel
producerar metadata, inte filer; en framtida sprint som vidgar LLM-
kontraktet till file-emission kommer naturligt att stänga B13 vid
samma tillfälle.

## Konsekvenser

- `build-result.json:codegen.source` rapporterar nu fyra distinkta
  värden som ärligt speglar vad som faktiskt hände.
- `build-result.json:codegen.usage` exposerar token-spend för Sprint
  3C-aggregering eller Backoffice-visning.
- En operator med `OPENAI_API_KEY` och `painter-palma` får real LLM-
  generated rationale + risk-notes, vilket ger faktisk codegen-
  insikt utan att riskera filhallucinationer.
- Tester kör utan att kalla riktig OpenAI; `tests/test_codegen.py`
  har autouse-fixture som tar bort `OPENAI_API_KEY` plus mockar
  `_call_real_codegen_model`. Den enda gated-testen är
  `tests/test_real_codegen_model.py::test_real_codegen_model_call_marketing_base`
  (skippad om inte `SAJTBYGGAREN_E2E=1`).
- `engine-run.v1.json` och `repo-boundaries.v1.json` är oförändrade —
  Sprint 3B-next vidgar bara `CodegenResult`-payloaden, inte
  arkitekturen.

## Vad detta INTE är

- **Inte LLM-baserad file-emission.** LLM levererar metadata; filerna
  produceras fortfarande deterministiskt. Sprint 3C eller senare
  vidgar kontraktet när Quality Gate + Repair Pipeline har bevisad
  drift-fångst.
- **Inte real-codegen för andra starters än `marketing-base`.**
  `data/starters/commerce-base/` är fortfarande oharmoniserad (B20).
  Övriga starter-IDs är gitkeep-only.
- **Inte modelUsage-aggregering.** Sprint 3C synkar
  `brief.usage + planning.usage + codegen.usage` till
  `build-result.json:modelUsage`. Sprint 3B-next exposerar bara
  `codegen.usage` som ett separat fält.
- **Inte ny mekanisk fix.** Repair Pipeline-registret är oförändrat.
- **Inte B13-stängning.** Produktlogik i `scripts/build_site.py` är
  oförändrad.
- **Inte StackBlitzRuntime / Backoffice / starter-harmonisering /
  Shopify / Stripe / Clerk.**

## Alternativ vi övervägde

1. **Låta LLM emittera CodegenFile entries (file-paths + roles).**
   Avvisat: hallucinerade filer kan bryta route-/Dossier-policy som
   scaffold + plan redan låst. Smal scope först; vidgning när drift-
   skydd är beprövat.

2. **Aktivera real codegen för alla starters.**
   Avvisat: `commerce-base` är oharmoniserad; övriga är tomma. Att
   skicka en tom starter genom LLM ger ingen mening. Hård starter-
   gating ger ärlig telemetri.

3. **Aggregera `modelUsage` i samma sprint.**
   Avvisat: scope-creep. `brief.usage` finns inte ännu (Sprint 2A
   sparade inte usage); `planning.usage` finns inte heller. Sprint 3C
   adresserar alla tre samtidigt.

4. **Sätta default `source` till `mock-no-key` även för
   icke-marketing-base starters.**
   Avvisat: `deterministic-v1` är ärligare — det säger "ingen LLM
   kallades, scope-uteslutet" istället för "API-nyckel saknades".
   Fyra distinkta source-värden för fyra distinkta tillstånd.

## Verifiering

Sprint 3B-next anses levererad när:

- `produce_codegen_artefakt` returnerar `source` motsvarande de fyra
  paths ovan (real / mock-llm-error / mock-no-key / deterministic-v1).
- `tests/test_codegen.py` täcker alla fyra paths via mockad
  `_call_real_codegen_model` (utan att kalla OpenAI på riktigt).
- `tests/test_real_codegen_model.py` har en gated test som kallar
  riktig OpenAI när `SAJTBYGGAREN_E2E=1 + OPENAI_API_KEY` är satt.
- `governance_validate`, `rules_sync --check`,
  `check_term_coverage --strict`, `pytest`, `ruff` är gröna.
- `build-result.json:codegen` exposerar `riskNotes` och `usage` plus
  de tidigare fyra fälten.

## B-IDs

Inga nya bug-IDs öppnas. Befintliga bug B13 (produktlogik i scripts/)
och bug B20 (commerce-base oharmoniserad) kvarstår per
`docs/known-issues.md`.
