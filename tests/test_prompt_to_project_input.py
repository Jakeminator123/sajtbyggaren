"""Tests for scripts/prompt_to_project_input.py.

Locks the prompt-driven Project Input loop:

- Slugified siteId always satisfies apps/viewser/lib/project-inputs.ts'
  SITE_ID_PATTERN so the Viewser path-escape guards still hold when the
  siteId is generated server-side instead of operator-picked.
- Generated Project Input validates against
  governance/schemas/project-input.schema.json. A future schema bump
  must keep the helper passing or the prompt loop silently produces
  builds that crash inside build_site.py with a confusing KeyError.
- Scaffold heuristic flips to ecommerce-lite for shop-flavoured prompts
  and stays on local-service-business otherwise (default behaviour).
- Sidecar `<siteId>.meta.json` carries projectId + version + briefSource
  so the follow-up sprint can build "prompt -> ny version" on top of
  this sprint without a project-input schema migration.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
SITE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

sys.path.insert(0, str(REPO_ROOT))

from scripts.prompt_to_project_input import (  # noqa: E402
    _build_services,
    _company_business_label,
    _derive_company_name,
    _derive_story,
    _derive_tagline,
    _normalize_location_hint,
    _slugify_label,
    classify_followup_intent,
    generate,
    generate_followup,
    merge_followup_project_input,
    pick_scaffold,
    site_brief_to_project_input,
    slugify_site_id,
)


@pytest.fixture(scope="module")
def project_input_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_slugify_produces_valid_site_id() -> None:
    site_id = slugify_site_id("Skapa hemsida för en elektriker i Malmö")
    assert SITE_ID_PATTERN.match(site_id), site_id
    assert site_id.startswith("skapa-hemsida"), site_id


@pytest.mark.tooling
def test_slugify_handles_punctuation_only_prompt() -> None:
    """Falls back to `site-<tail>` so the schema-required siteId field
    cannot end up empty even for crafted prompts."""
    site_id = slugify_site_id("???")
    assert SITE_ID_PATTERN.match(site_id), site_id
    assert site_id.startswith("site-"), site_id


@pytest.mark.tooling
def test_slugify_handles_non_latin_script() -> None:
    """Cyrillic/CJK prompts still produce a valid siteId via the
    fallback. No silent crash inside build_site.py downstream."""
    site_id = slugify_site_id("漢字 のみ")
    assert SITE_ID_PATTERN.match(site_id), site_id


@pytest.mark.tooling
def test_slugify_site_id_uses_company_name_when_provided() -> None:
    site_id = slugify_site_id(
        "[Operatörens beskrivning]\nJag vill ha en varm keramiksajt",
        suffix="abcdef",
        company_name="Atelje Vit Lera",
    )
    assert site_id == "atelje-vit-lera-abcdef"


@pytest.mark.tooling
def test_slugify_site_id_falls_back_to_prompt_when_company_empty() -> None:
    site_id = slugify_site_id(
        "elektriker i Malmö",
        suffix="abcdef",
        company_name="   ",
    )
    assert site_id == "elektriker-i-malmo-abcdef"


@pytest.mark.tooling
def test_slugify_site_id_strips_master_prompt_header_when_no_company_name() -> None:
    site_id = slugify_site_id(
        "[Operatörens beskrivning]\nFrisörsalongen Tussilago i Göteborg",
        suffix="abcdef",
    )
    assert site_id == "frisorsalongen-tussilago-abcdef"
    assert not site_id.startswith("operatorens-beskrivning")


@pytest.mark.tooling
def test_prompt_helper_docstring_matches_stdout_contract() -> None:
    """B85: module docs must list the same stdout keys as ``main()`` emits."""
    helper_path = REPO_ROOT / "scripts" / "prompt_to_project_input.py"
    helper_text = helper_path.read_text(encoding="utf-8")
    module = ast.parse(helper_text)
    module_docstring = ast.get_docstring(module) or ""

    documented_keys = re.findall(r"``([A-Za-z][A-Za-z0-9]*):", module_docstring)
    emitted_keys = re.findall(r'print\(f"([A-Za-z][A-Za-z0-9]*):', helper_text)

    assert documented_keys == emitted_keys


@pytest.mark.tooling
def test_pick_scaffold_defaults_to_local_service_business() -> None:
    scaffold_id, variant_id = pick_scaffold(
        "Skapa en hemsida för en målare", brief_business_type="painter"
    )
    assert scaffold_id == "local-service-business"
    assert variant_id == "nordic-trust"


@pytest.mark.tooling
def test_pick_scaffold_flips_to_ecommerce_for_shop_prompt() -> None:
    scaffold_id, variant_id = pick_scaffold(
        "Bygg en webshop med produkter och checkout",
        brief_business_type=None,
    )
    assert scaffold_id == "ecommerce-lite"
    assert variant_id == "clean-store"


@pytest.mark.tooling
def test_pick_scaffold_flips_via_business_type_signal() -> None:
    """When the prompt has no shop tokens but briefModel detected a
    shop-flavoured business type, still flip to ecommerce-lite."""
    scaffold_id, _ = pick_scaffold(
        "Skapa en sida som visar mitt varumärke",
        brief_business_type="online-shop",
    )
    assert scaffold_id == "ecommerce-lite"


# ---------------------------------------------------------------------------
# pick_scaffold — clinic-healthcare routing (closes Lane 3 embeddings-gate
# blocker for naprapat-stockholm baseline case in
# scripts/run_golden_path_eval.py). Pre-fix the pinned-Project-Input flow
# routed every clinic prompt to local-service-business via the default
# branch; the eval scored naprapat-stockholm 5.83 (under
# PASS_CASE_THRESHOLD=6.5). Mirrors the _CLINIC_SIGNALS test block in
# tests/test_planning.py — both code paths need the same coverage.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_pick_scaffold_flips_to_clinic_on_naprapat_prompt() -> None:
    """The exact naprapat-stockholm prompt from run_golden_path_eval.py."""
    scaffold_id, variant_id = pick_scaffold(
        "Skapa en hemsida för en naprapatklinik i Stockholm.",
        brief_business_type=None,
    )
    assert scaffold_id == "clinic-healthcare"
    assert variant_id == "clinic-calm"


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt,case_label",
    [
        ("Skapa en hemsida för en tandläkarmottagning i Uppsala.", "tandläkare"),
        ("Skapa en hemsida för en kiropraktor i Lund.", "kiropraktor"),
        ("Skapa en hemsida för en fysioterapeut i Borås.", "fysioterapeut"),
        ("Skapa en hemsida för en psykolog i Linköping.", "psykolog"),
        ("Skapa en hemsida för en veterinärklinik i Skövde.", "veterinärklinik"),
        ("Build a site for a chiropractor in Stockholm.", "chiropractor"),
        ("Build a site for a small dental practice.", "dental"),
    ],
)
def test_pick_scaffold_flips_to_clinic_on_sharp_medical_prompt(
    prompt, case_label
) -> None:
    """Sharp medical terms in the prompt route to clinic-healthcare.

    Mirrors the regulated-clinician subset of
    ``packages/generation/orchestration/scaffolds/clinic-healthcare/selection-profile.json``
    semanticSignals while staying conservative against false positives on
    wellness/salon briefs.
    """
    scaffold_id, variant_id = pick_scaffold(prompt, brief_business_type=None)
    assert scaffold_id == "clinic-healthcare", (
        f"{case_label} should route to clinic-healthcare (prompt={prompt!r})."
    )
    assert variant_id == "clinic-calm"


@pytest.mark.tooling
@pytest.mark.parametrize(
    "business_type,case_label",
    [
        ("naprapath-clinic", "naprapath-clinic slug"),
        ("naprapatklinik", "naprapatklinik slug"),
        ("dental-clinic", "dental-clinic slug"),
        ("physiotherapy-clinic", "physiotherapy-clinic slug"),
        ("chiropractic-clinic", "chiropractic-clinic slug"),
    ],
)
def test_pick_scaffold_flips_to_clinic_via_business_type_signal(
    business_type, case_label
) -> None:
    """When the prompt has no medical tokens but briefModel returned a
    clinic-flavoured business-type slug, still flip to clinic-healthcare.

    Mirrors the existing ecommerce business-type branch — briefModel
    sometimes produces a precise ``businessTypeGuess`` while the
    operator's prompt is generic ("Hjälp med ryggsmärta — lugn mottagning").
    """
    scaffold_id, _ = pick_scaffold(
        "Hjälp med ryggsmärta — lugn och bekväm mottagning.",
        brief_business_type=business_type,
    )
    assert scaffold_id == "clinic-healthcare", (
        f"{case_label} businessType should route to clinic-healthcare."
    )


@pytest.mark.tooling
def test_pick_scaffold_keeps_local_service_for_salon_prompt() -> None:
    """Negative: hairsalon prompt must keep routing to local-service-business.

    Bare ``klinik`` / ``clinic`` is intentionally NOT in _CLINIC_TOKENS
    because beauty-klinik / hair-klinik / wellness-klinik are scaffold's
    explicit negative-signals (selection-profile.json
    llmClassificationHints rad 31-32). Mirrors the salon-goteborg
    baseline case in run_golden_path_eval.py.
    """
    scaffold_id, _ = pick_scaffold(
        "Skapa en hemsida för en frisörsalong i Göteborg.",
        brief_business_type="frisor-salong",
    )
    assert scaffold_id == "local-service-business"


@pytest.mark.tooling
def test_pick_scaffold_picks_ecommerce_over_clinic_when_both_signal() -> None:
    """Order-of-operations: commerce signals beat clinic signals.

    A "tandvårdsbutik som säljer munhygienprodukter" has both ``dental``
    (clinic-adjacent in _CLINIC_TOKENS) and ``produkter`` + ``butik``
    (commerce). The pick must route to ecommerce-lite, not clinic-
    healthcare — otherwise an obvious shop would silently inherit clinic
    chrome (treatments page, credentials row, etc).
    """
    scaffold_id, _ = pick_scaffold(
        (
            "Bygg en webshop för en tandvårdsbutik som säljer "
            "munhygienprodukter i Stockholm."
        ),
        brief_business_type="dental-supplies-shop",
    )
    assert scaffold_id == "ecommerce-lite"


@pytest.mark.tooling
def test_site_brief_to_project_input_validates_against_schema(
    project_input_schema: dict,
) -> None:
    """Empty mock-no-key brief must still produce a schema-valid
    Project Input - that is the path local dev hits without an OpenAI
    API key."""
    mock_brief = {
        "language": "sv",
        "businessTypeGuess": None,
        "rawPrompt": "Skapa en hemsida",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": None,
        "notesForPlanner": None,
        "briefSource": "mock-no-key",
    }
    project_input, _ = site_brief_to_project_input(
        mock_brief,
        site_id="example-site-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa en hemsida",
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["siteId"] == "example-site-abcdef"
    # Schema requires services minItems=1; the placeholder must satisfy it.
    assert len(project_input["services"]) >= 1


@pytest.mark.tooling
def test_site_brief_to_project_input_uses_real_brief_fields(
    project_input_schema: dict,
) -> None:
    rich_brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "rawPrompt": "Skapa hemsida för elektriker i Malmö",
        "tone": ["trustworthy", "local"],
        "conversionGoals": ["call", "quote-request"],
        "servicesMentioned": ["paneldragning", "laddbox-installation"],
        "requestedCapabilities": ["contact-form"],
        "locationHint": "Malmö",
        "notesForPlanner": "Lokal elektriker som söker offertförfrågningar.",
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        rich_brief,
        site_id="elektriker-malmo-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa hemsida för elektriker i Malmö",
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["language"] == "sv"
    assert project_input["company"]["businessType"] == "electrician"
    assert project_input["location"]["city"] == "Malmö"
    assert project_input["conversionGoals"] == ["call", "quote-request"]
    service_ids = {svc["id"] for svc in project_input["services"]}
    assert "paneldragning" in service_ids
    assert "laddbox-installation" in service_ids
    assert project_input["tone"]["primary"] == "trustworthy"


@pytest.mark.tooling
def test_site_brief_company_name_overrides_derived_h1(
    project_input_schema: dict,
) -> None:
    """B64: an explicit companyName from Site Brief must survive into
    Project Input instead of being replaced by businessType + location.
    """
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "companyName": "Volt & Co",
        "rawPrompt": "Skapa hemsida för Volt & Co i Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="volt-co-malmo",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa hemsida för Volt & Co i Malmö",
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["company"]["name"] == "Volt & Co"


@pytest.mark.tooling
def test_site_brief_without_company_name_uses_existing_fallback() -> None:
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "rawPrompt": "elektriker Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="elektriker-malmo",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="elektriker Malmö",
    )
    assert project_input["company"]["name"] == "Elektriker i Malmö"


@pytest.mark.tooling
def test_placeholder_contact_returns_field_list() -> None:
    """B133: ``_placeholder_contact`` returns a ``(contact_dict, fields)``
    tuple. With no real values from briefModel, all four contact slots
    (phone, email, addressLines, openingHours) are filled with B88
    dummies and the list reports every key.

    ``openingHours`` was added in the Codex P2 review follow-up
    2026-05-19 — the contact page renders the fallback schedule next to
    the phone number, so it must also surface as a placeholder warning
    until wizard/scrape supplies real hours.
    """
    from scripts.prompt_to_project_input import _placeholder_contact

    contact_sv, fields_sv = _placeholder_contact("sv")
    assert fields_sv == ["phone", "email", "addressLines", "openingHours"]
    assert contact_sv["phone"] == "+46 8 000 00 00"
    assert contact_sv["email"] == "kontakt@example.se"
    assert contact_sv["addressLines"] == ["Adress lämnas på förfrågan"]
    assert contact_sv["openingHours"] == "Mån-Fre 09:00-17:00"

    contact_en, fields_en = _placeholder_contact("en")
    assert fields_en == ["phone", "email", "addressLines", "openingHours"]
    assert contact_en["email"] == "contact@example.se"
    assert contact_en["addressLines"] == ["Address available on request"]
    assert contact_en["openingHours"] == "Mon-Fri 09:00-17:00"


@pytest.mark.tooling
def test_placeholder_contact_omits_filled_fields_from_list() -> None:
    """B133: every field the caller fills in must be absent from the
    placeholder list. Mixed input is the common scrape case where one
    or two fields landed but the rest stayed empty.
    """
    from scripts.prompt_to_project_input import _placeholder_contact

    contact, fields = _placeholder_contact(
        "sv",
        contact_phone="0701234567",
        contact_email="hej@voltco.se",
        contact_address="Storgatan 1, 211 22 Malmö",
        contact_opening_hours="Tis-Lör 10:00-18:00",
    )
    assert fields == [], "every contact slot supplied means no placeholders"
    assert contact["phone"] == "0701234567"
    assert contact["email"] == "hej@voltco.se"
    assert contact["addressLines"] == ["Storgatan 1, 211 22 Malmö"]
    assert contact["openingHours"] == "Tis-Lör 10:00-18:00"

    _, only_phone_left = _placeholder_contact(
        "sv",
        contact_email="hej@voltco.se",
        contact_address="Storgatan 1, 211 22 Malmö",
        contact_opening_hours="Tis-Lör 10:00-18:00",
    )
    assert only_phone_left == ["phone"]

    _, only_email_left = _placeholder_contact(
        "sv",
        contact_phone="0701234567",
        contact_address="Storgatan 1, 211 22 Malmö",
        contact_opening_hours="Tis-Lör 10:00-18:00",
    )
    assert only_email_left == ["email"]

    _, only_address_left = _placeholder_contact(
        "sv",
        contact_phone="0701234567",
        contact_email="hej@voltco.se",
        contact_opening_hours="Tis-Lör 10:00-18:00",
    )
    assert only_address_left == ["addressLines"]

    _, only_hours_left = _placeholder_contact(
        "sv",
        contact_phone="0701234567",
        contact_email="hej@voltco.se",
        contact_address="Storgatan 1, 211 22 Malmö",
    )
    assert only_hours_left == ["openingHours"]


@pytest.mark.tooling
def test_site_brief_to_project_input_propagates_placeholder_contact_fields() -> (
    None
):
    """B133: when briefModel returns nothing for the three contact
    fields, ``site_brief_to_project_input`` reports the full placeholder
    list as the second tuple element so ``generate()`` can put it on the
    meta sidecar (and ``scripts/build_site.py`` can surface it in
    ``build-result.json`` for Viewser).
    """
    mock_brief = {
        "language": "sv",
        "businessTypeGuess": None,
        "rawPrompt": "Skapa en hemsida",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": None,
        "notesForPlanner": None,
        "briefSource": "mock-no-key",
    }
    project_input, placeholder_fields = site_brief_to_project_input(
        mock_brief,
        site_id="placeholder-contact-site",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa en hemsida",
    )
    # ``openingHours`` always lands in the list when the brief is the
    # only source — the brief itself never carries opening hours, so
    # the dummy schedule survives unless the resolver's wizard layer
    # supplies real hours.
    assert placeholder_fields == [
        "phone",
        "email",
        "addressLines",
        "openingHours",
    ]
    assert project_input["contact"]["phone"] == "+46 8 000 00 00"

    rich_brief = {
        **mock_brief,
        "contactPhone": "0701234567",
        "contactEmail": "hej@voltco.se",
        "contactAddress": "Storgatan 1, 211 22 Malmö",
    }
    _, only_hours_placeholder = site_brief_to_project_input(
        rich_brief,
        site_id="real-contact-site",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa en hemsida",
    )
    # briefModel never returns ``contactOpeningHours``, so the dummy
    # schedule survives ``site_brief_to_project_input``. Wizard/scrape
    # must fill ``openingHours`` for the warning list to be empty in
    # the final ``generate()``-level recompute (see the follow-up test
    # for that path).
    assert only_hours_placeholder == ["openingHours"]


@pytest.mark.tooling
def test_generate_writes_placeholder_contact_fields_to_meta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B133: when briefModel has no contact values, the meta sidecar
    must carry ``placeholderContactFields`` so ``scripts/build_site.py``
    can read it via ``load_prompt_input_meta`` and write it into
    ``build-result.json``. When the brief has phone/email/address but
    no opening hours, only ``openingHours`` survives in the warning
    list — the brief itself never carries opening hours, so the dummy
    schedule needs wizard/scrape to disappear.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _, meta_placeholder, _, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="placeholder-meta-site",
    )
    assert meta_placeholder.get("placeholderContactFields") == [
        "phone",
        "email",
        "addressLines",
        "openingHours",
    ]

    def rich_brief_extract(*_args: object, **_kwargs: object) -> object:
        return {
            "language": "sv",
            "businessTypeGuess": "electrician",
            "companyName": "Volt & Co",
            "contactPhone": "0701234567",
            "contactEmail": "hej@voltco.se",
            "contactAddress": "Storgatan 1, 211 22 Malmö",
            "rawPrompt": "Volt & Co, telefon 0701234567, hej@voltco.se",
            "tone": [],
            "conversionGoals": [],
            "servicesMentioned": ["paneldragning"],
            "requestedCapabilities": [],
            "locationHint": "Malmö",
            "notesForPlanner": None,
        }

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(
        "scripts.prompt_to_project_input.extract_site_brief",
        rich_brief_extract,
    )
    monkeypatch.setattr(
        "scripts.prompt_to_project_input.site_brief_to_artifact",
        lambda brief, **_kw: {**brief, "briefSource": "real"},
    )

    _, meta_filled, _, _ = generate(
        "Volt & Co, telefon 0701234567, hej@voltco.se",
        output_dir=tmp_path,
        site_id="real-meta-site",
    )
    # Brief carries phone/email/address but never opening hours, so
    # the dummy schedule survives and the warning list narrows down to
    # ``openingHours`` only.
    assert meta_filled.get("placeholderContactFields") == ["openingHours"]


@pytest.mark.tooling
def test_followup_uses_preserved_language_for_placeholder_detection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B133 Codex P2 follow-up: a Swedish v1 edited with a follow-up
    prompt detected as English must still recognise its own Swedish
    placeholder values. ``merge_followup_project_input`` preserves the
    previous ``language`` + ``contact`` byte-stably, so the recompute
    must use ``project_input["language"]`` (preserved Swedish) rather
    than the prompt-detected English — otherwise the warning silently
    disappears even though ``kontakt@example.se`` / ``Adress lämnas på
    förfrågan`` are still rendered publicly in v2.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _, meta_v1, _, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="follow-up-language-site",
    )
    assert meta_v1["placeholderContactFields"] == [
        "phone",
        "email",
        "addressLines",
        "openingHours",
    ]

    monkeypatch.setattr(
        "scripts.prompt_to_project_input.detect_language",
        lambda *_args, **_kwargs: "en",
    )

    _, meta_v2, _, _ = generate_followup(
        "Make the headline shorter.",
        site_id="follow-up-language-site",
        output_dir=tmp_path,
    )

    assert meta_v2["mode"] == "followup"
    assert meta_v2["version"] == 2
    # Pre-fix this list silently went to ``[]`` because the recompute
    # compared preserved Swedish placeholders against English defaults.
    # Post-fix the preserved ``project_input["language"]`` keeps the
    # comparison correct and the warning survives into v2.
    assert meta_v2["placeholderContactFields"] == [
        "phone",
        "email",
        "addressLines",
        "openingHours",
    ]


def test_followup_with_discovery_recomputes_placeholder_fields_against_merged_contact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B136: follow-up med ny discovery måste låta resolve_discovery se
    placeholder_fields beräknade mot post-merge ``project_input.contact``,
    inte mot candidate brief från ny prompt. ``merge_followup_project_input``
    bevarar previous contact byte-stabilt, så candidate-listan från ny brief
    kan flagga phone/email/openingHours som placeholder trots att v1:s real
    contact-värden ligger kvar i den slutliga PI:n. Pre-B136 satte resolvern
    då ``fieldSources["contact.phone"] = "default"`` på real-värden, vilket
    var semantiskt fel och triggade ``operatorReviewRequired = True`` utan
    fog.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    real_contact_discovery = {
        "schemaVersion": 1,
        "rawPrompt": "frisör i Stockholm",
        "answers": {
            "siteType": ["salon"],
            "companyName": "Frisörsalongen Tussilago",
            "offer": "Klipper hår",
            "contact": {
                "phone": "08-123 45 67",
                "email": "kontakt@tussilago.se",
                "address": "Götgatan 12, 11646 Stockholm",
                "openingHours": "Tis-Lör 10:00-18:00",
            },
        },
    }

    _, meta_v1, _, _ = generate(
        "frisör i Stockholm",
        output_dir=tmp_path,
        site_id="b136-followup-site",
        discovery=real_contact_discovery,
    )

    decision_v1 = meta_v1["discoveryDecision"]
    assert decision_v1["fieldSources"]["contact.phone"] == "wizard"
    assert decision_v1["fieldSources"]["contact.email"] == "wizard"
    # Wizardens openingHours måste vara olik B88-default ("Mån-Fre 09:00-17:00")
    # för att inte markeras som placeholder; testet använder "Tis-Lör 10:00-18:00".
    assert meta_v1.get("placeholderContactFields", []) == []

    new_discovery_no_contact = {
        "schemaVersion": 1,
        "rawPrompt": "ändra ton till mer professionell",
        "answers": {
            "siteType": ["salon"],
        },
    }

    _, meta_v2, _, _ = generate_followup(
        "ändra ton till mer professionell",
        site_id="b136-followup-site",
        output_dir=tmp_path,
        discovery=new_discovery_no_contact,
    )

    decision_v2 = meta_v2["discoveryDecision"]
    # Pre-B136 skulle dessa rapporteras som "default" eftersom candidate-
    # listan från ny brief flaggade phone/email/openingHours som placeholder
    # trots att merge_followup bevarade v1:s real-värden byte-stabilt.
    # Post-B136 ska de visa "brief" (eller annan icke-default-källa) eftersom
    # post-merge contact är real och pre_resolve_placeholder_fields är tom.
    assert decision_v2["fieldSources"]["contact.phone"] != "default"
    assert decision_v2["fieldSources"]["contact.email"] != "default"
    assert decision_v2["fieldSources"]["contact.addressLines"] != "default"
    # Som följdkonsekvens: placeholderContactFields i meta är fortsatt tom
    # (B133-recompute kör mot samma post-merge contact).
    assert meta_v2.get("placeholderContactFields", []) == []


@pytest.mark.tooling
def test_site_brief_contact_fields_override_placeholders(
    project_input_schema: dict,
) -> None:
    """B65: explicit contact values from Site Brief must map to the
    schema-required Project Input contact block.
    """
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "companyName": "Volt & Co",
        "contactPhone": "0701234567",
        "contactEmail": "hej@voltco.se",
        "contactAddress": "Storgatan 1, 211 22 Malmö",
        "rawPrompt": "Volt & Co, telefon 0701234567, hej@voltco.se",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="volt-co-contact",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Volt & Co, telefon 0701234567, hej@voltco.se",
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["contact"]["phone"] == "0701234567"
    assert project_input["contact"]["email"] == "hej@voltco.se"
    assert project_input["contact"]["addressLines"] == [
        "Storgatan 1, 211 22 Malmö"
    ]


@pytest.mark.tooling
def test_selected_dossiers_rationale_matches_project_language() -> None:
    """B79: Swedish prompt-generated Project Inputs should not carry
    English operator rationale by default.
    """
    sv_brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "rawPrompt": "elektriker Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    en_brief = {**sv_brief, "language": "en", "rawPrompt": "electrician in Malmö"}

    sv_project_input, _ = site_brief_to_project_input(
        sv_brief,
        site_id="sv-rationale",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="elektriker Malmö",
    )
    en_project_input, _ = site_brief_to_project_input(
        en_brief,
        site_id="en-rationale",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="electrician in Malmö",
    )

    assert "Auto-genererat" in sv_project_input["selectedDossiers"]["rationale"]
    assert "Auto-generated" not in sv_project_input["selectedDossiers"]["rationale"]
    assert "Auto-generated" in en_project_input["selectedDossiers"]["rationale"]


@pytest.mark.tooling
def test_generate_writes_project_input_and_meta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """End-to-end: helper writes both files into the scratch dir.

    Uses tmp_path so the test never pollutes data/prompt-inputs/. Forces
    mock-no-key by deleting OPENAI_API_KEY so the test does not attempt
    a real network call.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    project_input, meta, project_input_path, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)

    assert project_input_path.exists()
    assert meta_path.exists()
    assert project_input_path.parent == tmp_path
    assert project_input_path.name.endswith(".v1.project-input.json")
    assert meta_path.name.endswith(".v1.meta.json")
    assert (tmp_path / f"{project_input['siteId']}.project-input.json").exists()
    assert (tmp_path / f"{project_input['siteId']}.meta.json").exists()

    # Meta sidecar contract: projectId + version are minimum what the
    # follow-up sprint reads to build "prompt -> ny version".
    assert "projectId" in meta and meta["projectId"]
    assert meta["version"] == 1
    assert meta["mode"] == "init"
    assert meta["siteId"] == project_input["siteId"]
    assert meta["originalPrompt"].startswith("Skapa")
    # mock-no-key path must be honest about not calling the real LLM.
    assert meta["briefSource"] == "mock-no-key"


