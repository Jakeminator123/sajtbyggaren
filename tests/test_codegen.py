"""Tests for packages/generation/codegen/.

Sprint 3A v1 locked the deterministic shape (CodegenResult,
CodegenFile, route/component/layout adaptation, truth-field convention).
Sprint 3B-next (ADR 0017) extends with a minimal real codegenModel
LLM call for marketing-base + OPENAI_API_KEY, plus the four-source
truth field (real / mock-no-key / mock-llm-error / deterministic-v1).

All tests in this module run with OPENAI_API_KEY removed via the
``_disable_real_codegen`` autouse fixture so they are deterministic
even when an operator runs pytest with a key in their shell. The
SAJTBYGGAREN_E2E-gated test in tests/test_real_codegen_model.py is
the only one that exercises the real LLM call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.codegen import (
    CodegenFile,
    CodegenLLMResponse,
    CodegenModelResolutionError,
    CodegenResult,
    CodegenUsage,
    produce_codegen_artefakt,
    resolve_codegen_model,
)
from packages.generation.codegen.codegen import _route_to_page_path

REPO_ROOT = Path(__file__).resolve().parents[1]
LLM_MODELS_POLICY = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"


@pytest.fixture(autouse=True)
def _disable_real_codegen(monkeypatch):
    """Strip OPENAI_API_KEY for every test in this module so the
    deterministic + mock paths are exercised consistently regardless of
    operator shell state. The real-LLM path is exercised in the
    dedicated gated test in tests/test_real_codegen_model.py.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# Sprint 3A v1 contract (deterministic file list, truth fields)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_codegen_result_has_truth_fields_for_marketing_base_no_key():
    """marketing-base + no API key -> source=mock-no-key (Sprint 3B-next).
    deterministic-v1 is now reserved for starters explicitly out of
    real-codegen scope.
    """
    result = produce_codegen_artefakt(
        {"runId": "fake"},
        routes_written=["/"],
        dossier_components=[],
        starter_id="marketing-base",
    )
    assert result.source == "mock-no-key"
    assert result.modelUsed == "mock"
    assert result.error is None


@pytest.mark.tooling
def test_codegen_emits_one_page_per_route():
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
        "'components/' so the codegen manifest mirrors disk."
    )


@pytest.mark.tooling
def test_codegen_always_includes_patched_starter_files():
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
    result = produce_codegen_artefakt(
        {}, routes_written=[], dossier_components=[], starter_id="marketing-base"
    )
    paths_by_role: dict[str, set[str]] = {}
    for f in result.files:
        paths_by_role.setdefault(f.role, set()).add(f.path)
    assert "app/layout.tsx" in paths_by_role.get("layout", set())


@pytest.mark.tooling
def test_codegen_rationale_mentions_counts_and_starter():
    result = produce_codegen_artefakt(
        {},
        routes_written=["/"],
        dossier_components=["a", "b", "c"],
        starter_id="marketing-base",
    )
    # The rationale string for non-real paths is the deterministic boilerplate.
    assert "1 routes" in result.rationale
    assert "3 dossier components" in result.rationale
    assert "marketing-base" in result.rationale


@pytest.mark.tooling
def test_codegen_rejects_non_dict_generation_package():
    with pytest.raises(TypeError):
        produce_codegen_artefakt(
            "not a dict",  # type: ignore[arg-type]
            routes_written=[],
            dossier_components=[],
            starter_id="marketing-base",
        )


@pytest.mark.tooling
def test_route_to_page_path_handles_root_and_nested():
    assert _route_to_page_path("/") == "app/page.tsx"
    assert _route_to_page_path("/tjanster") == "app/tjanster/page.tsx"
    assert _route_to_page_path("/foo/bar") == "app/foo/bar/page.tsx"


@pytest.mark.tooling
def test_codegen_file_pydantic_validates_role():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CodegenFile(path="x", source="codegen", role="bogus")  # type: ignore[arg-type]


@pytest.mark.tooling
def test_codegen_result_is_pydantic_serialisable():
    result = produce_codegen_artefakt(
        {}, routes_written=["/"], dossier_components=[], starter_id="other-starter"
    )
    payload = result.model_dump()
    json.dumps(payload)
    assert isinstance(payload, dict)
    assert isinstance(payload["files"], list)


