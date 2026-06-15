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
    _copy_directive_llm_eligible,
    _extract_copy_directives,
    _extract_copy_directives_via_llm,
    _is_content_rewrite_request,
    _validate_against_schema,
    _validate_copy_directive_candidate,
    classify_followup_intent,
    generate,
    generate_followup,
    merge_followup_project_input,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

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


# --- 2026-06-08 diagnosis: "rubrik" means the hero H1, not the company name ---


@pytest.mark.tooling
def test_extract_rubrik_targets_hero_tagline() -> None:
    """The live-demo failure: "byt rubriken på startsidan" edited the company
    NAME instead of the hero H1 because "rubrik" sat in the name keyword set.

    A heading ("rubrik"/"huvudrubrik") is the hero tagline; only an explicit
    company-name keyword (företagsnamn/header/heter/rename) should rename the
    company. Regression for docs/diagnosis-and-handoff-2026-06-08.md class A.
    """
    directives = _extract_copy_directives(
        "byt rubriken på startsidan till 'Jakobs smålandshöns'", language="sv"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "Jakobs smålandshöns",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_extract_huvudrubrik_targets_hero_tagline() -> None:
    directives = _extract_copy_directives(
        "ändra huvudrubriken till 'Vi bygger framtidens hus'", language="sv"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "Vi bygger framtidens hus",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_explicit_company_name_keyword_still_renames_company() -> None:
    """The contrast guard: after rubrik* moved to the tagline set, an explicit
    company-name keyword must still target company-name (not regress to a
    no-op or hijack the tagline)."""
    directives = _extract_copy_directives(
        "byt företagsnamnet till 'Jakobs Smålandshöns'", language="sv"
    )
    assert directives == [
        {
            "target": "company-name",
            "operation": "replace-text",
            "payload": "Jakobs Smålandshöns",
            "source": "prompt-rule",
        }
    ]


# --- 2026-06-08 phrasing slice: "<NEW> istället för <OLD>" ------------------


@pytest.mark.tooling
def test_extract_hero_text_instead_of_phrasing() -> None:
    """The operator's natural phrasing 'gör ... herotexten "X" istället för
    "Y"' lands the hero tagline = X. The text after the marker is the OLD value
    and is ignored. Regression for the 2026-06-08 live-demo no-op."""
    directives = _extract_copy_directives(
        'Gör sajten med herotexten "ölälskarna från palma" istället för '
        '"En tydlig och lugn företagswebb"',
        language="sv",
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "ölälskarna från palma",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_instead_of_marker_with_till_takes_new_value_before_marker() -> None:
    directives = _extract_copy_directives(
        'ändra rubriken till "Nytt" istället för "Gammalt"', language="sv"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "Nytt",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_unquoted_instead_of_is_honest_no_op() -> None:
    """No quoted new value before the marker -> honest no-op (never guess)."""
    assert (
        _extract_copy_directives(
            "gör herotexten blå istället för röd", language="sv"
        )
        == []
    )


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
def test_llm_extraction_path_drops_about_text_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extraction fallback only carries company-name/tagline. Generated
    about copy must come from the planner path (rewrite-verb + grounding), never
    the extraction fallback - so a vague non-rewrite prompt is an honest no-op
    even if the model returns about-text copy (reviewer P2 2026-06-02)."""
    previous = _previous_project_input()
    assert _extract_copy_directives("fixa om oss-texten lite", language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "Ett familjeägt bageri i hjärtat av Malmö.",
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "fixa om oss-texten lite", previous=previous, enable_llm_fallback=True
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


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
def test_llm_extraction_path_drops_services_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extraction fallback must not apply a services rewrite either; that is
    planner-path territory (reviewer P2 2026-06-02)."""
    previous = _previous_project_input()
    assert (
        _extract_copy_directives("fixa tjänsten örhängen lite", language="sv") == []
    )
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
    merged = _merge(
        "fixa tjänsten örhängen lite", previous=previous, enable_llm_fallback=True
    )
    assert merged["services"][0]["summary"] == previous["services"][0]["summary"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


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


# --- nivå 3a: editPlan planner (generation-with-guards) ---

_PLANNER_PATH = "packages.generation.brief.extract.plan_copy_directives_llm"


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "skriv om om oss så det låter mer personligt",
        "förbättra om-oss-texten så den känns mer levande",
        "förbättra tjänsten 'Örhängen' så den låter mer säljande",
        "skriv om tjänsten 'Örhängen' så den blir tydligare",
    ],
)
def test_is_content_rewrite_request_positive(prompt: str) -> None:
    assert _is_content_rewrite_request(prompt) is True


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "gör tonen mer premium",
        "ändra om oss-texten till 'En ny text'",
        "förbättra tjänsten så den blir bättre",
        "förbättra texten lite",
        "lägg till ny tjänst 'Klippning'",
    ],
)
def test_is_content_rewrite_request_negative(prompt: str) -> None:
    assert _is_content_rewrite_request(prompt) is False


@pytest.mark.tooling
def test_merge_planned_about_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    new_story = "Vi är ett litet familjeföretag med stort hjärta i Malmö"
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": new_story,
                "source": "llm",
            }
        ],
    )
    # Deterministic + extraction paths must miss; only the planner fires.
    assert (
        _extract_copy_directives(
            "skriv om om oss så det låter mer personligt", language="sv"
        )
        == []
    )
    merged = _merge(
        "skriv om om oss så det låter mer personligt", enable_llm_fallback=True
    )
    assert merged["company"]["story"] == new_story
    assert merged["directives"]["copyDirectives"][0]["target"] == "about-text"
    assert merged["directives"]["copyDirectives"][0]["source"] == "llm"


@pytest.mark.tooling
def test_merge_planned_service_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    new_summary = "Unika handgjorda örhängen i återvunnet silver"
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": new_summary,
                "targetRef": "Örhängen",
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "förbättra tjänsten 'Örhängen' så den låter mer säljande",
        enable_llm_fallback=True,
    )
    assert merged["services"][0]["summary"] == new_summary
    assert merged["directives"]["copyDirectives"][0]["target"] == "services"
    assert merged["directives"]["copyDirectives"][0]["targetRef"] == "Örhängen"


@pytest.mark.tooling
def test_planner_leak_instruction_payload_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated payload that is really an instruction is dropped (no-op)."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "byt namnet till något annat",
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "skriv om om oss så det låter mer personligt", enable_llm_fallback=True
    )
    assert merged["company"]["story"] == "En liten butik med stor passion."
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planner_drops_company_name_and_tagline_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """nivå 3a only generates about/services copy; name/tagline are dropped."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {"target": "company-name", "operation": "replace-text", "payload": "Nytt Namn", "source": "llm"},
            {"target": "tagline", "operation": "replace-text", "payload": "Ny tagline här", "source": "llm"},
        ],
    )
    merged = _merge(
        "skriv om om oss så det låter mer personligt", enable_llm_fallback=True
    )
    assert merged["company"]["name"] == "Örhängsföretaget"  # unchanged
    assert merged["company"]["tagline"] == "Handgjorda örhängen i Malmö"  # unchanged
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planner_unknown_service_is_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": "Snabb och prydlig herrklippning",
                "targetRef": "Klippning",
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "förbättra tjänsten 'Klippning' så den blir bättre", enable_llm_fallback=True
    )
    assert merged["services"][0]["summary"] == "Fina örhängen."
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planner_drops_ungrounded_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """A generated payload that invents an unfounded year is dropped."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "Vi har levererat kvalitet sedan 1985",
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "skriv om om oss så det låter mer etablerat", enable_llm_fallback=True
    )
    assert merged["company"]["story"] == "En liten butik med stor passion."
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planner_allows_year_grounded_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    new_story = "Vi grundades 1985 av en lokal silversmed i Malmö"
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": new_story,
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "skriv om om oss och nämn att vi grundades 1985", enable_llm_fallback=True
    )
    assert merged["company"]["story"] == new_story


