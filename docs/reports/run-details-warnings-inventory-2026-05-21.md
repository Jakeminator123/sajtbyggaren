# Run Details warnings inventory (2026-05-21)

Read-only inventeringspass: alla befintliga warning-/varningsfält i
pipeline-artefakter och UI-ytor, plus rekommendation för var framtida
`intentGuardWarnings` bör visas.

## 1. site-plan.json

| Fält | Schema | Producent | Konsument |
| --- | --- | --- | --- |
| `pageIntentWarnings` | `governance/schemas/site-plan.schema.json` (array of `{page, expectedPath, reason}`) | `packages/generation/planning/plan.py:_page_intent_warnings()` — jämför `wizardMustHave`-sidor mot scaffoldens `routePlan` | Propageras vidare till `build-result.json` via `scripts/build_site.py` |

Inga övriga warning-fält i site-plan-schemat.

## 2. build-result.json

| Fält | Typ | Producent | Konsument |
| --- | --- | --- | --- |
| `pageIntentWarnings` | `list[{page, expectedPath, reason}]` | Kopieras rakt från `site-plan.json` i `scripts/build_site.py` rad 2523 | Viewser Run Details (idag: **inte renderad** — fältet finns i payloaden men `BuildSection` i `run-details-panel.tsx` läser det inte) |
| `placeholderContactFields` | `list[str]` (e.g. `["phone","email"]`) | `scripts/build_site.py:_prompt_meta_placeholder_contact_fields()` — läser sidecar-metans `placeholderContactFields` (B133) | Viewser `BuildSection` → amber-badge med `⚠ Kontakt-fält är platshållare: ...` |
| `placeholderContactMessage` | `str` | `scripts/build_site.py:_placeholder_contact_warning_message()` — canonical operator-facing prosa | JSON-artefakt (operatör kan läsa direkt); Viewser visar inte denna sträng (genererar eget badge-text) |
| `status` (degraded / failed) | `str` | Builder-slutstatus baserat på npm/quality gate | Viewser `StatusBadge` renderar amber/red badge |
| `codegen.riskNotes` | `list[str]` | `packages/generation/codegen/codegen.py` — real `codegenModel` skriver risk-observations | Viewser `CodegenSection` renderar som lista |
| `codegen.error` | `str` | Codegen-catchblock | Viewser `CodegenSection` renderar red box |

## 3. Sidecar / run-meta (`<siteId>.vN.meta.json`)

| Fält | Typ | Producent | Konsument |
| --- | --- | --- | --- |
| `placeholderContactFields` | `list[str]` | `scripts/prompt_to_project_input.py` rad 1893 — skrivs när `_placeholder_contact()` fyllde dummy-värden | `scripts/build_site.py:_prompt_meta_placeholder_contact_fields()` läser vid build-tid |
| `wizardMustHave` | `list[str]` | `scripts/prompt_to_project_input.py` rad 1899 — Discovery-wizardens page-labels | `scripts/build_site.py:_prompt_meta_wizard_must_have()` → `pageIntentWarnings` i site-plan + build-result |
| `discoveryDecision.fallbackWarnings` | `list[{code, message, ...}]` | `packages/generation/discovery/resolve.py` | Backoffice Discovery dry-run-vyn; ärvs till v2+ för Backoffice/Doctor |

## 4. quality-result.json

| Fält | Typ | Producent | Konsument |
| --- | --- | --- | --- |
| `status` | `str` (ok / degraded / failed) | `packages/generation/quality_gate/gate.py` | Viewser `QualitySection` → `StatusBadge` |
| `checks[].findings` | `list[str]` | Individuella Quality Gate-checks (typecheck, route-scan, build-status, policy-compliance) | Viewser `QualitySection` renderar max 5 findings per check |

Inga explicit namngivna "warning"-fält — `status=degraded` och per-check findings fungerar som implicit warning-mekanism.

## 5. repair-result.json

| Fält | Typ | Producent | Konsument |
| --- | --- | --- | --- |
| `status` | `str` (not-needed / partial / failed) | `packages/generation/repair/` | Viewser `RepairSection` → `StatusBadge` med `no-fix-applied` = amber |
| `remainingErrors` | `list[str]` | Repair Pipeline sandwich-loop | Viewser `RepairSection` renderar red-lista |

## 6. Run Details UI (`apps/viewser/components/run-details-panel.tsx`)

Befintliga renderade warnings/varningar:

| UI-element | Datakälla | Visuellt uttryck |
| --- | --- | --- |
| `placeholderContactFields` amber-badge | `build-result.json:placeholderContactFields` | Amber-box med `⚠ Kontakt-fält är platshållare: ...` + subtext |
| `StatusBadge` (degraded/warning) | Diverse `status`-fält | Amber badge (`bg-amber-500/15`) |
| `codegen.riskNotes` lista | `build-result.json:codegen.riskNotes` | Bullet-list i Codegen-sektionen |
| `codegen.error` red box | `build-result.json:codegen.error` | Red background paragraph |
| `remainingErrors` red lista | `repair-result.json:remainingErrors` | Red bullet list i Repair-sektionen |
| Quality findings | `quality-result.json:checks[].findings` | Bullet list under varje check, max 5 |

