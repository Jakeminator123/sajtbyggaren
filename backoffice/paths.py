"""Filesystem path constants used across the backoffice."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
POLICIES_DIR = GOVERNANCE_DIR / "policies"
SCHEMAS_DIR = GOVERNANCE_DIR / "schemas"
RULES_DIR = GOVERNANCE_DIR / "rules"
DECISIONS_DIR = GOVERNANCE_DIR / "decisions"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
CURSOR_RULES_DIR = REPO_ROOT / ".cursor" / "rules"
TESTS_DIR = REPO_ROOT / "tests"
DATA_DIR = REPO_ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"

# Canonical eval layout (post evals-folder-plan):
#   data/evals/summaries/ — small operator-facing JSON/MD reports.
#   data/evals/artifacts/ — heavy per-run work dirs (gitignored, retention-styrda).
EVALS_DIR = DATA_DIR / "evals"
EVALS_SUMMARIES_DIR = EVALS_DIR / "summaries"
EVALS_ARTIFACTS_DIR = EVALS_DIR / "artifacts"
EVALS_SUITE_SUMMARIES_DIR = EVALS_SUMMARIES_DIR / "suite"
EVALS_MANUAL_SCORECARDS_DIR = EVALS_SUMMARIES_DIR / "manual-scorecards"
EVALS_GOLDEN_PATH_SUMMARIES_DIR = EVALS_SUMMARIES_DIR / "golden-path"
EVALS_SCAFFOLD_PROBE_SUMMARIES_DIR = EVALS_SUMMARIES_DIR / "scaffold-probe"
EVALS_SUITE_ARTIFACTS_DIR = EVALS_ARTIFACTS_DIR / "suite"
EVALS_GOLDEN_PATH_ARTIFACTS_DIR = EVALS_ARTIFACTS_DIR / "golden-path"
EVALS_MINI_ARTIFACTS_DIR = EVALS_ARTIFACTS_DIR / "mini"

# Legacy locations preserved for read-fallback during the migration
# window. Backoffice cleanup uses the same constants to recognise old
# folders that operators may still have on disk after upgrading.
LEGACY_EVAL_RUNS_DIR = EVALS_DIR / "eval-runs"
LEGACY_MANUAL_SCORECARDS_DIR = EVALS_DIR / "manual-scorecards"
LEGACY_EVAL_GENERATED_DIR = EVALS_DIR / "generated"
LEGACY_GOLDEN_PATH_DIR = EVALS_DIR / "golden-path"
LEGACY_SCAFFOLD_PROBE_DIR = EVALS_DIR / "scaffold-probe"

# Backwards-compatible aliases. Existing imports (``EVAL_RUNS_DIR`` and
# ``MANUAL_SCORECARDS_DIR``) keep working but now resolve to the new
# canonical summaries location.
EVAL_RUNS_DIR = EVALS_SUITE_SUMMARIES_DIR
MANUAL_SCORECARDS_DIR = EVALS_MANUAL_SCORECARDS_DIR
