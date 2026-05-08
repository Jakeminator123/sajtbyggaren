## Cursor Cloud specific instructions

### Overview

The operator/governance/builder layer is Python. The **output** of the
builder is a Next.js project (TypeScript), so Node.js is required when you
actually run `scripts/build_site.py` end-to-end (it shells out to
`npm install` + `npm run build`). For pure governance/validation/test work
no Node.js is needed.

Four main components:

1. Governance validation — JSON policies validated against schemas
2. Streamlit backoffice — operator UI for governance editing
3. Mock engine run — 3-phase pipeline (understand, plan, build), no real codegen
4. Builder MVP — deterministic Next.js builder. Phase 1 (Site Brief) calls
 `briefModel` via OpenAI when `OPENAI_API_KEY` is set, otherwise falls back
 to a mock. Phase 2 (Plan) goes through shared
 `packages/generation/planning/produce_site_plan` (real `planningModel`
 with mock fallback). Phase 3 (Sprint 3A, ADR 0015) emits a deterministic
 codegen v1 manifest from `packages/generation/codegen/`, runs real
 Quality Gate checks (typecheck/route-scan/build-status/policy-compliance)
 from `packages/generation/quality_gate/`, and routes the result through
 a no-fix-applied Repair Pipeline in `packages/generation/repair/`. Real
 `codegenModel` LLM calls + mechanical fixes land in Sprint 3B.

### Python environment

A local virtualenv at `.venv/` is the recommended setup. `.venv/` is in
`.gitignore` and must never be committed.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On Linux (Cloud Agent VMs), the venv package must be installed first
(`sudo apt-get install -y python3-venv`). On Ubuntu Noble `python3.12-venv`
is not directly installable but `python3-venv` pulls it in transitively.
Activate with
`source .venv/bin/activate`. The update script handles this automatically.

### Running services

| Service           | Command                                                                     | Notes                                                                                                                                     |
| ----------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Backoffice        | `streamlit run backend.py --server.headless true`                           | Serves on port 8501                                                                                                                       |
| Engine run | `python scripts/dev_generate.py "your prompt"`                                   | Writes artifacts to `data/runs/`. Calls `briefModel` + `planningModel` when `OPENAI_API_KEY` is set; mock fallback otherwise.             |
| Builder MVP       | `python scripts/build_site.py --dossier examples/<slug>.project-input.json` | Real Next.js output under `.generated/<siteId>/` + canonical artifacts under `data/runs/<runId>/`. Add `--skip-build` for fast iteration. |

### Lint, test, validate

Commands are documented in the README under "Snabbstart". Key commands:

- Lint: `python -m ruff check .` (ruff is installed inside the venv)
- Tests: `python -m pytest tests/ -v`
- Governance validation: `python scripts/governance_validate.py && python scripts/rules_sync.py --check && python scripts/check_term_coverage.py --strict`

### Gotchas

- The ruff binary is shipped inside the venv. If the binary is not on
  `$PATH`, invoke via `python -m ruff check .` or `python -m ruff format .`.
- Run `python -m ruff check .` for the current lint count. The baseline
  is **0 findings** as of the post-Sprint-2B cleanup (`e8143cf` and later).
  Any new finding is a real bug to fix, not a `noqa` candidate — `noqa`
  comments must be backed by an ADR. Fix any new lint findings in dedicated
  `chore: ruff auto-fixes` commits, never mixed with feature work.
  `tests/test_docs_freshness.py` enforces that this number matches reality.
- `.env` is not required for backoffice, mock/real engine dry-runs, governance checks or
  the test suite. `OPENAI_API_KEY` is required when you want
  `scripts/build_site.py` and `scripts/dev_generate.py` to call the real
  `briefModel`/`planningModel`; without it both fall back to mock and write
  `briefSource=mock-no-key` into `site-brief.json` plus
  `planSource=mock-no-key` into `site-plan.json`.
- All code identifiers and JSON field names must be in English; operator-
  facing text (docs, rules, UI labels) is in Swedish.
- The `check_term_coverage.py --strict` script flags capitalized phrases
  (backtick-quoted or bold in markdown) as potential domain terms. Avoid
  using uppercase multi-word phrases in backticks or bold in `.md` files
  unless they are registered in the naming dictionary.
- Tests use `tmp_path` for run artefacts and no longer pollute
  `data/runs/`. If you see test runs leaving behind run directories, that
  is a regression of `e376439` and must be filed in
  `docs/known-issues.md`.