**Ej renderade trots att data finns i payloaden:**

| Fält i payload | Anledning att det inte renderas |
| --- | --- |
| `pageIntentWarnings` | `SitePlanSection` läser bara `scaffoldId`, `variantId`, `starterId`, `routePlan` — B132 landade warning-only men UI-rendering saknas |

## 7. Backoffice (`backoffice/`)

| Vy | Warning-typ | Källa |
| --- | --- | --- |
| Discovery dry-run (`views/building_blocks.py`) | `fallbackWarnings` JSON-expandable | `DiscoveryDecision.fallbackWarnings` från `resolve.py` |
| Discovery kontroll (`views/building_blocks.py`) | `st.warning(...)` edit-mode-disclaimer | Statisk Streamlit-varning |
| Asset graph / Doctor (`asset_graph.py`) | `level: "warning"` per scaffold/node | `run_health_checks` → Doctor findings |
| Engine Runs (`views/engine_runs.py`) | `st.warning(...)` vid trace-parse-fel | Defensiv felhantering |
| Trace viewer (`views/_trace.py`) | Severity `"warning"` events | Structured `trace.ndjson` events med fail/error-status |
| Maintenance (`views/maintenance.py`) | `CleanupItem.warning` fält per FS-target | `plan_warning_cleanup()` — operatör-bekräftelse krävs |
| Selection profiles (`discovery_control.py`) | `level="warning"` per signal-fynd + `fallbackWarnings` summary | Discovery taxonomy gap-analysis |

## 8. Rekommendation: var `intentGuardWarnings` bör visas

`intentGuardWarnings` (prompt-vs-wizard-mismatch-flaggor) bör följa samma
mönster som `pageIntentWarnings` (B132):

### 8.1 Dataflöde (förslag)

```text
prompt_to_project_input.py (eller ny intent_guard.py)
  → meta sidecar: meta["intentGuardWarnings"] = [...]
  → build_site.py läser från meta vid build-tid
  → site-plan.json ELLER build-result.json: "intentGuardWarnings": [...]
  → Viewser Run Details renderar
  → Backoffice Doctor/trace kan läsa
```

### 8.2 Artefakt-placering

| Alternativ | Fördelar | Nackdelar |
| --- | --- | --- |
| **build-result.json** (rekommenderat) | Konsistent med `placeholderContactFields`/`pageIntentWarnings`; Run Details läser redan build-result | Kräver att `build_site.py` propagerar fältet |
| site-plan.json | Semantiskt tidigt (plan-fas) | Intent Guard produceras vid prompt-till-project-input, inte vid planning; schema-ändring krävs |
| Separat artefakt | Renast separation | Bryter 8-artefakt-kontraktet (engine-run.v1) |

**Rekommendation:** skriv `intentGuardWarnings` i `build-result.json` med
samma array-of-objects-mönster som `pageIntentWarnings`:

```json
"intentGuardWarnings": [
  {
    "field": "businessType",
    "promptValue": "mat/soppa",
    "wizardValue": "gym/bygg",
    "severity": "high",
    "message": "Fri prompt och wizard-val pekar mot olika branscher."
  }
]
```

### 8.3 UI-rendering i Run Details

Placera en ny amber-box (samma stil som `placeholderContactFields`-badge)
i `BuildSection`, direkt under befintliga placeholder-varningen:

```text
⚠ Prompt/wizard-mismatch: <field> — prompt säger "<X>", wizard säger "<Y>".
```

Operatören ser konflikten direkt i samma vy som status, routes och
kontakt-placeholder.

### 8.4 Backoffice-exponering

`views/_trace.py` kan redan hantera severity `"warning"` events. Om
Intent Guard emittar en trace-event med `[intent_guard.mismatch]` dyker
den automatiskt upp i trace-vyn med amber-ikon. Separat Doctor-rule
(`asset_graph.py:run_health_checks`) kan flagga runs med intent-guard-
warnings som "requires operator review".

## Sammanfattning

- **3 warning-fält** existerar idag i pipeline-artefakterna:
  `pageIntentWarnings`, `placeholderContactFields`/`placeholderContactMessage`,
  `fallbackWarnings`.
- **1 fält (`pageIntentWarnings`) skrivs till build-result men renderas
  inte i Run Details UI** — gap sedan B132.
- Framtida `intentGuardWarnings` bör landa i `build-result.json` med
  rendering i `BuildSection` och trace-event-exponering i Backoffice.