@pytest.mark.tooling
def test_planner_drops_ungrounded_multi_digit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The grounding guard now covers any multi-digit number, not just years:
    an invented price/count is dropped (honest no-op)."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "Vi har glatt över 5000 kunder genom åren",
                "source": "llm",
            }
        ],
    )
    previous = _previous_project_input()
    merged = _merge(
        "skriv om om oss så det låter mer etablerat",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planner_grounding_is_whole_token_not_substring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shorter ungrounded number must not slip through as a substring of a
    longer grounded one: payload '500' is NOT grounded by prompt '5000'."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "Prova vårt erbjudande för 500 kr",
                "source": "llm",
            }
        ],
    )
    previous = _previous_project_input()
    merged = _merge(
        "skriv om om oss och nämn att vi haft 5000 kunder",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planner_allows_grounded_number_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A number the operator supplied in the prompt is grounded and allowed."""
    new_story = "Vi har glatt över 5000 kunder sedan starten"
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": new_story,
                "source": "llm",
            }
        ],
    )
    merged = _merge(
        "skriv om om oss och nämn att vi haft över 5000 kunder",
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == new_story


@pytest.mark.tooling
def test_end_to_end_planned_about_rewrite_visible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Nivå 3a acceptance: a planned about rewrite reaches the rendered site."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    unique = "Ett familjeägt smyckesmärke med stort hjärta mitt i Malmö"
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": unique,
                "source": "llm",
            }
        ],
    )
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        "Skapa en hemsida för Smyckesboden i Malmö.",
        output_dir=prompt_inputs_dir,
        site_id="smyckesboden-plan",
        project_id="copydir-plan",
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)

    _, _, followup_path, _ = generate_followup(
        "skriv om om oss så det låter mer personligt",
        output_dir=prompt_inputs_dir,
        site_id="smyckesboden-plan",
        enable_copy_directive_llm=True,
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
    assert found, "planned about rewrite should appear in the generated site"
    build_result = _read_json(run_dir_v2 / "build-result.json")
    assert build_result["appliedVisibleEffect"] is True


# --- reviewer edge cases 2026-06-02 (pre-sync-PR hardening) ---


@pytest.mark.tooling
def test_about_rewrite_to_quality_phrase_does_not_publish_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vibe rewrite via trailing 'till' must never publish the instruction.

    "skriv om om oss till mer personligt" should NOT set company.story =
    "mer personligt"; with no planner available it is an honest no-op.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    previous = _previous_project_input()
    merged = _merge(
        "skriv om om oss till mer personligt",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] != "mer personligt"
    assert merged["company"]["story"] == previous["company"]["story"]


@pytest.mark.tooling
def test_rewrite_verb_does_not_publish_vibe_as_tagline() -> None:
    """A rewrite-vibe verb on the tagline requires an explicit value; an
    unquoted trailing vibe is a no-op, not literal tagline copy (reviewer P2)."""
    assert (
        _extract_copy_directives("skriv om hero till mer premium", language="sv")
        == []
    )
    assert (
        _extract_copy_directives("rewrite hero to more premium", language="sv") == []
    )


@pytest.mark.tooling
def test_plain_set_verb_keeps_unquoted_tagline_value() -> None:
    """A plain set verb ('byt') still accepts an unquoted trailing tagline value
    that legitimately starts with 'mer'."""
    directives = _extract_copy_directives(
        "byt taglinen till mer än bara kaffe", language="sv"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "mer än bara kaffe",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_about_text_unquoted_trailing_vibe_is_no_op() -> None:
    """about-text requires a quoted/colon value; a bare trailing vibe is no-op."""
    assert (
        _extract_copy_directives(
            "ändra om oss-texten till mer personligt", language="sv"
        )
        == []
    )


@pytest.mark.tooling
def test_planned_about_rewrite_without_valid_plan_is_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planner enabled but returns [] -> honest no-op, not a semantic append."""
    monkeypatch.setattr(_PLANNER_PATH, lambda *a, **k: [])
    previous = _previous_project_input()
    merged = _merge(
        "skriv om om oss så det låter mer personligt",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_planned_story_rewrite_without_valid_plan_does_not_semantic_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 'historia' rewrite request that the planner cannot fulfil must NOT
    fall back to a generic story-emphasize append (the no-op promise)."""
    monkeypatch.setattr(_PLANNER_PATH, lambda *a, **k: [])
    previous = _previous_project_input()
    merged = _merge(
        "skriv om vår historia så den känns mer personlig",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_about_rewrite_drops_planner_service_directive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An about-rewrite must never apply a services directive the model
    returned for the wrong target (scope-leak guard, reviewer P1)."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": "Felaktig serviceändring",
                "targetRef": "Örhängen",
                "source": "llm",
            }
        ],
    )
    previous = _previous_project_input()
    merged = _merge(
        "skriv om om oss så det låter mer personligt",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["services"][0]["summary"] == previous["services"][0]["summary"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_service_rewrite_drops_planner_about_directive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A service rewrite must never apply an about-text directive the model
    returned for the wrong target (scope-leak guard, reviewer P1)."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": "Felaktig om oss-ändring",
                "source": "llm",
            }
        ],
    )
    previous = _previous_project_input()
    merged = _merge(
        "förbättra tjänsten 'Örhängen' så den låter mer säljande",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["services"][0]["summary"] == previous["services"][0]["summary"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_about_copy_directive_refreshes_project_dna_story(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An about-text copyDirective marks story as followup-updated in Project
    DNA even though the intent classifies as no-semantic-change (reviewer P2)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    generate(
        "Skapa en hemsida för Surdegsbagaren i Malmö.",
        output_dir=prompt_inputs_dir,
        site_id="surdegsbagaren-dna",
        project_id="copydir-dna",
    )
    _, meta, _, _ = generate_followup(
        "ändra om oss-texten till 'En personlig berättelse om vårt bageri'",
        output_dir=prompt_inputs_dir,
        site_id="surdegsbagaren-dna",
    )
    story_dna = meta["projectDna"]["story"]
    assert story_dna["source"] == "followup"
    assert story_dna["lastUpdatedVersion"] == 2


def _previous_with_two_services() -> dict[str, object]:
    previous = _previous_project_input()
    previous["services"] = [
        {"id": "orhangen", "label": "Örhängen", "summary": "Fina örhängen."},
        {"id": "ringar", "label": "Ringar", "summary": "Fina ringar."},
    ]
    return previous


@pytest.mark.tooling
def test_service_rewrite_drops_planner_directive_for_wrong_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The planner may only edit the service the operator named; a directive
    pointing at a DIFFERENT existing service is dropped (reviewer P1)."""
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": "Fel tjänst ändrad",
                "targetRef": "Ringar",
                "source": "llm",
            }
        ],
    )
    previous = _previous_with_two_services()
    merged = _merge(
        "förbättra tjänsten 'Örhängen' så den låter mer säljande",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["services"][0]["summary"] == "Fina örhängen."
    assert merged["services"][1]["summary"] == "Fina ringar."
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_service_rewrite_applies_to_named_service_among_many(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The correct named service is still rewritten when several exist."""
    new_summary = "Handgjorda örhängen i återvunnet silver"
    monkeypatch.setattr(
        _PLANNER_PATH,
        lambda *a, **k: [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": new_summary,
                "targetRef": "Örhängen",
                "source": "llm",
            }
        ],
    )
    previous = _previous_with_two_services()
    merged = _merge(
        "förbättra tjänsten 'Örhängen' så den låter mer säljande",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert merged["services"][0]["summary"] == new_summary
    assert merged["services"][1]["summary"] == "Fina ringar."


@pytest.mark.tooling
def test_planned_about_rewrite_no_op_when_site_had_no_story(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the site had no story and the planner fails, the no-op promise still
    holds: a semantic story-emphasize addition is removed, not left behind."""
    monkeypatch.setattr(_PLANNER_PATH, lambda *a, **k: [])
    previous = _previous_project_input()
    previous["company"].pop("story", None)  # site started without a story
    merged = _merge(
        "skriv om vår historia så den känns mer personlig",
        previous=previous,
        enable_llm_fallback=True,
    )
    assert not merged["company"].get("story")
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


def _project_input_with_directive(directive: dict[str, object]) -> dict[str, object]:
    pi = _previous_project_input()
    pi.pop("$schema", None)
    pi["directives"] = {"copyDirectives": [directive]}
    return pi


@pytest.mark.tooling
def test_schema_rejects_services_directive_without_target_ref() -> None:
    pi = _project_input_with_directive(
        {"target": "services", "operation": "replace-text", "payload": "Ny summary"}
    )
    with pytest.raises(SystemExit):
        _validate_against_schema(pi)


@pytest.mark.tooling
def test_schema_accepts_services_directive_with_target_ref() -> None:
    pi = _project_input_with_directive(
        {
            "target": "services",
            "operation": "replace-text",
            "payload": "Ny summary",
            "targetRef": "orhangen",
        }
    )
    _validate_against_schema(pi)  # must not raise


@pytest.mark.tooling
def test_schema_rejects_about_text_include_token() -> None:
    pi = _project_input_with_directive(
        {"target": "about-text", "operation": "include-token", "payload": "X"}
    )
    with pytest.raises(SystemExit):
        _validate_against_schema(pi)


# --- 2026-06-08 (jakob-be): copyDirectiveModel as the PRIMARY copy-edit layer ---
#
# The deterministic _extract_copy_directives is the safety net, not the gate:
# the model is now consulted for free-text copy edits the keyword rules miss
# even when the intent is tagline-update (not only no-semantic-change), while
# tone-shift/story-emphasize/positioning-shift/clarify and additive prompts stay
# deterministic so the model can never fabricate a cross-field copy edit.


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("prompt", "intent", "expected"),
    [
        # no-semantic-change stays eligible (unchanged behaviour)...
        ("kan du kalla firman Nordens Smycken", "no-semantic-change", True),
        # ...and tagline-update is now ALSO eligible so the model can read the
        # free-text hero/tagline edits the deterministic rules miss.
        ("gör herotexten ölälskarna från palma", "tagline-update", True),
        (
            'byt ut sloganen mot något lekfullare: "Surdeg med kärlek"',
            "tagline-update",
            True,
        ),
        # Add-only requests never trigger a copy edit, whatever the intent.
        ("lägg till en kontaktknapp", "no-semantic-change", False),
        # Intents whose semantic-patch field the extraction path cannot emit stay
        # deterministic (no double-apply / no fabricated cross-field copy).
        ("gör tonen varmare", "tone-shift", False),
        ("lyft fram vår historia", "story-emphasize", False),
        ("positionera oss som premium", "positioning-shift", False),
        ("ok", "clarify", False),
    ],
)
def test_copy_directive_llm_eligible_widened_to_tagline_update(
    prompt: str, intent: str, expected: bool
) -> None:
    assert _copy_directive_llm_eligible(prompt, intent=intent) is expected


@pytest.mark.tooling
def test_merge_llm_extracts_hero_tagline_when_intent_is_tagline_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'gör herotexten ölälskarna från palma' classifies as tagline-update and
    the deterministic rules miss it (no replace verb/marker, no till/to value).
    The widened eligibility lets copyDirectiveModel read the literal, which then
    overrides the conservative semantic fallback. Regression for the 2026-06-08
    silent no-op (docs/diagnosis-and-handoff-2026-06-08.md)."""
    prompt = "gör herotexten ölälskarna från palma"
    assert classify_followup_intent(prompt, language="sv") == "tagline-update"
    assert _extract_copy_directives(prompt, language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "tagline",
                "operation": "replace-text",
                "payload": "ölälskarna från palma",
                "source": "llm",
            }
        ],
    )
    merged = _merge(prompt, enable_llm_fallback=True)
    assert merged["company"]["tagline"] == "ölälskarna från palma"
    assert merged["directives"]["copyDirectives"] == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "ölälskarna från palma",
            "source": "llm",
        }
    ]


@pytest.mark.tooling
def test_merge_llm_extracts_slogan_from_mot_phrasing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'byt ut sloganen mot något lekfullare: "X"' is tagline-update, but the
    deterministic value extractor only understands 'till'/'instead of'/quoted-
    before-marker - not 'mot ... :'. With the model consulted the quoted literal
    still lands as the tagline."""
    prompt = 'byt ut sloganen mot något lekfullare: "Surdeg med kärlek"'
    assert classify_followup_intent(prompt, language="sv") == "tagline-update"
    assert _extract_copy_directives(prompt, language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "tagline",
                "operation": "replace-text",
                "payload": "Surdeg med kärlek",
                "source": "llm",
            }
        ],
    )
    merged = _merge(prompt, enable_llm_fallback=True)
    assert merged["company"]["tagline"] == "Surdeg med kärlek"
    assert merged["directives"]["copyDirectives"][0]["source"] == "llm"


