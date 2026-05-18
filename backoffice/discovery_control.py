"""Backoffice helpers for reviewing and editing Discovery mapping."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .io import atomic_write_json
from .paths import POLICIES_DIR, REPO_ROOT

DISCOVERY_TAXONOMY_PATH = POLICIES_DIR / "discovery-taxonomy.v1.json"
DISCOVERY_TAXONOMY_SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "discovery-taxonomy.schema.json"
CAPABILITY_MAP_PATH = POLICIES_DIR / "capability-map.v1.json"
SCAFFOLD_CONTRACT_PATH = POLICIES_DIR / "scaffold-contract.v1.json"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"

EDITABLE_CATEGORY_FIELDS = {
    "supportStatus",
    "labelSv",
    "operatorNotes",
    "targetScaffoldId",
    "activeScaffoldId",
    "fallbackScaffoldId",
    "defaultVariantId",
    "requestedCapabilities",
    "candidateDossiers",
}

SUPPORT_STATUSES = {"active", "fallback", "planned", "disabled"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _node(
    *,
    node_type: str,
    node_id: str,
    path: Path,
    status: str,
    canonical: bool,
    enabled: bool | None = None,
    details: str = "",
) -> dict[str, Any]:
    return {
        "type": node_type,
        "id": node_id,
        "path": _repo_relative(path),
        "status": status,
        "canonical": canonical,
        "enabled": enabled,
        "details": details,
    }


def _edge(source: str, target: str, relation: str, details: str = "") -> dict[str, str]:
    return {"from": source, "to": target, "relation": relation, "details": details}


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_discovery_policy(path: Path | None = None) -> dict[str, Any]:
    """Read the Discovery Taxonomy policy as a JSON object."""
    return _read_json(path or DISCOVERY_TAXONOMY_PATH)


def _capability_map(path: Path | None = None) -> dict[str, dict[str, Any]]:
    payload = _read_json(path or CAPABILITY_MAP_PATH)
    raw = payload.get("capabilities", {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): value for key, value in raw.items() if isinstance(value, dict)}


def _scaffold_registry(path: Path | None = None) -> set[str]:
    payload = _read_json(path or SCAFFOLD_CONTRACT_PATH)
    return {
        str(entry["id"])
        for entry in payload.get("primaryScaffoldRegistry", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def _runtime_mapping() -> dict[str, str]:
    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER

    return dict(SCAFFOLD_TO_STARTER)


def _selected_scaffold(category: dict[str, Any]) -> str:
    status = category.get("supportStatus")
    if status == "active":
        return str(category.get("activeScaffoldId") or category.get("targetScaffoldId") or "")
    if category.get("fallbackScaffoldId"):
        return str(category["fallbackScaffoldId"])
    if category.get("activeScaffoldId"):
        return str(category["activeScaffoldId"])
    return str(category.get("targetScaffoldId") or "")


def _variant_path(scaffold_id: str, variant_id: str) -> Path:
    return SCAFFOLDS_DIR / scaffold_id / "variants" / f"{variant_id}.json"


def _dossier_manifest_path(dossier_id: str) -> Path | None:
    for dossier_class in ("soft", "hard"):
        path = DOSSIERS_DIR / dossier_class / dossier_id / "manifest.json"
        if path.exists():
            return path
    return None


def _dossier_node_key(dossier_id: str) -> str:
    manifest = _dossier_manifest_path(dossier_id)
    if manifest is None:
        return f"dossier:{dossier_id}"
    return f"{manifest.parent.parent.name}-dossier:{dossier_id}"


def _capability_status(capability_id: str, capabilities: dict[str, dict[str, Any]]) -> str:
    entry = capabilities.get(capability_id)
    if entry is None:
        return "missing"
    dossiers = entry.get("dossiers") or []
    return "implemented" if dossiers else "gap"


def category_mapping_rows(policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return compact Backoffice rows for Discovery category mappings."""
    payload = policy if policy is not None else load_discovery_policy()
    findings_by_category = _findings_by_category(discovery_doctor_findings(payload))
    runtime_map = _runtime_mapping()
    rows: list[dict[str, Any]] = []
    for category in payload.get("categories", []):
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id", ""))
        findings = findings_by_category.get(category_id, [])
        rows.append(
            {
                "categoryId": category_id,
                "label": category.get("labelSv", ""),
                "supportStatus": category.get("supportStatus", ""),
                "mappingState": _mapping_state(category, runtime_map),
                "operatorReviewRequired": _operator_review_required(category, findings),
                "targetScaffoldId": category.get("targetScaffoldId", ""),
                "activeScaffoldId": category.get("activeScaffoldId", ""),
                "fallbackScaffoldId": category.get("fallbackScaffoldId", ""),
                "defaultVariantId": category.get("defaultVariantId", ""),
                "expectedStarterId": category.get("expectedStarterId", ""),
                "requestedCapabilities": ", ".join(category.get("requestedCapabilities") or []),
                "candidateDossiers": ", ".join(category.get("candidateDossiers") or []),
                "fallbackWarnings": _warning_summary(category, findings),
                "rationale": category.get("rationale", ""),
            }
        )
    return rows


