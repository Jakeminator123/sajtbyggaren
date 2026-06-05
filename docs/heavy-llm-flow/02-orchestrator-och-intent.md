# 02 — Orchestrator och intent (OpenClaw)

Referensdokument. Beskriver routern ovanpå init/follow-up: hur ett användarmeddelande
klassas, hur mycket kontext som hämtas, om build ska startas, och vad agenten returnerar.

> **Namn:** I sajtmaskin var **OpenClaw** en extern gateway-agent och **Sajtagenten**
> dess svenska UX-namn — och den låg som **sidecar bredvid** codegen, inte som
> orchestrator. I Sajtbyggaren vill vi ge samma kontextförmåga en **given plats som
> router ovanpå** pipelinen. Tills termen är registrerad i `naming-dictionary.v1.json`
> kallar vi den **OpenClaw Router** i dessa docs. Den ersätter inte pipelinen — den
> väljer hur den ska användas.

---

## 1. Problemet routern löser

Dagens follow-up är säker men primitiv: intent är deterministisk, whitelist-baserad
(`clarify`, `no-semantic-change`, `tone-shift`, `tagline-update`, `story-emphasize`,
`positioning-shift`) och okända prompter blir konservativa. Den kan inte skilja på:

> "vad är klockan" · "lägg en klocka i andra sektionen till vänster" · "vilka klockor
> finns?" · "samma klocka som på aftonbladet.se" · "gör sidan mer premium och lägg en
> klocka men ändra inte texterna"

Alla dessa behöver **olika** beteende. Idag riskerar de alla att tolkas som site-edit
→ kör build → starta adapter → uppdatera iframe. Det är fel.

---

## 2. Två ortogonala klassningar

Lärdom från sajtmaskin: håll **en** tydlig intent-yta (de hade två överlappande
klassificerare + en halv-wirad taxonomi → brus). Vi använder **två ortogonala** fält
som båda konsumeras hela vägen:

### 2.1 `messageKind` — vad är detta för meddelande?

```ts
type MessageKind =
  | "answer_only"          // ren fråga, inget med sajten att göra
  | "site_review"          // "vad tycker du om sidan?"
  | "edit_instruction"     // faktisk ändring
  | "component_discovery"  // "vilka X finns att tillgå?"
  | "reference_analysis"   // "som på www.exempel.se"
  | "bug_report"           // "knappen funkar inte"
  | "multi_intent"         // flera deluppgifter + constraints
  | "unclear";             // be om förtydligande
```

### 2.2 `buildRequirement` — hur mycket måste systemet göra?

```ts
type BuildRequirement =
  | "none"                 // svara bara
  | "plan_only"            // visa förslag/plan, ingen build
  | "artifact_patch_only"  // patcha blueprint-fält, ingen full build
  | "targeted_rebuild"     // bygg om bara påverkad route/section
  | "full_rebuild";        // hela sajten (sällan)
```

Plus stödfält:

```ts
type ContextLevel =
  | "none" | "project_dna" | "artifacts" | "artifacts_plus_sections"
  | "manifest" | "selected_files" | "preview_dom" | "external_reference"
  | "component_registry";

type EditKind =
  | "component_add" | "component_remove" | "visual_style"
  | "copy_change" | "layout_change" | "route_add" | "none";
```

> Detta avlöser dagens enkla follow-up-intent — den lever kvar som **delsignal** för
> copy/positionering, men `messageKind` + `buildRequirement` är det nya yttre beslutet.

---

## 3. Klock-exemplen som testfall

Dessa är acceptanskriterier för `kor-6a` (routern). De ska bli regressionstester.

### A — "vad är klockan?"

```json
{ "messageKind": "answer_only", "buildRequirement": "none",
  "contextLevel": "none", "actions": [], "shouldStartPreview": false }
```

Ingen patch, ingen preview, ingen adapter. Svar: tiden (ev. via tool).

### B — "jag vill ha en klocka på andra sektionen till vänster"

```json
{ "messageKind": "edit_instruction", "editKind": "component_add",
  "target": { "routeId": "home", "sectionOrdinal": 2, "position": "left" },
  "componentIntent": "clock_widget",
  "buildRequirement": "targeted_rebuild",
  "contextLevel": "artifacts_plus_sections" }
```

Routern: läs Site Plan → mappa "andra sektionen" till faktiskt `sectionId` → kolla om
capability/komponent finns → om inte, föreslå soft dossier eller inline-komponent →
patch-plan → bygg om bara den routen → uppdatera preview. **Inte** "släck ner allt".

### C — "vilka klockor finns att tillgå?"

```json
{ "messageKind": "component_discovery", "editKind": "none",
  "buildRequirement": "none", "contextLevel": "component_registry" }
```

Svar listar alternativ (digital, öppettider-status, countdown, flera kontor, analog)
och frågar om placering. **Ingen build förrän användaren väljer.**

### D — "samma klocka som på aftonbladet.se"

```json
{ "messageKind": "reference_analysis", "editKind": "component_add",
  "reference": { "url": "aftonbladet.se", "object": "clock" },
  "buildRequirement": "plan_only", "contextLevel": "external_reference",
  "risk": "do_not_copy_exact_design_or_code" }
```

Routern: hämta/analysera referens (tool om tillåtet) → beskriv vad som menas → skapa
**egen** inspirerad variant → fråga om placering → patcha först därefter. Kopiera
**aldrig** exakt design/kod.

### E — "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna"

```json
{ "messageKind": "multi_intent", "buildRequirement": "targeted_rebuild",
  "subtasks": [
    { "editKind": "visual_style", "scope": "global", "instruction": "more premium" },
    { "editKind": "component_add", "component": "clock", "target": "home.section[2].left" },
    { "constraint": "preserve_copy" }
  ] }
```