@pytest.mark.tooling
def test_codegen_result_round_trips_through_pydantic():
    original = produce_codegen_artefakt(
        {},
        routes_written=["/", "/x"],
        dossier_components=["components/y.tsx"],
        starter_id="marketing-base",
    )
    payload = original.model_dump()
    restored = CodegenResult.model_validate(payload)
    assert restored.source == original.source
    assert len(restored.files) == len(original.files)
    assert restored.files[0].path == original.files[0].path


# ---------------------------------------------------------------------------
# Sprint 3B-next (ADR 0017): truth-field paths
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_codegen_falls_back_to_deterministic_v1_for_unsupported_starter():
    """Sprint 3B-next is intentionally limited to marketing-base. Any
    other starter_id must skip the LLM and return source=deterministic-v1
    so eventual support is gated by an explicit policy update, not by
    a silent fallback that pretends real codegen ran.
    """
    result = produce_codegen_artefakt(
        {},
        routes_written=["/"],
        dossier_components=[],
        starter_id="ecommerce-lite",
    )
    assert result.source == "deterministic-v1"
    assert result.modelUsed == "deterministic"
    assert result.usage.totalTokens == 0
    assert result.riskNotes == []


@pytest.mark.tooling
def test_codegen_no_key_path_returns_zero_usage_and_no_risk_notes():
    """Without an API key we never call the LLM, so usage stays zeroed
    and riskNotes empty. Backoffice can rely on these defaults to
    distinguish "real call ran" from "skipped".
    """
    result = produce_codegen_artefakt(
        {},
        routes_written=["/", "/x"],
        dossier_components=[],
        starter_id="marketing-base",
    )
    assert result.source == "mock-no-key"
    assert result.usage.promptTokens == 0
    assert result.usage.completionTokens == 0
    assert result.usage.totalTokens == 0
    assert result.riskNotes == []


@pytest.mark.tooling
def test_codegen_falls_back_to_mock_llm_error_when_call_raises(monkeypatch):
    """When the OpenAI call raises, source must flip to mock-llm-error
    with the exception detail in error, while files stay deterministic
    so the rest of the pipeline keeps running."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-fake-key")

    def _raising_call(**_kwargs):
        raise RuntimeError("simulated openai failure")

    import packages.generation.codegen.codegen as codegen_module

    monkeypatch.setattr(codegen_module, "_call_real_codegen_model", _raising_call)
    monkeypatch.setattr(
        codegen_module, "resolve_codegen_model", lambda: "gpt-fake-model"
    )

    result = produce_codegen_artefakt(
        {"siteBrief": {}},
        routes_written=["/", "/x"],
        dossier_components=[],
        starter_id="marketing-base",
    )

    assert result.source == "mock-llm-error"
    assert result.modelUsed == "gpt-fake-model"
    assert result.error is not None
    assert "simulated openai failure" in result.error
    # Deterministic files preserved.
    assert any(f.path == "app/page.tsx" for f in result.files)
    assert any(f.path == "app/x/page.tsx" for f in result.files)


@pytest.mark.tooling
def test_codegen_real_path_populates_rationale_risk_notes_and_usage(monkeypatch):
    """Mocked real-call: when _call_real_codegen_model returns a parsed
    response + usage, the result mirrors them and source flips to real.
    """

    monkeypatch.setenv("OPENAI_API_KEY", "test-fake-key")

    def _stub_call(**_kwargs):
        return (
            CodegenLLMResponse(
                rationale=(
                    "Marketing-base scaffold matches a service business "
                    "with conversion focus on /kontakt; tone calls for "
                    "warm Swedish copy."
                ),
                riskNotes=[
                    "Hero section depends on operator imagery.",
                    "/tjanster needs concrete service list to score 9/10.",
                ],
            ),
            CodegenUsage(promptTokens=120, completionTokens=80, totalTokens=200),
        )

    import packages.generation.codegen.codegen as codegen_module

    monkeypatch.setattr(codegen_module, "_call_real_codegen_model", _stub_call)
    monkeypatch.setattr(
        codegen_module, "resolve_codegen_model", lambda: "gpt-fake-model"
    )

    result = produce_codegen_artefakt(
        {"siteBrief": {"businessTypeGuess": "painter"}},
        routes_written=["/", "/tjanster", "/kontakt"],
        dossier_components=[],
        starter_id="marketing-base",
    )

    assert result.source == "real"
    assert result.modelUsed == "gpt-fake-model"
    assert "marketing-base" in result.rationale.lower() or "scaffold" in result.rationale.lower()
    assert len(result.riskNotes) == 2
    assert result.usage.promptTokens == 120
    assert result.usage.completionTokens == 80
    assert result.usage.totalTokens == 200
    assert result.error is None


@pytest.mark.tooling
def test_codegen_real_path_caught_when_resolver_raises(monkeypatch):
    """If llm-models.v1.json is misconfigured (CodegenModelResolutionError),
    we should NOT crash the build; we should fall through to
    mock-llm-error with the resolver error captured."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-fake-key")

    def _raising_resolver(**_kwargs):
        raise CodegenModelResolutionError("policy missing")

    import packages.generation.codegen.codegen as codegen_module

    monkeypatch.setattr(codegen_module, "resolve_codegen_model", _raising_resolver)

    result = produce_codegen_artefakt(
        {},
        routes_written=["/"],
        dossier_components=[],
        starter_id="marketing-base",
    )

    assert result.source == "mock-llm-error"
    assert result.error is not None
    assert "policy missing" in result.error


