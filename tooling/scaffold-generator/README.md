# Scaffold generator

CLI that turns a single declarative **spec file** into the six required scaffold files plus N variant files, validated against the same schemas the runtime uses.

This exists so we can batch-add new scaffolds in week 2/3/4 without copy-pasting six JSON files per scaffold. Spec format is intentionally narrow: every field maps 1:1 to something the runtime already reads.

## Quick start

```bash
# From repo root, with .venv activated
python tooling/scaffold-generator/generate.py restaurant-hospitality
# Writes packages/generation/orchestration/scaffolds/restaurant-hospitality/{6 files + variants/*.json}
# Validates each file against governance/schemas/*.json
# Exit code 0 = all files written and valid
```

Re-running with the same spec **overwrites every generated file in place** (idempotent for unchanged specs, destructive for handedited scaffolds). See the next section for the source-of-truth contract.

## Source-of-truth contract

A spec is a **bootstrap seed**, not a live source of truth. The intended lifecycle is:

1. Author a spec under `spec/<id>.json`.
2. Run `generate.py <id>` once to produce the initial scaffold skeleton under `packages/generation/orchestration/scaffolds/<id>/`.
3. Hand-edit the generated files during PR review and follow-up batches — section IDs may be renamed, `compatible-dossiers.recommended` may be expanded as new dossiers land, variants may be added.
4. **After step 3, the on-disk scaffold files are authoritative**; the spec is a historical record of the initial seed.

> [!WARNING]
> The generator has **no drift detection or three-way merge**. Re-running `generate.py <id>` on a hand-edited scaffold will silently overwrite handedits with stale spec content and leave new variant files orphaned (they are never deleted by the generator). Update the spec to match the new disk state *before* re-running, or do not re-run at all.

Empirically, the `restaurant-hospitality` spec was already out of sync with its scaffold after the Week 1 batch 2 + batch 3 follow-ups (section `opening-hours` was renamed to `hours-block`, `compatible-dossiers.recommended` grew from 1 → 5 dossiers, a 4th `midnight-bar` variant was added). The spec has been re-synced to the post-batch-3 disk state as a one-shot defensive update so that an accidental `generate.py restaurant-hospitality` run does not regress those decisions, but the long-term contract above still applies.

## Spec format

A spec is a single JSON file under `tooling/scaffold-generator/spec/<scaffoldId>.json`. See `_TEMPLATE.json` for the full annotated structure and `restaurant-hospitality.json` for a real example.

Required top-level keys:

| Key | Type | Purpose |
|---|---|---|
| `id` | string | scaffold id, matches directory name |
| `label` | string | human-readable label |
| `description` | string | one-sentence scope, drives selection profile + governance docs |
| `rationale` | string | one-sentence reason this scaffold exists in the registry |
| `buildIntent` | array | scaffold.json `buildIntent` |
| `primaryJobs` | array | scaffold.json `primaryJobs` |
| `defaultPageCount` | int | scaffold.json `defaultPageCount` |
| `routes` | array | each `{ id, path, label, required, optional? }` for routes.json |
| `sectionsPerRoute` | object | route-id → array of `{ id, required, dossier?, fixedOrder? }` for sections.json |
| `qualityContract` | object | `{ scorecardWeights, mustPass, avoid }` for quality-contract.json |
| `compatibleDossiers` | object | `{ required, recommended, conditional, disallowedByDefault }` |
| `selectionProfile` | object | `{ embeddingText, semanticSignals, negativeSignals, llmClassificationHints, minConfidence, requiresTieBreakWhenWithin }` |
| `variants` | array | each `{ id, label, description, tokens, tone }` |

Optional:

| Key | Default | Purpose |
|---|---|---|
| `supportsSinglePage` | `false` | |
| `supportsMultiPage` | `true` | |
| `supportsAppFeatures` | `false` | |
| `scaffoldVersion` | `"1.0.0"` | |

## What the generator does NOT do

1. **It does not modify `scripts/build_site.py`, `packages/generation/discovery/resolve.py` or `packages/generation/planning/plan.py`.** Those are off-limits for the UI branch per `governance/rules/branch-scope-ui-ux.md`. After generating a scaffold, the operator still needs to coordinate the runtime extension (see `docs/scaffold-runtime-extension-needed.md`) with the backend owner before end-to-end execution works.
2. **It does not update `governance/policies/capability-map.v1.json`** with new capabilities/dossiers. That is a human decision that needs ADR review.
3. **It does not auto-create dossiers.** A scaffold can reference dossiers in `compatibleDossiers.required`, but the dossier itself lives under `packages/generation/orchestration/dossiers/{soft,hard}/<id>/` and is built manually with its own `manifest.json` + `instructions.md`.

The generator's scope is exactly: *take a spec, produce schema-valid scaffold files*. Everything beyond that is human or Jakob.

## How to add a new scaffold

1. Copy `spec/_TEMPLATE.json` to `spec/<your-scaffold-id>.json`.
2. Fill in every required field. Use existing specs as reference (`restaurant-hospitality.json`).
3. Run `python tooling/scaffold-generator/generate.py <your-scaffold-id>`.
4. Inspect the generated files in `packages/generation/orchestration/scaffolds/<your-scaffold-id>/`.
5. Run the four guards from repo root: `python scripts/governance_validate.py && python scripts/rules_sync.py --check && python scripts/check_term_coverage.py --strict && python -m ruff check .`
6. If your scaffold introduces a new entry that should appear in `governance/policies/scaffold-contract.v1.json:primaryScaffoldRegistry`, add it manually with an ADR.
7. If your scaffold uses capabilities not already in `capability-map.v1.json`, add them manually too.
8. If your scaffold introduces route ids beyond `{home, services, products, about, contact, menu, booking}`, file a backend hand-off so the section-renderer registry gains entries.

## Test

```bash
python tooling/scaffold-generator/generate.py --check restaurant-hospitality
```

`--check` runs the generator in dry-run mode: it builds the files in memory, validates against schemas, but does NOT write to disk. Exit code 0 = spec is valid and would produce schema-valid output.

`--check` does NOT verify that the generated output matches the existing files on disk — it only validates the spec against schemas. A drift-detection mode (compare generated output vs. disk, exit non-zero on any difference) would be useful for teams that want to keep spec = disk strictly aligned (Strategy A); it is intentionally not built today because the project follows Strategy B per the source-of-truth contract above.

## Why JSON spec instead of YAML

- Zero new dependencies (the repo only has PyYAML transitively through pytest; nothing in the runtime uses it).
- Same format as the output, so diff-readability stays high.
- `jq`-friendly for ad-hoc spec inspection.
- No YAML-anchor / tab-vs-space footguns.
