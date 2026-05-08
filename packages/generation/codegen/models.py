"""Pydantic types for codegenModel v1 output.

Locked by ADR 0015 so later sprints can swap the deterministic body for
real LLM calls without breaking Quality Gate or Repair Pipeline callers.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
    the file: ``codegen`` for codegenModel v1 emissions, ``dossier-mount``
    for files copied from a Dossier's components/, ``starter-patched``
    for starter files modified after copy, and ``scaffold`` for scaffold-
    derived structural files. ``role`` records what kind of file it is.
    """

    path: str = Field(min_length=1)
    source: CodegenFileSource
    role: CodegenFileRole


class CodegenResult(BaseModel):
    """Aggregated output from codegenModel v1.

    ``source`` follows the same truth-field convention as briefSource
    and planSource: ``deterministic-v1`` (Sprint 3A v1 placeholder),
    ``real`` (when the real codegenModel runs), ``mock-no-key``
    (OPENAI_API_KEY missing) or ``mock-llm-error`` (call raised).
    """

    files: list[CodegenFile] = Field(default_factory=list)
    source: CodegenSource = "deterministic-v1"
    modelUsed: str = "deterministic"
    rationale: str = ""
    error: str | None = None
