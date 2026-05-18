"""Helpers for reading and editing Scaffold selection-profile files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import asset_graph
from .io import atomic_write_json

REQUIRED_FIELDS = [
    "id",
    "embeddingText",
    "semanticSignals",
    "negativeSignals",
    "llmClassificationHints",
    "minConfidence",
    "requiresTieBreakWhenWithin",
]


def profile_path(scaffold_id: str, scaffolds_dir: Path | None = None) -> Path:
    """Return the selection-profile path for one Scaffold."""
    base = scaffolds_dir if scaffolds_dir is not None else asset_graph.SCAFFOLDS_DIR
    return base / scaffold_id / "selection-profile.json"


def load_profile(scaffold_id: str, scaffolds_dir: Path | None = None) -> dict[str, Any]:
    """Read one selection-profile JSON object."""
    return asset_graph.read_json(profile_path(scaffold_id, scaffolds_dir))


def list_profile_summaries(scaffolds_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return one compact summary per on-disk Scaffold profile."""
    rows: list[dict[str, Any]] = []
    for scaffold_dir in asset_graph.list_scaffold_dirs(scaffolds_dir):
        path = scaffold_dir / "selection-profile.json"
        if not path.exists():
            rows.append(
                {
                    "scaffold": scaffold_dir.name,
                    "status": "missing",
                    "semanticSignals": 0,
                    "negativeSignals": 0,
                    "hints": 0,
                    "minConfidence": "",
                    "path": asset_graph.repo_relative(path),
                }
            )
            continue
        try:
            payload = asset_graph.read_json(path)
            errors = validate_profile(payload)
            status = "ok" if not errors else "invalid"
        except (OSError, ValueError) as exc:
            payload = {}
            errors = [str(exc)]
            status = "invalid"
        rows.append(
            {
                "scaffold": scaffold_dir.name,
                "status": status,
                "semanticSignals": len(payload.get("semanticSignals", []) or []),
                "negativeSignals": len(payload.get("negativeSignals", []) or []),
                "hints": len(payload.get("llmClassificationHints", []) or []),
                "minConfidence": payload.get("minConfidence", ""),
                "path": asset_graph.repo_relative(path),
                "issues": "; ".join(errors),
            }
        )
    return rows


def _normalised_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip().lower() for value in values if str(value).strip()}


def signal_findings(payload: dict[str, Any]) -> list[str]:
    """Return read-only signal coverage findings for one profile."""
    findings: list[str] = []
    semantic = payload.get("semanticSignals", [])
    negative = payload.get("negativeSignals", [])
    hints = payload.get("llmClassificationHints", [])
    if isinstance(semantic, list) and len(semantic) < 3:
        findings.append("semanticSignals has fewer than 3 entries")
    if isinstance(negative, list) and len(negative) < 3:
        findings.append("negativeSignals has fewer than 3 entries")
    if isinstance(hints, list) and len(hints) < 1:
        findings.append("llmClassificationHints is empty")
    overlap = sorted(_normalised_set(semantic) & _normalised_set(negative))
    if overlap:
        findings.append("semanticSignals overlap negativeSignals: " + ", ".join(overlap))
    for field_name in ("semanticSignals", "negativeSignals", "llmClassificationHints"):
        values = payload.get(field_name, [])
        if not isinstance(values, list):
            continue
        normalised = [str(value).strip().lower() for value in values if str(value).strip()]
        duplicates = sorted({value for value in normalised if normalised.count(value) > 1})
        if duplicates:
            findings.append(f"{field_name} has duplicates: " + ", ".join(duplicates))
    return findings


def validate_profile(payload: dict[str, Any]) -> list[str]:
    """Validate shape required by scaffold-contract.v1 selection profiles."""
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in payload:
            errors.append(f"Missing required field: {field_name}")
    for field_name in ("semanticSignals", "negativeSignals", "llmClassificationHints"):
        if field_name in payload and not isinstance(payload[field_name], list):
            errors.append(f"{field_name} must be a list")
    if "embeddingText" in payload and not isinstance(payload["embeddingText"], str):
        errors.append("embeddingText must be a string")
    for field_name in ("minConfidence", "requiresTieBreakWhenWithin"):
        value = payload.get(field_name)
        if field_name in payload and not isinstance(value, int | float):
            errors.append(f"{field_name} must be numeric")
    return errors


def lines_to_list(text: str) -> list[str]:
    """Convert a textarea value to a clean string list."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def write_profile(
    scaffold_id: str,
    payload: dict[str, Any],
    *,
    scaffolds_dir: Path | None = None,
) -> None:
    """Validate and atomically write one selection-profile."""
    errors = validate_profile(payload)
    if errors:
        raise ValueError("; ".join(errors))
    atomic_write_json(profile_path(scaffold_id, scaffolds_dir), payload)
