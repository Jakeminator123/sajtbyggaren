# KÖR O1 — OpenClaw Core Contract (design + spike, ingen runtime-kod)

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`02-orchestrator-och-intent.md`](02-orchestrator-och-intent.md),
[`kor-6a-router-deterministisk.md`](kor-6a-router-deterministisk.md),
[`kor-7a-context-assembler.md`](kor-7a-context-assembler.md),
`docs/open_claw.txt` (coach-rådgivning, **icke-canonical & optional** — läs som riktning om filen finns, aldrig som build-order).
**Beror på:** `kor-6a` (inne), `kor-7a` (inne). Detta kort blockerar inget och bygger ingen runtime-kod. **OpenClaw Core V0 är read-only och får implementeras NÄR SOM HELST — även före `kor-7b`/`7c`. Bara Patch Flow (Nivå 2) väntar på 7b/7c.**

---

## Vad detta kort är (och inte är)

Detta är ett **kontrakts-/designkort**, inte en byggkörning. Det definierar vad
"OpenClaw Core" får vara ovanpå den befintliga rälsen, så att en separat
OpenClaw-agent kan designas (t.ex. tillsammans med operatörens coach) **utan**
att råka skapa en parallell motor. Ingen runtime-kod ändras av detta kort.

Bakgrund: routern (`kor-6a`) och Context Assembler (`kor-7a`) är inne. De är
redan de första två delarna av OpenClaw-arkitekturen — men de saknar
"hjärnan" som binder ihop dem till svar/plan. OpenClaw Core är den hjärnan,
och den ska byggas **i repot ovanpå rälsen** — inte hostas på Render som första
steg (coach, `open_claw.txt`: bygg core först, deploya worker sist).

## Mål

Definiera den **transienta** beslutsstrukturen `OpenClawDecision`, dess
**tool-yta** och dess **capability-plan** (vilket meddelande → vilken kontextnivå
→ vilken handling), för en **V0** som bara kan:

- svara (`answer_only`),
- be om förtydligande (`clarification`),
- föreslå en plan (`plan_only`),
- och **markera** att en ändring kräver patch-planner som ännu saknas
  (`patch_plan_request`).

V0 **bygger aldrig**, **skriver aldrig filer**, **startar aldrig preview**,
**installerar aldrig dependencies**, **kör aldrig shell** och **rör aldrig**
`current.json`. Den är lika read-only som `kor-7a` — den föreslår, den utför inte.

## Icke-mål (hårda gränser, från `04` §3–4 + `open_claw.txt`)

- **Ingen hostad/Render-worker** i detta steg. Render blir aktuellt först på Nivå 3
  (nedan), när patch-apply, auth, rate-limit, trace och rollback finns.
- **Ingen fri filpatch.** OpenClaw får aldrig skriva Next.js-filer direkt.
  Vägen är blueprint/artefaktfält → deterministisk render.
- Ingen parallell engine och ingen egen begreppsmodell bredvid
  Project Input / Site Brief / Site Plan / Generation Package.
- **Ingen ny canonical artefakt.** `OpenClawDecision` är ett transient objekt
  (Pydantic), exakt som `RouterDecision` och `AssembledContext` — det
  persisteras aldrig som egen fil. (Skulle det någonsin sparas som canonical
  fil eller bli ett runtime-kontrakt krävs ADR, se `04` §4.)
- **Ingen suddig gräns** mellan svar, plan, patch och build. Varje
  OpenClaw-handling är exakt en av de fyra V0-handlingarna ovan.

## Kontraktet: `OpenClawDecision` (transient)

OpenClaw Core komponerar de befintliga typerna — den uppfinner inga nya enums:

```jsonc
{
  // 1. Vad meddelandet är (oförändrat från kor-6a, packages/.../router/models.py)
  "router": { /* RouterDecision: messageKind, editKind, buildRequirement,
                 contextLevel, target, subtasks, reference, requiresClarification … */ },

  // 2. Vad som lästes för att förstå (oförändrat från kor-7a, .../context/models.py)
  "context": { /* AssembledContext: contextLevel, payload, charCount, charBudget,
                  suppressed, dropped, permissionRequired/Granted, notes */ },

  // 3. OpenClaw Cores faktiska beslut (det enda nya — och transient)
  "action": "answer_only | clarification | plan_only | patch_plan_request",
  "answer": "…",            // satt bara för answer_only / component-discovery-svar
  "clarifyingQuestion": "…",// satt bara för clarification
  "plan": ["steg 1", "…"],  // satt bara för plan_only / reference
  "patchPlanRequest": {      // satt bara för edit_instruction i V0:
    "targetSummary": "contentBlocks.home.<section>.<field>",
    "status": "patch_planner_missing",   // ärligt: kor-7b finns inte än
    "blockedBy": "kor-7b"
  },
  "toolCalls": [             // FÖRESLAGNA verktyg — aldrig auto-körda i V0:
    { "name": "propose_patch_plan", "args": {},
      "requiresApproval": true, "reason": "…" }
  ],
  "capability": null,        // satt för capability_request (t.ex. "three_3d_scene")
  "appliedVisibleEffect": false,  // V0 ändrar aldrig något → alltid false
  "rationale": "…"                // kort, för trace/observability
}
```

`action` är kärnan i det nya. `toolCalls` och `capability` är **destillerade från
coachens `openclaw-mvp/`-spike**: `toolCalls` är FÖRESLAGNA verktyg som alltid kräver
godkännande (`requiresApproval:true`) och aldrig körs av V0 själv; `capability` sätts
för en `capability_request` (t.ex. `three_3d_scene`) som ska gå via dependency-policy +
recept, **inte** fri kodpatch. `OpenClawAction` är en **sluten enum**: `answer_only`,
`clarification`, `plan_only`, `patch_plan_request`.

**En router-sanning.** Klassningen (`messageKind`/`editKind`/`contextLevel`) ägs av
`kor-6a` (`packages/generation/orchestration/router/`) — den är schemalåst och testad.
`openclaw-mvp/` har just nu en egen regex-router för att kunna köras fristående; det är
OK som spike, men den får inte bli en andra permanent klassificerare. Vid integration
ska MVP:n **delegera** klassningen till `kor-6a` (importera paketet eller via en tunn
endpoint), inte underhålla en divergerande kopia.

## Tool-ytan (vad OpenClaw Core V0 får anropa)

V0 har en **liten, read-only** verktygslåda. Inga skriv-/build-verktyg finns i V0.

| Verktyg | Källa | Får göra | Får aldrig |
|---------|-------|----------|------------|
| `classify_message(message, ctx)` | `kor-6a` `router/` | klassa meddelandet → `RouterDecision` | starta build på ren fråga |
| `assemble_context(level, …)` | `kor-7a` `context/` | hämta exakt den `contextLevel` routern satte, inom budget | skriva, bygga, boota preview |
| `decide(router, context)` | **nytt, V0** | välja `OpenClawAction` + formulera svar/plan/fråga | applicera patch, skriva fil, bygga |

Tillägg **senare** (Nivå 2, efter `kor-7b`/`kor-7c`): `plan_patches` (dry-run,
`kor-7b`) och `apply_patch → ny version` (`kor-7c`). V0 stannar **före** dem och
returnerar i stället `patch_plan_request{status:"patch_planner_missing"}` på en
ändringsorder — ärligt, inte en falsk success.

## Capability-plan (meddelande → kontext → handling, V0)

| `messageKind` (kor-6a) | `contextLevel` (kor-7a) | OpenClaw V0-handling |
|------------------------|--------------------------|-----------------------|
| `answer_only` | `none` | `answer_only` |
| `component_discovery` | `component_registry` | `answer_only` (lista tillgängliga val) |
| `reference_analysis` | `external_reference` (gated) | `plan_only` (föreslå egen variant, kopiera aldrig) |
| `site_review` | `artifacts` / `artifacts_plus_sections` / `preview_dom` | `answer_only` eller `plan_only` |
| `edit_instruction` | `artifacts_plus_sections` | `patch_plan_request` (V0: planner saknas → ärlig flagga) |
| `edit_instruction` + `capability_request` (t.ex. three.js) | `component_registry` + `artifacts_plus_sections` | `plan_only` + föreslagen `check_dependency_policy` (kräver godkännande) |
| `bug_report` | `manifest` / `selected_files` | `plan_only` |
| `multi_intent` | per subtask (kor-6a `subtasks[]`) | en handling per subtask, aggregerad |
| `unclear` | `none` | `clarification` |

Routern äger redan `shouldStartPreview` och tvingar den `False` vid aktiv
användarsession (coexistence, `02` §8) — OpenClaw V0 respekterar det och kan
ändå aldrig starta build.

## De tre nivåerna (sekvens, från `open_claw.txt`)