@pytest.mark.tooling
def test_merge_llm_extracts_company_name_from_kalla_firman(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'kan du kalla firman Nordens Smycken' is no-semantic-change and the
    deterministic rules miss it ('kalla'/'firman' are not name keywords); the
    model reads the rename. Locks the operator's exact free-text phrasing."""
    prompt = "kan du kalla firman Nordens Smycken"
    assert classify_followup_intent(prompt, language="sv") == "no-semantic-change"
    assert _extract_copy_directives(prompt, language="sv") == []
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
    merged = _merge(prompt, enable_llm_fallback=True)
    assert merged["company"]["name"] == "Nordens Smycken"
    assert merged["directives"]["copyDirectives"][0]["source"] == "llm"


@pytest.mark.tooling
def test_tone_shift_never_fabricates_tagline_via_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: 'gör tonen varmare' is tone-shift, so the extraction path is
    NOT consulted - even a misbehaving model proposing a literal tagline can
    never be reached/applied. The semantic tone patch leaves company.tagline
    byte-stable and no copyDirective is recorded."""
    previous = _previous_project_input()
    prompt = "gör tonen varmare"
    assert classify_followup_intent(prompt, language="sv") == "tone-shift"
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "tagline",
                "operation": "replace-text",
                "payload": "Värme i varje möte",
                "source": "llm",
            }
        ],
    )
    merged = _merge(prompt, previous=previous, enable_llm_fallback=True)
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_additive_request_never_triggers_llm_copy_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: 'lägg till en kontaktknapp' must never become a copy edit
    (add-only guard), even with the model enabled and (wrongly) proposing a
    rename. Name + tagline stay byte-stable; no copyDirective is recorded."""
    previous = _previous_project_input()
    prompt = "lägg till en kontaktknapp"
    assert _extract_copy_directives(prompt, language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "company-name",
                "operation": "replace-text",
                "payload": "Knappbolaget",
                "source": "llm",
            }
        ],
    )
    merged = _merge(prompt, previous=previous, enable_llm_fallback=True)
    assert merged["company"]["name"] == previous["company"]["name"]
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