@pytest.mark.tooling
def test_generate_falls_back_when_extract_site_brief_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """Unexpected exceptions from extract_site_brief must not crash the
    prompt-driven Viewser flow. The script should still write a
    schema-valid placeholder Project Input and record the failure in
    meta.briefError.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")

    def raise_llm_error(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("network timeout")

    monkeypatch.setattr(
        "scripts.prompt_to_project_input.extract_site_brief",
        raise_llm_error,
    )

    project_input, meta, project_input_path, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.exists()
    assert meta_path.exists()
    assert meta["briefSource"] == "mock-llm-error"
    assert "RuntimeError" in meta["briefError"]
    assert "network timeout" in meta["briefError"]


@pytest.mark.tooling
def test_generate_warns_when_brief_model_resolution_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """B87: model policy resolution failures must be visible on stderr."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def raise_policy_error() -> str:
        raise RuntimeError("briefModel role missing")

    monkeypatch.setattr(
        "scripts.prompt_to_project_input.resolve_brief_model",
        raise_policy_error,
    )

    _project_input, meta, _project_input_path, _meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="b87-model-warning",
    )

    captured = capsys.readouterr()
    assert "briefModel resolution failed; using fallback model gpt-5.4" in captured.err
    assert "briefModel role missing" in captured.err
    assert meta["briefSource"] == "mock-no-key"


