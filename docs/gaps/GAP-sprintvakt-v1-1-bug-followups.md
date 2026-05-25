# GAP-sprintvakt-v1-1-bug-followups — Sprintvakt V1.1 follow-up: file-only gaps, dupe reservations, sys.path

- id: `GAP-sprintvakt-v1-1-bug-followups`
- type: `Gap/Guard`
- owner: `jakob`
- reviewer: `jakob`
- status: `queued`
- collisionRisk: `green`
- createdAt: `2026-05-24T23:52:13Z`
- updatedAt: `2026-05-24T23:52:13Z`

## Why now

Three AI bug review findings from PR #70 that do not block V1 coordination but should land before V2.

## Paths

- `tooling/sprintvakt_mcp/core.py`
- `scripts/sprintvakt_check.py`
- `tests/test_sprintvakt_check.py`

## Do not touch

- `scripts/build_site.py`
- `packages/generation/**`
- `apps/viewser/**`

## Acceptance criteria

- generate_agent_prompt resolves file-only gaps in docs/gaps/*.md
- reserve_paths replaces rather than appends entries for the same gapId
- scripts/sprintvakt_check.py imports tooling.sprintvakt_mcp via real package install or PYTHONPATH instead of sys.path mutation

## Checks

- `python scripts/sprintvakt_check.py`
- `python -m pytest tests/test_sprintvakt_check.py -q`
