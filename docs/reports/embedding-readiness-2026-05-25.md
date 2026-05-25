# Embeddings readiness audit — 2026-05-25

**Roll:** Scout, read-only.
**Bas:** `origin/jakob-be` HEAD `86c01fa` (`fix(grind): close B83 service slug
collision (#81)`), nyare än referenscommit `b12c164`.
**Branch:** `cursor/jakob-be-scout-embeddings-readiness`.
**Scope:** Avgöra om vi kan starta embeddings-implementation i nästa sprint
(Go/No-Go) och, om Go, vad första kontraktet bör se ut.

Inga API-anrop har gjorts. Inga filer utanför `docs/reports/` har ändrats.
Den lokala WIP-stashen för Lane 2/4 (`scout-pre-checkout`) lämnades orörd
under audit.

---

## 1. Go/No-Go just nu

**No-Go ännu — men nära. Hold tills Lane 2 är formellt mergad till
`jakob-be`.**

ADR-0026:s parkering hade två konkreta trigger-villkor i avsnittet "Beslut":

1. **B137 + B138 stängda** så att LLM-output håller hela vägen brief→render.
2. **B139/B140/B141 stängda eller parkerade** med dokumenterad rationale.

Båda är formellt uppfyllda på disk: `docs/known-issues.md` på `origin/jakob-be`
har samtliga fem markerade som stängda (`B137`/`B138` 2026-05-21, `B141`
2026-05-21, `B139`/`B140` 2026-05-22). Selection-skalan är fortfarande
liten (3 scaffolds + 11 soft dossiers, långt under ADR-0026:s 30-troskeln),
så scaling-triggern är inte aktiv heller — bara contract-propagation-
triggern bär beslutet.

Två kvarvarande blockers gör att domen *just nu* blir No-Go:

- **Lane 2 är listad som pågående**, inte avslutad, i
  `docs/current-focus.md:104-107` ("Direkt nästa fokus … 4 lanes pågår").
  Bug-fixarna är inne men lane:n är inte formellt klosad i köplanen.
- **Cross-lock-tester saknas på disk.** `docs/known-issues.md` på
  `origin/jakob-be` refererar till `tests/test_llm_contract_propagation.py`
  med åtta specifika test-namn för B137-B141 cross-locks, men filen finns
  inte i commit-historiken (`git log -- tests/test_llm_contract_propagation.py`
  ger tom output). Tester ligger som untracked WIP lokalt. Utan dem är
  kontraktet *påstått* lockat men inte mekaniskt skyddat mot regression.

ADR-0026:s mini-eval-villkor (4 baseline-prompter ≥7/10) är inte verifierat
i ny re-eval efter B137-B141-fixarna — det är vad Lane 4 (Golden Path
eval baseline) ska producera, och den lane:n delar samma "pågående"-status
som Lane 2.

**Konkret Go-villkor när det inträffar:** Lane 2:s contract-lock-tester
mergade till `jakob-be` + Lane 4:s första Golden Path-körning visar
genomsnitt ≥7/10 utan något case <6.5. Då — och inte tidigare —
kan ADR-0026 omklassas Accepted→Superseded och embeddings-sprinten startas.

---

## 2. Vad finns redan på disk

**Policy + schema (låsta, status `draft-but-authoritative`)**

- `governance/policies/embedding-policy.v1.json` — fem domäner låsta:
  `scaffolds` (topK=5, minScore=0.62), `dossiers` (topK=8, minScore=0.6),
  `reference-templates` (topK=5, minScore=0.55), `section-patterns`
  (topK=10, minScore=0.5), `style-signatures` (topK=5, minScore=0.55).
  Alla pekar på `ownerPackage: packages/generation/orchestration/embedding`.
- `governance/schemas/embedding-policy.schema.json` — låser kontraktet
  ovan, ingen ändring behövs vid implementation.
- `governance/policies/llm-models.v1.json:68-72` — `embeddingModel`-rollen
  registrerad med `model: text-embedding-3-small` + `provider: openai`,
  ingrupperad i `sharedModelGroups.embedding`. Default i `defaults`-blocket
  är samma sträng.
