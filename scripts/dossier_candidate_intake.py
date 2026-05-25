"""Read-only intake analysis for local Dossier candidate sources.

The helper inspects one local file or directory and returns a JSON-serialisable
report that Backoffice can show before any candidate files are written. It
never copies source files and it never reads secret-like paths.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_GENERATED_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated"
REPORT_VERSION = 1
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_READABLE_TEXT_BYTES_PER_FILE = 256 * 1024
LARGE_FILE_BYTES = 1 * 1024 * 1024
RECOGNISED_EXTENSIONS = {
    ".css",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".png",
    ".svg",
    ".ts",
    ".tsx",
}
TEXT_EXTENSIONS = {".css", ".json", ".md", ".ts", ".tsx", ".txt"}
ASSET_EXTENSIONS = {".jpeg", ".jpg", ".png", ".svg", ".webp"}
COMPONENT_EXTENSIONS = {".tsx", ".ts", ".css"}
FORBIDDEN_DIRECTORY_NAMES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
LOCKFILE_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "pipfile.lock",
}
SECRET_NAME_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "*secret*",
    "*token*",
    "*credential*",
)
HARD_SIGNAL_RE = re.compile(
    r"\b(api|auth|backend|database|db|env|oauth|payment|secret|server|stripe|"
    r"supabase|token|webhook|openai|process\.env|api_key)\b",
    re.IGNORECASE,
)
CUSTOMER_SIGNAL_RE = re.compile(
    r"\b(company|customer|kund|logo|logga|team|vårt team|our team|lineage|"
    r"brand manual|varumärke)\b",
    re.IGNORECASE,
)
SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
SLUG_DASHES = re.compile(r"-{2,}")


class DossierIntakeError(RuntimeError):
    """Raised when a source path cannot be analysed safely."""


@dataclass(frozen=True)
class IntakeScanCaps:
    """Safety caps for read-only source analysis."""

    max_files: int = DEFAULT_MAX_FILES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_readable_text_bytes_per_file: int = DEFAULT_MAX_READABLE_TEXT_BYTES_PER_FILE


def _normalise_report_for_hash(report: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(report)
    normalised.pop("reportHash", None)
    return normalised


def intake_report_hash(report: dict[str, Any]) -> str:
    """Return a stable sha256 digest for an intake report."""
    payload = json.dumps(
        _normalise_report_for_hash(report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_intake_report_for_model(report: dict[str, Any]) -> dict[str, Any]:
    """Return report data safe to send to dossierModel.

    V1 reports contain path metadata, not source file contents. The sanitizer
    still strips any future accidental content-ish keys defensively and keeps
    excluded secret-like paths as path-only provenance.
    """
    safe = {
        key: value
        for key, value in report.items()
        if key
        not in {
            "fileContents",
            "rawContents",
            "sourceText",
            "textPreview",
        }
    }
    safe["includedFiles"] = [
        _strip_content_like_keys(item)
        for item in safe.get("includedFiles", [])
        if isinstance(item, dict)
    ]
    safe["excludedFiles"] = [
        _strip_content_like_keys(item)
        for item in safe.get("excludedFiles", [])
        if isinstance(item, dict)
    ]
    return safe


def _strip_content_like_keys(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if key
        not in {
            "content",
            "fileContents",
            "rawContents",
            "sourceText",
            "text",
            "textPreview",
        }
    }


def _slugify(text: str) -> str:
    cleaned = SLUG_CLEAN.sub("-", text.lower()).strip("-")
    cleaned = SLUG_DASHES.sub("-", cleaned)
    if not cleaned:
        cleaned = "generated-dossier"
    if cleaned[0].isdigit():
        cleaned = f"dossier-{cleaned}"
    return cleaned


def _default_allowed_roots() -> list[Path]:
    roots = [REPO_ROOT, DEFAULT_GENERATED_DIR]
    env_generated = os.environ.get("SAJTBYGGAREN_GENERATED_DIR")
    if env_generated:
        roots.append(Path(env_generated).expanduser())
    return roots


def _resolve_allowed_roots(allowed_roots: list[Path] | tuple[Path, ...] | None) -> list[Path]:
    roots = list(allowed_roots) if allowed_roots is not None else _default_allowed_roots()
    return [root.resolve(strict=False) for root in roots]


def _resolve_source_path(
    source_path: str | Path,
    *,
    allowed_roots: list[Path] | tuple[Path, ...] | None,
) -> tuple[Path, list[Path]]:
    raw = Path(source_path).expanduser()
    candidate = raw if raw.is_absolute() else REPO_ROOT / raw
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DossierIntakeError(f"Source path does not exist: {source_path}") from exc
    roots = _resolve_allowed_roots(allowed_roots)
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise DossierIntakeError(f"Source path is outside allowed roots: {source_path}")
    return resolved, roots


def _path_for_report(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_secret_like_path(path: Path) -> bool:
    lowered_parts = [part.lower() for part in path.parts]
    lowered_name = path.name.lower()
    for pattern in SECRET_NAME_PATTERNS:
        if fnmatch.fnmatch(lowered_name, pattern):
            return True
    return any(
        "secret" in part or "token" in part or "credential" in part
        for part in lowered_parts
    )


def _file_entry(path: Path, source_root: Path, *, reason: str | None = None) -> dict[str, Any]:
    try:
        relative_path = path.resolve(strict=False).relative_to(source_root).as_posix()
    except ValueError:
        relative_path = _path_for_report(path)
    entry: dict[str, Any] = {
        "path": relative_path,
        "sizeBytes": path.stat().st_size if path.exists() else 0,
        "extension": path.suffix.lower(),
    }
    if reason is not None:
        entry["reason"] = reason
    return entry


def _initial_report(source: Path, source_kind: str) -> dict[str, Any]:
    return {
        "reportVersion": REPORT_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sourcePath": _path_for_report(source),
        "sourceKind": source_kind,
        "fileCount": 0,
        "fileSummary": {
            "extensions": {},
            "recognizedFileCount": 0,
            "totalBytes": 0,
            "largeFileCount": 0,
            "maxFiles": DEFAULT_MAX_FILES,
            "maxTotalBytes": DEFAULT_MAX_TOTAL_BYTES,
            "maxReadableTextBytesPerFile": DEFAULT_MAX_READABLE_TEXT_BYTES_PER_FILE,
        },
        "candidateSignals": {
            "hasManifest": False,
            "hasInstructions": False,
            "hasComponents": False,
            "hasAssets": False,
            "hasHardSignals": False,
            "hasCustomerSpecificSignals": False,
        },
        "riskFlags": [],
        "recommendedClass": "needs-review",
        "suggestedCapability": "",
        "suggestedDossierId": _slugify(source.stem or source.name),
        "includedFiles": [],
        "excludedFiles": [],
        "operatorQuestions": [],
    }


def _add_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _iter_source_files(
    source: Path,
    roots: list[Path],
    report: dict[str, Any],
) -> list[Path]:
    if source.is_file():
        return [source]

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        current_dir = Path(dirpath)
        kept_dirnames = []
        for dirname in dirnames:
            child = current_dir / dirname
            if dirname.lower() in FORBIDDEN_DIRECTORY_NAMES:
                report["excludedFiles"].append(
                    {
                        "path": child.relative_to(source).as_posix(),
                        "reason": "forbidden-directory",
                    }
                )
                continue
            try:
                resolved_child = child.resolve(strict=True)
            except OSError:
                report["excludedFiles"].append(
                    {
                        "path": child.relative_to(source).as_posix(),
                        "reason": "unreadable-directory",
                    }
                )
                continue
            if not any(
                resolved_child == root or root in resolved_child.parents
                for root in roots
            ):
                report["excludedFiles"].append(
                    {
                        "path": child.relative_to(source).as_posix(),
                        "reason": "path-escape",
                    }
                )
                continue
            kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames
        files.extend(current_dir / filename for filename in filenames)
    return files


def _read_small_text(path: Path, caps: IntakeScanCaps) -> str:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    if path.stat().st_size > caps.max_readable_text_bytes_per_file:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _update_signals_from_content(
    *,
    path: Path,
    text: str,
    manifest_payload: dict[str, Any] | None,
    report: dict[str, Any],
) -> None:
    signals = report["candidateSignals"]
    lowered_path = path.as_posix().lower()
    if path.name == "manifest.json":
        signals["hasManifest"] = True
    if path.name == "instructions.md":
        signals["hasInstructions"] = True
    if path.suffix.lower() in COMPONENT_EXTENSIONS:
        signals["hasComponents"] = True
    if path.suffix.lower() in ASSET_EXTENSIONS:
        signals["hasAssets"] = True
    if HARD_SIGNAL_RE.search(lowered_path) or HARD_SIGNAL_RE.search(text):
        signals["hasHardSignals"] = True
        _add_unique(report["riskFlags"], "hard-signal")
    if CUSTOMER_SIGNAL_RE.search(lowered_path) or CUSTOMER_SIGNAL_RE.search(text):
        signals["hasCustomerSpecificSignals"] = True
        _add_unique(report["riskFlags"], "customer-specific")
    if manifest_payload:
        capability = manifest_payload.get("capability")
        dossier_id = manifest_payload.get("id")
        dossier_class = manifest_payload.get("class")
        if isinstance(capability, str) and capability:
            report["suggestedCapability"] = _slugify(capability)
        if isinstance(dossier_id, str) and dossier_id:
            report["suggestedDossierId"] = _slugify(dossier_id)
        if dossier_class == "hard":
            signals["hasHardSignals"] = True
            _add_unique(report["riskFlags"], "hard-signal")


def _try_manifest_payload(path: Path, text: str) -> dict[str, Any] | None:
    if path.name != "manifest.json" or not text.strip():
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _finish_recommendation(report: dict[str, Any], *, operator_brief: str) -> None:
    signals = report["candidateSignals"]
    if "source-too-large" in report["riskFlags"] or "source-too-broad" in report["riskFlags"]:
        report["recommendedClass"] = "needs-review"
    elif (
        signals["hasCustomerSpecificSignals"]
        and not signals["hasManifest"]
        and not signals["hasInstructions"]
        and not signals["hasComponents"]
    ):
        report["recommendedClass"] = "not-a-dossier"
    elif signals["hasHardSignals"]:
        report["recommendedClass"] = "hard"
    elif signals["hasManifest"] or signals["hasInstructions"] or signals["hasComponents"]:
        report["recommendedClass"] = "soft"
    else:
        report["recommendedClass"] = "needs-review"

    if not report["suggestedCapability"]:
        report["suggestedCapability"] = _slugify(operator_brief or report["suggestedDossierId"])
    if not report["suggestedDossierId"]:
        report["suggestedDossierId"] = _slugify(operator_brief or report["sourcePath"])

    if report["recommendedClass"] == "not-a-dossier":
        _add_unique(
            report["operatorQuestions"],
            "Källan verkar kundspecifik. Ska detta vara Project Input/assets i stället för en återanvändbar Dossier?",
        )
    if report["recommendedClass"] == "hard":
        _add_unique(
            report["operatorQuestions"],
            "Källan verkar kräva secrets/API/backend senare. Ska detta bara bli en hard candidate för framtida separat integration?",
        )
    if report["recommendedClass"] == "needs-review":
        _add_unique(
            report["operatorQuestions"],
            "Behöver operatörsgranskning innan kandidat skapas.",
        )


def analyze_dossier_source(
    source_path: str | Path,
    *,
    operator_brief: str = "",
    allowed_roots: list[Path] | tuple[Path, ...] | None = None,
    scan_caps: IntakeScanCaps | None = None,
) -> dict[str, Any]:
    """Analyse one local source path without writing or copying files."""
    caps = scan_caps or IntakeScanCaps()
    source, roots = _resolve_source_path(source_path, allowed_roots=allowed_roots)
    source_kind = "file" if source.is_file() else "directory"
    report = _initial_report(source, source_kind)
    summary = report["fileSummary"]
    summary["maxFiles"] = caps.max_files
    summary["maxTotalBytes"] = caps.max_total_bytes
    summary["maxReadableTextBytesPerFile"] = caps.max_readable_text_bytes_per_file

    if source == REPO_ROOT:
        _add_unique(report["riskFlags"], "source-too-broad")
        _add_unique(report["riskFlags"], "source-too-large")
        report["recommendedClass"] = "needs-review"
        report["operatorQuestions"].append(
            "Källan är repo-roten. Välj en smalare fil eller mapp innan intake körs."
        )
        report["reportHash"] = intake_report_hash(report)
        return report

    files = sorted(_iter_source_files(source, roots, report))
    total_bytes = 0
    for index, path in enumerate(files, start=1):
        if index > caps.max_files:
            _add_unique(report["riskFlags"], "source-too-large")
            report["excludedFiles"].append(
                {"path": _path_for_report(path), "reason": "max-files-exceeded"}
            )
            break
        try:
            resolved_path = path.resolve(strict=True)
        except OSError:
            report["excludedFiles"].append(
                _file_entry(path, source, reason="unreadable-file")
            )
            continue
        if not any(
            resolved_path == root or root in resolved_path.parents for root in roots
        ):
            report["excludedFiles"].append(_file_entry(path, source, reason="path-escape"))
            continue
        size = resolved_path.stat().st_size
        total_bytes += size
        if total_bytes > caps.max_total_bytes:
            _add_unique(report["riskFlags"], "source-too-large")
            report["excludedFiles"].append(
                _file_entry(resolved_path, source, reason="max-total-bytes-exceeded")
            )
            break
        if _is_secret_like_path(resolved_path):
            report["excludedFiles"].append(
                _file_entry(resolved_path, source, reason="secret-like-path")
            )
            continue
        if resolved_path.name.lower() in LOCKFILE_NAMES:
            report["excludedFiles"].append(
                _file_entry(resolved_path, source, reason="lockfile")
            )
            _add_unique(report["riskFlags"], "lockfile")
            continue

        extension = resolved_path.suffix.lower()
        summary["extensions"][extension or "<none>"] = (
            int(summary["extensions"].get(extension or "<none>", 0)) + 1
        )
        summary["totalBytes"] = total_bytes
        report["fileCount"] += 1
        if extension in RECOGNISED_EXTENSIONS:
            summary["recognizedFileCount"] += 1
        if size > LARGE_FILE_BYTES:
            summary["largeFileCount"] += 1
            _add_unique(report["riskFlags"], "large-file")

        included = _file_entry(resolved_path, source)
        if extension in TEXT_EXTENSIONS and size > caps.max_readable_text_bytes_per_file:
            included["readState"] = "skipped-too-large"
        report["includedFiles"].append(included)

        text = _read_small_text(resolved_path, caps)
        manifest_payload = _try_manifest_payload(resolved_path, text)
        _update_signals_from_content(
            path=resolved_path,
            text=text,
            manifest_payload=manifest_payload,
            report=report,
        )

    _finish_recommendation(report, operator_brief=operator_brief)
    report["reportHash"] = intake_report_hash(report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only analysis for a local Dossier candidate source."
    )
    parser.add_argument("--source-path", required=True, help="Local file or directory")
    parser.add_argument("--brief", default="", help="Operator brief")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument(
        "--max-readable-text-bytes-per-file",
        type=int,
        default=DEFAULT_MAX_READABLE_TEXT_BYTES_PER_FILE,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = analyze_dossier_source(
            args.source_path,
            operator_brief=args.brief,
            scan_caps=IntakeScanCaps(
                max_files=args.max_files,
                max_total_bytes=args.max_total_bytes,
                max_readable_text_bytes_per_file=args.max_readable_text_bytes_per_file,
            ),
        )
    except DossierIntakeError as exc:
        print(f"dossier candidate intake failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