@pytest.mark.tooling
def test_tagline_update_llm_no_op_does_not_fabricate_copy_directive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Honesty: when the model returns nothing valid for a tagline-update with
    no literal copy ('gör herotexten mer slagkraftig'), the LLM no-op stays an
    honest no-op - no copyDirective is fabricated."""
    prompt = "gör herotexten mer slagkraftig"
    assert classify_followup_intent(prompt, language="sv") == "tagline-update"
    assert _extract_copy_directives(prompt, language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [],
    )
    merged = _merge(prompt, enable_llm_fallback=True)
    assert "directives" not in merged or "copyDirectives" not in merged.get(
        "directives", {}
    )


# --- 2026-06-08 (jakob-be): hero-copy decoupling fix (company.heroHeadline) ---
#
# Root cause from the kaka-ab live demo: the follow-up DID work at the data
# layer (copyDirectiveModel set company.tagline = "jakobs kakor"), but the big
# hero H1 renders from the planning blueprint (contentBlocks.home.hero.headline,
# regenerated from briefModel positioning every build), NOT from company.tagline
# (which only feeds the meta description, footer and a subheadline fallback the
# blueprint overrides). So the edit was invisible. The fix mirrors an explicit
# tagline edit into company.heroHeadline, an operator override the renderer
# prefers over the regenerated blueprint headline.

THE_KAKA_DEMO_PROMPT = (
    'Ändra denna text: "En svensk webbshop för kakor med tydlig väg från '
    'produkt till köp." til att säga "jakobs kakor".'
)


@pytest.mark.tooling
def test_tagline_replace_mirrors_into_hero_headline_override() -> None:
    """A deterministic tagline edit (rubrik -> tagline) also writes the operator
    hero-headline override so the big hero H1 reflects the edit, not just the
    invisible tagline/meta field."""
    merged = _merge("byt rubriken till 'Jakobs kakor'")
    assert merged["company"]["tagline"] == "Jakobs kakor"
    assert merged["company"]["heroHeadline"] == "Jakobs kakor"


@pytest.mark.tooling
def test_include_token_tagline_reflects_in_hero_headline() -> None:
    """An include-token tagline edit also surfaces in the hero-headline override
    (the resulting tagline value), so the token is visible in the H1 too."""
    merged = _merge(INCLUDE_TOKEN_PROMPT)
    assert "TEST-JAKOB" in merged["company"]["heroHeadline"]
    assert merged["company"]["heroHeadline"] == merged["company"]["tagline"]


@pytest.mark.tooling
def test_company_rename_does_not_set_hero_headline_override() -> None:
    """A company rename keeps the nav/footer brand and must NOT hijack the hero
    H1 - so it never writes company.heroHeadline."""
    merged = _merge(OPERATOR_RENAME_PROMPT)
    assert merged["company"]["name"] == "Jakobs Örhängen"
    assert "heroHeadline" not in merged["company"]


@pytest.mark.tooling
def test_about_text_edit_does_not_set_hero_headline_override() -> None:
    """An about-text (story) edit must not touch the hero-headline override."""
    merged = _merge(ABOUT_REPLACE_PROMPT)
    assert merged["company"]["story"] == "Vi är ett familjeföretag sedan 1982"
    assert "heroHeadline" not in merged["company"]


@pytest.mark.tooling
def test_kaka_demo_prompt_sets_hero_headline_via_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The operator's exact live-demo prompt: "Ändra denna text: '<old>' til att
    säga 'jakobs kakor'." The deterministic rules miss it ("denna text" has no
    stable target keyword), the intent is no-semantic-change (LLM-eligible), and
    copyDirectiveModel returns a tagline directive. The fix then mirrors it into
    company.heroHeadline so the big hero H1 becomes "jakobs kakor" - the change
    that was silently swallowed in the live demo."""
    assert classify_followup_intent(THE_KAKA_DEMO_PROMPT, language="sv") == (
        "no-semantic-change"
    )
    assert _extract_copy_directives(THE_KAKA_DEMO_PROMPT, language="sv") == []
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_copy_directives_llm",
        lambda *a, **k: [
            {
                "target": "tagline",
                "operation": "replace-text",
                "payload": "jakobs kakor",
                "source": "llm",
            }
        ],
    )
    merged = _merge(THE_KAKA_DEMO_PROMPT, enable_llm_fallback=True)
    assert merged["company"]["tagline"] == "jakobs kakor"
    assert merged["company"]["heroHeadline"] == "jakobs kakor"
    assert merged["directives"]["copyDirectives"][0]["target"] == "tagline"


@pytest.mark.tooling
def test_merged_hero_headline_override_passes_schema() -> None:
    merged = _merge("byt rubriken till 'Jakobs kakor'")
    assert merged["company"]["heroHeadline"] == "Jakobs kakor"
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_schema_accepts_company_hero_headline() -> None:
    pi = _previous_project_input()
    pi.pop("$schema", None)
    pi["company"]["heroHeadline"] = "Jakobs kakor"
    _validate_against_schema(pi)  # must not raise


