"""ADR 0065 - answerModel: the conductor's answer/reasoning Model Role.

Locks the three guarantees that make a follow-up answer feel natural AND stay
honest (closing the #363 "unregistered LLM call" gap):

(a) the conductor's chat answer is driven by the REGISTERED answerModel role -
    the prompt-route helpers route their LLM call through chatWithAnswerModel,
    which threads the role's params via the same readRoleModelParams plumbing as
    every other role (proved at the policy + source-lock level);
(b) without OPENAI_API_KEY the answer falls back to the deterministic #363
    report.py line (no-key parity preserved verbatim in route.ts);
(c) the deterministic floor NEVER emits a success line when the bridge did not
    apply a VISIBLE change (bridge.applied=false / previewShouldRefresh=false) -
    the anti-"fake Klart!" guard from SOUL.md honesty + ADR 0062 rails.

report.py is a pure function exercised directly; the TS wiring is a source-lock
in the established apps/viewser style (tests/test_viewser_*).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.orchestration.openclaw import build_followup_report
from packages.policies.llm_model_params import resolve_role_params
from tests.support.viewser import VIEWSER_DIR

REPO_ROOT = Path(__file__).resolve().parents[1]
LLM_MODELS = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

# Visible-success phrases the deterministic floor must NEVER emit on a turn that
# did not visibly apply (the anti-fake-success guard, ADR 0062 / SOUL.md).
_SUCCESS_PHRASES = ("byggde en ny version", "previewen visar ändringen")


def _read_viewser(rel: str) -> str:
    return (VIEWSER_DIR / rel).read_text(encoding="utf-8")


def _edit_decision(edit_kind: str = "visual_style") -> dict:
    """A minimal patch_plan_request decision payload (router editKind only)."""
    return {"action": "patch_plan_request", "router": {"editKind": edit_kind}}


# ---------------------------------------------------------------------------
# STEP 2: answerModel is a registered Model Role (not a roleless LLM call).
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_answer_model_is_registered_in_policy():
    """llm-models.v1.json must register answerModel with the ADR 0065 params."""
    data = json.loads(LLM_MODELS.read_text(encoding="utf-8"))
    role = next((r for r in data["roles"] if r["id"] == "answerModel"), None)
    assert role is not None, "llm-models.v1.json must register answerModel (ADR 0065)"
    assert role["model"] == "gpt-5.5"
    assert role["provider"] == "openai"
    assert role["reasoningEffort"] == "low"
    assert role["maxOutputTokens"] == 16000


@pytest.mark.governance
def test_answer_model_belongs_to_exactly_one_shared_group():
    """Every role must sit in exactly one sharedModelGroup (cross-policy lock)."""
    data = json.loads(LLM_MODELS.read_text(encoding="utf-8"))
    groups = [
        g["groupId"] for g in data["sharedModelGroups"] if "answerModel" in g["roles"]
    ]
    assert groups == ["smallReasoning"], (
        "answerModel must belong to exactly one sharedModelGroup (smallReasoning), "
        f"got {groups}"
    )


@pytest.mark.governance
def test_answer_model_resolves_via_shared_reader():
    """The same plumbing the TS readRoleModelParams mirrors must resolve it."""
    params = resolve_role_params("answerModel")
    assert params.model == "gpt-5.5"
    assert params.reasoning_effort == "low"
    assert params.max_output_tokens == 16000


# ---------------------------------------------------------------------------
# STEP 4 (b positive): the floor DOES report a visible apply (grounded).
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_floor_reports_version_only_on_visible_apply():
    report = build_followup_report(
        _edit_decision("visual_style"),
        {
            "applied": True,
            "previewShouldRefresh": True,
            "chain": {"stage": "built", "version": 2, "changedRoutes": ["/"]},
        },
    )
    assert "Jag uppfattar" in report  # "okej, du menar nog X"
    assert "byggde en ny version" in report and "v2" in report


# ---------------------------------------------------------------------------
# STEP 4 (c): anti-"fake Klart!" - never a success line without a visible apply.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("edit_kind", "bridge"),
    [
        (
            "visual_style",
            {
                "applied": False,
                "previewShouldRefresh": False,
                "status": "plan_empty",
                "chain": {"stage": "plan_empty"},
            },
        ),
        (
            # An unowned editKind (ADR 0062 §4) - the honest unsupported no-op.
            "route_add",
            {
                "applied": False,
                "previewShouldRefresh": False,
                "status": "route_add_unsupported",
                "chain": {"stage": "route_add_unsupported"},
            },
        ),
    ],
)
def test_floor_no_op_is_honest_and_never_a_success(edit_kind, bridge):
    report = build_followup_report(_edit_decision(edit_kind), bridge)
    assert "Jag uppfattar" in report  # states what was understood
    assert "likadan ut" in report  # site unchanged
    for phrase in _SUCCESS_PHRASES:
        assert phrase not in report, f"floor faked a success line: {phrase!r}"


@pytest.mark.tooling
def test_floor_mount_only_never_claims_a_visible_change():
    """applied=true but previewShouldRefresh=false -> 'registrerade' + 'syns
    inte', never a visible-success claim (mount without visible effect)."""
    report = build_followup_report(
        _edit_decision("section_add"),
        {
            "applied": True,
            "previewShouldRefresh": False,
            "chain": {"stage": "built", "version": 4},
        },
    )
    assert "registrerade" in report and "syns inte" in report
    assert "previewen visar ändringen" not in report
    assert "byggde en ny version" not in report


