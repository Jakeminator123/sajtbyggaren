"""Read-only industry coverage helpers for Backoffice.

The module joins SNI diagnostics, Discovery Taxonomy and the Asset Graph into
operator-friendly rows. It intentionally does not write files, mutate policy or
promote candidates. Candidate generation remains in the Backoffice UI layer and
must pass through existing candidate-only generators.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from packages.generation.discovery.taxonomy import TaxonomyCategory, load_discovery_taxonomy

from . import asset_graph, sni_diagnostics

COVERAGE_STATUSES = (
    "active_native",
    "active_fallback",
    "planned",
    "fallback_only",
    "missing_mapping",
)

RUNTIME_SCAFFOLD_STATUS = "active-runtime"

SAFE_SOFT_CANDIDATE_CAPABILITY_GAPS = {
    "carousel",
    "marquee",
    "command-search",
}

HARD_OR_EXTERNAL_CAPABILITY_GAPS = {
    "ai-chat",
    "analytics",
    "auth",
    "error-tracking",
    "newsletter-subscribe",
    "payments",
}

GENERIC_VARIANTS = {
    "nordic-trust",
    "clean-store",
}

SNI_CATCH_ALL_CATEGORIES = {
    "business",
    "landing",
    "minimal",
    "other",
}

FORBIDDEN_DIRECT_PICK_FIELDS = {
    "starterId",
    "scaffoldId",
    "variantId",
    "dossierId",
    "selectedDossiers",
}


def _comma_join(values: list[str] | tuple[str, ...] | set[str]) -> str:
    """Return stable comma-separated text for Backoffice table cells."""
    return ", ".join(sorted(str(value) for value in values if str(value)))


def _ordered_unique(values: list[str]) -> list[str]:
    """Return values in first-seen order without duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _capability_entries() -> dict[str, dict[str, Any]]:
    payload = asset_graph.load_policy("capability-map.v1.json")
    capabilities = payload.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return {}
    return {
        str(capability_id): entry
        for capability_id, entry in capabilities.items()
        if isinstance(entry, dict)
    }


def _canonical_dossier_ids_by_capability() -> dict[str, set[str]]:
    """Return canonical Dossier ids grouped by declared capability."""
    by_capability: dict[str, set[str]] = defaultdict(set)
    classes = asset_graph.dossier_classes()
    for _dossier_class, dossier_dir in asset_graph.list_dossier_dirs(classes=classes):
        manifest_path = dossier_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            payload = asset_graph.read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        capability = payload.get("capability")
        dossier_id = payload.get("id")
        if isinstance(capability, str) and isinstance(dossier_id, str):
            by_capability[capability].add(dossier_id)
    return by_capability


def _dossier_candidate_counts_by_capability(
    candidates_dir: Path | None = None,
) -> dict[str, int]:
    """Return candidate Dossier counts grouped by manifest capability."""
    base = candidates_dir if candidates_dir is not None else asset_graph.DOSSIER_CANDIDATES_DIR
    counts: Counter[str] = Counter()
    if not base.exists():
        return {}
    for manifest_path in sorted(base.glob("*/*/manifest.json")):
        try:
            payload = _read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        capability = payload.get("capability")
        if isinstance(capability, str) and capability:
            counts[capability] += 1
    return dict(counts)


def _scaffold_rows_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(row["scaffoldId"]): row
        for row in asset_graph.asset_graph_scaffold_rows()
        if row.get("scaffoldId")
    }


def _is_runtime_scaffold(scaffold_row: dict[str, Any] | None) -> bool:
    """Return whether Asset Graph considers this Scaffold buildable today."""
    if not scaffold_row:
        return False
    return (
        str(scaffold_row.get("status") or "") == RUNTIME_SCAFFOLD_STATUS
        and str(scaffold_row.get("fileState") or "") == "implemented"
        and bool(scaffold_row.get("runtimeStarterId"))
    )