- `governance/decisions/0026-embeddings-postponed-until-contract.md` —
  status `Proposed`, datum 2026-05-21, beroenden ADR 0005/0012/0024.

**Index-pipeline**

- `data/embedding-index/` är gitignored (verifierat med `git check-ignore`).
  Mappen finns inte i working tree. ADR-0026:s "infrastruktur förberedd"
  stämmer — det räcker att skapa katalogen vid första indexkörningen.
- `packages/generation/orchestration/embedding/` finns inte — modulen
  som policy + ADR pekar ut är inte initierad.

**Curerade källtexter (delvis på plats)**

- Scaffold `selection-profile.json` har redan `embeddingText` curerad text
  per scaffold (verifierat på `local-service-business/selection-profile.json:3`).
  Konsekvent med policy-principen `embedding-text-is-curated`.
- Dossier-manifesten har `summary`-fält men *ingen* `embeddingText` än
  (kontrollerat på `booking-cta/manifest.json`). Policyn säger att index
  byggs från "dossier.json per Dossier (purpose, bestFor, activation)" —
  vi kan starta från `summary` eller införa explicit `embeddingText`
  som dokumentation-disciplinerad sträng. Schemabumpning krävs i
  `governance/schemas/dossier.schema.json` om vi vill kräva fältet.
- `data/reference-templates/` finns inte. Domänerna `reference-templates`,
  `section-patterns` och `style-signatures` saknar källdata helt och
  bör därför *parkeras separat* från scaffold-/dossier-domänerna.

**Sajtmaskin-inspiration**

- Sajtmaskin nämns i `docs/product-operating-context.md:47-60`, `54-58`,
  `120-121` som *referens och baslinje*, uttryckligen inte som kodbas
  att återinföra. Ingen sajtmaskin-arkitektur eller kod ligger i repot.
- `docs/current-focus.md:114` listar "Sajtmaskin inspiration Scout —
  lokalt-only (kräver `sajtmaskin.rar` på operatörens maskin)" som
  parkerad lane. Embeddings-arkitekturen ska **inte** vänta på den —
  vi vet redan att sajtmaskins bredd (auth, credits, domäner,
  integrationslager) inte ska kopieras hit. Sajtmaskins eventuella
  embedding-erfarenhet kan plockas upp som en separat operator-rapport
  efter att skissen nedan är gjord.

---

## 3. ADR-0026-blockers fortfarande öppna efter Lane 2-fixarna

| # | Blocker | Status | Stängs av |
| --- | --- | --- | --- |
| B1 | Lane 2 formell merge till `jakob-be` | Pågående (`docs/current-focus.md:104-107`) | Builder-PR som flyttar B137-B141 cross-lock-tester + ev. follow-up från WIP till commit. |
| B2 | `tests/test_llm_contract_propagation.py` saknas på disk | Untracked/WIP, refererad i `known-issues.md` men ingen commit-historik | Samma Lane 2-PR. Utan suiten är kontraktet inte mekaniskt låst → regression-risk innan vi lägger till en ny signal-källa. |
| B3 | Mini-eval (≥7/10 på 4 baseline-prompter) inte ny-verifierad | Lane 4 pågående (Golden Path eval) | Första körning av `scripts/run_golden_path_eval.py` med snitt ≥7/10 och inget case <6.5. |
| B4 | Selection-problemet inte isolerat per case | Öppen | Lane 4-resultatet behöver indikera *vilka* case som faktiskt skulle gynnats av embedding-retrieval (idag gör 3 scaffolds + 11 dossiers manuell matchning trivial). Om inga case är embedding-känsliga är Go-värdet litet. |
| B5 | `DiscoveryDecision`-schema saknar plats för embedding-score | Öppen | Schema-bump i `governance/schemas/discovery-decision.schema.json` (se §4). |
| B6 | `embeddingText` saknas på dossier-manifesten | Öppen | Antingen schema-bumpa `dossier.schema.json` med valfritt `embeddingText`, eller acceptera `summary` som källfält och dokumentera valet i embedding-policy v2. |
| B7 | Operator-frågor i ADR-0026 §"Öppna frågor" obesvarade | Öppen | Modellval (se §5), cache-strategi (se §4), backoffice-/Doctor-yta. Behöver operatörsbeslut innan första prod-commit. |
| B8 | ADR-0026 status `Proposed`, inte `Accepted` | Öppen | Operatör godkänner och bumpar till `Accepted` (eller `Superseded` om ny ADR skrivs). |

