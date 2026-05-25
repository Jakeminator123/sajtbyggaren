"""Runtime smoke coverage for scaffold activation on jakob-be.

This suite distinguishes policy-declared/on-disk scaffolds from runtime-active
scaffolds. Runtime activation requires both resolver whitelist coverage and a
planner starter mapping; simply adding files under orchestration/scaffolds is
not enough.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCAFFOLDS_ROOT = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
SCAFFOLD_CONTRACT = REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"

RUNTIME_EXAMPLES: dict[str, str] = {
    "local-service-business": "examples/painter-palma.project-input.json",
    "ecommerce-lite": "examples/atelje-bird.project-input.json",
    "restaurant-hospitality": "examples/cafe-bistro.project-input.json",
    "clinic-healthcare": "examples/clinic-tandvard.project-input.json",
    "professional-services": "examples/advokatbyra-novum.project-input.json",
    "agency-studio": "examples/studio-bjork.project-input.json",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _enabled_scaffold_ids_from_contract() -> set[str]:
    payload = _json(SCAFFOLD_CONTRACT)
    return {
        entry["id"]
        for entry in payload["primaryScaffoldRegistry"]
        if isinstance(entry, dict) and entry.get("enabled") is True
    }


def _on_disk_scaffold_ids() -> set[str]:
    return {
        path.name
        for path in SCAFFOLDS_ROOT.iterdir()
        if path.is_dir() and (path / "scaffold.json").exists()
    }


@pytest.mark.tooling
def test_runtime_active_scaffolds_require_explicit_resolver_and_planner_mapping() -> None:
    from packages.generation.discovery.resolve import _RUNTIME_SCAFFOLD_HINTS
    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER

    runtime_from_resolver = set(_RUNTIME_SCAFFOLD_HINTS)
    runtime_from_planner = set(SCAFFOLD_TO_STARTER)
    runtime_active = runtime_from_resolver & runtime_from_planner

    assert runtime_active == set(RUNTIME_EXAMPLES)
    assert runtime_from_resolver == runtime_from_planner

    enabled_not_runtime = _enabled_scaffold_ids_from_contract() - runtime_active
    on_disk_not_runtime = _on_disk_scaffold_ids() - runtime_active

    # These sets are deliberately separate from RUNTIME_EXAMPLES: a scaffold can
    # be registered in policy, or even added on disk later, without becoming
    # runtime-active until resolver + planner mappings are both updated.
    assert RUNTIME_EXAMPLES.keys().isdisjoint(enabled_not_runtime)
    assert RUNTIME_EXAMPLES.keys().isdisjoint(on_disk_not_runtime)
    assert "real-estate" in enabled_not_runtime


@pytest.mark.tooling
@pytest.mark.parametrize(
    "scaffold_id,example_relpath",
    sorted(RUNTIME_EXAMPLES.items()),
)
def test_runtime_active_scaffold_build_skip_smoke(
    scaffold_id: str,
    example_relpath: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from packages.generation.discovery.resolve import _RUNTIME_SCAFFOLD_HINTS
    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER
    from scripts.build_site import _route_href, build, route_to_page_path

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    example_path = REPO_ROOT / example_relpath
    project_input = _json(example_path)
    routes_payload = _json(SCAFFOLDS_ROOT / scaffold_id / "routes.json")
    default_routes = routes_payload["defaultRoutes"]
    expected_paths = [route["path"] for route in default_routes]
    contact_route = next(route for route in default_routes if route["id"] == "contact")

    assert project_input["scaffoldId"] == scaffold_id
    assert project_input["variantId"] == _RUNTIME_SCAFFOLD_HINTS[scaffold_id][1]
    assert (SCAFFOLDS_ROOT / scaffold_id / "variants" / f"{project_input['variantId']}.json").exists()
    assert SCAFFOLD_TO_STARTER[scaffold_id] == _RUNTIME_SCAFFOLD_HINTS[scaffold_id][2]

    target, run_dir = build(
        example_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    site_plan = _json(run_dir / "site-plan.json")
    build_result = _json(run_dir / "build-result.json")

    assert site_plan["planSource"] == "pinned"
    assert site_plan["starterId"] == SCAFFOLD_TO_STARTER[scaffold_id]
    assert [route["path"] for route in site_plan["routePlan"]] == expected_paths

    assert build_result["status"] == "skipped"
    assert build_result["scaffoldId"] == scaffold_id
    assert build_result["variantId"] == project_input["variantId"]
    assert build_result["starterId"] == SCAFFOLD_TO_STARTER[scaffold_id]
    assert set(expected_paths).issubset(set(build_result["routes"]))

    for route_path in expected_paths:
        page_path = route_to_page_path(target, route_path)
        page = page_path.read_text(encoding="utf-8")
        assert "export default function" in page, f"{route_path} has no default export"

    contact_page = route_to_page_path(target, contact_route["path"])
    assert contact_page.exists()

    home_page = (target / "app" / "page.tsx").read_text(encoding="utf-8")
    assert f"href={_route_href(contact_route['path'])}" in home_page
    if contact_route["path"] != "/kontakt":
        assert "href={\"/kontakt\"}" not in home_page


@pytest.mark.tooling
def test_build_site_delegates_moved_renderers_to_build_package() -> None:
    import packages.generation.build.renderers as renderers
    import scripts.build_site as build_site

    assert build_site.write_pages is renderers.write_pages
    assert build_site.render_home is renderers.render_home
    assert build_site.render_services is renderers.render_services
    assert build_site.render_contact is renderers.render_contact
    assert build_site.render_products is renderers.render_products

    assert inspect.getsourcefile(build_site.write_pages)
    assert inspect.getsourcefile(build_site.write_pages).replace("\\", "/").endswith(
        "packages/generation/build/renderers.py"
    )

    build_site_source = inspect.getsource(build_site)
    assert 'importlib.import_module("packages.generation.build.renderers")' in build_site_source
    for moved_function in (
        "render_home",
        "render_services",
        "render_about",
        "render_contact",
        "render_products",
        "write_pages",
    ):
        assert f"def {moved_function}(" not in build_site_source
