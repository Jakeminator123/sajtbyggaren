## Cursor Cloud specific instructions

### Overview

This is a Python-only project (no Node.js/Docker needed). Three main components:

1. Governance validation — JSON policies validated against schemas
2. Streamlit backoffice — operator UI for governance editing
3. Mock engine run — 3-phase pipeline (understand, plan, build)

### Running services

| Service | Command | Notes |
|---------|---------|-------|
| Backoffice | `streamlit run backend.py --server.headless true` | Serves on port 8501 |
| Engine run (mock) | `python scripts/dev_generate.py "your prompt"` | Writes artifacts to `data/runs/` |

### Lint, test, validate

Commands are documented in the README under "Snabbstart". Key commands:

- Lint: `python3 -m ruff check .` (ruff is installed but not on PATH; invoke via python module)
- Tests: `python3 -m pytest tests/ -v`
- Governance validation: `python3 scripts/governance_validate.py && python3 scripts/rules_sync.py --check && python3 scripts/check_term_coverage.py`

### Gotchas

- The ruff binary is not on `$PATH` in this environment; always invoke as `python3 -m ruff check .` or `python3 -m ruff format .`.
- The existing codebase has 15 import-ordering lint errors (all isort-related). These are pre-existing and not blocking.
- No `.env` file is required to run the backoffice or mock engine. API keys are only needed for future real LLM sprints.
- All code identifiers and JSON field names must be in English; operator-facing text (docs, rules, UI labels) is in Swedish.
- The `check_term_coverage.py --strict` script flags capitalized phrases (backtick-quoted or bold in markdown) as potential domain terms. Avoid using uppercase multi-word phrases in backticks or bold in `.md` files unless they are registered in the naming dictionary.