B1-B3 är hårda blockers för Go. B4-B8 är schemabumpar/beslut som måste
in i samma sprint som första implementations-PR men kan beredas parallellt.

---

## 4. Minsta möjliga arkitektur-sketch när Go inträffar

### 4.1 Var i brief→plan-flödet

Entrypoint: `packages/generation/planning/plan.py:produce_site_plan`
(rad 1134). Två konkreta call-sites där embedding-retrieval ska sättas in:

- **Scaffold recall:** ersätt/komplettera den deterministiska heuristiken
  i `_pick_scaffold_from_brief` (`plan.py:346-373`) med ett retrieval-steg.
  Mock-vägen behåller heuristiken som fallback när embedding-index saknas
  eller `OPENAI_API_KEY` inte är satt — samma mönster som `briefModel`
  och `planningModel` redan följer (jfr `AGENTS.md` "Builder MVP", `briefSource=mock-no-key`).
- **Dossier recall + LLM-rerank:** mellan `filter_capabilities`
  (`plan.py:289-338`) och `_real_plan_choice` (`plan.py:505-567`). Idag
  skickar `_build_planning_prompt` *hela* registry till `planningModel`
  (`plan.py:522`). När registry växer bortom ~30 dossiers ska vi i stället
  ge LLM topK-kandidater från embedding-index per
  `embedding-policy.v1.json`-domännerna (`topKDefault: 5` för scaffolds,
  `8` för dossiers). `rerankModel` (redan registrerad i `llm-models.v1.json:32-36`)
  väger sedan kandidaterna i en separat call.

Discovery-pinning kvarstår: när `DiscoveryDecision.selectedScaffoldId`
är satt av wizarden (`resolve.py:485-487`, `selectionSource="wizard"`)
ska embedding-retrieval skippas för scaffolden — operatörens explicita
val vinner alltid över retrieval-score (samma princip som B137-fixen).

### 4.2 Cache/TTL

Två lager, båda owned av `packages/generation/orchestration/embedding/`:

| Lager | Lagring | Nyckel | TTL | Invalidering |
| --- | --- | --- | --- | --- |
| **Källtext-index** (per domän) | `data/embedding-index/<domain>/index.json` (vektor + meta) + `data/embedding-index/<domain>/manifest.json` (källfil-mtime + sha256) | `<domain>:<id>` (t.ex. `scaffolds:local-service-business`) | Ingen TTL — invalideras av manifest-diff | Rebuild när källfilens sha256 ändrats; rebuild *hela domän-indexet* när `embedding-policy.v1.json.version` bumpas eller `embeddingModel`-strängen i `llm-models.v1.json` byter värde. |
| **Query-cache** (per Site Brief) | In-memory dict i `produce_site_plan`-runen + valfri persistens till `data/runs/<runId>/embedding-cache.json` | `sha256(sortedJSON(site_brief.embeddingFields))` — bara fälten som faktiskt går in i embedding-prompt (rawPrompt, businessTypeGuess, servicesMentioned, tone, pageCount) | Run-scoped (default), 24h persistent som opt-in | Run-scope rensas vid varje ny run; persistent cache invalideras tillsammans med källtext-index. |

Inga `OPENAI_API_KEY`-anrop görs när source-mtime/sha256 matchar manifest
och query-cache träffar. Cache-miss → en `embeddingModel`-call per
ny källtext, en per ny brief-hash. Detta håller cost låg (3 scaffolds +
11 dossiers ≈ 14 embeddings totalt vid första indexering, sedan bara
deltarn).

### 4.3 Score-exponering i `DiscoveryDecision`

Befintlig `fieldSources`-enum (`discovery-decision.schema.json:111-118`)
är en `Project Input-fält → källa`-map med strikt enum
(`wizard|scrape|brief|taxonomy|default|operator|pinned|derived`). Den
*kan inte* bära numerisk score eller per-kandidat-trace.