@pytest.mark.tooling
def test_end_to_end_hero_headline_override_visible_as_h1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Acceptance: a hero/tagline follow-up reaches the rendered hero H1, not
    just the invisible tagline/meta field. This is the end-to-end proof for the
    kaka-ab live-demo fix - "byt rubriken till X" now changes the big hero
    headline in the generated page."""
    import re

    new_headline = "Smaskiga kakor varje dag"
    page, build_result = _build_two_versions(
        monkeypatch,
        tmp_path,
        init_prompt="Skapa en hemsida för Surdegsbagaren i Malmö.",
        followup_prompt=f"byt rubriken till '{new_headline}'",
        site_id="surdegsbagaren-hero",
        project_id="copydir-hero",
    )
    text = page.read_text(encoding="utf-8")
    assert new_headline in text
    h1_blocks = re.findall(r"<h1[^>]*>(.*?)</h1>", text, flags=re.DOTALL)
    assert any(new_headline in block for block in h1_blocks), (
        "the hero override must render inside the hero H1, not only meta/footer"
    )
    assert build_result["engineMode"] == "followup"
    assert build_result["appliedVisibleEffect"] is True


# --- 2026-06-09 (copy-passthrough fix): rows 1-4 ----------------------------
#
# The lask-ab regression: "Ändra denna text '<hero>' till Jakobs tjänsteföretag
# i Småland" became a silent paraphrase. Root causes: (4) tone words inside the
# quoted OLD text drove a tone-shift misclassification, (1) "tjänst" matched as
# a substring of "tjänsteföretag" and forced a services no-op, (2) no literal
# find-and-replace path existed, and (3) the file-diff signal reported the
# regenerated paraphrase as a successful edit.

LASK_LITERAL_PROMPT = (
    'Ändra denna text "Ett svenskt tjänsteföretag med en exklusiv och modern '
    'känsla." till "Jakobs tjänsteföretag i Småland"'
)


@pytest.mark.tooling
def test_quoted_old_copy_does_not_trigger_tone_shift() -> None:
    """ROW 4: tone scope/descriptor words INSIDE the quoted OLD text being
    replaced ("exklusiv och modern känsla") must not drive intent. The literal
    hero edit must classify as no-semantic-change, not tone-shift."""
    assert classify_followup_intent(LASK_LITERAL_PROMPT, language="sv") == (
        "no-semantic-change"
    )


@pytest.mark.tooling
def test_tone_shift_still_fires_when_scope_outside_quotes() -> None:
    """ROW 4 guard: a genuine tone request with the scope word OUTSIDE quotes
    still classifies as tone-shift."""
    assert classify_followup_intent("gör tonen mer modern", language="sv") == (
        "tone-shift"
    )


@pytest.mark.tooling
def test_services_substring_does_not_misroute_to_services() -> None:
    """ROW 1: 'tjänsteföretag' must NOT match the services keyword 'tjänst' as
    a substring (which forced a services no-op). Word-boundary matching keeps
    the compound noun out of the services branch."""
    from packages.generation.followup.copy_directives import _classify_copy_target
    from packages.generation.followup.text import _normalise_followup_text

    text = _normalise_followup_text(
        "ändra texten om vårt tjänsteföretag till något helt nytt"
    )
    assert _classify_copy_target(text) != "services"


@pytest.mark.tooling
def test_service_word_still_routes_to_services() -> None:
    """ROW 1 guard: a real whole-word 'tjänsten' still routes to services."""
    from packages.generation.followup.copy_directives import _classify_copy_target
    from packages.generation.followup.text import _normalise_followup_text

    text = _normalise_followup_text("ändra tjänsten till något nytt")
    assert _classify_copy_target(text) == "services"


@pytest.mark.tooling
def test_literal_replace_on_tagline_field_sets_hero_headline() -> None:
    """ROW 2: 'ändra denna text "X" till "Y"' where X is the current tagline
    replaces it verbatim and mirrors into the hero-headline override."""
    merged = _merge(
        'ändra denna text "Handgjorda örhängen i Malmö" till '
        '"Jakobs örhängen i Småland"'
    )
    assert merged["company"]["tagline"] == "Jakobs örhängen i Småland"
    assert merged["company"]["heroHeadline"] == "Jakobs örhängen i Småland"
    directives = merged["directives"]["copyDirectives"]
    assert directives[0]["source"] == "prompt-rule"
    assert directives[0]["target"] == "tagline"


@pytest.mark.tooling
def test_literal_replace_on_story_field() -> None:
    """ROW 2: matching the current story replaces company.story (about-text)."""
    merged = _merge(
        'ändra denna text "En liten butik med stor passion." till '
        '"Vi brinner för kvalitet och hantverk."'
    )
    # _safe_copy_payload strips a single trailing period (shared copy guard).
    assert merged["company"]["story"] == "Vi brinner för kvalitet och hantverk"
    assert "heroHeadline" not in merged["company"]


@pytest.mark.tooling
def test_literal_replace_on_service_summary() -> None:
    """ROW 2: matching a service summary replaces that service's summary via
    the resolved targetRef."""
    merged = _merge(
        'ändra denna text "Fina örhängen." till "Handgjorda smycken i silver."'
    )
    # _safe_copy_payload strips a single trailing period (shared copy guard).
    assert merged["services"][0]["summary"] == "Handgjorda smycken i silver"
    directive = merged["directives"]["copyDirectives"][0]
    assert directive["target"] == "services"
    assert directive["targetRef"] == "orhangen"


@pytest.mark.tooling
def test_additive_two_quote_prompt_never_mutates_copy() -> None:
    """#318 review fix: an ADDITIVE follow-up that quotes two values - even when
    the FIRST quote matches the current tagline verbatim - is NOT a copy-replace.
    Before the additive guard the bare quoted pair (has_quoted_pair, kept for
    B204-mangled verbs) passed the literal-replace gate and silently mutated the
    tagline to the SECOND quote; now it is an honest no-op."""
    merged = _merge(
        'lägg till en knapp som säger "Handgjorda örhängen i Malmö" och en '
        'som säger "Boka tid"'
    )
    # The tagline (matched verbatim by the first quote) is untouched...
    assert merged["company"]["tagline"] == "Handgjorda örhängen i Malmö"
    # ...and no copyDirective was fabricated from the additive prompt.
    assert "copyDirectives" not in merged.get("directives", {})


@pytest.mark.tooling
def test_literal_replace_honest_no_op_when_old_not_found() -> None:
    """ROW 2: when the quoted OLD text matches NO current field (e.g. the
    operator quoted the regenerated hero line), it is an HONEST no-op - no
    fabricated copy, no copyDirective, fields untouched."""
    merged = _merge(LASK_LITERAL_PROMPT)
    assert merged["company"]["tagline"] == "Handgjorda örhängen i Malmö"
    assert merged["company"]["story"] == "En liten butik med stor passion."
    assert "copyDirectives" not in merged.get("directives", {})


@pytest.mark.tooling
def test_followup_requested_copy_replace_detection() -> None:
    """ROW 3 helper: detect an explicit quoted copy-replace request (used by the
    build's honest-effect signal) without firing on tone/section follow-ups."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
    )

    assert _followup_requested_copy_replace(LASK_LITERAL_PROMPT) is True
    assert _followup_requested_copy_replace('byt "gammalt" till "nytt"') is True
    assert _followup_requested_copy_replace("gör tonen mörkare") is False
    assert _followup_requested_copy_replace("lägg till en faq-sektion") is False


# --- 2026-06-09 (#224 P2): additive section_add that quotes its new copy is NOT
#     a copy-REPLACE. Before the fix, the "texten" anchor + a quoted span made
#     _followup_requested_copy_replace return True, so a visible section_add was
#     mis-reported as a failed copy no-op (copy_directive_not_applied).


@pytest.mark.tooling
def test_additive_section_add_with_quoted_text_is_not_copy_replace() -> None:
    """An additive 'lägg till en FAQ-sektion med texten "..."' quotes the NEW
    section copy, not an OLD string to swap, so it must NOT be detected as a
    copy-replace request (#224 P2)."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
    )

    # The exact #224 symptom: additive add + a quoted span, no replace verb.
    assert (
        _followup_requested_copy_replace(
            'lägg till en FAQ-sektion med texten "Vanliga frågor"'
        )
        is False
    )
    # 'inkludera' + a quoted token is additive (include keyword), not a replace.
    assert (
        _followup_requested_copy_replace('inkludera "TEST-JAKOB" i en ny sektion')
        is False
    )
    # A 'ny ... sektion' add intent + quoted new copy is additive, not a replace.
    assert (
        _followup_requested_copy_replace('skapa en ny sektion med rubriken "Om oss"')
        is False
    )
    # A compound that ALSO adds a section is additive -> the visible add wins,
    # so the copy-replace honesty signal must not fire even with a replace verb.
    assert (
        _followup_requested_copy_replace(
            'lägg till en FAQ-sektion och byt rubriken till "Ny rubrik"'
        )
        is False
    )


@pytest.mark.tooling
def test_genuine_copy_replace_still_detected_after_additive_tightening() -> None:
    """Guard for the #224 tightening: a genuine quoted copy-replace still fires,
    and a quoted value that merely MENTIONS 'ny sektion' is still a replace
    (the additive check runs on the instruction skeleton, not the quoted copy)."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
    )

    # A quoted NEW value that happens to read 'Ny sektion om oss' is still a
    # replace - the add intent must come from the instruction, not the payload.
    assert (
        _followup_requested_copy_replace('ändra rubriken till "Ny sektion om oss"')
        is True
    )
    # The 'instead of'/'istället för' replace marker still counts as a replace.
    assert (
        _followup_requested_copy_replace('gör herotexten "X" istället för "Y"') is True
    )


# --- 2026-06-10 (B155): UNQUOTED literal replace -----------------------------
#
# "ändra <OLD> till <NEW>" WITHOUT quotes used to paraphrase (semantic patch) or
# silently no-op, because the literal find-and-replace path only extracted OLD
# from quoted spans. The unquoted path matches OLD as an exact (normalised,
# case-insensitive) SUBSTRING of a known stored copy field
# (company.tagline / company.story / services[].summary), applies a literal
# substitution on a single match, stays an honest no-op on a miss, and is an
# honest AMBIGUOUS no-op (with a surfaced reason) when OLD hits >= 2 fields. It
# never guesses a target or paraphrases.


@pytest.mark.tooling
def test_unquoted_replace_on_tagline_substring() -> None:
    """A word inside the stored tagline is swapped verbatim; heroHeadline mirrors."""
    merged = _merge("ändra Handgjorda till Maskingjorda")
    assert merged["company"]["tagline"] == "Maskingjorda örhängen i Malmö"
    assert merged["company"]["heroHeadline"] == "Maskingjorda örhängen i Malmö"
    directive = merged["directives"]["copyDirectives"][0]
    assert directive["target"] == "tagline"
    assert directive["operation"] == "replace-text"
    assert directive["source"] == "prompt-rule"


