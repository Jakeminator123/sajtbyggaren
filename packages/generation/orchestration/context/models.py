"""Pydantic types for the read-only Context Assembler (KÖR-7a).

These types back the result the assembler returns for a single
``contextLevel`` (the level the deterministic router, KÖR-6a, set). The
assembler fetches *lagom* much context per question, with a hard character
budget per level and anti-bloat suppression of files the previous version
already showed (docs/heavy-llm-flow/02 §4).

Nothing here is a new canonical artefakt: the assembler never persists a
result of its own. ``ContextLevel`` is intentionally re-used from the
sibling router module so the two halves of the orchestration layer share a
single closed enum instead of duplicating it (builder-profil §3: do not
duplicate a canonical type).

Read-only contract: every value below describes *what was read*; there is
no field that records a write, a build, a preview start or a created run,
because the assembler does none of those.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..router.models import ContextLevel

__all__ = [
    "AssembledContext",
    "ContextLevel",
    "ManifestEntry",
    "PriorContext",
    "ReferencePermission",
    "SelectedFile",
]


class PriorContext(BaseModel):
    """Anti-bloat signal: what the previous version already showed the model.

    ``knownFiles`` maps a generated-files-relative path to the sha256 hex of
    the content that version carried. The assembler uses it to *suppress*
    redundant context (sajtmaskins anti-bloat-trick, 02 §4):

    - ``manifest`` suppresses any path already present in ``knownFiles`` (the
      model has seen that the file exists).
    - ``selected_files`` suppresses a file only when its path *and* its
      content digest match - a changed file at a known path is still
      returned, because its content is new.

    An empty digest string means "path known, digest unknown" and suppresses
    by path only.
    """

    knownFiles: dict[str, str] = Field(default_factory=dict)


class ReferencePermission(BaseModel):
    """Permission gate for the ``external_reference`` level (the only tool call).

    The assembler never reaches the network itself. ``external_reference``
    requires an explicit ``allow=True`` grant *and* a caller-supplied fetch
    tool; without the grant the assembler returns an empty, gated result and
    never invokes the fetcher (docs/heavy-llm-flow/02 §4 + kor-7a step 3).
    """

    allow: bool = False
    reason: str = ""


class ManifestEntry(BaseModel):
    """One file in a ``manifest`` listing - path + byte size, no content."""

    path: str
    bytes: int


class SelectedFile(BaseModel):
    """One file in a ``selected_files`` result - path, size, digest, content.

    ``content`` may be clipped to keep the level within its character budget;
    ``truncated`` records whether that happened for this specific file.
    """

    path: str
    bytes: int
    sha256: str
    content: str
    truncated: bool = False


class AssembledContext(BaseModel):
    """The envelope every level returns.

    ``payload`` carries *only* what the level requires (kor-7a step 1) and is
    the thing a caller would hand to the model; ``charCount`` measures that
    payload and is guaranteed ``<= charBudget``. ``suppressed`` lists files
    omitted by anti-bloat, ``dropped`` lists content omitted to fit the
    budget, and the two ``permission*`` flags are only meaningful for
    ``external_reference``.

    The model is never written to disk - it is returned to the caller (the
    router / a future patch-planner slice) exactly like the router's
    decision is.
    """

    contextLevel: ContextLevel
    siteId: str | None = None
    runId: str | None = None
    charBudget: int = 0
    charCount: int = 0
    truncated: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    suppressed: list[str] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    permissionRequired: bool = False
    permissionGranted: bool = False
