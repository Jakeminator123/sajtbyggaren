# Testlanes och testklassificering

Sviten har vuxit till 209 testfiler och cirka 4227 testfall, och en full
körning tar flera minuter. (Ögonblicksbild per `jakob-be@3747e74`, mätt med
`python -m pytest --collect-only -q`. Två filer hoppar import utan
extra-beroenden — `requests`/`bs4` — och samlas inte i den siffran. När #328
mergas tillkommer två testfiler, `test_route_directives.py` och
`test_followup_route_remove.py`, så filsiffran blir 211; re-mät vid rebase så
siffran inte driftar.) Det här dokumentet beskriver körlanen och klassificerar
testfamiljerna, så att en agent eller operatör kan välja rätt lane utan
att tappa regressionsskydd. Bakgrund: extern testaudit 2026-06-10 som
föreslog massradering av historiska regressionslås — beslutet blev i
stället en snabb kärnlane plus den här klassificeringen, där radering av
historiska lås listas som operatörsbeslut (se sist).

## Lanes

| Lane | Kommando | Omfattning | Riktvärde |
| ---- | -------- | ---------- | --------- |
| Riktade tester | `python -m pytest tests/test_<berörd>*.py -q` | sviterna som rör ändrade filer/paket — **lokal default före commit** (operatörsbeslut 2026-06-11) | sekunder–minut |
| Kärnlane | `python -m pytest -m core -q` | ~28 filer som täcker kärnloopen (prompt → bygge → preview → följdprompt) | ~1 min |
| Full svit (parallell) | `python -m pytest tests/ -q -n auto` | allt, via pytest-xdist — för breda ändringar (flera paket) eller på explicit begäran | ~5 min (uppmätt 291 s, 16 workers) |
| Full svit (seriell) | `python -m pytest tests/ -q` | allt — det CI kör på varje PR; merge-gaten | ~13 min på operatörens Windows-maskin |
| Grindade | markörerna `slow`, `e2e`, `requires_node` | skippas automatiskt när förutsättningen saknas (npm, nyckel, `SAJTBYGGAREN_E2E=1`) | varierar |

### Markörlanor (tier-urval)

Utöver lanen ovan finns markörer som låter dig välja eller välja bort hela
testfamiljer additivt. De ändrar inte vad CI kör — CI kör alltid full svit
(`python -m pytest tests/ -v`), så markörerna är bara lokala snabbval och
merge-gaten är oförändrad. Alla markörer är registrerade i `pyproject.toml`
under `--strict-markers`.

| Markör | Kommando | Vad den väljer |
| ------ | -------- | -------------- |
| `tooling` | `python -m pytest -m tooling -q` | operatörsverktyg och repo-hygien, inklusive hela `test_backoffice_*`-familjen |
| `integration` | `python -m pytest -m integration -q` | de nio hostade viewser-låsen (`test_viewser_hosted_*`) |
| `source_lock` | `python -m pytest -m source_lock -q` | de historiska källkodslåsen (granskningskandidaterna, se sist) |
| `smoke` | `python -m pytest -m smoke -q` | en liten, snabb sanity-delmängd — markören är registrerad men ännu inte applicerad på några tester; den taggas inkrementellt i en egen, granskad runda |

Snabb lokal check som hoppar de tunga/hostade familjerna:

```
python -m pytest -m "not slow and not integration" -q
```

De sju `test_viewser_hosted_*`-filer som redan låg i kärnlanen behåller sina
`core`- och `tooling`-markörer och får `integration` additivt. Det betyder att
`-m "not integration"` väljer bort just dem ur snabblanen, medan `-m core` är
helt oförändrat — kärnlanen samlar samma uppsättning som tidigare.

`python scripts/review_check.py --core` kör hela guard-kedjan
(governance, rules-sync, term coverage, ruff) med kärnlanen i stället
för full pytest. Full svit är fortsatt kravet före merge, men den körs
av CI på PR:en (governance-workflowet kör `python -m pytest tests/ -v`
på `pull_request`): lokalt räcker riktade tester som default.