@pytest.mark.tooling
def test_unquoted_replace_whole_tagline_value() -> None:
    """OLD equal to the entire tagline replaces the whole field."""
    merged = _merge("ändra Handgjorda örhängen i Malmö till Smycken i Lund")
    assert merged["company"]["tagline"] == "Smycken i Lund"


@pytest.mark.tooling
def test_unquoted_replace_on_story_substring() -> None:
    """A substring of company.story is replaced; no heroHeadline is written."""
    merged = _merge("ändra liten butik till stor verkstad")
    assert merged["company"]["story"] == "En stor verkstad med stor passion."
    assert "heroHeadline" not in merged["company"]
    assert merged["directives"]["copyDirectives"][0]["target"] == "about-text"


@pytest.mark.tooling
def test_unquoted_replace_on_service_summary() -> None:
    """A substring of a service summary replaces that summary, with targetRef."""
    merged = _merge("ändra Fina örhängen till Vackra smycken")
    assert merged["services"][0]["summary"] == "Vackra smycken."
    directive = merged["directives"]["copyDirectives"][0]
    assert directive["target"] == "services"
    assert directive["targetRef"] == "orhangen"


@pytest.mark.tooling
def test_unquoted_replace_case_insensitive_lowercase_old() -> None:
    """OLD typed all-lowercase still matches a capitalised stored value."""
    merged = _merge("ändra handgjorda till Maskingjorda")
    assert merged["company"]["tagline"] == "Maskingjorda örhängen i Malmö"


@pytest.mark.tooling
def test_unquoted_replace_uppercase_old_matches_lowercase_field() -> None:
    """OLD typed uppercase matches a lower/mixed-case stored value (versaler)."""
    merged = _merge("ändra HANDGJORDA till Maskingjorda")
    assert merged["company"]["tagline"] == "Maskingjorda örhängen i Malmö"


@pytest.mark.tooling
def test_unquoted_replace_no_match_is_honest_no_op() -> None:
    """OLD that matches no stored field leaves every copy field untouched."""
    previous = _previous_project_input()
    merged = _merge("ändra Helikopterplattan till Något annat", previous)
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "copyDirectives" not in merged.get("directives", {})


@pytest.mark.tooling
def test_unquoted_replace_ambiguous_two_fields_is_no_op() -> None:
    """OLD present in BOTH tagline and story is an honest no-op (no guess)."""
    previous = _previous_project_input()
    previous["company"]["tagline"] = "Vi älskar kvalitet"
    previous["company"]["story"] = "Vår story handlar om kvalitet och passion."
    merged = _merge("ändra kvalitet till klass", previous)
    assert merged["company"]["tagline"] == "Vi älskar kvalitet"
    assert merged["company"]["story"] == "Vår story handlar om kvalitet och passion."
    assert "copyDirectives" not in merged.get("directives", {})


@pytest.mark.tooling
def test_unquoted_ambiguous_records_unapplied_reason() -> None:
    """The ambiguous no-op surfaces a honest reason via the observer; a single
    clean match (and a plain miss) records nothing."""
    from scripts.prompt_to_project_input import compute_unapplied_followup_intents

    previous = _previous_project_input()
    previous["company"]["tagline"] = "Vi älskar kvalitet"
    previous["company"]["story"] = "Vår story handlar om kvalitet och passion."
    ambiguous_prompt = "ändra kvalitet till klass"
    merged = _merge(ambiguous_prompt, previous)
    posts = compute_unapplied_followup_intents(
        previous, merged, follow_up_prompt=ambiguous_prompt
    )
    assert any(post["target"] == "copy-replace" for post in posts)
    reason = next(post["reason"] for post in posts if post["target"] == "copy-replace")
    assert "flera fält" in reason

    # A single clean match must NOT produce an ambiguous post.
    clean_previous = _previous_project_input()
    clean_prompt = "ändra Handgjorda till Maskingjorda"
    clean_merged = _merge(clean_prompt, clean_previous)
    clean_posts = compute_unapplied_followup_intents(
        clean_previous, clean_merged, follow_up_prompt=clean_prompt
    )
    assert all(post["target"] != "copy-replace" for post in clean_posts)


@pytest.mark.tooling
def test_unquoted_replace_does_not_hijack_target_keyword_prompt() -> None:
    """'ändra taglinen till X' is still owned by the target-keyword path, not the
    substring matcher (the word 'taglinen' is not stored copy)."""
    from packages.generation.followup.copy_directives import (
        unquoted_literal_replace_status,
    )

    previous = _previous_project_input()
    assert (
        unquoted_literal_replace_status("ändra taglinen till Helt ny text", previous)[
            "status"
        ]
        == "none"
    )
    merged = _merge("ändra taglinen till Helt ny text", previous)
    assert merged["company"]["tagline"] == "Helt ny text"


@pytest.mark.tooling
def test_unquoted_replace_additive_request_is_not_literal_replace() -> None:
    """An additive 'lägg till ...' ask is never treated as a copy replace, even
    when a replace verb co-occurs and a 'till' marker is present."""
    from packages.generation.followup.copy_directives import (
        unquoted_literal_replace_status,
    )

    previous = _previous_project_input()
    result = unquoted_literal_replace_status(
        "ändra startsidan och lägg till Fina örhängen i menyn", previous
    )
    assert result["status"] == "none"
    assert result["directives"] == []


@pytest.mark.tooling
def test_unquoted_resolver_bails_on_quoted_prompt() -> None:
    """A quoted prompt is owned by the quoted whole-field path; the unquoted
    resolver must not engage (returns status 'none')."""
    from packages.generation.followup.copy_directives import (
        unquoted_literal_replace_status,
    )

    previous = _previous_project_input()
    assert (
        unquoted_literal_replace_status(
            'ändra "Handgjorda örhängen i Malmö" till "Nytt"', previous
        )["status"]
        == "none"
    )
    # And the quoted whole-field path still applies the rename.
    merged = _merge('ändra "Handgjorda örhängen i Malmö" till "Nytt värde"')
    assert merged["company"]["tagline"] == "Nytt värde"


@pytest.mark.tooling
def test_unquoted_replace_rejects_instruction_shaped_new_value() -> None:
    """OLD matches, but a NEW value that reads as an instruction (carries a
    change-verb) is rejected by the leak guard -> honest no-op."""
    previous = _previous_project_input()
    merged = _merge("ändra Handgjorda till byt knappen", previous)
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert "copyDirectives" not in merged.get("directives", {})


@pytest.mark.tooling
def test_unquoted_replace_partial_substring_preserves_surrounding_copy() -> None:
    """Only the matched span changes; the rest of the field is preserved."""
    merged = _merge("ändra Malmö till Lund")
    assert merged["company"]["tagline"] == "Handgjorda örhängen i Lund"


@pytest.mark.tooling
def test_end_to_end_unquoted_replace_visible_and_applied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Acceptance: an unquoted replace of the stored tagline reaches the rendered
    page and reports an honest appliedVisibleEffect=True."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"
    site_id = "surdeg-b155-unq"

    _, _, init_path, _ = generate(
        "Skapa en hemsida för Surdegsbagaren i Malmö.",
        output_dir=prompt_inputs_dir,
        site_id=site_id,
        project_id="b155-unq-applied",
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)
    v1 = json.loads(Path(init_path).read_text(encoding="utf-8"))
    tagline = v1["company"]["tagline"]
    token = "JAKOBTOKEN"

    _, _, followup_path, _ = generate_followup(
        f"ändra {tagline} till {token}",
        output_dir=prompt_inputs_dir,
        site_id=site_id,
    )
    _, run_dir = build(
        followup_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )
    page = (run_dir / "generated-files" / "app" / "page.tsx").read_text(
        encoding="utf-8"
    )
    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    assert token in page
    assert build_result["appliedVisibleEffect"] is True


