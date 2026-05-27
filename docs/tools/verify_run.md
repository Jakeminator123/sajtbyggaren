# `scripts/verify_run.py` — post-run smoke-checker

Stand-alone verktyg som verifierar att en sajtbyggaren-run uppfyller
LLM contract propagation-förväntningar **utan** att starta dev-server
eller titta i preview-iframe. Designat för adversarial-test (typ
sköldpaddssoppa Case 4) och baseline-mini-eval där vi vill jämföra
före/efter snabbt.

## När du ska använda det

- **Efter varje build du vill mäta** — istället för att försöka rendera
  i StackBlitz/preview (som ofta är blockerad av B125-browserstöd).
- **Mini-eval på 4 baseline-prompter** (elektriker / frisör / naprapat /
  sköldpaddssoppa) efter en B137/B138/B139/B140/B141-fix-sprint.
- **Som regression-koll inom Builder-loop** mellan check-ins (Plan Mode →
  fix → re-build → `verify_run.py` → nästa fix).

## Vad det inte är

- Inte en ersättning för pytest. Skriptet kollar **artefakter på disk**,
  inte enhetsbeteende.
- Inte en ersättning för Scout-rapportens 8-kriterier-skala
  (`intentMatch`, `branchMatch`, `routeStructure`, ...). Det är fortsatt
  Scout-rollens jobb att ge subjektiv kvalitetsbedömning på en run.
- Inte en preview. Det visar inte hur sajten ser ut visuellt — bara att
  data flödar rätt genom kedjan.

## Snabbstart

Från repo-rot, PowerShell:

```powershell
# Default - alla checks, text-output mot senaste matchande run
python scripts/verify_run.py --site-id skoldpaddssoppa-karlsson-099d5c

# Senaste run överhuvudtaget (för "vad just byggdes?")
python scripts/verify_run.py --latest

# Specifik run-ID (exakt match i data/runs/)
python scripts/verify_run.py --run-id 20260519T190606.540Z-51cef6dd-skoldpaddssoppa-karlsson-099d5c

# Maskin-läsbar JSON-output för agent-konsumtion
python scripts/verify_run.py --site-id <id> --json

# Bara specifika checks (kommaseparerat)
python scripts/verify_run.py --site-id <id> --checks b137,b138,intent-guard
```

## Vilka filer skriptet läser

Read-only mot:

- `data/runs/<runId>/site-brief.json` — briefModel-output (signaler in)
- `data/runs/<runId>/site-plan.json` — planning-output (route-plan + warnings)
- `data/runs/<runId>/build-result.json` — build-status, quality-checks
- `data/prompt-inputs/<siteId>.meta.json` — sidecar-meta (field-sources,
  placeholder-fält, discovery-decision)
- `<generated-root>/<siteId>/app/page.tsx` (+ underrouter) — renderad output

Skriptet **rör aldrig** några filer. Det är säkert att köra parallellt
med Builder, Steward, Scout eller cloud-grind-agenter.

## Checks i default-set

| ID | Vad det mäter | FAIL-villkor |
|---|---|---|
| `brief` | Skriver ut briefModel-signaler (info-only) | aldrig FAIL |
| `b137` | Hero-tagline läcker rå UI-direktiv? | Tagline innehåller någon av `BLOCKED_TAGLINE_PHRASES` (t.ex. `"Hemsida om"`, `"2 sidor"`, `"gröna färger"`) |
| `b138` | `routePlan` respekterar `brief.pageCount`? | Route-count > brief.pageCount utan trim |
| `intent-guard` | Warnings emitterade vid wizard-vs-brief-konflikt? | Mat-services utan warning (WARN, inte FAIL) |
| `routes` | Filsystem (`app/<route>/page.tsx`) matchar `site-plan.routePlan`? | Set-skillnad mellan disk och plan |
| `services` | Service-summaries är B107-fallback eller operatörsspecifika? | Aldrig FAIL — WARN om B107-mönster aktivt |
| `contact` | Placeholder-contact-fält (info-only) | aldrig FAIL |
| `field-sources` | `fieldSources`-mappning i sidecar-meta (info-only) | aldrig FAIL |
| `page-intent` | B132 `pageIntentWarnings` (info-only) | aldrig FAIL |

`--checks` tar en kommaseparerad lista. Default = alla.

## Exit-koder

- **0** — alla aktiverade checks passerade (inkl. WARN/UNKNOWN/SKIP räknas inte som fail)
- **1** — minst en check returnerade `FAIL`
- **2** — argument- eller path-fel (run/site-id ej funnen, etc)

Skriptet exit:ar inte på `WARN` eller `UNKNOWN` — operatören eller en
orchestrerande agent får tolka dem.

## JSON-output (för agenter)

`--json` ger en strukturerad payload:

```json
{
  "run": "20260519T190606.540Z-51cef6dd-skoldpaddssoppa-karlsson-099d5c",
  "siteId": "skoldpaddssoppa-karlsson-099d5c",
  "buildStatus": "ok",
  "results": [
    {
      "status": "OK",
      "label": "B137 - Hero tagline",
      "details": {
        "tagline": "Tydlig hjälp inom restaurant",
        "blocked_leaks": []
      }
    },
    ...
  ],
  "summary": {
    "ok": 6, "fail": 0, "warn": 1, "unknown": 1, "skip": 0
  }
}
```

