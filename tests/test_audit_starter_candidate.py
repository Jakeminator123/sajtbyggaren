"""Tests for scripts/audit_starter_candidate.py.

The auditor must remain a pure read-only tool. These tests therefore
build their fixtures programmatically inside ``tmp_path`` instead of
pointing at any real ``data/starters/`` directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from scripts.audit_starter_candidate import (
    SCHEMA_VERSION,
    VALID_CLASSIFICATIONS,
    audit_candidate,
    main,
)

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


_BASELINE_PACKAGE_JSON: dict[str, Any] = {
    "name": "ready-candidate",
    "version": "0.1.0",
    "private": True,
    "scripts": {
        "dev": "next dev",
        "build": "next build",
        "start": "next start",
        "lint": "eslint",
        "prettier:check": "prettier --check .",
    },
    "dependencies": {
        "next": "16.2.6",
        "react": "19.2.4",
        "react-dom": "19.2.4",
        "lucide-react": "^1.14.0",
        "clsx": "^2.1.1",
        "tailwind-merge": "^3.5.0",
    },
    "devDependencies": {
        "@types/node": "^20",
        "@types/react": "^19",
        "@types/react-dom": "^19",
        "eslint": "^9",
        "eslint-config-next": "16.2.6",
        "postcss": "^8.5.10",
        "prettier": "^3.8.3",
        "tailwindcss": "^4",
        "typescript": "^5",
    },
}


_BASELINE_TSCONFIG: dict[str, Any] = {
    "compilerOptions": {
        "target": "ES2017",
        "strict": True,
        "esModuleInterop": True,
        "module": "esnext",
        "moduleResolution": "bundler",
        "resolveJsonModule": True,
        "isolatedModules": True,
        "jsx": "react-jsx",
    },
    "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
    "exclude": ["node_modules"],
}


_BASELINE_COMPONENTS_JSON: dict[str, Any] = {
    "$schema": "https://ui.shadcn.com/schema.json",
    "style": "base-nova",
    "rsc": True,
    "tsx": True,
    "tailwind": {
        "config": "",
        "css": "app/globals.css",
        "baseColor": "neutral",
        "cssVariables": True,
        "prefix": "",
    },
    "iconLibrary": "lucide",
    "rtl": False,
    "aliases": {
        "components": "@/components",
        "utils": "@/lib/utils",
    },
}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _ready_candidate(root: Path) -> Path:
    """Build a minimum viable starter-candidate-ready fixture."""
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "package.json", _BASELINE_PACKAGE_JSON)
    _write_json(root / "tsconfig.json", _BASELINE_TSCONFIG)
    _write_json(root / "components.json", _BASELINE_COMPONENTS_JSON)
    (root / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (root / ".env.example").write_text("# example\n", encoding="utf-8")
    (root / ".gitignore").write_text(".env\nnode_modules\n.next\n", encoding="utf-8")
    (root / "app").mkdir(exist_ok=True)
    (root / "app" / "page.tsx").write_text(
        "export default function Page() { return null }\n", encoding="utf-8"
    )
    return root


def _modify_package_json(root: Path, mutator) -> None:
    pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    mutator(pkg)
    _write_json(root / "package.json", pkg)


# ---------------------------------------------------------------------------
# Sanity / structure
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_classification_set_is_locked() -> None:
    assert set(VALID_CLASSIFICATIONS) == {
        "starter-candidate-ready",
        "needs-cleanup",
        "too-integrated",
        "better-as-dossier",
        "reference-only",
        "blocked",
    }


@pytest.mark.tooling
def test_audit_returns_blocked_for_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    result = audit_candidate(missing)
    assert result.classification == "blocked"
    assert any("does not exist" in blocker for blocker in result.blockers)
    assert result.next_actions, (
        "blocked early-return path must still populate next_actions so the "
        "operator gets the same guidance as a normal blocked classification"
    )
    assert any("Fix every blocker" in action for action in result.next_actions)
    assert any("Never run this script" in action for action in result.next_actions)


@pytest.mark.tooling
def test_audit_returns_blocked_for_file_path(tmp_path: Path) -> None:
    candidate = tmp_path / "not-a-dir"
    candidate.write_text("hello\n", encoding="utf-8")
    result = audit_candidate(candidate)
    assert result.classification == "blocked"
    assert any("not a directory" in blocker for blocker in result.blockers)
    assert result.next_actions, (
        "not-a-directory early-return path must still populate next_actions"
    )
    assert any("Fix every blocker" in action for action in result.next_actions)
    assert any("Never run this script" in action for action in result.next_actions)


# ---------------------------------------------------------------------------
# Core scenarios required by Starter Candidate Auditor v1
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_ready_starter_classifies_as_ready(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "ready")
    result = audit_candidate(candidate)
    assert result.classification == "starter-candidate-ready", (
        f"unexpected warnings: {result.warnings}, blockers: {result.blockers}"
    )
    assert result.blockers == []
    assert result.warnings == []
    assert "dev" in result.scripts_present
    assert "build" in result.scripts_present
    assert "start" in result.scripts_present
    assert result.integrations == {}
    assert "reference-only" not in result.demo_signals


@pytest.mark.tooling
def test_pnpm_lock_triggers_cleanup_warning(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "pnpm")
    (candidate / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n", encoding="utf-8")
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert "pnpm-lock.yaml" in result.files_disallowed
    assert any("pnpm-lock.yaml" in warning for warning in result.warnings)


@pytest.mark.tooling
def test_yarn_lock_triggers_cleanup_warning(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "yarn")
    (candidate / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert "yarn.lock" in result.files_disallowed
    assert any("yarn.lock" in warning for warning in result.warnings)


@pytest.mark.tooling
def test_env_secret_blocks_import(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "leaky")
    (candidate / ".env").write_text(
        "STRIPE_SECRET_KEY=sk_live_VERY_REAL_TOKEN\n", encoding="utf-8"
    )
    result = audit_candidate(candidate)
    assert result.classification == "blocked"
    assert ".env" in result.files_disallowed
    assert any(".env present" in blocker for blocker in result.blockers)


@pytest.mark.tooling
def test_auth_dependency_marks_too_integrated(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "auth")

    def add_auth(pkg: dict[str, Any]) -> None:
        pkg["dependencies"]["next-auth"] = "^5.0.0"

    _modify_package_json(candidate, add_auth)
    result = audit_candidate(candidate)
    assert result.classification == "too-integrated"
    assert "auth" in result.integrations
    assert "next-auth" in result.integrations["auth"]


@pytest.mark.tooling
def test_database_dependency_marks_too_integrated(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "db")

    def add_db(pkg: dict[str, Any]) -> None:
        pkg["dependencies"]["@prisma/client"] = "^5.0.0"
        pkg["devDependencies"]["prisma"] = "^5.0.0"

    _modify_package_json(candidate, add_db)
    result = audit_candidate(candidate)
    assert result.classification == "too-integrated"
    assert "database" in result.integrations
    assert "@prisma/client" in result.integrations["database"]
    assert "prisma" in result.integrations["database"]


@pytest.mark.tooling
def test_analytics_dependency_marks_better_as_dossier(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "analytics")

    def add_analytics(pkg: dict[str, Any]) -> None:
        pkg["dependencies"]["@vercel/analytics"] = "^1.4.0"

    _modify_package_json(candidate, add_analytics)
    result = audit_candidate(candidate)
    assert result.classification == "better-as-dossier"
    assert "analytics" in result.integrations
    assert "@vercel/analytics" in result.integrations["analytics"]


@pytest.mark.tooling
def test_missing_components_json_triggers_cleanup(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "no-shadcn")
    (candidate / "components.json").unlink()
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert any("components.json" in warning for warning in result.warnings)
    assert result.detected_stack["shadcn"] == {"componentsJsonPresent": False}


@pytest.mark.tooling
def test_missing_package_lock_triggers_cleanup(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "no-lock")
    (candidate / "package-lock.json").unlink()
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert any("package-lock.json" in warning for warning in result.warnings)


# ---------------------------------------------------------------------------
# Additional guardrails: stack, scripts, demo-signals
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_old_next_major_triggers_warning(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "old-next")

    def downgrade(pkg: dict[str, Any]) -> None:
        pkg["dependencies"]["next"] = "^14.0.0"

    _modify_package_json(candidate, downgrade)
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert any(
        "next major 14" in warning and "below desired 16" in warning
        for warning in result.warnings
    )


@pytest.mark.tooling
def test_old_tailwind_major_triggers_warning(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "old-tw")

    def downgrade(pkg: dict[str, Any]) -> None:
        pkg["devDependencies"]["tailwindcss"] = "^3.4.0"

    _modify_package_json(candidate, downgrade)
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert any(
        "tailwind major 3" in warning and "below desired 4" in warning
        for warning in result.warnings
    )


@pytest.mark.tooling
def test_typescript_strict_false_triggers_warning(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "loose-ts")
    tsconfig = json.loads((candidate / "tsconfig.json").read_text(encoding="utf-8"))
    tsconfig["compilerOptions"]["strict"] = False
    _write_json(candidate / "tsconfig.json", tsconfig)
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert any("strict is false" in warning for warning in result.warnings)


@pytest.mark.tooling
def test_missing_required_script_triggers_warning(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "no-build")

    def remove_build(pkg: dict[str, Any]) -> None:
        del pkg["scripts"]["build"]

    _modify_package_json(candidate, remove_build)
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert "build" in result.scripts_missing
    assert any("missing required npm script: build" in w for w in result.warnings)


@pytest.mark.tooling
def test_demo_markers_classify_as_reference_only(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "demo")
    (candidate / "README.md").write_text(
        "# Example\n\nDeploy on Vercel and view source on GitHub.\n",
        encoding="utf-8",
    )
    result = audit_candidate(candidate)
    assert result.classification == "reference-only"
    assert "deploy on vercel" in result.demo_signals
    assert "view source on github" in result.demo_signals


@pytest.mark.tooling
def test_nested_git_blocks_import(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "nested-git")
    (candidate / ".git").mkdir()
    (candidate / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n", encoding="utf-8"
    )
    result = audit_candidate(candidate)
    assert result.classification == "blocked"
    assert any("nested .git" in blocker for blocker in result.blockers)


@pytest.mark.tooling
def test_tracked_node_modules_triggers_cleanup(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "tracked-nm")
    (candidate / "node_modules").mkdir()
    (candidate / "node_modules" / "marker").write_text("x", encoding="utf-8")
    result = audit_candidate(candidate)
    assert result.classification == "needs-cleanup"
    assert "node_modules/" in result.files_disallowed


@pytest.mark.tooling
def test_nested_tracked_artefact_uses_trailing_slash_consistently(tmp_path: Path) -> None:
    """Nested tracked artefacts must be stored with the same trailing-slash
    convention as top-level entries so the dedup check inside
    ``_audit_disallowed_artefacts`` can actually compare them.
    """
    candidate = _ready_candidate(tmp_path / "nested-nm")
    (candidate / "packages" / "a" / "node_modules").mkdir(parents=True)
    (candidate / "packages" / "a" / "node_modules" / "marker").write_text(
        "x", encoding="utf-8"
    )
    result = audit_candidate(candidate)
    assert "packages/a/node_modules/" in result.files_disallowed
    assert result.files_disallowed.count("packages/a/node_modules/") == 1


@pytest.mark.tooling
def test_nested_artefact_walk_handles_unresolved_root(tmp_path: Path) -> None:
    """Regression: ``_audit_disallowed_artefacts`` must resolve ``root``
    before calling ``relative_to``. Path.relative_to is a lexical
    operation, so passing a root that contains ``..`` segments would
    fail to match a resolved ``current`` and raise ``ValueError``. The
    helper at ``_relative_posix`` already resolves both sides; this
    function must do the same.
    """
    from scripts.audit_starter_candidate import (
        AuditResult,
        _audit_disallowed_artefacts,
    )

    candidate = _ready_candidate(tmp_path / "unresolved")
    (candidate / "packages" / "a" / "node_modules").mkdir(parents=True)

    unresolved_root = tmp_path / "unresolved" / ".." / "unresolved"
    assert ".." in unresolved_root.parts

    result = AuditResult(candidate_path=candidate.resolve())
    _audit_disallowed_artefacts(unresolved_root, result)

    assert "packages/a/node_modules/" in result.files_disallowed


@pytest.mark.tooling
def test_nested_artefact_dedup_survives_repeated_invocation(tmp_path: Path) -> None:
    """Regression: ``_audit_disallowed_artefacts`` must deduplicate using the
    exact string shape it appends. The previous implementation compared
    ``rel_path`` (no trailing slash) against entries that were appended with
    a trailing slash, so calling the helper twice would double-add both the
    ``files_disallowed`` entry and the matching warning. This guard fails
    the moment that broken shape is reintroduced.
    """
    from scripts.audit_starter_candidate import (
        AuditResult,
        _audit_disallowed_artefacts,
    )

    candidate = _ready_candidate(tmp_path / "dedup")
    (candidate / "packages" / "a" / "node_modules").mkdir(parents=True)
    candidate_root = candidate.resolve()
    result = AuditResult(candidate_path=candidate_root)

    _audit_disallowed_artefacts(candidate_root, result)
    _audit_disallowed_artefacts(candidate_root, result)

    nested = "packages/a/node_modules/"
    assert result.files_disallowed.count(nested) == 1
    assert sum(1 for warning in result.warnings if nested in warning) == 1


@pytest.mark.tooling
def test_blockers_take_precedence_over_integrations(tmp_path: Path) -> None:
    """An auth dep plus a leaked .env must classify as blocked, not too-integrated."""
    candidate = _ready_candidate(tmp_path / "auth-and-env")

    def add_auth(pkg: dict[str, Any]) -> None:
        pkg["dependencies"]["next-auth"] = "^5.0.0"

    _modify_package_json(candidate, add_auth)
    (candidate / ".env").write_text("SECRET=value\n", encoding="utf-8")
    result = audit_candidate(candidate)
    assert result.classification == "blocked"


# ---------------------------------------------------------------------------
# JSON output stability
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_json_output_is_stable_across_runs(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "stable")
    (candidate / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n", encoding="utf-8")
    first = audit_candidate(candidate).to_dict()
    second = audit_candidate(candidate).to_dict()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.tooling
def test_json_payload_has_expected_top_level_keys(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "shape")
    payload = audit_candidate(candidate).to_dict()
    expected = {
        "schemaVersion",
        "candidatePath",
        "classification",
        "summary",
        "blockers",
        "warnings",
        "detectedStack",
        "integrations",
        "scriptsPresent",
        "scriptsMissing",
        "scriptsNiceToHavePresent",
        "filesPresent",
        "filesDisallowed",
        "largeAssets",
        "demoSignals",
        "nextActions",
    }
    assert set(payload) == expected
    assert payload["schemaVersion"] == SCHEMA_VERSION


@pytest.mark.tooling
def test_json_lists_are_sorted_for_stability(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "sorted")
    (candidate / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n", encoding="utf-8")
    (candidate / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    payload = audit_candidate(candidate).to_dict()
    assert payload["warnings"] == sorted(payload["warnings"])
    assert payload["blockers"] == sorted(payload["blockers"])
    assert payload["filesDisallowed"] == sorted(payload["filesDisallowed"])
    assert payload["scriptsPresent"] == sorted(payload["scriptsPresent"])
    assert payload["scriptsMissing"] == sorted(payload["scriptsMissing"])
    assert payload["scriptsNiceToHavePresent"] == sorted(payload["scriptsNiceToHavePresent"])
    assert payload["filesPresent"] == sorted(payload["filesPresent"])
    assert payload["demoSignals"] == sorted(payload["demoSignals"])


@pytest.mark.tooling
def test_next_actions_preserves_priority_order(tmp_path: Path) -> None:
    """Regression: nextActions must keep the priority order from
    _build_next_actions (classification-specific action first, the
    "Never run this script on a path..." trailer last). Sorting
    alphabetically would move the trailer ahead of the actual
    recommendation for some classifications and degrade operator UX
    in render_text() output. Determinism across runs is preserved
    because the construction logic itself is deterministic.
    """
    candidate = _ready_candidate(tmp_path / "priority")
    payload = audit_candidate(candidate).to_dict()
    actions = payload["nextActions"]
    assert len(actions) >= 2
    assert "Operator may now propose a Starter import" in actions[0], (
        "starter-candidate-ready must surface the ADR/registry guidance first"
    )
    assert "Never run this script" in actions[-1], (
        "the universal trailer must always be the last entry in nextActions"
    )


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_main_writes_report_file_and_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate = _ready_candidate(tmp_path / "cli")
    out_path = tmp_path / "report.json"
    rc = main(
        [
            "--path",
            str(candidate),
            "--json",
            "--report-out",
            str(out_path),
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["classification"] == "starter-candidate-ready"
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk == payload


@pytest.mark.tooling
def test_main_returns_two_for_missing_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--path", str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert rc == 2
    assert "does not exist" in captured.err


# ---------------------------------------------------------------------------
# Read-only guarantee
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_audit_does_not_modify_candidate(tmp_path: Path) -> None:
    candidate = _ready_candidate(tmp_path / "untouched")
    snapshot_dir = tmp_path / "snapshot"
    shutil.copytree(candidate, snapshot_dir)
    audit_candidate(candidate)

    def _file_set(root: Path) -> set[tuple[str, str]]:
        items: set[tuple[str, str]] = set()
        for p in root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                items.add((rel, p.read_text(encoding="utf-8", errors="ignore")))
        return items

    assert _file_set(candidate) == _file_set(snapshot_dir)
