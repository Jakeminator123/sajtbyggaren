"""Locks for the KÖR-6a routerDecision wiring in /api/prompt (Fas 1, skiva 1a).

Proves the contract the Viewser operator UI relies on:

  1. ``scripts/classify_message.py`` (the bridge the route shells out to) emits
     a RouterDecision that is schema-valid against
     governance/schemas/router-decision.schema.json. This is exactly the JSON
     ``apps/viewser/lib/router-classify-runner.ts`` parses and ``/api/prompt``
     attaches to its response — so the /api/prompt response carries a
     schema-valid routerDecision.
  2. ``answer_only`` / ``plan_only`` messages never request a build: the router
     reports ``buildRequirement`` in {none, plan_only} and
     ``shouldStartPreview=false`` (still starts no build, by contract).
  3. The bridge + CLI use the DETERMINISTIC ``classify_message`` only (no LLM
     fallback, no model role, no per-prompt cost).
  4. ``/api/prompt`` exposes routerDecision as READ-ONLY metadata: it never
     feeds the value into the build/preview path and keeps the
     assertLocalhost + isHostedVercelRuntime guards.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "router-decision.schema.json"
CLI_PATH = REPO_ROOT / "scripts" / "classify_message.py"
ROUTE_PATH = REPO_ROOT / "apps" / "viewser" / "app" / "api" / "prompt" / "route.ts"
BRIDGE_PATH = REPO_ROOT / "apps" / "viewser" / "lib" / "router-classify-runner.ts"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _run_cli(message: str, *, site_id: str | None = None) -> dict:
    args = [sys.executable, str(CLI_PATH)]
    if site_id:
        args += ["--site-id", site_id]
    args += ["--", message]
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"classify_message.py failed: {result.stderr}"
    return json.loads(result.stdout.strip())


# ---------------------------------------------------------------------------
# 1. The bridge CLI emits a schema-valid RouterDecision (= what /api/prompt attaches)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    "message",
    [
        "vad är klockan?",
        "lägg en klocka i andra sektionen till vänster",
        "vilka klockor finns att tillgå?",
        "samma klocka som på aftonbladet.se",
        "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna",
        "Skapa en hemsida för en elektriker i Malmö.",
    ],
)
def test_classify_cli_emits_schema_valid_router_decision(message: str) -> None:
    payload = _run_cli(message)
    jsonschema.Draft202012Validator(_schema()).validate(payload)
    # The few fields the operator UI branches on must be present + typed.
    assert isinstance(payload["messageKind"], str)
    assert isinstance(payload["buildRequirement"], str)
    assert isinstance(payload["requiresClarification"], bool)
    assert isinstance(payload["subtasks"], list)


# ---------------------------------------------------------------------------
# 2. answer_only / plan_only still start no build (router never actuates them)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_answer_only_never_requests_a_build() -> None:
    payload = _run_cli("vad är klockan?")
    assert payload["messageKind"] == "answer_only"
    assert payload["buildRequirement"] == "none"
    assert payload["shouldStartPreview"] is False


@pytest.mark.tooling
def test_plan_only_reference_never_requests_a_build() -> None:
    payload = _run_cli("samma klocka som på aftonbladet.se")
    assert payload["buildRequirement"] == "plan_only"
    assert payload["shouldStartPreview"] is False


@pytest.mark.tooling
@pytest.mark.parametrize(
    "message",
    [
        "vad är klockan?",  # answer_only / none
        "vilka klockor finns att tillgå?",  # component_discovery / none
        "samma klocka som på aftonbladet.se",  # reference_analysis / plan_only
    ],
)
def test_non_actuating_kinds_keep_shouldstartpreview_false(message: str) -> None:
    payload = _run_cli(message)
    assert payload["buildRequirement"] in {"none", "plan_only"}
    assert payload["shouldStartPreview"] is False


# ---------------------------------------------------------------------------
# 3. Deterministic only — no LLM fallback, no model role
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_cli_uses_deterministic_classify_only() -> None:
    src = CLI_PATH.read_text(encoding="utf-8")
    assert "classify_message(" in src, "CLI must call the deterministic classify_message."
    # The CLI must not CALL the LLM fallback (the docstring may name it to
    # explain that it is deliberately avoided — so match the call form only).
    assert "classify_message_with_llm_fallback(" not in src, (
        "skiva 1a must use the deterministic classify_message, not the LLM "
        "fallback (no model role, no per-prompt OPENAI_API_KEY cost)."
    )


@pytest.mark.tooling
def test_bridge_shells_out_to_cli_and_degrades_to_null() -> None:
    src = BRIDGE_PATH.read_text(encoding="utf-8")
    assert "classify_message.py" in src, "bridge must spawn the Python CLI."
    assert "return null" in src, (
        "bridge must degrade to null on any failure so /api/prompt's build flow "
        "is never broken by this read-only metadata step."
    )


# ---------------------------------------------------------------------------
# 4. /api/prompt exposes routerDecision as read-only metadata (does not gate build)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_route_attaches_router_decision_to_response() -> None:
    src = ROUTE_PATH.read_text(encoding="utf-8")
    assert 'from "@/lib/router-classify-runner"' in src
    assert "classifyMessage(" in src
    assert "routerDecision" in src, "the response must carry routerDecision."


@pytest.mark.tooling
def test_route_does_not_let_router_decision_gate_the_build() -> None:
    """routerDecision is read-only: the build call must be unchanged and the
    decision value must never be passed into runBuild / runPromptToProjectInput."""
    src = ROUTE_PATH.read_text(encoding="utf-8")
    # The build is still driven only by the deterministic helper output.
    assert "await runBuild(helper.siteId, helper.dossierPath)" in src, (
        "build behaviour must stay EXACTLY as before — routerDecision may not "
        "change how the site is built."
    )
    # The router decision must not be threaded into the build/Phase-1 calls.
    assert "runBuild(helper.siteId, helper.dossierPath, " not in src
    # The router decision is only resolved AFTER the build (await comes after the
    # runBuild call), proving it cannot gate whether/how the build runs.
    build_idx = src.index("await runBuild(helper.siteId, helper.dossierPath)")
    resolve_idx = src.index("await routerDecisionPromise")
    assert build_idx < resolve_idx, (
        "routerDecision must be resolved after the build (read-only metadata), "
        "never used to decide whether to build."
    )


@pytest.mark.tooling
def test_route_keeps_localhost_and_hosted_runtime_guards() -> None:
    src = ROUTE_PATH.read_text(encoding="utf-8")
    assert "assertLocalhost(request)" in src
    assert "isHostedVercelRuntime()" in src
