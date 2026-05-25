# ADR 0029 — Editable install av tooling-paketet via setuptools.packages.find

**Status:** Accepted
**Datum:** 2026-05-25
**Beroenden:** PR #70 (Sprintvakt V1 koordineringsserver), Fynd 3 i
`GAP-sprintvakt-v1-1-bug-followups` (PR #70 follow-up).

## Kontext

Sprintvakt V1 (PR #70) lade till två import-vägar för samma kod under
`tooling/sprintvakt_mcp/`:

1. `scripts/sprintvakt_check.py` (CLI) — importerade
   `tooling.sprintvakt_mcp.core` via en `sys.path`-mutation överst i
   skriptet:

   ```python
   REPO_ROOT = Path(__file__).resolve().parent.parent
   if str(REPO_ROOT) not in sys.path:
       sys.path.insert(0, str(REPO_ROOT))
   from tooling.sprintvakt_mcp.core import ...  # noqa: E402
   ```

2. `python -m tooling.sprintvakt_mcp.server` (MCP-server) — fungerade
   bara om Pythons CWD råkade vara repo-roten, eftersom `tooling/`
   saknar `__init__.py` på top-level (namespace package).

Cursor-MCP-launchen avslöjade båda svagheterna: `python -m
tooling.sprintvakt_mcp.server` kraschade med `ModuleNotFoundError: No
module named 'tooling'` när Cursor startade subprocessen utan att
ärva CWD som sys.path-bidrag.

AI-bug-reviewen på PR #70 flaggade `sys.path`-mutationen som en
LOW-severity anti-pattern (74 % probability, 6/10 impact). Den lokala
verkligheten visade att skörheten är mer än kosmetisk — det blockerade
Cursor-MCP-aktiveringen helt.

`pyproject.toml` hade redan `requirements.txt`-en som antydde
`pip install -e .[dev]`, men `[tool.setuptools]`-sektionen pekade på
`py-modules = ["backend"]` — en död referens eftersom `backend.py`
inte finns på disk (grep visade noll förekomster av `from backend`
eller `import backend` i hela repot). Editable install har därmed
aldrig faktiskt registrerat något användbart.

## Beslut

Registrera `tooling`-paketet som en first-party-installable via
`setuptools.packages.find` och gör `pip install -e .` till en
del av venv-setup-flödet. Drop den döda `py-modules = ["backend"]`
i samma edit.

Konkret diff i `pyproject.toml`:

```toml
# FÖRE
[tool.setuptools]
py-modules = ["backend"]

# EFTER
[tool.setuptools.packages.find]
where = ["."]
include = ["tooling*"]
```

Konkret effekt:

- `scripts/sprintvakt_check.py` tappar sin `sys.path`-mutation och
  blir en tunn shim som importerar via standardvägen.
- `python -m tooling.sprintvakt_mcp.server` fungerar oavsett CWD så
  länge `pip install -e .` har körts i venv:n.
- Cursor MCP-config kan använda `python -m tooling.sprintvakt_mcp.server`
  rent (med `PYTHONPATH` som belt-and-braces tills alla utvecklare
  har kört editable install).
- `pyproject.toml` blir ärlig — den dokumenterar exakt vad som faktiskt
  installeras.

## Alternativ som övervägdes

| Alternativ | Bedömning |
| --- | --- |
| Bevara `sys.path`-hacken | Avslogs: anti-pattern, blockerar Cursor MCP-launch, gör import-ordningen oförutsägbar för dev-verktyg (ruff E402 kräver `noqa`). |
| `PYTHONPATH=.`-prefix vid varje invokation | Funkar lokalt men kräver att varje launcher (CI, Cursor MCP, dokumentation, dev-loop) sätter `PYTHONPATH`. Skört och spritt. |
| Lägg till `tooling/__init__.py` som tom fil (regular package) | Hjälper inte med top-level import utan installation. Plus: `tooling/` är en samling oberoende verktyg, inte ett single coherent package — namespace-mönster passar bättre. |
| `setuptools.packages.find` med editable install (detta förslag) | Standardmönster för Python-paket. En engångsregistrering per venv, sedan fungerar import oberoende av CWD. Belt-and-braces med `PYTHONPATH` i `.cursor/mcp.json` tills alla maskiner har kört `pip install -e .`. |

## Konsekvenser

Positiva:

- `scripts/sprintvakt_check.py` är ren utan import-hacks.
- Cursor MCP-server kan launchas av valfri Cursor-instans utan
  CWD-magi.
- `pyproject.toml` reflekterar verkligheten (`tooling*` installeras,
  inget annat).
- Framtida tooling-moduler under `tooling/`-rotet får automatisk
  import-väg via `packages.find`-globben.
- Cursor IDE kan indexera `tooling/` som första-parts-kod istället
  för okänd extern dependency.

Negativa:

- Nya utvecklare måste komma ihåg `pip install -e .` efter
  `pip install -r requirements.txt`. Mitigation: dokumenterat i
  `docs/sprintvakt-mcp.md` CLI-sektionen + AGENTS.md.
- CI-jobb som inte kör editable install kommer fortsätta crasha på
  `tooling`-imports. Mitigation: separat gap (CI-integration av
  sprintvakt-check) ska säkra att CI-stegen kör `pip install -e .`
  före import-anrop.

## Triggers för att ompröva

- Om `tooling/`-mappens scope växer till flera oberoende paket
  (t.ex. `tooling/sprintvakt_mcp/`, `tooling/scaffold_generator/`,
  `tooling/quality_eval/`), kan det vara värt att skifta till
  workspace-style monorepo med flera `pyproject.toml`. Tills dess
  räcker en single editable install.
- Om `backend.py` eller `backend/`-modulen någonsin lägg till på
  disk, ompröva om den ska in i `packages.find`-globben.

## Implementation (klar)

Landade i commit `90df708` på `jakob-be` (2026-05-25):

- `pyproject.toml` — dropp `py-modules = ["backend"]`, lägg till
  `[tool.setuptools.packages.find]` med `include = ["tooling*"]`.
- `scripts/sprintvakt_check.py` — bort `import sys`,
  `sys.path.insert`-block och `# noqa: E402`.
- `docs/sprintvakt-mcp.md` — ny rad om `pip install -e .` i
  CLI-sektionen.
- `tests/test_sprintvakt_check.py` — ny regression
  `test_sprintvakt_check_script_has_no_sys_path_hack`.

Verifierad efter merge: `pip install -e .` lyckades med
`sajtbyggaren-0.0.1` (editable wheel), 18 sprintvakt-tester gröna,
full pytest-svit grön, ruff 0 findings, MCP stdio-smoke OK.

## Vad ADR 0029 inte beslutar

- Ingen ändring i `requirements.txt` (oförändrad).
- Ingen ändring i andra `packages/`-paket (`packages/generation/**`
  har separat installations-modell idag).
- Ingen registrering av `backend`-modul eller `backoffice`-paket
  (separat ADR om de ska distribueras som installables).
- Ingen ny CI-konfiguration (planerad i separat gap för CI-integration
  av sprintvakt-check).