@pytest.mark.tooling
def test_generate_falls_back_when_site_brief_to_artifact_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """The fallback must also cover exceptions after brief extraction,
    including serialization errors in site_brief_to_artifact.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def raise_serializer_error(*_args: object, **_kwargs: object) -> object:
        raise ValueError("bad artifact shape")

    monkeypatch.setattr(
        "scripts.prompt_to_project_input.site_brief_to_artifact",
        raise_serializer_error,
    )

    project_input, meta, project_input_path, meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.exists()
    assert meta_path.exists()
    assert meta["briefSource"] == "mock-llm-error"
    assert "ValueError" in meta["briefError"]
    assert "bad artifact shape" in meta["briefError"]


@pytest.mark.tooling
def test_generate_respects_explicit_site_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input, meta, project_input_path, _ = generate(
        "valfri prompt",
        output_dir=tmp_path,
        site_id="custom-site-id-abc",
    )
    assert project_input["siteId"] == "custom-site-id-abc"
    assert meta["siteId"] == "custom-site-id-abc"
    assert project_input_path.name == "custom-site-id-abc.v1.project-input.json"
    assert (tmp_path / "custom-site-id-abc.project-input.json").exists()


@pytest.mark.tooling
def test_generate_rejects_unsafe_explicit_site_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An operator-supplied siteId that violates SITE_ID_PATTERN must
    fail loudly here, not silently land a Project Input that the
    Viewser file APIs (assertSafeSiteId) will then refuse to read."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        generate(
            "valfri prompt",
            output_dir=tmp_path,
            site_id="../escape",
        )


@pytest.mark.tooling
def test_generate_followup_bumps_version_and_reuses_project_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_input_schema: dict,
) -> None:
    """Follow-up prompts keep projectId stable while version increments."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initial_project_input, initial_meta, initial_path, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="electrician-malmo",
        project_id="stable-project-id",
    )
    initial_snapshot = initial_path.read_text(encoding="utf-8")

    project_input, meta, project_input_path, next_meta_path = generate_followup(
        "Lägg till mer fokus på laddboxar och offertförfrågan.",
        output_dir=tmp_path,
        site_id="electrician-malmo",
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input_path.name == "electrician-malmo.v2.project-input.json"
    assert next_meta_path.name == "electrician-malmo.v2.meta.json"
    assert initial_path.read_text(encoding="utf-8") == initial_snapshot
    assert meta["projectId"] == initial_meta["projectId"] == "stable-project-id"
    assert meta["siteId"] == "electrician-malmo"
    assert meta["version"] == 2
    assert meta["mode"] == "followup"
    assert meta["previousVersion"] == 1
    assert meta["originalPrompt"] == initial_meta["originalPrompt"]
    assert meta["followUpPrompt"].startswith("Lägg till mer fokus")
    assert "latestPrompt" not in meta
    assert meta["projectDna"]["story"] == initial_meta["projectDna"]["story"]
    assert meta["projectDna"]["tagline"] == initial_meta["projectDna"]["tagline"]
    assert meta["projectDna"]["tone"] == initial_meta["projectDna"]["tone"]
    assert meta["projectDna"]["positioning"] == initial_meta["projectDna"]["positioning"]
    assert meta["projectDna"]["followUpIntent"]["id"] == "no-semantic-change"
    assert project_input["company"]["name"] == initial_project_input["company"]["name"]
    assert project_input["contact"] == initial_project_input["contact"]
    assert project_input["scaffoldId"] == initial_project_input["scaffoldId"]
    # B60 fynd 2: follow-up prompt MUST NOT leak into customer-facing
    # company.story. The operator's prompt lives in meta.followUpPrompt
    # only; render_about in build_site.py renders company.story directly
    # on /om-oss, so any English workflow suffix would surface as public
    # copy. Lock the absence of the pre-B60 leakage and lock that
    # company.story matches v1 byte-for-byte (no merge-time mutation).
    assert "Follow-up request" not in project_input["company"]["story"]
    assert "Lägg till mer fokus" not in project_input["company"]["story"]
    assert (
        project_input["company"]["story"]
        == initial_project_input["company"]["story"]
    )

    current_meta = json.loads(
        (tmp_path / "electrician-malmo.meta.json").read_text(encoding="utf-8")
    )
    assert current_meta["version"] == 2
    assert current_meta["followUpPrompt"] == meta["followUpPrompt"]
    assert current_meta["projectDna"] == meta["projectDna"]


def _wizard_discovery_payload(
    must_have: list[str],
    *,
    company_name: str = "Wizard Must Have AB",
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "rawPrompt": "Skapa hemsida för Wizard Must Have AB",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {
            "siteType": ["business"],
            "companyName": company_name,
            "mustHave": must_have,
        },
    }


@pytest.mark.tooling
def test_followup_with_new_discovery_resets_wizard_must_have(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B134: a fresh follow-up discovery payload must replace v1 pages."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _, initial_meta, _, _ = generate(
        "Skapa hemsida för Wizard Must Have AB",
        output_dir=tmp_path,
        site_id="wizard-reset-site",
        project_id="stable-project-id",
        discovery=_wizard_discovery_payload(
            ["Bokning online", "Bildgalleri"],
        ),
    )
    assert initial_meta["wizardMustHave"] == ["Bokning online", "Bildgalleri"]

    _project_input, followup_meta, _path, followup_meta_path = generate_followup(
        "Byt riktning till en kort FAQ-sajt.",
        output_dir=tmp_path,
        site_id="wizard-reset-site",
        discovery=_wizard_discovery_payload(["FAQ"]),
    )

    assert followup_meta["mode"] == "followup"
    assert followup_meta["version"] == 2
    assert followup_meta["wizardMustHave"] == ["FAQ"]
    assert "inheritedFromVersion" not in followup_meta["discoveryDecision"]
    written_meta = json.loads(followup_meta_path.read_text(encoding="utf-8"))
    assert written_meta["wizardMustHave"] == ["FAQ"]


@pytest.mark.tooling
def test_followup_without_new_discovery_inherits_wizard_must_have(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B134 keeps B132's warning signal for follow-ups without a new wizard."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _, initial_meta, _, _ = generate(
        "Skapa hemsida för Wizard Must Have AB",
        output_dir=tmp_path,
        site_id="wizard-inherit-site",
        project_id="stable-project-id",
        discovery=_wizard_discovery_payload(
            ["Bokning online", "Bildgalleri"],
        ),
    )

    _project_input, followup_meta, _path, followup_meta_path = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="wizard-inherit-site",
    )

    assert followup_meta["wizardMustHave"] == initial_meta["wizardMustHave"]
    assert followup_meta["discoveryDecision"]["inheritedFromVersion"] == 1
    written_meta = json.loads(followup_meta_path.read_text(encoding="utf-8"))
    assert written_meta["wizardMustHave"] == initial_meta["wizardMustHave"]


@pytest.mark.tooling
def test_followup_with_explicit_reset_flag_clears_wizard_must_have(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B134 opt-out: callers can explicitly clear stale page intent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa hemsida för Wizard Must Have AB",
        output_dir=tmp_path,
        site_id="wizard-clear-site",
        project_id="stable-project-id",
        discovery=_wizard_discovery_payload(
            ["Bokning online", "Bildgalleri"],
        ),
    )

    _project_input, followup_meta, _path, followup_meta_path = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="wizard-clear-site",
        reset_wizard_must_have=True,
    )

    assert followup_meta["mode"] == "followup"
    assert followup_meta["version"] == 2
    assert followup_meta["previousVersion"] == 1
    assert followup_meta["followUpPrompt"] == "Gör tonen varmare."
    assert "wizardMustHave" not in followup_meta
    written_meta = json.loads(followup_meta_path.read_text(encoding="utf-8"))
    assert "wizardMustHave" not in written_meta


@pytest.mark.tooling
def test_generate_followup_supports_multiple_version_bumps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="malare-lund",
        project_id="stable-project-id",
    )

    _, meta_v2, path_v2, meta_path_v2 = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="malare-lund",
    )
    _, meta_v3, path_v3, meta_path_v3 = generate_followup(
        "Lyft fram fasadmålning.",
        output_dir=tmp_path,
        site_id="malare-lund",
    )

    assert meta_v2["projectId"] == "stable-project-id"
    assert meta_v2["version"] == 2
    assert meta_v3["projectId"] == "stable-project-id"
    assert meta_v3["version"] == 3
    assert meta_v3["previousVersion"] == 2
    assert path_v2.name == "malare-lund.v2.project-input.json"
    assert path_v3.name == "malare-lund.v3.project-input.json"
    assert meta_path_v2.name == "malare-lund.v2.meta.json"
    assert meta_path_v3.name == "malare-lund.v3.meta.json"

    current_meta = json.loads(
        (tmp_path / "malare-lund.meta.json").read_text(encoding="utf-8")
    )
    assert current_meta["version"] == 3
    assert current_meta["followUpPrompt"] == "Lyft fram fasadmålning."


@pytest.mark.tooling
def test_generate_followup_requires_existing_meta(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="meta sidecar saknas"):
        generate_followup(
            "Lägg till ny text.",
            output_dir=tmp_path,
            site_id="missing-site",
        )


