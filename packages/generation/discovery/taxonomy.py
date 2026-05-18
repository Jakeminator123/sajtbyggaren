"""Loader och accessor för ``governance/policies/discovery-taxonomy.v1.json``.

Discovery Taxonomy är canonical mapping från ``WizardCategoryId`` till
``targetScaffoldId``/``activeScaffoldId``/``fallbackScaffoldId``/
``defaultVariantId``/``expectedStarterId``/``requestedCapabilities``/
``candidateDossiers``/``recommendedPages``. Backendens Discovery Resolver
läser policyn via ``load_discovery_taxonomy`` och svarar med ett
``DiscoveryTaxonomy``-objekt med snabba uppslag.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import SupportStatus

DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "policies"
    / "discovery-taxonomy.v1.json"
)
"""Lokalisering för policyfilen relativt repo-roten."""


@dataclass(slots=True)
class TaxonomyCategory:
    """En kategori-post läst från ``discovery-taxonomy.v1.json``.

    Speglar shape:en under ``categories[]``. ``activeScaffoldId`` och
    ``fallbackScaffoldId`` är optional i schemat; resolvern hanterar att
    minst en av dem måste vara satt baserat på ``supportStatus``.
    """

    id: str
    labelSv: str
    contentBranch: str
    supportStatus: SupportStatus
    targetScaffoldId: str
    defaultVariantId: str
    requestedCapabilities: list[str]
    candidateDossiers: list[str]
    rationale: str
    labelEn: str | None = None
    activeScaffoldId: str | None = None
    fallbackScaffoldId: str | None = None
    expectedStarterId: str | None = None
    recommendedPages: list[str] = field(default_factory=list)
    operatorNotes: str | None = None

    @property
    def runtime_scaffold_id(self) -> str:
        """Scaffold som ska användas vid faktisk build.

        Returnerar ``activeScaffoldId`` när kategorin är active; annars
        ``fallbackScaffoldId``. Faller tillbaka till ``targetScaffoldId``
        som sista utväg så typen alltid är ``str`` — om varken active eller
        fallback finns för en planned-kategori har policyn ett valideringsfel
        som taxonomy-loadern hade flaggat.
        """
        if self.supportStatus == "active" and self.activeScaffoldId:
            return self.activeScaffoldId
        if self.fallbackScaffoldId:
            return self.fallbackScaffoldId
        if self.activeScaffoldId:
            return self.activeScaffoldId
        return self.targetScaffoldId


@dataclass(slots=True)
class DiscoveryTaxonomy:
    """In-memory representation av ``discovery-taxonomy.v1.json``.

    Ger ``O(1)`` uppslag på kategori-id via ``get(category_id)`` och en
    deterministisk content-branch-prioritetslista via
    ``branch_priority`` (lägst priority vinner vid multi-select).
    """

    policy_id: str
    version: int
    categories: dict[str, TaxonomyCategory]
    branch_priority: dict[str, int]

    def get(self, category_id: str) -> TaxonomyCategory | None:
        """Hämta en kategori per id, ``None`` när id är okänt."""
        return self.categories.get(category_id)

    def known_category_ids(self) -> set[str]:
        """Set av alla registrerade kategori-id."""
        return set(self.categories.keys())

    def pick_branch(self, category_ids: list[str]) -> str:
        """Returnerar branch:en med lägst ``priority`` för givna kategorier.

        När taxonomyn inte har ``branch_priority`` (saknad
        ``contentBranches``) eller alla kategorier är okända faller den
        tillbaka till första kända kategorins ``contentBranch``. Om ingen
        känd kategori finns alls returneras strängen ``"business"`` som
        ofarlig default (samma som ``resolveContentBranch`` i frontend).
        """
        best_branch: str | None = None
        best_priority: int | None = None
        for cid in category_ids:
            category = self.get(cid)
            if category is None:
                continue
            priority = self.branch_priority.get(category.contentBranch)
            if priority is None:
                if best_branch is None:
                    best_branch = category.contentBranch
                continue
            if best_priority is None or priority < best_priority:
                best_priority = priority
                best_branch = category.contentBranch
        return best_branch or "business"


def load_discovery_taxonomy(
    path: Path | None = None,
) -> DiscoveryTaxonomy:
    """Läs och parse ``discovery-taxonomy.v1.json``.

    ``path`` får överskridas för tester. Resolverns publika API anropar
    helpern utan argument och får policyfilen från canonical placeringen.
    """
    actual = path if path is not None else DEFAULT_TAXONOMY_PATH
    payload = json.loads(actual.read_text(encoding="utf-8"))
    categories_raw: list[dict[str, Any]] = payload.get("categories", [])
    categories: dict[str, TaxonomyCategory] = {}
    for raw in categories_raw:
        category = TaxonomyCategory(
            id=raw["id"],
            labelSv=raw["labelSv"],
            labelEn=raw.get("labelEn"),
            contentBranch=raw["contentBranch"],
            supportStatus=raw["supportStatus"],
            targetScaffoldId=raw["targetScaffoldId"],
            activeScaffoldId=raw.get("activeScaffoldId"),
            fallbackScaffoldId=raw.get("fallbackScaffoldId"),
            defaultVariantId=raw["defaultVariantId"],
            expectedStarterId=raw.get("expectedStarterId"),
            requestedCapabilities=list(raw.get("requestedCapabilities") or []),
            candidateDossiers=list(raw.get("candidateDossiers") or []),
            recommendedPages=list(raw.get("recommendedPages") or []),
            rationale=raw["rationale"],
            operatorNotes=raw.get("operatorNotes"),
        )
        categories[category.id] = category

    branch_priority: dict[str, int] = {}
    for branch_raw in payload.get("contentBranches") or []:
        branch_id = branch_raw.get("id")
        priority = branch_raw.get("priority")
        if isinstance(branch_id, str) and isinstance(priority, int):
            branch_priority[branch_id] = priority

    return DiscoveryTaxonomy(
        policy_id=payload["policyId"],
        version=int(payload["version"]),
        categories=categories,
        branch_priority=branch_priority,
    )
