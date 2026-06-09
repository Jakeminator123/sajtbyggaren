"""Behavior-parity lock for the prompt-meta reader family before it moves.

``docs/refactor/megafiles-plan.md`` (Del 2, slice 3) extracts the prompt-input
meta reader family from ``scripts/build_site.py`` into
``packages/generation/build/prompt_meta.py``. Today ``load_prompt_input_meta``
and the ``_prompt_meta_*`` accessors are only exercised indirectly (builder
smoke + follow-up versioning regression), so this file closes that gap with a
focused unit lock over a representative sidecar pair (init + follow-up).

With the lock in place the extraction can be proven behavior-preserving: the
test passes against the pre-move code (it captured the contract) and must keep
passing against the post-move re-export.

All symbols are imported via ``scripts.build_site`` on purpose: that spelling
must keep resolving through the re-export façade after the move, so the test
doubles as a guard that the façade stays intact (``build()`` /
``build_targeted_version()`` and the tests call these as bare ``scripts``
names).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _followup_meta() -> dict[str, Any]:
    """A representative follow-up sidecar with every field the readers touch."""
    return {
        "siteId": "painter-palma",
        "projectId": "01HPROMPTMETA000000000000001",
        "version": 3,
        "previousVersion": 2,
        "mode": "followup",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "originalPrompt": "Bygg en sajt åt måleriföretaget Palma.",
        "followUpPrompt": "Gör hjältesektionen lugnare och lägg till priser.",
        # Mixes a valid contact field, a duplicate and an unknown key so the
        # filter + dedupe contract is locked.
        "placeholderContactFields": ["phone", "email", "phone", "bogus"],
        # Mixes blanks + duplicates so the strip + dedupe contract is locked.
        "wizardMustHave": ["Priser", "  ", "Priser", "Öppettider"],
        "projectDna": {"followUpIntent": {"id": "section_add"}},
        "copyDirectives": [{"target": "hero", "text": "ny rubrik"}],
    }


@pytest.mark.tooling
def test_load_prompt_input_meta_init_no_sidecar(tmp_path: Path) -> None:
    """A curated-example layout (current-pointer filename outside
    ``prompt-inputs/``) with no sidecar keeps the historical init-mode
    contract.
    """
    from scripts.build_site import load_prompt_input_meta

    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    dossier_path = examples_dir / "painter-palma.project-input.json"
    dossier_path.write_text(
        json.dumps({"siteId": "painter-palma"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = load_prompt_input_meta(dossier_path, {"siteId": "painter-palma"})
    assert result == {"mode": "init"}


@pytest.mark.tooling
def test_load_prompt_input_meta_normalizes_followup_sidecar(tmp_path: Path) -> None:
    """A versioned follow-up sidecar is normalized: ``mode`` resolved,
    ``metaPath`` recorded (POSIX), every other field preserved.
    """
    from scripts.build_site import load_prompt_input_meta

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    prompt_inputs_dir.mkdir()
    dossier_path = prompt_inputs_dir / "painter-palma.v3.project-input.json"
    dossier = {"siteId": "painter-palma"}
    dossier_path.write_text(
        json.dumps(dossier, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    meta_path = prompt_inputs_dir / "painter-palma.v3.meta.json"
    meta = _followup_meta()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")

    result = load_prompt_input_meta(dossier_path, dossier)

    assert result["mode"] == "followup"
    assert result["projectId"] == meta["projectId"]
    assert result["version"] == 3
    assert result["previousVersion"] == 2
    assert result["metaPath"].endswith("painter-palma.v3.meta.json")
    assert "\\" not in result["metaPath"]
    # Original fields survive the normalization untouched.
    assert result["followUpPrompt"] == meta["followUpPrompt"]
    assert result["wizardMustHave"] == meta["wizardMustHave"]


@pytest.mark.tooling
def test_prompt_meta_accessors_followup_contract() -> None:
    """Lock every ``_prompt_meta_*`` accessor against the representative
    follow-up sidecar, including the filter/dedupe/strip rules.
    """
    from scripts.build_site import (
        _has_copy_directives,
        _placeholder_contact_warning_message,
        _prompt_meta_followup_intent_id,
        _prompt_meta_mode,
        _prompt_meta_placeholder_contact_fields,
        _prompt_meta_previous_version,
        _prompt_meta_project_id,
        _prompt_meta_raw_prompt,
        _prompt_meta_version,
        _prompt_meta_wizard_must_have,
    )

    meta = _followup_meta()

    assert _prompt_meta_mode(meta) == "followup"
    assert _prompt_meta_project_id(meta) == "01HPROMPTMETA000000000000001"
    assert _prompt_meta_version(meta) == 3
    assert _prompt_meta_previous_version(meta) == 2
    # follow-up -> followUpPrompt wins over originalPrompt.
    assert _prompt_meta_raw_prompt(meta) == meta["followUpPrompt"]
    # filter to known fields + dedupe, preserve first-seen order.
    assert _prompt_meta_placeholder_contact_fields(meta) == ["phone", "email"]
    # strip + dedupe + drop blanks.
    assert _prompt_meta_wizard_must_have(meta) == ["Priser", "Öppettider"]
    assert _prompt_meta_followup_intent_id(meta) == "section_add"
    assert _has_copy_directives(meta) is True
    assert _placeholder_contact_warning_message(["phone", "email"]) == (
        "Contact fields phone, email are placeholder values - operator "
        "must fill these before publishing."
    )


@pytest.mark.tooling
def test_prompt_meta_accessors_empty_and_init_defaults() -> None:
    """The accessors degrade safely on ``None`` / empty / init metadata.

    Locks the previous-version derivation fallback (``version - 1`` when the
    sidecar omits ``previousVersion``) and the init-prompt selection.
    """
    from scripts.build_site import (
        _has_copy_directives,
        _prompt_meta_followup_intent_id,
        _prompt_meta_mode,
        _prompt_meta_placeholder_contact_fields,
        _prompt_meta_previous_version,
        _prompt_meta_project_id,
        _prompt_meta_raw_prompt,
        _prompt_meta_version,
        _prompt_meta_wizard_must_have,
    )

    assert _prompt_meta_mode(None) == "init"
    assert _prompt_meta_project_id(None) is None
    assert _prompt_meta_version(None) is None
    assert _prompt_meta_previous_version(None) is None
    assert _prompt_meta_raw_prompt(None) is None
    assert _prompt_meta_placeholder_contact_fields(None) == []
    assert _prompt_meta_wizard_must_have(None) == []
    assert _prompt_meta_followup_intent_id(None) is None
    assert _has_copy_directives(None) is False

    init_meta = {
        "mode": "init",
        "version": 4,
        "originalPrompt": "Bygg en sajt åt måleriföretaget Palma.",
    }
    # init -> originalPrompt selected.
    assert _prompt_meta_raw_prompt(init_meta) == init_meta["originalPrompt"]
    # previousVersion derived from version - 1 when absent.
    assert _prompt_meta_previous_version(init_meta) == 3