@pytest.mark.tooling
def test_generate_followup_with_base_run_id_iterates_from_specific_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GAP-backend-build-trace-endpoint D-criterion.

    When ``base_run_id`` points at v1's run, follow-up should:
      * Read the v1 PI snapshot (not the latest v2 pointer).
      * Bump version to ``max(latest, base) + 1`` so we never overwrite
        an existing snapshot.
      * Persist ``baseRunId`` in the new meta so the operator can audit
        which version a v3 was iterated from.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    initial_pi, _initial_meta, _initial_pi_path, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="electrician-fork",
        project_id="stable-project-id",
    )
    # Anchor a fake v1 run on disk that points back at the v1 snapshot.
    v1_run_id = "run-v1-anchor"
    v1_run_dir = runs_dir / v1_run_id
    v1_run_dir.mkdir()
    (v1_run_dir / "input.json").write_text(
        json.dumps(
            {
                "runId": v1_run_id,
                "mode": "init",
                "rawPrompt": "Skapa en hemsida för en elektriker i Malmö",
                "dossierPath": "irrelevant",
                "projectId": "stable-project-id",
                "version": 1,
            }
        ),
        encoding="utf-8",
    )

    # Bump latest to v2 first so we can prove that base-run-id reads v1
    # rather than picking up the latest pointer.
    generate_followup(
        "Lägg till mer fokus på laddboxar",
        output_dir=tmp_path,
        site_id="electrician-fork",
    )
    assert (tmp_path / "electrician-fork.v2.project-input.json").exists()

    # Now iterate from v1 — expected to land at v3 (max(2, 1) + 1) and
    # use the v1 PI snapshot as base, not v2.
    project_input, meta, project_input_path, meta_path = generate_followup(
        "Hoppa tillbaka och förstärk lokal närhet istället",
        output_dir=tmp_path,
        site_id="electrician-fork",
        base_run_id=v1_run_id,
        runs_dir=runs_dir,
    )

    assert project_input_path.name == "electrician-fork.v3.project-input.json"
    assert meta_path.name == "electrician-fork.v3.meta.json"
    assert meta["version"] == 3
    assert meta["previousVersion"] == 1
    assert meta["baseRunId"] == v1_run_id
    assert project_input["company"]["story"] == initial_pi["company"]["story"]


@pytest.mark.tooling
def test_generate_followup_rejects_unknown_base_run_id(tmp_path: Path) -> None:
    """An empty data/runs directory means the baseRunId cannot be resolved
    — surface a clean SystemExit instead of a stack trace.
    """
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    generate(
        "Skapa en hemsida för en cykelbutik",
        output_dir=tmp_path,
        site_id="bike-shop",
        project_id="bs-1",
    )
    with pytest.raises(SystemExit, match="baseRunId saknar katalog"):
        generate_followup(
            "Justera färgerna",
            output_dir=tmp_path,
            site_id="bike-shop",
            base_run_id="does-not-exist",
            runs_dir=runs_dir,
        )


@pytest.mark.tooling
def test_generate_followup_rejects_path_traversal_base_run_id(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    generate(
        "Skapa en hemsida för en bilverkstad",
        output_dir=tmp_path,
        site_id="auto-shop",
        project_id="as-1",
    )
    with pytest.raises(SystemExit, match="run-id-mönstret"):
        generate_followup(
            "Lägg till bokning",
            output_dir=tmp_path,
            site_id="auto-shop",
            base_run_id="../escape",
            runs_dir=runs_dir,
        )


@pytest.mark.tooling
def test_versioned_snapshot_refuses_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B60 fynd 1: `.vN.project-input.json` and `.vN.meta.json` snapshots
    must be immutable. A second `generate(...)` call that targets the
    same explicit `(site_id, project_id, version)` tuple would otherwise
    silently overwrite the previous snapshot and break PR #27's "older
    versions stay byte-stable" promise. Lock the SystemExit so future
    refactors of `write_project_input` cannot drop the FileExistsError
    guard in `_write_immutable_snapshot`.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="painter-immut",
        project_id="stable-project-id",
    )
    with pytest.raises(SystemExit, match="Versioned snapshot already exists"):
        generate(
            "Försök skriva över v1 med samma siteId/projectId/version.",
            output_dir=tmp_path,
            site_id="painter-immut",
            project_id="stable-project-id",
        )


