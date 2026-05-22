"""Backoffice read-only diagnostik för SNI 2025 → Discovery category.

Modulen är medvetet runtime-fri: ingen kod under ``packages/generation``
importerar härifrån, och inga policy-writes sker. Den läser SNI
2025-referensen (``data/taxonomies/sni/sni-2025.v1.json``), SNI Discovery
Map-policyn (``governance/policies/sni-discovery-map.v1.json``) och
Discovery Taxonomy och bygger:

- ``mapping_rows`` — en rad per policymappning med faktisk SNI labelSv
  och Discovery Taxonomy-konsekvenser (supportStatus, scaffold/variant/
  starter/capabilities) som downstream-information, inte SNI-beslut.
- ``mapping_summary`` — kompakta räknare för Backoffice-metrics.
- ``lookup_row`` — diagnostiskt resultat när operatorn matar in en SNI-kod.

Diagnostiken får aldrig returnera ``starterId``, ``scaffoldId``,
``variantId``, ``dossierId`` eller ``selectedDossiers`` som SNI-beslut;
de visas bara som *konsekvens via Discovery Taxonomy* när policyn ger en
kandidat-kategori.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from packages.generation.discovery.sni_map import (
    SniDiscoveryMap,
    SniMapping,
    SniMatch,
    load_sni_discovery_map,
    resolve_sni_discovery_category,
)
from packages.generation.discovery.taxonomy import (
    DiscoveryTaxonomy,
    TaxonomyCategory,
    load_discovery_taxonomy,
)

from .paths import DATA_DIR, POLICIES_DIR

DEFAULT_SNI_REFERENCE_PATH = DATA_DIR / "taxonomies" / "sni" / "sni-2025.v1.json"
DEFAULT_SNI_POLICY_PATH = POLICIES_DIR / "sni-discovery-map.v1.json"
"""Canonical placering för SNI-data och SNI Discovery Map-policy."""

WARNING_LINES_SV: tuple[str, ...] = (
    "SNI är branschsignal, inte runtime-sanning.",
    "SNI väljer inte starter, scaffold, variant eller Dossier direkt.",
    "Discovery Taxonomy avgör fortsatt scaffold/variant/expectedStarterId/requestedCapabilities.",
)
"""Operatörstext som Backoffice-vyn ska visa ovanför tabellen."""


def load_sni_reference(path: Path | None = None) -> dict[str, Any]:
    """Läs ``sni-2025.v1.json`` och returnera payload (eller tomt dict)."""
    actual = path if path is not None else DEFAULT_SNI_REFERENCE_PATH
    if not actual.exists():
        return {"taxonomyId": "sni-2025", "items": []}
    try:
        return json.loads(actual.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"taxonomyId": "sni-2025", "items": []}


def _index_reference_labels(reference: dict[str, Any]) -> dict[str, str]:
    items = reference.get("items") or []
    out: dict[str, str] = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "")
        label = entry.get("labelSv")
        if code and isinstance(label, str):
            out[code] = label
    return out


def _category_chain(category: TaxonomyCategory | None) -> dict[str, Any]:
    """Pack a Discovery Taxonomy category in a backoffice-friendly shape."""
    if category is None:
        return {
            "discoverySupportStatus": "unknown",
            "discoveryTargetScaffoldId": None,
            "discoveryFallbackScaffoldId": None,
            "discoveryActiveScaffoldId": None,
            "discoveryDefaultVariantId": None,
            "discoveryExpectedStarterId": None,
            "discoveryRequestedCapabilities": [],
            "discoveryCandidateDossiers": [],
        }
    return {
        "discoverySupportStatus": category.supportStatus,
        "discoveryTargetScaffoldId": category.targetScaffoldId,
        "discoveryActiveScaffoldId": category.activeScaffoldId,
        "discoveryFallbackScaffoldId": category.fallbackScaffoldId,
        "discoveryDefaultVariantId": category.defaultVariantId,
        "discoveryExpectedStarterId": category.expectedStarterId,
        "discoveryRequestedCapabilities": list(category.requestedCapabilities),
        "discoveryCandidateDossiers": list(category.candidateDossiers),
    }


def _row_for_mapping(
    mapping: SniMapping,
    reference_labels: dict[str, str],
    taxonomy: DiscoveryTaxonomy,
) -> dict[str, Any]:
    sni_label = reference_labels.get(mapping.sniCode, mapping.labelSv or "")
    category = taxonomy.get(mapping.wizardCategoryId)
    chain = _category_chain(category)
    row: dict[str, Any] = {
        "sniCode": mapping.sniCode,
        "sniLevel": mapping.level,
        "sniLabelSv": sni_label,
        "wizardCategoryId": mapping.wizardCategoryId,
        "confidence": mapping.confidence,
        "notesSv": mapping.notesSv or "",
        "categoryKnown": category is not None,
    }
    row.update(chain)
    return row


def mapping_rows(
    *,
    sni_map: SniDiscoveryMap | None = None,
    taxonomy: DiscoveryTaxonomy | None = None,
    reference: dict[str, Any] | None = None,
    policy_path: Path | None = None,
    reference_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Bygg radlistan över alla policy-mappningar.

    Divisions sorteras före group-overrides och sedan på ``sniCode``.
    """
    resolved_map = sni_map if sni_map is not None else load_sni_discovery_map(policy_path)
    resolved_taxonomy = taxonomy if taxonomy is not None else load_discovery_taxonomy()
    resolved_reference = reference if reference is not None else load_sni_reference(reference_path)
    labels = _index_reference_labels(resolved_reference)
    rows: list[dict[str, Any]] = []
    for mapping in resolved_map.all_mappings():
        rows.append(_row_for_mapping(mapping, labels, resolved_taxonomy))
    return rows