Agenter ska parsa `summary.fail` för att avgöra grön/röd och
`results[].label` + `results[].details` för att rapportera per-check
till operatör eller orchestrator.

## För agenter — användningsdiscipline

- **Read-only**. Skriptet ändrar inte filer. Du kan köra det utan
  backup-N.
- **Citerbart via `--json`**. Klistra payload i din rapport-fil eller
  chatten till orchestrator. Sammanfatta i text om operatören är
  trött; använd raw JSON om orchestrator vill parsa.
- **Hör inte hemma i pytest**. Det här är post-build-verifiering, inte
  enhetsbeteende. Behåll regression-tester i `tests/`.
- **Påverkar inte governance-räkningen**. Skriptet är ett verktyg, inte
  en policy. Du behöver inte registrera det i `governance/`.
- **Använd vid Scout-pass case-mätning**: `--json` ger en deterministisk
  data-bas att jämföra mot tidigare runs.

## Mini-eval-flöde (4 baseline-prompter)

För automatiserad lokal mini-eval efter B139/B140 finns nu
`scripts/mini_eval.py`. Den är byggd för att kunna köras i separat terminal
vid sidan av Cursor-agentens huvudflöde:

```powershell
# Snabb eval utan npm-build (default). Skriver till data/evals/artifacts/mini/
python scripts/mini_eval.py

# Välj eval-root explicit, t.ex. på snabb disk eller i en separat workspace-mapp
$env:SAJTBYGGAREN_EVALS_DIR = "D:/sajtbyggaren-evals"
python scripts/mini_eval.py --eval-id local-smoke-001

# Kör bara ett case medan annat arbete pågår
python scripts/mini_eval.py --case electrician-malmo

# Låt även npm-build köra (långsammare, när du vill ha starkare bevis)
python scripts/mini_eval.py --run-build
```

Output per eval:

- `prompt-inputs/` — isolerade Project Input-versioner och meta-sidecars
- `runs/` — isolerade Engine Run-artefakter
- `generated/` — isolerad genererad Next.js-output
- `mini-eval-report.json` — maskinläsbar jämförelse
- `mini-eval-report.md` — operatörsrapport + scorecard-mall

Default-casen är elektriker Malmö, frisör Göteborg, naprapat Stockholm och
sköldpaddssoppa. Runnern gör init + follow-up per case, jämför
story/tagline/tone, CSS-token-diff (`--primary`, `--accent` och foreground-
tokens), raw prompt-läckage och warnings. Den skriver inte till canonical
`data/runs/` eller `data/prompt-inputs/`, så den är säker att köra parallellt
med Builder/Steward/Scout-arbete.

### Manuell variant med `verify_run.py`

Standardflödet efter en kedje-propagation-sprint (B137/B138/B139/etc):

1. Operatören kör 4 prompter via Viewser-overlay:
   - elektriker Malmö
   - frisör Göteborg
   - naprapatklinik Stockholm
   - sköldpaddssoppa Karlsson (adversarial)
2. För varje run:
   ```powershell
   python scripts/verify_run.py --site-id <siteId> --json > eval-<siteId>.json
   ```
3. Agent (eller operatör) parsar de 4 JSON-filerna och sammanställer
   i en rapport under `docs/reports/mini-eval-<datum>.md`:
   - Per case: FAIL-count, WARN-count, tagline, route-count
   - Cross-case: regressioner mellan körningar
   - Beslut: ≥ alla 4 case OK + 0 FAIL → Project DNA-sprint unblocked

## Lägg till en ny check

1. Skriv en `check_<id>(...)` i `verify_run.py` som returnerar
   `{"status": "OK"|"FAIL"|"WARN"|"UNKNOWN"|"SKIP", "label": "...",
   "details": {...}}`.
2. Lägg `id` i `ALL_CHECKS`-tuplen.
3. Lägg dispatch-rad i `main()` (`if "<id>" in wanted: ...`).
4. Uppdatera den här fil-tabellen ("Checks i default-set").
5. Ingen pytest behövs — skriptet är post-run-tool, inte enhetsbeteende.

## Felsökning

- **"data/runs/ saknas"** — du kör inte från repo-rot. `cd` dit först.
- **"generated-dir saknas"** — du kör med non-default
  `SAJTBYGGAREN_GENERATED_DIR`-env eller har raderat output. Sätt env
  eller bygg om.
- **`UNKNOWN` på B137 tagline** — `app/page.tsx` matchar inte renderer-
  mönstret `<p ...>{"..."}</p>`. Kan vara en starter som inte är
  marketing-base.
- **`UNKNOWN` på field-sources/contact** — `data/prompt-inputs/<siteId>.meta.json`
  saknas. Antingen är det en gammal run från före sidecar-meta
  införsel eller en run via dossier-path-override.

## Relaterat

- `docs/archive/2026-05-19/scout-wizard-tagline-pagecount-tone-2026-05-19.md` — Scout-
  kartläggning av kodvägarna B137/B138/B139 pekar på.
- `docs/archive/run-details-warnings-inventory-2026-05-21.md` — vilka
  warning-fält finns idag, var de bör renderas.
- `docs/agent-handbook.md` — när Scout/Builder/Steward ska köra det här
  verktyget i sina loopar.
