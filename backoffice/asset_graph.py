"""Read-only graph and health helpers for Backoffice building blocks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import DATA_DIR, POLICIES_DIR, REPO_ROOT

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
STARTERS_DIR = DATA_DIR / "starters"
VARIANT_CANDIDATES_DIR = DATA_DIR / "variant-candidates"
DOSSIER_CANDIDATES_DIR = DATA_DIR / "dossier-candidates"
EMBEDDING_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "embedding"
PLACEHOLDER_MARKER = "placeholder, fill per scaffold-contract"
ATTENTION_STATUSES = {"gap", "orphan", "missing-on-disk", "unknown"}
UNKNOWN_CANDIDATE_SOURCE = "unknown-existing"


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_candidate_metadata(path: Path) -> dict[str, Any]:
    """Read candidate sidecar metadata without blocking legacy candidates."""
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _metadata_string(
    metadata: dict[str, Any],
    key: str,
    default: str = "",
) -> str:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else default


def _candidate_provenance(meta_path: Path) -> dict[str, Any]:
    metadata = _read_candidate_metadata(meta_path)
    provenance = {
        "source": _metadata_string(
            metadata,
            "source",
            UNKNOWN_CANDIDATE_SOURCE,
        ),
        "modelUsed": _metadata_string(metadata, "modelUsed"),
        "createdAt": _metadata_string(metadata, "createdAt"),
        "metaPath": repo_relative(meta_path) if metadata else "",
    }
    return provenance


def repo_relative(path: Path) -> str:
    """Return a readable repo-relative path."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_policy(filename: str) -> dict[str, Any]:
    """Read one governance policy without Streamlit cache dependencies."""
    return read_json(POLICIES_DIR / filename)


def scaffold_required_files(contract: dict[str, Any] | None = None) -> list[str]:
    """Return required Scaffold files from scaffold-contract.v1.json."""
    payload = contract if contract is not None else load_policy("scaffold-contract.v1.json")
    files = payload.get("scaffoldDirectoryLayout", {}).get("requiredFiles", [])
    return [str(file_name) for file_name in files]


def dossier_classes(contract: dict[str, Any] | None = None) -> list[str]:
    """Return canonical Dossier classes from dossier-contract.v1.json."""
    payload = contract if contract is not None else load_policy("dossier-contract.v1.json")
    return [
        str(entry["class"])
        for entry in payload.get("dossierClasses", [])
        if isinstance(entry, dict) and entry.get("class")
    ]


