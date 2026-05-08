"""Tests for packages/generation/codegen/ (Sprint 3A v1).

Locks the deterministic codegenModel v1 contract: shape of CodegenResult,
adaptation of routes/dossier components into CodegenFile entries, and
the truth-field convention (source=deterministic-v1, modelUsed=
deterministic). Future sprints replace the body with a real LLM call;
the tests for the public API must keep passing.
"""

from __future__ import annotations

import pytest

from packages.generation.codegen import (
    CodegenFile,
    CodegenResult,
    produce_codegen_artefakt,
)
from packages.generation.codegen.codegen import _route_to_page_path


@pytest.mark.tooling
def test_codegen_result_has_truth_fields():
    """CodegenResult mirrors briefSource/planSource truth-field pattern.
    Sprint 3A v1 always returns deterministic-v1 + modelUsed=deterministic.
    """
    result = produce_codegen_artefakt(
        {"runId": "fake"},
        routes_written=["/"],
        dossier_components=[],
        starter_id="marketing-base",
    )
    assert result.source == "deterministic-v1"
    assert result.modelUsed == "deterministic"
    assert result.error is None


@pytest.mark.tooling
def test_codegen_emits_one_page_per_route():
    """Every route in routes_written becomes a CodegenFile with role=page
    and source=codegen.
    """
    routes = ["/", "/tjanster", "/om-oss", "/kontakt"]
    result = produce_codegen_artefakt(
        {"runId": "fake"},
        routes_written=routes,
        dossier_components=[],
        starter_id="marketing-base",
    )
    page_files = [f for f in result.files if f.role == "page"]
    assert len(page_files) == len(routes)
    paths = {f.path for f in page_files}
    assert paths == {
        "app/page.tsx",
        "app/tjanster/page.tsx",
        "app/om-oss/page.tsx",
        "app/kontakt/page.tsx",
    }
    for f in page_files:
        assert f.source == "codegen"


@pytest.mark.tooling
def test_codegen_emits_dossier_mount_entries():
    """dossier_components paths become CodegenFile entries with
    source=dossier-mount, role=component.

    Paths must include the ``components/`` prefix because that is where
    ``scripts/build_site.py:mount_dossier_components`` actually writes
    the files. An earlier Sprint 3A revision used bare filenames which
    made the manifest lie about the on-disk location.
    """
    components = [
        "components/pacman-game.tsx",
        "components/before-after-slider.tsx",
    ]
    result = produce_codegen_artefakt(
        {},
        routes_written=[],
        dossier_components=components,
        starter_id="marketing-base",
    )
    component_files = [f for f in result.files if f.role == "component"]
    assert {f.path for f in component_files} == set(components)
    for f in component_files:
        assert f.source == "dossier-mount"


@pytest.mark.tooling
def test_codegen_dossier_paths_match_builder_mount_path():
    """Lock the contract that mount_dossier_components returns
    ``components/<filename>``. If the builder ever changes its return
    shape, this test catches it before the manifest goes out of sync
    with disk.
    """
    import inspect

    from scripts.build_site import mount_dossier_components

    source = inspect.getsource(mount_dossier_components)
    assert 'copied.append(f"components/{source.name}")' in source, (
        "mount_dossier_components must return paths prefixed with "
        "'components/' so the codegen manifest mirrors disk. "
        "If you renamed the prefix or moved the helper, update the "
        "test and produce_codegen_artefakt at the same time."
    )


@pytest.mark.tooling
def test_codegen_always_includes_patched_starter_files():
    """package.json and app/globals.css are always patched by the builder,
    so the manifest must list them with source=starter-patched.
    """
    result = produce_codegen_artefakt(
        {}, routes_written=[], dossier_components=[], starter_id="marketing-base"
    )
    paths = {f.path for f in result.files}
    assert "package.json" in paths
    assert "app/globals.css" in paths
    starter_patched = [f for f in result.files if f.source == "starter-patched"]
    assert len(starter_patched) >= 2