**Förslag (kräver schema-bump till `schemaVersion: 2`):**

Lägg till ett valfritt syskon-fält `selectionTrace` på
`DiscoveryDecision` (matchar `embedding-policy.v1.json`-principen
`selection-trace-required`):

```jsonc
"selectionTrace": {
  "type": "object",
  "properties": {
    "scaffolds": { "$ref": "#/$defs/embeddingDomainTrace" },
    "dossiers":  { "$ref": "#/$defs/embeddingDomainTrace" }
  }
}
// där embeddingDomainTrace = {
//   "indexVersion": "embedding-policy.v1+scaffolds",
//   "queryHash": "sha256:…",
//   "candidates": [
//     { "id": "local-service-business", "score": 0.74, "rerankReason": "matchar 'elektriker' + 'lokalt'" },
//     { "id": "restaurant-hospitality", "score": 0.41 }
//   ],
//   "selectedId": "local-service-business",
//   "selectedScore": 0.74,
//   "minScoreFloor": 0.62,
//   "fellBackTo": null
// }
```

Och utöka `fieldSources`-enumen med ett nytt värde `"embedding"` så att
`fieldSources["scaffoldId"]` kan peka på *att* embedding drev valet,
med `selectionTrace.scaffolds.selectedScore` som det numeriska beviset.

Exempel-payload när embedding vann:

```json
{
  "selectedScaffoldId": "local-service-business",
  "selectionSource": "brief",
  "fieldSources": {
    "scaffoldId": "embedding",
    "variantId": "default"
  },
  "selectionTrace": {
    "scaffolds": {
      "indexVersion": "embedding-policy.v1+scaffolds",
      "queryHash": "sha256:a1b2…",
      "candidates": [
        {"id": "local-service-business", "score": 0.74},
        {"id": "ecommerce-lite", "score": 0.31}
      ],
      "selectedId": "local-service-business",
      "selectedScore": 0.74,
      "minScoreFloor": 0.62,
      "fellBackTo": null
    }
  }
}
```

Konsekvens: skarp typing, bakåtkompatibelt (valfritt fält), och Backoffice/
Doctor kan rendera `selectionTrace` precis som `fallbackWarnings` redan
renderas idag.

---

## 5. Modellvalsalternativ

| Alternativ | Kvalitet (sv) | Latency | Kostnad | Ops/Deps | Sekretess | Bedömning |
| --- | --- | --- | --- | --- | --- | --- |
| **Lokal `sentence-transformers`** (t.ex. `paraphrase-multilingual-mpnet-base-v2`) | Hyfsad på sv för korta texter, sämre på branschspecifik nyans | ~50-200 ms / batch på CPU, ~10-30 ms på GPU | Noll efter pip install | Ny tung dep (`torch` + `sentence-transformers` ≈ 1+ GB), måste byggas in i Cloud Agent VM. Offline-kapabelt. | Bäst — texten lämnar aldrig maskinen | Bra som "default off the bench" men dep-storlek krockar med `AGENTS.md`-principen *tunn första version* och bryter mot Cloud Agent-snabbstartens 2 GB-budget. |
| **OpenAI `text-embedding-3-small`** | Stark på sv, känd kvalitet, samma provider som briefModel/planningModel | ~80-150 ms per call över nätet | ~$0.02 per 1M tokens. För 14 källtexter + ~100 briefs/dag: ≪ $1/månad. | Inga nya deps — använder befintlig `openai`-klient. Kräver `OPENAI_API_KEY`. | Skickar Site Brief-text till OpenAI (samma sekretessprofil som briefModel idag) | **Default-rekommendation.** Redan registrerad i `llm-models.v1.json:68-72`, `defaults.embeddingModel`, och `sharedModelGroups.embedding`. Inga schema-, dep- eller infra-bumpar. |
| **Hybrid (lokal default + OpenAI opt-in)** | Bästa av båda | Lokal latency med opt-in remote-fallback | Som lokal default | Dubbel implementation, två kontrakt att underhålla. Governance behöver `embedding-policy.v2` med fältet `runtimeMode`. Fallback-policy blir komplex (vad räknas som "score" när två backends ger olika skalor?). | Konfigurerbar | Inte värt komplexiteten vid 3 scaffolds + 11 dossiers. Lägg på listan för v2 om/när vi får en sekretess-kritisk operator-profil eller behöver air-gapped install. |

