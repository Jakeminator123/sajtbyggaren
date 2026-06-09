# ADR 0038 — Golden Path som canonical term

**Status:** Accepted
**Datum:** 2026-06-09
**Beroenden:** ADR 0006 (term-discipline), ADR 0012 (vocabulary compression).
Referens: [`docs/llm-golden-path-runbook.md`](../../docs/llm-golden-path-runbook.md),
[`docs/product-operating-context.md`](../../docs/product-operating-context.md),
[`docs/evals.md`](../../docs/evals.md).

## Kontext

Begreppet "golden path" har vuxit fram organiskt i repot utan att vara
registrerat i `naming-dictionary.v1.json`. Det används idag på flera ytor som
beskriver **samma sak** — produktens kanoniska huvudflöde — men under olika
stavningar och utan en sanningskälla:

- `docs/llm-golden-path-runbook.md` (runbook för huvudflödet)
- `scripts/run_golden_path_eval.py` (deterministisk mätning av flödet)
- `tests/test_golden_path_eval.py` + `tests/test_llm_golden_path_smoke.py`
- `data/evals/summaries/golden-path/` + `data/evals/artifacts/golden-path/`
- `backoffice/paths.py` / `backoffice/maintenance.py`
  (`MAX_GOLDEN_PATH_EVALS`, prune-logik)

Samtidigt används ordet "golden" på ett **annat** ställe i en helt annan
betydelse: snapshot-/golden-master-testning (t.ex.
`tests/test_section_treatments_json_parity.py` och
`tests/test_build_tokens_parity.py` som fryser en referens som "golden truth"
respektive "golden file"). Det skapade begreppsförvirring: är "golden" flödet
eller är det ett fruset testfacit?

Per `.cursor/BUGBOT.md` och ADR 0006 måste ett begrepp som syns i docs,
artefakter och operatörsytor antingen registreras i `naming-dictionary.v1.json`
med en ADR, eller allowlistas i `COMMON_WORDS`. Golden Path är operatörssynlig
produktvokabulär → den hör hemma i naming-dictionary med denna ADR som
motivering.

## Beslut

### 1. Golden Path är canonical (registreras nu)

`Golden Path` registreras som canonical term i `naming-dictionary.v1.json`
(v27). Definition: produktens **kanoniska huvudflöde** —
`prompt -> företagshemsida -> preview -> följdprompt -> ny version` — och den
smala vertikala skiva av motorn som bevisar att huvudflödet lever
(`Project Input -> Site Brief -> Site Plan -> Generation Package ->
Generated Files -> Quality Gate -> Preview`).

`ownerPackage` sätts till `scripts` eftersom den canonical entrypoint-ytan
(`scripts/run_golden_path_eval.py`, som `scripts/`-ägarskapet redan listar under
"eval-run") och dess tester/runbook är de konkreta artefakter som mäter flödet.

`aliasesForbidden`: `happy-path`, `main-flow`, `core-path`, `goldenflow` — så
flödet inte får parallella namn igen.

### 2. Golden Path ≠ snapshot/golden-master-testning

Ordet "golden" i snapshot-testning ("golden truth", "golden file") är **inte**
Golden Path. Det är den vanliga test-idiomatiken för ett fruset facit. För att ta
bort den överlagrade betydelsen ska sådan testtext säga **snapshot baseline**
(eller "frozen reference") i stället för "golden". Detta är en
docstring-/kommentarsändring; ingen testlogik eller assertion ändras.

### 3. Ingen ny artefakt, ingen ny golden-term

Det införs **ingen** ny canonical typ utöver `Golden Path` (ingen
"Golden Path Eval", "Golden Fixtures" eller "Quality Scorecard" som egna canonical
termer). Mätningen refereras via sin kodväg (`scripts/run_golden_path_eval.py`),
testdata via `tests/`-fixturer, och de befintliga scorecard-betydelserna
(automatisk `Quality Result.scorecard` + det manuella operatörs-scorecardet under
`data/evals/.../manual-scorecards/`) dokumenteras som de är i `docs/glossary.md`
utan ett nytt ord.

## Vad ADR 0038 INTE beslutar

- Ingen ändring av Golden Path-evalens beteende, output-kontrakt eller
  gate-trösklar (ADR 0026 äger embeddings-gaten).
- Ingen ny Preview Runtime, auth, billing eller scaffold-ändring.
- Ingen pensionering av `Project DNA` (aktivt, canonical) och ingen omtolkning
  av blueprint-fältgrupperna (per ADR 0036).
- Ingen ny backoffice-feature; en eventuell read-only golden-status-yta är ren
  observation av redan skrivna eval-artefakter.

## Verifiering

- `python scripts/governance_validate.py` — naming-dictionary v27 validerar.
- `python scripts/check_term_coverage.py --strict` — grön (Golden Path är nu
  registrerad och flaggas inte längre som okänd kandidat).
- `python -m pytest tests/test_cross_policy_consistency.py
  tests/test_decisions_and_docs.py -q` — ownerPackage `scripts` finns i
  repo-boundaries; ADR 0038 är unikt numrerad efter 0037.
- `python -m pytest tests/test_no_legacy_terms.py -q` — inga globallyForbidden
  termer återinförda.
