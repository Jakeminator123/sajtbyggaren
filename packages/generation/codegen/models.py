"""Pydantic types and resolver for codegenModel.

Sprint 3A locked the basic shape (CodegenFile + CodegenResult).
Sprint 3B-next (ADR 0017) extends:

- ``CodegenResult.usage`` records token usage from the real LLM call
  so build-result.json:modelUsage can aggregate brief + planning +
  codegen costs without a separate stub.
- ``CodegenLLMResponse`` is the *narrow* schema the real codegenModel
  call must return: rationale + risk-notes only. Sprint 3B-next does
  NOT let the LLM emit file content; the deterministic file list
  (routes / dossier mounts / starter patches) stays the source of
  truth so a hallucinating LLM cannot inject arbitrary files. Later
  sprints widen this contract once Quality Gate + Repair Pipeline
  have proven they catch LLM drift end-to-end.
- ``resolve_codegen_model`` mirrors ``resolve_brief_model`` /
  ``resolve_planning_model`` and reads the model id from
  ``governance/policies/llm-models.v1.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

CODEGEN_ROLE_ID = "codegenModel"
EXPECTED_PROVIDER = "openai"


CodegenFileSource = Literal[
    "codegen",
    "dossier-mount",
    "starter-patched",
    "scaffold",
]

CodegenFileRole = Literal[
    "page",
    "component",
    "config",
    "theme",
    "layout",
    "route",
]

CodegenSource = Literal[
    "deterministic-v1",
    "real",
    "mock-no-key",
    "mock-llm-error",
]


class CodegenFile(BaseModel):
    """One entry in CodegenResult.files.

    ``path`` is relative to the build target (the ``.generated/<siteId>/``
    or per-test ``tmp_path`` directory). ``source`` records who produced
    the file: ``codegen`` for codegenModel emissions, ``dossier-mount``
    for files copied from a Dossier's components/, ``starter-patched``
    for starter files modified after copy, and ``scaffold`` for scaffold-
    derived structural files. ``role`` records what kind of file it is.
    """

    path: str = Field(min_length=1)
    source: CodegenFileSource
    role: CodegenFileRole


class CodegenLLMResponse(BaseModel):
    """Narrow structured output schema the real codegenModel must return.

    Sprint 3B-next intentionally limits the LLM to commentary, NOT file
    content:

    - ``rationale``: one paragraph explaining the codegen strategy for
      this site (which routes prioritise conversion, why a Dossier is
      mounted on a particular page, etc.). Surfaces in
      ``build-result.json:codegen.rationale``.
    - ``riskNotes``: up to 3 risks the model identified that Quality
      Gate or Repair Pipeline should watch for. Empty list when none.

    File path / source / role decisions stay deterministic - the LLM
    cannot widen the manifest. ADR 0017 documents why: hallucinating
    extra files would bypass the route/Dossier policy that scaffold
    + plan already chose.
    """

    rationale: str = Field(
        description=(
            "One short paragraph explaining the codegen strategy for "
            "this site. Mention which conversion goals drove the route "
            "set and any Dossier-related copy choices."
        ),
    )
    riskNotes: list[str] = Field(
        default_factory=list,
        description=(
            "Up to 3 short risk callouts the operator should watch for "
            "(e.g. 'Hero relies on operator-supplied imagery'). 0-3 items."
        ),
        max_length=3,
    )


class CodegenUsage(BaseModel):
    """Token usage and cost stub mirroring build-result.json:modelUsage."""

    promptTokens: int = 0
    completionTokens: int = 0
    totalTokens: int = 0


class CodegenResult(BaseModel):
    """Aggregated output from codegenModel.

    ``source`` follows the same truth-field convention as briefSource
    and planSource: ``real`` (real LLM call succeeded), ``mock-no-key``
    (OPENAI_API_KEY missing), ``mock-llm-error`` (call raised), or
    ``deterministic-v1`` (Sprint 3A heritage; used when starter is
    explicitly out of real-codegen scope, e.g. non-marketing-base
    starters in Sprint 3B-next).

    ``riskNotes`` populates only on ``source="real"``; deterministic
    paths leave it empty.

    ``usage`` populates only on ``source="real"``; deterministic +
    mock paths leave it zeroed (a no-op cost record).
    """

    files: list[CodegenFile] = Field(default_factory=list)
    source: CodegenSource = "deterministic-v1"
    modelUsed: str = "deterministic"
    rationale: str = ""
    riskNotes: list[str] = Field(default_factory=list)
    usage: CodegenUsage = Field(default_factory=CodegenUsage)
    error: str | None = None


class CodegenModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json does not declare a usable codegenModel."""


def resolve_codegen_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for codegenModel in
    ``governance/policies/llm-models.v1.json``.

    Strict: raises ``CodegenModelResolutionError`` when the policy file
    is missing the role, the provider is not openai, or the model field
    is empty. Mirrors ``resolve_brief_model`` and ``resolve_planning_model``
    so all three model roles share the same contract surface.
    """
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise CodegenModelResolutionError(
            f"llm-models.v1.json missing at {path}"
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodegenModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != CODEGEN_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise CodegenModelResolutionError(
                f"codegenModel provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise CodegenModelResolutionError(
                "codegenModel role is missing a non-empty model value"
            )
        return model

    raise CodegenModelResolutionError(
        f"codegenModel role missing from {path.name}"
    )
