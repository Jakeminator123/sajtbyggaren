"""Tests for the Component Catalog lager 1+2 (ADR 0040).

Lager 1: scripts/generate_component_manifests.py emits a deterministic
data/starters/<id>/component-manifest.json per Starter from components.json +
components/ui/ on disk. A sync-check (same pattern as rules_sync.py) fails on
drift.

Lager 2: capability-map.v1.json gains an optional 'components' field per
capability; scripts/governance_validate.py cross-checks each name against the
union of enabled Starters' manifests. A reference to a component missing from
every enabled Starter is a gate error (no silent fallback). Pilot:
faq-section -> accordion, vendored as marketing-base/components/ui/accordion.tsx
with zero new dependencies.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.generate_component_manifests import (
    MANIFEST_FILENAME,
    build_manifest,
    starter_ids,
)
from scripts.governance_validate import cross_check_capability_components

REPO_ROOT = Path(__file__).resolve().parents[1]
STARTERS_DIR = REPO_ROOT / "data" / "starters"
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "component-manifest.schema.json"
CAPABILITY_MAP_PATH = (
    REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
)
STARTER_REGISTRY_PATH = (
    REPO_ROOT / "governance" / "policies" / "starter-registry.v1.json"
)
ACCORDION_PATH = (
    STARTERS_DIR / "marketing-base" / "components" / "ui" / "accordion.tsx"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _enabled_starter_ids() -> list[str]:
    registry = _load(STARTER_REGISTRY_PATH)
    return [
        starter["id"]
        for starter in registry["starters"]
        if starter.get("enabled", True)
    ]


def _disk_scan_ui(starter_id: str) -> list[dict]:
    """Independent re-implementation of the components/ui/ scan for drift-proofing."""
    ui_dir = STARTERS_DIR / starter_id / "components" / "ui"
    out: list[dict] = []
    if ui_dir.is_dir():
        for child in sorted(ui_dir.iterdir()):
            if not child.is_file() or child.suffix != ".tsx":
                continue
            if child.stem.endswith(".test"):
                continue
            out.append(
                {
                    "name": child.stem,
                    "path": child.relative_to(STARTERS_DIR / starter_id).as_posix(),
                }
            )
    out.sort(key=lambda component: component["name"])
    return out


@pytest.mark.tooling
def test_generator_check_exits_zero():
    """The committed manifests must match what the generator would produce."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "generate_component_manifests.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "generate_component_manifests.py --check failed (manifests out of sync). "
        "Run 'python scripts/generate_component_manifests.py' and commit.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.tooling
def test_every_enabled_starter_has_manifest():
    missing = [
        starter_id
        for starter_id in _enabled_starter_ids()
        if not (STARTERS_DIR / starter_id / MANIFEST_FILENAME).exists()
    ]
    assert not missing, (
        f"Enabled Starters without a {MANIFEST_FILENAME}: {missing}. "
        "Run 'python scripts/generate_component_manifests.py'."
    )


@pytest.mark.tooling
def test_manifests_validate_against_schema():
    validator = jsonschema.Draft202012Validator(_load(SCHEMA_PATH))
    for starter_id in starter_ids():
        manifest_path = STARTERS_DIR / starter_id / MANIFEST_FILENAME
        if not manifest_path.exists():
            continue
        errors = sorted(
            validator.iter_errors(_load(manifest_path)),
            key=lambda err: list(err.path),
        )
        assert not errors, (
            f"{starter_id}/{MANIFEST_FILENAME} does not validate: "
            + "; ".join(e.message for e in errors)
        )


@pytest.mark.tooling
def test_manifest_components_match_disk():
    """The committed manifest must equal what build_manifest produces from disk."""
    for starter_id in starter_ids():
        manifest_path = STARTERS_DIR / starter_id / MANIFEST_FILENAME
        assert manifest_path.exists(), f"{starter_id} has no manifest"
        committed = _load(manifest_path)
        assert committed == build_manifest(starter_id), (
            f"{starter_id}/{MANIFEST_FILENAME} drifted from disk; regenerate."
        )
        # And the components list matches an independent scan.
        assert committed["components"] == _disk_scan_ui(starter_id), (
            f"{starter_id} components do not match an independent components/ui/ scan."
        )


