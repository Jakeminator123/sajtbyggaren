"""Tests for ADR 0056: merging operator-curated, pinned dossier dependencies
into the generated ``package.json``.

Covers the pure merge/pin/collision logic, the byte-identical no-dependency
path, the ``--skip-build`` path, and a ``requires_node`` smoke test that proves
a fixture dossier declaring ``three@<pin>`` produces an installable site.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.build_site as build_site  # noqa: E402
from packages.generation.build.dossier_dependencies import (  # noqa: E402
    merge_dossier_dependencies,
    parse_pinned_spec,
)
from scripts.build_site import build, patch_package_json  # noqa: E402

THREE_PIN = "0.160.0"
THREE_SPEC = f"three@{THREE_PIN}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_package_json(target: Path, dependencies: dict[str, str]) -> Path:
    """Write a minimal starter-style ``package.json`` and return its path."""
    target.mkdir(parents=True, exist_ok=True)
    pkg = {
        "name": "starter-base",
        "version": "0.1.0",
        "private": True,
        "dependencies": dict(dependencies),
        "devDependencies": {"typescript": "^5"},
    }
    pkg_path = target / "package.json"
    pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pkg_path


def _dossier(dossier_id: str, dependencies: list[str]) -> dict:
    return {"id": dossier_id, "manifest": {"dependencies": list(dependencies)}}


def _write_three_dossier(dossiers_dir: Path, spec: str = THREE_SPEC) -> None:
    """Create a soft fixture dossier under ``dossiers_dir`` that declares one
    pinned dependency and ships one trivial component."""
    dossier_dir = dossiers_dir / "soft" / "three-demo"
    components_dir = dossier_dir / "components"
    components_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": "three-demo",
        "enabled": True,
        "label": "Three Demo",
        "capability": "interactive-game",
        "class": "soft",
        "codeFidelity": "rewritable",
        "complexity": "low",
        "defaultForCapability": False,
        "summary": "Test fixture soft dossier that declares one pinned npm dependency.",
        "envVars": [],
        "dependencies": [spec],
        "files": ["components/demo.tsx"],
        "exposes": ["Demo"],
        "lastVerified": "2026-06-12",
    }
    (dossier_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Trivial component, deliberately importing nothing: the dependency is
    # declared in the manifest, not consumed by code (the test only proves the
    # merge + install path, per ADR 0056 definition of done).
    (components_dir / "demo.tsx").write_text(
        "export default function Demo() {\n  return null;\n}\n", encoding="utf-8"
    )


def _write_three_project_input(tmp_path: Path, site_id: str) -> Path:
    """Derive a project-input from painter-palma that selects only the fixture
    dossier."""
    source = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["siteId"] = site_id
    payload["selectedDossiers"] = {
        "required": ["three-demo"],
        "recommended": [],
        "rationale": "Test fixture: mount the three-demo dossier to exercise dependency merge.",
    }
    target = tmp_path / "fixtures" / f"{site_id}.project-input.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Pure merge / pin / collision unit tests
# ---------------------------------------------------------------------------


def test_parse_pinned_spec_exact_and_scoped() -> None:
    assert parse_pinned_spec("three@0.160.0") == ("three", "0.160.0")
    assert parse_pinned_spec("@react-three/fiber@8.0.0") == ("@react-three/fiber", "8.0.0")


def test_parse_pinned_spec_tilde_accepted() -> None:
    assert parse_pinned_spec("three@~0.160.0") == ("three", "~0.160.0")


@pytest.mark.parametrize("bad", ["three@^0.160.0", "three", "three@latest", "three@*", "three@1.x"])
def test_parse_pinned_spec_rejects_non_pins(bad: str) -> None:
    with pytest.raises(SystemExit):
        parse_pinned_spec(bad)


def test_merge_adds_new_pinned_package() -> None:
    base = {"next": "16.2.6", "react": "19.2.4"}
    merge = merge_dossier_dependencies(base, [_dossier("three-demo", [THREE_SPEC])])
    assert merge.changed is True
    assert merge.added == {"three": THREE_PIN}
    assert merge.dependencies["three"] == THREE_PIN
    # Base entries preserved, original keys kept in their original order.
    assert list(merge.dependencies)[:2] == ["next", "react"]


def test_merge_scoped_and_tilde() -> None:
    base = {"next": "16.2.6"}
    merge = merge_dossier_dependencies(
        base, [_dossier("d", ["@react-three/fiber@8.0.0", "foo@~1.2.3"])]
    )
    assert merge.dependencies["@react-three/fiber"] == "8.0.0"
    assert merge.dependencies["foo"] == "~1.2.3"


def test_merge_no_dependencies_is_no_op() -> None:
    base = {"next": "16.2.6", "react": "19.2.4"}
    merge = merge_dossier_dependencies(base, [_dossier("d", [])])
    assert merge.changed is False
    assert merge.added == {}
    assert merge.dependencies == base


def test_merge_identical_redeclaration_is_no_op() -> None:
    base = {"next": "16.2.6"}
    merge = merge_dossier_dependencies(base, [_dossier("d", ["next@16.2.6"])])
    assert merge.changed is False
    assert merge.added == {}


def test_merge_cross_dossier_collision_raises() -> None:
    base: dict[str, str] = {}
    with pytest.raises(SystemExit) as excinfo:
        merge_dossier_dependencies(
            base,
            [
                _dossier("alpha", ["three@0.160.0"]),
                _dossier("beta", ["three@0.159.0"]),
            ],
        )
    message = str(excinfo.value)
    assert "three" in message
    assert "alpha" in message
    assert "beta" in message


def test_merge_starter_collision_raises() -> None:
    base = {"next": "16.2.6"}
    with pytest.raises(SystemExit) as excinfo:
        merge_dossier_dependencies(base, [_dossier("alpha", ["next@1.0.0"])])
    message = str(excinfo.value)
    assert "next" in message
    assert "starter" in message.lower()


# ---------------------------------------------------------------------------
# patch_package_json integration with the file on disk
# ---------------------------------------------------------------------------


def test_patch_package_json_merges_pinned_dependency(tmp_path: Path) -> None:
    target = tmp_path / "site"
    _write_package_json(target, {"next": "16.2.6"})
    merge = patch_package_json(
        target, {"siteId": "demo-site"}, [_dossier("three-demo", [THREE_SPEC])]
    )
    assert merge.changed is True
    pkg = json.loads((target / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "demo-site"
    assert pkg["dependencies"]["three"] == THREE_PIN
    assert pkg["dependencies"]["next"] == "16.2.6"


def test_patch_package_json_without_dependencies_is_byte_identical(tmp_path: Path) -> None:
    """No dossier deps (and a dossier with empty deps) must yield exactly the
    same bytes as today's name-only rewrite."""
    target_none = tmp_path / "none"
    target_empty = tmp_path / "empty"
    _write_package_json(target_none, {"next": "16.2.6", "react": "19.2.4"})
    _write_package_json(target_empty, {"next": "16.2.6", "react": "19.2.4"})

    patch_package_json(target_none, {"siteId": "demo-site"}, None)
    patch_package_json(target_empty, {"siteId": "demo-site"}, [_dossier("d", [])])

    none_bytes = (target_none / "package.json").read_bytes()
    empty_bytes = (target_empty / "package.json").read_bytes()
    assert none_bytes == empty_bytes

    # And both equal the reference name-only transform (today's behaviour).
    reference_pkg = json.loads((target_none / "package.json").read_text(encoding="utf-8"))
    reference_bytes = (
        json.dumps(reference_pkg, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    assert none_bytes == reference_bytes


# ---------------------------------------------------------------------------
# Build integration: --skip-build path is unaffected (merges, no install)
# ---------------------------------------------------------------------------


def test_skip_build_merges_dependency_without_installing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dossiers_dir = tmp_path / "dossiers"
    _write_three_dossier(dossiers_dir)
    monkeypatch.setattr(build_site, "DOSSIERS_DIR", dossiers_dir)

    project_input = _write_three_project_input(tmp_path, "three-demo-skip")
    target, run_dir = build(
        project_input,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    pkg = json.loads((target / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["three"] == THREE_PIN

    # Build was skipped -> no install ran, so node_modules must be absent.
    assert not (target / "node_modules").exists()
    events = [
        json.loads(line)
        for line in (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(event.get("event") == "build.skipped" for event in events)


# ---------------------------------------------------------------------------
# requires_node smoke: real npm install of the merged package.json
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.slow
@pytest.mark.requires_node
def test_npm_install_succeeds_with_dossier_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("npm") is None:
        pytest.skip("npm not available; dossier dependency install smoke test cannot run.")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dossiers_dir = tmp_path / "dossiers"
    _write_three_dossier(dossiers_dir)
    monkeypatch.setattr(build_site, "DOSSIERS_DIR", dossiers_dir)

    project_input = _write_three_project_input(tmp_path, "three-demo-install")
    # do_build=True exercises the full path end-to-end: the dependency merge,
    # the honest npm ci -> npm install fallback (the merged package.json no
    # longer matches the starter lockfile), the dependency_drift trace note,
    # the install itself and `next build`. See ADR 0056. (Measured ~25s on the
    # CI VM; behind requires_node/slow.)
    target, run_dir = build(
        project_input,
        do_build=True,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    pkg = json.loads((target / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["three"] == THREE_PIN
    assert (target / "package-lock.json").is_file()

    events = [
        json.loads(line)
        for line in (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_event = {event.get("event"): event for event in events}

    # The builder must have honestly fallen back from npm ci to npm install,
    # recording the deviation as a neutral warning note.
    drift = by_event.get("npm.install.dependency_drift")
    assert drift is not None, "expected an npm.install.dependency_drift trace event"
    assert drift.get("status") == "warning"
    assert "three@" + THREE_PIN in (drift.get("reason") or "")

    # And the install + build must have succeeded.
    assert by_event.get("npm.install", {}).get("status") == "done"
    assert by_event.get("npm.build", {}).get("status") == "done"
    assert (target / "node_modules" / "three").is_dir()
