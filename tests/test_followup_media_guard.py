"""Regression coverage for the bildbyte-guard (2026-06-11).

The operator prompt "Byt ut hero-bilden till en unsplash bild" (hero marked in
the preview) used to be classified as a TEXT replace: ``_classify_copy_target``
mapped "hero" to the tagline and ``_extract_replace_value`` spliced the
trailing "en unsplash bild" into public copy. Free-text image/video changes
have no deterministic consumer (the structured asset_set path is the supported
route), so these prompts must be an honest no-op in the copyDirective
subsystem and be named in ``unappliedFollowupIntents``.

Locked here:

- media prompts produce no copy directive (deterministic rules),
- media prompts never reach the copyDirectiveModel fallback,
- quoted media words (payload/OLD copy) do NOT trigger the guard,
- an explicit text noun ("rubriken under bilden") exempts the prompt,
- the merge leaves copy untouched end-to-end,
- compute_unapplied_followup_intents reports the miss honestly.
"""

from __future__ import annotations

import copy

import pytest

from packages.generation.followup.copy_directives import is_media_change_request
from scripts.prompt_to_project_input import (
    _copy_directive_llm_eligible,
    _extract_copy_directives,
    compute_unapplied_followup_intents,
    merge_followup_project_input,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

OPERATOR_BUG_PROMPT = "Byt ut hero-bilden till en unsplash bild"


def _previous_project_input() -> dict[str, object]:
    """A schema-valid Project Input standing in for a previous version."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "fotofirma-abc123",
        "scaffoldId": "local-service-business",
        "variantId": "family-warmth",
        "language": "sv",
        "company": {
            "name": "Fotofirman",
            "businessType": "service",
            "tagline": "Vi fångar ögonblicken",
            "story": "En liten studio med stor passion.",
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö"],
        },
        "services": [
            {"id": "portratt", "label": "Porträtt", "summary": "Fina porträtt."}
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


def _merge(prompt: str) -> dict[str, object]:
    previous = _previous_project_input()
    return merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt=prompt,
        enable_llm_fallback=False,
    )


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        OPERATOR_BUG_PROMPT,
        "Byt ut till en unsplash bild",
        "Byt bilden i hero till en bild från unsplash",
        "Byt ut bakgrundsbilden till något ljusare",
        "Byt ut bilden mot en film",
        "Byt loggan till något modernare",
        "Change the hero image to a photo of a workshop",
    ],
)
def test_media_prompts_trigger_guard_and_extract_nothing(prompt: str) -> None:
    assert is_media_change_request(prompt) is True
    assert _extract_copy_directives(prompt, language="sv") == []


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        # Media words INSIDE quotes are payload/OLD copy, never asset intent.
        'Ändra taglinen till "En bild säger mer än tusen ord"',
        # An explicit text noun exempts: the image is a LOCATION here.
        "Byt rubriken under bilden till 'Välkommen in'",
        # Unquoted trailing payload that merely contains a media word.
        "Byt taglinen till Bilder för livet",
        # Closed compound payloads never word-match the media nouns.
        "Ändra företagsnamnet till Bildstudion",
        # No media word at all ("utbildar" must not substring-match "bild").
        "Vi utbildar hantverkare i Malmö",
    ],
)
def test_copy_prompts_do_not_trigger_guard(prompt: str) -> None:
    assert is_media_change_request(prompt) is False


@pytest.mark.tooling
def test_guarded_prompt_keeps_tagline_extraction_alive() -> None:
    directives = _extract_copy_directives(
        "Byt rubriken under bilden till 'Välkommen in'", language="sv"
    )
    assert directives == [
        {
            "target": "tagline",
            "operation": "replace-text",
            "payload": "Välkommen in",
            "source": "prompt-rule",
        }
    ]


@pytest.mark.tooling
def test_media_prompt_is_not_llm_eligible() -> None:
    assert (
        _copy_directive_llm_eligible(OPERATOR_BUG_PROMPT, intent="no-semantic-change")
        is False
    )
    assert (
        _copy_directive_llm_eligible(
            "Byt ut till en unsplash bild", intent="tagline-update"
        )
        is False
    )


@pytest.mark.tooling
def test_non_media_prompt_stays_llm_eligible() -> None:
    assert (
        _copy_directive_llm_eligible(
            "Byt taglinen till något varmare", intent="tagline-update"
        )
        is True
    )


@pytest.mark.tooling
def test_merge_leaves_copy_untouched_for_media_prompt() -> None:
    previous = _previous_project_input()
    merged = _merge(OPERATOR_BUG_PROMPT)
    assert merged["company"]["name"] == previous["company"]["name"]
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["company"]["story"] == previous["company"]["story"]
    assert "unsplash" not in str(merged).lower()


@pytest.mark.tooling
def test_unapplied_intents_report_media_miss() -> None:
    previous = _previous_project_input()
    merged = _merge(OPERATOR_BUG_PROMPT)
    posts = compute_unapplied_followup_intents(
        previous, merged, follow_up_prompt=OPERATOR_BUG_PROMPT
    )
    targets = [post["target"] for post in posts]
    assert "image-asset" in targets
    media_post = next(post for post in posts if post["target"] == "image-asset")
    assert "Byt bild här" in media_post["reason"]


@pytest.mark.tooling
def test_unapplied_intents_skip_media_mention_without_change_verb() -> None:
    previous = _previous_project_input()
    posts = compute_unapplied_followup_intents(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt="Bilden i heron är jättefin",
    )
    assert all(post["target"] != "image-asset" for post in posts)


@pytest.mark.tooling
def test_unapplied_intents_skip_quoted_media_words() -> None:
    previous = _previous_project_input()
    merged = _merge('Ändra taglinen till "En bild säger mer än tusen ord"')
    posts = compute_unapplied_followup_intents(
        previous,
        merged,
        follow_up_prompt='Ändra taglinen till "En bild säger mer än tusen ord"',
    )
    assert all(post["target"] != "image-asset" for post in posts)