Multi-intent: dela upp i deluppgifter, bevara constraints (`preserve_copy`), kör
patchar i rätt ordning. Detta är där routern blir game changer.

---

## 4. Kontext-assembler (lagom kontext per fråga)

Sajtmaskins starkaste OpenClaw-idé: hämta **lagom** mycket kontext beroende på frågan,
med hårda budgetar (de hade tiers `none`/`light`/`manifest`/`full`, full upp till 180k
tecken — vi sätter snålare tak). Mappning till våra artefakter:

| `contextLevel` | Hämtar | Källa |
|----------------|--------|-------|
| `none` | inget | — |
| `project_dna` | siteId/projectId/version, scaffold/variant | `data/prompt-inputs/<siteId>.meta.json` |
| `artifacts` | brief/plan/package | `data/runs/<runId>/*.json` |
| `artifacts_plus_sections` | + route/section-map | Site Plan `routePlan` + scaffold `sections.json` |
| `component_registry` | tillgängliga capabilities/dossiers | `capability-map.v1.json` + dossier-manifests |
| `manifest` | fil-lista | `generated-files/` listing |
| `selected_files` | utvalda filer | `generated-files/<path>` |
| `preview_dom` | render-snapshot | preview (vercel-sandbox) |
| `external_reference` | extern URL-analys | tool call |

Budget-regel: varje nivå har ett tecken-tak; suppress filer som redan är kända i
föregående version (sajtmaskins anti-bloat-trick).

---

## 5. Tool-yta (OpenClaw = LLM + verktyg + hårda kontrakt + trace)

Routern ska inte vara "en LLM som kan allt". Den ska vara en LLM med **read-tunga**
verktyg och **få, validerade** write-verktyg. Föreslagen yta (mappar mot befintliga
moduler):

```text
readCurrentProject()              data/prompt-inputs/<siteId>.meta.json
readRunArtifacts(runId)           data/runs/<runId>/*
readProjectInput(siteId, ver?)    data/prompt-inputs/<siteId>.v<N>.project-input.json
readSiteBrief / readSitePlan / readGenerationPackage(runId)
listRoutesAndSections(siteId)     Site Plan + scaffold sections.json
listAvailableScaffolds()          load_scaffold_registry()
listAvailableVariants(scaffoldId) scaffolds/<id>/variants/
listAvailableCapabilities()       capability-map.v1.json
listAvailableDossiers(capability?) dossiers/{soft,hard}/
readFileManifest(runId)           generated-files/ listing
readRelevantFiles(paths)          generated-files/<path>
inspectPreview(route?, selector?) preview-runtime
fetchReferenceUrl(url)            extern (tillåtelse-gate)
-- write (validerade) --
proposeArtifactPatch(plan)        patch-plan mot brief/plan/package/PI
validatePatch(patch)              schema + rails
runQualityGate(scope)             packages/generation/quality_gate
runTargetedBuild(scope)           build_site.py (avgränsad)
startPreviewIfNeeded()            PreviewRuntime
```

**Varje tool-call ska hamna i `trace.ndjson`** (eller motsvarande) så man i efterhand
kan se: varför ändrades detta, vilken kontext lästes, varför startades (inte) build,
vilka filer/artefakter påverkades.

---

## 6. Strukturerad output (inte bara text)

Varje svar producerar ett **beslut**, inte bara prosa:

```jsonc
{
  "messageKind": "edit_instruction",
  "editKind": "component_add",
  "buildRequirement": "targeted_rebuild",
  "contextLevel": "artifacts_plus_sections",
  "target": { "routeId": "home", "sectionId": "service-summary", "position": "left" },
  "actions": [
    { "type": "artifact_patch", "artifact": "generation-package.json",
      "field": "contentBlocks.home.service-summary.accessoryComponent",
      "value": { "component": "clock-widget", "variant": "minimal-digital" } }
  ],
  "requiresUserConfirmation": false,
  "shouldStartPreview": true,
  "rationale": "Anvandaren bad om en synlig komponent i nuvarande sida."
}
```

För "vad är klockan": `buildRequirement: none`, `actions: []`,
`shouldStartPreview: false`. Det är detta som gör chatten smart på riktigt.

---

## 7. Faser (hur routern byggs utan att röra renderern)

| Fas | Vad | Kördokument |
|-----|-----|-------------|
| 1 | Router-klassificering deterministisk (inga filändringar, ingen build på rena frågor). Klock-exemplen gröna. | `kor-6a` |
| 1b | LLM-fallback för tvetydiga meddelanden | `kor-6b` |
| 2 | Context Assembler (hämta rätt nivå) | `kor-7a` |
| 3 | Artifact Patch Planner (dry-run → apply, ingen fri kodpatch) | `kor-7b` → `kor-7c` |
| 4 | Targeted rebuild (bara påverkad route/section) | `kor-7d` |
| 5 | (senare) Sajtagent i Viewser-UI + tool calls | egen skiva, koordineras med UI-lane |

Fas 1 kan byggas helt utan att röra `build_site.py`. Den låser upp resten.

---

## 8. Koppling till `builder-coexistence`-regeln

OpenClaw-routern och dess tool calls får **inte** öppna en live builder-/preview-session
mot samma `chatId`/`siteId` som användaren aktivt genererar i (race på version-raden,
felaktig "Fel"-badge, spridd preview-heartbeat). Routern arbetar mot **artefakter på
disk** och egna run-id:n. Build/preview-tools startas bara när `buildRequirement`
kräver det och aldrig parallellt med en användarsession på samma site.