@pytest.mark.tooling
def test_followup_does_not_inject_workflow_text_into_company_story(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """B60 fynd 2: cover the merge helper directly so the contract is
    locked even if a future caller bypasses `generate_followup`. The
    follow-up prompt must not be appended to `company.story`; it lives
    in `meta.followUpPrompt` only.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initial_project_input, _, _, _ = generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="painter-story",
        project_id="stable-project-id",
    )
    expected_story = initial_project_input["company"]["story"]

    followup_project_input, followup_meta, _, _ = generate_followup(
        "Lägg till ett tydligt prisavsnitt och varmare ton.",
        output_dir=tmp_path,
        site_id="painter-story",
    )

    assert followup_project_input["company"]["story"] == expected_story
    assert "Follow-up request" not in followup_project_input["company"]["story"]
    assert (
        "prisavsnitt" not in followup_project_input["company"]["story"]
    ), "Follow-up prompt content leaked into customer-facing copy."
    # Operator visibility is preserved via meta.followUpPrompt.
    assert followup_meta["followUpPrompt"].startswith("Lägg till ett tydligt")


@pytest.mark.tooling
def test_followup_story_intent_does_not_leak_raw_prompt() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "story": "Lyft fram familjeföretag-storyn.",
        },
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Lyft fram familjeföretag-storyn.",
    )

    assert merged["company"]["story"] != previous["company"]["story"]
    assert "Lyft fram familjeföretag-storyn" not in merged["company"]["story"]
    assert "familjeföretagets närhet" in merged["company"]["story"]


def _minimal_previous_project_input() -> dict[str, object]:
    return {
        "siteId": "stable-site",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Volt & Co",
            "businessType": "electrician",
            "tagline": "Byte-stable tagline",
            "story": "Byte-stable story",
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö"],
        },
        "contact": {
            "phone": "0701234567",
            "email": "hej@voltco.se",
            "addressLines": ["Storgatan 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "tone": {"primary": "lugn", "secondary": ["lokal"], "avoid": []},
        "services": [
            {"id": "elservice", "label": "Elservice", "summary": "Elservice."}
        ],
        "conversionGoals": ["call"],
        "requestedCapabilities": [],
        "trustSignals": [],
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }


@pytest.mark.tooling
def test_followup_merge_keeps_story_tagline_and_tone_byte_stable_when_intent_is_no_change() -> None:
    """B71: additive follow-up prompts keep semantic fields byte-stable."""
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            "name": "Ny kandidat",
            "businessType": "electrician",
            "tagline": "Candidate tagline",
            "story": "Candidate story",
        },
        "tone": {"primary": "premium", "secondary": ["varm"], "avoid": ["kall"]},
        "services": [
            {"id": "laddbox", "label": "Laddbox", "summary": "Laddbox."}
        ],
        "conversionGoals": ["quote-request"],
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Lägg till laddboxar och offertförfrågan.",
    )

    assert merged["company"]["story"] == "Byte-stable story"
    assert merged["company"]["tagline"] == "Byte-stable tagline"
    assert merged["tone"] == previous["tone"]
    assert {service["id"] for service in merged["services"]} == {
        "elservice",
        "laddbox",
    }
    assert merged["conversionGoals"] == ["call", "quote-request"]


@pytest.mark.tooling
def test_followup_merge_tone_shift_updates_tone_only() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "tagline": "Candidate tagline",
            "story": "Candidate story",
        },
        "tone": {"primary": "premium", "secondary": [], "avoid": []},
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Gör tonen mer premium, personlig och undvik kall ton.",
    )

    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["tone"]["primary"] == "premium"
    assert "personlig" in merged["tone"]["secondary"]
    assert merged["tone"]["avoid"] == ["kall"]


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("follow_up_prompt", "expected_primary", "expected_secondary"),
    [
        (
            "gör den lugnare och mer förtroendeingivande",
            "lugn",
            "förtroendeingivande",
        ),
        ("gör tonen lugnare", "lugn", None),
        ("gör sidan mer förtroendeingivande", "förtroendeingivande", None),
    ],
)
def test_followup_merge_trust_and_calm_prompts_update_tone_only(
    follow_up_prompt: str,
    expected_primary: str,
    expected_secondary: str | None,
) -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "tagline": "Candidate tagline",
            "story": "Candidate story",
        },
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt=follow_up_prompt,
    )

    assert classify_followup_intent(follow_up_prompt, language="sv") == "tone-shift"
    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["tone"]["primary"] == expected_primary
    if expected_secondary:
        assert expected_secondary in merged["tone"]["secondary"]


@pytest.mark.tooling
@pytest.mark.parametrize(
    "follow_up_prompt",
    [
        "lägg till premium produkt",
        "lägg till personalsida",
        "lägg till premium tjänst",
        "lägg till en lugnare sida om vår historia",
    ],
)
def test_followup_merge_additive_prompts_with_tone_words_keep_semantics_stable(
    follow_up_prompt: str,
) -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "tagline": "Candidate tagline",
            "story": "Candidate story",
        },
        "tone": {"primary": "premium", "secondary": ["personlig"], "avoid": []},
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt=follow_up_prompt,
    )

    assert classify_followup_intent(follow_up_prompt, language="sv") == "no-semantic-change"
    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["tone"] == previous["tone"]


@pytest.mark.tooling
def test_followup_mixed_additive_and_tone_prompt_preserves_additive_merge_and_updates_tone() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "tagline": "Candidate tagline",
            "story": "Candidate story",
        },
        "tone": {"primary": "premium", "secondary": [], "avoid": []},
        "services": [
            {"id": "faq", "label": "FAQ", "summary": "Vanliga frågor."}
        ],
    }

    prompt = "Lägg till FAQ och gör tonen mer premium."
    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt=prompt,
    )

    assert classify_followup_intent(prompt, language="sv") == "tone-shift"
    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["company"]["tagline"] == previous["company"]["tagline"]
    assert merged["tone"]["primary"] == "premium"
    assert {service["id"] for service in merged["services"]} == {"elservice", "faq"}


@pytest.mark.tooling
def test_followup_add_page_about_history_does_not_patch_story() -> None:
    """Additive page prompts containing story/history words stay conservative."""
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "story": "Candidate story from new brief",
        },
    }

    prompt = "Lägg till en sida om vår historia."
    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt=prompt,
    )

    assert classify_followup_intent(prompt, language="sv") == "no-semantic-change"
    assert merged["company"]["story"] == previous["company"]["story"]


@pytest.mark.tooling
def test_followup_merge_tagline_update_filters_ui_directive() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "tagline": "Hemsida om Volt, 2 sidor, gröna färger",
        },
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Gör taglinen mer personlig.",
    )

    assert merged["company"]["story"] == previous["company"]["story"]
    assert merged["tone"] == previous["tone"]
    assert merged["company"]["tagline"] == "Personlig hjälp med tydlig väg vidare"


@pytest.mark.tooling
def test_followup_merge_tagline_update_uses_safe_candidate_copy() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "tagline": "Alltid nära hjälp",
        },
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Uppdatera taglinen till: Alltid nära hjälp",
    )

    assert merged["company"]["tagline"] == "Alltid nära hjälp"


@pytest.mark.tooling
def test_followup_merge_story_update_allows_explicit_public_copy() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "story": "Lyft storyn till: Vi är ett familjeföretag sedan 1995.",
        },
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Lyft storyn till: Vi är ett familjeföretag sedan 1995.",
    )

    assert merged["company"]["story"] == "Vi är ett familjeföretag sedan 1995."


@pytest.mark.tooling
def test_followup_story_update_requires_colon_for_explicit_copy() -> None:
    previous = _minimal_previous_project_input()
    candidate = {
        **previous,
        "company": {
            **previous["company"],
            "story": "Candidate story",
        },
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Lyft storyn till en mer varm känsla.",
    )

    assert merged["company"]["story"] == "Candidate story."


@pytest.mark.tooling
def test_classify_followup_intent_matches_semantic_keywords() -> None:
    assert (
        classify_followup_intent("gör tonen mer premium", language="sv")
        == "tone-shift"
    )
    assert (
        classify_followup_intent("gör känslan mer personlig", language="sv")
        == "tone-shift"
    )
    assert (
        classify_followup_intent("lyft familjeföretag-storyn", language="sv")
        == "story-emphasize"
    )
    assert (
        classify_followup_intent("gör taglinen mer personlig", language="sv")
        == "tagline-update"
    )
    assert (
        classify_followup_intent("positionera oss mer premium", language="sv")
        == "positioning-shift"
    )


@pytest.mark.tooling
def test_classify_followup_intent_defaults_to_safe_states() -> None:
    assert (
        classify_followup_intent("lägg till FAQ", language="sv")
        == "no-semantic-change"
    )
    assert (
        classify_followup_intent("gör texten mer personlig", language="sv")
        == "no-semantic-change"
    )
    assert classify_followup_intent("", language="sv") == "clarify"
    assert classify_followup_intent("ok", language="sv") == "clarify"


@pytest.mark.tooling
def test_generate_followup_clarify_prompt_does_not_create_new_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _project_input, _meta, _path, _meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="clarify-block-site",
    )

    with pytest.raises(SystemExit, match="too unclear"):
        generate_followup(
            "ok",
            output_dir=tmp_path,
            site_id="clarify-block-site",
        )

    assert not (tmp_path / "clarify-block-site.v2.project-input.json").exists()


@pytest.mark.tooling
def test_generate_followup_tone_shift_updates_project_input_and_project_dna(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initial_project_input, initial_meta, _, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="tone-dna-site",
        project_id="stable-project-id",
    )

    project_input, meta, _, meta_path = generate_followup(
        "Gör tonen mer premium, personlig och undvik kall ton.",
        output_dir=tmp_path,
        site_id="tone-dna-site",
    )

    assert project_input["company"]["story"] == initial_project_input["company"]["story"]
    assert project_input["company"]["tagline"] == initial_project_input["company"]["tagline"]
    assert project_input["tone"]["primary"] == "premium"
    assert "personlig" in project_input["tone"]["secondary"]
    assert project_input["tone"]["avoid"] == ["kall"]
    assert meta["projectDna"]["createdAtVersion"] == 1
    assert meta["projectDna"]["followUpIntent"]["id"] == "tone-shift"
    assert meta["projectDna"]["tone"]["primary"] == {
        "value": "premium",
        "lastUpdatedVersion": 2,
        "source": "followup",
    }
    assert meta["projectDna"]["story"] == initial_meta["projectDna"]["story"]
    written_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert written_meta["projectDna"] == meta["projectDna"]


@pytest.mark.tooling
def test_generate_followup_story_and_tagline_prompts_change_project_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initial_project_input, _initial_meta, _, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="story-tagline-site",
        project_id="stable-project-id",
    )

    story_input, story_meta, _, _ = generate_followup(
        "Lyft familjeföretag-storyn.",
        output_dir=tmp_path,
        site_id="story-tagline-site",
    )
    tagline_input, tagline_meta, _, _ = generate_followup(
        "Gör taglinen mer personlig.",
        output_dir=tmp_path,
        site_id="story-tagline-site",
    )

    assert story_input["company"]["story"] != initial_project_input["company"]["story"]
    assert "Lyft familjeföretag" not in story_input["company"]["story"]
    assert story_meta["projectDna"]["story"]["source"] == "followup"
    assert tagline_input["company"]["tagline"] != story_input["company"]["tagline"]
    assert tagline_input["company"]["tagline"] == "Personlig hjälp med tydlig väg vidare"
    assert tagline_meta["projectDna"]["tagline"]["source"] == "followup"


@pytest.mark.tooling
def test_project_dna_sidecar_validates_against_snapshot_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _project_input, meta, _path, _meta_path = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="schema-dna-site",
    )
    schema = json.loads(
        (
            REPO_ROOT
            / "governance"
            / "schemas"
            / "project-dna-snapshot.schema.json"
        ).read_text(encoding="utf-8")
    )

    jsonschema.Draft202012Validator(schema).validate(meta["projectDna"])


@pytest.mark.tooling
def test_followup_with_no_intent_keeps_project_dna_fields_byte_stable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _initial_project_input, initial_meta, _, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="no-change-dna-site",
    )

    _project_input, meta, _, _ = generate_followup(
        "Lägg till FAQ och mer fokus på offert.",
        output_dir=tmp_path,
        site_id="no-change-dna-site",
    )

    assert meta["projectDna"]["story"] == initial_meta["projectDna"]["story"]
    assert meta["projectDna"]["tagline"] == initial_meta["projectDna"]["tagline"]
    assert meta["projectDna"]["tone"] == initial_meta["projectDna"]["tone"]
    assert meta["projectDna"]["positioning"] == initial_meta["projectDna"]["positioning"]
    assert meta["projectDna"]["followUpIntent"]["id"] == "no-semantic-change"


@pytest.mark.tooling
def test_followup_project_dna_refreshes_intent_after_prior_semantic_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="refresh-dna-intent-site",
    )
    _tone_input, tone_meta, _, _ = generate_followup(
        "Gör tonen mer premium.",
        output_dir=tmp_path,
        site_id="refresh-dna-intent-site",
    )
    _additive_input, additive_meta, _, _ = generate_followup(
        "Lägg till FAQ.",
        output_dir=tmp_path,
        site_id="refresh-dna-intent-site",
    )

    assert tone_meta["projectDna"]["followUpIntent"]["id"] == "tone-shift"
    assert additive_meta["projectDna"]["tone"] == tone_meta["projectDna"]["tone"]
    assert additive_meta["projectDna"]["followUpIntent"]["id"] == "no-semantic-change"


@pytest.mark.tooling
def test_followup_merge_docstring_describes_semantic_patching() -> None:
    doc = merge_followup_project_input.__doc__ or ""
    assert "visible story note" not in doc
    assert "Story, tagline and tone remain byte-stable" in doc
    assert "Project DNA semantic patching" in doc


@pytest.mark.tooling
def test_followup_merge_keeps_legacy_additive_behaviour() -> None:
    """Existing additive merge behaviour stays intact around semantic V1."""
    previous = {
        "siteId": "stable-site",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Volt & Co",
            "businessType": "electrician",
            "tagline": "Byte-stable tagline",
            "story": "Byte-stable story",
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö"],
        },
        "contact": {
            "phone": "0701234567",
            "email": "hej@voltco.se",
            "addressLines": ["Storgatan 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "tone": {"primary": "lugn", "secondary": ["lokal"], "avoid": []},
        "services": [
            {"id": "elservice", "label": "Elservice", "summary": "Elservice."}
        ],
        "conversionGoals": ["call"],
        "requestedCapabilities": [],
        "trustSignals": [],
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }
    candidate = {
        **previous,
        "company": {
            "name": "Ny kandidat",
            "businessType": "electrician",
            "tagline": "Candidate tagline",
            "story": "Candidate story",
        },
        "tone": {"primary": "premium", "secondary": ["varm"], "avoid": ["kall"]},
        "services": [
            {"id": "laddbox", "label": "Laddbox", "summary": "Laddbox."}
        ],
        "conversionGoals": ["quote-request"],
    }

    merged = merge_followup_project_input(
        previous,
        candidate,
        follow_up_prompt="Lägg till laddboxar och offertförfrågan.",
    )

    assert merged["company"]["story"] == "Byte-stable story"
    assert merged["company"]["tagline"] == "Byte-stable tagline"
    assert merged["tone"] == previous["tone"]
    assert {service["id"] for service in merged["services"]} == {
        "elservice",
        "laddbox",
    }
    assert merged["conversionGoals"] == ["call", "quote-request"]


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A (T2): raw prompt must never become customer-facing
# company.name or company.story copy. The previous helper used
# `prompt[:60]` as H1 and `prompt[:600]` as /om-oss story, which leaked
# operator typos and meta-instructions onto the public site.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_company_name_uses_swedish_business_type_mapping() -> None:
    """`electrician` + `Malmö` -> "Elektriker i Malmö", not the raw prompt."""
    name = _derive_company_name(
        business_type="electrician",
        location_hint="Malmö",
        language="sv",
    )
    assert name == "Elektriker i Malmö"


@pytest.mark.tooling
def test_ecommerce_company_name_uses_product_category_when_name_missing() -> None:
    """B106: e-commerce prompts should not fall back to plain "Webbshop"."""
    name = _derive_company_name(
        business_type="e-commerce",
        location_hint=None,
        services_mentioned=["keramik"],
        language="sv",
    )

    assert name == "Keramikbutik"
    assert name != "Webbshop"


@pytest.mark.tooling
def test_product_category_name_uses_last_word_for_multi_word_service() -> None:
    """B112: multi-word categories must not concat into a garbled stem.

    The previous helper joined every part of ``label.split()`` without a
    separator, so ``"handgjord keramik"`` rendered as
    ``"Handgjordkeramik"`` and ``_derive_company_name`` appended
    ``"butik"`` to produce ``"Handgjordkeramikbutik"``. The Swedish
    compound noun is ``"Keramikbutik"``; the helper now picks the
    trailing noun of the label so the suffix attaches to a single word.
    """
    from scripts.prompt_to_project_input import _product_category_name

    assert _product_category_name(["handgjord keramik"]) == "Keramik"
    assert _product_category_name(["ekologisk mat"]) == "Mat"
    assert _product_category_name(["unika handgjorda smycken"]) == "Smycken"


@pytest.mark.tooling
def test_product_category_name_preserves_single_word_categories() -> None:
    """Single-word categories must still produce the expected stem."""
    from scripts.prompt_to_project_input import _product_category_name

    assert _product_category_name(["keramik"]) == "Keramik"
    assert _product_category_name(["böcker"]) == "Böcker"


@pytest.mark.tooling
def test_ecommerce_company_name_produces_clean_compound_for_multi_word_brief() -> None:
    """B112 end-to-end: handgjord keramik -> Keramikbutik, inte Handgjordkeramikbutik."""
    name = _derive_company_name(
        business_type="e-commerce",
        location_hint=None,
        services_mentioned=["handgjord keramik"],
        language="sv",
    )

    assert name == "Keramikbutik"
    assert "Handgjordkeramik" not in name


@pytest.mark.tooling
def test_company_name_falls_back_when_brief_has_no_signals() -> None:
    """Empty brief -> safe placeholder; never the raw prompt."""
    name = _derive_company_name(
        business_type=None,
        location_hint=None,
        language="sv",
    )
    assert name == "Ny sajt"


@pytest.mark.tooling
def test_company_name_handles_location_only() -> None:
    name = _derive_company_name(
        business_type=None,
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Sajt i Stockholm"


@pytest.mark.tooling
def test_company_name_falls_back_for_unknown_business_type_slug() -> None:
    """Unknown English slug surfaces as a Swedish placeholder phrase.

    Demo-baseline-fix 1A-hotfix (B63): the previous fallback emitted
    "Sajt för <slug>", which rendered as "Sajt för thinly niche
    business" and read as broken placeholder copy. The hotfix fallback
    is the more natural "företag som arbetar med <slug>" reading so
    unknown briefModel slugs still surface as readable Swedish prose.
    """
    name = _derive_company_name(
        business_type="thinly-niche-business",
        location_hint="Lund",
        language="sv",
    )
    assert name.startswith("Företag som arbetar med thinly niche business")
    assert "Lund" in name
    assert "Sajt för" not in name, (
        "B63: pre-hotfix 'Sajt för X' fallback must not return."
    )


@pytest.mark.tooling
def test_story_never_uses_notes_for_planner() -> None:
    """B61: notes_for_planner is briefModel's English planner orientation
    and must never surface as customer-facing /om-oss copy.

    Pre-hotfix `_derive_story` returned `notes_for_planner` verbatim as
    the story. Verifierings-Scout 2026-05-15 caught that this leaked
    English meta instructions ("Likely a Swedish electrician website
    targeting Malmö; prompt is minimal...") onto every Swedish demo
    site. The hotfix ignores `notes_for_planner` entirely.
    """
    notes = (
        "Likely a Swedish electrician website targeting Malmö; prompt is "
        "minimal, so keep scope conservative and local."
    )
    story = _derive_story(
        business_type="electrician",
        location_hint="Malmö",
        notes_for_planner=notes,
        language="sv",
    )
    assert story != notes, (
        "B61: notes_for_planner must not be returned as story copy."
    )
    assert "Likely a Swedish" not in story, (
        "B61: English planner prose must not surface in /om-oss copy."
    )
    assert "scope conservative" not in story
    assert "elektriker" in story.lower()
    assert "Malmö" in story


@pytest.mark.tooling
def test_story_constructs_placeholder_when_notes_missing() -> None:
    """The Swedish story is built from businessType + location only.

    Demo-baseline-fix 1A-hotfix (B61): the second sentence must not
    contain the dev-jargon phrase "Justera Project Input"; rendered
    /om-oss copy is for end customers, not operators. B99 extends this
    to the old "Byt ut den här texten" placeholder instruction.
    """
    story = _derive_story(
        business_type="electrician",
        location_hint="Malmö",
        notes_for_planner=None,
        language="sv",
    )
    assert "elektriker" in story.lower()
    assert "Malmö" in story
    assert "Justera Project Input" not in story, (
        "B61: customer copy must not name the Project Input file."
    )
    assert "Byt ut" not in story


@pytest.mark.tooling
def test_story_uses_customer_safe_notes_for_planner() -> None:
    """B99: real-ish safe planner notes should beat generic fallback copy."""
    story = _derive_story(
        business_type="electrician",
        location_hint="Malmö",
        notes_for_planner="Lokal elektriker med fokus på tydlig kontakt.",
        language="sv",
    )
    assert story == "Lokal elektriker med fokus på tydlig kontakt."
    assert "Byt ut" not in story
    assert "Project Input" not in story


@pytest.mark.tooling
def test_story_discards_internal_notes_for_planner() -> None:
    """B61/B99: internal planner orientation is still not public copy."""
    story = _derive_story(
        business_type="electrician",
        location_hint="Malmö",
        notes_for_planner=(
            "Likely a Swedish electrician website targeting Malmö; prompt "
            "is minimal, so keep scope conservative and local."
        ),
        language="sv",
    )
    assert "Likely" not in story
    assert "prompt is minimal" not in story
    assert "Byt ut" not in story
    assert "elektriker" in story.lower()
    assert "Malmö" in story


# ---------------------------------------------------------------------------
# B128 (re-Verifierings-Scout 2026-05-19): operator-/planner-instructions
# that open with a Swedish/English build-imperative ("Bygg en liten
# e-handel ...", "Skapa en hemsida ...") used to slip past the B99
# blocklist because the tokens they contained ("e-handel", "keramik",
# "köpkonvertering") were not on the blocklist and none of the B99
# guard-strings (likely/prompt/site/byt ut/...) appeared. The result was
# a /om-oss page that read "Bygg en liten e-handel på svenska för
# försäljning av keramik med fokus på köpkonvertering." instead of public
# customer copy. The fix tightens `_customer_safe_planner_note` so a note
# that begins with a build-imperative is rejected outright.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_story_discards_swedish_build_imperative_planner_note() -> None:
    """B128: the exact keramik-leak observed in re-Verifierings-Scout
    2026-05-19 must not surface on /om-oss as customer copy."""
    leak = (
        "Bygg en liten e-handel på svenska för försäljning av keramik "
        "med fokus på köpkonvertering."
    )
    story = _derive_story(
        business_type="e-commerce",
        location_hint=None,
        notes_for_planner=leak,
        language="sv",
    )
    assert story != leak, (
        "B128: planner-imperativ släpptes igenom till /om-oss-copy."
    )
    assert "Bygg" not in story
    assert "köpkonvertering" not in story
    assert "på svenska" not in story
    assert "tydligt erbjudande" in story or "enkel kontaktväg" in story, (
        "B128: utan godkänd note ska _derive_story falla tillbaka till "
        "den neutrala publika copyn som B99 redan låser."
    )


@pytest.mark.tooling
@pytest.mark.parametrize(
    "leading_imperative",
    [
        "Bygg en hemsida för min butik.",
        "Skapa en stylig sida åt en kund.",
        "Gör en clean landing page med produkter.",
        "Generera en svensk företagswebb.",
        "Designa en e-handel med fokus på keramik.",
        "Lägg upp ett snyggt galleri.",
        "Sätt upp en webshop med checkout.",
        "Build a small e-commerce site for ceramics.",
        "Create a clean landing page with green tones.",
        "Make a two-page site that sells turtles.",
        "Set up a portfolio for a photographer.",
    ],
)
def test_customer_safe_planner_note_rejects_build_imperative(
    leading_imperative: str,
) -> None:
    """B128: every typical Swedish/English build-imperative form must
    be rejected by ``_customer_safe_planner_note``. Operator
    instructions never become public /om-oss copy.
    """
    from scripts.prompt_to_project_input import _customer_safe_planner_note

    assert _customer_safe_planner_note(leading_imperative) is None, (
        f"B128: imperativ {leading_imperative!r} släpptes igenom som "
        "publik /om-oss-copy."
    )


@pytest.mark.tooling
def test_customer_safe_planner_note_keeps_present_tense_business_copy() -> None:
    """B128 positive lock: a real customer-style 'about'-mening som råkar
    börja med samma stam (men i tredje person presens, t.ex.
    ``"Bygger på 25 års erfarenhet ..."``) ska fortfarande passera. Bara
    imperativ-formen ("Bygg ...") blockeras.
    """
    from scripts.prompt_to_project_input import _customer_safe_planner_note

    note = "Bygger på 25 års erfarenhet inom hantverk och keramik."
    accepted = _customer_safe_planner_note(note)
    assert accepted == note, (
        "B128 går för långt: third-person 'Bygger' (inte imperativ) "
        "blockerades trots att den är giltig kundvänd /om-oss-copy."
    )


@pytest.mark.tooling
def test_customer_safe_planner_note_blocks_konvertering_tokens() -> None:
    """B128: rena marketing-/operator-tokens (``konvertering``,
    ``köpkonvertering``, ``på svenska``, ``in english``) hör inte hemma
    i kundcopy på /om-oss även när satsen inte börjar med imperativ.
    """
    from scripts.prompt_to_project_input import _customer_safe_planner_note

    leak_konvertering = (
        "Liten studio med fokus på köpkonvertering och låg friktion."
    )
    leak_svenska = (
        "Skriv all kundkopia på svenska för en småskalig keramikstudio."
    )
    leak_in_english = (
        "Write the public copy in English for a niche ceramics shop."
    )

    assert _customer_safe_planner_note(leak_konvertering) is None
    assert _customer_safe_planner_note(leak_svenska) is None
    assert _customer_safe_planner_note(leak_in_english) is None


@pytest.mark.tooling
@pytest.mark.parametrize(
    "wrapped_imperative",
    [
        "-Bygg en sajt för keramik.",
        "- Bygg en sajt för keramik.",
        "* Bygg en webshop.",
        "**Bygg en hemsida för min butik**.",
        "1. Bygg en webshop.",
        "1) Bygg en webshop.",
        ">>> Skapa en webshop.",
        "  - Make a clean shop.",
        "* * * Build a small e-commerce site.",
        "123 Skapa en svensk företagswebb.",
    ],
)
def test_customer_safe_planner_note_rejects_imperative_with_leading_prefix(
    wrapped_imperative: str,
) -> None:
    """B128 hardening (post-Composer-2.5-review 2026-05-19): the
    pre-hotfix `_starts_with_planner_imperative` regex
    ``re.match(r"[a-zåäöéü]+", stripped)`` returned ``None`` whenever
    the first character was not a letter, so notes wrapped in markdown
    bold-markers, list dashes or list numerals slipped past the guard
    even though the build-imperative was sitting one character to the
    right of position 0. The hardening strips a single leading run of
    non-letter characters before the token match so the bypass is
    closed; this parametrised fixture covers the prefix shapes
    Composer-2.5 flagged in the read-only review.
    """
    from scripts.prompt_to_project_input import _customer_safe_planner_note

    assert _customer_safe_planner_note(wrapped_imperative) is None, (
        f"B128 hardening: leading-prefix imperative {wrapped_imperative!r} "
        "slipped past the planner-imperative guard."
    )


@pytest.mark.tooling
def test_customer_safe_planner_note_keeps_leading_numeral_when_no_imperative() -> None:
    """B128 hardening positive lock: stripping the leading non-letter
    prefix must not over-block legitimate customer copy that simply
    starts with a list numeral or marker followed by non-imperative
    text. The guard should only reject when the first letter-token
    after the prefix matches a known build-imperative.
    """
    from scripts.prompt_to_project_input import _customer_safe_planner_note

    legitimate = "1. Vi är ett litet bageri som drejar för hand."
    accepted = _customer_safe_planner_note(legitimate)
    assert accepted == legitimate, (
        "B128 hardening over-blocked: leading numeral + non-imperative "
        f"sentence rejected: {legitimate!r}"
    )


@pytest.mark.tooling
def test_b128_full_pipeline_blocks_keramik_planner_instruction() -> None:
    """End-to-end B128 lock for the exact 2026-05-19 keramik-prompt: the
    Project Input that lands on disk must not surface the operator
    instruction as `company.story` on /om-oss.
    """
    leak = (
        "Bygg en liten e-handel på svenska för försäljning av keramik "
        "med fokus på köpkonvertering."
    )
    brief = {
        "language": "sv",
        "businessTypeGuess": "e-commerce",
        "locationHint": None,
        "rawPrompt": "liten e-handel som säljer keramik",
        "tone": [],
        "conversionGoals": ["product_purchase"],
        "servicesMentioned": ["keramik"],
        "requestedCapabilities": [],
        "notesForPlanner": leak,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="keramik-shop-b128",
        scaffold_id="ecommerce-lite",
        variant_id="clean-store",
        original_prompt="liten e-handel som säljer keramik",
    )
    story = project_input["company"]["story"]
    for forbidden in (
        "Bygg",
        "på svenska",
        "köpkonvertering",
    ):
        assert forbidden not in story, (
            f"B128: planner-instruktion-token {forbidden!r} läckte till "
            f"company.story: {story!r}"
        )


@pytest.mark.tooling
def test_company_name_and_story_never_contain_raw_prompt(
    project_input_schema: dict,
) -> None:
    """The exact regression observed on the real prompt-run
    `enehmsida-som-s-ljer-b-t-661e23`: prompt typos and meta-instructions
    must not surface on the rendered H1 or `/om-oss` copy.
    """
    raw_prompt = "Enehmsida som säljer båtari skövde. 2 sidor"
    brief = {
        "language": "sv",
        "businessTypeGuess": "boat-dealer",
        "locationHint": "Skövde",
        "notesForPlanner": (
            "2-sidig svensk företagswebb för båtverksamhet i Skövde "
            "med fokus på köpkonvertering."
        ),
        "rawPrompt": raw_prompt,
        "tone": ["trustworthy"],
        "conversionGoals": ["purchase"],
        "servicesMentioned": ["båtförsäljning"],
        "requestedCapabilities": [],
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="boat-skovde-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt=raw_prompt,
    )
    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)

    name = project_input["company"]["name"]
    story = project_input["company"]["story"]
    for forbidden in ("Enehmsida", "båtari", "2 sidor"):
        assert forbidden not in name, (
            f"Raw prompt token {forbidden!r} leaked into company.name: {name!r}"
        )
        assert forbidden not in story, (
            f"Raw prompt token {forbidden!r} leaked into company.story: "
            f"{story!r}"
        )


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A (T3): service labels must preserve Swedish
# characters (å/ä/ö) so the rendered service grid reads naturally. The
# previous `_SLUG_CLEAN` substitution stripped Swedish letters from
# both slug and label, turning "färska ägg direkt från gården" into
# the unreadable label "F Rska Gg Direkt Fr N G Rden".
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_slugify_label_ascii_folds_swedish_chars() -> None:
    assert _slugify_label("färska ägg direkt från gården") == (
        "farska-agg-direkt-fran-garden"
    )
    assert _slugify_label("paneldragning") == "paneldragning"
    assert _slugify_label("Akut elservice!") == "akut-elservice"


@pytest.mark.tooling
def test_swedish_service_labels_preserve_case() -> None:
    brief = {
        "language": "sv",
        "businessTypeGuess": "egg-farm",
        "locationHint": "Småland",
        "rawPrompt": "Skapa en hemsida för en äggfarm",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [
            "färska ägg direkt från gården",
            "gårdsbutik",
            "lokal produktion",
        ],
        "requestedCapabilities": [],
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="egg-farm-abcdef",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Skapa en hemsida för en äggfarm",
    )

    labels = {svc["label"] for svc in project_input["services"]}
    assert "Färska ägg direkt från gården" in labels
    assert "Gårdsbutik" in labels
    assert "Lokal produktion" in labels

    slugs = {svc["id"] for svc in project_input["services"]}
    for slug in slugs:
        assert all(ord(c) < 128 for c in slug), (
            f"Slug {slug!r} contains non-ASCII; must ASCII-fold for safe "
            "use as React key / route segment."
        )
    assert "farska-agg-direkt-fran-garden" in slugs
    assert "gardsbutik" in slugs
    assert "lokal-produktion" in slugs


@pytest.mark.tooling
def test_service_slug_collisions_get_deterministic_suffixes() -> None:
    """B83: two distinct labels that normalize to the same slug should
    both survive instead of silently dropping the later service.
    """
    brief = {
        "language": "sv",
        "businessTypeGuess": "service-provider",
        "locationHint": "Malmö",
        "rawPrompt": "test",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": ["A+B", "A B", "A_B"],
        "requestedCapabilities": [],
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="collision-test",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="test",
    )
    service_ids = [service["id"] for service in project_input["services"]]
    assert service_ids[:3] == ["a-b", "a-b-2", "a-b-3"]


@pytest.mark.tooling
def test_slugify_site_id_ascii_folds_swedish_chars() -> None:
    """The siteId is operator-facing in URLs/paths. NFKD-folding before
    `_SLUG_CLEAN` means "elektriker i Malmö" reads as
    `elektriker-i-malmo-<tail>` instead of the pre-T3
    `elektriker-i-malm-<tail>` (with `ö` collapsed to a dash).
    """
    site_id = slugify_site_id("elektriker i Malmö", suffix="abcdef")
    assert site_id == "elektriker-i-malmo-abcdef"


@pytest.mark.tooling
def test_pointer_writes_use_atomic_replace(tmp_path: Path) -> None:
    """B60 fynd 3: pointer files must be written via tempfile + replace,
    never `Path.write_text` directly. Source-lock the helper names so a
    refactor cannot regress to non-atomic writes that leave readers
    observing half-written JSON.
    """
    helper_path = REPO_ROOT / "scripts" / "prompt_to_project_input.py"
    text = helper_path.read_text(encoding="utf-8")
    assert "_atomic_write_text" in text, (
        "scripts/prompt_to_project_input.py måste exponera "
        "_atomic_write_text-helpern (tempfile + os.replace) som används "
        "för pointer-filerna."
    )
    assert "os.replace(tmp_name, path)" in text, (
        "Pointer-uppdateringen måste gå via os.replace för att vara "
        "atomic; en framtida refactor får inte regressera till en "
        "vanlig Path.write_text på pointer-pathen."
    )
    assert "_atomic_write_text(current_project_input_path" in text, (
        "write_project_input måste använda _atomic_write_text för "
        "current pointer Project Input."
    )
    assert "_atomic_write_text(current_meta_path" in text, (
        "write_project_input måste använda _atomic_write_text för "
        "current pointer meta."
    )
    # Tempfile is empty after a successful write (the actual scratch dir
    # used by tests is `tmp_path`; functional verification happens via
    # test_generate_writes_project_input_and_meta which reads the
    # final pointer payload).
    assert tmp_path.is_dir()


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A-hotfix (B61): notes_for_planner is briefModel's
# internal English orientation for Phase 2 ("Likely a Swedish electrician
# website targeting Malmö; prompt is minimal..."). It must not surface
# anywhere on the rendered site (story, tagline, service summaries).
# Verifierings-Scout 2026-05-15 caught the 1A regression on all four
# demo prompts; the hotfix derives all three fields from brief signals
# only.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_tagline_never_uses_notes_for_planner() -> None:
    """B61: company.tagline must not contain briefModel's planner notes."""
    leak = (
        "Likely a Swedish electrician website targeting Malmö; prompt is "
        "minimal, so keep scope conservative and local."
    )
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "locationHint": "Malmö",
        "rawPrompt": "elektriker Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "notesForPlanner": leak,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="elektriker-malmo-leak",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="elektriker Malmö",
    )
    tagline = project_input["company"]["tagline"]
    assert "Likely a Swedish" not in tagline
    assert "scope conservative" not in tagline
    assert tagline != leak
    assert tagline == "Tydlig hjälp med elarbeten"


@pytest.mark.tooling
def test_derive_tagline_builds_from_business_type_and_location() -> None:
    """B103: tagline should add a concrete angle instead of repeating H1."""
    tagline = _derive_tagline(
        business_type="electrician",
        location_hint="Malmö",
        language="sv",
    )
    assert tagline == "Tydlig hjälp med elarbeten"
    assert tagline != "Lokal elektriker i Malmö"
    assert len(tagline) <= 140


@pytest.mark.tooling
def test_derive_tagline_booking_businesses_do_not_repeat_h1() -> None:
    """B103: short booking prompts need useful USP-style taglines."""
    hair = _derive_tagline(
        business_type="hair-salon",
        location_hint="Göteborg",
        language="sv",
    )
    naprapat = _derive_tagline(
        business_type="naprapat-clinic",
        location_hint="Stockholm",
        language="sv",
    )
    swedish_naprapat = _derive_tagline(
        business_type="naprapatklinik",
        location_hint="Stockholm",
        language="sv",
    )
    assert hair == "Klippning, färg och styling med enkel bokning"
    assert naprapat == "Behandling och rådgivning med enkel bokning"
    assert swedish_naprapat == "Behandling och rådgivning med enkel bokning"
    assert hair != "Lokal frisör i Göteborg"
    assert naprapat != "Lokal naprapatklinik i Stockholm"


@pytest.mark.tooling
def test_derive_tagline_falls_back_when_brief_is_empty() -> None:
    """Schema requires non-empty tagline; fallback must satisfy that."""
    tagline = _derive_tagline(
        business_type=None,
        location_hint=None,
        language="sv",
    )
    assert tagline == "Välkommen"
    assert len(tagline) <= 140
    assert "Likely" not in tagline
    assert "Project Input" not in tagline
    assert "taglinen" not in tagline


@pytest.mark.tooling
def test_service_summaries_do_not_leak_dev_jargon() -> None:
    """B61: rendered services grid is customer-facing copy.

    Pre-hotfix the placeholder summary read "kort beskrivning genererad
    från din prompt. Justera Project Input för att förbättra texten",
    which surfaced operator workflow on every Swedish demo site. The
    hotfix replaces the second sentence with a short customer call to
    action. The English variant is tested via the same forbidden-string
    check.
    """
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "locationHint": "Malmö",
        "rawPrompt": "elektriker Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": ["paneldragning", "laddbox-installation"],
        "requestedCapabilities": [],
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="elektriker-malmo-svc",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="elektriker Malmö",
    )
    forbidden = [
        "Justera Project Input",
        "placeholder generated from your prompt",
        "kort beskrivning genererad från din prompt",
        "Edit the Project Input",
    ]
    for service in project_input["services"]:
        summary = service["summary"]
        for needle in forbidden:
            assert needle not in summary, (
                f"B61: service summary leaked dev jargon {needle!r}: "
                f"{summary!r}"
            )


