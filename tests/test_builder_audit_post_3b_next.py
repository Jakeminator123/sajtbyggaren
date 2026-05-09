"""Post-3B-next reviewer audit regression tests.

A reviewer round on commit 6cf255c flagged four legitimate bugs:

- B29 (8/10): scripts/build_site.py renderers index Project Input fields
  the schema marked optional (services[].summary, company.tagline/story,
  location.serviceAreas, contact.*). Schema and builder were out of sync.
- B30 (8/10): renderers interpolated raw customer text into JSX with no
  escaping. ``<``, ``{``, ``}`` and similar characters in customer-
  supplied strings produced invalid TSX that ``next build`` would reject.
- B31 (5/10): ``write_phase1_understand`` called
  ``dossier_path.relative_to(REPO_ROOT)`` directly which raises
  ValueError when the operator points ``--dossier`` at a path outside
  the repo. ``_to_repo_relative`` already had the safe fallback.
- B32 (3/10): ``run_npm`` timeout-handling tested ``isinstance(exc.stdout,
  bytes)`` and silently dropped ``exc.stderr`` when ``exc.stdout`` was
  ``None``. Operators lost the only diagnostic the timeout produced.

These tests lock the fixes from the audit-cleanup commit so a future
refactor cannot quietly bring the bugs back.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"


# ---------------------------------------------------------------------------
# B32 - run_npm timeout output preserves stderr even when stdout is None
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_coerce_subprocess_text_handles_all_three_types() -> None:
    """The helper must turn None / bytes / str into a plain string so
    callers cannot accidentally drop one of the streams.
    """
    from scripts.build_site import _coerce_subprocess_text

    assert _coerce_subprocess_text(None) == ""
    assert _coerce_subprocess_text(b"hello\xe2\x98\x83") == "hello☃"
    assert _coerce_subprocess_text("plain text") == "plain text"


@pytest.mark.tooling
def test_run_npm_timeout_preserves_stderr_when_stdout_is_none(
    monkeypatch, tmp_path
) -> None:
    """B32: stdout=None + stderr="<error log>" must surface stderr in
    the ``run_npm`` return tuple. The previous implementation only
    decoded one stream and dropped the other when stdout was None.
    """
    from scripts import build_site

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["npm", "install"],
            timeout=300.0,
            output=None,
            stderr="ECONNREFUSED while reaching registry.npmjs.org",
        )

    monkeypatch.setattr(build_site.subprocess, "run", _raise_timeout)
    monkeypatch.setattr(build_site.shutil, "which", lambda _name: "/usr/bin/npm")

    ok, _elapsed, message = build_site.run_npm(
        ["npm", "install"], cwd=tmp_path, timeout=300.0
    )
    assert ok is False
    assert "ECONNREFUSED" in message, (
        "stderr must appear in the timeout diagnostic; "
        f"got message={message!r}"
    )


@pytest.mark.tooling
def test_run_npm_timeout_preserves_stderr_with_bytes_stream(
    monkeypatch, tmp_path
) -> None:
    """B32 variant: bytes streams must round-trip through utf-8 decode
    so a partially-buffered binary log still shows up.
    """
    from scripts import build_site

    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["npm", "install"],
            timeout=300.0,
            output=None,
            stderr=b"npm warn deprecated foo@1.0.0\nnpm err! tarball corrupted",
        )

    monkeypatch.setattr(build_site.subprocess, "run", _raise_timeout)
    monkeypatch.setattr(build_site.shutil, "which", lambda _name: "/usr/bin/npm")

    ok, _elapsed, message = build_site.run_npm(
        ["npm", "install"], cwd=tmp_path, timeout=300.0
    )
    assert ok is False
    assert "tarball corrupted" in message


# ---------------------------------------------------------------------------
# B31 - write_phase1_understand handles external dossier paths
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_to_repo_relative_handles_external_path(tmp_path: Path) -> None:
    """B31: paths outside REPO_ROOT must fall back to absolute POSIX
    string instead of raising ValueError.
    """
    from scripts.build_site import _to_repo_relative

    external = tmp_path / "ad-hoc.project-input.json"
    external.write_text("{}", encoding="utf-8")
    rel = _to_repo_relative(external)
    assert rel.endswith("ad-hoc.project-input.json")
    assert "\\" not in rel  # POSIX form, even on Windows


@pytest.mark.tooling
def test_write_phase1_understand_does_not_raise_on_external_path() -> None:
    """B31 source-level lock: write_phase1_understand must call
    ``_to_repo_relative`` on dossier_path, not ``relative_to(REPO_ROOT)``
    directly. Without the helper, a ``--dossier`` path outside the repo
    crashes the whole build with ValueError before Quality Gate can
    surface a structured failure.
    """
    import inspect

    from scripts import build_site

    source = inspect.getsource(build_site.write_phase1_understand)
    assert "_to_repo_relative(dossier_path)" in source, (
        "write_phase1_understand must call _to_repo_relative on the "
        "dossier path so external paths fall back gracefully (B31)."
    )
    assert "dossier_path.relative_to(REPO_ROOT)" not in source, (
        "Direct relative_to call reintroduces B31 - external dossier "
        "paths will crash with ValueError. Use _to_repo_relative."
    )


# ---------------------------------------------------------------------------
# B29 - project-input schema matches builder-required fields
# ---------------------------------------------------------------------------


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.governance
def test_company_required_includes_tagline_and_story() -> None:
    """B29: render_home renders ``company.tagline`` and render_about
    renders ``company.story`` as direct TSX paragraphs. Both must be
    required by the schema; otherwise a schema-valid input crashes with
    KeyError during build.
    """
    schema = _load_schema()
    company_required = schema["properties"]["company"]["required"]
    assert "tagline" in company_required
    assert "story" in company_required


@pytest.mark.governance
def test_location_required_includes_service_areas() -> None:
    """B29: render_about renders ``location.serviceAreas`` as comma-
    joined text. Must be required.
    """
    schema = _load_schema()
    location_required = schema["properties"]["location"]["required"]
    assert "serviceAreas" in location_required


@pytest.mark.governance
def test_services_item_requires_summary() -> None:
    """B29: render_home and render_services render ``svc.summary``.
    Must be required on each service item.
    """
    schema = _load_schema()
    item = schema["properties"]["services"]["items"]
    assert "summary" in item["required"]


@pytest.mark.governance
def test_contact_requires_all_four_fields() -> None:
    """B29: render_contact reads every field on contact directly
    (phone, email, addressLines, openingHours). All four must be
    required.
    """
    schema = _load_schema()
    contact_required = schema["properties"]["contact"]["required"]
    for field in ("phone", "email", "addressLines", "openingHours"):
        assert field in contact_required, (
            f"contact.{field} is dereferenced unconditionally by "
            f"render_contact; the schema must require it."
        )


@pytest.mark.governance
def test_schema_rejects_payload_missing_company_tagline() -> None:
    """B29 negative: a payload that satisfies the OLD permissive schema
    (company.required = [name, businessType] only) must now fail
    validation against the tightened schema. Locks the regression in
    the validator path, not just the policy text.
    """
    schema = _load_schema()
    payload = {
        "siteId": "minimal",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Test",
            "businessType": "test",
            # tagline + story missing intentionally
        },
        "location": {"city": "x", "country": "y", "serviceAreas": ["z"]},
        "services": [{"id": "s", "label": "S", "summary": "summary"}],
        "tone": {},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46",
            "email": "x@y.z",
            "addressLines": ["a"],
            "openingHours": "9-17",
        },
        "selectedDossiers": [],
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    paths = {"/".join(str(p) for p in e.path) for e in errors}
    assert any("company" in p for p in paths) or any(
        "tagline" in e.message or "story" in e.message for e in errors
    ), (
        "Schema must reject company-without-tagline-or-story payloads "
        "after B29 cleanup; got errors at paths " + repr(paths)
    )


# ---------------------------------------------------------------------------
# B30 - renderers JSX-escape customer text
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_jsx_safe_string_wraps_text_as_jsx_expression() -> None:
    """B30 unit: the helper must emit ``{"<text>"}`` form so JSX-special
    characters become valid JS string-literal content.
    """
    from scripts.build_site import _jsx_safe_string

    assert _jsx_safe_string("plain") == '{"plain"}'
    # < and > would break JSX-text parsing; { and } would be treated as
    # JSX expressions.
    assert _jsx_safe_string("a<b{c}") == '{"a<b{c}"}'
    # quotes round-trip via JSON-encoding (escaped inside the string).
    assert _jsx_safe_string('quoted"value') == '{"quoted\\"value"}'
    # Non-ASCII (Swedish) preserved literally because ensure_ascii=False.
    assert _jsx_safe_string("hejsa å ä ö") == '{"hejsa å ä ö"}'


@pytest.mark.tooling
def test_member_initials_handles_single_and_multi_word_names() -> None:
    """B30 unit: the initials helper must not index out-of-range when a
    member only has one name. The earlier inline expression
    ``name.split()[-1][:1]`` would fail or give wrong output for those.
    """
    from scripts.build_site import _member_initials

    assert _member_initials("Anders Holm") == "AH"
    assert _member_initials("Anders") == "A"
    assert _member_initials("Anders Bertil Holm") == "AH"
    assert _member_initials("") == ""


@pytest.mark.tooling
def test_render_home_jsx_escapes_special_characters() -> None:
    """B30 integration: a customer name with ``<`` and ``{`` must produce
    valid TSX (i.e. those characters appear inside a JSX expression,
    not as raw JSX text).
    """
    from scripts.build_site import render_home

    dossier = {
        "company": {
            "name": "<Studio> {Curly}",
            "tagline": "Tagline with \"quotes\"",
            "businessType": "test",
            "story": "Story",
        },
        "location": {
            "city": "Test City",
            "country": "SE",
            "serviceAreas": ["Area"],
        },
        "services": [
            {
                "id": "svc",
                "label": "Service A",
                "summary": "Summary 10 < 20",
            }
        ],
        "trustSignals": ["Trust > Doubt"],
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "x@y.z",
            "addressLines": ["Line 1"],
            "openingHours": "Mon-Fri",
        },
    }
    output = render_home(dossier, dossier_routes=["/"])

    # B30 negative smells: each pattern is a literal substring that
    # would ONLY appear in the output if customer text was interpolated
    # raw (i.e. without _jsx_safe_string wrapping). When the helper is
    # used, the value lives inside {"..."} JSON encoding so these
    # specific tag-text-tag triples never form. Substring-search is
    # safe here because the JSON-encoded form ALWAYS starts with a
    # double-quote right after the {, breaking the patterns below.
    forbidden_smells = [
        ">{Curly}",  # raw { in JSX text after closing >
        "><Studio>",  # raw < in JSX text after closing >
    ]
    for smell in forbidden_smells:
        assert smell not in output, (
            f"render_home leaked raw JSX-special characters: "
            f"{smell!r} appears in output - B30 regression."
        )

    # Positive smell: customer text appears wrapped via _jsx_safe_string.
    assert '{"<Studio> {Curly}"}' in output
    assert '{"Summary 10 < 20"}' in output


@pytest.mark.tooling
def test_render_contact_jsx_escapes_phone_and_email() -> None:
    """B30 integration: contact rendering must wrap phone/email through
    _jsx_safe_string both as text and as href.
    """
    from scripts.build_site import render_contact

    dossier = {
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": 'op"erator@example.com',  # unrealistic but exercises escaping
            "addressLines": ["Line <one>"],
            "openingHours": "Mon-Fri 9-17",
        },
    }
    output = render_contact(dossier)

    # phone / email / addressLines / openingHours all dynamic -> all wrapped.
    assert "{\"+46 70 123 45 67\"}" in output
    assert '{"Line <one>"}' in output
    assert '{"Mon-Fri 9-17"}' in output
    # The email must be wrapped both as href ("mailto:..." form) and as
    # link text - the JSON-encoded representation contains the escaped
    # double-quote.
    assert '{"mailto:op\\"erator@example.com"}' in output
    assert '{"op\\"erator@example.com"}' in output


@pytest.mark.tooling
def test_renderers_use_jsx_safe_string_for_customer_text() -> None:
    """B30 source-level lock: every renderer that interpolates customer
    text must call _jsx_safe_string. A refactor that quietly drops the
    helper from one of them re-opens B30 silently.

    ``render_layout`` was missed in the original B30 cleanup - it
    composes header + footer from company.name, company.tagline,
    contact.* and addressLines but kept raw f-string interpolation.
    Adding it to the list catches that gap and prevents the next
    renderer from sneaking in the same way.
    """
    import inspect

    from scripts import build_site

    for fn_name in (
        "render_layout",
        "render_home",
        "render_services",
        "render_about",
        "render_contact",
    ):
        fn = getattr(build_site, fn_name)
        source = inspect.getsource(fn)
        assert "_jsx_safe_string(" in source, (
            f"{fn_name} does not call _jsx_safe_string. Customer text "
            f"must be JSX-escaped or B30 regresses."
        )


@pytest.mark.tooling
def test_render_layout_jsx_escapes_customer_text() -> None:
    """B30 follow-up: render_layout was missed in the first cleanup -
    it interpolated customer data directly via raw f-strings into the
    header (logo + brand name) and footer (brand, tagline, address,
    phone, email, copyright row). This test renders a layout with
    JSX-special characters in those fields and verifies they all reach
    the output via {"..."}-form rather than as raw JSX text.
    """
    from scripts.build_site import render_layout

    dossier = {
        "company": {
            "name": '<Studio> {Curly}',
            "tagline": 'Hand & "Quote"',
            "businessType": "test",
            "story": "ok",
        },
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": 'op"er@example.com',
            "addressLines": ["Line <one>", "Line {two}"],
            "openingHours": "Mon-Fri",
        },
        "location": {
            "city": "X",
            "country": "SE",
            "serviceAreas": ["A"],
        },
    }
    output = render_layout(dossier, dossier_routes=["/", "/kontakt"])

    # Customer text appears via _jsx_safe_string wrapping.
    assert '{"<Studio> {Curly}"}' in output, (
        "render_layout must wrap company.name through _jsx_safe_string; "
        "raw <Studio> would break JSX parsing."
    )
    assert '{"Hand & \\"Quote\\""}' in output, (
        "render_layout must wrap company.tagline through "
        "_jsx_safe_string so the literal double quote does not close "
        "the surrounding JSX attribute or text."
    )
    assert '{"+46 70 123 45 67"}' in output
    assert '{"Line <one>, Line {two}"}' in output, (
        "render_layout must wrap the joined address line through "
        "_jsx_safe_string; raw < and { would break JSX text parsing."
    )

    # Negative smell - none of the JSX-special characters should appear
    # as raw inline JSX text. The double-quote-wrapped form prefixes the
    # value with a JSON quote, so these patterns can only appear if the
    # wrapping was bypassed.
    forbidden_smells = [
        ">{Curly}",  # raw { in JSX text after >
        "><Studio>",  # raw < in JSX text after >
        '<Studio> {Curly}<',  # raw company.name as plain text
    ]
    for smell in forbidden_smells:
        assert smell not in output, (
            f"render_layout leaked raw JSX-special characters: "
            f"{smell!r} appears in output - B30 regression."
        )


@pytest.mark.tooling
def test_render_layout_metadata_uses_js_string_literal() -> None:
    """B30 follow-up: the metadata block in layout.tsx is JS-object
    syntax, not JSX. The earlier ``"{title}".replace('"', '\\\\"')``
    approach only escaped double quotes; backslash, newline or other
    control characters could still produce an invalid JS string. Force
    the metadata path through ``_js_string_literal`` (json.dumps) which
    handles every special character.
    """
    from scripts.build_site import render_layout

    dossier = {
        "company": {
            "name": 'Studio with "quotes" and \\backslash',
            "tagline": "Line one\nline two",
            "businessType": "test",
            "story": "ok",
        },
        "contact": {
            "phone": "+46",
            "email": "x@y.z",
            "addressLines": ["A"],
            "openingHours": "h",
        },
        "location": {"city": "x", "country": "y", "serviceAreas": ["z"]},
    }
    output = render_layout(dossier, dossier_routes=["/", "/kontakt"])

    # The metadata block expects a JSON-encoded string literal (with
    # quotes already attached). title_line is the FULL line including
    # surrounding indentation.
    assert (
        '  title: "Studio with \\"quotes\\" and \\\\backslash",\n'
        in output
    ), "render_layout metadata.title must use _js_string_literal so backslash + quote survive."
    assert (
        '  description: "Line one\\nline two",\n' in output
    ), "render_layout metadata.description must use _js_string_literal so newline becomes \\n."


@pytest.mark.tooling
def test_render_layout_does_not_use_legacy_replace_quote_only_escape() -> None:
    """Source-level lock: render_layout must not regress to the manual
    ``.replace('"', '\\\\"')`` escape that only protected double quotes.
    The new path runs through ``_js_string_literal`` which uses
    ``json.dumps`` to cover every special character.
    """
    import inspect

    from scripts import build_site

    source = inspect.getsource(build_site.render_layout)
    assert '.replace(\'"\', \'\\\\"\')' not in source, (
        "render_layout still uses the legacy `.replace('\"', '\\\\\"')` "
        "manual escape. Switch to `_js_string_literal(...)` which "
        "handles backslash, newline, control characters, etc."
    )
    assert "_js_string_literal(" in source, (
        "render_layout must call _js_string_literal for the metadata "
        "title/description lines (B30 follow-up)."
    )
