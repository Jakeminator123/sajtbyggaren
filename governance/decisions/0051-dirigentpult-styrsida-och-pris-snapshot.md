# ADR 0051 — Dirigentpult: överordnad styrsida i backoffice + tokenpris-snapshot

**Status:** Accepted
**Datum:** 2026-06-11 (operatörsuppdrag, Jakob; coach-spec via Cloud-agent)
**Beroenden:** ADR 0002 (backoffice är operatörsyta, aldrig runtime),
ADR 0044 (SOUL-runtime + Identitet-vyn), governance/rules/09
(ärlighetsprincipen för actions/mutationer).
Referenser: [`backoffice/views/control_room.py`](../../backoffice/views/control_room.py),
[`scripts/fetch_model_prices.py`](../../scripts/fetch_model_prices.py),
[`data/model-pricing.json`](../../data/model-pricing.json).

## Kontext

Dirigentens kontroller låg utspridda över flera backoffice-sektioner:
modellroller under LLM Engine, persona under Identitet, sanktionerade actions
och skills bara som filer på disk, konduktör-rollernas kontrakt bara i kod,
och tokenpriser fanns inte alls som operatörsyta. Operatören behövde EN
sammanhållen plats att styra och inspektera dirigenten från — utan att någon
kontroll låtsas kunna mer än koden stöder.

## Beslut

### 1. Ny sektion Dirigentpult, först i sidomenyn

En vy (cockpit med flikar A–G) i ny modul `backoffice/views/control_room.py`,
registrerad först i `SECTION_MODULES` och i `backoffice-views.v1.json`
(version 2). Landningsvyn förblir Idag — Dirigentpult är överordnad i menyn,
inte ny default.

### 2. Återanvänd skriv-vägar, duplicera aldrig

- Modellroller (flik A) sparar via nya delade helpers i
  `backoffice/model_roles.py` (atomic write -> governance-validate ->
  rollback) som även LLM Engine / Model Roles använder. Ett modell-/
  providerbyte är fortsatt en policy-bump i `llm-models.v1.json`.
- SOUL-editorn (flik C) är `identity.render_soul_editor` — logiken och
  path-låsen bor kvar i identity-modulen (ADR 0044), Dirigentpulten anropar
  den bara med eget widget-prefix. Editor-cap 8000 tecken; runtime-cap 3500
  tecken visas ärligt i räknaren.

### 3. Ärlighet är hård princip i varje kontroll

- Action-status (flik D) i `docs/openclaw-workspace/action-registry.json`
  får redigeras, men statusen SPEGLAR kodstöd — den togglar ingen förmåga.
  En permanent banner säger detta, och en korskoll varnar när registret
  driftar mot rollkontrakten i koden.
- Skills (flik E) är text, inte behörighet — redigerbara med caps och
  tom-text-skydd, path-låsta via katalogscan (ingen fri path-input).
- Konduktör-rollerna (flik F) visas read-only: kontrakten är frysta
  dataclasses i kod och en ändring är en kod-PR, aldrig en UI-handling.
- ENV-styrda chatt-/vision-/discovery-modeller (flik B) visas read-only och
  deras defaults parsas LIVE ur källfilerna (`backoffice/runtime_models.py`)
  i stället för att hårdkodas — fliken kan inte driva när fallbacken byts i
  koden (som gpt-4o -> gpt-5.5-bytet 2026-06-11).

### 4. Tokenpris-snapshot som data-cache, inte governance-policy

`data/model-pricing.json` (USD per 1M input-/output-tokens) skrivs enbart av
`scripts/fetch_model_prices.py` och läses read-only av flik G. Snapshotten är
en cache över extern fakta — inte en styrande policy — och valideras därför
inte av governance-kedjan utan av `tests/test_fetch_model_prices.py`.
Fältnamnen är engelska i camelCase (`needsRefresh`, `inputPer1M`,
`outputPer1M`, `lastFetched`, `fetchedAt`) per repo-regeln om engelska
JSON-fältnamn.

Hämtningen går i första hand mot OpenAI:s officiella docs-MCP
(`developers.openai.com/mcp`) via en egen MCP-over-HTTP-klient i skriptet
(urllib + JSON-RPC, inga nya beroenden). Ärlig fallback: utan nät/MCP eller
vid parse-miss behålls befintlig snapshot, `needsRefresh: true` skrivs och
skriptet avslutar med exit-kod 0. Prisfält uppdateras bara med siffror som
faktiskt står på prissidan; saknat pris förblir null — aldrig påhittade
värden.

## Konsekvenser

- Operatören styr dirigentens alla ytor från en plats, med samma räcken som
  tidigare (governance-validate, path-lås, read-only där koden äger).
- Registret + testerna (`tests/test_backoffice_control_room.py`,
  `tests/test_backoffice_model_roles.py`, `tests/test_fetch_model_prices.py`)
  låser registrering, path-lås, ärlighetstexter och dynamisk modell-läsning.
- Priserna blir synliga bredvid varje modellroll utan att en stale siffra
  kan smyga sig in som sanning (needsRefresh-flaggan döljs aldrig).
- Nästa planerade slice — per-roll modellparametrar i llm-models-policyn —
  tar ADR 0052.