# ---------------------------------------------------------------------------
# resolve_codegen_model
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_resolve_codegen_model_reads_policy():
    """Resolver returns a non-empty string from the live llm-models.v1.json
    policy. Mirrors test_resolve_planning_model and test_resolve_brief_model.
    """
    model = resolve_codegen_model()
    assert isinstance(model, str)
    assert model.strip()


@pytest.mark.tooling
def test_resolve_codegen_model_raises_for_missing_role(tmp_path):
    """Strict resolver: missing codegenModel role -> CodegenModelResolutionError."""
    fake_policy = tmp_path / "llm-models.v1.json"
    fake_policy.write_text(
        json.dumps({"roles": [{"id": "briefModel", "provider": "openai", "model": "x"}]}),
        encoding="utf-8",
    )
    with pytest.raises(CodegenModelResolutionError) as exc:
        resolve_codegen_model(policy_path=fake_policy)
    assert "codegenModel" in str(exc.value)


@pytest.mark.tooling
def test_resolve_codegen_model_raises_for_non_openai_provider(tmp_path):
    fake_policy = tmp_path / "llm-models.v1.json"
    fake_policy.write_text(
        json.dumps(
            {"roles": [{"id": "codegenModel", "provider": "anthropic", "model": "x"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(CodegenModelResolutionError) as exc:
        resolve_codegen_model(policy_path=fake_policy)
    assert "openai" in str(exc.value).lower()


@pytest.mark.tooling
def test_resolve_codegen_model_raises_for_empty_model_field(tmp_path):
    fake_policy = tmp_path / "llm-models.v1.json"
    fake_policy.write_text(
        json.dumps(
            {"roles": [{"id": "codegenModel", "provider": "openai", "model": "  "}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(CodegenModelResolutionError):
        resolve_codegen_model(policy_path=fake_policy)


@pytest.mark.tooling
def test_resolve_codegen_model_raises_for_missing_policy_file(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(CodegenModelResolutionError) as exc:
        resolve_codegen_model(policy_path=missing)
    assert "missing" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# CodegenLLMResponse schema lock
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_codegen_llm_response_caps_risk_notes():
    """riskNotes is capped at 3 entries so a chatty LLM cannot blow up
    build-result.json."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CodegenLLMResponse(
            rationale="x",
            riskNotes=["a", "b", "c", "d"],  # 4 > max 3
        )


@pytest.mark.tooling
def test_codegen_llm_response_allows_zero_risk_notes():
    """0 is a valid riskNotes count; LLM doesn't need to invent risks."""
    resp = CodegenLLMResponse(rationale="ok", riskNotes=[])
    assert resp.riskNotes == []
