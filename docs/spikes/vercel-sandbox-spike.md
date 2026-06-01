# Spike: Vercel-sandbox-preview (flag-gated PoC)

> Status: spike / proof-of-concept. **INTE** en `PreviewRuntime`-adapter.
> Ägare: Builder-lane (jakob-be). Datum: 2026-06-01.
> Branch: `cursor/vercel-sandbox-spike` (PR mot `jakob-be`).
> Flagga: `VIEWSER_SANDBOX_SPIKE=1`. Default av.

Den här spiken svarar på en enda fråga:

> Vad är minsta sandbox som bevisar att vi kan skapa **och visa** en isolerad
> preview av en redan-genererad sajt, stabilt, länge nog att faktiskt öppna
> och bedöma (mobilkänsla, cold-start)?

Den bygger exakt det — inte mer. Ingen route-wiring, ingen
`PreviewRuntimeKind`-utökning, inget nytt domänbegrepp, ingen ny ADR. Allt
ligger bakom en feature-flagga och degraderar ärligt utan tokens. Promotion
till en riktig adapter är ett separat beslut (se "Go/No-go").

Relaterat: ADR 0030 (preview-provider-portability), `runtime-adapter-plan.md`
(prior skiss på `origin/cursor/preview-runtime-adapters`), skill `vercel-sandbox`.

---

## STEG 0 — verifierat API (`@vercel/sandbox` v2.0.2, 2026-06-01)

Verifierat mot officiella Vercel-docs (`https://vercel.com/docs/vercel-sandbox`,
SDK-referensen + npm-paketet) **innan** kod skrevs. Där prior skiss skilde sig
från docs följer vi docs.

### Auth — OIDC vs access-token

Två lägen, helpern stödjer båda:

| Läge | Hur | När |
| --- | --- | --- |
| OIDC (rekommenderat) | `VERCEL_OIDC_TOKEN` läses automatiskt av SDK:n. Lokalt: `vercel link` + `vercel env pull` (token utgår efter 12h). Auto på Vercel-hosting. | Default när Viewser någon gång hostas på Vercel, eller lokalt efter env-pull. |
| Access-token | Trion `VERCEL_TOKEN` + `VERCEL_TEAM_ID` + `VERCEL_PROJECT_ID` spreadas in i `Sandbox.create()`/`Sandbox.get()`. | Externa CI/CD eller maskiner utan OIDC. |

Saknas båda → helpern returnerar `status:"failed"` med pedagogisk text. Ingen krasch.

### Runtime — node24 / node22

Tillgängliga: `node26`, `node24` (default), `node22`, `python3.13`. Körs på
Amazon Linux 2023, användare `vercel-sandbox` med sudo. Spiken väljer `node24`
(matchar Viewser-stacken; Next 16 + React 19 vill ha modern Node).

### Publik URL från exponerad port — **skiljer sig från prior skiss**

- **Verifierat:** deklarera porten vid create: `Sandbox.create({ ports: [3000] })`
  (max 15 portar). Hämta sedan publik https-URL via `sandbox.domain(3000)`.
  URL-formatet är leverantörens (t.ex. `https://<subdomän>.vercel.run`) och ska
  **inte** parsas/hårdkodas (ADR 0030 Regel 2 — läck inte URL-format genom
  abstraktionen). `domain()` kastar om porten inte registrerades vid create.
- **Prior skiss (FEL):** antog en `--publish-port 3000`-flagga på `npm start`
  som auto-genererar `https://sb-<id>.vercel.app`. Den flaggan finns inte i
  v2-API:t. Vi följer docs: `ports`-array + `domain(port)`.

### TTL + cleanup/stop

- TTL sätts vid create: `timeout` i ms. Default 5 min. **Max 45 min på Hobby,
  5 h på Pro/Enterprise.** `sandbox.extendTimeout(ms)` förlänger en levande
  session. Vid timeout stoppas sandboxen automatiskt.
- Spiken sätter default 15 min (klampas till intervallet 5–45 min, styrbart via
  `VIEWSER_SANDBOX_SPIKE_TTL_MS`). Det är medvetet längre än default 5 min så
  URL:en hinner öppnas på mobil + bedömas, men under Hobby-taket.
- Stopp: `sandbox.stop()` avslutar sessionen och returnerar slutstatus. CPU- och
  nätverkssiffror populeras på instans-accessorerna (`sandbox.activeCpuUsageMs`,
  `sandbox.networkTransfer`) **efter** stopp → används som kostnadssignal.
- Reconnect för separat cleanup: `Sandbox.get({ name })`. **Kontrakts-not:** i
  v2 är `name` den hållbara handeln (v1:s `sandboxId` backfillas som `name`).
  Spiken sätter ett deterministiskt `name` vid create och exponerar det som
  `sandboxId` i resultatet — cleanup-entryn tar emot detta värde.