def _findings_by_category(
    findings: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    by_category: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        parts = finding.get("id", "").split(":")
        if len(parts) < 2:
            continue
        by_category.setdefault(parts[1], []).append(finding)
    return by_category


def _mapping_state(category: dict[str, Any], runtime_map: dict[str, str]) -> str:
    status = str(category.get("supportStatus") or "unknown")
    if status == "disabled":
        return "disabled"
    selected_scaffold = _selected_scaffold(category)
    target_scaffold = str(category.get("targetScaffoldId") or "")
    if selected_scaffold and selected_scaffold not in runtime_map:
        return "orphan"
    if selected_scaffold and target_scaffold and selected_scaffold != target_scaffold:
        return "fallback-runtime" if status == "fallback" else "planned-fallback"
    if selected_scaffold in runtime_map:
        return "active-runtime"
    return status


def _operator_review_required(
    category: dict[str, Any],
    findings: list[dict[str, str]],
) -> str:
    status = str(category.get("supportStatus") or "")
    if status in {"planned", "disabled"}:
        return "ja"
    if any(finding.get("level") == "error" for finding in findings):
        return "ja"
    if any(":capability:" in finding.get("id", "") for finding in findings):
        return "ja"
    return "nej"


def _warning_summary(
    category: dict[str, Any],
    findings: list[dict[str, str]],
) -> str:
    if findings:
        return "; ".join(
            f"{finding['level']}:{finding['id'].split(':', 1)[0]}"
            for finding in findings
        )
    status = str(category.get("supportStatus") or "")
    if status == "planned":
        return "planned target uses fallback scaffold for future init-runs"
    if status == "fallback":
        return "fallback mapping until native scaffold support exists"
    if status == "disabled":
        return "disabled category requires operator review"
    return ""


def build_discovery_graph(policy: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Build graph nodes/edges for Discovery mapping relationships."""
    payload = policy if policy is not None else load_discovery_policy()
    capabilities = _capability_map()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    seen_capabilities: set[str] = set()

    for category in payload.get("categories", []):
        if not isinstance(category, dict) or not category.get("id"):
            continue
        category_id = str(category["id"])
        status = str(category.get("supportStatus") or "unknown")
        category_key = f"discovery-category:{category_id}"
        selected_scaffold = _selected_scaffold(category)
        target_scaffold = str(category.get("targetScaffoldId") or "")
        default_variant = str(category.get("defaultVariantId") or "")
        expected_starter = str(category.get("expectedStarterId") or "")

        nodes.append(
            _node(
                node_type="discovery-category",
                node_id=category_id,
                path=DISCOVERY_TAXONOMY_PATH,
                status=status,
                canonical=True,
                details=str(category.get("labelSv") or ""),
            )
        )
        if target_scaffold:
            edges.append(
                _edge(
                    category_key,
                    f"scaffold:{target_scaffold}",
                    "target-scaffold",
                    str(category.get("rationale") or ""),
                )
            )
        if selected_scaffold:
            relation = "active-scaffold" if status == "active" else "fallback-scaffold"
            edges.append(_edge(category_key, f"scaffold:{selected_scaffold}", relation))
        if default_variant and selected_scaffold:
            edges.append(
                _edge(
                    f"scaffold:{selected_scaffold}",
                    f"variant:{default_variant}",
                    "default-variant",
                    f"category:{category_id}",
                )
            )
        if expected_starter and selected_scaffold:
            edges.append(
                _edge(
                    f"scaffold:{selected_scaffold}",
                    f"starter:{expected_starter}",
                    "expected-starter",
                    f"category:{category_id}",
                )
            )

        requested = [
            str(capability)
            for capability in category.get("requestedCapabilities", []) or []
            if isinstance(capability, str)
        ]
        candidate_dossiers = [
            str(dossier)
            for dossier in category.get("candidateDossiers", []) or []
            if isinstance(dossier, str)
        ]
        for capability_id in requested:
            if capability_id not in seen_capabilities:
                seen_capabilities.add(capability_id)
                nodes.append(
                    _node(
                        node_type="capability",
                        node_id=capability_id,
                        path=CAPABILITY_MAP_PATH,
                        status=_capability_status(capability_id, capabilities),
                        canonical=capability_id in capabilities,
                        details=str(capabilities.get(capability_id, {}).get("comment") or ""),
                    )
                )
            edges.append(_edge(category_key, f"capability:{capability_id}", "requests"))

            entry = capabilities.get(capability_id) or {}
            for dossier_id in entry.get("dossiers") or []:
                if isinstance(dossier_id, str) and dossier_id:
                    edges.append(
                        _edge(
                            f"capability:{capability_id}",
                            _dossier_node_key(dossier_id),
                            "implemented-by",
                        )
                    )
            for dossier_id in candidate_dossiers:
                edges.append(
                    _edge(
                        f"capability:{capability_id}",
                        _dossier_node_key(dossier_id),
                        "candidate-dossier",
                        f"category:{category_id}",
                    )
                )

    return {"nodes": nodes, "edges": edges}


def discovery_doctor_findings(policy: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Return Doctor findings for Discovery mapping governance."""
    payload = policy if policy is not None else load_discovery_policy()
    registry = _scaffold_registry()
    runtime_map = _runtime_mapping()
    capabilities = _capability_map()
    findings: list[dict[str, str]] = []

    for category in payload.get("categories", []):
        if not isinstance(category, dict) or not category.get("id"):
            continue
        findings.extend(_category_findings(category, registry, runtime_map, capabilities))
    return findings


def _finding(
    *,
    level: str,
    finding_id: str,
    message: str,
    details: str,
    path: Path = DISCOVERY_TAXONOMY_PATH,
) -> dict[str, str]:
    return {
        "level": level,
        "id": finding_id,
        "message": message,
        "path": _repo_relative(path),
        "details": details,
    }


def _category_findings(
    category: dict[str, Any],
    registry: set[str],
    runtime_map: dict[str, str],
    capabilities: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    category_id = str(category["id"])
    status = str(category.get("supportStatus") or "")
    target_scaffold = str(category.get("targetScaffoldId") or "")
    selected_scaffold = _selected_scaffold(category)
    default_variant = str(category.get("defaultVariantId") or "")
    expected_starter = category.get("expectedStarterId")
    findings: list[dict[str, str]] = []

    if status not in SUPPORT_STATUSES:
        findings.append(
            _finding(
                level="error",
                finding_id=f"discovery-support-status:{category_id}",
                message=f"{category_id} har ogiltig supportStatus.",
                details=status,
            )
        )

    if target_scaffold not in registry:
        findings.append(
            _finding(
                level="error",
                finding_id=f"discovery-target-scaffold:{category_id}",
                message=f"{category_id} pekar mot okänd targetScaffoldId.",
                details=target_scaffold,
            )
        )
    elif target_scaffold not in runtime_map and status == "active":
        findings.append(
            _finding(
                level="error",
                finding_id=f"discovery-target-runtime:{category_id}",
                message=f"{category_id} har runtime-status men target saknar runtime-mapping.",
                details=target_scaffold,
            )
        )
    elif target_scaffold not in runtime_map and status in {"fallback", "planned"}:
        findings.append(
            _finding(
                level="warning",
                finding_id=f"discovery-target-runtime:{category_id}",
                message=f"{category_id} target-scaffold saknar runtime-mapping och kör via fallback.",
                details=target_scaffold,
            )
        )

    if selected_scaffold and selected_scaffold not in registry:
        findings.append(
            _finding(
                level="error",
                finding_id=f"discovery-selected-scaffold:{category_id}",
                message=f"{category_id} pekar mot okänd buildbar scaffold.",
                details=selected_scaffold,
            )
        )
    if selected_scaffold and selected_scaffold not in runtime_map and status != "disabled":
        findings.append(
            _finding(
                level="error",
                finding_id=f"discovery-selected-runtime:{category_id}",
                message=f"{category_id} pekar mot scaffold som saknar runtime-mapping.",
                details=selected_scaffold,
            )
        )

    if selected_scaffold in runtime_map:
        if not default_variant:
            findings.append(
                _finding(
                    level="error",
                    finding_id=f"discovery-default-variant:{category_id}",
                    message=f"{category_id} saknar defaultVariantId för vald buildbar scaffold.",
                    details=selected_scaffold,
                )
            )
        else:
            variant_path = _variant_path(selected_scaffold, default_variant)
            if not variant_path.exists():
                findings.append(
                    _finding(
                        level="error",
                        finding_id=f"discovery-default-variant:{category_id}",
                        message=f"{category_id} defaultVariantId saknas under vald scaffold.",
                        details=f"{selected_scaffold}/{default_variant}",
                    )
                )
            else:
                try:
                    from packages.generation.artifacts import validate_variant

                    validate_variant(_read_json(variant_path))
                except Exception as exc:  # noqa: BLE001
                    findings.append(
                        _finding(
                            level="error",
                            finding_id=f"discovery-default-variant:{category_id}",
                            message=f"{category_id} defaultVariantId pekar på ogiltig Variant.",
                            details=str(exc),
                            path=variant_path,
                        )
                    )

        actual_starter = runtime_map[selected_scaffold]
        if not expected_starter:
            findings.append(
                _finding(
                    level="error",
                    finding_id=f"discovery-starter-mapping:{category_id}",
                    message=f"{category_id} saknar expectedStarterId för vald scaffold.",
                    details=selected_scaffold,
                )
            )
        elif expected_starter != actual_starter:
            findings.append(
                _finding(
                    level="error",
                    finding_id=f"discovery-starter-mapping:{category_id}",
                    message=f"{category_id} expectedStarterId matchar inte planning.SCAFFOLD_TO_STARTER.",
                    details=f"expected={expected_starter!r}, actual={actual_starter!r}",
                )
            )

    for capability_id in category.get("requestedCapabilities", []) or []:
        if not isinstance(capability_id, str):
            continue
        entry = capabilities.get(capability_id)
        if entry is None:
            findings.append(
                _finding(
                    level="error",
                    finding_id=f"discovery-capability:{category_id}:{capability_id}",
                    message=f"{category_id} requestedCapability saknas i capability-map.",
                    details=capability_id,
                )
            )
            continue
        if not (entry.get("dossiers") or []):
            findings.append(
                _finding(
                    level="warning",
                    finding_id=f"discovery-capability-gap:{category_id}:{capability_id}",
                    message=f"{category_id} requestedCapability saknar implementerad Dossier.",
                    details=str(entry.get("comment") or capability_id),
                )
            )

    for dossier_id in category.get("candidateDossiers", []) or []:
        if not isinstance(dossier_id, str):
            continue
        if _dossier_manifest_path(dossier_id) is None:
            findings.append(
                _finding(
                    level="error",
                    finding_id=f"discovery-candidate-dossier:{category_id}:{dossier_id}",
                    message=f"{category_id} candidateDossier saknar soft/hard manifest.",
                    details=dossier_id,
                )
            )

    return findings


def discovery_gap_rows(policy: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Return Discovery-specific gap/orphan rows for the impact view."""
    return [
        {
            "level": finding["level"],
            "id": finding["id"],
            "gap": finding["message"],
            "details": finding["details"],
            "path": finding["path"],
        }
        for finding in discovery_doctor_findings(policy)
        if finding["level"] in {"error", "warning", "info"}
    ]


def sample_discovery_payload(category_id: str) -> dict[str, Any]:
    """Return a minimal Discovery Payload for Backoffice dry-run."""
    policy = load_discovery_policy()
    category = next(
        (
            item
            for item in policy.get("categories", [])
            if isinstance(item, dict) and item.get("id") == category_id
        ),
        {},
    )
    scaffold_hint = (
        _selected_scaffold(category)
        if isinstance(category, dict) and category
        else "local-service-business"
    )
    return {
        "schemaVersion": 1,
        "rawPrompt": f"Backoffice dry-run for {category_id}",
        "contentBranch": str(category.get("contentBranch") or "business"),
        "scaffoldHint": scaffold_hint,
        "answers": {
            "siteType": [category_id],
            "companyName": "Demo AB",
            "offer": "Demoerbjudande for en liten foretagshemsida.",
            "contact": {"email": "demo@example.se"},
        },
    }


def sample_project_input() -> dict[str, Any]:
    """Return a minimal Project Input candidate used only for dry-run."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "backoffice-discovery-dry-run",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Demo AB",
            "businessType": "service-provider",
            "tagline": "Demo tagline",
            "story": "Demo story",
        },
        "location": {"city": "Malmo", "country": "Sverige", "serviceAreas": ["Malmo"]},
        "services": [{"id": "demo", "label": "Demo", "summary": "Demo."}],
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "brief@example.se",
            "addressLines": ["Demo adress"],
            "openingHours": "Man-Fre 09:00-17:00",
        },
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "dry-run"},
    }