@pytest.mark.tooling
def test_placeholder_services_summary_is_customer_friendly() -> None:
    """When the brief has no services_mentioned the schema-required
    placeholder service must still pass the B61 forbidden-string check.
    """
    brief = {
        "language": "sv",
        "businessTypeGuess": None,
        "locationHint": None,
        "rawPrompt": "frisör Göteborg",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="empty-brief",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="frisör Göteborg",
    )
    summaries = [svc["summary"] for svc in project_input["services"]]
    assert summaries
    for summary in summaries:
        assert "Justera Project Input" not in summary
        assert "platshållare" not in summary, (
            "B61: customer copy must not call itself a platshållare."
        )
        assert "placeholder" not in summary.lower()


@pytest.mark.tooling
def test_service_summary_uses_business_specific_copy_for_empty_brief() -> None:
    """B105: no more public "Konsultation - kontakta oss..." filler."""
    services = _build_services([], "sv", business_type="electrician")

    assert services == [
        {
            "id": "elservice",
            "label": "Elservice",
            "summary": "Tydlig hjälp med elarbeten, felsökning och nästa steg.",
        }
    ]
    assert "kontakta oss för mer information" not in services[0]["summary"]


@pytest.mark.tooling
def test_service_summary_uses_business_specific_copy_for_stub_service() -> None:
    """B105: generic one-word brief services still get useful summaries."""
    services = _build_services(["Konsultation"], "sv", business_type="electrician")

    assert services[0]["label"] == "Konsultation"
    assert services[0]["summary"] == (
        "Tydlig hjälp med elarbeten, felsökning och nästa steg."
    )
    assert "kontakta oss för mer information" not in services[0]["summary"]


