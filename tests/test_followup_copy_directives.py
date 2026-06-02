"""Regression coverage for ADR 0034 path A — copyDirectives passthrough.

The core loop promise is `prompt -> site -> preview -> follow-up -> new
version`. Before this slice a follow-up like "byt namnet i headern till X" was
preserved only as metadata: `merge_followup_project_input` always kept the
previous `company.name`, so the rename never reached the renderer. These tests
lock the deterministic, leak-safe extractor + apply path:

- the operator's reported failing case (rename the company name) now changes
  `company.name` and is visible in the built `app/page.tsx`,
- the ADR acceptance case ("inkludera 'TEST-JAKOB' i hero") surfaces the token
  in the hero tagline,
- non-copy follow-ups produce no directive (the honest no-op path still fires),
- the raw instruction text can never leak into customer copy.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.build_site import build
from scripts.prompt_to_project_input import (
    _extract_copy_directives,
    _extract_copy_directives_via_llm,
    _validate_against_schema,
    _validate_copy_directive_candidate,
    generate,
    generate_followup,
    merge_followup_project_input,
)

OPERATOR_RENAME_PROMPT = "Gör om 'örhängsföretag' på headern till 'jakobs örhängen'"
INCLUDE_TOKEN_PROMPT = (
    "Kan du ändra den där texten vid hero och lite överallt till att "
    "inkludera 'TEST-JAKOB' i typ alla meninar?"
)


def _previous_project_input() -> dict[str, object]:
    """A schema-valid Project Input standing in for a previous version."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "orhangsforetag-abc123",
        "scaffoldId": "ecommerce-lite",
        "variantId": "clean-store",
        "language": "sv",
        "company": {
            "name": "Örhängsföretaget",
            "businessType": "shop",
            "tagline": "Handgjorda örhängen i Malmö",
            "story": "En liten butik med stor passion.",
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö"],
        },
        "services": [
            {"id": "orhangen", "label": "Örhängen", "summary": "Fina örhängen."}
        ],
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "kontakt@example.se",
            "addressLines": ["Adress lämnas på förfrågan"],
            "openingHours": "Mån-Fre 9-17",
        },
        "selectedDossiers": {"required": [], "recommended": []},
    }


def _merge(
    prompt: str,
    previous: dict[str, object] | None = None,
    *,
    enable_llm_fallback: bool = False,
) -> dict[str, object]:
    previous = previous or _previous_project_input()
    return merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt=prompt,
        enable_llm_fallback=enable_llm_fallback,
    )