1. **Nivå 1 — OpenClaw Core i repot (detta kontrakt).** Modul, inte deploy.
   Kopplar `classify_message` → `assemble_context` → `decide`. Får inte patcha
   filer. **Read-only → kan byggas (som `kor-o2`) NÄR SOM HELST, även före `kor-7b`/`7c`.**
2. **Nivå 2 — OpenClaw Patch Flow.** Efter `kor-7b` (patch planner) + `kor-7c`
   (apply/version): följdprompt → router → context → patch plan → artefakt-patch
   → ny version → build/preview. Här börjar "ändra lite text" funka på riktigt
   (stänger `B155`).
3. **Nivå 3 — Hostad OpenClaw-worker (t.ex. Render).** Först när patch
   planner/apply finns + auth/operator-gate + rate-limit/kostnadsskydd +
   trace/loggning + rollback/versionering + bara Sajtbyggarens tools (ingen fri
   filesystem-rätt). Render = driftplats, inte arkitektur.

## Destillera från gamla Sajtmaskin/OpenClaw — importera inte

| Ta med (destillera) | Lämna kvar (importera inte) |
|---------------------|------------------------------|
| kontextnivåer (lätt / manifest / relevanta filer / full) — redan i `kor-7a` | fri filpatch som första strategi |
| förmågan att se buggar/inkonsistenser | egen parallell generator |
| tydliga tool calls | egen begreppsmodell bredvid Brief/Plan/Generation Package |
| skilja fråga från ändringsorder — redan i `kor-6a` | suddig gräns mellan svar/plan/patch/build |
| läsa aktuell version + historik | — |
| självgranskning innan ändring | — |

## Var koden hamnar (öppet placeringsbeslut)

Två kandidater, och det är ett **mappgräns-/arkitekturbeslut (ADR-värt, `04` §4)**:
- **(a) In-repo modul:** `packages/generation/orchestration/openclaw/` (`models.py`
  för `OpenClawDecision`/`OpenClawAction`, `core.py` för `decide(...)`). Återanvänder
  `router/` + `context/`. Ingen ny mappgräns utanför `orchestration/`.
- **(b) Fristående service:** coachens `openclaw-mvp/` (FastAPI, `/v1/chat` m.m.).
  Bra för standalone dry-run + Render/Vercel senare. Risk: andra Python-service +
  ny mappgräns i monorepot.

Rekommendation: bygg **(a)** som sanning för logiken; låt **(b)** bli ett tunt
transportlager ovanpå (a) om/när en HTTP-yta behövs. `openclaw-mvp/` hålls
ocommittad/lokal tills beslutet är taget (ingen mappgräns låses i förväg).

## Definition of done (för detta designkort)

- `OpenClawDecision`-formen, `OpenClawAction`-enumen, tool-ytan och
  capability-planen är dokumenterade (ovan).
- Nivåsekvensen + Sajtmaskin-destillatet är dokumenterade.
- **Ingen runtime-kod ändrad**, ingen canonical artefakt skapad, ingen ADR
  krävd (transient objekt).
- Slottar in i `README.md`-sekvensen som en **påbyggnad** (LLM/orchestration
  ovanpå grön bas).
- Detta är ett **designkort**, inte en nuläges-handoff. Aktuellt läge / öppna PR:er /
  nästa steg för en ny orchestrator lever i `handoff-orchestration.md` +
  `docs/current-focus.md` — peka dit, duplicera inte hit.

## Prompt till builder-agenten (för den senare V0-implementationen, ~`kor-o2`)

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR O2 - implementera OpenClaw Core V0 enligt kontraktet i
docs/heavy-llm-flow/kor-o1-openclaw-core-contract.md.

Krav:
- Komponera RouterDecision (kor-6a) + AssembledContext (kor-7a) till en transient
  OpenClawDecision. INGEN ny canonical artefakt, INGEN sparad fil.
- Handlingar i V0: answer_only / clarification / plan_only / patch_plan_request.
  V0 bygger ALDRIG, skriver ALDRIG fil, startar ALDRIG preview.
- En edit_instruction i V0 ger patch_plan_request{status:"patch_planner_missing"}
  tills kor-7b finns - arligt, ingen falsk success.
- Mock-safe (ingen OPENAI_API_KEY behovs; deterministiskt over router+context).

Definition of done: capability-planens rader (answer/clarify/plan/patch_plan_request)
testas, V0 skriver/bygger ingenting (verifierat), ruff + openclaw-pytest grona.
```
