# GAP-windows-safe-rebuild-pipeline

> **status: superseded (lane A, 2026-06).** Gapets scope — nivå 4: immutable
> `builds/<buildId>/` + atomär `current.json`-pointer-swap — är landat
> (`packages/generation/build/immutable_builds.py`, `scripts/gc_old_builds.py`,
> + flat-layout-städning + POSIX-tree-kill). Nivå 5 (`vercel-preview`-adapter,
> "ny version"-banner) är uttryckligen framtida arbete utanför detta gap.
> Arkiverat (frontmatter-statusen nedan är ögonblicksbilden vid skapandet;
> auktoritativ lifecycle = `docs/workboard.json`). Se `docs/gaps/archive/README.md`.

```yaml
id: GAP-windows-safe-rebuild-pipeline
type: Gap/Backend
owner: jakob
title: Windows-safe rebuild pipeline (immutable build-dir + pointer-swap)
status: queued
source: extern reviewer-analys 2026-05-27 efm
relatedBugs: [B157]
relatedArchitecture: [ADR 0028 Runtime Ladder, ADR 0030 Preview-Provider Portability]
```

## Sammanfattning

Builder-pipelinen rebuildar samma `.generated/<siteId>/`-katalog som en
live `next dev`/`next start`-process håller låst. På Windows hamnar
native binaries (typiskt `next-swc.win32-x64-msvc.node` i
`node_modules/@next/swc-win32-x64-msvc/`) i `WinError 5 — Åtkomst
nekad` när `build_site.py:copy_starter()` försöker `shutil.rmtree`
dem. Symptomatik registrerad som `B157`.

Den här gap-spec:en täcker arkitektur-fixen, inte symptom-läkningen.

## Implementationsstatus (2026-06-05)

Nivå 4-kärnan är landad: immutable `builds/<buildId>/` + atomär
`current.json`-pekarbyte (Stage A,
`packages/generation/build/immutable_builds.py` + `scripts/build_site.py`)
och fördröjd garbage collection (Stage B, `scripts/gc_old_builds.py`).

De två kvarvarande icke-blockerande städpunkterna är nu också klara:

- **flat-layout-städning** — efter att `current.json` swappats till en ny
  immutable build städar `scripts/build_site.py:cleanup_flat_layout` bort
  legacy flat-layout-artefakter (`.next`, `node_modules`, `app`, ...) som
  ligger kvar direkt i sajt-roten från tiden före immutable builds. Best
  effort: en låst artefakt hoppas över utan att fälla bygget. Gateas på
  pekarbytet så preview aldrig tappar sin flat-`.next`-fallback innan
  pekaren är live.
- **POSIX-tree-kill i build-runner** — `apps/viewser/lib/build-runner.ts`
  spawnar numera `build_site.py` detached i egen process-grupp och dödar
  vid timeout hela trädet (python → npm → next) via
  `process.kill(-pid)` (killpg) på POSIX, `taskkill /T /F` på Windows.
  Stänger den descendant-läcka som den delade `killProcessTree`-helpern
  bara löste på Windows.

