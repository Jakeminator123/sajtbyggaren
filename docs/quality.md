# Kvalitetsskydd och regression-tester

Det här dokumentet beskriver vad som hindrar repot från att glida ifrån governance. Tre lager skydd, plus en CI-grind på toppen.

## Lager 1: Schema-validering

`scripts/governance_validate.py` validerar varje policy under `governance/policies/` mot motsvarande JSON Schema i `governance/schemas/`. Plus en cross-check som hindrar `globallyForbidden`-termer från att användas utanför explicita anti-pattern-fält (`forbiddenTerms`, `aliasesForbidden`, `mustNotDo`, `avoid`, `limitations`, `negativeSignals`).

```bash
python scripts/governance_validate.py
```

## Lager 2: Spegelsync

`scripts/rules_sync.py` säkerställer att `.cursor/rules/*.mdc` är ren spegel av `governance/rules/*.md`. Direkt-redigeringar i `.cursor/rules/` upptäcks och kan rättas.

```bash
python scripts/rules_sync.py            # skriv om alla speglar
python scripts/rules_sync.py --check    # exit 1 om out-of-sync
```

## Lager 3: Term-coverage

`scripts/check_term_coverage.py` skannar `*.{md,mdc,py,ts,tsx,js,json}` (utom `referens/`, `data/`, `node_modules/` etc.) och rapporterar PascalCase-symboler eller citerade fraser som ser ut som domänbegrepp men inte finns i `naming-dictionary.v1.json`.

```bash
python scripts/check_term_coverage.py            # rapportera kandidater
python scripts/check_term_coverage.py --strict   # exit 1 om kandidater hittas
```

## Lager 4: pytest-svit

Under `tests/` ligger sex test-moduler. Tillsammans täcker de:

| Test-modul | Vad den fångar |
|------------|----------------|
| [`test_governance_validate.py`](../tests/test_governance_validate.py) | Schema-fel, globally-forbidden missbruk. |
| [`test_rules_sync.py`](../tests/test_rules_sync.py) | Out-of-sync `.cursor/rules`, källfiler utan mirror. |
| [`test_term_coverage.py`](../tests/test_term_coverage.py) | Strict mode på term-coverage; nya begrepp utan registrering. |
| [`test_cross_policy_consistency.py`](../tests/test_cross_policy_consistency.py) | Default-scaffold finns i registry, alla canonicals är unika, vikter summerar, canonicalFlow matchar phase ids, etc. |
| [`test_decisions_and_docs.py`](../tests/test_decisions_and_docs.py) | ADR:er är unikt numrerade, kritiska docs finns, README nämner principen. |
| [`test_no_legacy_terms.py`](../tests/test_no_legacy_terms.py) | Globally-forbidden termer återinförs inte i produkttext. |

Kör hela sviten:

```bash
python -m pytest tests/ -v
```

Bara governance-markerade tester (snabbt):

```bash
python -m pytest tests/ -m governance -q
```

## Lager 5: GitHub Actions

[`.github/workflows/governance.yml`](../.github/workflows/governance.yml) kör alla skript och hela pytest-sviten på varje push och PR mot `main`. Status syns på commit-listan i GitHub.

## Vad som händer när något fallerar

| Symptom | Åtgärd |
|---------|--------|
| `governance_validate.py` failar | Läs fel-output. Antingen är JSON ogiltig mot schema, eller så används en globally-forbidden term aktivt. Justera policyn eller flytta termen till en `aliasesForbidden`-lista. |
| `rules_sync.py --check` failar | Kör utan `--check` för att speglar ska skrivas om. Om någon redigerade `.cursor/rules/` direkt - flytta innehållet till `governance/rules/` och kör syncen. |
| `check_term_coverage.py --strict` failar | Antingen lägg till termen i `naming-dictionary.v1.json` (om den är ett riktigt domänbegrepp), eller utöka `COMMON_WORDS` i skriptet (om den är prosa eller icke-domän). |
| `test_cross_policy_consistency.py` failar | Två policies har divergerat. Texten i felmeddelandet pekar på exakt vilken regel som bröts. |
| `test_no_legacy_terms.py` failar | En förbjuden term har skrivits in i en docs- eller kodfil. Skriv om eller flytta till en explicit anti-pattern-lista. |

## När du skapar en ny policy eller ändrar en

Checklist:

1. Definiera schema i `governance/schemas/<name>.schema.json` om det är en ny policy.
2. Skapa eller uppdatera policy under `governance/policies/<name>.v<N>.json`.
3. Bumpa `version`-fältet vid additiva ändringar; bumpa `policyId.vN` vid breaking changes.
4. Lägg till nya domänbegrepp i `naming-dictionary.v1.json` enligt `term-discipline`.
5. Uppdatera `repo-boundaries.v1.json` om en ny mapp äger något.
6. Lägg ny ADR i `governance/decisions/NNNN-...md` med kontext + beslut + konsekvenser.
7. Kör de fem stegen ovan (validate, sync, coverage, pytest, ev. CI).
8. Commit med kort engelsk message som beskriver vilken policy/ADR som lagts till.

## När backoffice ska visa något nytt

Backoffice (`backend.py` + `backoffice/`-modulen) får aldrig dubbla logiken som finns i policies. Den **läser** governance, kör skripten och visar resultatet. Om en ny vy behövs:

1. Lägg vyfunktion i `backend.py` (eller `backoffice/views.py` om kodvolymen växer).
2. Lägg till i `SECTIONS`-dict så den dyker upp i sidopanelen.
3. Använd `loaders.load_policy(...)` så caching fungerar.
4. Om vyn behöver köra ett skript: använd `health.run_*` så output formateras enhetligt.