@pytest.mark.tooling
def test_floor_answer_only_never_claims_a_change():
    report = build_followup_report(
        {"action": "answer_only", "conversation": {"conversationKind": "question"}},
        {
            "applied": False,
            "previewShouldRefresh": False,
            "status": "no_build_needed",
            "chain": None,
        },
    )
    assert "rör inte sajten" in report
    assert "ny version" not in report


# ---------------------------------------------------------------------------
# STEP 4 (a) + (b): the TS wiring routes the answer through the registered role
# and preserves the deterministic report.py fallback when there is no key.
# ---------------------------------------------------------------------------


@pytest.mark.source_lock
def test_openai_ts_exposes_registered_answer_model_seam():
    src = _read_viewser("lib/openai.ts")
    assert 'ANSWER_MODEL_ROLE_ID = "answerModel"' in src, (
        "openai.ts must register the answerModel role id (ADR 0065)"
    )
    assert "export async function chatWithAnswerModel" in src
    assert "roleId: ANSWER_MODEL_ROLE_ID" in src, (
        "chatWithAnswerModel must thread the registered roleId so the call "
        "resolves answerModel's params via readRoleModelParams"
    )
    # The generic helper stays exported for the out-of-scope callers
    # (hosted-answer-only.ts, app/api/chat/route.ts) - backwards compatible.
    assert "export async function chatWithOpenAi" in src


@pytest.mark.source_lock
def test_prompt_route_answers_through_answer_model():
    """(a) all three conductor chat helpers drive the answer via the registered
    answerModel role, never a roleless chatWithOpenAi."""
    src = _read_viewser("app/api/prompt/route.ts")
    assert "import { chatWithAnswerModel" in src
    assert src.count("chatWithAnswerModel(") >= 3, (
        "the three conductor helpers (conversation/applied/outcome) must each "
        "route their LLM call through the registered answerModel role"
    )
    assert "chatWithOpenAi(" not in src, (
        "the prompt route's conductor answer must not bypass the registered "
        "answerModel role with a roleless chatWithOpenAi call"
    )


@pytest.mark.source_lock
def test_prompt_route_preserves_deterministic_report_no_key_fallback():
    """(b) no-key parity: the deterministic report.py line stays the answerText
    fallback on both the applied-edit and the legacy/no-op return paths."""
    src = _read_viewser("app/api/prompt/route.ts")
    assert "applyResult.report" in src
    assert "applyResult?.report" in src
