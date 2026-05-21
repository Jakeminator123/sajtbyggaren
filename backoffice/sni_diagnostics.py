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