@pytest.mark.tooling
def test_end_to_end_unquoted_replace_miss_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A miss (OLD in no stored field) never fabricates copy and reports an
    honest appliedVisibleEffect=False."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"
    site_id = "surdeg-b155-miss"

    _, _, init_path, _ = generate(
        "Skapa en hemsida för Surdegsbagaren i Malmö.",
        output_dir=prompt_inputs_dir,
        site_id=site_id,
        project_id="b155-unq-miss",
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)
    token = "JAKOBTOKEN"

    _, _, followup_path, _ = generate_followup(
        f"ändra Helikopterlandningsplattan till {token}",
        output_dir=prompt_inputs_dir,
        site_id=site_id,
    )
    _, run_dir = build(
        followup_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )
    page = (run_dir / "generated-files" / "app" / "page.tsx").read_text(
        encoding="utf-8"
    )
    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    assert token not in page
    assert build_result["appliedVisibleEffect"] is False


# --- 2026-06-10 (B178): UNQUOTED demonstrative free-text replace --------------
#
# "Denna text: <OLD> ska bli <NEW>" is how an operator naturally points at a
# specific visible string without quoting it. Before this slice the anchor-led
# form (no leading replace verb, a "become" separator) was invisible to BOTH the
# capability path (it only knew the verb-led "<verb> <OLD> till <NEW>") and the
# honest-effect signal (it required a quoted span), so a free-text ask that did
# not land was reported as a false "Klart! v1 -> v2". The fix is gated on an
# explicit demonstrative text anchor so a style ("sajten ska bli mörkblå") or
# section ("lägg till en sektion") follow-up never trips the copy-replace path.


@pytest.mark.tooling
def test_b178_demonstrative_anchor_replace_request_detected() -> None:
    """The honest-effect signal fires for an UNQUOTED demonstrative replace
    ("denna text: X ska bli Y") so a regenerated paraphrase can never pose as a
    successful edit - regardless of whether OLD matches a stored field."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
    )

    assert (
        _followup_requested_copy_replace(
            "Denna text: En lugn och tydlig servicesajt ska bli JAKOB"
        )
        is True
    )
    # "blir" / "så den blir" separators count too (neutral OLD/NEW so no target
    # keyword like "rubrik" hijacks the classification).
    assert (
        _followup_requested_copy_replace("denna text: Gammalt värde blir Nytt värde")
        is True
    )
    assert (
        _followup_requested_copy_replace(
            "den här texten: Gammalt värde så den blir Nytt"
        )
        is True
    )


@pytest.mark.tooling
def test_b178_style_and_section_are_not_demonstrative_replace() -> None:
    """A style or section follow-up carries no demonstrative text anchor, so the
    copy-replace honesty signal stays silent (no false no-op on a real change)."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
        unquoted_literal_replace_status,
    )

    previous = _previous_project_input()
    for prompt in (
        "sajten ska bli mörkblå",
        "gör hela sajten ljusare",
        "lägg till en ny sektion längst ner",
    ):
        assert _followup_requested_copy_replace(prompt) is False, prompt
        assert unquoted_literal_replace_status(prompt, previous)["status"] == "none"


@pytest.mark.tooling
def test_b178_anchor_led_replace_applies_on_stored_field() -> None:
    """An anchor-led demonstrative replace whose OLD matches a stored field is
    applied verbatim (the B155 capability half), across become separators."""
    for prompt in (
        "denna text: Handgjorda örhängen i Malmö ska bli Smycken i Lund",
        "denna text: Handgjorda örhängen i Malmö blir Smycken i Lund",
        "den här texten: Handgjorda örhängen i Malmö så den blir Smycken i Lund",
    ):
        merged = _merge(prompt)
        assert merged["company"]["tagline"] == "Smycken i Lund", prompt
        assert merged["company"]["heroHeadline"] == "Smycken i Lund", prompt
        directive = merged["directives"]["copyDirectives"][0]
        assert directive["operation"] == "replace-text"
        assert directive["source"] == "prompt-rule"


@pytest.mark.tooling
def test_b178_anchor_led_replace_miss_is_honest_no_op() -> None:
    """The operator's exact repro shape: the quoted-but-unquoted hero line is not
    a stored field, so the change is an honest no-op (fields untouched, no
    directive) WHILE the honest-effect signal still reports a replace request."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
        unquoted_literal_replace_status,
    )

    previous = _previous_project_input()
    prompt = "Denna text: En lugn och tydlig servicesajt ska bli JAKOB"
    status = unquoted_literal_replace_status(prompt, previous)
    assert status["status"] == "no_match"
    assert status["directives"] == []
    merged = _merge(prompt, previous)
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "copyDirectives" not in merged.get("directives", {})
    # Honest-effect signal must still flag this as a replace REQUEST.
    assert _followup_requested_copy_replace(prompt) is True


@pytest.mark.tooling
def test_b178_anchor_led_does_not_hijack_additive_or_target_prompt() -> None:
    """A demonstrative anchor inside an additive ask, or a target-keyword prompt,
    stays out of the anchor-led replace path."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
        unquoted_literal_replace_status,
    )

    previous = _previous_project_input()
    # Additive wins even with a demonstrative anchor present.
    additive = "lägg till en sektion med denna text: Hej ska bli Hå"
    assert _followup_requested_copy_replace(additive) is False
    assert unquoted_literal_replace_status(additive, previous)["status"] == "none"


# --- Track B (#318): quoting the RENDERED/derived om-oss text lands -----------
#
# The operator quotes the about/story text they SEE in the preview. That text is
# derive_story(brief) (planning blueprint), regenerated every build and shadowing
# the stored company.story at render - so it is NOT the stored field. The merge
# now matches the previously rendered story too (previous_rendered_story) and
# pins the edit to directives.sectionContentOverrides for BOTH story surfaces so
# it survives the next build's derive_story regeneration (ADR 0043 + 0034).

# A derived om-oss story distinct from the stored company.story so the match can
# only succeed via the rendered-story candidate, not the stored field.
_RENDERED_ABOUT_STORY = (
    "Vi har bakat surdegsbröd i Malmö sedan 1998, för hand varje morgon."
)
_RENDERED_ABOUT_PROMPT = (
    f'ändra "{_RENDERED_ABOUT_STORY}" till "Jakobs ölbryggeri är 20 år gammalt"'
)


def _merge_rendered(prompt: str, *, previous: dict[str, object] | None = None) -> dict:
    previous = previous or _previous_project_input()
    return merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt=prompt,
        previous_rendered_story=_RENDERED_ABOUT_STORY,
    )


@pytest.mark.tooling
def test_quoted_rendered_story_lands_as_section_overrides() -> None:
    """Quoting the RENDERED om-oss text (≠ stored company.story) matches via the
    rendered-story candidate and pins both story surfaces as section-content
    overrides - the renderer prefers them over the regenerated blueprint copy."""
    from packages.generation.build.blueprint_render import (
        resolve_section_content_override,
    )
    from scripts.prompt_to_project_input import (
        compute_applied_followup_directive_kinds,
    )

    previous = _previous_project_input()
    # Precondition: the quoted OLD is NOT the stored story (so only the rendered
    # candidate can match it).
    assert previous["company"]["story"] != _RENDERED_ABOUT_STORY

    merged = _merge_rendered(_RENDERED_ABOUT_PROMPT, previous=previous)
    overrides = merged["directives"]["sectionContentOverrides"]
    assert overrides["home.story.body"] == "Jakobs ölbryggeri är 20 år gammalt"
    assert overrides["about.about-story.body"] == "Jakobs ölbryggeri är 20 år gammalt"
    # company.story carries the edit too (the structured field the apply writes).
    assert merged["company"]["story"] == "Jakobs ölbryggeri är 20 år gammalt"
    # Honesty signal: the applied-kinds include "section-content".
    kinds = compute_applied_followup_directive_kinds(previous, merged)
    assert "section-content" in kinds
    # The renderer resolves the override for BOTH story sections (it wins over
    # the company.story / regenerated derive_story copy).
    assert (
        resolve_section_content_override(merged, "story", "body")
        == "Jakobs ölbryggeri är 20 år gammalt"
    )
    assert (
        resolve_section_content_override(merged, "about-story", "body")
        == "Jakobs ölbryggeri är 20 år gammalt"
    )