def mapping_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Returnera kompakta räknare för Backoffice-metrics."""
    level_counts = Counter(row["sniLevel"] for row in rows)
    category_counts = Counter(row["wizardCategoryId"] for row in rows)
    unknown_categories = sum(1 for row in rows if not row["categoryKnown"])
    return {
        "total": len(rows),
        "divisionMappings": level_counts.get("division", 0),
        "groupOverrides": level_counts.get("group", 0),
        "uniqueCategories": len(category_counts),
        "unknownCategories": unknown_categories,
    }


def confidence_breakdown(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Antal mappningar per confidence-nivå (high/medium/low/other)."""
    counts: Counter[str] = Counter()
    for row in rows:
        level = str(row.get("confidence") or "").strip().lower() or "other"
        counts[level] += 1
    return {
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "other": sum(value for key, value in counts.items() if key not in {"high", "medium", "low"}),
    }


def taxonomy_coverage_gaps(
    *,
    rows: list[dict[str, Any]] | None = None,
    taxonomy: DiscoveryTaxonomy | None = None,
    policy_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Returnera Discovery Taxonomy-kategorier som *saknar* SNI-mappning.

    Den här diagnostiken hjälper operatören se var policyn behöver
    breddas. Resultatet listar bara taxonomy-kategorier som inte har en
    enda matchande policyrad (division eller group-override); kategorier
    med ofullständig SNI-bredd men minst en rad räknas som täckta.
    """
    resolved_taxonomy = taxonomy if taxonomy is not None else load_discovery_taxonomy()
    resolved_rows = rows if rows is not None else mapping_rows(policy_path=policy_path)
    covered = {row["wizardCategoryId"] for row in resolved_rows if row["wizardCategoryId"]}
    gaps: list[dict[str, Any]] = []
    for category_id in sorted(resolved_taxonomy.known_category_ids()):
        if category_id in covered:
            continue
        category = resolved_taxonomy.get(category_id)
        if category is None:
            continue
        gaps.append(
            {
                "wizardCategoryId": category_id,
                "labelSv": category.labelSv,
                "supportStatus": category.supportStatus,
                "rationale": category.rationale,
            }
        )
    return gaps


def reference_summary(reference: dict[str, Any]) -> dict[str, int]:
    """Antal SNI-poster per nivå i den committade referensen."""
    items = reference.get("items") or []
    counts = Counter(
        entry.get("level", "unknown")
        for entry in items
        if isinstance(entry, dict)
    )
    return {
        "total": len(items),
        "section": counts.get("section", 0),
        "division": counts.get("division", 0),
        "group": counts.get("group", 0),
        "class": counts.get("class", 0),
        "subclass": counts.get("subclass", 0),
    }


def lookup_row(
    value: str | None,
    *,
    sni_map: SniDiscoveryMap | None = None,
    taxonomy: DiscoveryTaxonomy | None = None,
    reference: dict[str, Any] | None = None,
    policy_path: Path | None = None,
    reference_path: Path | None = None,
) -> dict[str, Any]:
    """Bygg diagnostisk rad för en SNI-kod som operatören matar in.

    Resultatet inkluderar både SNI-matchningen från
    :func:`resolve_sni_discovery_category` och Discovery Taxonomy-
    konsekvenser för den föreslagna kategorin. Trasiga eller okända koder
    ger en rad med ``matchedLevel="unknown"`` och tomma downstream-fält.
    """
    resolved_map = sni_map if sni_map is not None else load_sni_discovery_map(policy_path)
    resolved_taxonomy = taxonomy if taxonomy is not None else load_discovery_taxonomy()
    resolved_reference = reference if reference is not None else load_sni_reference(reference_path)
    labels = _index_reference_labels(resolved_reference)

    match: SniMatch = resolve_sni_discovery_category(value, sni_map=resolved_map)
    sni_label = (
        labels.get(match.normalizedCode)
        or labels.get(match.matchedSniCode or "")
        or match.labelSv
        or ""
    )
    category = (
        resolved_taxonomy.get(match.wizardCategoryId)
        if match.wizardCategoryId
        else None
    )
    chain = _category_chain(category)
    row: dict[str, Any] = {
        "input": match.input,
        "normalizedCode": match.normalizedCode,
        "matchedLevel": match.matchedLevel,
        "matchedSniCode": match.matchedSniCode,
        "sniLabelSv": sni_label,
        "wizardCategoryId": match.wizardCategoryId,
        "confidence": match.confidence,
        "notesSv": match.notesSv or "",
        "sourcePolicy": match.sourcePolicy,
        "categoryKnown": category is not None,
    }
    row.update(chain)
    return row


def lookup_parent_chain(
    value: str | None,
    *,
    reference: dict[str, Any] | None = None,
    reference_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Returnera parent-chain från avdelning ner till själva SNI-koden.

    Helpern letar i ``sni-2025.v1.json`` på normaliserad kod-form
    (``56.100`` -> ``56100``) och returnerar de items vars koder
    förekommer i target-itemets ``path`` (inklusive itemet själv som
    sista rad). Returnerar tom lista när koden inte hittas i referensen.

    Backoffice-vyn använder detta för att ge samma översikt som
    ``scripts/lookup_sni.py code <CODE>`` ger på CLI:
    *avdelning → huvudgrupp → grupp → undergrupp → detaljgrupp*.
    """
    if not value or not str(value).strip():
        return []
    resolved_reference = reference if reference is not None else load_sni_reference(reference_path)
    items = resolved_reference.get("items") or []
    if not items:
        return []

    code_index: dict[str, dict[str, Any]] = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "").upper()
        if code:
            code_index[code] = entry

    from packages.generation.discovery.sni_map import normalize_sni_code

    needle = normalize_sni_code(value).upper()
    if not needle:
        return []

    target: dict[str, Any] | None = code_index.get(needle)
    # När operatören skriver en kod som inte är en faktisk SNI-post (t.ex.
    # ``56100`` istället för canonical ``56110``) trunkerar vi från höger
    # tills en faktisk kod hittas — då får parent-chain ändå rätt SNI-
    # struktur från avdelning ner till djupaste verkliga match.
    while target is None and len(needle) > 1:
        needle = needle[:-1]
        target = code_index.get(needle)
    if target is None:
        return []

    chain: list[dict[str, Any]] = []
    for code in target.get("path", []) or []:
        match = code_index.get(str(code).upper())
        if match is None:
            continue
        chain.append(
            {
                "code": match.get("code"),
                "level": match.get("level"),
                "labelSv": match.get("labelSv"),
            }
        )
    return chain


def filter_rows_by_category(
    rows: list[dict[str, Any]],
    wizard_category_id: str | None,
) -> list[dict[str, Any]]:
    """Filtrera ``mapping_rows`` på vald wizardCategoryId.

    ``None`` eller ``"Alla"`` returnerar rows oförändrade.
    """
    if not wizard_category_id or wizard_category_id == "Alla":
        return list(rows)
    return [row for row in rows if row["wizardCategoryId"] == wizard_category_id]