def _sni_rows_by_category(
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows if rows is not None else sni_diagnostics.mapping_rows():
        category_id = str(row.get("wizardCategoryId") or "")
        if category_id:
            grouped[category_id].append(row)
    return grouped


def _sni_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    confidence = sni_diagnostics.confidence_breakdown(rows)
    divisions = [
        str(row.get("sniCode") or "")
        for row in rows
        if row.get("sniLevel") == "division"
    ]
    groups = [
        str(row.get("sniCode") or "")
        for row in rows
        if row.get("sniLevel") == "group"
    ]
    labels = [
        f"{row.get('sniCode')}: {row.get('sniLabelSv')}"
        for row in rows
        if row.get("sniCode") and row.get("sniLabelSv")
    ]
    return {
        "mappedSniDivisions": _ordered_unique(divisions),
        "mappedSniGroups": _ordered_unique(groups),
        "mappedSniLabels": _ordered_unique([str(label) for label in labels]),
        "sniMappingCount": len(rows),
        "sniConfidenceHigh": confidence["high"],
        "sniConfidenceMedium": confidence["medium"],
        "sniConfidenceLow": confidence["low"],
        "sniConfidenceOther": confidence["other"],
    }


def _selected_runtime_scaffold_id(
    category: TaxonomyCategory,
    scaffold_rows: dict[str, dict[str, Any]],
) -> str | None:
    """Pick the runtime Scaffold without promoting planned target Scaffolds."""
    candidates: list[str | None] = []
    if category.supportStatus == "active":
        candidates.append(category.activeScaffoldId)
        candidates.append(category.fallbackScaffoldId)
    else:
        candidates.append(category.fallbackScaffoldId)

    for scaffold_id in candidates:
        if scaffold_id and _is_runtime_scaffold(scaffold_rows.get(scaffold_id)):
            return scaffold_id
    return None


def _variant_ids(scaffold_id: str | None) -> list[str]:
    if not scaffold_id:
        return []
    ids: list[str] = []
    for payload in asset_graph.load_existing_variants(scaffold_id):
        variant_id = payload.get("id")
        if isinstance(variant_id, str) and variant_id:
            ids.append(variant_id)
    return sorted(ids)


def _capability_state(
    requested_capabilities: list[str],
    capability_entries: dict[str, dict[str, Any]],
    canonical_by_capability: dict[str, set[str]],
    candidates_by_capability: dict[str, int],
) -> dict[str, Any]:
    unknown: list[str] = []
    gaps: list[str] = []
    hard_or_external_gaps: list[str] = []
    safe_soft_gaps: list[str] = []
    canonical_count = 0
    candidate_count = 0

    for capability_id in requested_capabilities:
        entry = capability_entries.get(capability_id)
        if entry is None:
            unknown.append(capability_id)
            continue
        configured = [
            str(dossier_id)
            for dossier_id in entry.get("dossiers", []) or []
            if isinstance(dossier_id, str) and dossier_id
        ]
        implemented = sorted(set(configured) & canonical_by_capability.get(capability_id, set()))
        canonical_count += len(implemented)
        candidate_count += int(candidates_by_capability.get(capability_id, 0))
        if not implemented:
            gaps.append(capability_id)
            if capability_id in SAFE_SOFT_CANDIDATE_CAPABILITY_GAPS:
                safe_soft_gaps.append(capability_id)
            elif capability_id in HARD_OR_EXTERNAL_CAPABILITY_GAPS:
                hard_or_external_gaps.append(capability_id)

    return {
        "unknownCapabilities": unknown,
        "capabilityGaps": gaps,
        "safeSoftCapabilityGaps": safe_soft_gaps,
        "hardOrExternalCapabilityGaps": hard_or_external_gaps,
        "canonicalDossierCount": canonical_count,
        "dossierCandidateCount": candidate_count,
        "capabilityGapCount": len(gaps),
        "unknownCapabilityCount": len(unknown),
    }


def _coverage_status(
    *,
    category: TaxonomyCategory,
    selected_runtime_scaffold_id: str | None,
    sni_mapping_count: int,
    target_is_runtime: bool,
) -> str:
    if sni_mapping_count == 0:
        return "missing_mapping"
    if category.supportStatus == "planned":
        return "planned"
    if selected_runtime_scaffold_id and selected_runtime_scaffold_id != category.targetScaffoldId:
        return "active_fallback" if category.supportStatus == "active" else "fallback_only"
    if category.supportStatus == "fallback":
        return "fallback_only"
    if category.supportStatus == "active" and target_is_runtime:
        return "active_native"
    return "active_fallback"


def _attention_reasons(
    *,
    category: TaxonomyCategory,
    selected_runtime_scaffold_id: str | None,
    default_variant_id: str,
    has_default_variant: bool,
    runtime_starter_id: str,
    target_is_runtime: bool,
    capability_state: dict[str, Any],
    sni_mapping_count: int,
) -> list[str]:
    reasons: list[str] = []
    if sni_mapping_count == 0 and category.id not in SNI_CATCH_ALL_CATEGORIES:
        reasons.append("missing_sni_mapping")
    if selected_runtime_scaffold_id is None:
        reasons.append("missing_runtime_scaffold")
    if selected_runtime_scaffold_id and default_variant_id and not has_default_variant:
        reasons.append("missing_default_variant")
    if runtime_starter_id and category.expectedStarterId and runtime_starter_id != category.expectedStarterId:
        reasons.append("starter_mismatch")
    if capability_state["unknownCapabilities"]:
        reasons.append("unknown_capability")
    if capability_state["capabilityGaps"]:
        reasons.append("capability_gap")
    if category.supportStatus in {"planned", "fallback"} and target_is_runtime:
        reasons.append("policy_asset_divergence")
    if category.supportStatus == "active" and selected_runtime_scaffold_id != category.targetScaffoldId:
        reasons.append("policy_asset_divergence")
    return _ordered_unique(reasons)


def _recommended_actions(
    *,
    row: dict[str, Any],
    capability_state: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    if row["sniMappingCount"] == 0 and row["wizardCategoryId"] not in SNI_CATCH_ALL_CATEGORIES:
        actions.append("add_sni_mapping")
    if row["selectedRuntimeScaffoldId"]:
        if not row["hasDefaultVariant"]:
            actions.append("create_variant_candidate")
        elif row["defaultVariantId"] in GENERIC_VARIANTS and row["contentBranch"] not in {
            "business",
            "ecommerce",
        }:
            actions.append("create_variant_candidate")
    if capability_state["safeSoftCapabilityGaps"]:
        actions.append("create_soft_dossier_candidate")
    if capability_state["unknownCapabilities"] or capability_state["hardOrExternalCapabilityGaps"]:
        actions.append("review_capability_gap")
    if "policy_asset_divergence" in row["attentionReasons"]:
        actions.append("review_taxonomy_status")
    if row["targetScaffoldId"] and row["targetScaffoldStatus"] not in {
        RUNTIME_SCAFFOLD_STATUS,
        "implemented",
    }:
        actions.append("create_scaffold_candidate")
    if row["supportStatus"] in {"planned", "fallback"} and row["targetScaffoldStatus"] == RUNTIME_SCAFFOLD_STATUS:
        actions.append("promote_planned_scaffold_later")
    return _ordered_unique(actions)


def industry_coverage_rows() -> list[dict[str, Any]]:
    """Return one read-only coverage row per Discovery Taxonomy category."""
    taxonomy = load_discovery_taxonomy()
    sni_by_category = _sni_rows_by_category()
    scaffold_rows = _scaffold_rows_by_id()
    capability_entries = _capability_entries()
    canonical_by_capability = _canonical_dossier_ids_by_capability()
    candidates_by_capability = _dossier_candidate_counts_by_capability()

    rows: list[dict[str, Any]] = []
    for category_id in sorted(taxonomy.categories):
        category = taxonomy.categories[category_id]
        sni_summary = _sni_summary(sni_by_category.get(category.id, []))
        selected_runtime_scaffold = _selected_runtime_scaffold_id(category, scaffold_rows)
        selected_scaffold_row = scaffold_rows.get(selected_runtime_scaffold or "")
        target_scaffold_row = scaffold_rows.get(category.targetScaffoldId)
        target_is_runtime = _is_runtime_scaffold(target_scaffold_row)
        selected_variant_ids = _variant_ids(selected_runtime_scaffold)
        variant_candidate_count = len(
            asset_graph.list_variant_candidates(selected_runtime_scaffold)
            if selected_runtime_scaffold
            else []
        )
        requested_capabilities = list(category.requestedCapabilities)
        capability_state = _capability_state(
            requested_capabilities,
            capability_entries,
            canonical_by_capability,
            candidates_by_capability,
        )
        runtime_starter_id = str((selected_scaffold_row or {}).get("runtimeStarterId") or "")
        default_variant_id = category.defaultVariantId
        has_default_variant = bool(
            selected_runtime_scaffold
            and default_variant_id
            and default_variant_id in selected_variant_ids
        )
        attention_reasons = _attention_reasons(
            category=category,
            selected_runtime_scaffold_id=selected_runtime_scaffold,
            default_variant_id=default_variant_id,
            has_default_variant=has_default_variant,
            runtime_starter_id=runtime_starter_id,
            target_is_runtime=target_is_runtime,
            capability_state=capability_state,
            sni_mapping_count=int(sni_summary["sniMappingCount"]),
        )
        coverage_status = _coverage_status(
            category=category,
            selected_runtime_scaffold_id=selected_runtime_scaffold,
            sni_mapping_count=int(sni_summary["sniMappingCount"]),
            target_is_runtime=target_is_runtime,
        )

        row: dict[str, Any] = {
            "contentBranch": category.contentBranch,
            "wizardCategoryId": category.id,
            "labelSv": category.labelSv,
            "supportStatus": category.supportStatus,
            "mappedSniDivisions": sni_summary["mappedSniDivisions"],
            "mappedSniGroups": sni_summary["mappedSniGroups"],
            "mappedSniLabels": sni_summary["mappedSniLabels"],
            "sniMappingCount": sni_summary["sniMappingCount"],
            "sniConfidenceHigh": sni_summary["sniConfidenceHigh"],
            "sniConfidenceMedium": sni_summary["sniConfidenceMedium"],
            "sniConfidenceLow": sni_summary["sniConfidenceLow"],
            "sniConfidenceOther": sni_summary["sniConfidenceOther"],
            "targetScaffoldId": category.targetScaffoldId,
            "activeScaffoldId": category.activeScaffoldId or "",
            "fallbackScaffoldId": category.fallbackScaffoldId or "",
            "selectedRuntimeScaffoldId": selected_runtime_scaffold,
            "defaultVariantId": default_variant_id,
            "expectedStarterId": category.expectedStarterId or "",
            "runtimeStarterId": runtime_starter_id,
            "requestedCapabilities": requested_capabilities,
            "candidateDossiers": list(category.candidateDossiers),
            "recommendedPages": list(category.recommendedPages),
            "targetScaffoldStatus": str((target_scaffold_row or {}).get("status") or "missing"),
            "selectedScaffoldStatus": str((selected_scaffold_row or {}).get("status") or ""),
            "implementedScaffoldStatus": str((target_scaffold_row or {}).get("fileState") or "missing"),
            "variantCount": len(selected_variant_ids),
            "variantCandidateCount": variant_candidate_count,
            "hasDefaultVariant": has_default_variant,
            "canonicalDossierCount": capability_state["canonicalDossierCount"],
            "dossierCandidateCount": capability_state["dossierCandidateCount"],
            "capabilityGapCount": capability_state["capabilityGapCount"],
            "unknownCapabilityCount": capability_state["unknownCapabilityCount"],
            "unknownCapabilities": capability_state["unknownCapabilities"],
            "capabilityGaps": capability_state["capabilityGaps"],
            "safeSoftCapabilityGaps": capability_state["safeSoftCapabilityGaps"],
            "hardOrExternalCapabilityGaps": capability_state["hardOrExternalCapabilityGaps"],
            "coverageStatus": coverage_status,
            "needsAttention": bool(attention_reasons),
            "attentionReasons": attention_reasons,
            "recommendedActions": [],
            "rationale": category.rationale,
            "operatorNotes": category.operatorNotes or "",
        }
        row["recommendedActions"] = _recommended_actions(
            row=row,
            capability_state=capability_state,
        )
        forbidden = FORBIDDEN_DIRECT_PICK_FIELDS.intersection(row)
        if forbidden:
            raise RuntimeError(f"Industry coverage row leaked direct-pick fields: {sorted(forbidden)}")
        rows.append(row)
    return rows


def content_branch_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return aggregate coverage counters per contentBranch."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("contentBranch") or "")].append(row)

    summary: list[dict[str, Any]] = []
    for branch, branch_rows in sorted(grouped.items()):
        status_counts = Counter(str(row.get("coverageStatus") or "") for row in branch_rows)
        summary.append(
            {
                "contentBranch": branch,
                "categories": len(branch_rows),
                "activeNative": status_counts.get("active_native", 0),
                "activeFallback": status_counts.get("active_fallback", 0),
                "planned": status_counts.get("planned", 0),
                "fallbackOnly": status_counts.get("fallback_only", 0),
                "missingMapping": status_counts.get("missing_mapping", 0),
                "needsAttention": sum(1 for row in branch_rows if row.get("needsAttention")),
                "sniMappings": sum(int(row.get("sniMappingCount") or 0) for row in branch_rows),
                "variantCandidates": sum(int(row.get("variantCandidateCount") or 0) for row in branch_rows),
                "dossierCandidates": sum(int(row.get("dossierCandidateCount") or 0) for row in branch_rows),
            }
        )
    return summary


def recommended_action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten category recommended actions into a table-friendly list."""
    out: list[dict[str, Any]] = []
    for row in rows:
        for action in row.get("recommendedActions", []) or []:
            out.append(
                {
                    "action": action,
                    "wizardCategoryId": row["wizardCategoryId"],
                    "labelSv": row["labelSv"],
                    "contentBranch": row["contentBranch"],
                    "coverageStatus": row["coverageStatus"],
                    "needsAttention": row["needsAttention"],
                    "attentionReasons": list(row.get("attentionReasons", [])),
                    "selectedRuntimeScaffoldId": row.get("selectedRuntimeScaffoldId") or "",
                    "targetScaffoldId": row.get("targetScaffoldId") or "",
                }
            )
    return out


def _bullet_list(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {value}" for value in values)


def build_variant_candidate_brief(row: dict[str, Any]) -> str:
    """Build a safe operator brief for a category-specific Variant candidate."""
    return f"""Create a disabled Scaffold Variant candidate for Sajtbyggaren.

Category context:
- wizardCategoryId: {row["wizardCategoryId"]}
- labelSv: {row["labelSv"]}
- contentBranch: {row["contentBranch"]}
- supportStatus: {row["supportStatus"]}
- coverageStatus: {row["coverageStatus"]}
- targetScaffoldId: {row["targetScaffoldId"]}
- selectedRuntimeScaffoldId: {row.get("selectedRuntimeScaffoldId") or "none"}
- defaultVariantId: {row["defaultVariantId"]}

Mapped SNI prefixes:
{_bullet_list([*row.get("mappedSniDivisions", []), *row.get("mappedSniGroups", [])])}

Mapped SNI labels:
{_bullet_list(list(row.get("mappedSniLabels", [])))}

Recommended pages:
{_bullet_list(list(row.get("recommendedPages", [])))}

Requested capabilities:
{_bullet_list(list(row.get("requestedCapabilities", [])))}

Rationale:
{row.get("rationale") or "No rationale provided."}

Operator notes:
{row.get("operatorNotes") or "No operator notes."}

Hard rules:
- Candidate only; write under data/variant-candidates.
- Keep enabled=false.
- Do not promote to canonical variants.
- Do not add runtime integrations, auth, payments, backend services or env vars.
- Make the visual direction concrete for real Swedish small-business previews.
"""


def build_dossier_candidate_brief(
    row: dict[str, Any],
    capability_id: str | None = None,
) -> str:
    """Build a safe operator brief for a soft Dossier candidate."""
    capability = capability_id or (row.get("safeSoftCapabilityGaps") or [""])[0]
    return f"""Create a disabled soft Dossier candidate for Sajtbyggaren.

Capability:
- {capability or "unspecified"}

Category context:
- wizardCategoryId: {row["wizardCategoryId"]}
- labelSv: {row["labelSv"]}
- contentBranch: {row["contentBranch"]}
- supportStatus: {row["supportStatus"]}
- coverageStatus: {row["coverageStatus"]}

Mapped SNI prefixes:
{_bullet_list([*row.get("mappedSniDivisions", []), *row.get("mappedSniGroups", [])])}

Mapped SNI labels:
{_bullet_list(list(row.get("mappedSniLabels", [])))}

Recommended pages:
{_bullet_list(list(row.get("recommendedPages", [])))}

Requested capabilities:
{_bullet_list(list(row.get("requestedCapabilities", [])))}

Rationale:
{row.get("rationale") or "No rationale provided."}

Operator notes:
{row.get("operatorNotes") or "No operator notes."}

Hard rules:
- Candidate only; write under data/dossier-candidates.
- This is a soft, instructions-only Dossier candidate.
- Keep enabled=false.
- Do not promote to canonical Dossiers.
- Do not require env vars, auth, payments, backend services or external APIs.
- Describe concrete capability behavior that improves website generation.
- Do not write a generic industry description; keep the guidance operational.
"""


def table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return rows with list fields flattened for Streamlit dataframes."""
    flattened: list[dict[str, Any]] = []
    list_fields = {
        "mappedSniDivisions",
        "mappedSniGroups",
        "mappedSniLabels",
        "requestedCapabilities",
        "candidateDossiers",
        "recommendedPages",
        "unknownCapabilities",
        "capabilityGaps",
        "safeSoftCapabilityGaps",
        "hardOrExternalCapabilityGaps",
        "attentionReasons",
        "recommendedActions",
    }
    for row in rows:
        next_row = dict(row)
        for field in list_fields:
            next_row[field] = _comma_join(next_row.get(field, []))
        flattened.append(next_row)
    return flattened