@pytest.mark.tooling
def test_quoted_rendered_story_override_wins_in_rendered_about_page() -> None:
    """The pinned section-content override wins over a shadowing company.story at
    render time (derive_story regenerates company.story every build, so the pin
    is what makes the edit visible)."""
    from packages.generation.build.renderers import render_section_about_story

    merged = _merge_rendered(_RENDERED_ABOUT_PROMPT)
    # Simulate the next build: derive_story has shadowed company.story with a
    # freshly regenerated value. The override must still win.
    dossier = {
        "company": {
            "name": "Surdegsbageriet",
            "story": "EN HELT REGENERERAD BLUEPRINT-BERÄTTELSE SOM SKUGGAR.",
        },
        "directives": merged["directives"],
    }
    tsx = render_section_about_story(dossier)
    assert "Jakobs ölbryggeri är 20 år gammalt" in tsx
    assert "REGENERERAD BLUEPRINT-BERÄTTELSE" not in tsx


@pytest.mark.tooling
def test_quoted_rendered_story_lands_even_with_mangled_verb() -> None:
    """Encoding-robustness (B204): the edit still lands when the leading "Ä" was
    mangled to "*" at the chat -> CLI boundary ("Ändra" -> "*ndra"). The gate
    keys on the quoted OLD/NEW pair, not the verb keyword."""
    mangled = (
        f'*ndra "{_RENDERED_ABOUT_STORY}" till "Jakobs ölbryggeri är 20 år gammalt"'
    )
    merged = _merge_rendered(mangled)
    overrides = merged.get("directives", {}).get("sectionContentOverrides", {})
    assert overrides.get("home.story.body") == "Jakobs ölbryggeri är 20 år gammalt"
    assert (
        overrides.get("about.about-story.body") == "Jakobs ölbryggeri är 20 år gammalt"
    )


@pytest.mark.tooling
def test_story_pin_carries_forward_and_does_not_clobber_siblings() -> None:
    """The story pin only updates its own two canonical keys and drops a sibling
    sharing the same suffix (so the renderer's single-match rule is satisfied);
    an unrelated override (a hero headline) carries through untouched."""
    previous = _previous_project_input()
    previous["directives"] = {
        "sectionContentOverrides": {
            "home.hero.headline": "Pinnad rubrik",
            # A sibling about-story override from another route/path.
            "om-oss.about-story.body": "Tidigare om-oss-override",
        }
    }
    merged = _merge_rendered(_RENDERED_ABOUT_PROMPT, previous=previous)
    overrides = merged["directives"]["sectionContentOverrides"]
    # Unrelated hero override survives.
    assert overrides["home.hero.headline"] == "Pinnad rubrik"
    # The sibling about-story key is dropped (single-match), canonical key set.
    assert "om-oss.about-story.body" not in overrides
    assert overrides["about.about-story.body"] == "Jakobs ölbryggeri är 20 år gammalt"


# --- Track A (#318): encoding-robust honest no-op for an unmatched replace ----
#
# A QUOTED copy-replace whose OLD matches nothing editable must ALWAYS surface an
# honest unapplied post and never an implied success - keyed on the OLD/NEW pair
# present + a genuine miss, NEVER on the (possibly mangled) leading verb (#313).

_GENUINE_MISS_PROMPT = 'ändra "den här texten finns inte i någon copy alls" till "Ny text"'


@pytest.mark.tooling
def test_quoted_copy_replace_genuine_miss_is_honest_unapplied() -> None:
    """A quoted replace whose OLD matches no editable copy (stored OR rendered)
    is an honest no-op: a non-empty copy-replace unapplied post, no override, and
    the honest-effect helper still flags it as a replace REQUEST."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
    )
    from scripts.prompt_to_project_input import compute_unapplied_followup_intents

    previous = _previous_project_input()
    merged = _merge_rendered(_GENUINE_MISS_PROMPT, previous=previous)
    # Nothing landed: no copyDirectives, no section overrides, story untouched.
    assert "copyDirectives" not in merged.get("directives", {})
    assert "sectionContentOverrides" not in merged.get("directives", {})
    assert merged["company"]["story"] == previous["company"]["story"]
    # Honest unapplied post.
    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt=_GENUINE_MISS_PROMPT,
        previous_rendered_story=_RENDERED_ABOUT_STORY,
    )
    assert {"target": "copy-replace"}.items() <= posts[0].items()
    assert any(post["target"] == "copy-replace" for post in posts)
    # The honest-effect signal still recognises the replace REQUEST.
    assert _followup_requested_copy_replace(_GENUINE_MISS_PROMPT) is True


@pytest.mark.tooling
def test_quoted_copy_replace_miss_is_honest_even_with_mangled_verb() -> None:
    """The honest miss is reported even when the leading "Ä" was mangled to "*"
    (B204): the unapplied rule keys on the OLD/NEW pair + miss, not the verb."""
    from packages.generation.followup.copy_directives import (
        _followup_requested_copy_replace,
    )
    from scripts.prompt_to_project_input import compute_unapplied_followup_intents

    previous = _previous_project_input()
    mangled_miss = '*ndra "den här texten finns inte i någon copy alls" till "Ny text"'
    merged = _merge_rendered(mangled_miss, previous=previous)
    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt=mangled_miss,
        previous_rendered_story=_RENDERED_ABOUT_STORY,
    )
    assert any(post["target"] == "copy-replace" for post in posts)
    # The build-side honest-effect gate also still flags the mangled request.
    assert _followup_requested_copy_replace(mangled_miss) is True


@pytest.mark.tooling
def test_landed_rendered_story_edit_has_no_unapplied_post() -> None:
    """The successful rendered-story edit (Track B) must NOT also report an
    unapplied copy-replace miss - the two tracks compose, no double-signal."""
    from scripts.prompt_to_project_input import compute_unapplied_followup_intents

    previous = _previous_project_input()
    merged = _merge_rendered(_RENDERED_ABOUT_PROMPT, previous=previous)
    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt=_RENDERED_ABOUT_PROMPT,
        previous_rendered_story=_RENDERED_ABOUT_STORY,
    )
    assert not any(post["target"] == "copy-replace" for post in posts)


@pytest.mark.tooling
def test_additive_prompt_with_quoted_labels_is_not_a_copy_replace_miss() -> None:
    """An ADDITIVE ask that merely quotes two new labels must NOT be reported as
    a copy-replace miss - the rule is gated on the (verb-independent) replace
    request, which excludes additive phrasings, so a section/button add is never
    mistaken for a failed swap."""
    from scripts.prompt_to_project_input import compute_unapplied_followup_intents

    previous = _previous_project_input()
    additive = 'lägg till en knapp som säger "Boka nu" och en som säger "Ring oss"'
    merged = _merge_rendered(additive, previous=previous)
    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt=additive,
        previous_rendered_story=_RENDERED_ABOUT_STORY,
    )
    assert not any(post["target"] == "copy-replace" for post in posts)
