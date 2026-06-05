# 03 — Preview, data och versioner

Referensdokument. Hur den genererade sajten visas i realtid, hur användardata lagras,
och hur växling mellan versioner sker när nya prompter kommer.

> **Status (verifiera mot branchen före bygge):** Detta lager är **beslutad mål- och
> integrationsriktning**. Delar är byggda/live-verifierade (vercel-sandbox-spike,
> immutable builds + `current.json` på `jakob-be`), men en agent ska **kontrollera
> faktisk kodstatus** innan den bygger mot `current.json`/immutable-build-kontraktet.
> Det tunga LLM-flödet ska **respektera** dessa kontrakt, inte bygga om dem.
> `vercel-sandbox` är förstahandsval (ADR 0033).

> **Verifiera före `kor-7d` (targeted render):**
> - Finns `packages/generation/build/immutable_builds.py` (`write_active_pointer`/
>   `read_active_build_dir`) faktiskt i koden?
> - Skriver buildern `current.json` med atomär swap på `ok`/`degraded`?
> - **Om något saknas:** `kor-7d` är **blockerad** tills Windows-safe-rebuild-pipelinen
>   landat (se `workboard.json`-gap). Bygg inte ett eget pointer-/build-system.

> **Känd drift att dubbelkolla:** `governance/policies/preview-runtime-policy.v1.json`
> kan fortfarande säga StackBlitz som default medan ADR 0033 + produktkompassen säger
> `vercel-sandbox` primär / StackBlitz pausad. Lita på ADR 0033 + koden, inte en ev.
> stale policy-rad.

---

## 1. Preview via adaptrar

Produktkoden pratar med abstraktionen `PreviewRuntime`; en adapter väljs med env
`VIEWSER_PREVIEW_MODE`.

| Kind | Adapter | Roll |
|------|---------|------|
| `vercel-sandbox` | `vercelSandboxRuntime` | **Förstahandsval** för användarnära preview: isolerad Vercel-microVM kör sajten, publik `…vercel.run`-URL som funkar i alla browsers |
| `local` (`local-next`) | `localRuntime` | Snabb intern dev + **garanterad fallback** (`next start` på host, port 4100–4199) |
| `stackblitz` | `stackblitzRuntime` | **Pausad** — embed bara i Chromium |
| `fly` | `flyRuntime` | Stub — framtida produktionslik fallback |

- Typer/registry: `packages/preview-runtime/src/{types,registry,adapters}.ts`
- Viewser-wiring: `apps/viewser/lib/preview-runtime-server.ts` (anropa
  `currentViewserRuntime()`, inte rå `currentRuntime()`)
- `@vercel/sandbox` finns **bara** i `apps/viewser/lib/vercel-sandbox-runner.ts` —
  aldrig i `packages/preview-runtime` eller `packages/generation` (portabilitet, ADR 0030).

> **Default i repo idag = `local-next`** tills operatören sätter
> `VIEWSER_PREVIEW_MODE=vercel-sandbox`. "Primärt val" (produktriktning) och "default i
> env" är två olika saker.

### Vercel Sandbox-körningen

`createSandboxPreview({ siteId, runId?, ttlMs? })` i `vercel-sandbox-runner.ts`:

1. Auth: `VERCEL_OIDC_TOKEN` (föredraget, ~12h via `vercel env pull`), annars
   `VERCEL_TOKEN` + `VERCEL_TEAM_ID` + `VERCEL_PROJECT_ID`. Filen
   `apps/viewser/.env.vercel.local` laddas vid behov.
2. Källa: `resolveSourceDir(siteId)` → den **aktiva** builden via `current.json` →
   `<siteRoot>/builds/<activeBuildId>/`.
3. Upload: alla filer utom `node_modules`/`.next`/`.git`/`.env*` (cap 4000 filer/64 MB).
4. Boot: `npm install` → `npx next build` → detached `npx next start -p 3000`.
5. URL: `sandbox.domain(3000)` (publik HTTPS). Ready-poll upp till ~150s.
6. Session: `recordSandboxSession(siteId, sandboxId, url)` (in-memory per Viewser-process).

Sessions stoppas före ny build (`build-runner.ts`) och före ny sandbox för samma site.

---

## 2. Datamodell (ingen användare/auth ännu)

Identitet är **`siteId` + `projectId` + heltals-`version`** — **inte** konton. Auth är
parkerad (produktkompassen). `apps/viewser/lib/localhost-guard.ts`: "no auth and no
rate limit".

| Plats | Innehåll |
|-------|----------|
| `data/prompt-inputs/` | Project Input-snapshots + meta (versionssanning) |
| `data/runs/<runId>/` | Engine Run-artefakter per körning |
| `../sajtbyggaren-output/.generated/<siteId>/` | Genererade Next.js-sajter (immutable builds) |

### Två pekare, två betydelser (förväxla inte)

```text
data/prompt-inputs/<siteId>.meta.json    -> vilken Project Input-VERSION ar "senaste" for follow-up
.generated/<siteId>/current.json         -> vilken BYGGD Next-app preview serverar
```

`current.json`:

