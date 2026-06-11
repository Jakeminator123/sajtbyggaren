# Testlanes och testklassificering

Sviten har vuxit till ~160 filer och en full körning tar flera minuter.
Det här dokumentet beskriver de tre körlanen och klassificerar
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

`python scripts/review_check.py --core` kör hela guard-kedjan
(governance, rules-sync, term coverage, ruff) med kärnlanen i stället
för full pytest. Full svit är fortsatt kravet före merge, men den körs
av CI på PR:en (governance-workflowet kör `python -m pytest tests/ -v`
på `pull_request`): lokalt räcker riktade tester som default.

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
(`test_viewser_*`), quality-gate-specialfallen samt eval-tooling
(`test_mini_eval`, `test_golden_path_eval`, `test_run_eval_suite`).

### Tooling/infrastruktur

Skydd för operatörsverktyg och repo-hygien, inte produktflödet:
`test_backoffice_*`, sprintvakt, docs-checkarna (`test_docs_check`,
`test_docs_freshness`, `test_decisions_and_docs`), namngivning/term-
coverage, repo-gränser, github-workflow, `test_kill_dev_trees`,
`test_test_hygiene`, `test_build_site_size`.

### Historiska källkodslås — granskningskandidater (operatörsbeslut)

Lås skrivna mot en specifik historisk bugg eller sprint, där koden de
låser kan ha förändrats så mycket att låset mest kostar körtid:

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