@pytest.mark.tooling
def test_full_pipeline_locks_no_planner_jargon_for_scout_prompt() -> None:
    """End-to-end B61 lock for the Verifierings-Scout 2026-05-15 case.

    Builds a Project Input from a typical Scout-style brief (electrician
    in Malmö with the exact `notesForPlanner` leak observed in the
    audit) and asserts that none of the three customer-facing copy
    surfaces (`company.story`, `company.tagline`, `services[].summary`)
    contain any of the forbidden strings.
    """
    leak = (
        "Likely a Swedish electrician website targeting Malmö; prompt is "
        "minimal, so keep scope conservative and local."
    )
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "locationHint": "Malmö",
        "rawPrompt": "elektriker Malmö",
        "tone": ["trustworthy"],
        "conversionGoals": ["call"],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "notesForPlanner": leak,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="elektriker-malmo-e2e",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="elektriker Malmö",
    )
    forbidden = (
        "Likely a Swedish",
        "Justera Project Input",
        "placeholder generated from your prompt",
        "scope conservative",
    )
    surfaces = [
        ("company.story", project_input["company"]["story"]),
        ("company.tagline", project_input["company"]["tagline"]),
    ]
    surfaces.extend(
        (f"services[{idx}].summary", svc["summary"])
        for idx, svc in enumerate(project_input["services"])
    )
    for label, text in surfaces:
        for needle in forbidden:
            assert needle not in text, (
                f"B61: forbidden string {needle!r} leaked into {label}: "
                f"{text!r}"
            )


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A-hotfix (B62) + Demo-baseline-fix 1C (B95):
# locationHint normalisation. After B95 every Nordic country name (in
# either Swedish or English form) is mapped to ``None`` so the
# placeholder falls back to ``city == country`` as a "country only"
# marker. Real city names are returned unchanged on both languages.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_normalize_location_hint_drops_english_country_names() -> None:
    """B95: English country names map to None on every language."""
    assert _normalize_location_hint("Sweden", "sv") is None
    assert _normalize_location_hint("sweden", "sv") is None
    assert _normalize_location_hint(" SWEDEN ", "sv") is None
    assert _normalize_location_hint("Sweden", "en") is None


@pytest.mark.tooling
def test_normalize_location_hint_drops_swedish_country_names() -> None:
    """B95: ``locationHint="Sverige"`` (no city) was the actual re-Scout
    finding on the e-commerce prompt; the helper now drops it just
    like the English variant."""
    assert _normalize_location_hint("Sverige", "sv") is None
    assert _normalize_location_hint("sverige", "en") is None
    assert _normalize_location_hint("  Sverige  ", "sv") is None


@pytest.mark.tooling
def test_normalize_location_hint_drops_other_nordic_country_names() -> None:
    """B95: covers the Nordic country names the helper actively knows
    about (Norway/Norge, Denmark/Danmark, Finland, Iceland/Island)."""
    for value in ("Norway", "Norge", "Denmark", "Danmark", "Finland", "Iceland", "Island"):
        assert _normalize_location_hint(value, "sv") is None, value
        assert _normalize_location_hint(value, "en") is None, value


@pytest.mark.tooling
def test_normalize_location_hint_preserves_real_city() -> None:
    """B95: real city names are returned unchanged on both languages."""
    assert _normalize_location_hint("Göteborg", "sv") == "Göteborg"
    assert _normalize_location_hint("Stockholm", "sv") == "Stockholm"
    assert _normalize_location_hint("Malmö", "en") == "Malmö"


@pytest.mark.tooling
def test_swedish_brief_with_country_location_uses_country_only_marker() -> None:
    """B95: ``locationHint="Sverige"`` + language=sv falls back to the
    country-only marker (``location.city == location.country``) so
    ``scripts/build_site.py:render_home`` can suppress the hero
    ortstag. Previously this case surfaced the country name as a
    rendered city on the e-commerce demo prompt."""
    brief = {
        "language": "sv",
        "businessTypeGuess": "hairdresser",
        "locationHint": "Sverige",
        "rawPrompt": "frisör i Sverige",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="frisor-sverige",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="frisör i Sverige",
    )
    assert project_input["location"]["city"] == "Sverige"
    assert project_input["location"]["country"] == "Sverige"
    assert project_input["location"]["city"] == project_input["location"]["country"]