@pytest.mark.tooling
@pytest.mark.governance
def test_capability_components_exist_in_some_manifest():
    """Every capability-map components name must exist in >=1 enabled Starter manifest."""
    capability_map = _load(CAPABILITY_MAP_PATH)
    available: set[str] = set()
    for starter_id in _enabled_starter_ids():
        manifest_path = STARTERS_DIR / starter_id / MANIFEST_FILENAME
        if manifest_path.exists():
            for component in _load(manifest_path)["components"]:
                available.add(component["name"])

    dangling: list[tuple[str, str]] = []
    for slug, entry in capability_map["capabilities"].items():
        for name in entry.get("components", []) or []:
            if name not in available:
                dangling.append((slug, name))
    assert not dangling, (
        "capability-map components reference component(s) absent from every "
        f"enabled Starter manifest: {dangling}. Vendor the component or drop "
        "the mapping."
    )


@pytest.mark.tooling
@pytest.mark.governance
def test_faq_section_pilot_maps_to_accordion():
    capability_map = _load(CAPABILITY_MAP_PATH)
    faq = capability_map["capabilities"]["faq-section"]
    assert faq.get("components") == ["accordion"], (
        "ADR 0040 pilot: faq-section must map to the accordion component."
    )
    marketing = _load(STARTERS_DIR / "marketing-base" / MANIFEST_FILENAME)
    names = {component["name"] for component in marketing["components"]}
    assert "accordion" in names, (
        "accordion must be vendored in marketing-base's manifest for the pilot."
    )


@pytest.mark.tooling
def test_marketing_base_vendors_accordion():
    assert ACCORDION_PATH.is_file(), (
        "ADR 0040 (A): marketing-base must vendor components/ui/accordion.tsx."
    )


@pytest.mark.tooling
def test_accordion_adds_no_dependency():
    """Operator requirement (ADR 0040): accordion.tsx must add zero dependencies.

    Locks two things: (1) marketing-base/package.json gains no accordion-related
    dependency, and (2) accordion.tsx imports only from react and @/lib/utils -
    no external package (e.g. @radix-ui/*, @base-ui/react) is pulled in.
    """
    package_json = _load(STARTERS_DIR / "marketing-base" / "package.json")
    deps = {
        **package_json.get("dependencies", {}),
        **package_json.get("devDependencies", {}),
    }
    offending = [
        name
        for name in deps
        if "accordion" in name.lower() or name.startswith("@radix-ui/")
    ]
    assert not offending, (
        f"accordion.tsx must add no dependency, but package.json has: {offending}"
    )

    source = ACCORDION_PATH.read_text(encoding="utf-8")
    import_targets = re.findall(r"""from\s+["']([^"']+)["']""", source)
    allowed = {"react", "@/lib/utils"}
    external = [target for target in import_targets if target not in allowed]
    assert not external, (
        "accordion.tsx may only import from react and @/lib/utils (zero new deps); "
        f"found: {external}"
    )


@pytest.mark.tooling
@pytest.mark.governance
def test_cross_check_flags_missing_component():
    """The governance gate must reject a components mapping to an absent component.

    This locks the 'missing component = gate error, not silent fallback'
    semantics from the design note / ADR 0040, independent of the live data.
    """
    fake_policies = {
        "starter-registry.v1.json": {
            "starters": [{"id": "marketing-base", "enabled": True}]
        },
        "capability-map.v1.json": {
            "capabilities": {
                "faq-section": {
                    "dossiers": ["faq-accordion"],
                    "components": ["this-component-does-not-exist"],
                }
            }
        },
    }
    errors = cross_check_capability_components(fake_policies)
    assert any("this-component-does-not-exist" in err for err in errors), (
        "cross_check_capability_components must flag a mapping to a component "
        f"missing from every enabled Starter manifest; got: {errors}"
    )
    # And the live policies must NOT produce that error (accordion is vendored).
    live = {
        "starter-registry.v1.json": _load(STARTER_REGISTRY_PATH),
        "capability-map.v1.json": _load(CAPABILITY_MAP_PATH),
    }
    assert cross_check_capability_components(live) == [], (
        "Live capability-map components must all resolve to a vendored component."
    )
