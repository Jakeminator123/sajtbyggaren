# Bugbot review rules for sajtbyggaren

> **Status: passive.** Cursor Bugbot is not confirmed active on this repo
> yet. These rules are written so they can be activated by toggling
> Bugbot on in the repository settings - no rewrites needed. Until then
> they double as a manual checklist for the ro-review-agent role in
> `docs/agent-handbook.md` under "Standard loop".

## Always flag

- **Scope creep.** PR description must list changed files. Anything
  changed but not listed = blocker. Cross-check the scope and
  what-changed sections in `.github/pull_request_template.md` against
  the actual diff.
- **Secrets or generated artefacts.** Any `.env*` (other than
  `.env.example`), `*.pem`, `node_modules/`, `.next/`, `.generated/`,
  `data/runs/<runId>/` written to the PR = blocker.
- **Direct edits to `.cursor/rules/`.** These are mirrors. Source lives
  under `governance/rules/`. Direct edits = blocker.
- **New canonical terms without ADR.** Capitalized multi-word phrases in
  backticks or bold in markdown trigger `scripts/check_term_coverage.py`.
  A new term needs either an entry in `naming-dictionary.v1.json` (with
  ADR) or a registration under `COMMON_WORDS` in the term-coverage
  script.

## Starter-specific rules

Applies to anything under `data/starters/`:

- **Do not touch `data/starters/commerce-base/` or
  `data/starters/marketing-base/`** without a referenced ADR in the PR
  description. These are vendored or load-bearing bases - changes need
  governance.
- **No hardcoded customer copy.** Starters must stay neutral. Customer-
  specific text belongs in scaffold/dossier output, not in the base.
- **No external deploy CTAs.** No `vercel.com/templates/...`, no
  `github.com/<vendor>/...` "view the source" runtime links, no
  "Created by <vendor>"-style attribution in runtime UI. Upstream
  attribution lives in `README.md` and `license.md` only.
- **Must build without real env.** `npm ci && npm run build` must pass
  with empty or example env values. Auth, database, payment, CMS or
  vendor API keys must not be required for the build.

## Mapping and routing risk

- **`SCAFFOLD_TO_STARTER` in `packages/generation/planning/plan.py`.**
  Any change to this dict needs an ADR in the same PR. Mapping flips
  without route-emission support (B13) are the failure mode B20 hit.
- **`scripts/build_site.py` route hardcoding.** Watch for new hardcoded
  routes like `/tjanster`, `/om-oss`, `/kontakt`. Route generation must
  read from `routes.json` in the scaffold once B13 lands.

## Draft / ready discipline

- **Draft PR marked ready with known blockers** = blocker. If the PR
  description lists items under "Known risks / blockers" that are not
  resolved, the PR should stay draft.
- **Mainline-steward push to `main`** is only allowed for docs,
  governance, checklists, cleanup, and the lightweight check scripts.
  Anything that touches `apps/`, `packages/`, `data/starters/<starter>/`
  or `scripts/build_site.py` belongs on a feature branch.

## Cross-references

- `docs/current-focus.md` - current queue. PR must align.
- `docs/agent-handbook.md` - standard loop, reviewer checklist, parallel-
  agent rules.
- `governance/rules/branch-discipline.md` - branch and push rules.
- `docs/known-issues.md` - active B-IDs and blockers.