@pytest.mark.tooling
def test_english_brief_with_country_location_uses_country_only_marker() -> None:
    """B95 (en variant): same marker shape on English builds."""
    brief = {
        "language": "en",
        "businessTypeGuess": "ecommerce-shop",
        "locationHint": "Sweden",
        "rawPrompt": "small ceramics e-commerce shop",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="ceramics-shop",
        scaffold_id="ecommerce-lite",
        variant_id="nordic-trust",
        original_prompt="small ceramics e-commerce shop",
    )
    assert project_input["location"]["city"] == "Sweden"
    assert project_input["location"]["country"] == "Sweden"
    assert project_input["location"]["city"] == project_input["location"]["country"]


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1C (B88): contact-placeholder dev jargon. Before
# the fix the default ``addressLines`` value was operator-facing dev
# jargon ("Adress saknas - uppdatera Project Input") that leaked
# verbatim into the public ``<address>`` tag on every generated
# /kontakt page. The fallback is now a brand-neutral phrase that
# reads acceptably to a real visitor; the operator can still override
# it via Project Input.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_placeholder_contact_address_has_no_dev_jargon_on_swedish_brief() -> None:
    """B88: the Swedish address placeholder must read as customer copy."""
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "rawPrompt": "elektriker Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="electrician-malmo",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="elektriker Malmö",
    )
    address_lines = project_input["contact"]["addressLines"]
    assert len(address_lines) == 1
    joined = " ".join(address_lines).lower()
    forbidden = (
        "adress saknas",
        "uppdatera project input",
        "project input",
        "placeholder",
        "address placeholder",
        "update project input",
    )
    for token in forbidden:
        assert token not in joined, (token, address_lines)
    assert address_lines == ["Adress lämnas på förfrågan"]


@pytest.mark.tooling
def test_placeholder_contact_address_has_no_dev_jargon_on_english_brief() -> None:
    """B88 (en variant): the English address placeholder must read as
    customer copy too."""
    brief = {
        "language": "en",
        "businessTypeGuess": "electrician",
        "rawPrompt": "electrician in Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="electrician-malmo-en",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="electrician in Malmö",
    )
    address_lines = project_input["contact"]["addressLines"]
    joined = " ".join(address_lines).lower()
    for token in ("placeholder", "update project input", "project input"):
        assert token not in joined, (token, address_lines)
    assert address_lines == ["Address available on request"]


@pytest.mark.tooling
def test_placeholder_contact_address_prefers_brief_value_over_fallback() -> None:
    """B88: when the brief actually carries a customer address the
    helper must keep that value verbatim and never substitute the
    neutral fallback phrase."""
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "rawPrompt": "Volt & Co, Storgatan 1",
        "companyName": "Volt & Co",
        "contactAddress": "Storgatan 1, 211 22 Malmö",
        "tone": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "requestedCapabilities": [],
        "locationHint": "Malmö",
        "notesForPlanner": None,
        "briefSource": "real",
    }
    project_input, _ = site_brief_to_project_input(
        brief,
        site_id="volt-co-address",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        original_prompt="Volt & Co, Storgatan 1",
    )
    assert project_input["contact"]["addressLines"] == [
        "Storgatan 1, 211 22 Malmö"
    ]


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A-hotfix (B63): _BUSINESS_TYPE_LABEL_SV must cover
# the hyphenated slugs briefModel actually returns ("e-commerce",
# "naprapath-clinic"), and the fallback for unknown slugs must read as
# Swedish prose, not the broken "Sajt för X" placeholder.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("e-commerce", "webbshop"),
        ("ecommerce", "webbshop"),
        ("ecommerce-shop", "webbshop"),
        ("ecommerce-store", "webbshop"),
        ("naprapath-clinic", "naprapatklinik"),
        ("naprapat-clinic", "naprapatklinik"),
        # B92 (2026-05-26): bare "naprapat" / "naprapath" slugs now map
        # to the sole-practitioner form, not the clinic form. The
        # explicit *-clinic variants (above) keep the clinic mapping.
        ("naprapat", "naprapat"),
        ("naprapath", "naprapat"),
        ("electrical-services", "elektriker"),
        ("plumbing-services", "rörmokare"),
        ("hair-salon", "frisör"),
        ("dental-clinic", "tandläkare"),
        ("photo-studio", "fotostudio"),
    ],
)
def test_business_type_map_covers_briefmodel_hyphenated_slugs(
    slug: str, expected: str
) -> None:
    """B63: every hyphenated slug Verifierings-Scout flagged maps to a
    real Swedish noun, not the fallback branch.
    """
    assert _company_business_label(slug, "sv") == expected


@pytest.mark.tooling
def test_unknown_business_type_uses_swedish_fallback_phrase() -> None:
    """B63: unknown slugs read as Swedish prose, not 'Sajt för X'."""
    label = _company_business_label("okänt-företag", "sv")
    assert label is not None
    assert label.startswith("företag som arbetar med ")
    assert "Sajt för" not in label
    assert "okänt företag" in label


@pytest.mark.tooling
def test_business_type_map_lookup_is_case_and_whitespace_safe() -> None:
    """Defensive: lookup strips and lowercases so briefModel quirks
    (`E-Commerce`, `  e-commerce  `) still hit the map."""
    assert _company_business_label("E-Commerce", "sv") == "webbshop"
    assert _company_business_label("  e-commerce  ", "sv") == "webbshop"


@pytest.mark.tooling
def test_company_name_for_e_commerce_brief_uses_swedish_label() -> None:
    """`businessTypeGuess="e-commerce"` -> H1 reads "Webbshop ..."."""
    name = _derive_company_name(
        business_type="e-commerce",
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Webbshop i Stockholm"


@pytest.mark.tooling
def test_company_name_for_naprapath_clinic_brief_uses_swedish_label() -> None:
    """`businessTypeGuess="naprapath-clinic"` -> H1 reads
    "Naprapatklinik ..." not "Sajt för naprapath clinic".
    """
    name = _derive_company_name(
        business_type="naprapath-clinic",
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Naprapatklinik i Stockholm"


# ---------------------------------------------------------------------------
# B92 — `naprapat` (sole practitioner) must NOT be over-adapted to
# "naprapatklinik" (clinic). The explicit *-clinic / *klinik slugs stay
# clinic-form so briefModel can express the distinction.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b92_bare_naprapat_slug_renders_sole_practitioner_h1() -> None:
    """B92: businessTypeGuess="naprapat" -> H1 reads "Naprapat i Stockholm"
    (sole practitioner). Previously over-adapted to "Naprapatklinik".
    """
    name = _derive_company_name(
        business_type="naprapat",
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Naprapat i Stockholm"


@pytest.mark.tooling
def test_b92_naprapath_english_slug_also_maps_to_sole_practitioner() -> None:
    """B92: English slug "naprapath" mirrors the bare "naprapat" mapping.
    Only the explicit *-clinic variants carry the clinic meaning.
    """
    name = _derive_company_name(
        business_type="naprapath",
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Naprapat i Stockholm"


@pytest.mark.tooling
def test_b92_explicit_clinic_variants_still_render_clinic_h1() -> None:
    """B92 scope-lock: every explicit clinic-flavoured naprapat slug
    must still render the clinic H1, so operators that intend the
    clinic form keep their existing output.
    """
    for slug in ("naprapat-clinic", "naprapath-clinic", "naprapatklinik"):
        name = _derive_company_name(
            business_type=slug,
            location_hint="Stockholm",
            language="sv",
        )
        assert name == "Naprapatklinik i Stockholm", (
            f"slug {slug!r} must still render the clinic-form H1"
        )


# ---------------------------------------------------------------------------
# B93 — common multi-word English business slugs that briefModel emits
# must map to a Swedish noun in `_BUSINESS_TYPE_LABEL_SV` instead of
# leaking through the "företag som arbetar med <slug>"-fallback.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("pet-grooming", "djursalong"),
        ("dog-grooming", "hundtrim"),
        ("veterinary-clinic", "veterinärklinik"),
        ("tattoo-studio", "tatuerare"),
        ("personal-trainer", "personlig tränare"),
        ("personal-training", "personlig tränare"),
        ("fitness-studio", "gym"),
        ("law-firm", "advokatbyrå"),
        ("real-estate-agent", "fastighetsmäklare"),
        ("cleaning-services", "städföretag"),
        ("auto-repair", "bilverkstad"),
        ("interior-designer", "inredare"),
        ("graphic-designer", "grafisk formgivare"),
        ("marketing-agency", "marknadsföringsbyrå"),
    ],
)
def test_b93_common_multi_word_english_slugs_map_to_swedish(
    slug: str, expected: str
) -> None:
    """B93: common briefModel multi-word slugs no longer leak through
    the "företag som arbetar med <slug>"-fallback. Each registered slug
    maps to a real Swedish noun that reads naturally in H1 copy.
    """
    assert _company_business_label(slug, "sv") == expected


@pytest.mark.tooling
def test_b93_pet_grooming_h1_no_longer_leaks_english_slug() -> None:
    """B93 integration: the reviewer's specific example. Before the fix,
    H1 read "Företag som arbetar med pet grooming i Stockholm" — English
    slug masquerading as Swedish copy. After fix, H1 reads "Djursalong i
    Stockholm".
    """
    name = _derive_company_name(
        business_type="pet-grooming",
        location_hint="Stockholm",
        language="sv",
    )
    assert name == "Djursalong i Stockholm"
    assert "pet grooming" not in name


@pytest.mark.tooling
def test_b93_unknown_swedish_slug_still_uses_swedish_fallback_phrase() -> None:
    """B93 scope-lock: only known English slugs got new mappings.
    Genuinely unknown slugs (Swedish or otherwise) still fall through
    to the "företag som arbetar med <slug>"-phrase so operators can
    spot un-mapped slugs in test output.
    """
    label = _company_business_label("okänt-företag", "sv")
    assert label is not None
    assert label.startswith("företag som arbetar med ")


# ---------------------------------------------------------------------------
# B91 — `_normalize_location_hint` translates confirmed English city
# exonyms to their Swedish endonym on Swedish builds, so a Swedish-
# tagged build does not render an English city name in the hero
# ortstag. English-tagged builds keep the English form unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("english", "swedish"),
    [
        ("Gothenburg", "Göteborg"),
        ("gothenburg", "Göteborg"),
        ("GOTHENBURG", "Göteborg"),
        ("Helsinki", "Helsingfors"),
        ("Copenhagen", "Köpenhamn"),
        ("  Gothenburg  ", "Göteborg"),
    ],
)
def test_b91_swedish_builds_translate_english_city_exonyms(
    english: str, swedish: str
) -> None:
    """B91: on language=sv, the English exonym for a Swedish/Nordic city
    is translated to the proper Swedish endonym. Case-insensitive and
    whitespace-tolerant lookup mirrors `_normalize_location_hint`'s
    existing country-name handling.
    """
    assert _normalize_location_hint(english, "sv") == swedish


@pytest.mark.tooling
def test_b91_english_builds_preserve_english_city_unchanged() -> None:
    """B91 scope-lock: language=en builds must NOT get the Swedish
    translation — the English city name is the correct render for an
    English-tagged site.
    """
    assert _normalize_location_hint("Gothenburg", "en") == "Gothenburg"
    assert _normalize_location_hint("Helsinki", "en") == "Helsinki"
    assert _normalize_location_hint("Copenhagen", "en") == "Copenhagen"


@pytest.mark.tooling
def test_b91_unknown_english_city_passes_through() -> None:
    """B91 scope-lock: the translation map is intentionally narrow.
    Unknown city names pass through unchanged on both languages so we
    do not invent translations the operator did not provide.
    """
    assert _normalize_location_hint("Stockholm", "sv") == "Stockholm"
    assert _normalize_location_hint("Boston", "sv") == "Boston"
    assert _normalize_location_hint("Malmoo", "sv") == "Malmoo"


# ---------------------------------------------------------------------------
# B90 — ENGLISH_HINTS no longer contains the single-letter "a"/"an"
# articles, so Swedish company names with single-letter tokens
# ("A & O El Malmö") no longer false-positive as English.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b90_single_letter_swedish_company_name_stays_sv() -> None:
    """B90: "A & O El Malmö" used to tokenise to a set containing "a",
    which matched ENGLISH_HINTS and made detect_language return "en".
    After the B90 fix (a/an removed from ENGLISH_HINTS), the å/ä/ö in
    "Malmö" carries the prompt back to "sv" via the cascade step 3.
    """
    from packages.generation.brief import detect_language

    assert detect_language("A & O El Malmö") == "sv"
    assert detect_language("A&O El Stockholm") == "sv"  # falls through to default
    assert detect_language("Skapa hemsida för A & O Bygg") == "sv"


@pytest.mark.tooling
def test_b90_english_prompts_without_a_an_still_detect_as_english() -> None:
    """B90 scope-lock: the remaining English stop-words in the set
    ("the", "and", "for", "create", "build", "website", etc.) still
    fire for genuine English prompts. The articles "a"/"an" were
    redundant given the other hints.
    """
    from packages.generation.brief import detect_language

    assert detect_language("Build a website for a clinic in Boston") == "en"
    assert detect_language("Create the page for my shop") == "en"
    assert detect_language("Make a site for our store") == "en"