- Persistens: persistent sandbox är default (auto-snapshot på stop). Spiken
  sätter `persistent: false` (ephemeral) för att slippa snapshot-storage-kostnad.

### Filer in i sandboxen

- `sandbox.writeFiles([{ path, content }])` (content är en `Buffer` / Uint8Array).
  Paths är relativa `/vercel/sandbox`. Kataloger auto-skapas **inte** av
  `writeFiles` → spiken kör `mkdir -p <dirs>` först.
- Alternativ (ej använt i spiken): `source: { type: "git" | "tarball" | "snapshot" }`
  vid create. Vi har lokala disk-filer, inte en publik URL, så `writeFiles` är
  rätt väg för PoC:n. (En framtida adapter kan paketera en tarball för färre
  round-trips.)
- Spiken kopierar **käll-filerna** (utom `node_modules`, `.next`, `.git`,
  `.turbo`, `.vercel`, `.cache`, `out`) och bygger om i sandboxen — den
  genererade sajten förblir vanlig Next.js (ADR 0030 Regel 1).

---

## Vad spiken gör (minsta beviset)

`apps/viewser/lib/vercel-sandbox-spike.ts`:

- `createSandboxPreview({ siteId, runId?, ttlMs? })` →
  `{ status, url, sandboxId, ttlMs, timings, cost, logs }`
  1. Grindar på `VIEWSER_SANDBOX_SPIKE=1` + credentials + att bygget finns på
     disk under `.generated/<siteId>/builds/<id>/` (immutable-pekare via
     `current.json`, fallback till flat layout).
  2. `Sandbox.create({ ports:[3000], runtime:"node24", timeout, persistent:false })`.
  3. `mkdir -p` + `writeFiles` av käll-filerna.
  4. `npm install` → `next build` → `next start -p 3000` (detached).
  5. Pollar `sandbox.domain(3000)` tills den svarar; mäter cold-start.
  6. Stoppar **inte** vid lyckad start — URL:en lever till TTL/cleanup.
- `stopSandboxPreview(sandboxId)` → `Sandbox.get({ name }).stop()` + kostnadssignal.

`scripts/spike_vercel_sandbox.ts`: tunn CLI (`create <siteId> [runId]` /
`cleanup <sandboxId>`).

Resultattyperna (`SandboxPreviewRequest`, `SandboxPreviewResult`,
`SandboxStopResult`) är lokala PoC-shapes — inte canonical domänbegrepp och
inte `PreviewResult`/`PreviewSession` från `packages/preview-runtime/`.

### Honest degrade (mönster: `local.ts:missingHandler`)

Alla dessa returnerar `status:"failed"` med pedagogisk svensk text, aldrig krasch:

- flaggan av,
- credentials saknas,
- `@vercel/sandbox` inte installerad (dynamisk import i try/catch),
- bygget saknas på disk,
- käll-trädet orimligt stort (skydd mot att råka ladda upp `node_modules`),
- `npm install` / `next build` / readiness-poll misslyckas (sandbox städas då).

PoC:n typ-checkar utan tokens (`cd apps/viewser && npx tsc --noEmit` grön).

---

## Hur operatören kör den (kräver tokens)

```bash
cd apps/viewser && npm install            # installerar @vercel/sandbox
# Sätt tokens: VERCEL_OIDC_TOKEN (vercel link + vercel env pull)
#   ELLER VERCEL_TOKEN + VERCEL_TEAM_ID + VERCEL_PROJECT_ID
# Sätt VIEWSER_SANDBOX_SPIKE=1
cd ..
node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts create <siteId>
# → skriver ut { url, sandboxId, status, timings, cost }
# Öppna url i mobil + desktop, bedöm. Städa sedan:
node --env-file apps/viewser/.env.local scripts/spike_vercel_sandbox.ts cleanup <sandboxId>
```

(På äldre Node: lägg till `--experimental-strip-types`.)

---

## Cold-start / TTL / kostnad / stabilitet

Spiken loggar fas-timing (`createMs`, `uploadMs`, `installMs`, `buildMs`,
`readyMs`, `totalMs`) + kostnadssignal, så en operatörskörning fyller i
faktiska siffror. Nedan är **projektioner från docs + resonemang** plus en
mätmall. Faktiska tal: **väntar operatör-körning med tokens** (kan inte mätas
utan auth).

### Cold-start (projektion)

| Fas | Förväntan | Not |
| --- | --- | --- |
| VM create | < 1 s (millisekunder enligt docs) | Firecracker microVM |
| Upload filer | ~ sekunder | Liten sajt (tiotals källfiler) |
| `npm install` | ~30–90 s | Dominerar; nätverksberoende. En sandbox-snapshot med deps skulle ta detta nära noll |
| `next build` | ~15–45 s | CPU-bundet; fler vCPU snabbar upp |
| `next start` redo | ~1–3 s | Health-poll mot publik URL |

