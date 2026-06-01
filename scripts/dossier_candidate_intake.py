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

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief.models import has_openai_api_key  # noqa: E402

DEFAULT_GENERATED_DIR = REPO_ROOT.parent / "sajtbyggaren-output" / ".generated"
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"
DOSSIER_ROLE_ID = "dossierModel"
EXPECTED_PROVIDER = "openai"
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
ALLOWED_REVIEW_DECISIONS = {"can-be-dossier", "not-a-dossier", "needs-review"}
ALLOWED_RECOMMENDED_CLASSES = {"soft", "hard", "needs-review", "not-a-dossier"}
FORBIDDEN_DIRECTORY_NAMES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
BROAD_REPO_SOURCE_PARTS = {
    ".cursor",
    "apps",
    "data",
    "docs",
    "governance",
    "packages",
    "scripts",
    "tests",
}
FORBIDDEN_REPO_SOURCE_PREFIXES = {
    ("data", "runs"),
    ("data", "prompt-inputs"),
    ("data", "versions"),
    ("data", "output"),
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
HARD_PATH_SIGNAL_RE = re.compile(
    r"(^|/)(api|auth|backend|server|webhook)(/|[-_.])|"
    r"\b(env-contract|integration-contract|stripe|supabase|clerk|shopify|openai)\b",
    re.IGNORECASE,
)
HARD_TEXT_SIGNAL_RE = re.compile(
    r"\b(process\.env|api[_ -]?key|secret[_ -]?key|access[_ -]?token|bearer|"
    r"database[_ -]?url|webhook[_ -]?secret|oauth[_ -]?client|"
    r"stripe[_ -]?secret|supabase[_ -]?service)\b",
    re.IGNORECASE,
)
CUSTOMER_SIGNAL_RE = re.compile(
    r"\b(kundspecifik|logo|logga|vårt team|our team|lineage|brand manual|varumärke)\b",
    re.IGNORECASE,
)
SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
SLUG_DASHES = re.compile(r"-{2,}")
WORD_RE = re.compile(r"[a-z0-9]+")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
IMPORT_RE = re.compile(r"^\s*import\s+(?:[^'\"]+\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE)
EXPORT_RE = re.compile(r"\bexport\s+(?:default\s+)?(?:function|const|class)\s+([A-Za-z0-9_]+)")
SECRET_TEXT_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]+|secret[_ -]?key\s*[:=]|api[_ -]?key\s*[:=]|"
    r"token\s*[:=]|-----BEGIN [A-Z ]+PRIVATE KEY-----)",
    re.IGNORECASE,
)
SAFE_SNIPPET_CHARS = 1200
SAFE_LINE_CHARS = 220
SAFE_DEPENDENCY_LIMIT = 40


class DossierIntakeError(RuntimeError):
    """Raised when a source path cannot be analysed safely."""


class DossierIntakeModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json has no usable dossierModel role."""


@dataclass(frozen=True)
class IntakeScanCaps:
    """Safety caps for read-only source analysis."""

    max_files: int = DEFAULT_MAX_FILES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_readable_text_bytes_per_file: int = DEFAULT_MAX_READABLE_TEXT_BYTES_PER_FILE


class DossierIntakeReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    recommendedClass: str
    suggestedDossierId: str
    suggestedCapability: str
    summary: str
    proposedContents: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    operatorQuestions: list[str] = Field(default_factory=list)
    testPlan: list[str] = Field(default_factory=list)
    promotionBlockedReason: str = ""


def resolve_dossier_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for dossierModel."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise DossierIntakeModelResolutionError(f"llm-models.v1.json missing at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DossierIntakeModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc
    for role in data.get("roles", []):
        if role.get("id") != DOSSIER_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise DossierIntakeModelResolutionError(
                f"dossierModel provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise DossierIntakeModelResolutionError(
                "dossierModel role is missing a non-empty model value"
            )
        return model
    raise DossierIntakeModelResolutionError(f"dossierModel role missing from {path.name}")


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


def _words_from_slug(text: str) -> list[str]:
    return WORD_RE.findall(_slugify(text))


def suggest_capability_from_source_path(source_path: str | Path) -> str:
    """Suggest a capability from source path before falling back to operator prose."""
    slug = _slugify(Path(str(source_path)).stem or Path(str(source_path)).name)
    words = _words_from_slug(slug)
    word_set = set(words)
    if {"stripe", "checkout"} <= word_set:
        return "stripe-checkout"
    if "checkout" in word_set and ({"payment", "payments"} & word_set):
        return "payment-checkout"
    if {"resend", "contact", "form"} <= word_set:
        return "contact-form"
    if {"contact", "form"} <= word_set:
        return "contact-form"
    if {"openai", "chat"} <= word_set:
        return "ai-chat"
    if "payments" in words:
        words = ["payment" if word == "payments" else word for word in words]
    filtered = [word for word in words if word not in {"dossier", "candidate", "legacy"}]
    return "-".join(filtered[:3]) if filtered else slug


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


def _excluded_path_entry(path: Path, source_root: Path, *, reason: str) -> dict[str, Any]:
    """Return an excluded-file entry without stat/read calls.

    Used for secret-like paths so intake can list the path without touching
    file metadata or contents.
    """
    try:
        relative_path = path.relative_to(source_root).as_posix()
    except ValueError:
        relative_path = path.as_posix()
    return {
        "path": relative_path,
        "sizeBytes": 0,
        "extension": path.suffix.lower(),
        "reason": reason,
    }


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


def _repo_relative_parts(path: Path) -> tuple[str, ...]:
    try:
        return path.resolve(strict=False).relative_to(REPO_ROOT).parts
    except ValueError:
        return ()


def _is_broad_repo_source(source: Path) -> bool:
    parts = _repo_relative_parts(source)
    if not parts:
        return source == REPO_ROOT
    if len(parts) == 1 and parts[0] in BROAD_REPO_SOURCE_PARTS:
        return True
    return any(parts[: len(prefix)] == prefix for prefix in FORBIDDEN_REPO_SOURCE_PREFIXES)


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
    if HARD_PATH_SIGNAL_RE.search(lowered_path) or HARD_TEXT_SIGNAL_RE.search(text):
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
        report["suggestedCapability"] = suggest_capability_from_source_path(
            str(report.get("sourcePath") or report.get("suggestedDossierId") or operator_brief)
        )
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

    if _is_broad_repo_source(source):
        _add_unique(report["riskFlags"], "source-too-broad")
        _add_unique(report["riskFlags"], "source-too-large")
        report["recommendedClass"] = "needs-review"
        report["operatorQuestions"].append(
            "Källan är för bred eller pekar på genererade artefakter. Välj en smalare fil eller mapp innan intake körs."
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
        if _is_secret_like_path(path):
            report["excludedFiles"].append(
                _excluded_path_entry(path, source, reason="secret-like-path")
            )
            continue
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


def _safe_excerpt(text: str, *, limit: int = SAFE_SNIPPET_CHARS) -> str:
    safe_lines: list[str] = []
    for line in text.splitlines():
        if SECRET_TEXT_RE.search(line):
            continue
        stripped = line.strip()
        if stripped:
            safe_lines.append(stripped[:SAFE_LINE_CHARS])
        if len("\n".join(safe_lines)) >= limit:
            break
    return "\n".join(safe_lines)[:limit]


def _headings_from_text(text: str) -> list[str]:
    return [match.group(2).strip()[:SAFE_LINE_CHARS] for match in HEADING_RE.finditer(text)]


def _component_symbols(text: str) -> dict[str, list[str]]:
    return {
        "imports": sorted(set(IMPORT_RE.findall(text)))[:SAFE_DEPENDENCY_LIMIT],
        "exports": sorted(set(EXPORT_RE.findall(text)))[:SAFE_DEPENDENCY_LIMIT],
    }


def _read_safe_text_for_evidence(path: Path) -> str:
    if _is_secret_like_path(path):
        return ""
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    try:
        if path.stat().st_size > DEFAULT_MAX_READABLE_TEXT_BYTES_PER_FILE:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json_object_from_text(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_package_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("name", "version", "description"):
        value = payload.get(key)
        if isinstance(value, str):
            metadata[key] = value[:SAFE_LINE_CHARS]
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = payload.get(key)
        if isinstance(value, dict):
            metadata[key] = sorted(str(item) for item in value)[:SAFE_DEPENDENCY_LIMIT]
    return metadata


def _resolve_evidence_candidate(
    source: Path,
    relative_path: Path,
) -> tuple[Path | None, str | None]:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None, "path-escape"
    candidate = source / relative_path if source.is_dir() else source
    try:
        resolved_candidate = candidate.resolve(strict=True)
    except OSError:
        return None, "unreadable-file"
    if source.is_dir() and not (
        resolved_candidate == source or source in resolved_candidate.parents
    ):
        return None, "path-escape"
    if source.is_file() and resolved_candidate != source:
        return None, "path-escape"
    return resolved_candidate, None


def build_safe_intake_evidence(
    report: dict[str, Any],
    source_path: str | Path,
) -> dict[str, Any]:
    """Build safe, bounded evidence for dossierModel review."""
    raw_source = Path(source_path).expanduser()
    source = raw_source if raw_source.is_absolute() else REPO_ROOT / raw_source
    try:
        source = source.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DossierIntakeError(f"Source path does not exist: {source_path}") from exc
    evidence: dict[str, Any] = {
        "sourcePath": report.get("sourcePath", _path_for_report(source)),
        "includedFilePaths": [],
        "manifest": {},
        "markdown": {},
        "package": {},
        "components": [],
        "warnings": [],
    }
    for item in report.get("includedFiles", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        relative_path = Path(str(item["path"]))
        candidate, warning = _resolve_evidence_candidate(source, relative_path)
        if warning is not None:
            evidence["warnings"].append({"path": str(item["path"]), "reason": warning})
            continue
        if candidate is None:
            continue
        if _is_secret_like_path(candidate) or item.get("readState") == "skipped-too-large":
            continue
        evidence["includedFilePaths"].append(str(item["path"]))
        text = _read_safe_text_for_evidence(candidate)
        if not text:
            continue
        name = candidate.name.lower()
        if name == "manifest.json":
            manifest = _json_object_from_text(text)
            evidence["manifest"] = {
                key: manifest.get(key)
                for key in ("id", "label", "capability", "class", "summary", "envVars", "dependencies")
                if key in manifest
            }
        elif name == "package.json":
            evidence["package"] = _safe_package_metadata(_json_object_from_text(text))
        elif name in {"instructions.md", "readme.md"}:
            evidence["markdown"][item["path"]] = {
                "headings": _headings_from_text(text)[:20],
                "excerpt": _safe_excerpt(text),
            }
        elif candidate.suffix.lower() in {".ts", ".tsx"}:
            evidence["components"].append(
                {
                    "path": item["path"],
                    **_component_symbols(text),
                }
            )
    return evidence


def _normalise_review_choice(value: str, allowed: set[str], fallback: str) -> str:
    normalised = _slugify(value)
    if normalised in allowed:
        return normalised
    if normalised in {"hard-candidate", "hard-dossier"} and "hard" in allowed:
        return "hard"
    if normalised in {"soft-candidate", "soft-dossier"} and "soft" in allowed:
        return "soft"
    return fallback


def normalise_intake_review(review: dict[str, Any]) -> dict[str, Any]:
    """Normalise model enum-like values to the V1.1 review contract."""
    normalised = dict(review)
    normalised["decision"] = _normalise_review_choice(
        str(normalised.get("decision") or ""),
        ALLOWED_REVIEW_DECISIONS,
        "needs-review",
    )
    normalised["recommendedClass"] = _normalise_review_choice(
        str(normalised.get("recommendedClass") or ""),
        ALLOWED_RECOMMENDED_CLASSES,
        "needs-review",
    )
    return normalised


def _operator_questions_for_review(recommended_class: str, capability: str) -> list[str]:
    if recommended_class == "hard":
        return [
            f"Ska dossiern beskriva {capability} generellt eller just denna implementation?",
            "Ska den vara hard candidate only tills riktig integration prioriteras?",
            "Ska V1-kandidaten bara ge CTA/checkout-instruktioner utan backend?",
            "Finns exempel på success/cancel URL-flöde som ska dokumenteras senare?",
            "Vilka env vars, till exempel STRIPE_SECRET_KEY, behövs i en separat framtida integration?",
        ]
    if recommended_class == "not-a-dossier":
        return [
            "Är detta kundspecifikt material som bör ligga i Project Input/assets i stället?",
            "Vilken återanvändbar capability finns här, om någon?",
        ]
    return [
        "Vilka delar är återanvändbar capability och vilka är projektspecifik copy?",
        "Vilket preview-case ska bevisa att kandidaten fungerar innan promotion?",
    ]


def _deterministic_intake_review(
    *,
    operator_brief: str,
    intake_report: dict[str, Any],
    safe_evidence: dict[str, Any],
    source: str,
    model_used: str,
) -> dict[str, Any]:
    recommended_class = _normalise_review_choice(
        str(intake_report.get("recommendedClass") or "needs-review"),
        ALLOWED_RECOMMENDED_CLASSES,
        "needs-review",
    )
    suggested_id = _slugify(
        str(
            safe_evidence.get("manifest", {}).get("id")
            or intake_report.get("suggestedDossierId")
            or safe_evidence.get("sourcePath")
            or operator_brief
        )
    )
    suggested_capability = _slugify(
        str(
            safe_evidence.get("manifest", {}).get("capability")
            or suggest_capability_from_source_path(str(safe_evidence.get("sourcePath") or suggested_id))
        )
    )
    decision = "can-be-dossier"
    if recommended_class == "not-a-dossier":
        decision = "not-a-dossier"
    elif recommended_class == "needs-review":
        decision = "needs-review"
    risks = list(intake_report.get("riskFlags") or [])
    if recommended_class == "hard":
        risks.append("real integration intentionally blocked in candidate-only V1")
    return normalise_intake_review({
        "decision": decision,
        "recommendedClass": recommended_class,
        "suggestedDossierId": suggested_id,
        "suggestedCapability": suggested_capability,
        "summary": (
            f"Deterministic review of {safe_evidence.get('sourcePath')}. "
            "Use this as operator guidance before candidate creation."
        ),
        "proposedContents": [
            "manifest.json",
            "instructions.md",
            "meta.json",
        ],
        "risks": sorted(set(risks)),
        "operatorQuestions": _operator_questions_for_review(recommended_class, suggested_capability),
        "testPlan": [
            "Validate manifest schema.",
            "Confirm no secrets are copied or sent to the model.",
            "Create candidate only after operator review.",
        ],
        "promotionBlockedReason": (
            "Hard candidates need a separate reviewed integration PR before canonical promotion."
            if recommended_class == "hard"
            else ""
        ),
        "source": source,
        "modelRole": DOSSIER_ROLE_ID,
        "modelUsed": model_used,
    })


def _call_intake_review_model(
    *,
    operator_brief: str,
    intake_report: dict[str, Any],
    safe_evidence: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    payload = {
        "operatorBrief": operator_brief,
        "intakeReport": sanitize_intake_report_for_model(intake_report),
        "safeEvidence": safe_evidence,
        "hardRules": [
            "Return structured JSON only.",
            "Use only intakeReport and safeEvidence; do not assume unseen file contents.",
            "Never ask to write canonical Dossiers, runtime wiring, API routes, env-contracts or integration-contracts in this V1.1 review.",
            "For hard candidates, explain that real integration work is blocked until a separate reviewed PR.",
            "Prefer capability slugs from source path/manifest over slugging the operator question.",
        ],
    }
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You review local Dossier candidate intake for Sajtbyggaren. "
                    "Decide if it can become a reusable candidate-only Dossier."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        text_format=DossierIntakeReviewModel,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("dossierModel returned no structured intake review")
    return parsed.model_dump()


def review_dossier_intake_with_model(
    *,
    operator_brief: str,
    intake_report: dict[str, Any],
    safe_evidence: dict[str, Any],
    use_llm: bool = True,
) -> dict[str, Any]:
    """Review an intake report with dossierModel or deterministic fallback."""
    if use_llm and has_openai_api_key():
        try:
            model_used = resolve_dossier_model()
            review = normalise_intake_review(_call_intake_review_model(
                operator_brief=operator_brief,
                intake_report=sanitize_intake_report_for_model(intake_report),
                safe_evidence=safe_evidence,
                model=model_used,
            ))
            review["source"] = "real"
            review["modelRole"] = DOSSIER_ROLE_ID
            review["modelUsed"] = model_used
            return review
        except Exception as exc:
            fallback = _deterministic_intake_review(
                operator_brief=operator_brief,
                intake_report=intake_report,
                safe_evidence=safe_evidence,
                source="mock-llm-error",
                model_used="mock",
            )
            fallback["risks"].append(f"dossierModel fallback used: {exc}")
            return fallback
    return _deterministic_intake_review(
        operator_brief=operator_brief,
        intake_report=intake_report,
        safe_evidence=safe_evidence,
        source="mock-no-key" if use_llm else "deterministic-v1",
        model_used="mock" if use_llm else "deterministic",
    )


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
