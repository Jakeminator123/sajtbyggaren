"""Read-only graph and health helpers for Backoffice building blocks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import DATA_DIR, POLICIES_DIR, REPO_ROOT

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
VARIANT_CANDIDATES_DIR = DATA_DIR / "variant-candidates"
DOSSIER_CANDIDATES_DIR = DATA_DIR / "dossier-candidates"
EMBEDDING_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "embedding"
PLACEHOLDER_MARKER = "placeholder, fill per scaffold-contract"


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


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
) -> list[dict[str, str]]:
    """Return graph edges from one Scaffold to compatible Dossiers."""
    edges: list[dict[str, str]] = []
    for relation in ("required", "recommended", "conditional"):
        entries = compatible.get(relation, []) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            dossier_id = _compatible_dossier_id(entry)
            if dossier_id is None:
                continue
            edges.append(
                _edge(
                    f"scaffold:{scaffold_id}",
                    f"dossier:{dossier_id}",
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
    return nodes


def build_graph() -> dict[str, list[dict[str, Any]]]:
    """Build a read-only graph of current generation assets."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    scaffold_contract = load_policy("scaffold-contract.v1.json")
    starter_registry = load_policy("starter-registry.v1.json")
    llm_models = load_policy("llm-models.v1.json")
    required_files = scaffold_required_files(scaffold_contract)

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
            edges.extend(_compatible_dossier_edges(scaffold_id, compatible))

    for dossier_class, dossier_dir in list_dossier_dirs():
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
        if state["status"] == "implemented":
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
                    "source": "unknown-existing",
                    "enabled": enabled,
                    "status": status,
                    "collidesWithCanonical": candidate_id in canonical_ids,
                    "modifiedAt": modified,
                    "path": repo_relative(candidate_path),
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
