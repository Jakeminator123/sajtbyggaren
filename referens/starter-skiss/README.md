# Sajtmaskin Next Control Starter

This is a clean control shell for a new Sajtmaskin rebuild. It is not the full app. Its job is to make the next repo understandable before the old code is migrated.

## Principle

JSON policies are source of truth. Docs explain. Cursor rules enforce. Code imports policy through `packages/policies`.

## Start here

```bash
npm run governance:validate
npm run rules:sync
```

Then migrate code in this order:

1. Generation core from the chosen April baseline.
2. Policy loaders and page quality traits.
3. Builder lifecycle.
4. Preview Runtime adapter, preferably StackBlitz first if that is the new target.
5. Evals and promotion gate.
6. UI/API last.

## Core source-of-truth files

- `governance/policies/page-quality-traits.v1.json` - ten quality traits for a 9/10 business website.
- `governance/policies/llm-flow-concepts.v1.json` - canonical LLM flow and glossary.
- `governance/policies/naming-dictionary.v1.json` - canonical terms and forbidden aliases.
- `governance/policies/repo-boundaries.v1.json` - folder ownership and import boundaries.
- `.cursor/rules` - agent-facing rules mirrored from `governance/rules`.

## Non-negotiable rule

If a concept affects several folders, it must exist in governance before it exists in code.
