"""Typade modeller för Discovery Resolver.

Speglar JSON-schemas under ``governance/schemas/discovery-*.schema.json``.
Modellerna är medvetet lätta (TypedDict / dataclass) snarare än Pydantic
eftersom resolvern bygger dict-payloads som passerar jsonschema-validering
direkt — Pydantic skulle bara duplicera schemavalideringen.

Domäntermer som registreras i ``governance/policies/naming-dictionary.v1.json``:

- ``Discovery Payload`` — input shape från Viewser-wizarden.
- ``Discovery Decision`` — resolverns spårbara output med ``fieldSources``
  och ``fallbackWarnings``.
- ``Field Source`` — strängenum som beskriver var ett Project Input-fält
  kom från (wizard, scrape, brief, taxonomy, default, operator, pinned).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

FieldSourceLiteral = Literal[
    "wizard",
    "scrape",
    "brief",
    "taxonomy",
    "default",
    "operator",
    "pinned",
]
"""Tillåtna värden i ``DiscoveryDecision.fieldSources``-mappen."""

SelectionSource = Literal[
    "wizard",
    "taxonomy",
    "brief",
    "default",
    "fallback",
]
"""Toppnivåkälla för scaffold/variant-beslutet i ``DiscoveryDecision``."""

SupportStatus = Literal["active", "fallback", "planned", "disabled"]
"""``supportStatus`` på en taxonomy-kategori."""

DEFAULT_TAXONOMY_CATEGORY_ID = "other"
"""Fallback-id när payloaden saknar siteType eller alla värden är okända."""


class DiscoveryPayload(TypedDict, total=False):
    """Speglar ``governance/schemas/discovery-payload.schema.json``.

    Backend tolererar okända toppnycklar (frontend wizard utvecklas i
    discreta spår), så bara de fält Discovery Resolver konsumerar är
    typade. ``schemaVersion`` är ``int`` istället för ``Literal[1]`` så
    framtida bumpar inte triggar typningsfel; resolvern validerar mot
    ``_SCHEMA_VERSION`` runtime.
    """

    schemaVersion: int
    rawPrompt: str
    contentBranch: str
    scaffoldHint: str
    answers: dict[str, Any]


@dataclass(slots=True)
class FieldSource:
    """En post i ``DiscoveryDecision.fieldSources``.

    Bara ``path`` + ``source`` är obligatoriska; ``value`` är en
    operatörsläsbar repr av vad som vann (max 200 tecken i resolvern) som
    Backoffice kan visa utan att läsa hela Project Input-trädet. Resolvern
    serialiserar sedan till en enkel ``dict[path, source]`` så schemat
    håller sig tunt.
    """

    path: str
    source: FieldSourceLiteral
    value: str | None = None


@dataclass(slots=True)
class FallbackWarning:
    """Maskinläsbar varning för planned/fallback/disabled mappningar.

    ``code`` är enum:en ur ``discovery-decision.schema.json``;
    ``message`` är operator-vänlig prosa; övriga fält är kontextberoende
    pekare till entiteten som triggade varningen.
    """

    code: Literal[
        "category-unknown",
        "category-planned",
        "category-fallback",
        "category-disabled",
        "scaffold-runtime-missing",
        "variant-missing",
        "starter-mapping-missing",
        "capability-unknown",
        "capability-gap",
        "dossier-missing",
    ]
    message: str
    categoryId: str | None = None
    scaffoldId: str | None = None
    capabilityId: str | None = None
    dossierId: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Serialise till dict utan ``None``-fält så schema-validation passerar."""
        payload: dict[str, str] = {"code": self.code, "message": self.message}
        if self.categoryId is not None:
            payload["categoryId"] = self.categoryId
        if self.scaffoldId is not None:
            payload["scaffoldId"] = self.scaffoldId
        if self.capabilityId is not None:
            payload["capabilityId"] = self.capabilityId
        if self.dossierId is not None:
            payload["dossierId"] = self.dossierId
        return payload


@dataclass(slots=True)
class DiscoveryDecision:
    """Strukturerad output från resolvern.

    Skrivs som extra fält ``discoveryDecision`` på prompt-input meta-
    sidecaren i ``scripts/prompt_to_project_input.py``. Är *inte* en ny
    Engine Run-artefakt; run-kontraktet förblir åtta filer.
    """

    categoryIds: list[str]
    contentBranch: str
    selectedScaffoldId: str
    targetScaffoldId: str
    selectedVariantId: str
    requestedCapabilities: list[str]
    candidateDossiers: list[str]
    fallbackWarnings: list[FallbackWarning] = field(default_factory=list)
    fieldSources: dict[str, FieldSourceLiteral] = field(default_factory=dict)
    selectionSource: SelectionSource = "default"
    operatorReviewRequired: bool = False
    fallbackScaffoldId: str | None = None
    expectedStarterId: str | None = None
    rationale: str = ""
    confidence: Literal["high", "medium", "low"] | None = None
    schemaVersion: Literal[1] = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialise till schema-kompatibel dict utan ``None``-fält."""
        payload: dict[str, Any] = {
            "schemaVersion": self.schemaVersion,
            "categoryIds": list(self.categoryIds),
            "contentBranch": self.contentBranch,
            "selectedScaffoldId": self.selectedScaffoldId,
            "targetScaffoldId": self.targetScaffoldId,
            "selectedVariantId": self.selectedVariantId,
            "requestedCapabilities": list(self.requestedCapabilities),
            "candidateDossiers": list(self.candidateDossiers),
            "fallbackWarnings": [w.to_dict() for w in self.fallbackWarnings],
            "fieldSources": dict(self.fieldSources),
            "selectionSource": self.selectionSource,
            "operatorReviewRequired": self.operatorReviewRequired,
        }
        if self.fallbackScaffoldId is not None:
            payload["fallbackScaffoldId"] = self.fallbackScaffoldId
        if self.expectedStarterId is not None:
            payload["expectedStarterId"] = self.expectedStarterId
        if self.rationale:
            payload["rationale"] = self.rationale
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload
