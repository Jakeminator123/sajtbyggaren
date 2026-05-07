# Repo map

```text
sajtmaskin-next-control/
  .cursor/rules/                  # Cursor agent rules mirrored from governance/rules
  governance/
    policies/                     # JSON truth: quality, LLM flow, naming, boundaries
    schemas/                      # JSON schemas for policies
    rules/                        # Human-editable rule source
    decisions/                    # Architecture Decision Records
  docs/
    architecture/                 # Architecture explanations
    terminology.md                # Human glossary, derived from naming policy
    migration-plan.md             # Controlled migration order from old repo
    agent-handbook.md             # How AI agents should work in this repo
  apps/
    web/                          # UI shell only
    api/                          # API/auth/transport only
  packages/
    generation/                   # LLM flow and codegen
    builder/                      # lifecycle, state, promotion
    preview-runtime/              # StackBlitz/local/VM adapter boundary
    policies/                     # typed access to governance JSON
    shared/                       # shared primitive types
  tests/evals/                    # 9/10 quality gate and regressions
  scripts/                        # sync and validation scripts
```

## Ownership rule

A folder may own only what `governance/policies/repo-boundaries.v1.json` says it owns.

## Policy rule

A JSON policy may be referenced from many places, but it must not be duplicated.
