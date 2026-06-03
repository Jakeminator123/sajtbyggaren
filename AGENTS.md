## Cursor Cloud specific instructions

### Codex-IDE agent parity

When working from Codex-IDE, act as a Cursor-compatible repo agent for this
repository. Treat `.cursor/BUGBOT.md` and every rule under `.cursor/rules/`
as active operating rules in addition to this file.

For non-trivial changes, keep `docs/product-operating-context.md` in view:
the product target is better small-business websites through the core loop
`prompt -> företagshemsida -> preview -> följdprompt -> ny version`.

For long Codex-IDE sessions with subagents, use
`docs/orchestrator-playbook.md` as the operating playbook. It coordinates the
existing Scout/Builder/Steward roles; it does not create a fourth fixed role.

Do not edit `.cursor/rules/` directly. Those files are generated mirrors; the
source lives under `governance/rules/`. If a rule needs to change, update the
governance source and run the rule sync check.

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

On Linux (Cloud Agent VMs), the venv package must be installed first.
On Ubuntu Noble use `sudo apt-get install -y python3-venv` when available;
if the meta-package is missing, install `python3.12-venv` explicitly before
the first `python3 -m venv .venv`. When neither apt package is available,
the VM update script falls back to `pip install virtualenv` and
`~/.local/bin/virtualenv .venv` (same outcome as `python3 -m venv`; user
installs land in `~/.local/bin`, which may be off `PATH` in non-login shells).
Activate with `source .venv/bin/activate`. The update script handles
this automatically.

### Running services

| Service           | Command                                                                     | Notes                                                                                                                                     |
| ----------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Backoffice        | `streamlit run backoffice.py --server.headless true`                        | Serves on port 8501                                                                                                                       |
| Engine run | `python scripts/dev_generate.py "your prompt"`                                   | Writes artifacts to `data/runs/`. Calls `briefModel` + `planningModel` when `OPENAI_API_KEY` is set; mock fallback otherwise.             |
| Builder MVP       | `python scripts/build_site.py --dossier examples/<slug>.project-input.json` | Real Next.js output under `../sajtbyggaren-output/.generated/<siteId>/` by default (override with `--generated-dir` or env `SAJTBYGGAREN_GENERATED_DIR`) + canonical artifacts under `data/runs/<runId>/`. Add `--skip-build` for fast iteration. |
| Viewser (operator UI) | `cd apps/viewser && npm install && cp .env.example .env.local && npm run dev` | Operator prototype on http://localhost:3000 (`VIEWSER_PREVIEW_MODE=local-next` in `.env.local`). API routes shell out to `scripts/build_site.py`, so the repo-root `.venv` must be active first. |

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
- The builder writes generated sites to `../sajtbyggaren-output/` by
  default (resolves to `/sajtbyggaren-output/` on Cloud Agent VMs). The
  update script creates this directory with open permissions. If tests
  fail with a permission error on that path, run
  `sudo mkdir -p /sajtbyggaren-output && sudo chmod 777 /sajtbyggaren-output`.
- Each `scripts/build_site.py` run writes the npm project under
  `<generated-dir>/<siteId>/builds/<timestamp>/`. For a manual `npm run dev`,
  `cd` into the newest `builds/*` directory, not the site root.
- Cloud Agent secrets often set `SAJTBYGGAREN_EVALS_DIR` (and
  `SAJTBYGGAREN_GENERATED_DIR`). That is fine for builder work, but
  `tests/test_cleanup_dev_artifacts.py::test_default_evals_dir_is_inside_data_evals_artifacts_mini`
  asserts the repo-default evals path — unset `SAJTBYGGAREN_EVALS_DIR` (or
  point it at `data/evals/artifacts/mini`) for a fully green full suite.
- Long-running dev servers (Next.js preview, Streamlit backoffice) should run
  under tmux on Cloud Agent VMs (portal config under
  `/exec-daemon/tmux.portal.conf`).