**Rekommendation:** Starta med **OpenAI `text-embedding-3-small`**.
Det är redan kontrakterat i policy, kräver ingen ny dep, har samma
sekretessprofil som briefModel/planningModel (vilka redan körs med
samma key), och kostnaden är försumbar vid nuvarande skala. Bygg
indexerings-helpern provider-agnostiskt så hybrid kan läggas på i
embedding-policy v2 utan kodändring i call-sites (samma princip som
`llm-models.v1.json:providerNotes.swap-rule`).

---

## 6. Testplan (3-5 tester innan första prod-anrop)

Alla i `tests/test_embedding_retriever.py` (ny fil, hör hemma i samma
PR som `packages/generation/orchestration/embedding/`):

1. `test_index_build_is_deterministic_per_source_hash` — bygg index två
   gånger från samma `selection-profile.json`, verifiera identisk
   `manifest.json.sha256` och identisk vektor-output med mockad
   `embeddingModel`. Säkerställer att cache-invalidering trigger:as på
   källtext-diff, inget annat.
2. `test_retriever_respects_min_score_floor` — kör mot ett deterministiskt
   embedding-mock som ger score 0.50 på alla kandidater, verifiera att
   scaffolds-domänen (minScoreDefault=0.62) returnerar tom topK och
   triggar fallback-grenen i `_pick_scaffold_from_brief` istället för
   att returnera lågkvalitativ träff.
3. `test_retriever_falls_back_to_mock_without_openai_api_key` — kör utan
   `OPENAI_API_KEY`, verifiera att `produce_site_plan` returnerar samma
   `PlanResult` som idag (`planSource="mock-no-key"`), `selectionTrace`
   utelämnas, `fieldSources["scaffoldId"]` är *inte* `"embedding"`.
   Lockar in att embeddings aldrig blir hård-beroende.
4. `test_discovery_pinning_overrides_embedding` — när
   `DiscoveryDecision.selectionSource == "wizard"` skall embedding-retrieval
   skippas och `fieldSources["scaffoldId"]` förbli `"wizard"`. Cross-lock
   mot B137-mönstret (explicit operator-signal vinner alltid över
   härledd signal).
5. `test_selection_trace_schema_compliance` — bygg en run end-to-end med
   mockad embedding, validera den emitterade `discoveryDecision`-blocken
   mot `governance/schemas/discovery-decision.schema.json` (bumpad till
   v2). Säkerställer att `selectionTrace`-fältet är schema-konformt och
   att existerande consumers (Backoffice, Doctor, Sprintvakt) inte
   bryts.

Optional sjätte test (rekommenderad innan första prod-PR):

6. `test_golden_path_eval_does_not_regress_with_embedding_off` — kör
   `scripts/run_golden_path_eval.py` med embeddings-feature-flag av,
   jämför mot pre-embedding-baseline från Lane 4. Säkerställer att vi
   inte regredierar mock-/heuristik-vägen när embedding-koden läggs in.

---

## 7. "BYGG INTE ÄNNU" vs "KAN BYGGAS NU"

**KAN BYGGAS NU (förberedande, no-runtime-impact):**

- Schema-skiss för `selectionTrace` i `discovery-decision.schema.v2.json`
  (separat draft-fil, inte v1-bump än) — låser kontraktet innan kod skrivs.
- Förslag på `embeddingText`-fält i `dossier.schema.json` v2 + curera
  texterna i alla 11 soft-dossier-manifest. Pure-docs PR, ingen kod
  använder fältet än.
- `governance/decisions/0026`-uppdatering: flytta status `Proposed → Accepted`
  efter operatörsbeslut, eller skriv `ADR-0030 embeddings-implementation-go`
  som superseder med konkreta Go-kriterier (denna rapport som bilaga).
- Skiss i `docs/architecture/embedding-retriever.md` — read-only design-doc
  som beskriver §4 ovan utan att introducera kod. Bra steward-uppgift.

