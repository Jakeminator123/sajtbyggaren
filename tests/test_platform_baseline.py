"""Tests for the platform version baseline + drift checker (ADR 0037).

The baseline in ``governance/policies/platform-baseline.v1.json`` is the single
source of truth for runtime/dependency versions. ``scripts/check_platform_baseline.py``
must:

- pass (exit 0) on the live tree, because the ``enforced`` pins are uniform
  across ``apps/viewser/package.json`` + ``data/starters/*/package.json`` today;
- fail (exit 1) deterministically when an ``enforced`` pin drifts;
- treat ``pendingPropagation`` targets (engines/volta + @types/node bump + the
  pins that currently vary) as reportable-but-not-fatal until the reviewed
  step-4 ``--fix`` runs;
- align pins + inject engines/volta mechanically on ``--fix`` (idempotent).

Fixtures are built programmatically in ``tmp_path`` so the tests never write to
real ``package.json`` files (apps/viewser is off-limits in this lane).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.check_platform_baseline import (
    BASELINE_PATH,
    baseline_pins,
    check_package,
    collect_deps,
    fix_package,
    load_baseline,
    policy_consistency_errors,
    resolve_targets,
    run_check,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def baseline() -> dict:
    return load_baseline()


def _conformant_package(baseline: dict) -> dict[str, Any]:
    """A package.json that fully conforms to the baseline (enforced + pending)."""
    pins = baseline_pins(baseline)
    runtime = baseline["runtime"]
    return {
        "name": "fixture-site",
        "private": True,
        "dependencies": {
            "next": pins["next"],
            "react": pins["react"],
            "react-dom": pins["react-dom"],
            "lucide-react": pins["lucide-react"],
            "shadcn": pins["shadcn"],
            "class-variance-authority": pins["class-variance-authority"],
            "tailwind-merge": pins["tailwind-merge"],
            "clsx": pins["clsx"],
            "tw-animate-css": pins["tw-animate-css"],
            "@base-ui/react": pins["@base-ui/react"],
        },
        "devDependencies": {
            "@tailwindcss/postcss": pins["@tailwindcss/postcss"],
            "@types/node": pins["@types/node"],
            "eslint": pins["eslint"],
            "eslint-config-next": pins["eslint-config-next"],
            "prettier": pins["prettier"],
            "prettier-plugin-tailwindcss": pins["prettier-plugin-tailwindcss"],
            "tailwindcss": pins["tailwindcss"],
            "typescript": pins["typescript"],
        },
        "engines": {"node": runtime["node"]},
        "volta": {"node": runtime["voltaNode"]},
        "packageManager": f"npm@{runtime['npm'].split('.')[0]}.0.0",
    }


# ---------------------------------------------------------------------------
# Policy + schema
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_baseline_validates_against_schema():
    """The baseline policy must validate against its schema."""
    jsonschema = pytest.importorskip("jsonschema")
    baseline = load_baseline()
    schema_path = REPO_ROOT / "governance" / "schemas" / "platform-baseline.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(baseline)


@pytest.mark.governance
def test_policy_is_internally_consistent(baseline: dict):
    """Every baseline pin is classified, and every classified package exists."""
    assert policy_consistency_errors(baseline) == []


@pytest.mark.governance
def test_baseline_pins_node_24(baseline: dict):
    """ADR 0037: Node 24 LTS is the pinned standard."""
    assert baseline["runtime"]["node"].startswith("24")
    assert baseline["runtime"]["voltaNode"].startswith("24.")
    assert baseline["vercelSupport"]["node"] == "24"


@pytest.mark.governance
def test_no_workspace_or_catalog_in_baseline(baseline: dict):
    """ADR 0030 guard: the baseline must not introduce npm/pnpm workspaces.

    We assert on structure, not prose: the principles intentionally mention
    "workspace/catalog" to say we are NOT introducing them. The guard is that
    no top-level key declares a workspace/catalog dependency-management graph.
    """
    forbidden_keys = {"workspaces", "catalog", "catalogs", "pnpm"}
    assert forbidden_keys.isdisjoint(baseline.keys())


# ---------------------------------------------------------------------------
# check_package
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_conformant_package_has_no_errors_or_notes(baseline: dict):
    errors, notes = check_package(_conformant_package(baseline), baseline)
    assert errors == []
    assert notes == []


@pytest.mark.tooling
def test_enforced_pin_drift_is_a_hard_error(baseline: dict):
    pkg = _conformant_package(baseline)
    pkg["dependencies"]["next"] = "16.3.0"  # drift on an enforced pin
    errors, _ = check_package(pkg, baseline)
    assert any("next" in e for e in errors), errors


@pytest.mark.tooling
def test_pending_pin_drift_is_a_note_not_error(baseline: dict):
    pkg = _conformant_package(baseline)
    # @types/node is pendingPropagation; drifting it must NOT be a hard error.
    pkg["devDependencies"]["@types/node"] = "^20"
    errors, notes = check_package(pkg, baseline)
    assert errors == []
    assert any("@types/node" in n for n in notes), notes


@pytest.mark.tooling
def test_missing_engines_and_volta_are_pending_notes(baseline: dict):
    pkg = _conformant_package(baseline)
    pkg.pop("engines")
    pkg.pop("volta")
    errors, notes = check_package(pkg, baseline)
    assert errors == []
    assert any("engines.node" in n for n in notes)
    assert any("volta.node" in n for n in notes)


@pytest.mark.tooling
def test_missing_package_manager_is_pending_note(baseline: dict):
    """runtime.npm is now checked: a missing packageManager is a pending note
    (step 4 / corepack sets it), never a hard error."""
    pkg = _conformant_package(baseline)
    pkg.pop("packageManager")
    errors, notes = check_package(pkg, baseline)
    assert errors == []
    assert any("packageManager" in n for n in notes), notes


@pytest.mark.tooling
def test_mismatched_package_manager_npm_major_is_pending_note(baseline: dict):
    """A packageManager pinning a different npm major is reported as pending."""
    pkg = _conformant_package(baseline)
    pkg["packageManager"] = "npm@10.9.0"  # wrong major vs baseline 11.x
    errors, notes = check_package(pkg, baseline)
    assert errors == []
    assert any("packageManager" in n for n in notes), notes


@pytest.mark.tooling
def test_present_only_starter_without_a_pin_is_fine(baseline: dict):
    """A starter that does not use @base-ui/react (e.g. commerce-base) is fine."""
    pkg = _conformant_package(baseline)
    del pkg["dependencies"]["@base-ui/react"]
    errors, notes = check_package(pkg, baseline)
    assert errors == []


@pytest.mark.tooling
def test_collect_deps_merges_dependencies_and_dev(baseline: dict):
    deps = collect_deps(_conformant_package(baseline))
    assert "next" in deps
    assert "typescript" in deps


# ---------------------------------------------------------------------------
# fix_package
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_fix_aligns_pins_and_injects_engines_volta(baseline: dict):
    pins = baseline_pins(baseline)
    runtime = baseline["runtime"]
    drifted = {
        "name": "drifted",
        "dependencies": {"next": "16.1.0", "react": pins["react"]},
        "devDependencies": {"@types/node": "^20", "tailwindcss": "^4.0.14"},
    }
    fixed, changes = fix_package(drifted, baseline)
    assert fixed["dependencies"]["next"] == pins["next"]
    assert fixed["devDependencies"]["@types/node"] == pins["@types/node"]
    assert fixed["devDependencies"]["tailwindcss"] == pins["tailwindcss"]
    assert fixed["engines"]["node"] == runtime["node"]
    assert fixed["volta"]["node"] == runtime["voltaNode"]
    assert changes  # something changed


@pytest.mark.tooling
def test_fix_is_idempotent(baseline: dict):
    conformant = _conformant_package(baseline)
    fixed, changes = fix_package(conformant, baseline)
    assert changes == []
    assert fixed == conformant


@pytest.mark.tooling
def test_fix_never_creates_a_missing_pin(baseline: dict):
    """present-only: --fix must not add a pin that was not already there."""
    pkg = {"name": "x", "dependencies": {"next": "16.1.0"}}
    fixed, _ = fix_package(pkg, baseline)
    assert "lucide-react" not in fixed["dependencies"]


# ---------------------------------------------------------------------------
# resolve_targets
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_resolve_targets_literal_missing_is_error(tmp_path: Path):
    fake_baseline = {"targets": {"include": ["apps/viewser/package.json"], "comment": ""}}
    paths, errors = resolve_targets(fake_baseline, tmp_path)
    assert paths == []
    assert any("apps/viewser/package.json" in e for e in errors)


@pytest.mark.tooling
def test_resolve_targets_glob_skips_missing(tmp_path: Path):
    (tmp_path / "data" / "starters" / "a-base").mkdir(parents=True)
    (tmp_path / "data" / "starters" / "a-base" / "package.json").write_text("{}")
    # b-base has no package.json -> must be skipped silently
    (tmp_path / "data" / "starters" / "b-base").mkdir(parents=True)
    fake_baseline = {"targets": {"include": ["data/starters/*/package.json"], "comment": ""}}
    paths, errors = resolve_targets(fake_baseline, tmp_path)
    assert errors == []
    assert len(paths) == 1
    assert paths[0].name == "package.json"


# ---------------------------------------------------------------------------
# Live tree: the baseline must hold today
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_live_tree_check_passes(baseline: dict, capsys: pytest.CaptureFixture[str]):
    """--check must be green on the real repo: enforced pins are uniform across
    apps/viewser + starters today. This is the gate that other agents run.
    """
    assert run_check(baseline, REPO_ROOT) == 0


@pytest.mark.governance
def test_live_targets_include_viewser_and_starters(baseline: dict):
    paths, errors = resolve_targets(baseline, REPO_ROOT)
    assert errors == []
    rels = {p.relative_to(REPO_ROOT).as_posix() for p in paths}
    assert "apps/viewser/package.json" in rels
    assert any(r.startswith("data/starters/") for r in rels)


@pytest.mark.governance
def test_baseline_path_points_at_the_policy():
    assert BASELINE_PATH.name == "platform-baseline.v1.json"
    assert BASELINE_PATH.exists()


@pytest.mark.governance
def test_run_check_fails_when_a_starter_drifts(baseline: dict, tmp_path: Path):
    """Deterministic failure: copy a conformant target, drift an enforced pin,
    point a synthetic baseline at it, and assert exit 1.
    """
    starter = tmp_path / "data" / "starters" / "drift-base"
    starter.mkdir(parents=True)
    pkg = _conformant_package(baseline)
    pkg["dependencies"]["react"] = "19.0.0"  # enforced drift
    (starter / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

    synthetic = copy.deepcopy(baseline)
    synthetic["targets"]["include"] = ["data/starters/*/package.json"]
    assert run_check(synthetic, tmp_path) == 1