@pytest.mark.tooling
def test_codegen_always_includes_app_layout():
    """scripts/build_site.py:write_pages always writes app/layout.tsx (via
    render_layout). The manifest must record it as a CodegenFile with
    role=layout. Earlier Sprint 3A v1 forgot the layout entry, which
    broke the "adapt actual builder output" promise of v1.
    """
    result = produce_codegen_artefakt(
        {}, routes_written=[], dossier_components=[], starter_id="marketing-base"
    )
    paths_by_role: dict[str, set[str]] = {}
    for f in result.files:
        paths_by_role.setdefault(f.role, set()).add(f.path)
    assert "app/layout.tsx" in paths_by_role.get("layout", set()), (
        "Codegen manifest must include app/layout.tsx with role=layout. "
        "The builder writes it on every run; missing it makes v1 dishonest."
    )


@pytest.mark.tooling
def test_codegen_rationale_mentions_counts_and_starter():
    """The rationale string is operator-facing telemetry. It must mention
    the route/component counts and the starter_id so a Backoffice viewer
    can summarise without re-walking the files list.
    """
    result = produce_codegen_artefakt(
        {},
        routes_written=["/"],
        dossier_components=["a", "b", "c"],
        starter_id="marketing-base",
    )
    assert "1 routes" in result.rationale
    assert "3 dossier components" in result.rationale
    assert "marketing-base" in result.rationale


@pytest.mark.tooling
def test_codegen_rejects_non_dict_generation_package():
    """Defensive: a future caller passing a list or None would silently
    succeed if the type were not enforced. Sprint 3A v1 raises early.
    """
    with pytest.raises(TypeError):
        produce_codegen_artefakt(
            "not a dict",  # type: ignore[arg-type]
            routes_written=[],
            dossier_components=[],
            starter_id="marketing-base",
        )


@pytest.mark.tooling
def test_route_to_page_path_handles_root_and_nested():
    """Sprint 3A v1 mirrors scripts/build_site.py:route_to_page_path.
    If one drifts, this test catches the divergence.
    """
    assert _route_to_page_path("/") == "app/page.tsx"
    assert _route_to_page_path("/tjanster") == "app/tjanster/page.tsx"
    assert _route_to_page_path("/foo/bar") == "app/foo/bar/page.tsx"


@pytest.mark.tooling
def test_codegen_file_pydantic_validates_role():
    """CodegenFile.role is a Literal - invalid roles must be rejected at
    construction so the manifest cannot smuggle in bogus types.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CodegenFile(path="x", source="codegen", role="bogus")  # type: ignore[arg-type]


@pytest.mark.tooling
def test_codegen_result_is_pydantic_serialisable():
    """The orchestrator passes CodegenResult through model_dump() to keep
    it JSON-clean. This test catches any future field that breaks JSON.
    """
    import json

    result = produce_codegen_artefakt(
        {}, routes_written=["/"], dossier_components=[], starter_id="x"
    )
    payload = result.model_dump()
    json.dumps(payload)
    assert isinstance(payload, dict)
    assert isinstance(payload["files"], list)


@pytest.mark.tooling
def test_codegen_v1_does_not_call_llm():
    """Sprint 3A v1 must not call OpenAI. ADR 0015 reserves real
    codegenModel for Sprint 3B. If a future commit smuggles an LLM call
    in, this test catches it via env-var check.
    """
    import os

    saved = os.environ.pop("OPENAI_API_KEY", None)
    try:
        result = produce_codegen_artefakt(
            {}, routes_written=["/"], dossier_components=[], starter_id="x"
        )
    finally:
        if saved is not None:
            os.environ["OPENAI_API_KEY"] = saved
    assert result.source == "deterministic-v1"
    assert result.error is None


@pytest.mark.tooling
def test_codegen_result_round_trips_through_pydantic():
    """A CodegenResult dumped to dict must be reconstructable. Round-trip
    is what makes the type usable as a build-result.json field later.
    """
    original = produce_codegen_artefakt(
        {},
        routes_written=["/", "/x"],
        dossier_components=["app/components/y.tsx"],
        starter_id="marketing-base",
    )
    payload = original.model_dump()
    restored = CodegenResult.model_validate(payload)
    assert restored.source == original.source
    assert len(restored.files) == len(original.files)
    assert restored.files[0].path == original.files[0].path