## Eval-baseline-grind (regressionsgrind)

`scripts/eval_gate.py` är en regressionsgrind ovanpå den deterministiska
golden-path-evalen (`scripts/run_golden_path_eval.py --mode deterministic`).
Den körs Node-fritt och kräver ingen LLM-nyckel.

- **Vad grinden gör:** kör de fyra golden-path-casen i deterministiskt läge,
  destillerar de bit-stabila poängen (per-case `totalScore`, aggregerat
  `totalScore`, `embeddingsReadiness`) och jämför mot en committad baseline.
  Den fäller (exit 1) bara vid regression utöver tolerans; en förbättring
  fäller aldrig.
- **Tolerans:** aggregat-snittet får inte sjunka mer än `0.2`, och inget
  enskilt case mer än `0.5` (0–10-skalan). En försämring av
  `embeddingsReadiness` från `go` till `no-go` fäller också. Konstanterna bor
  i `scripts/eval_gate.py` (`AGGREGATE_MAX_DROP` / `CASE_MAX_DROP`) och valdes
  så att en enskild trait som tippar på ett case ryms inom tolerans, medan en
  bred copy-/render-regression fäller.
- **Var baseline ligger:** `tests/evals/golden-path-baseline.json` (spårad i
  git — hela `data/evals/` är gitignorad och dög därför inte som committad
  path). Filen har bara poäng plus ett `_meta`-block; inga timestamps,
  run-id:n eller sökvägar, så den är byte-stabil och diffbar.
- **Regenerera baseline:** `python scripts/eval_gate.py --update-baseline`
  efter en avsiktlig, granskad kvalitetsändring. Committa baseline-diffen för
  sig.
- **Utan nyckel:** grinden är aldrig en tyst no-op. Deterministiskt läge tar
  bort `OPENAI_API_KEY` internt, så den producerar och validerar riktiga
  poäng oavsett om en nyckel finns eller inte.
- **I CI:** eget Node-fritt jobb `eval-baseline` i
  `.github/workflows/governance.yml`, parallellt med `governance`-jobbet. Samma
  jobb kör även `scripts/mini_eval.py` (no-LLM follow-up-eval) mot en
  tmp-katalog (`--evals-dir "$RUNNER_TEMP/..."`) så `data/`-trädet aldrig
  smutsas ner. npm-tunga lanen (full svit + next build) ligger kvar i
  `builder-smoke`.
- **Gate-logiken testas:** i `tests/test_eval_gate.py` — lika-med-baseline
  passerar, regression utöver tolerans fäller, förbättring passerar, och
  nyckel-satt kör ändå deterministiskt (ingen tyst no-op).

## Parallellkörning (pytest-xdist)

`pytest-xdist` ligger i dev-beroendena (`requirements.txt` /
`pip install -e .[dev]`). Uppmätt 2026-06-11 på operatörens maskin
(16 logiska kärnor): full svit 291 s med `-n auto` mot ~13 min seriellt
— allt grönt, inklusive de tre tyngsta testerna (golden-path real-build
115 s, `/api/prompt`-smoke 109 s, B154-chunkkörningen 97 s) som spawnar
egna Next-processer på slumpade portar med `tmp_path`-isolerade
kataloger. Kända begränsningar:

- `test_api_prompt_smoke` startar `next dev` i delade `apps/viewser/` —
  samma `.next`-dev-lock-kollision som vid seriell körning gäller
  (stäng Viewser på port 3000 först). Bara ett test i sviten gör detta,
  så xdist-arbetarna kolliderar inte med varandra.
- Golvet för väggtiden är det långsammaste enskilda testet (~2 min);
  mer än ~8 workers ger marginell ytterligare vinst.

Praktiska noter för full svit:

- Stäng Viewser på port 3000 först — annars flakar
  `test_api_prompt_smoke` (egen dev-server, `.next`-kollision).