@pytest.mark.tooling
def test_extract_rename_directive_from_operator_case() -> None:
    directives = _extract_copy_directives(OPERATOR_RENAME_PROMPT, language="sv")
    assert directives == [
        {
            "target": "company-name",
            "operation": "replace-text",
            "payload": "Jakobs Örhängen",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_extract_rename_preserves_intended_casing() -> None:
    directives = _extract_copy_directives(
        "byt företagsnamnet till Volvo", language="sv"
    )
    assert directives[0]["payload"] == "Volvo"


@pytest.mark.tooling
def test_extract_include_token_targets_hero_tagline() -> None:
    directives = _extract_copy_directives(INCLUDE_TOKEN_PROMPT, language="sv")
    assert directives == [
        {
            "target": "tagline",
            "operation": "include-token",
            "payload": "TEST-JAKOB",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_extract_tagline_replace() -> None:
    directives = _extract_copy_directives(
        "ändra underrubriken till 'Vi fixar allt inom el'", language="sv"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "Vi fixar allt inom el",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "lägg till en kontaktsida",
        "gör tonen varmare",
        "Allt ska vara mycket ljusare",
        "kan du göra sidan finare",
        "byt namnet",  # no value after a till/to marker
    ],
)
def test_extract_returns_empty_for_non_copy_followups(prompt: str) -> None:
    assert _extract_copy_directives(prompt, language="sv") == []


@pytest.mark.tooling
def test_leak_guard_rejects_instruction_text_as_payload() -> None:
    # Extraction would grab instruction text after "till"; the change-verb
    # reject + planner-note guard must drop it rather than render it.
    prompt = "ändra namnet till att du ändrar och byter rubriken"
    assert _extract_copy_directives(prompt, language="sv") == []


# --- Codex hardening 2026-06-01: copyDirective edge cases ---------------------


@pytest.mark.tooling
def test_company_rename_to_changemakers_is_not_rejected() -> None:
    """A real one-word name that merely *contains* a reject-verb must apply.

    "Changemakers" contains the substring "change"; the old substring reject
    no-op:ed the rename. Word-boundary matching lets the rename through.
    """
    directives = _extract_copy_directives(
        "byt företagsnamnet till Changemakers", language="sv"
    )
    assert directives == [
        {
            "target": "company-name",
            "operation": "replace-text",
            "payload": "Changemakers",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_service_scoped_generic_namn_does_not_rename_company() -> None:
    """A generic "namn/namnet" scoped to a service must not touch company.name."""
    assert (
        _extract_copy_directives(
            "byt namnet på tjänsten till Akut eljour", language="sv"
        )
        == []
    )


@pytest.mark.tooling
def test_past_tense_bytte_narrative_does_not_trigger_replace() -> None:
    """Past-tense narration is not an imperative copy-directive command."""
    assert (
        _extract_copy_directives("Jag bytte företagsnamnet till Ny Namn", language="sv")
        == []
    )


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "byt namnet på produkten till Premiumpaket",
        "ändra namnet på sidan till Startsidan",
    ],
)
def test_product_or_page_scoped_generic_namn_is_no_op(prompt: str) -> None:
    assert _extract_copy_directives(prompt, language="sv") == []


@pytest.mark.tooling
def test_explicit_company_name_keyword_wins_over_scope_word() -> None:
    """``företagsnamnet`` is explicit, so a stray scope word does not block it."""
    directives = _extract_copy_directives(
        "ändra företagsnamnet (inte tjänsten) till Akustik", language="sv"
    )
    assert directives == [
        {
            "target": "company-name",
            "operation": "replace-text",
            "payload": "Akustik",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_merge_service_scoped_namn_keeps_company_name() -> None:
    merged = _merge("byt namnet på tjänsten till Akut eljour")
    assert merged["company"]["name"] == "Örhängsföretaget"
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_unquoted_trailing_instruction_is_not_captured_as_tagline() -> None:
    """"change the hero to be more premium" must not publish "be more premium"."""
    assert _extract_copy_directives("change the hero to be more premium", language="en") == []
    assert _extract_copy_directives("gör om hero till att bli mer exklusiv", language="sv") == []


@pytest.mark.tooling
def test_quoted_value_after_to_is_still_respected() -> None:
    """The instruction guard only narrows the UNQUOTED trailing branch."""
    directives = _extract_copy_directives(
        "ändra underrubriken till 'Be bold'", language="en"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "Be bold",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_extract_unquoted_include_token_targets_hero_tagline() -> None:
    """Unquoted "inkludera TEST-JAKOB i hero" surfaces the token (B-Codex 2026-06-01).

    Previously only quoted tokens were extracted, so the natural unquoted
    phrasing of the ADR 0034 acceptance case was a silent no-op.
    """
    directives = _extract_copy_directives("inkludera TEST-JAKOB i hero", language="sv")
    assert directives == [
        {
            "target": "tagline",
            "operation": "include-token",
            "payload": "TEST-JAKOB",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "inkludera mer text i hero",  # no token-like word -> honest no-op
        "lägg till lite mer i rubriken",  # vague, lowercase
    ],
)
def test_extract_unquoted_include_without_token_is_no_op(prompt: str) -> None:
    assert _extract_copy_directives(prompt, language="sv") == []


@pytest.mark.tooling
def test_extract_unquoted_include_token_with_digits() -> None:
    """A digit-bearing token (campaign code) also qualifies."""
    directives = _extract_copy_directives("inkludera SALE2026 i hero", language="sv")
    assert directives == [
        {
            "target": "tagline",
            "operation": "include-token",
            "payload": "SALE2026",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_merge_applies_company_name_and_records_directive() -> None:
    merged = _merge(OPERATOR_RENAME_PROMPT)
    assert merged["company"]["name"] == "Jakobs Örhängen"
    assert merged["directives"]["copyDirectives"] == [
        {
            "target": "company-name",
            "operation": "replace-text",
            "payload": "Jakobs Örhängen",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_merge_include_token_appends_to_tagline() -> None:
    merged = _merge(INCLUDE_TOKEN_PROMPT)
    assert "TEST-JAKOB" in merged["company"]["tagline"]
    # original tagline copy is preserved, token appended
    assert merged["company"]["tagline"].startswith("Handgjorda örhängen")


@pytest.mark.tooling
def test_merged_project_input_passes_schema() -> None:
    merged = _merge(OPERATOR_RENAME_PROMPT)
    # Must not raise: directives.copyDirectives has to be schema-valid.
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_merge_clears_inherited_copy_directives_on_unrelated_followup() -> None:
    previous = _previous_project_input()
    previous["directives"] = {
        "copyDirectives": [
            {
                "target": "company-name",
                "operation": "replace-text",
                "payload": "Gammalt Namn",
                "source": "prompt-rule",
            }
        ]
    }
    merged = _merge("gör tonen varmare", previous=previous)
    # The stale rename directive must not linger and re-claim an effect.
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_merge_preserves_other_directives_when_no_copy_directive() -> None:
    previous = _previous_project_input()
    previous["directives"] = {"layoutHint": "split"}
    merged = _merge("gör tonen varmare", previous=previous)
    assert merged["directives"]["layoutHint"] == "split"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_two_versions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    init_prompt: str,
    followup_prompt: str,
    site_id: str,
    project_id: str,
) -> tuple[Path, dict[str, object]]:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        init_prompt,
        output_dir=prompt_inputs_dir,
        site_id=site_id,
        project_id=project_id,
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)

    _, _, followup_path, _ = generate_followup(
        followup_prompt,
        output_dir=prompt_inputs_dir,
        site_id=site_id,
    )
    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )
    page = run_dir_v2 / "generated-files" / "app" / "page.tsx"
    return page, _read_json(run_dir_v2 / "build-result.json")


@pytest.mark.tooling
def test_end_to_end_rename_visible_in_page_and_build_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ADR 0034 acceptance: a rename follow-up reaches the rendered page."""
    page, build_result = _build_two_versions(
        monkeypatch,
        tmp_path,
        init_prompt="Skapa en hemsida för Surdegsbagaren i Malmö.",
        followup_prompt="byt företagsnamnet till TestbolagXYZ",
        site_id="surdegsbagaren-rename",
        project_id="copydir-rename",
    )
    assert "TestbolagXYZ" in page.read_text(encoding="utf-8")
    assert build_result["engineMode"] == "followup"
    assert build_result["appliedVisibleEffect"] is True


@pytest.mark.tooling
def test_llm_candidate_is_validated_and_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "company-name",
                "operation": "replace-text",
                "payload": "Nordens Smycken",
                "source": "llm",
            }
        ],
    )
    directives = _extract_copy_directives_via_llm(
        "kan du kalla firman något helt annat",
        company={"name": "Gammalt", "tagline": "Tagline"},
        language="sv",
    )
    assert directives == [
        {
            "target": "company-name",
            "operation": "replace-text",
            "payload": "Nordens Smycken",
            "source": "llm",
        }
    ]


@pytest.mark.tooling
def test_llm_candidate_with_instruction_text_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "company-name",
                "operation": "replace-text",
                "payload": "byt namnet till något annat",
                "source": "llm",
            }
        ],
    )
    directives = _extract_copy_directives_via_llm(
        "byt namnet till något annat",
        company={"name": "Gammalt", "tagline": "Tagline"},
        language="sv",
    )
    assert directives == []


@pytest.mark.tooling
def test_llm_invalid_target_is_dropped() -> None:
    directive = _validate_copy_directive_candidate(
        {"target": "footer", "operation": "replace-text", "payload": "X"},
        follow_up_prompt="ändra footern till X",
    )
    assert directive is None


@pytest.mark.tooling
def test_llm_path_runs_in_merge_when_deterministic_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deterministic rules return [] for this phrasing; the (mocked) briefModel
    # fallback supplies a validated rename that the merge then applies.
    assert _extract_copy_directives("kan du kalla firman något helt annat", language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "company-name",
                "operation": "replace-text",
                "payload": "Nordens Smycken",
                "source": "llm",
            }
        ],
    )
    merged = _merge("kan du kalla firman något helt annat", enable_llm_fallback=True)
    assert merged["company"]["name"] == "Nordens Smycken"
    assert merged["directives"]["copyDirectives"][0]["source"] == "llm"


@pytest.mark.tooling
def test_end_to_end_include_token_visible_in_hero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ADR 0034 acceptance: 'inkludera TEST-JAKOB i hero' surfaces the token."""
    page, build_result = _build_two_versions(
        monkeypatch,
        tmp_path,
        init_prompt="Skapa en hemsida för Surdegsbagaren i Malmö.",
        followup_prompt="inkludera 'TEST-JAKOB' i hero",
        site_id="surdegsbagaren-token",
        project_id="copydir-token",
    )
    assert "TEST-JAKOB" in page.read_text(encoding="utf-8")
    assert build_result["appliedVisibleEffect"] is True


# --- slice 2a: about-text target (company.story), ADR 0034 väg A nivå 2 ---

ABOUT_REPLACE_PROMPT = "ändra om oss-texten till 'Vi är ett familjeföretag sedan 1982'"


@pytest.mark.tooling
def test_extract_about_text_replace_from_explicit_value() -> None:
    directives = _extract_copy_directives(ABOUT_REPLACE_PROMPT, language="sv")
    assert directives == [
        {
            "target": "about-text",
            "operation": "replace-text",
            "payload": "Vi är ett familjeföretag sedan 1982",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_extract_about_text_via_rewrite_verb_with_value() -> None:
    directives = _extract_copy_directives(
        "skriv om om-oss-texten till 'En personlig berättelse om vårt hantverk'",
        language="sv",
    )
    assert directives == [
        {
            "target": "about-text",
            "operation": "replace-text",
            "payload": "En personlig berättelse om vårt hantverk",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_about_text_vibe_rewrite_without_value_is_honest_no_op() -> None:
    """A vibe-only rewrite has no literal new copy; slice 2a stays an honest
    no-op (generating about copy from an instruction is later-level LLM work)."""
    assert (
        _extract_copy_directives(
            "skriv om om oss så det låter mer personligt", language="sv"
        )
        == []
    )


@pytest.mark.tooling
def test_about_text_does_not_hijack_service_text() -> None:
    """Service/product copy must never become about-text (or tagline)."""
    assert (
        _extract_copy_directives(
            "byt tjänstbeskrivningen till 'Akut eljour dygnet runt'", language="sv"
        )
        == []
    )


@pytest.mark.tooling
def test_tone_prompt_is_not_about_text() -> None:
    assert _extract_copy_directives("gör tonen mer premium", language="sv") == []


@pytest.mark.tooling
def test_merge_applies_about_text_to_story() -> None:
    merged = _merge(ABOUT_REPLACE_PROMPT)
    assert merged["company"]["story"] == "Vi är ett familjeföretag sedan 1982"
    assert merged["directives"]["copyDirectives"] == [
        {
            "target": "about-text",
            "operation": "replace-text",
            "payload": "Vi är ett familjeföretag sedan 1982",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_merged_about_text_passes_schema() -> None:
    merged = _merge(ABOUT_REPLACE_PROMPT)
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_about_text_rejects_include_token_candidate() -> None:
    """about-text is replace-only in slice 2a; a model include-token is dropped."""
    directive = _validate_copy_directive_candidate(
        {"target": "about-text", "operation": "include-token", "payload": "X"},
        follow_up_prompt="lägg till X i om oss",
    )
    assert directive is None


@pytest.mark.tooling
def test_about_text_validate_replace_candidate_ok() -> None:
    directive = _validate_copy_directive_candidate(
        {
            "target": "about-text",
            "operation": "replace-text",
            "payload": "Vi grundades 1998 av två systrar i Lund.",
        },
        follow_up_prompt="skriv om om oss så den nämner att vi grundades 1998",
    )
    assert directive is not None
    assert directive["target"] == "about-text"
    assert directive["operation"] == "replace-text"
    assert directive["source"] == "llm"
    assert directive["payload"].startswith("Vi grundades 1998")


@pytest.mark.tooling
def test_llm_about_text_candidate_applied_in_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deterministic rules find no explicit value here; the mocked model supplies
    # a validated about-text replace that the merge applies to company.story.
    assert _extract_copy_directives("fixa om oss-texten lite", language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "Ett familjeägt bageri i hjärtat av Malmö sedan 1962.",
                "source": "llm",
            }
        ],
    )
    merged = _merge("fixa om oss-texten lite", enable_llm_fallback=True)
    assert merged["company"]["story"].startswith("Ett familjeägt bageri")
    assert merged["directives"]["copyDirectives"][0]["target"] == "about-text"
    assert merged["directives"]["copyDirectives"][0]["source"] == "llm"


@pytest.mark.tooling
def test_end_to_end_about_text_visible_in_generated_site(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Slice 2a acceptance: an about-text follow-up reaches the rendered site."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        "Skapa en hemsida för Surdegsbagaren i Malmö.",
        output_dir=prompt_inputs_dir,
        site_id="surdegsbagaren-about",
        project_id="copydir-about",
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)

    unique = "Vi grundades 1962 av tre systrar med kärlek för surdeg"
    _, _, followup_path, _ = generate_followup(
        f"ändra om oss-texten till '{unique}'",
        output_dir=prompt_inputs_dir,
        site_id="surdegsbagaren-about",
    )
    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )
    generated_files = run_dir_v2 / "generated-files"
    found = any(
        unique in path.read_text(encoding="utf-8")
        for path in generated_files.rglob("*.tsx")
    )
    assert found, "about story text should appear in the generated site"
    build_result = _read_json(run_dir_v2 / "build-result.json")
    assert build_result["engineMode"] == "followup"
    assert build_result["appliedVisibleEffect"] is True


# --- slice 2c: services target (services[].summary via targetRef) ---

SERVICES_REPLACE_PROMPT = (
    "ändra tjänsten 'Örhängen' till 'Handgjorda örhängen i återvunnet silver'"
)


@pytest.mark.tooling
def test_extract_services_replace_from_quoted_ref_and_value() -> None:
    directives = _extract_copy_directives(SERVICES_REPLACE_PROMPT, language="sv")
    assert directives == [
        {
            "target": "services",
            "operation": "replace-text",
            "payload": "Handgjorda örhängen i återvunnet silver",
            "targetRef": "Örhängen",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_extract_services_unquoted_ref() -> None:
    directives = _extract_copy_directives(
        "byt beskrivningen av tjänsten Örhängen till 'Snygga handgjorda örhängen'",
        language="sv",
    )
    assert directives == [
        {
            "target": "services",
            "operation": "replace-text",
            "payload": "Snygga handgjorda örhängen",
            "targetRef": "Örhängen",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_merge_applies_services_summary_to_matched_service() -> None:
    merged = _merge(SERVICES_REPLACE_PROMPT)
    assert (
        merged["services"][0]["summary"] == "Handgjorda örhängen i återvunnet silver"
    )
    assert merged["services"][0]["id"] == "orhangen"  # id/label unchanged
    assert merged["services"][0]["label"] == "Örhängen"
    assert merged["directives"]["copyDirectives"] == [
        {
            "target": "services",
            "operation": "replace-text",
            "payload": "Handgjorda örhängen i återvunnet silver",
            "targetRef": "Örhängen",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_merge_services_matches_by_id_not_only_label() -> None:
    """A targetRef that matches a service id (not its label) still resolves."""
    merged = _merge("ändra tjänsten 'orhangen' till 'Handgjorda örhängen i silver'")
    assert merged["services"][0]["summary"] == "Handgjorda örhängen i silver"
    assert merged["directives"]["copyDirectives"][0]["targetRef"] == "orhangen"


@pytest.mark.tooling
def test_services_unknown_service_is_honest_no_op() -> None:
    """An unknown service ref never creates/hijacks a service; it is a no-op."""
    merged = _merge("ändra tjänsten 'Klippning' till 'Snabb herrklippning'")
    assert merged["services"][0]["summary"] == "Fina örhängen."  # unchanged
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_services_additive_new_service_is_no_op() -> None:
    """Adding a new service is the semantic merge's job, never a copy replace."""
    assert (
        _extract_copy_directives(
            "lägg till ny tjänst 'Klippning' med beskrivning 'Snabb klippning'",
            language="sv",
        )
        == []
    )


@pytest.mark.tooling
def test_services_without_named_service_is_no_op() -> None:
    """A generic services edit with no named service stays an honest no-op."""
    assert (
        _extract_copy_directives("ändra tjänsten till 'Ny text'", language="sv") == []
    )


@pytest.mark.tooling
def test_merged_services_directive_passes_schema() -> None:
    merged = _merge(SERVICES_REPLACE_PROMPT)
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_services_validate_candidate_requires_target_ref() -> None:
    without_ref = _validate_copy_directive_candidate(
        {"target": "services", "operation": "replace-text", "payload": "Ny summary"},
        follow_up_prompt="ändra tjänsten Örhängen till Ny summary",
    )
    assert without_ref is None
    with_ref = _validate_copy_directive_candidate(
        {
            "target": "services",
            "operation": "replace-text",
            "payload": "Handgjorda örhängen i silver",
            "targetRef": "Örhängen",
        },
        follow_up_prompt="ändra tjänsten Örhängen till Handgjorda örhängen i silver",
    )
    assert with_ref is not None
    assert with_ref["target"] == "services"
    assert with_ref["targetRef"] == "Örhängen"
    assert with_ref["source"] == "llm"


@pytest.mark.tooling
def test_services_rejects_include_token_candidate() -> None:
    directive = _validate_copy_directive_candidate(
        {
            "target": "services",
            "operation": "include-token",
            "payload": "X",
            "targetRef": "Örhängen",
        },
        follow_up_prompt="lägg till X i tjänsten Örhängen",
    )
    assert directive is None


@pytest.mark.tooling
def test_llm_services_candidate_applied_in_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deterministic rules miss (no replace verb / value); the mocked model
    # supplies a validated services replace the merge applies to the summary.
    assert _extract_copy_directives("fixa tjänsten örhängen lite", language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": "Handgjorda örhängen gjutna i Malmö",
                "targetRef": "orhangen",
                "source": "llm",
            }
        ],
    )
    merged = _merge("fixa tjänsten örhängen lite", enable_llm_fallback=True)
    assert merged["services"][0]["summary"] == "Handgjorda örhängen gjutna i Malmö"
    assert merged["directives"]["copyDirectives"][0]["target"] == "services"
    assert merged["directives"]["copyDirectives"][0]["targetRef"] == "orhangen"
    assert merged["directives"]["copyDirectives"][0]["source"] == "llm"


@pytest.mark.tooling
def test_end_to_end_services_summary_visible_in_generated_site(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Slice 2c acceptance: a services follow-up reaches the rendered site."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    pi_v1, _, init_path, _ = generate(
        "Skapa en hemsida för Elflödet Elektriker i Malmö.",
        output_dir=prompt_inputs_dir,
        site_id="elflodet-services",
        project_id="copydir-services",
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)
    service_label = pi_v1["services"][0]["label"]

    unique = "Felsökning och akut eljour dygnet runt i hela Malmö"
    _, _, followup_path, _ = generate_followup(
        f"ändra tjänsten '{service_label}' till '{unique}'",
        output_dir=prompt_inputs_dir,
        site_id="elflodet-services",
    )
    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )
    generated_files = run_dir_v2 / "generated-files"
    found = any(
        unique in path.read_text(encoding="utf-8")
        for path in generated_files.rglob("*.tsx")
    )
    assert found, "service summary should appear in the generated site"
    build_result = _read_json(run_dir_v2 / "build-result.json")
    assert build_result["engineMode"] == "followup"
    assert build_result["appliedVisibleEffect"] is True
