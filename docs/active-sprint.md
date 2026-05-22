# Active Sprint

Mall och initial plan för gemensamt arbete. Håll den kort. Om den blir en
parallell `current-focus.md` ska den förenklas.

## Milestone

Team Parallel Work v1.

## Backend Focus

- generation/run contracts
- preview/follow-up state
- quality/eval outputs

## Frontend Focus

- Viewser shell
- prompt input UI
- run status UI
- preview/follow-up UX using mocks

## Shared Contracts

- `generation-run.v1`
- `preview-state.v1` senare
- `followup-version.v1` senare

## Do Not Touch

- auth
- billing
- runtime deploy
- starter import
- registry activation
- B125 implementation unless explicitly selected

## Active Branches

- `docs/team-parallel-workflow-v1` - workflow docs and contracts.
- `backup-43-INNAN-SAMMARBETE` - backup from pre-collaboration local HEAD.

## Open PRs

- To be filled by Steward when PR exists.

## Blockers

- Frontend-medutvecklarens GitHub username is not documented yet.
- Shared TypeScript contract location is not decided yet; use docs contracts
  until a code location is chosen.

## Test Commands

```powershell
.\.venv\Scripts\python.exe scripts\rules_sync.py --check
.\.venv\Scripts\python.exe scripts\check_term_coverage.py --strict
```

## Merge Order

1. Workflow docs PR.
2. Small `contract/generation-run-v1` PR if runtime types or mocks are added.
3. Frontend mock UI PR.
4. Backend run-state/API PR.
5. Follow-up/version contract PR.
