"""Generate draft Dossier candidate folders.

The script writes candidate-only folders under ``data/dossier-candidates/``.
It never writes into canonical ``packages/generation/orchestration/dossiers``;
promotion remains an operator decision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.artifacts import validate_dossier  # noqa: E402
from packages.generation.brief.models import (  # noqa: E402
    OPENAI_API_KEY_ENV,
    has_openai_api_key,
)
from scripts.candidate_generation_metadata import (  # noqa: E402
    brief_fingerprint,
    created_at,
    guard_candidate_output_dir,
    repo_or_output_relative,
)
from scripts.dossier_candidate_intake import (  # noqa: E402
    intake_report_hash,
    sanitize_intake_report_for_model,
)

DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
ORCHESTRATION_DIR = REPO_ROOT / "packages" / "generation" / "orchestration"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "dossier-candidates"
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"
DOSSIER_ROLE_ID = "dossierModel"
EXPECTED_PROVIDER = "openai"
SLUG_PATTERN_TEXT = r"^[a-z][a-z0-9-]*$"
SLUG_PATTERN = re.compile(SLUG_PATTERN_TEXT)
SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
SLUG_DASHES = re.compile(r"-{2,}")
CANDIDATE_CLASSES = {"soft", "hard"}


class DossierGenerationError(RuntimeError):
    """Raised when a Dossier candidate cannot be generated or written."""


class DossierModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json has no usable dossierModel role."""


class DossierManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: str | None = Field(default=None, alias="$schema")
    id: str = Field(pattern=SLUG_PATTERN_TEXT)
    enabled: bool
    label: str
    capability: str = Field(pattern=SLUG_PATTERN_TEXT)
    class_: str = Field(alias="class")
    code_fidelity: str = Field(alias="codeFidelity")
    complexity: str
    default_for_capability: bool = Field(alias="defaultForCapability")
    summary: str
    env_vars: list[str] = Field(alias="envVars")
    dependencies: list[str]
    files: list[str]
    exposes: list[str]
    last_verified: str = Field(alias="lastVerified")


class DossierCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: DossierManifestModel
    instructionsMarkdown: str


@dataclass(frozen=True)
class DossierGenerationResult:
    """Result metadata for one written Dossier candidate."""

    candidate_dir: Path
    manifest_path: Path
    instructions_path: Path
    meta_path: Path
    manifest: dict[str, Any]
    instructions: str
    metadata: dict[str, Any]
    source: str
    model_used: str