```json
{ "activeBuildId": "20260602T192207Z",
  "buildPath": "builds/20260602T192207Z",
  "updatedAt": "<ISO-8601 UTC>" }
```

Immutabla builds + atomär pekar-swap: `packages/generation/build/immutable_builds.py`
(`new_build_id`, `build_dir_for`, `write_active_pointer`, `read_active_build_dir`).
Pekaren flyttas **bara** på shippable build (`ok`/`degraded`); `failed`/`skipped`
lämnar förra aktiva build serverande.

### Project Input-snapshots

```text
data/prompt-inputs/
  <siteId>.v<N>.project-input.json     (immutabel per version)
  <siteId>.v<N>.meta.json
  <siteId>.project-input.json          (rullande "senaste")
  <siteId>.meta.json                   { projectId, siteId, version, originalPrompt, briefSource, ... }
```

---

## 3. Versionsväxling när nya prompter kommer

### Follow-up bevarar identitet

| Fält | Init | Follow-up |
|------|------|-----------|
| `siteId` | ny slug från prompt | **samma** |
| `projectId` | ny UUID | **återanvänds** från meta |
| `version` | 1 | **inkrementeras** |
| `runId` | ny per build | ny per build |
| `scaffoldId` / `variantId` | väljs | **fryses** (`merged[...] = previous[...]`) |

### Flödet prompt → ny version → ny preview

```text
FloatingChat / PromptBuilder
  -> POST /api/prompt { prompt, mode:"followup", siteId, baseRunId? }
  -> Fas 1: scripts/prompt_to_project_input.py   (ny v<N+1> snapshot, fryser scaffold/variant)
  -> Fas 2: scripts/build_site.py --dossier <path>  (stoppar gammal preview, bygger ny build)
  -> pa ok/degraded: write_active_pointer -> current.json byter activeBuildId
  -> svar { runId, siteId, projectId, version, buildStatus, buildResult, appliedCopyDirectives }
  -> page.tsx handleBuildDone valjer nya runId
  -> ViewerPanel useEffect [runId, siteId] -> POST /api/preview/<siteId> -> ny sandbox-URL -> iframe byts
```

### Iterera från en **historisk** version

Versions-tabben sätter `pendingBaseRunId` → nästa `/api/prompt` skickar `baseRunId` →
Python läser `data/runs/<baseRunId>/input.json` (version N) → mergar till N+1. Så
operatören kan greppa tillbaka och förgrena från valfri tidigare version.

### Run history + växling

- `apps/viewser/lib/runs.ts` (`listRuns`, `readRunTrace`, `readAppliedCopyDirectives`)
- `apps/viewser/components/run-history.tsx` → klick → `onSelect(runId)`
- Preview följer vald runs `siteId` och serverar **aktiv** `current.json`-build.

### Avbrutna runs (känd robusthet att förbättra)

En run vars `build-result.json` saknas (hård kill mitt i bygget) fastnar `pending`
(grå) för evigt; `current.json` promotas inte → preview visar gammal version. Detta är
en **öppen robusthetsbugg** (se handoff), inte en del av det tunga LLM-flödet — men det
tunga flödet får inte göra den värre. Builder-kontraktet: `build-result.json` ska
**alltid** skrivas (även vid fel).

---

## 4. Vad det tunga LLM-flödet måste respektera

- **Ändra inte adaptrarna eller `current.json`-kontraktet** i blueprint-/codegen-/
  router-skivorna. Targeted rebuild (`kor-7d`) producerar fortfarande en normal build +
  pekar-swap.
- **Generated output förblir vanlig Next.js.** Sandbox kör bara en ephemeral kopia;
  Sajtbyggaren äger projekt/versioner (`data/runs`, `data/prompt-inputs`).
- **En följdprompt = en ny version, inte en ny sajt.** Bevara `projectId`/`siteId` och
  frys scaffold/variant (utom vid `clear-redesign`-motsvarighet, som är ett uttryckligt
  framtida beslut).
- **Preview startas inte i onödan.** Routern (`kor-6a`) sätter `shouldStartPreview`/
  `buildRequirement`; `answer_only`/`plan_only` startar varken build eller adapter.
- **Coexistence:** kör aldrig agent-build/-preview mot en `siteId` som operatören har
  öppen i en live-session (se `builder-coexistence`-regeln).

---

## 5. Relevanta env-variabler

| Variabel | Effekt |
|----------|--------|
| `VIEWSER_PREVIEW_MODE` | adapter: `local-next` / `vercel-sandbox` / `stackblitz` / `fly` / `auto` |
| `VERCEL_OIDC_TOKEN` (+ `.env.vercel.local`) | sandbox-auth (~12h TTL) |
| `SAJTBYGGAREN_GENERATED_DIR` | rot för `.generated` |
| `VIEWSER_RUNS_DIR` | rot för run-artefakter |
| `OPENAI_API_KEY` | riktig brief/plan i Python (annars mock) |

> Operatörsgrant (2026-06-02): agenten får läsa/ändra alla `.env*` i repo-rot och
> `apps/viewser/` som del av builder-/preview-arbete. Skriv aldrig ut secrets;
> committa aldrig `.env*`.
