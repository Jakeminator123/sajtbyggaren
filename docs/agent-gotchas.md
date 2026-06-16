# Agent-gotchas (miljöfällor)

Långa miljö- och verktygsfällor som tidigare låg i `AGENTS.md`. De flyttades
hit så att agentregeln förblir kort; innehållet är oförändrat. Korta
beteenderegler bor i [`AGENTS.md`](../AGENTS.md), körkommandon i
[`docs/agent-setup.md`](agent-setup.md).

## Gotchas

- The ruff binary is shipped inside the venv. If the binary is not on
  `$PATH`, invoke via `python -m ruff check .` or `python -m ruff format .`.
- The ruff baseline finding count and the no-`noqa` rule are owned by
  `AGENTS.md` (parsed by `tests/test_docs_freshness.py`). When a cleanup
  commit changes the count, update `AGENTS.md` in the same commit. Fix any
  new lint findings in dedicated `chore: ruff auto-fixes` commits, never
  mixed with feature work.
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
- Cloud Agent secrets often inject `VIEWSER_PREVIEW_MODE=vercel-sandbox`
  (Vercel sandbox). That wins over `apps/viewser/.env.local`, since
  `process.env` beats dotenv, so local preview (`POST /api/preview/<siteId>`)
  returns `vercel_auth` even though `.env.local` says `local-next` — unless
  you start Viewser with an explicit override, e.g.
  `VIEWSER_PREVIEW_MODE=local-next npm run dev` (tmux session `viewser-dev`).
  Vercel sandbox preview still needs a fresh `VERCEL_OIDC_TOKEN` from
  `vercel env pull apps/viewser/.env.vercel.local`. That pull (and the
  auto-refresh in `scripts/dev.mjs`) runs with cwd = repo root, so `vercel link`
  must be run ONCE from the repo root — it creates a monorepo link at
  `.vercel/repo.json` mapping the project to `apps/viewser`. A link made inside
  `apps/viewser/` is not found from the root and the refresh silently degrades.
- Cloud Agent secrets often set `SAJTBYGGAREN_EVALS_DIR` (and
  `SAJTBYGGAREN_GENERATED_DIR`). That is fine for builder work, but
  `tests/test_cleanup_dev_artifacts.py::test_default_evals_dir_is_inside_data_evals_artifacts_mini`
  asserts the repo-default evals path — unset `SAJTBYGGAREN_EVALS_DIR` (or
  point it at `data/evals/artifacts/mini`) for a fully green full suite.
- Long-running dev servers (Next.js preview, Streamlit backoffice) should run
  under tmux on Cloud Agent VMs (portal config under
  `/exec-daemon/tmux.portal.conf`).
- Stop Viewser on port 3000 before `python -m pytest tests/`: otherwise
  `test_api_prompt_smoke` (which starts its own Next dev server) flakes /
  collides on an already-heavy suite. Run the full suite first, then start
  `npm run dev` in `apps/viewser`. (Same coexistence note as the Windows
  orphan gotcha above — applies to Cloud VMs too.)
- Killing leftover Sajtbyggaren node processes (Windows) — the easy-fix: run
  `kill-dev-trees.bat` (repo root) **as administrator**. It tree-kills only
  Sajtbyggaren-scoped node trees (path token, or `next start`/`next dev` on the
  preview port range, or a matching port listener). Run it elevated: without
  admin the script often cannot read other processes' command lines (especially
  after UAC changes, or when a process runs at a different integrity level), so
  the match whitelist sees empty cmdlines and reports "ingen matchar" even when
  Sajtbyggaren processes exist. Make a shortcut to the `.bat` with "Run as
  administrator" ticked. This is the canonical "kill all my dev/preview node"
  recovery after an interrupted `npm run dev` or an orphaned preview server.

## Vercel- och Viewser-detaljer

- Operator grant (Jakob, 2026-06-02; utökad 2026-06-03): the agent has standing
  rights to read and edit ALL `.env*` files **anywhere in the repo** (repo root,
  `apps/viewser/`, and any subfolder) plus `.cursorignore`, and the `.vercel/`
  and `.cursor/` folders, as part of builder/preview/orchestration work. Never
  print real secret values in replies, and never commit `.env*` or
  `.cursor/mcp.json` (they stay gitignored). To run the vercel-sandbox preview
  locally, the dev process needs a fresh `VERCEL_OIDC_TOKEN` (`vercel env pull
  apps/viewser/.env.vercel.local`, ~12h TTL) in its environment plus
  `VIEWSER_PREVIEW_MODE=vercel-sandbox`.