def _guard_dossier_output_dir(output_dir: Path) -> None:
    """Thin wrapper that pins the Dossier-specific guard arguments."""
    guard_candidate_output_dir(
        output_dir,
        forbidden_roots=(ORCHESTRATION_DIR, SCAFFOLDS_DIR, DOSSIERS_DIR),
        error_cls=DossierGenerationError,
        kind="Dossier",
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DossierGenerationError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DossierGenerationError(f"{path} must contain a JSON object")
    return payload


def resolve_dossier_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for dossierModel."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise DossierModelResolutionError(f"llm-models.v1.json missing at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DossierModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc
    for role in data.get("roles", []):
        if role.get("id") != DOSSIER_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise DossierModelResolutionError(
                f"dossierModel provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise DossierModelResolutionError(
                "dossierModel role is missing a non-empty model value"
            )
        return model
    raise DossierModelResolutionError(f"dossierModel role missing from {path.name}")


def slugify_dossier_id(text: str) -> str:
    """Return a valid Dossier id slug from free text."""
    normalised = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(
        char for char in normalised if not unicodedata.combining(char)
    )
    cleaned = SLUG_CLEAN.sub("-", ascii_text.lower()).strip("-")
    cleaned = SLUG_DASHES.sub("-", cleaned)
    if not cleaned:
        cleaned = "generated-dossier"
    if cleaned[0].isdigit():
        cleaned = f"dossier-{cleaned}"
    return cleaned


def _existing_dossier_ids() -> set[str]:
    ids: set[str] = set()
    for manifest_path in DOSSIERS_DIR.glob("*/*/manifest.json"):
        try:
            payload = _read_json(manifest_path)
        except DossierGenerationError:
            continue
        dossier_id = payload.get("id")
        if isinstance(dossier_id, str):
            ids.add(dossier_id)
    return ids


def _unique_dossier_id(
    base: str,
    output_dir: Path,
    reserved_ids: set[str],
    candidate_class: str,
) -> str:
    candidate = slugify_dossier_id(base)
    if candidate not in reserved_ids and not _candidate_id_exists(output_dir, candidate):
        return candidate
    suffix = 2
    while True:
        next_id = f"{candidate}-{suffix}"
        if next_id not in reserved_ids and not _candidate_id_exists(output_dir, next_id):
            return next_id
        suffix += 1


def _candidate_id_exists(output_dir: Path, dossier_id: str) -> bool:
    """Return True when a candidate id already exists in any candidate class."""
    return any((output_dir / candidate_class / dossier_id).exists() for candidate_class in CANDIDATE_CLASSES)


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _label_from_id(dossier_id: str) -> str:
    return " ".join(part.capitalize() for part in dossier_id.split("-"))


def _mock_dossier_candidate(
    *,
    brief: str,
    dossier_id: str,
    capability: str,
    candidate_class: str,
    intake_report: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Deterministic local fallback used without OPENAI_API_KEY."""
    label = _label_from_id(dossier_id)
    source_hint = ""
    if intake_report:
        source_hint = f" based on read-only intake of {intake_report.get('sourcePath')}"
    manifest = {
        "$schema": "../../../../../../governance/schemas/dossier.schema.json",
        "id": dossier_id,
        "enabled": False,
        "label": label,
        "capability": capability,
        "class": candidate_class,
        "codeFidelity": "instructions-only",
        "complexity": "low",
        "defaultForCapability": False,
        "summary": (
            f"Candidate-only {candidate_class} Dossier for {brief.strip()}{source_hint}. Review and promote "
            "manually before canonical use."
        ),
        "envVars": [],
        "dependencies": [],
        "files": [],
        "exposes": [],
        "lastVerified": _today(),
    }
    hard_guidance = ""
    if candidate_class == "hard":
        hard_guidance = """
# Hard-candidate boundary

- This candidate only documents a capability that appears to need secrets, API access or backend work later.
- Do not add API routes, backend files, env-contract.json or integration-contract.json in this V1 candidate.
- Define the real integration in a separate reviewed implementation PR before canonical promotion.
"""

    instructions = f"""# When to use

Use this candidate Dossier when a project needs: {brief.strip()}.

# How to integrate

- Keep the implementation frontend-only.
- Do not require secrets, backend services, auth, payments or external APIs.
- Prefer instructions and small reusable components over broad starter changes.
- Keep copy and visuals project-specific; this Dossier only describes the reusable capability.
{hard_guidance}

# Avoid

- Do not add environment variables.
- Do not add runtime dependencies without an explicit operator review.
- Do not enable this candidate until it has been reviewed against real generated previews.

# Verification

- Confirm the generated site still builds without real environment variables.
- Confirm the capability appears only when the selected project asks for it.
- Confirm keyboard and mobile behavior if the capability is interactive.
"""
    return manifest, instructions


def _normalise_candidate(
    manifest: dict[str, Any],
    instructions: str,
    *,
    dossier_id: str,
    capability: str,
    candidate_class: str,
) -> tuple[dict[str, Any], str]:
    if candidate_class not in CANDIDATE_CLASSES:
        raise DossierGenerationError(f"Invalid Dossier candidate class: {candidate_class!r}")
    manifest = dict(manifest)
    manifest["id"] = dossier_id
    manifest["capability"] = capability
    manifest["class"] = candidate_class
    manifest["enabled"] = False
    # V1 hard candidates are audit artifacts, not real integrations. The
    # current dossier schema accepts empty envVars/dependencies for both
    # classes, and dossier-contract.v1 has no extra required hard files yet.
    # A future promotion/integration PR must add real env/integration
    # contracts before canonical use.
    manifest["envVars"] = []
    manifest["dependencies"] = []
    model = DossierManifestModel.model_validate(manifest)
    normalised_manifest = model.model_dump(by_alias=True, exclude_none=True)
    validate_dossier(normalised_manifest)
    if not instructions.strip():
        raise DossierGenerationError("instructionsMarkdown must not be empty")
    return normalised_manifest, instructions.strip() + "\n"


def _call_dossier_model(
    *,
    brief: str,
    dossier_id: str,
    capability: str,
    candidate_class: str,
    model: str,
    intake_report: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Call OpenAI dossierModel with strict structured output."""
    from openai import OpenAI

    client = OpenAI()
    payload = {
        "operatorBrief": brief,
        "requestedDossierId": dossier_id,
        "capability": capability,
        "candidateClass": candidate_class,
        "intakeReport": (
            sanitize_intake_report_for_model(intake_report) if intake_report else None
        ),
        "hardRules": [
            "Return one Dossier candidate only.",
            f"Set manifest.class to {candidate_class} and enabled to false.",
            "Do not add env vars or dependencies in this candidate.",
            "For hard candidates, document that real integration work must happen later; do not create backend/API/env-contract/integration-contract files.",
            "Do not write canonical files; this is a candidate for manual review.",
            "instructionsMarkdown must be practical English Markdown for codegen.",
        ],
    }
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You generate candidate-only Dossier manifests and "
                    "instructions for Sajtbyggaren. Respect candidateClass."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        text_format=DossierCandidateModel,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("dossierModel returned no structured output")
    output = parsed.model_dump(by_alias=True)
    return output["manifest"], output["instructionsMarkdown"]


def _write_candidate(
    *,
    output_dir: Path,
    dossier_id: str,
    manifest: dict[str, Any],
    instructions: str,
    source: str,
    model_used: str,
    operator_brief: str,
    intake_report: dict[str, Any] | None,
    force: bool,
) -> tuple[Path, Path, Path, Path, dict[str, Any]]:
    _guard_dossier_output_dir(output_dir)
    dossier_class = str(manifest["class"])
    if dossier_class not in CANDIDATE_CLASSES:
        raise DossierGenerationError(f"Invalid Dossier candidate class: {dossier_class!r}")
    candidate_dir = output_dir / dossier_class / dossier_id
    if candidate_dir.exists() and not force:
        raise DossierGenerationError(
            f"Candidate already exists: {candidate_dir}. Pass --force to overwrite."
        )
    candidate_dir.mkdir(parents=True, exist_ok=True)
    if dossier_class == "soft":
        components_dir = candidate_dir / "components"
        components_dir.mkdir(exist_ok=True)
    manifest_path = candidate_dir / "manifest.json"
    instructions_path = candidate_dir / "instructions.md"
    meta_path = candidate_dir / "meta.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    instructions_path.write_text(instructions, encoding="utf-8")
    metadata = {
        "schemaVersion": 1,
        "candidateType": "dossier",
        "candidateId": manifest["id"],
        "capability": manifest["capability"],
        "source": source,
        "modelUsed": model_used,
        "modelRole": DOSSIER_ROLE_ID,
        "generator": "scripts.generate_dossier_candidate",
        "generatedBy": (
            "dossier-candidate-intake-v1" if intake_report else "brief-only"
        ),
        "createdAt": created_at(),
        "enabled": manifest["enabled"],
        "outputPath": repo_or_output_relative(
            manifest_path, repo_root=REPO_ROOT, output_dir=output_dir
        ),
        "instructionsPath": repo_or_output_relative(
            instructions_path, repo_root=REPO_ROOT, output_dir=output_dir
        ),
        "operatorBriefHash": brief_fingerprint(operator_brief),
    }
    if intake_report:
        metadata.update(
            {
                "sourcePath": str(intake_report.get("sourcePath") or ""),
                "sourceFileCount": int(intake_report.get("fileCount") or 0),
                "intakeReportHash": str(
                    intake_report.get("reportHash") or intake_report_hash(intake_report)
                ),
                "intakeRecommendedClass": str(
                    intake_report.get("recommendedClass") or ""
                ),
            }
        )
    meta_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return candidate_dir, manifest_path, instructions_path, meta_path, metadata


def generate_dossier_candidate(
    *,
    brief: str,
    candidate_id: str | None = None,
    capability: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    force: bool = False,
    use_llm: bool = True,
    intake_report: dict[str, Any] | None = None,
) -> DossierGenerationResult:
    """Generate and write one Dossier candidate folder."""
    if not brief.strip():
        raise DossierGenerationError("brief must not be empty")
    _guard_dossier_output_dir(output_dir)
    recommended_class = str((intake_report or {}).get("recommendedClass") or "soft")
    if recommended_class == "not-a-dossier":
        raise DossierGenerationError(
            "intake_report recommends not-a-dossier; refusing to write candidate"
        )
    candidate_class = "hard" if recommended_class == "hard" else "soft"
    reserved = _existing_dossier_ids()
    suggested_id = str((intake_report or {}).get("suggestedDossierId") or "")
    suggested_capability = str((intake_report or {}).get("suggestedCapability") or "")
    dossier_id = _unique_dossier_id(
        candidate_id or suggested_id or brief,
        output_dir,
        reserved,
        candidate_class,
    )
    capability_id = slugify_dossier_id(capability or suggested_capability or dossier_id)

    source = "mock-no-key" if use_llm else "deterministic-v1"
    model_used = "mock" if use_llm else "deterministic"
    if use_llm and has_openai_api_key():
        try:
            model_used = resolve_dossier_model()
            manifest, instructions = _call_dossier_model(
                brief=brief,
                dossier_id=dossier_id,
                capability=capability_id,
                candidate_class=candidate_class,
                model=model_used,
                intake_report=(
                    sanitize_intake_report_for_model(intake_report)
                    if intake_report
                    else None
                ),
            )
            source = "real"
        except Exception as exc:  # pragma: no cover - covered by caller tests
            print(f"dossierModel failed; using mock fallback: {exc}", file=sys.stderr)
            manifest, instructions = _mock_dossier_candidate(
                brief=brief,
                dossier_id=dossier_id,
                capability=capability_id,
                candidate_class=candidate_class,
                intake_report=intake_report,
            )
            source = "mock-llm-error"
    else:
        manifest, instructions = _mock_dossier_candidate(
            brief=brief,
            dossier_id=dossier_id,
            capability=capability_id,
            candidate_class=candidate_class,
            intake_report=intake_report,
        )

    manifest, instructions = _normalise_candidate(
        manifest,
        instructions,
        dossier_id=dossier_id,
        capability=capability_id,
        candidate_class=candidate_class,
    )
    candidate_dir, manifest_path, instructions_path, meta_path, metadata = _write_candidate(
        output_dir=output_dir,
        dossier_id=dossier_id,
        manifest=manifest,
        instructions=instructions,
        source=source,
        model_used=model_used,
        operator_brief=brief,
        intake_report=intake_report,
        force=force,
    )
    return DossierGenerationResult(
        candidate_dir=candidate_dir,
        manifest_path=manifest_path,
        instructions_path=instructions_path,
        meta_path=meta_path,
        manifest=manifest,
        instructions=instructions,
        metadata=metadata,
        source=source,
        model_used=model_used,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a draft Dossier candidate under data/dossier-candidates/."
    )
    parser.add_argument("--brief", required=True, help="Short capability brief")
    parser.add_argument("--candidate-id", help="Optional Dossier candidate id slug")
    parser.add_argument("--capability", help="Optional capability slug")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for Dossier candidates",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing candidate")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic local fallback")
    parser.add_argument(
        "--intake-report",
        type=Path,
        help="Optional JSON report from scripts/dossier_candidate_intake.py",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        intake_report = _read_json(args.intake_report) if args.intake_report else None
        result = generate_dossier_candidate(
            brief=args.brief,
            candidate_id=args.candidate_id,
            capability=args.capability,
            output_dir=args.output_dir,
            force=args.force,
            use_llm=not args.no_llm,
            intake_report=intake_report,
        )
    except DossierGenerationError as exc:
        print(f"dossier candidate generation failed: {exc}", file=sys.stderr)
        return 1
    key_state = "present" if has_openai_api_key() else "missing"
    print(f"{OPENAI_API_KEY_ENV}: {key_state}")
    print(f"candidateDir: {result.candidate_dir.resolve()}")
    print(f"source: {result.source}")
    print(f"modelUsed: {result.model_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