**BYGG INTE ÄNNU (kräver Go + Lane 2-stängning):**

- `packages/generation/orchestration/embedding/` — index-builder + retriever.
- `data/embedding-index/`-fyllning.
- Integration i `plan.py:_pick_scaffold_from_brief` /
  `_build_planning_prompt` / `_real_plan_choice`.
- `rerankModel`-call mellan retrieval och `planningModel`.
- Backoffice-yta som visar `selectionTrace` (kräver schema v2 mergad).
- `reference-templates`/`section-patterns`/`style-signatures`-indexen
  — saknar källdata helt (`data/reference-templates/` finns inte). Egen
  sprint *efter* scaffold/dossier-domänerna fungerar.

---

## 8. Säkerhet i %

- **Go/No-Go-domen (No-Go just nu):** **88%**. Hög säkerhet att vi *inte*
  ska starta idag — Lane 2 är inte mergad och cross-lock-testerna är WIP.
  Osäkerheten ligger i att Lane 2:s återstående arbete kan vara mindre
  än rapporten antar (om bug-fixarna räcker och tester är "nice to have").
  Den osäkerheten faller bort så snart Lane 2-PR mergas eller Operator
  förklarar Lane 2 stängd.

- **Modellvalsrekommendation (OpenAI `text-embedding-3-small`):** **82%**.
  Hög säkerhet på modellvalet givet att policy + defaults redan pekar dit
  och att kostnad/latency är försumbar vid nuvarande skala. Osäkerheten
  ligger i (a) framtida sekretess-/air-gapped-krav som vi inte vet om än,
  och (b) huruvida `text-embedding-3-small` håller på svenska för
  branschspecifik nyans när dossier-utbudet växer. Båda kan adresseras
  med hybrid-mode i embedding-policy v2 senare utan att första
  implementation-PR behöver röras.

---

## Akut fynd

**`docs/known-issues.md` på `origin/jakob-be` refererar till
`tests/test_llm_contract_propagation.py` med åtta specifika test-namn
(rader 607-608, 625-626, 697-698, 729-730, 761-762), men filen finns inte
i commit-historiken** (`git log --all -- tests/test_llm_contract_propagation.py`
ger tom output). Filen ligger som untracked i lokal stash. Det innebär att
dokumentationen påstår att kontrakts-låsen finns men de är inte i någon
branch — en framtida agent som läser known-issues kan tro att B137-B141
är dubbelt skyddade när de inte är det. Detta är inte en blocker för
embeddings-audit:en (cross-locks krävs *innan* Go ändå) men det är en
docs/known-issues-konsistensbug som hör hemma i Lane 2:s slutsteg eller
som en separat docs-PR som markerar testerna som *planerade* tills filen
mergas. Notera också att stashen `scout-pre-checkout` lämnats orörd under
denna audit och behöver popas tillbaka på `cursor/jakob-be-llm-contract-propagation`
eller motsvarande lane:s branch av lane:ns ägare.

---

## Sammanfattning för köplanen

- **Dom:** No-Go just nu. Hård blocker: Lane 2 contract-lock-tester
  mergade till `jakob-be`. Mjuk blocker: Lane 4 mini-eval-resultat.
- **Öppna ADR-0026-blockers efter Lane 2-fixarna:** 8 (B1-B8 i §3).
  Två hårda (B1-B3), resten schemabumpar/beslut.
- **Modellval när Go inträffar:** OpenAI `text-embedding-3-small` —
  redan kontrakterat i `llm-models.v1.json`, ingen ny dep, försumbar
  kostnad vid nuvarande skala (3 scaffolds + 11 dossiers).
- **Första entrypoint:** `packages/generation/planning/plan.py:produce_site_plan`
  → call-sites `_pick_scaffold_from_brief` (rad 346) och
  `_build_planning_prompt`/`_real_plan_choice` (rad 461/505).
- **Score-exponering:** Nytt valfritt `selectionTrace`-fält på
  `DiscoveryDecision` + ny enum-värde `"embedding"` i `fieldSources`,
  schema-bump till v2.
- **Säkerhet på rekommendationen:** 88% (Go/No-Go), 82% (modellval).
