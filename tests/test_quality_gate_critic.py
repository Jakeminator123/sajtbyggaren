"""Tests for the kor-4a deterministic Quality Critic (critic v0).

Locks the five heuristics (generic_copy, thin_offer, placeholder_leakage,
missing_local_context, missing_cta), the warning-lane invariant (the critic
NEVER changes QualityResult.status), the documented score formula, the
trace-event shape, and the schema <-> Pydantic alignment for the new ``critic``
section. No LLM, no model role, no OpenAI call is involved.

Tests use ``tmp_path`` so they never touch the canonical ``data/runs/``
directory (per AGENTS.md Gotchas).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.quality_gate import (
    CriticIssue,
    CriticResult,
    append_critic_trace_event,
    run_deterministic_critic,
    run_quality_gate,
)
from packages.generation.quality_gate.critic import _SEVERITY_WEIGHT


def _issue_types(critic: CriticResult) -> set[str]:
    return {issue.type for issue in critic.issues}


def _write_page(target: Path, route: str, body: str = "<div>x</div>") -> None:
    if route == "/":
        path = target / "app" / "page.tsx"
    else:
        path = target / "app" / route.lstrip("/") / "page.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"export default function Page() {{ return ({body}); }}",
        encoding="utf-8",
    )


# A blueprint that passes every heuristic: grounded hero copy with a CTA, three
# real services, no placeholder contact, the town named, a location hint.
def _clean_blueprint() -> tuple[dict, dict]:
    generation_package = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker i Malmö när jobbet måste bli rätt",
                "subheadline": "Vi hjälper föreningar och mindre företag i Malmö.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "Elinstallationer", "summary": "Säkra installationer."},
                {"title": "Felsökning", "summary": "Snabb felsökning på plats."},
                {"title": "Laddboxar", "summary": "Montering av laddbox hemma."},
            ],
        }
    }
    site_brief = {
        "locationHint": "Malmö",
        "contactPhone": "040-123 45 67",
        "conversion": {"primaryCta": "Be om offert"},
    }
    return generation_package, site_brief


# ---------------------------------------------------------------------------
# Clean blueprint -> no issues, perfect score
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_clean_blueprint_has_no_issues_and_full_score():
    gp, brief = _clean_blueprint()
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert critic.issues == []
    assert critic.score == 100
    assert critic.source == "deterministic-v0"


# ---------------------------------------------------------------------------
# directive_leak (defense in depth on #322; single shared signal w/ planning)
# ---------------------------------------------------------------------------


# Canonical briefModel leaks (mirror tests/test_planning_blueprint.py): an
# imperative lead verb, a modal + copy-craft-verb construction, a craft term.
_DIRECTIVE_LEAK_STRINGS: tuple[str, ...] = (
    "Lyft Kafé Solrosen som det självklara fikastället i Göteborg",
    "Göteborg som lokal förankring bör synas tydligt i copy och kontaktsektion",
    "Framhäv hantverket i varje rad subheadline",
)


@pytest.mark.tooling
def test_directive_leak_flags_instruction_text_in_content_blocks():
    """A directive-shaped string that reached contentBlocks is reported as a
    high-severity directive_leak finding (it must never render as customer copy).
    """
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Lyft Kafé Solrosen som det självklara fikastället",
            },
        }
    }
    critic = run_deterministic_critic(generation_package=gp, site_brief={})
    assert "directive_leak" in _issue_types(critic)
    leak = next(i for i in critic.issues if i.type == "directive_leak")
    assert leak.severity == "high"
    assert leak.target == "home.hero"


@pytest.mark.tooling
def test_clean_blueprint_has_no_directive_leak():
    """Honest, customer-ready copy never trips the directive_leak heuristic."""
    gp, brief = _clean_blueprint()
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "directive_leak" not in _issue_types(critic)


@pytest.mark.tooling
def test_directive_leak_critic_shares_single_signal_with_planning():
    """Lockstep: the critic and the planning prevention stage use the SAME
    detection function (one source in packages/shared/directive_signal.py), so
    prevention and detection can never drift. Also checks the canonical leak
    strings + honest baseline copy.
    """
    from packages.generation.planning.blueprint import _looks_like_directive
    from packages.shared.directive_signal import looks_like_directive

    # Same object = single source of truth (not two mirrored copies).
    assert _looks_like_directive is looks_like_directive
    for text in _DIRECTIVE_LEAK_STRINGS:
        assert looks_like_directive(text) is True
    for honest in (
        "Trygg elektriker i Malmö när elen måste bli rätt.",
        "Be om offert",
    ):
        assert looks_like_directive(honest) is False


# ---------------------------------------------------------------------------
# generic_copy
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generic_blueprint_flags_generic_copy():
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Välkommen till vår hemsida",
                "subheadline": "Vi erbjuder tjänster av högsta kvalitet i Malmö.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    brief = {"locationHint": "Malmö"}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "generic_copy" in _issue_types(critic)
    generic = [i for i in critic.issues if i.type == "generic_copy"]
    assert all(i.target == "home.hero" for i in generic)
    assert all(i.severity == "medium" for i in generic)
    assert all(i.repairHint for i in generic)


# ---------------------------------------------------------------------------
# thin_offer
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_single_service_flags_thin_offer():
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Snabb elektriker i Malmö",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "Elinstallationer", "summary": "Säkra installationer."},
            ],
        }
    }
    brief = {"locationHint": "Malmö"}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "thin_offer" in _issue_types(critic)
    thin = [i for i in critic.issues if i.type == "thin_offer"]
    assert thin[0].target == "services.service-list"
    assert thin[0].severity == "medium"


@pytest.mark.tooling
def test_three_services_do_not_flag_thin_offer():
    gp, brief = _clean_blueprint()
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "thin_offer" not in _issue_types(critic)


# ---------------------------------------------------------------------------
# placeholder_leakage
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_placeholder_contact_in_blueprint_flags_leakage():
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker i Malmö",
                "subheadline": "Ring oss på 08-000 00 00 idag.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    brief = {"locationHint": "Malmö"}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "placeholder_leakage" in _issue_types(critic)
    leak = [i for i in critic.issues if i.type == "placeholder_leakage"]
    assert all(i.severity == "high" for i in leak)
    assert leak[0].target == "home.hero"


@pytest.mark.tooling
def test_placeholder_contact_in_brief_fields_flags_leakage():
    gp, _ = _clean_blueprint()
    brief = {
        "locationHint": "Malmö",
        "contactEmail": "kontakt@example.se",
        "contactAddress": "Adress lämnas på förfrågan",
    }
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    leak = [i for i in critic.issues if i.type == "placeholder_leakage"]
    assert leak, "brief-level placeholder contact must be flagged"
    assert all(i.target == "global.contact" for i in leak)


# ---------------------------------------------------------------------------
# missing_local_context
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_location_hint_without_town_mention_flags_missing_local_context():
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker när jobbet måste bli rätt",
                "subheadline": "Vi hjälper föreningar och mindre företag.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    brief = {"locationHint": "Malmö", "conversion": {"primaryCta": "Be om offert"}}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "missing_local_context" in _issue_types(critic)
    local = [i for i in critic.issues if i.type == "missing_local_context"]
    assert local[0].severity == "low"
    assert local[0].target == "home.hero"


@pytest.mark.tooling
def test_town_mentioned_does_not_flag_missing_local_context():
    gp, brief = _clean_blueprint()
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "missing_local_context" not in _issue_types(critic)


@pytest.mark.tooling
def test_no_location_hint_does_not_flag_missing_local_context():
    gp = {
        "contentBlocks": {
            "home.hero": {"headline": "Snabb elektriker", "primaryCta": "Be om offert"},
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    critic = run_deterministic_critic(generation_package=gp, site_brief={})
    assert "missing_local_context" not in _issue_types(critic)


# ---------------------------------------------------------------------------
# missing_cta
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hero_without_cta_flags_missing_cta():
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker i Malmö",
                "subheadline": "Vi hjälper föreningar och mindre företag i Malmö.",
            },
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    brief = {"locationHint": "Malmö"}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "missing_cta" in _issue_types(critic)
    cta = [i for i in critic.issues if i.type == "missing_cta"]
    assert cta[0].severity == "high"


@pytest.mark.tooling
def test_brief_conversion_cta_satisfies_missing_cta():
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker i Malmö",
                "subheadline": "Vi hjälper föreningar och mindre företag i Malmö.",
            },
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    brief = {"locationHint": "Malmö", "conversion": {"primaryCta": "Be om offert"}}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert "missing_cta" not in _issue_types(critic)


# ---------------------------------------------------------------------------
# Generated-files scan (optional target_dir)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generated_files_scan_flags_placeholder_leakage(tmp_path):
    """With no blueprint copy but a placeholder contact rendered into the
    generated page, the optional file scan still catches the leak."""
    _write_page(
        tmp_path,
        "/",
        body='<a href="mailto:kontakt@example.se">Maila oss</a>',
    )
    gp = {
        "contentBlocks": {
            "home.hero": {"headline": "Trygg elektriker i Malmö", "primaryCta": "Be om offert"},
            "services.service-list": [
                {"title": "A", "summary": "x"},
                {"title": "B", "summary": "y"},
                {"title": "C", "summary": "z"},
            ],
        }
    }
    brief = {"locationHint": "Malmö"}
    critic = run_deterministic_critic(
        generation_package=gp, site_brief=brief, target_dir=tmp_path
    )
    leak = [i for i in critic.issues if i.type == "placeholder_leakage"]
    assert leak, "example.se in a generated page must be flagged"
    assert all(i.target.endswith(".page") for i in leak)


# ---------------------------------------------------------------------------
# Score formula
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_score_formula_is_weighted_by_severity():
    """score = max(0, 100 - sum(weight(severity)))."""
    assert _SEVERITY_WEIGHT == {"high": 20, "medium": 10, "low": 5}
    issues = [
        CriticIssue(
            severity="high",
            type="placeholder_leakage",
            target="home.hero",
            message="m",
            repairHint="h",
        ),
        CriticIssue(
            severity="medium",
            type="generic_copy",
            target="home.hero",
            message="m",
            repairHint="h",
        ),
        CriticIssue(
            severity="low",
            type="missing_local_context",
            target="home.hero",
            message="m",
            repairHint="h",
        ),
    ]
    result = CriticResult(score=max(0, 100 - (20 + 10 + 5)), issues=issues)
    assert result.score == 65


@pytest.mark.tooling
def test_score_floored_at_zero():
    gp = {
        "contentBlocks": {
            # generic + placeholder + thin + missing cta + missing local
            "home.hero": {
                "headline": "Välkommen till vår hemsida",
                "subheadline": "Ring oss på 08-000 00 00.",
            },
            "services.service-list": [{"title": "A", "summary": "x"}],
        }
    }
    brief = {"locationHint": "Göteborg"}
    critic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    assert critic.score >= 0
    assert len(critic.issues) >= 4


# ---------------------------------------------------------------------------
# Warning lane: critic never changes QualityResult.status
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_quality_gate_without_blueprint_leaves_critic_none(tmp_path):
    _write_page(tmp_path, "/")
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    assert result.critic is None
    assert result.status == "ok"
    # The legacy callers (Repair Pipeline) must keep the unchanged shape.
    payload = result.model_dump()
    assert payload["critic"] is None


@pytest.mark.tooling
def test_run_quality_gate_with_blueprint_attaches_critic_without_changing_status(tmp_path):
    _write_page(tmp_path, "/")
    gp = {
        "contentBlocks": {
            "home.hero": {"headline": "Välkommen till vår hemsida"},
            "services.service-list": [{"title": "A", "summary": "x"}],
        }
    }
    brief = {"locationHint": "Malmö"}
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
    )
    # critic is populated and reports issues...
    assert isinstance(result.critic, CriticResult)
    assert result.critic.issues
    # ...but status stays exactly what the blocking/warning checks decided.
    assert result.status == "ok"


@pytest.mark.tooling
def test_critic_does_not_appear_in_checks_list(tmp_path):
    """The critic is its own section, never a sixth/seventh CheckResult."""
    _write_page(tmp_path, "/")
    gp, brief = _clean_blueprint()
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
    )
    assert len(result.checks) == 7  # +internal-link-scan (ADR 0060 Slice B)
    assert all(c.name != "critic" for c in result.checks)


# ---------------------------------------------------------------------------
# Trace logging
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_critic_appends_warning_event_to_trace(tmp_path):
    gp = {
        "contentBlocks": {
            "home.hero": {"headline": "Välkommen till vår hemsida"},
            "services.service-list": [{"title": "A", "summary": "x"}],
        }
    }
    brief = {"locationHint": "Malmö"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # Pre-seed an existing trace line; the critic event must be appended, not
    # overwrite the run's trace.
    trace_path = run_dir / "trace.ndjson"
    trace_path.write_text(
        json.dumps({"runId": "r1", "event": "build.started"}) + "\n",
        encoding="utf-8",
    )
    run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
        run_dir=run_dir,
        run_id="r1",
    )
    lines = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines[0]["event"] == "build.started"
    critic_events = [line for line in lines if line["event"] == "critic.evaluated"]
    assert len(critic_events) == 1
    event = critic_events[0]
    assert event["status"] == "warning"
    assert event["runId"] == "r1"
    assert event["phase"] == "build"
    assert event["payloadPath"] == "quality-result.json"


@pytest.mark.tooling
def test_append_critic_trace_event_creates_file_when_missing(tmp_path):
    critic = CriticResult(score=100, issues=[])
    run_dir = tmp_path / "fresh"
    append_critic_trace_event(run_dir, "r2", critic)
    trace_path = run_dir / "trace.ndjson"
    assert trace_path.exists()
    record = json.loads(trace_path.read_text(encoding="utf-8").strip())
    assert record["event"] == "critic.evaluated"
    assert record["status"] == "warning"


@pytest.mark.tooling
def test_no_run_dir_means_no_trace_side_effect(tmp_path):
    gp, brief = _clean_blueprint()
    # No run_dir -> no trace file anywhere.
    run_quality_gate(
        target_dir=tmp_path,
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
    )
    assert list(tmp_path.rglob("trace.ndjson")) == []


# ---------------------------------------------------------------------------
# No LLM / OpenAI imports anywhere in the critic module
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_critic_module_makes_no_llm_calls():
    """kor-4a is deterministic: the critic module must not IMPORT openai,
    httpx or any model-role plumbing. Locks the no-LLM contract by scanning
    the module's import lines (docstrings may still reference kor-4b's
    verifierModel / briefModel by name - that is documentation, not a call).
    """
    import inspect

    from packages.generation.quality_gate import critic as critic_module

    forbidden = ("openai", "httpx", "anthropic", "requests")
    import_lines = [
        line.strip()
        for line in inspect.getsource(critic_module).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    leaked = [
        line
        for line in import_lines
        for bad in forbidden
        if bad in line
    ]
    assert not leaked, (
        f"critic module must stay deterministic; forbidden imports: {leaked}."
    )


# ---------------------------------------------------------------------------
# Schema <-> Pydantic alignment for the new critic section
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_critic_result_round_trips_and_validates():
    """A QualityResult carrying a critic must validate against the schema."""
    from packages.generation.artifacts import validate_quality_result

    gp = {
        "contentBlocks": {
            "home.hero": {"headline": "Välkommen till vår hemsida"},
            "services.service-list": [{"title": "A", "summary": "x"}],
        }
    }
    brief = {"locationHint": "Malmö"}
    result = run_quality_gate(
        target_dir=Path("/this/path/does/not/exist"),
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
    )
    payload = result.model_dump()
    assert payload["critic"]["source"] == "deterministic-v0"
    validate_quality_result(payload)  # raises on drift


def _critic_schema() -> dict:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "governance"
        / "schemas"
        / "quality-result.schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


@pytest.mark.governance
def test_critic_issue_schema_matches_pydantic_fields():
    schema = _critic_schema()
    schema_props = set(schema["$defs"]["criticIssue"]["properties"].keys())
    pydantic_fields = set(CriticIssue.model_fields.keys())
    assert schema_props == pydantic_fields, (
        f"criticIssue schema {schema_props} vs Pydantic "
        f"{pydantic_fields} drifted; bump both together."
    )


@pytest.mark.governance
def test_critic_section_schema_matches_pydantic_fields():
    schema = _critic_schema()
    schema_props = set(schema["properties"]["critic"]["properties"].keys())
    pydantic_fields = set(CriticResult.model_fields.keys())
    assert schema_props == pydantic_fields, (
        f"critic schema {schema_props} vs Pydantic "
        f"{pydantic_fields} drifted; bump both together."
    )