Resterande punkter (nivå 5 `vercel-preview`-adapter, UI-banner för "ny
version tillgänglig") är fortsatt framtida arbete, se off-limits nedan.

## Reproduktion

1. Operatören öppnar Viewser, kör prompt → first build skapar
   `.generated/<siteId>/`. Preview-iframe spawnar `next dev` mot den
   katalogen → låser native binaries under `node_modules`.
2. Operatören skriver en följdprompt → `/api/prompt` spawnar
   `build_site.py` mot samma `siteId` → `copy_starter()` kallas.
3. Om `data/starters/<starter>/package-lock.json` har drivit relativt
   `.generated/<siteId>/package-lock.json` (vilket händer efter
   `next`-version-bumpar eller dep-uppdateringar i starter), så
   returnerar `_npm_install_inputs_changed=True` →
   `preserved=set()` (rad 720 i `build_site.py`).
4. Loopen rad 722-728 raderar då alla dirs i target inklusive
   `node_modules` → `shutil.rmtree(node_modules)` →
   `PermissionError: [WinError 5]` på den första `.node`-binaryn som
   Next-processen har laddat.
5. `/api/prompt` returnerar 500. Operatören ser bara
   "build failed" — den verkliga orsaken är låsning, inte logik.

Empiriskt observerat 2026-05-27 efm efter
`commerce-base/package-lock.json`-bumpen `next 16.2.5 → 16.2.6` som
följde med post-PR-#131-batchen.

## Varför detta är ett arkitekturproblem, inte en bugg

Det är inte `rmtree` som är fel. Det är att builder-pipelinen
**bygger ovanpå aktiv preview-output-katalog**. Pipelinen antar att
hen är den enda processen som rör `.generated/<siteId>/`, men
preview-runtime (per ADR 0028 nivå 1: `LocalRuntime`) håller exakt
samma katalog öppen för `next dev`/`next start`.

På Linux/macOS skulle aggressive delete oftast lyckas eftersom
filesystems där tillåter unlink av öppna filer (inode-räknaren håller
filen tills sista handle stänger). På Windows är låsningen hård
särskilt för native `.node`-binaries (DLL-liknande). Det här är
varför buggen är "rätt Windows-specifik" men anti-patternet är
arkitektoniskt — fel på båda OS.

Modell ADR 0030 redan etablerar är "Vercel som adapter". I Vercels
egen modell är varje deployment immutable och får egen unique URL.
Aktiv preview byts via pointer-swap när nya builden lyckas. Det är
arkitektur-mallen vi vill efterlikna lokalt.

## Fix-strategi (laddrar)

| Nivå | Fix | Effekt | Sprint |
| ---- | --- | ------ | ------ |
| 1. Akut | Stoppa `next dev`/`next start`-process före `copy_starter()` | 50-70 % | < 2h |
| 2. Snabbfix | retry/backoff runt `rmtree()` (50ms-1s, max 5 retries) | 30-60 % | < 1h |
| 3. Bättre | `rename` till `.trash`-suffix + delayed GC (städjobb) | 70-85 % | 4-6h |
| 4. Rätt | Ny `builds/<timestamp>/`-katalog per follow-up + manifest-pointer-swap | 90-95 % | 12-16h |
| 5. Vercel-likt | Varje följdprompt = ny immutable deployment + unique URL | 95 %+ | 24-32h (kräver också `vercel-preview`-adapter, se ADR 0030 + naming-dict v18) |

**GC** = garbage collection. Städjobb som tar bort gamla mappar
senare när de inte längre används.

**Pointer-swap** = pekarbyte. UI byter från gammal build till ny
build först när nya builden är klar.

### Rekommenderad väg

Nivå 4 är **rätt** sprintmål. Nivåerna 1-2 är temporära fixar att
överväga om buggen blockerar operatörens iteration omedelbart.
Nivåerna 5 är framtida arbete som hör hemma efter `vercel-preview`-
adapter (ADR 0030 §"Vad ADR 0030 INTE beslutar" + naming-dict v18).

### Vad nivå 4 konkret innebär

```text
~/sajtbyggaren-output/.generated/
  tjansteforetag-i-hornsga-3cb216/
    builds/
      20260527T151931Z/          ← immutable build #1
        app/
        node_modules/
        .next/
        package-lock.json
        ...
      20260527T152225Z/          ← immutable build #2
        ...
      20260527T153010Z/          ← immutable build #3 (latest)
        ...
    current.json                 ← pointer-fil: {"activeBuildId": "20260527T153010Z"}
```

`current.json` (pekfil) säger vilken build UI ska visa.

Följdprompten ska göra:

1. Skapa ny `builds/<timestamp>/`-dir.
2. Bygg där (kopiera starter, npm install om input changed, npm run
   build, etc.).
3. Om build lyckas: uppdatera `current.json` atomärt (write-tmp +
   rename).
4. Gammal build städas senare av delayed GC (t.ex. behåll N senaste
   + alla < 24h).

Aktiv `next start`-process kan fortsätta köra mot gammal build tills
den restartas mot ny `activeBuildId`. UI får då en "ny version
tillgänglig"-signal eller restartas automatiskt.

### Vad nivå 4 INTE löser

- Om operatören har två fönster öppna mot samma site simultanously
  och båda bygger samtidigt: per-siteId-mutex (existerande i
  `apps/viewser/lib/build-runner.ts`) räcker.
- Om `current.json`-pointer-swap misslyckas mitt i: atomär rename
  + rollback-logik krävs.
- Disk-utrymme — N gamla builds kvar tar utrymme. GC-policy
  (`keep latest 5` eller `keep all < 24h`) måste bestämmas.

## Påverkade filer (förväntad scope vid nivå 4-implementation)

| Fil | Ändring |
| --- | ------- |
| `scripts/build_site.py` | `copy_starter()` skriver till
`builds/<timestamp>/` istället för target. Ny helper
`write_active_pointer()`. |
| `apps/viewser/lib/local-preview-server.ts` | `resolveGeneratedDir()`
läser `current.json` för att hitta aktiv build. |
| `apps/viewser/lib/build-runner.ts` | Spawnar build mot ny dir;
uppdaterar pointer vid success. |
| `scripts/cleanup_dev_artifacts.py` eller ny `gc_old_builds.py` |
Delayed GC-jobb. |
| `data/runs/<runId>/build-result.json` | Lägga till `activeBuildId`. |
| `governance/policies/repo-boundaries.v1.json` | Eventuell uppdatering
om builds-strukturen är policy-relevant. |
| Tester: `tests/test_immutable_builds.py` (ny) | Verifiera
pointer-swap, GC, parallella builds. |

**Bedömning av blast radius:** medium-stor. `copy_starter()` är
canonical builder-yta. Pointer-swap-mekaniken är ny per-siteId-state
som flera callers måste lära sig. Cleanup-jobb kan köras separat
utan att blockera fix.

## Off-limits för denna sprint

- `apps/viewser/components/**` (Christophers lane). UI-byte (visa
  "ny version tillgänglig"-banner) är egen följdsprint.
- `packages/preview-runtime/` (PreviewRuntime Bite A/B/C). Adapter-
  gränsen rörs inte; bara `apps/viewser/lib/`-helpers ändras.
- `vercel-preview`-adapter — naming-dict v18 + egen ADR krävs (se ADR
  0030).

## Validering vid implementation

- Reproducera B157 lokalt (kör follow-up-prompt mot site med aktiv
  preview-process, ändra `package-lock.json` så
  `_npm_install_inputs_changed=True`).
- Verifiera att gamla preview fortsätter funka under bygget av nya.
- Verifiera att pointer-swap är atomär (kill -9 mid-swap leder inte
  till korrupt state).
- Verifiera disk-housekeeping (GC tar inte aktiv build).
- Verifiera concurrent builds mot olika siteIds (per-siteId-mutex
  intakt).

## Stop-villkor (när nivå 4 är fel val)

- Om operatör väljer att gå direkt till nivå 5 (`vercel-preview`-
  adapter): hoppa över nivå 4-implementation, designa nivå 5 enligt
  ADR 0030 + ny ADR för immutable-deployment-model.
- Om akut blocker: implementera nivå 1 eller 2 som temporary fix
  först, dokumentera tech-debt, sprinta nivå 4 senare.

## Referenser

- B157 — `docs/known-issues.md`.
- ADR 0028 — Runtime Ladder. Definierar `LocalRuntime` (nivå 1) som
  håller `node_modules` öppen.
- ADR 0030 — Preview-Provider Portability. Motiverar Vercel-likt
  pattern utan att binda till Vercel.
- ADR 0021 — StackBlitz preview payload-workarounds. Tidigare
  Windows-specifik fix-historik.
- `scripts/build_site.py:705-731` — `copy_starter()`-impl.
- `scripts/build_site.py:669-702` — `_npm_install_inputs_changed`-
  impl (trigger för buggen).
- `apps/viewser/lib/local-preview-server.ts:57-67` —
  `resolveGeneratedDir()`-impl (där pointer-swap behöver läsas).
- `apps/viewser/lib/build-runner.ts` — per-siteId-mutex (relevant
  för nivå 1-akut-fix).
- Reviewer-analys 2026-05-27 efm (operatör-vidarebefordrad).
