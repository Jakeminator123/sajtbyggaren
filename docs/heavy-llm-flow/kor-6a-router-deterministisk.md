# KÖR 6a — OpenClaw Router (deterministisk, no build)

> Snabb produktvinst utan att röra generatorn: chatten slutar bygga om för rena frågor.
> Kan startas **parallellt** med blueprint-spåret. **Ingen LLM** här.

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md) (hela),
[`03-preview-data-och-versioner.md`](03-preview-data-och-versioner.md) §3.
**Beror på:** inget (oberoende start).

---

## Mål

Bygg den **deterministiska** klassificeraren ovanpå init/follow-up. Inga filändringar på
sajten, ingen build, ingen ny model role, inget OpenAI-anrop. Den avgör vad meddelandet
är och hur mycket systemet måste göra.

## Varför

Produktvärde direkt: rena frågor (`vad är klockan`), discovery (`vilka klockor finns?`)
och referens (`som på aftonbladet.se`) ska **inte** trigga build/adapter/iframe. Det är
det dagens primitiva follow-up inte klarar.

## Output (kontrakt)

```jsonc
{
  "messageKind": "answer_only|site_review|edit_instruction|component_discovery|reference_analysis|bug_report|multi_intent|unclear",
  "editKind": "component_add|component_remove|visual_style|copy_change|layout_change|route_add|none",
  "buildRequirement": "none|plan_only|artifact_patch_only|targeted_rebuild|full_rebuild",
  "contextLevel": "none|project_dna|artifacts|artifacts_plus_sections|manifest|selected_files|preview_dom|external_reference|component_registry",
  "target": { "routeId": "...", "sectionId": "...", "sectionOrdinal": 2, "position": "left" },
  "subtasks": [],
  "rationale": "...",
  "requiresClarification": false,
  "shouldStartPreview": false
}
```

## Scope (filer)

- Ny modul, t.ex. `packages/generation/orchestration/router/` (deterministisk heuristik,
  Unicode-medveten regex)
- `governance/schemas/` (router-output-schema)
- `tests/test_router_*.py` (klock-exemplen + 30–50 prompter)

**Off-limits:** LLM/model role (det är `kor-6b`), `build_site.py` generation-kod,
renderers, preview-runtime/adaptrar, viewser-UI, fri filgenerering, att starta
PreviewRuntime i `answer_only`/`plan_only`.

## Trace-regel (viktig)

- Hör routerbeslutet till en **befintlig run/follow-up** → logga i den runens
  `trace.ndjson`.
- Är det `answer_only` **utan** run → **skapa ingen run** bara för loggning. Returnera
  beslutet till UI/API.
- En separat router-logg är ett **senare beslut**, inte denna skiva. Skapa inte ny
  infrastruktur för ett rent svar.

## Testfall (DoD) — klock-exemplen

| Prompt | Förväntat |
|--------|-----------|
| "vad är klockan" | `answer_only`, `buildRequirement: none`, `shouldStartPreview: false`, ingen run skapad |
| "lägg en klocka i andra sektionen till vänster" | `edit_instruction`/`component_add`, `targeted_rebuild`, target upplöst |
| "vilka klockor finns att tillgå?" | `component_discovery`, `none`, `component_registry` |
| "samma klocka som på aftonbladet.se" | `reference_analysis`, `plan_only`, `do_not_copy_exact` |
| "gör sidan mer premium, lägg en klocka, ändra inte texterna" | `multi_intent` med `preserve_copy`-constraint |

Plus: router-testsvit grön; **inga** follow-up-versioneringstester regredderar; routern
kan förklara varför den **inte** startar build för rena frågor.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på router-modulen · `pytest tests/test_router_*.py -q` ·
`governance_validate` (schema rört). Ingen full pytest krävs (skivan rör inte generatorn).

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 6a - bygg en DETERMINISTISK OpenClaw Router enligt 02-orchestrator-och-
intent.md. Klassa userMessage -> messageKind/editKind/buildRequirement/contextLevel/
target. Heuristik + Unicode-medveten regex. INGEN LLM, ingen ny model role.

Krav:
- Inga filandringar pa sajten, ingen build, ingen PreviewRuntime i answer_only/plan_only.
- Las bara artefakter. Ror inte build_site.py generation-kod, renderers, adaptrar, UI.
- Trace-regel: logga i befintlig runs trace.ndjson; for answer_only UTAN run, skapa
  INGEN run bara for loggning - returnera beslutet till UI/API.
- Respektera builder-coexistence (ingen live-session mot anvandarens chatId/siteId).

Definition of done: klock-exemplen (A-E) grona, 30-50 prompter tackta, inga follow-up-
versioneringstester regredderar, ingen run skapas for rena fragor, ruff + router-pytest +
governance_validate grona.
```