- Kör med `SAJTBYGGAREN_EVALS_DIR` och `SAJTBYGGAREN_GENERATED_DIR`
  osatta; injicerade värden ändrar default-sökvägar som vissa tester
  asserterar.

## Kärnlanen (markör `core`)

Filerna är markerade med `pytestmark = pytest.mark.core` och valda för
att en grön kärnlane ska betyda "kärnloopen fungerar": router →
kontext → patch → apply → riktad render, OpenClaw-besluten, följdprompt-
direktiven (tema/copy/sektion), versionering, hero-/brief-stabilitet
(B173/B180), builder-smoke med route-emission, codegen → quality gate →
repair, schemalåsen för artefakter och projektinput, samt
prompt-till-projektinput och /api/prompt-seamen.

Markören registreras i `pyproject.toml` (strict-markers). Lägg bara till
nya filer i lanen när de täcker kärnloopen och håller totaltiden under
~2 minuter.

## Klassificering av testfamiljerna

Klassificeringen följer den externa auditens fyra grupper. Inget togs
bort i samband med att lanen infördes (utöver en död platshållare,
`tests/schemas/.gitkeep`, med noll referenser; `tests/evals/.gitkeep`
behålls — refererad av repo-boundaries-policyn och ADR 0005/0008).

### Kärna

De core-markerade filerna ovan. Ändras kärnloopen ska ett test här gå
rött.

### Sekundär (körs i full svit, inte i kärnlanen)

Detalj- och paritetsfamiljer som skyddar enskilda byggsteg:
assets/tokens/prompt-meta-paritet, mediarendering, favicon/og-bild,
kontaktrutter och CTA-mål, section treatments, planering/blueprint-
detaljer, dossier-montering och discovery, wizard- och Viewser-UI-låsen
(`test_viewser_*`; de nio hostade `test_viewser_hosted_*` bär även markören
`integration`), quality-gate-specialfallen samt eval-tooling
(`test_mini_eval`, `test_golden_path_eval`, `test_run_eval_suite`,
`test_eval_gate`).

### Tooling/infrastruktur

Skydd för operatörsverktyg och repo-hygien, inte produktflödet:
`test_backoffice_*` (hela familjen bär nu markören `tooling` på modulnivå),
sprintvakt, docs-checkarna (`test_docs_check`,
`test_docs_freshness`, `test_decisions_and_docs`), namngivning/term-
coverage, repo-gränser, github-workflow, `test_kill_dev_trees`,
`test_test_hygiene`, `test_build_site_size`.

### Historiska källkodslås — granskningskandidater (operatörsbeslut)

Lås skrivna mot en specifik historisk bugg eller sprint, där koden de
låser kan ha förändrats så mycket att låset mest kostar körtid. De fem
filerna nedan bär numera markören `source_lock`, så de kan köras eller
väljas bort som grupp (`-m source_lock` / `-m "not source_lock"`) utan att
någon rad raderas:

- `test_bug_sweep_b163_b171.py` — källkodslås från bug-sweepen
  2026-06-10; värdet sjunker när seams refaktoreras.
- `test_b154_next_dev_tdz.py` — chunk-heuristik, redan flaggad som
  otillräcklig i B156.
- `test_local_preview_server_b157_followup.py` — låser ett B157-
  följdscenario som B157 nivå 4 (immutable builds) sedan löste
  arkitekturellt.
- `test_builder_audit_post_3b_next.py`, `test_artefact_schema_3c_lite.py`
  — sprintbundna audit-lås (3b/3c) vars innehåll till stor del täcks av
  schema- och quality-gate-testerna i kärnlanen.

Motivering till att inget raderas nu: låsen är billiga (sekunder i full
svit), de skadar inte kärnlanen (omarkerade), och flera har historiskt
fångat verkliga regressioner. Radering är därför ett operatörsbeslut
per fil — inte en automatisk sanering. Vill du radera: ta bort filen i
en egen `chore:`-commit och notera det i `docs/known-issues.md` om låset
pekade på en öppen risk.
