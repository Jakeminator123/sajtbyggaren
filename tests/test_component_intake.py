"""Tests for the curated shadcn component intake CLI (ADR 0054).

The whole orchestration runs against a MOCKED MCP session + a fake structured-
output model client, so there is NO network, no ``npx`` and no ``OPENAI_API_KEY``
needed in CI (the key check is monkeypatched). The tests lock:

1. The deterministic tool flow search -> view -> examples drives the session and
   the gathered material reaches the model.
2. The candidate is written as component.tsx + intake-info.json + README.md with
   the right provenance (prompt, model, shadcnItemsUsed, contentHash, deps).
3. Missing OPENAI_API_KEY is an honest error - no files, no mock.
4. The output-dir guard refuses writes into data/starters/ and the canonical
   orchestration tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import component_intake as ci  # noqa: E402

pytestmark = pytest.mark.tooling


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeSession:
    """A fake shadcn MCP session that records calls and returns canned text."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.entered = False
        self.exited = False

    def __enter__(self) -> _FakeSession:
        self.entered = True
        return self

    def __exit__(self, *exc: object) -> None:
        self.exited = True

    def search_items_in_registries(self, query: str) -> str:
        self.calls.append(("search", query))
        return (
            "Found items:\n- @shadcn/accordion (Accordion)\n"
            "- @shadcn/collapsible (Collapsible)\n"
        )

    def view_items_in_registries(self, items: list[str]) -> str:
        self.calls.append(("view", list(items)))
        return f"VIEW for {items}: files: accordion.tsx, deps: @radix-ui/react-accordion"

    def get_item_examples_from_registries(self, query: str, items: list[str]) -> str:
        self.calls.append(("examples", (query, list(items))))
        return "EXAMPLE: <Accordion><AccordionItem>...</AccordionItem></Accordion>"


class _FakeParsed:
    def __init__(self, candidate: ci.ComponentCandidate) -> None:
        self.output_parsed = candidate


class _FakeResponses:
    def __init__(self, candidate: ci.ComponentCandidate) -> None:
        self._candidate = candidate
        self.last_kwargs: dict | None = None

    def parse(self, **kwargs: object) -> _FakeParsed:
        self.last_kwargs = kwargs
        return _FakeParsed(self._candidate)


class _FakeOpenAI:
    def __init__(self, candidate: ci.ComponentCandidate) -> None:
        self.responses = _FakeResponses(candidate)


def _candidate(**overrides: object) -> ci.ComponentCandidate:
    base = {
        "componentName": "Accordion",
        "tsx": 'import * as React from "react"\nexport function Accordion() { return null }',
        "requiredNpmDeps": [],
        "shadcnItemsUsed": ["@shadcn/accordion"],
        "notes": "Native details pattern, zero new deps.",
    }
    base.update(overrides)
    return ci.ComponentCandidate(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_intake_writes_candidate_files_with_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "has_openai_api_key", lambda: True)
    session = _FakeSession()
    client = _FakeOpenAI(_candidate())

    result = ci.run_component_intake(
        "accordion FAQ",
        slug="accordion",
        output_dir=tmp_path,
        session=session,
        openai_client=client,
        model="gpt-test",
    )

    # Tool flow ran in order, in a single session context.
    assert session.entered and session.exited
    assert [c[0] for c in session.calls] == ["search", "view", "examples"]
    # Items parsed from search output feed view + examples.
    assert "@shadcn/accordion" in session.calls[1][1]

    # Files written.
    assert result.component_path.exists()
    assert result.intake_info_path.exists()
    assert result.readme_path.exists()
    assert result.component_path.read_text(encoding="utf-8").endswith("\n")

    info = json.loads(result.intake_info_path.read_text(encoding="utf-8"))
    assert info["prompt"] == "accordion FAQ"
    assert info["model"] == "gpt-test"
    assert info["slug"] == "accordion"
    assert info["shadcnItemsUsed"] == ["@shadcn/accordion"]
    assert info["requiredNpmDeps"] == []
    assert info["contentHash"].startswith("sha256:")
    assert info["generatedBy"] == "scripts/component_intake.py"

    # contentHash matches the written component.tsx exactly.
    assert info["contentHash"] == ci.content_hash(
        result.component_path.read_text(encoding="utf-8")
    )

    # The gathered shadcn material reached the model call.
    user_msg = client.responses.last_kwargs["input"][1]["content"]
    assert "@shadcn/accordion" in user_msg
    assert "EXAMPLE" in user_msg


def test_intake_records_required_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "has_openai_api_key", lambda: True)
    client = _FakeOpenAI(_candidate(requiredNpmDeps=["@radix-ui/react-accordion"]))

    result = ci.run_component_intake(
        "fancy accordion",
        slug="fancy-accordion",
        output_dir=tmp_path,
        session=_FakeSession(),
        openai_client=client,
        model="gpt-test",
    )
    info = json.loads(result.intake_info_path.read_text(encoding="utf-8"))
    assert info["requiredNpmDeps"] == ["@radix-ui/react-accordion"]
    assert "@radix-ui/react-accordion" in result.readme_path.read_text(encoding="utf-8")


def test_missing_key_is_honest_error_no_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ci, "has_openai_api_key", lambda: False)
    with pytest.raises(ci.ComponentIntakeError, match="NO mock fallback"):
        ci.run_component_intake(
            "accordion",
            slug="accordion",
            output_dir=tmp_path,
            session=_FakeSession(),
            openai_client=_FakeOpenAI(_candidate()),
            model="gpt-test",
        )
    assert list(tmp_path.iterdir()) == []


def test_empty_prompt_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ci.ComponentIntakeError, match="non-empty"):
        ci.run_component_intake("   ", output_dir=tmp_path)


def test_output_dir_guard_refuses_starters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci, "has_openai_api_key", lambda: True)
    with pytest.raises(ci.ComponentIntakeError, match="Refusing to write"):
        ci.run_component_intake(
            "accordion",
            slug="accordion",
            output_dir=ci.STARTERS_DIR / "marketing-base",
            session=_FakeSession(),
            openai_client=_FakeOpenAI(_candidate()),
            model="gpt-test",
        )


def test_output_dir_guard_refuses_orchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci, "has_openai_api_key", lambda: True)
    with pytest.raises(ci.ComponentIntakeError, match="Refusing to write"):
        ci.run_component_intake(
            "accordion",
            slug="accordion",
            output_dir=ci.ORCHESTRATION_DIR / "dossiers",
            session=_FakeSession(),
            openai_client=_FakeOpenAI(_candidate()),
            model="gpt-test",
        )


def test_extract_item_names_falls_back_to_slug() -> None:
    assert ci._extract_item_names("no tokens here", "accordion") == [
        "@shadcn/accordion"
    ]
    names = ci._extract_item_names("@shadcn/accordion and @shadcn/button", "x")
    assert names == ["@shadcn/accordion", "@shadcn/button"]


def test_resolve_intake_model_reads_policy() -> None:
    model = ci.resolve_intake_model()
    assert isinstance(model, str) and model.strip()


def test_slugify_handles_unicode_and_digits() -> None:
    assert ci.slugify("Öppettider Widget") == "oppettider-widget"
    assert ci.slugify("3d carousel").startswith("component-")
