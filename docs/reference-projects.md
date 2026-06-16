# Read-only reference projects

Fuller descriptions of the external reference folders named in
[`AGENTS.md`](../AGENTS.md) under "READ-ONLY reference projects". The hard rule
lives there: these folders are strictly read-only — never create, edit, delete,
rename, move, format, lint, commit or write to them in any way. This file only
explains what each contains and why we study it.

## `C:\Users\jakem\Desktop\openclaw\`

The operator's standalone OpenClaw gateway/assistant installation plus the
sajtmaskin integration (`sajtmaskin_agent.py`, `docs/sajtmaskin_docs/`,
`assistant/`, `src/`, `dist/`). This is the conductor/agent-role reference we
study to design Sajtbyggaren's own conductor-only OpenClaw — a reference, never
a build target.

## `C:\Users\jakem\dev\projects\sajtmaskin\`

The actual predecessor project: a Next.js app plus the `infra/openclaw/` Docker
gateway blueprint (Dockerfile, render.yaml, railway.toml,
`config/agents/sajtagenten/`, the `config/workspace/` markdown files, plus
`src/app/api/openclaw/`, `src/lib/openclaw/`, `src/components/openclaw/`). This
is the richest reference for an external Docker OpenClaw conductor.

## Any other folder named `sajtmaskin`

Wherever it appears on disk, treat it as read-only reference material too,
unless the operator explicitly says otherwise.

## Where the repo's own OpenClaw work lives

Sajtbyggaren's own OpenClaw work happens ONLY inside this repository:
`packages/generation/orchestration/openclaw/`, `openclaw-mvp/`, `apps/`,
`scripts/`. Never in the read-only folders above. If a change to the reference
material ever seems necessary, STOP and ask the operator first.