Total första gången: i storleksordning **1–3 min**. Detta är "kallt" varje gång
i PoC:n (ingen snapshot). En framtida adapter bör använda en sandbox-snapshot
(förbyggd deps/`.next`) för att få total cold-start till sekunder.

### TTL

Default 15 min, klampat 5–45 min. Räcker gott för att öppna + bedöma på mobil.
Vill man hålla en demo längre: höj `VIEWSER_SANDBOX_SPIKE_TTL_MS` (kräver
Pro-plan för > 45 min). Auto-stop vid TTL hindrar glömda sandboxar att kosta.

### Kostnad (Pro-prislista, 2026-06-01)

- Active CPU $0.128/h (endast aktiv CPU-tid, ej I/O-väntan), provisioned memory
  $0.0212/GB-h, creation $0.60/M, data transfer $0.15/GB.
- Default 2 vCPU / 4 GB. En "build-and-serve"-session ≈ docs-exemplet
  "build and test, 30 min, 4 vCPU" ≈ **~$0.34**, men vår 2-vCPU/15-min-session
  bör landa **lägre** (~$0.05–0.15 beroende på faktisk CPU). Creation-kostnad
  försumbar. Hobby: 5 h CPU + 5000 creations/mån gratis → räcker för spike-bruk.
- Spiken loggar `cost` vid create (vcpus/memory/ttl/filantal/uploadbytes) och
  vid cleanup (faktisk `activeCpuMs` + nätverk) så verklig kostnad kan avläsas.

### Stabilitet

- Isolering: varje preview kör i egen Firecracker-VM med egen filsystem/nätverk
  → ingen risk att en genererad sajt påverkar Viewser-hosten (till skillnad från
  `local-next` som spawnar processer på operatörens maskin, jfr B157).
- Region: endast `iad1` idag → högre latens från Sverige än en EU-host. Påverkar
  upplevd snabbhet, inte korrekthet.
- Browser: publik https-URL fungerar i **alla** browsers (löser B125
  Safari/Firefox-problemet som `stackblitz` har).
- Risk: `npm install` + `next build` i molnet är nätverks-/CPU-känsligt; om en
  generad sajt har trasiga deps failar bygget — spiken rapporterar då exit-koden
  ärligt och städar sandboxen.

---

## Go/No-go — promota till en `vercel-sandbox` PreviewRuntime-adapter?

**Läge nu:** PoC är kod-komplett, typ-checkar, degraderar ärligt. Live-beviset
(öppningsbar URL + faktisk cold-start) **kräver en operatör-körning med tokens**
och är inte kört i detta pass.

**Rekommendation: villkorligt GO.** API:t bär exakt det adapter-kontraktet
behöver (`start` → URL, `stop`, tyst/ärlig degradering, non-Vercel-fallback
finns redan via `local-next`/`stackblitz`). Vercel-sandbox är dessutom den enda
av nuvarande kandidater som ger en publik URL som funkar i alla browsers utan
att belasta operatörens maskin.

Promotion **kräver först** (per ADR 0030 §"Vad ADR 0030 INTE beslutar"):

1. ADR 0033 som motiverar adaptern + token-beroendet och bekräftar
   non-Vercel-fallback.
2. **naming-dictionary bump (v18)** för `previewRuntimeKind`-värdet
   `vercel-sandbox` + ev. `VercelRuntime`-adapter-label.
3. **`PreviewRuntimeKind`-utökning** i `packages/preview-runtime/src/types.ts` +
   registry-entry + DI-wiring (mönster: Bite B `local`/`stackblitz`).
4. En **sandbox-snapshot-strategi** så cold-start blir sekunder, inte minuter.

Innan dess: kör spiken manuellt, fyll i faktisk cold-start/kostnad nedan, och
fatta beslut på riktiga siffror.

### Mätlogg (fylls i av operatör)

| Datum | siteId | totalMs | installMs | buildMs | URL öppningsbar? | Mobil? | activeCpuMs | Kommentar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _pending_ | | | | | | | | |

---

## Write-set (denna spike)

- `apps/viewser/lib/vercel-sandbox-spike.ts` — helper (`createSandboxPreview` + `stopSandboxPreview`).
- `apps/viewser/package.json` — la till `@vercel/sandbox`.
- `apps/viewser/.env.example` — flagga + tokens (kommenterade).
- `scripts/spike_vercel_sandbox.ts` — create + cleanup-entries.
- `docs/spikes/vercel-sandbox-spike.md` — denna fil.
- `scripts/check_term_coverage.py` — allowlist för PoC:ns lokala TS-symboler
  (inte domänbegrepp; samma mönster som befintliga apps/viewser-allowlists).

Orört: `packages/preview-runtime/**`, `naming-dictionary.v1.json`,
`scripts/build_site.py`, `packages/generation/**`, produktions-routes,
`viewer-panel.tsx`, `components/**`.
