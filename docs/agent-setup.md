# Agent-setup (miljö, tjänster, kommandon)

Uppslagsmanual för att köra Sajtbyggaren lokalt och på Cloud Agent-VM:er.
Detta är medvetet utlyft ur `AGENTS.md` så att agentregeln förblir kort.
Korta beteenderegler bor i [`AGENTS.md`](../AGENTS.md); miljöfällor i
[`docs/agent-gotchas.md`](agent-gotchas.md).

## Overview

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

## Python environment

A local virtualenv at `.venv/` is the recommended setup. `.venv/` is in
`.gitignore` and must never be committed.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On Linux (Cloud Agent VMs), the venv package must be installed first.
On Ubuntu Noble run `sudo apt-get update` FIRST (on a fresh VM both
`python3-venv` and `python3.12-venv` report "no installation candidate"
until the package lists are refreshed), then `sudo apt-get install -y
python3-venv`. If the meta-package is still missing, install
`python3.12-venv` explicitly before the first `python3 -m venv .venv`.
When neither apt package is available,
the VM update script falls back to `pip install virtualenv` and
`~/.local/bin/virtualenv .venv` (same outcome as `python3 -m venv`; user
installs land in `~/.local/bin`, which may be off the shell search path in
non-login shells).
Activate with `source .venv/bin/activate`. The update script handles
this automatically.

## Running services

| Service           | Command                                                                     | Notes                                                                                                                                     |
| ----------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Backoffice        | `streamlit run backoffice.py --server.headless true`                        | Serves on port 8501                                                                                                                       |
| Engine run | `python scripts/dev_generate.py "your prompt"`                                   | Writes artifacts to `data/runs/`. Calls `briefModel` + `planningModel` when `OPENAI_API_KEY` is set; mock fallback otherwise.             |
| Builder MVP       | `python scripts/build_site.py --dossier examples/<slug>.project-input.json` | Real Next.js output under `../sajtbyggaren-output/.generated/<siteId>/` by default (override with `--generated-dir` or env `SAJTBYGGAREN_GENERATED_DIR`) + canonical artifacts under `data/runs/<runId>/`. Add `--skip-build` for fast iteration. |
| Viewser (operator UI) | `cd apps/viewser && npm install && cp .env.example .env.local && npm run dev` | Operator prototype on http://localhost:3000 (`VIEWSER_PREVIEW_MODE=local-next` in `.env.local`). API routes shell out to `scripts/build_site.py`, so the repo-root `.venv` must be active first. |

## Lint, test, validate

Commands are documented in the README under "Snabbstart". Key commands:

- Lint: `python -m ruff check .` (ruff is installed inside the venv). The
  ruff baseline (current finding count and the no-`noqa` rule) is owned by
  `AGENTS.md` — see the "Lint, test och validering" section there.
- Tests: targeted suites for the files/packages you changed are the local
  default before commit (operator decision 2026-06-11), e.g.
  `python -m pytest tests/test_<area>*.py -q` or the core lane
  `python -m pytest -m core -q`. The FULL suite runs in CI on every PR
  (governance workflow) and remains the merge gate. Run the full suite
  locally only for broad changes (multiple packages) or on explicit request,
  and then in parallel: `python -m pytest tests/ -q -n auto` (pytest-xdist;
  see `docs/testing.md`).
- Governance validation: `python scripts/governance_validate.py && python scripts/rules_sync.py --check && python scripts/check_term_coverage.py --strict`