def run_discovery_dry_run(category_id: str) -> dict[str, Any]:
    """Run Discovery Resolver without writing Project Inputs or run artefacts."""
    from packages.generation.discovery import resolve_discovery

    payload = sample_discovery_payload(category_id)
    project_input, decision = resolve_discovery(
        raw_prompt=str(payload["rawPrompt"]),
        payload=payload,
        project_input_candidate=sample_project_input(),
    )
    return {
        "categoryId": category_id,
        "projectInput": project_input,
        "decision": decision.to_dict(),
        "fieldSources": decision.fieldSources,
        "fallbackWarnings": [warning.to_dict() for warning in decision.fallbackWarnings],
    }


def proposed_policy_update(
    category_id: str,
    updates: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    allow_warnings: bool = True,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Return a validated Discovery policy copy with one category edited."""
    payload = copy.deepcopy(policy if policy is not None else load_discovery_policy())
    unknown = sorted(set(updates) - EDITABLE_CATEGORY_FIELDS)
    if unknown:
        raise ValueError(
            "Discovery edit can only update these fields: "
            + ", ".join(sorted(EDITABLE_CATEGORY_FIELDS))
            + f". Rejected: {', '.join(unknown)}"
        )

    for category in payload.get("categories", []):
        if isinstance(category, dict) and category.get("id") == category_id:
            _apply_category_updates(category, updates)
            _sync_expected_starter(category)
            _validate_policy_schema(payload)
            findings = discovery_doctor_findings(payload)
            blocking_levels = {"error"} if allow_warnings else {"error", "warning"}
            blocking = [
                finding for finding in findings if finding["level"] in blocking_levels
            ]
            if blocking:
                details = "; ".join(f"{f['id']}: {f['details']}" for f in blocking[:5])
                raise ValueError(f"Discovery edit failed validation: {details}")
            return payload, findings

    raise ValueError(f"Unknown discovery category: {category_id}")


def _validate_policy_schema(payload: dict[str, Any]) -> None:
    import jsonschema

    schema = _read_json(DISCOVERY_TAXONOMY_SCHEMA_PATH)
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: error.path,
    )
    if errors:
        first = errors[0]
        location = first.json_path or "$"
        raise ValueError(
            f"Discovery taxonomy schema validation failed at {location}: {first.message}"
        )


def _apply_category_updates(category: dict[str, Any], updates: dict[str, Any]) -> None:
    for field_name, value in updates.items():
        if field_name in {"requestedCapabilities", "candidateDossiers"}:
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item for item in value
            ):
                raise ValueError(f"{field_name} must be a list of non-empty strings")
            category[field_name] = list(dict.fromkeys(value))
            continue
        if field_name == "supportStatus":
            if value not in SUPPORT_STATUSES:
                raise ValueError(
                    f"supportStatus must be one of {sorted(SUPPORT_STATUSES)}"
                )
            category[field_name] = value
            continue
        if field_name in {"activeScaffoldId", "fallbackScaffoldId", "operatorNotes"} and (
            value is None or value == ""
        ):
            category.pop(field_name, None)
            continue
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        category[field_name] = value


def _sync_expected_starter(category: dict[str, Any]) -> None:
    runtime_map = _runtime_mapping()
    selected_scaffold = _selected_scaffold(category)
    expected_starter = runtime_map.get(selected_scaffold)
    if expected_starter is not None:
        category["expectedStarterId"] = expected_starter


def save_category_update(
    category_id: str,
    updates: dict[str, Any],
    *,
    policy_path: Path | None = None,
    write: bool,
    allow_warnings: bool = True,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Validate a category edit and optionally write it atomically."""
    path = policy_path or DISCOVERY_TAXONOMY_PATH
    payload = load_discovery_policy(path)
    proposed, findings = proposed_policy_update(
        category_id,
        updates,
        policy=payload,
        allow_warnings=allow_warnings,
    )
    if write:
        atomic_write_json(path, proposed)
    return proposed, findings


__all__ = [
    "DISCOVERY_TAXONOMY_PATH",
    "EDITABLE_CATEGORY_FIELDS",
    "build_discovery_graph",
    "category_mapping_rows",
    "discovery_doctor_findings",
    "discovery_gap_rows",
    "load_discovery_policy",
    "proposed_policy_update",
    "run_discovery_dry_run",
    "save_category_update",
]