def is_placeholder_file(path: Path) -> bool:
    """Return True when a scaffold file is a Backoffice placeholder."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if PLACEHOLDER_MARKER in text:
        return True
    if path.suffix != ".json":
        return False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and "_status" in payload


def scaffold_file_state(scaffold_dir: Path, required_files: list[str]) -> dict[str, Any]:
    """Summarise required file state for one Scaffold directory."""
    missing: list[str] = []
    placeholders: list[str] = []
    present: list[str] = []
    for relative_path in required_files:
        path = scaffold_dir / relative_path
        if not path.exists():
            missing.append(relative_path)
            continue
        if is_placeholder_file(path):
            placeholders.append(relative_path)
            continue
        present.append(relative_path)

    if missing:
        status = "incomplete"
    elif placeholders:
        status = "placeholder"
    else:
        status = "implemented"
    return {
        "status": status,
        "present": present,
        "missing": missing,
        "placeholders": placeholders,
    }


def scaffold_is_real(scaffold_dir: Path, required_files: list[str] | None = None) -> bool:
    """A Scaffold is real only when every required file exists and is not a placeholder."""
    files = required_files if required_files is not None else scaffold_required_files()
    if not scaffold_dir.exists():
        return False
    return scaffold_file_state(scaffold_dir, files)["status"] == "implemented"


def list_scaffold_dirs(scaffolds_dir: Path | None = None) -> list[Path]:
    """List Scaffold directories."""
    base = scaffolds_dir if scaffolds_dir is not None else SCAFFOLDS_DIR
    if not base.exists():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir())


def list_dossier_dirs(
    dossiers_dir: Path | None = None,
    *,
    classes: list[str] | None = None,
) -> list[tuple[str, Path]]:
    """List Dossier directories for canonical classes only."""
    base = dossiers_dir if dossiers_dir is not None else DOSSIERS_DIR
    allowed_classes = classes if classes is not None else dossier_classes()
    out: list[tuple[str, Path]] = []
    for dossier_class in allowed_classes:
        class_dir = base / dossier_class
        if not class_dir.exists():
            continue
        for path in sorted(class_dir.iterdir()):
            if path.is_dir():
                out.append((dossier_class, path))
    return out


def list_unregistered_dossier_class_dirs(
    dossiers_dir: Path | None = None,
    *,
    classes: list[str] | None = None,
) -> list[Path]:
    """Return Dossier class directories not declared in the Dossier contract."""
    base = dossiers_dir if dossiers_dir is not None else DOSSIERS_DIR
    allowed = set(classes if classes is not None else dossier_classes())
    if not base.exists():
        return []
    return sorted(
        path for path in base.iterdir() if path.is_dir() and path.name not in allowed
    )


def _enabled(payload: dict[str, Any]) -> bool | None:
    value = payload.get("enabled")
    return value if isinstance(value, bool) else None


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
        "path": repo_relative(path),
        "status": status,
        "canonical": canonical,
        "enabled": enabled,
        "details": details,
    }


def _edge(source: str, target: str, relation: str, details: str = "") -> dict[str, str]:
    return {"from": source, "to": target, "relation": relation, "details": details}


def _runtime_mapping() -> dict[str, str]:
    """Return the runtime Scaffold to Starter mapping."""
    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER

    return dict(SCAFFOLD_TO_STARTER)


def _scaffold_registry_by_id(
    contract: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return scaffold-contract registry entries keyed by Scaffold id."""
    payload = contract if contract is not None else load_policy("scaffold-contract.v1.json")
    return {
        str(entry["id"]): entry
        for entry in payload.get("primaryScaffoldRegistry", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def _starter_registry_by_id(
    registry: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return starter-registry entries keyed by Starter id."""
    payload = registry if registry is not None else load_policy("starter-registry.v1.json")
    return {
        str(entry["id"]): entry
        for entry in payload.get("starters", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def _capability_entries(
    policy: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return capability-map entries keyed by Capability id."""
    payload = policy if policy is not None else load_policy("capability-map.v1.json")
    capabilities = payload.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return {}
    return {
        str(capability_id): entry
        for capability_id, entry in capabilities.items()
        if isinstance(entry, dict)
    }


def _status_needs_attention(status: str) -> bool:
    """Return whether a row status represents a gap, orphan, missing or unknown asset."""
    return status in ATTENTION_STATUSES


def _comma_join(values: list[str] | tuple[str, ...] | set[str]) -> str:
    """Return stable comma-separated display text for dataframe cells."""
    return ", ".join(sorted(str(value) for value in values if str(value)))


def _truthy_gap(value: Any) -> bool:
    """Return True when a dataframe row gap flag is truthy."""
    return value is True or str(value).lower() in {"ja", "true", "1"}


def _categories_by_capability(
    taxonomy: dict[str, Any],
) -> dict[str, list[str]]:
    """Return Discovery category ids grouped by requested Capability."""
    by_capability: dict[str, list[str]] = {}
    for category in taxonomy.get("categories", []) or []:
        if not isinstance(category, dict) or not isinstance(category.get("id"), str):
            continue
        category_id = str(category["id"])
        for capability_id in category.get("requestedCapabilities", []) or []:
            if isinstance(capability_id, str) and capability_id:
                by_capability.setdefault(capability_id, []).append(category_id)
    return by_capability


def _categories_by_scaffold(
    taxonomy: dict[str, Any],
) -> dict[str, list[str]]:
    """Return Discovery category ids grouped by any scaffold reference."""
    by_scaffold: dict[str, list[str]] = {}
    for category in taxonomy.get("categories", []) or []:
        if not isinstance(category, dict) or not isinstance(category.get("id"), str):
            continue
        category_id = str(category["id"])
        scaffold_ids = {
            str(category.get(field_name) or "")
            for field_name in (
                "targetScaffoldId",
                "activeScaffoldId",
                "fallbackScaffoldId",
            )
        }
        for scaffold_id in sorted(scaffold_ids):
            if scaffold_id:
                by_scaffold.setdefault(scaffold_id, []).append(category_id)
    return by_scaffold


def _scaffold_id_and_label(scaffold_dir: Path) -> tuple[str, str]:
    """Return the Scaffold id and label declared by a directory."""
    scaffold_json = scaffold_dir / "scaffold.json"
    if scaffold_json.exists() and not is_placeholder_file(scaffold_json):
        try:
            payload = read_json(scaffold_json)
        except (OSError, ValueError, json.JSONDecodeError):
            return scaffold_dir.name, ""
        return (
            str(payload.get("id") or scaffold_dir.name),
            str(payload.get("label") or ""),
        )
    return scaffold_dir.name, ""


def _variant_ids_for_scaffold(scaffold_dir: Path) -> list[str]:
    """Return canonical Variant ids found under one Scaffold directory."""
    variants_dir = scaffold_dir / "variants"
    if not variants_dir.exists():
        return []
    variant_ids: list[str] = []
    for variant_path in sorted(variants_dir.glob("*.json")):
        try:
            payload = read_json(variant_path)
            variant_ids.append(str(payload.get("id") or variant_path.stem))
        except (OSError, ValueError, json.JSONDecodeError):
            variant_ids.append(variant_path.stem)
    return variant_ids


def _starter_path(starter: dict[str, Any] | None, starter_id: str) -> Path:
    """Return the expected on-disk path for one Starter."""
    if starter and isinstance(starter.get("path"), str) and starter["path"]:
        return REPO_ROOT / starter["path"]
    return STARTERS_DIR / starter_id


def _starter_status(
    *,
    starter_id: str,
    registry_entry: dict[str, Any] | None,
    on_disk: bool,
    runtime_scaffolds: list[str],
) -> str:
    """Return the Asset Graph row status for one Starter."""
    registry_status = str(registry_entry.get("status", "")) if registry_entry else ""
    enabled = _enabled(registry_entry or {})
    if registry_entry is None and on_disk:
        return "orphan"
    if enabled is False:
        return "disabled"
    if not on_disk:
        return "missing-on-disk"
    if runtime_scaffolds:
        return "active-runtime"
    if registry_status in {
        "active",
        "fallback",
        "planned",
        "disabled",
        "active-runtime",
        "available-not-mapped",
        "placeholder",
    }:
        return registry_status
    return "unknown"


def _capability_status(
    *,
    entry: dict[str, Any] | None,
    dossier_ids: list[str],
    missing_dossier_ids: list[str],
) -> str:
    """Return the Asset Graph row status for one Capability."""
    if entry is None:
        return "unknown"
    if missing_dossier_ids:
        return "unknown"
    if not dossier_ids:
        return "gap"
    return "active"


def _compatible_dossier_id(entry: Any) -> str | None:
    """Return a Dossier id from a compatible-dossiers entry."""
    if isinstance(entry, str) and entry.strip():
        return entry.strip()
    if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"].strip():
        return entry["id"].strip()
    return None


def _compatible_dossier_details(entry: Any) -> str:
    """Return operator-readable details from a compatible-dossiers entry."""
    if not isinstance(entry, dict):
        return ""
    when = entry.get("when")
    return str(when) if when else ""


def _compatible_dossier_edges(
    scaffold_id: str,
    compatible: dict[str, Any],
    dossier_class_by_id: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Return graph edges from one Scaffold to compatible Dossiers.

    Edges must use the same ``{type}:{id}`` key format that the corresponding
    Dossier nodes are registered with, otherwise the Backoffice impact view
    cannot connect Scaffolds to their Dossiers. Dossier nodes use
    ``{class}-dossier:{id}`` (per :func:`build_graph`); resolve the class via
    ``dossier_class_by_id`` so edges target the same key. When the id is not
    registered we fall back to ``dossier:{id}`` which intentionally leaves an
    orphan-edge that :func:`run_health_checks` flags as "okänd Dossier".
    """
    edges: list[dict[str, str]] = []
    class_map = dossier_class_by_id or {}
    for relation in ("required", "recommended", "conditional"):
        entries = compatible.get(relation, []) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            dossier_id = _compatible_dossier_id(entry)
            if dossier_id is None:
                continue
            dossier_class = class_map.get(dossier_id)
            target_type = f"{dossier_class}-dossier" if dossier_class else "dossier"
            edges.append(
                _edge(
                    f"scaffold:{scaffold_id}",
                    f"{target_type}:{dossier_id}",
                    relation,
                    _compatible_dossier_details(entry),
                )
            )
    return edges


def _variant_nodes_for_scaffold(scaffold_dir: Path, scaffold_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    variants_dir = scaffold_dir / "variants"
    if not variants_dir.exists():
        return nodes, edges
    for variant_path in sorted(variants_dir.glob("*.json")):
        payload = read_json(variant_path)
        variant_id = str(payload.get("id") or variant_path.stem)
        nodes.append(
            _node(
                node_type="variant",
                node_id=variant_id,
                path=variant_path,
                status="canonical",
                canonical=True,
                enabled=_enabled(payload),
                details=str(payload.get("label") or ""),
            )
        )
        edges.append(_edge(f"scaffold:{scaffold_id}", f"variant:{variant_id}", "owns"))
    return nodes, edges


def _candidate_variant_nodes(scaffold_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    candidates_dir = VARIANT_CANDIDATES_DIR / scaffold_id
    if not candidates_dir.exists():
        return nodes, edges
    for candidate_path in sorted(candidates_dir.glob("*.json")):
        if candidate_path.name.endswith(".meta.json"):
            continue
        provenance = _candidate_provenance(
            candidate_path.with_name(f"{candidate_path.stem}.meta.json")
        )
        try:
            payload = read_json(candidate_path)
            status = "candidate"
            enabled = _enabled(payload)
            details = str(payload.get("label") or "")
            candidate_id = str(payload.get("id") or candidate_path.stem)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            status = "invalid"
            enabled = None
            details = str(exc)
            candidate_id = candidate_path.stem
        node_id = f"{scaffold_id}/{candidate_id}"
        nodes.append(
            _node(
                node_type="variant-candidate",
                node_id=node_id,
                path=candidate_path,
                status=status,
                canonical=False,
                enabled=enabled,
                details=details,
            )
        )
        nodes[-1].update(provenance)
        edges.append(
            _edge(
                f"scaffold:{scaffold_id}",
                f"variant-candidate:{node_id}",
                "candidate-for",
            )
        )
    return nodes, edges


def _candidate_dossier_nodes() -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if not DOSSIER_CANDIDATES_DIR.exists():
        return nodes
    for candidate_class_dir in sorted(path for path in DOSSIER_CANDIDATES_DIR.iterdir() if path.is_dir()):
        dossier_class = candidate_class_dir.name
        for candidate_dir in sorted(path for path in candidate_class_dir.iterdir() if path.is_dir()):
            manifest_path = candidate_dir / "manifest.json"
            provenance = _candidate_provenance(candidate_dir / "meta.json")
            if not manifest_path.exists():
                nodes.append(
                    _node(
                        node_type="dossier-candidate",
                        node_id=f"{dossier_class}/{candidate_dir.name}",
                        path=candidate_dir,
                        status="incomplete",
                        canonical=False,
                        details="manifest.json saknas",
                    )
                )
                nodes[-1].update(provenance)
                continue
            try:
                payload = read_json(manifest_path)
                status = "candidate"
                enabled = _enabled(payload)
                candidate_id = str(payload.get("id") or candidate_dir.name)
                details = str(payload.get("capability") or payload.get("summary") or "")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                status = "invalid"
                enabled = None
                candidate_id = candidate_dir.name
                details = str(exc)
            nodes.append(
                _node(
                    node_type="dossier-candidate",
                    node_id=f"{dossier_class}/{candidate_id}",
                    path=candidate_dir,
                    status=status,
                    canonical=False,
                    enabled=enabled,
                    details=details,
                )
            )
            nodes[-1].update(provenance)
    return nodes


def asset_graph_category_rows() -> list[dict[str, Any]]:
    """Return read-only Asset Graph rows for Discovery categories."""
    from . import discovery_control

    taxonomy = load_policy("discovery-taxonomy.v1.json")
    capability_entries = _capability_entries()
    mapping_rows = discovery_control.category_mapping_rows(taxonomy)
    rows: list[dict[str, Any]] = []
    for mapping_row in mapping_rows:
        category_id = str(mapping_row.get("categoryId") or "")
        category = next(
            (
                item
                for item in taxonomy.get("categories", [])
                if isinstance(item, dict) and item.get("id") == category_id
            ),
            {},
        )
        requested = [
            str(capability_id)
            for capability_id in category.get("requestedCapabilities", []) or []
            if isinstance(capability_id, str)
        ]
        capability_gaps = [
            capability_id
            for capability_id in requested
            if capability_id in capability_entries
            and not (capability_entries[capability_id].get("dossiers") or [])
        ]
        unknown_capabilities = [
            capability_id
            for capability_id in requested
            if capability_id not in capability_entries
        ]
        support_status = str(mapping_row.get("supportStatus") or "unknown")
        status = (
            support_status
            if support_status in {"active", "fallback", "planned", "disabled"}
            else "unknown"
        )
        mapping_state = str(mapping_row.get("mappingState") or "")
        gap_or_orphan = bool(
            capability_gaps
            or unknown_capabilities
            or mapping_state in {"orphan", "unknown"}
        )
        rows.append(
            {
                "categoryId": category_id,
                "label": str(mapping_row.get("label") or ""),
                "status": status,
                "supportStatus": support_status,
                "mappingState": mapping_state,
                "targetScaffoldId": str(mapping_row.get("targetScaffoldId") or ""),
                "activeScaffoldId": str(mapping_row.get("activeScaffoldId") or ""),
                "fallbackScaffoldId": str(mapping_row.get("fallbackScaffoldId") or ""),
                "defaultVariantId": str(mapping_row.get("defaultVariantId") or ""),
                "expectedStarterId": str(mapping_row.get("expectedStarterId") or ""),
                "requestedCapabilities": _comma_join(requested),
                "candidateDossiers": str(mapping_row.get("candidateDossiers") or ""),
                "capabilityGaps": _comma_join(capability_gaps),
                "unknownCapabilities": _comma_join(unknown_capabilities),
                "gapOrOrphan": gap_or_orphan,
                "fallbackWarnings": str(mapping_row.get("fallbackWarnings") or ""),
                "rationale": str(mapping_row.get("rationale") or ""),
            }
        )
    return rows


def asset_graph_scaffold_rows() -> list[dict[str, Any]]:
    """Return read-only Asset Graph rows for Scaffolds."""
    contract = load_policy("scaffold-contract.v1.json")
    starter_registry = _starter_registry_by_id()
    taxonomy = load_policy("discovery-taxonomy.v1.json")
    runtime_map = _runtime_mapping()
    required_files = scaffold_required_files(contract)
    registry = _scaffold_registry_by_id(contract)
    category_refs = _categories_by_scaffold(taxonomy)
    on_disk_dirs: dict[str, Path] = {}
    on_disk_labels: dict[str, str] = {}
    for scaffold_dir in list_scaffold_dirs():
        scaffold_id, label = _scaffold_id_and_label(scaffold_dir)
        on_disk_dirs[scaffold_id] = scaffold_dir
        on_disk_labels[scaffold_id] = label

    all_scaffold_ids = sorted(set(registry) | set(on_disk_dirs) | set(runtime_map))
    rows: list[dict[str, Any]] = []
    for scaffold_id in all_scaffold_ids:
        registry_entry = registry.get(scaffold_id)
        scaffold_dir = on_disk_dirs.get(scaffold_id)
        on_disk = scaffold_dir is not None
        path = scaffold_dir if scaffold_dir is not None else SCAFFOLDS_DIR / scaffold_id
        enabled = _enabled(registry_entry or {})
        if scaffold_dir is not None:
            file_state = scaffold_file_state(scaffold_dir, required_files)
            variant_ids = _variant_ids_for_scaffold(scaffold_dir)
        else:
            file_state = {
                "status": "missing",
                "missing": list(required_files),
                "placeholders": [],
            }
            variant_ids = []

        runtime_starter = runtime_map.get(scaffold_id, "")
        if registry_entry is None and on_disk:
            status = "orphan"
        elif enabled is False:
            status = "disabled"
        elif not on_disk:
            status = "missing-on-disk"
        elif file_state["status"] == "placeholder":
            status = "placeholder"
        elif file_state["status"] != "implemented":
            status = "missing-on-disk"
        elif runtime_starter:
            status = "active-runtime"
        elif registry_entry is not None:
            status = "planned"
        else:
            status = "unknown"

        starter_status = ""
        if runtime_starter:
            starter_status = str(
                starter_registry.get(runtime_starter, {}).get("status") or "unknown"
            )
        rows.append(
            {
                "scaffoldId": scaffold_id,
                "label": str(
                    (registry_entry or {}).get("label")
                    or on_disk_labels.get(scaffold_id)
                    or ""
                ),
                "status": status,
                "enabled": enabled,
                "onDisk": on_disk,
                "path": repo_relative(path),
                "fileState": str(file_state["status"]),
                "missingFiles": _comma_join(file_state.get("missing", [])),
                "placeholderFiles": _comma_join(file_state.get("placeholders", [])),
                "variantIds": _comma_join(variant_ids),
                "runtimeStarterId": runtime_starter,
                "starterStatus": starter_status,
                "referencedByCategories": _comma_join(category_refs.get(scaffold_id, [])),
                "gapOrOrphan": _status_needs_attention(status),
            }
        )
    return rows


def asset_graph_starter_rows() -> list[dict[str, Any]]:
    """Return read-only Asset Graph rows for Starters."""
    registry = _starter_registry_by_id()
    runtime_map = _runtime_mapping()
    runtime_scaffolds_by_starter: dict[str, list[str]] = {}
    for scaffold_id, starter_id in runtime_map.items():
        runtime_scaffolds_by_starter.setdefault(starter_id, []).append(scaffold_id)

    on_disk_ids: set[str] = set()
    if STARTERS_DIR.exists():
        on_disk_ids = {
            path.name for path in STARTERS_DIR.iterdir() if path.is_dir()
        }
    all_starter_ids = sorted(
        set(registry) | set(runtime_scaffolds_by_starter) | on_disk_ids
    )
    rows: list[dict[str, Any]] = []
    for starter_id in all_starter_ids:
        registry_entry = registry.get(starter_id)
        path = _starter_path(registry_entry, starter_id)
        on_disk = path.exists()
        runtime_scaffolds = sorted(runtime_scaffolds_by_starter.get(starter_id, []))
        status = _starter_status(
            starter_id=starter_id,
            registry_entry=registry_entry,
            on_disk=on_disk,
            runtime_scaffolds=runtime_scaffolds,
        )
        rows.append(
            {
                "starterId": starter_id,
                "label": str((registry_entry or {}).get("label") or ""),
                "status": status,
                "enabled": _enabled(registry_entry or {}),
                "onDisk": on_disk,
                "path": repo_relative(path),
                "registryStatus": str((registry_entry or {}).get("status") or ""),
                "runtimeMappedScaffolds": _comma_join(runtime_scaffolds),
                "runtimeMappedScaffoldCount": len(runtime_scaffolds),
                "gapOrOrphan": _status_needs_attention(status),
                "rationale": str((registry_entry or {}).get("rationale") or ""),
            }
        )
    return rows


def asset_graph_capability_rows() -> list[dict[str, Any]]:
    """Return read-only Asset Graph rows for Capabilities and their Dossiers."""
    capability_entries = _capability_entries()
    taxonomy = load_policy("discovery-taxonomy.v1.json")
    category_refs = _categories_by_capability(taxonomy)
    classes = dossier_classes()
    dossier_manifests = _dossier_manifests_by_id(classes=classes)
    all_capability_ids = sorted(set(capability_entries) | set(category_refs))
    rows: list[dict[str, Any]] = []
    for capability_id in all_capability_ids:
        entry = capability_entries.get(capability_id)
        dossier_ids = [
            str(dossier_id)
            for dossier_id in (entry or {}).get("dossiers", []) or []
            if isinstance(dossier_id, str) and dossier_id
        ]
        missing_dossier_ids = [
            dossier_id for dossier_id in dossier_ids if dossier_id not in dossier_manifests
        ]
        status = _capability_status(
            entry=entry,
            dossier_ids=dossier_ids,
            missing_dossier_ids=missing_dossier_ids,
        )
        referenced_by = sorted(category_refs.get(capability_id, []))
        rows.append(
            {
                "capabilityId": capability_id,
                "status": status,
                "dossierIds": _comma_join(dossier_ids),
                "defaultDossierId": str((entry or {}).get("default") or ""),
                "dossierCount": len(dossier_ids),
                "missingDossierIds": _comma_join(missing_dossier_ids),
                "referencedByCategories": _comma_join(referenced_by),
                "categoryCount": len(referenced_by),
                "comment": str((entry or {}).get("comment") or ""),
                "gapOrOrphan": _status_needs_attention(status),
            }
        )
    return rows


def asset_graph_summary() -> dict[str, int]:
    """Return summary counts for the Backoffice Asset Graph lens."""
    category_rows = asset_graph_category_rows()
    scaffold_rows = asset_graph_scaffold_rows()
    starter_rows = asset_graph_starter_rows()
    capability_rows = asset_graph_capability_rows()
    attention_rows = [*category_rows, *scaffold_rows, *starter_rows, *capability_rows]
    return {
        "categories": len(category_rows),
        "scaffolds": len(scaffold_rows),
        "starters": len(starter_rows),
        "runtimeMappedStarters": sum(
            1
            for row in starter_rows
            if int(row.get("runtimeMappedScaffoldCount") or 0) > 0
        ),
        "availableNotMappedStarters": sum(
            1 for row in starter_rows if row.get("status") == "available-not-mapped"
        ),
        "gapsOrphansMissing": sum(
            1
            for row in attention_rows
            if _truthy_gap(row.get("gapOrOrphan"))
            or _status_needs_attention(str(row.get("status") or ""))
        ),
    }


def build_graph() -> dict[str, list[dict[str, Any]]]:
    """Build a read-only graph of current generation assets."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    scaffold_contract = load_policy("scaffold-contract.v1.json")
    dossier_contract = load_policy("dossier-contract.v1.json")
    starter_registry = load_policy("starter-registry.v1.json")
    llm_models = load_policy("llm-models.v1.json")
    required_files = scaffold_required_files(scaffold_contract)
    classes = dossier_classes(dossier_contract)
    dossier_manifests = _dossier_manifests_by_id(classes=classes)
    dossier_class_by_id = {
        dossier_id: dossier_class
        for dossier_id, (dossier_class, _path, _payload) in dossier_manifests.items()
    }

    try:
        from packages.generation.planning.plan import SCAFFOLD_TO_STARTER
    except ImportError:
        SCAFFOLD_TO_STARTER = {}

    for starter in starter_registry.get("starters", []):
        if not isinstance(starter, dict) or not starter.get("id"):
            continue
        starter_id = str(starter["id"])
        nodes.append(
            _node(
                node_type="starter",
                node_id=starter_id,
                path=REPO_ROOT / str(starter.get("path", "")),
                status=str(starter.get("status", "registered")),
                canonical=True,
                enabled=_enabled(starter),
                details=str(starter.get("label") or ""),
            )
        )

    for scaffold_dir in list_scaffold_dirs():
        scaffold_json = scaffold_dir / "scaffold.json"
        if scaffold_json.exists() and not is_placeholder_file(scaffold_json):
            scaffold_payload = read_json(scaffold_json)
            scaffold_id = str(scaffold_payload.get("id") or scaffold_dir.name)
            label = str(scaffold_payload.get("label") or "")
        else:
            scaffold_id = scaffold_dir.name
            label = ""
        file_state = scaffold_file_state(scaffold_dir, required_files)
        nodes.append(
            _node(
                node_type="scaffold",
                node_id=scaffold_id,
                path=scaffold_dir,
                status=file_state["status"],
                canonical=True,
                details=label,
            )
        )
        starter_id = SCAFFOLD_TO_STARTER.get(scaffold_id)
        if starter_id:
            edges.append(_edge(f"starter:{starter_id}", f"scaffold:{scaffold_id}", "maps-to"))

        variant_nodes, variant_edges = _variant_nodes_for_scaffold(scaffold_dir, scaffold_id)
        nodes.extend(variant_nodes)
        edges.extend(variant_edges)

        candidate_nodes, candidate_edges = _candidate_variant_nodes(scaffold_id)
        nodes.extend(candidate_nodes)
        edges.extend(candidate_edges)

        compatible_path = scaffold_dir / "compatible-dossiers.json"
        if compatible_path.exists() and not is_placeholder_file(compatible_path):
            compatible = read_json(compatible_path)
            edges.extend(
                _compatible_dossier_edges(scaffold_id, compatible, dossier_class_by_id)
            )

    for dossier_class, dossier_dir in list_dossier_dirs(classes=classes):
        manifest_path = dossier_dir / "manifest.json"
        if manifest_path.exists():
            try:
                payload = read_json(manifest_path)
                status = "canonical"
                enabled = _enabled(payload)
                details = str(payload.get("capability") or payload.get("summary") or "")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                status = "invalid"
                enabled = None
                details = str(exc)
        else:
            status = "incomplete"
            enabled = None
            details = "manifest.json saknas"
        nodes.append(
            _node(
                node_type=f"{dossier_class}-dossier",
                node_id=dossier_dir.name,
                path=dossier_dir,
                status=status,
                canonical=True,
                enabled=enabled,
                details=details,
            )
        )

    nodes.extend(_candidate_dossier_nodes())

    for role in llm_models.get("roles", []):
        if not isinstance(role, dict) or not role.get("id"):
            continue
        nodes.append(
            _node(
                node_type="model-role",
                node_id=str(role["id"]),
                path=POLICIES_DIR / "llm-models.v1.json",
                status=str(role.get("provider", "unknown")),
                canonical=True,
                details=str(role.get("model") or ""),
            )
        )

    from . import discovery_control

    discovery_graph = discovery_control.build_discovery_graph()
    nodes.extend(discovery_graph["nodes"])
    edges.extend(discovery_graph["edges"])

    return {"nodes": nodes, "edges": edges}


def run_health_checks() -> list[dict[str, str]]:
    """Return Backoffice health findings for generation assets."""
    findings: list[dict[str, str]] = []
    scaffold_contract = load_policy("scaffold-contract.v1.json")
    dossier_contract = load_policy("dossier-contract.v1.json")
    embedding_policy = load_policy("embedding-policy.v1.json")
    required_files = scaffold_required_files(scaffold_contract)
    classes = dossier_classes(dossier_contract)
    dossier_manifests = _dossier_manifests_by_id(classes=classes)

    for scaffold_dir in list_scaffold_dirs():
        state = scaffold_file_state(scaffold_dir, required_files)
        # A Scaffold deserves a Doctor warning when it is NOT fully implemented
        # (status is "incomplete" because required files are missing, or
        # "placeholder" because every required file exists but at least one is
        # still a builder placeholder). When status is "implemented" the
        # scaffold is healthy and no warning is needed; emitting one then would
        # always produce findings with an empty details string.
        if state["status"] != "implemented":
            details = []
            if state["missing"]:
                details.append("saknar " + ", ".join(state["missing"]))
            if state["placeholders"]:
                details.append("platshållare " + ", ".join(state["placeholders"]))
            findings.append(
                {
                    "level": "warning",
                    "id": f"scaffold-files:{scaffold_dir.name}",
                    "message": f"{scaffold_dir.name} följer inte scaffold-contract fullt ut.",
                    "path": repo_relative(scaffold_dir),
                    "details": "; ".join(details),
                }
            )

        scaffold_json = scaffold_dir / "scaffold.json"
        if scaffold_json.exists() and not is_placeholder_file(scaffold_json):
            scaffold_payload = read_json(scaffold_json)
            scaffold_id = str(scaffold_payload.get("id") or scaffold_dir.name)
        else:
            scaffold_id = scaffold_dir.name
        compatible_path = scaffold_dir / "compatible-dossiers.json"
        if compatible_path.exists() and not is_placeholder_file(compatible_path):
            compatible = read_json(compatible_path)
            for relation in ("required", "recommended", "conditional"):
                entries = compatible.get(relation, []) or []
                if not isinstance(entries, list):
                    findings.append(
                        {
                            "level": "error",
                            "id": f"compatible-dossier:{scaffold_id}:{relation}",
                            "message": f"{relation} i compatible-dossiers.json är inte en lista.",
                            "path": repo_relative(compatible_path),
                            "details": f"Fältet har typ {type(entries).__name__}.",
                        }
                    )
                    continue
                for index, entry in enumerate(entries):
                    dossier_id = _compatible_dossier_id(entry)
                    if dossier_id is None:
                        findings.append(
                            {
                                "level": "error",
                                "id": f"compatible-dossier:{scaffold_id}:{relation}:{index}",
                                "message": "Compatible Dossier-entry saknar id.",
                                "path": repo_relative(compatible_path),
                                "details": json.dumps(entry, ensure_ascii=False, sort_keys=True),
                            }
                        )
                        continue
                    if dossier_id not in dossier_manifests:
                        findings.append(
                            {
                                "level": "warning",
                                "id": f"compatible-dossier:{scaffold_id}:{relation}:{dossier_id}",
                                "message": f"{scaffold_id} refererar till okänd Dossier.",
                                "path": repo_relative(compatible_path),
                                "details": dossier_id,
                            }
                        )

    for class_dir in list_unregistered_dossier_class_dirs(classes=classes):
        findings.append(
            {
                "level": "warning",
                "id": f"dossier-class:{class_dir.name}",
                "message": f"{class_dir.name} är inte en aktiv Dossier-klass.",
                "path": repo_relative(class_dir),
                "details": "Tillåtna klasser: " + ", ".join(classes),
            }
        )

    for dossier_id, (dossier_class, manifest_path, payload) in dossier_manifests.items():
        manifest_class = payload.get("class")
        if manifest_class != dossier_class:
            findings.append(
                {
                    "level": "error",
                    "id": f"dossier-class-mismatch:{dossier_id}",
                    "message": f"{dossier_id} har class som inte matchar mappen.",
                    "path": repo_relative(manifest_path),
                    "details": f"manifest class={manifest_class!r}, folder={dossier_class!r}",
                }
            )

    if not EMBEDDING_DIR.exists():
        findings.append(
            {
                "level": "info",
                "id": "embedding-index:not-implemented",
                "message": "Embedding-policy finns, men indexmappen är inte implementerad.",
                "path": repo_relative(POLICIES_DIR / "embedding-policy.v1.json"),
                "details": str(embedding_policy.get("implementationStatus", "")),
            }
        )

    from . import discovery_control

    findings.extend(discovery_control.discovery_doctor_findings())

    graph = build_graph()
    for node in graph["nodes"]:
        if node["type"] == "variant-candidate" and node["status"] == "invalid":
            findings.append(
                {
                    "level": "error",
                    "id": f"variant-candidate:{node['id']}",
                    "message": "Variant-kandidat kan inte läsas som JSON.",
                    "path": str(node["path"]),
                    "details": str(node["details"]),
                }
            )

    return findings


def compare_variant_to_existing(
    candidate: dict[str, Any],
    existing_variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a small similarity table between one candidate and canonical Variants."""
    candidate_colors = candidate.get("tokens", {}).get("color", {})
    candidate_vibes = set(candidate.get("tone", {}).get("vibe", []) or [])
    rows: list[dict[str, Any]] = []
    for variant in existing_variants:
        colors = variant.get("tokens", {}).get("color", {})
        vibes = set(variant.get("tone", {}).get("vibe", []) or [])
        rows.append(
            {
                "variant": variant.get("id", ""),
                "sameColorTokens": sum(
                    1
                    for key, value in candidate_colors.items()
                    if colors.get(key) == value
                ),
                "sharedVibes": ", ".join(sorted(candidate_vibes & vibes)),
            }
        )
    return rows


def _json_preview(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _nested_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def variant_diff_rows(
    candidate: dict[str, Any],
    canonical: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return field-level diff rows between candidate and canonical Variant JSON."""
    fields = [
        "id",
        "enabled",
        "label",
        "description",
        "tokens.color.background",
        "tokens.color.foreground",
        "tokens.color.muted",
        "tokens.color.border",
        "tokens.color.primary",
        "tokens.color.primaryForeground",
        "tokens.color.accent",
        "tokens.color.accentForeground",
        "tokens.typography.fontFamilyDisplay",
        "tokens.typography.fontFamilyBody",
        "tokens.typography.fontFamilyMono",
        "tokens.typography.scaleRatio",
        "tokens.radius.sm",
        "tokens.radius.md",
        "tokens.radius.lg",
        "tokens.spacing.section",
        "tokens.spacing.container",
        "tokens.motion.level",
        "tone.vibe",
    ]
    rows: list[dict[str, Any]] = []
    for field in fields:
        canonical_value = _nested_value(canonical, field)
        candidate_value = _nested_value(candidate, field)
        rows.append(
            {
                "field": field,
                "canonical": _json_preview(canonical_value),
                "candidate": _json_preview(candidate_value),
                "changed": canonical_value != candidate_value,
            }
        )
    return rows


def list_variant_candidates(scaffold_id: str | None = None) -> list[dict[str, Any]]:
    """Return existing Variant candidate files with validation and collision status."""
    from packages.generation.artifacts import ArtifactSchemaError, validate_variant

    rows: list[dict[str, Any]] = []
    if not VARIANT_CANDIDATES_DIR.exists():
        return rows
    scaffold_dirs = (
        [VARIANT_CANDIDATES_DIR / scaffold_id]
        if scaffold_id
        else sorted(path for path in VARIANT_CANDIDATES_DIR.iterdir() if path.is_dir())
    )
    for candidate_dir in scaffold_dirs:
        if not candidate_dir.exists():
            continue
        current_scaffold_id = candidate_dir.name
        canonical_ids = {
            str(variant.get("id"))
            for variant in load_existing_variants(current_scaffold_id)
            if variant.get("id")
        }
        for candidate_path in sorted(candidate_dir.glob("*.json")):
            if candidate_path.name.endswith(".meta.json"):
                continue
            meta_path = candidate_path.with_name(f"{candidate_path.stem}.meta.json")
            provenance = _candidate_provenance(meta_path)
            try:
                payload = read_json(candidate_path)
                candidate_id = str(payload.get("id") or candidate_path.stem)
                validate_variant(payload)
                status = "valid"
                details = ""
                enabled = _enabled(payload)
            except (OSError, ValueError, json.JSONDecodeError, ArtifactSchemaError) as exc:
                candidate_id = candidate_path.stem
                status = "invalid"
                details = str(exc)
                enabled = None
            modified = datetime.fromtimestamp(
                candidate_path.stat().st_mtime,
                tz=UTC,
            ).isoformat(timespec="seconds")
            rows.append(
                {
                    "scaffold": current_scaffold_id,
                    "candidate": candidate_id,
                    "source": provenance["source"],
                    "modelUsed": provenance["modelUsed"],
                    "createdAt": provenance["createdAt"],
                    "enabled": enabled,
                    "status": status,
                    "collidesWithCanonical": candidate_id in canonical_ids,
                    "modifiedAt": modified,
                    "path": repo_relative(candidate_path),
                    "metaPath": provenance["metaPath"],
                    "details": details,
                }
            )
    return rows


def load_existing_variants(scaffold_id: str) -> list[dict[str, Any]]:
    """Read canonical Variants for one Scaffold."""
    variants_dir = SCAFFOLDS_DIR / scaffold_id / "variants"
    if not variants_dir.exists():
        return []
    variants: list[dict[str, Any]] = []
    for path in sorted(variants_dir.glob("*.json")):
        variants.append(read_json(path))
    return variants


def _dossier_manifests_by_id(
    dossiers_dir: Path | None = None,
    *,
    classes: list[str] | None = None,
) -> dict[str, tuple[str, Path, dict[str, Any]]]:
    """Read Dossier manifests keyed by manifest id."""
    manifests: dict[str, tuple[str, Path, dict[str, Any]]] = {}
    for dossier_class, dossier_dir in list_dossier_dirs(dossiers_dir, classes=classes):
        manifest_path = dossier_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            payload = read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        dossier_id = payload.get("id")
        if isinstance(dossier_id, str) and dossier_id:
            manifests[dossier_id] = (dossier_class, manifest_path, payload)
    return manifests
