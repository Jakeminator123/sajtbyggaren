"""Generate draft Scaffold Variant JSON files.

The script reads the canonical Scaffold file set for one Scaffold and writes
one or more draft Variant JSON files under ``data/variant-candidates/``. It
does not write directly into ``packages/generation/orchestration/scaffolds``;
promotion to a canonical Variant remains an operator decision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.artifacts import (  # noqa: E402
    validate_scaffold,
    validate_sections,
    validate_variant,
)
from packages.generation.brief.models import (  # noqa: E402
    OPENAI_API_KEY_ENV,
    has_openai_api_key,
)

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "variant-candidates"
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"
SCAFFOLD_CONTRACT_PATH = REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"
VARIANT_SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "variant.schema.json"

VARIANT_ROLE_ID = "variantModel"
EXPECTED_PROVIDER = "openai"
SLUG_PATTERN_TEXT = r"^[a-z][a-z0-9-]*$"
SLUG_PATTERN = re.compile(SLUG_PATTERN_TEXT)
SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
SLUG_DASHES = re.compile(r"-{2,}")


class VariantGenerationError(RuntimeError):
    """Raised when a Variant candidate cannot be generated or written."""


class VariantModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json has no usable variantModel role."""


class ColorTokens(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    background: str
    foreground: str
    muted: str
    border: str
    primary: str
    primary_foreground: str = Field(alias="primaryForeground")
    accent: str
    accent_foreground: str = Field(alias="accentForeground")


class TypographyTokens(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    font_family_display: str = Field(alias="fontFamilyDisplay")
    font_family_body: str = Field(alias="fontFamilyBody")
    font_family_mono: str = Field(alias="fontFamilyMono")
    scale_ratio: float = Field(alias="scaleRatio", ge=1, le=1.6)


class RadiusTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sm: str
    md: str
    lg: str


class SpacingTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str
    container: str


class MotionTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str


class VariantTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: ColorTokens
    typography: TypographyTokens
    radius: RadiusTokens
    spacing: SpacingTokens
    motion: MotionTokens


class VariantTone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vibe: list[str]


class VariantCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=SLUG_PATTERN_TEXT)
    enabled: bool
    label: str
    description: str
    tokens: VariantTokens
    tone: VariantTone


@dataclass(frozen=True)
class VariantContext:
    """Canonical input context for generating one Variant candidate."""

    scaffold_id: str
    scaffold_dir: Path
    required_files: dict[str, dict[str, Any]]
    existing_variants: list[dict[str, Any]]
    variant_schema: dict[str, Any]

    @property
    def existing_variant_ids(self) -> set[str]:
        return {
            variant["id"]
            for variant in self.existing_variants
            if isinstance(variant.get("id"), str)
        }

    def as_prompt_payload(self) -> dict[str, Any]:
        """Return the exact context passed to variantModel."""
        return {
            "scaffoldId": self.scaffold_id,
            "requiredScaffoldFiles": self.required_files,
            "existingVariants": self.existing_variants,
            "existingVariantIds": sorted(self.existing_variant_ids),
            "variantOutputSchema": self.variant_schema,
            "hardRules": [
                "Return exactly one Variant JSON object.",
                "Do not define routes, sections, page content, Dossiers or starter behavior.",
                "Use only the fields allowed by variant.schema.json.",
                "Set enabled to false unless the operator explicitly asks otherwise.",
                "Use a unique id that does not appear in existingVariantIds.",
            ],
        }


@dataclass(frozen=True)
class VariantGenerationResult:
    """Result metadata for one written candidate file."""

    path: Path
    payload: dict[str, Any]
    source: str
    model_used: str


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VariantGenerationError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise VariantGenerationError(f"{path} must contain a JSON object")
    return payload


def resolve_variant_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for variantModel."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise VariantModelResolutionError(f"llm-models.v1.json missing at {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VariantModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != VARIANT_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise VariantModelResolutionError(
                f"variantModel provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise VariantModelResolutionError(
                "variantModel role is missing a non-empty model value"
            )
        return model

    raise VariantModelResolutionError(f"variantModel role missing from {path.name}")


def slugify_variant_id(text: str) -> str:
    """Return a valid Variant id slug from free text."""
    normalised = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(
        char for char in normalised if not unicodedata.combining(char)
    )
    cleaned = SLUG_CLEAN.sub("-", ascii_text.lower()).strip("-")
    cleaned = SLUG_DASHES.sub("-", cleaned)
    if not cleaned:
        cleaned = "generated-variant"
    if cleaned[0].isdigit():
        cleaned = f"variant-{cleaned}"
    return cleaned


def _unique_variant_id(base: str, reserved_ids: set[str]) -> str:
    candidate = slugify_variant_id(base)
    if candidate not in reserved_ids:
        return candidate
    suffix = 2
    while f"{candidate}-{suffix}" in reserved_ids:
        suffix += 1
    return f"{candidate}-{suffix}"


def _required_scaffold_files() -> list[str]:
    contract = _read_json(SCAFFOLD_CONTRACT_PATH)
    files = contract.get("scaffoldDirectoryLayout", {}).get("requiredFiles", [])
    if not files:
        raise VariantGenerationError("scaffold-contract.v1.json has no requiredFiles")
    return [str(file_name) for file_name in files]


def load_variant_context(
    scaffold_id: str,
    *,
    scaffolds_dir: Path = SCAFFOLDS_DIR,
) -> VariantContext:
    """Read the exact Scaffold files that inform Variant generation."""
    if not SLUG_PATTERN.match(scaffold_id):
        raise VariantGenerationError(f"Invalid scaffold id: {scaffold_id!r}")

    scaffold_dir = (scaffolds_dir / scaffold_id).resolve()
    allowed_root = scaffolds_dir.resolve()
    if allowed_root not in scaffold_dir.parents:
        raise VariantGenerationError(f"Scaffold path escapes {allowed_root}: {scaffold_dir}")
    if not scaffold_dir.exists():
        raise VariantGenerationError(f"Unknown scaffold: {scaffold_id}")

    required_files: dict[str, dict[str, Any]] = {}
    for relative_path in _required_scaffold_files():
        path = scaffold_dir / relative_path
        if not path.exists():
            raise VariantGenerationError(
                f"Scaffold {scaffold_id!r} is missing {relative_path}"
            )
        payload = _read_json(path)
        if relative_path == "scaffold.json":
            validate_scaffold(payload)
        if relative_path == "sections.json":
            validate_sections(payload)
        required_files[relative_path] = payload

    existing_variants: list[dict[str, Any]] = []
    variants_dir = scaffold_dir / "variants"
    if variants_dir.exists():
        for variant_path in sorted(variants_dir.glob("*.json")):
            variant = _read_json(variant_path)
            validate_variant(variant)
            existing_variants.append(variant)

    variant_schema = _read_json(VARIANT_SCHEMA_PATH)
    return VariantContext(
        scaffold_id=scaffold_id,
        scaffold_dir=scaffold_dir,
        required_files=required_files,
        existing_variants=existing_variants,
        variant_schema=variant_schema,
    )


def build_variant_prompt_payload(
    *,
    context: VariantContext,
    brief: str,
    requested_variant_id: str | None,
    enabled: bool,
) -> dict[str, Any]:
    """Build the structured payload sent to variantModel."""
    return {
        "operatorBrief": brief,
        "requestedVariantId": requested_variant_id,
        "enabled": enabled,
        "context": context.as_prompt_payload(),
    }


def _call_variant_model(
    *,
    context: VariantContext,
    brief: str,
    requested_variant_id: str | None,
    enabled: bool,
    model: str,
) -> dict[str, Any]:
    """Call OpenAI variantModel with strict structured output."""
    from openai import OpenAI

    client = OpenAI()
    payload = build_variant_prompt_payload(
        context=context,
        brief=brief,
        requested_variant_id=requested_variant_id,
        enabled=enabled,
    )
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You generate one Scaffold Variant JSON object for "
                    "Sajtbyggaren. Follow the schema exactly. A Variant "
                    "controls visual expression only."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        text_format=VariantCandidateModel,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("variantModel returned no structured output")
    return parsed.model_dump(by_alias=True)


def _label_from_variant_id(variant_id: str) -> str:
    return " ".join(part.capitalize() for part in variant_id.split("-"))


def _mock_variant_candidate(
    *,
    brief: str,
    variant_id: str,
    enabled: bool,
) -> dict[str, Any]:
    """Deterministic local fallback used without OPENAI_API_KEY."""
    lower_brief = brief.lower()
    if any(signal in lower_brief for signal in ("dark", "mork", "mörk", "contrast")):
        palette = {
            "background": "#111315",
            "foreground": "#f7f4ed",
            "muted": "#b8b1a3",
            "border": "#2b3033",
            "primary": "#f0b35a",
            "primaryForeground": "#111315",
            "accent": "#7cc7b8",
            "accentForeground": "#111315",
        }
        motion = "subtle"
        vibes = ["confident", "contrast-rich", "premium", "focused"]
    elif any(signal in lower_brief for signal in ("warm", "varm", "craft", "human")):
        palette = {
            "background": "#fbf7f0",
            "foreground": "#211d18",
            "muted": "#766b5f",
            "border": "#e4d8c8",
            "primary": "#8d4f2f",
            "primaryForeground": "#fffaf3",
            "accent": "#2f6f68",
            "accentForeground": "#fffaf3",
        }
        motion = "subtle"
        vibes = ["warm", "human", "crafted", "trustworthy"]
    elif any(signal in lower_brief for signal in ("bold", "lekfull", "playful")):
        palette = {
            "background": "#f8f8ff",
            "foreground": "#171321",
            "muted": "#6f6881",
            "border": "#dedaf0",
            "primary": "#4b3fd4",
            "primaryForeground": "#ffffff",
            "accent": "#f0c24b",
            "accentForeground": "#171321",
        }
        motion = "expressive"
        vibes = ["bold", "clear", "energetic", "approachable"]
    else:
        palette = {
            "background": "#f7f8f5",
            "foreground": "#18201b",
            "muted": "#68706a",
            "border": "#dde3dc",
            "primary": "#245c45",
            "primaryForeground": "#f7f8f5",
            "accent": "#b98f45",
            "accentForeground": "#18201b",
        }
        motion = "subtle"
        vibes = ["calm", "local", "credible", "polished"]

    label = _label_from_variant_id(variant_id)
    return {
        "id": variant_id,
        "enabled": enabled,
        "label": label,
        "description": (
            f"{label} visual expression generated from the operator brief. "
            "Candidate only; review against real small-business previews before promotion."
        ),
        "tokens": {
            "color": palette,
            "typography": {
                "fontFamilyDisplay": "var(--font-geist-sans)",
                "fontFamilyBody": "var(--font-geist-sans)",
                "fontFamilyMono": "var(--font-geist-mono)",
                "scaleRatio": 1.22,
            },
            "radius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem"},
            "spacing": {"section": "5.5rem", "container": "min(74rem, 92vw)"},
            "motion": {"level": motion},
        },
        "tone": {"vibe": vibes},
    }


def _normalise_variant_payload(
    payload: dict[str, Any],
    *,
    requested_variant_id: str | None,
    enabled: bool,
) -> dict[str, Any]:
    if requested_variant_id:
        payload = dict(payload)
        payload["id"] = slugify_variant_id(requested_variant_id)
    payload["enabled"] = enabled
    model = VariantCandidateModel.model_validate(payload)
    normalised = model.model_dump(by_alias=True)
    validate_variant(normalised)
    return normalised


def _write_candidate(
    payload: dict[str, Any],
    *,
    scaffold_id: str,
    output_dir: Path,
    force: bool,
) -> Path:
    target_dir = output_dir / scaffold_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{payload['id']}.json"
    if target_path.exists() and not force:
        raise VariantGenerationError(
            f"Candidate already exists: {target_path}. Pass --force to overwrite."
        )
    target_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target_path


def generate_variant_candidates(
    *,
    scaffold_id: str,
    brief: str,
    variant_id: str | None = None,
    count: int = 1,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    enabled: bool = False,
    force: bool = False,
    use_llm: bool = True,
) -> list[VariantGenerationResult]:
    """Generate and write one or more Variant candidate files."""
    if count < 1:
        raise VariantGenerationError("count must be at least 1")
    if not brief.strip():
        raise VariantGenerationError("brief must not be empty")

    context = load_variant_context(scaffold_id)
    reserved_ids = set(context.existing_variant_ids)
    results: list[VariantGenerationResult] = []

    for index in range(count):
        base_id = variant_id or brief
        if count > 1:
            base_id = f"{base_id} {index + 1}"
        candidate_id = _unique_variant_id(base_id, reserved_ids)
        reserved_ids.add(candidate_id)

        source = "mock-no-key" if use_llm else "deterministic-v1"
        model_used = "mock" if use_llm else "deterministic"
        payload: dict[str, Any]
        if use_llm and has_openai_api_key():
            try:
                model_used = resolve_variant_model()
                payload = _call_variant_model(
                    context=context,
                    brief=(
                        f"{brief}\n\nCandidate {index + 1} of {count}: "
                        "make this visual direction distinct from sibling candidates."
                    ),
                    requested_variant_id=candidate_id,
                    enabled=enabled,
                    model=model_used,
                )
                source = "real"
            except Exception as exc:  # pragma: no cover - covered via caller tests
                print(f"variantModel failed; using mock fallback: {exc}", file=sys.stderr)
                payload = _mock_variant_candidate(
                    brief=brief,
                    variant_id=candidate_id,
                    enabled=enabled,
                )
                source = "mock-llm-error"
        else:
            payload = _mock_variant_candidate(
                brief=brief,
                variant_id=candidate_id,
                enabled=enabled,
            )

        payload = _normalise_variant_payload(
            payload,
            requested_variant_id=candidate_id,
            enabled=enabled,
        )
        path = _write_candidate(
            payload,
            scaffold_id=scaffold_id,
            output_dir=output_dir,
            force=force,
        )
        results.append(
            VariantGenerationResult(
                path=path,
                payload=payload,
                source=source,
                model_used=model_used,
            )
        )

    return results


def _available_scaffold_ids() -> list[str]:
    if not SCAFFOLDS_DIR.exists():
        return []
    return sorted(path.name for path in SCAFFOLDS_DIR.iterdir() if path.is_dir())


def _fill_interactive(args: argparse.Namespace) -> argparse.Namespace:
    if not args.scaffold:
        scaffolds = _available_scaffold_ids()
        print("Available scaffolds:")
        for scaffold_id in scaffolds:
            print(f"  - {scaffold_id}")
        args.scaffold = input("Scaffold id: ").strip()
    if not args.brief:
        args.brief = input("Variant brief: ").strip()
    if not args.variant_id:
        entered = input("Variant id (blank = auto): ").strip()
        args.variant_id = entered or None
    return args


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate draft Scaffold Variant JSON under data/variant-candidates/."
    )
    parser.add_argument("--scaffold", help="Scaffold id, for example local-service-business")
    parser.add_argument("--brief", help="Short visual direction for the Variant")
    parser.add_argument("--variant-id", help="Optional Variant id slug")
    parser.add_argument("--count", type=int, default=1, help="Number of candidates to write")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for candidate files",
    )
    parser.add_argument(
        "--enabled",
        action="store_true",
        help="Write enabled:true. Default is enabled:false for draft safety.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing candidate files")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic local fallback")
    parser.add_argument("--interactive", action="store_true", help="Ask for missing inputs")
    parser.add_argument("--list-scaffolds", action="store_true", help="Print scaffold ids and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_scaffolds:
        for scaffold_id in _available_scaffold_ids():
            print(scaffold_id)
        return 0

    if args.interactive:
        args = _fill_interactive(args)
    if not args.scaffold or not args.brief:
        print(
            "--scaffold and --brief are required unless --interactive is used",
            file=sys.stderr,
        )
        return 2

    try:
        results = generate_variant_candidates(
            scaffold_id=args.scaffold,
            brief=args.brief,
            variant_id=args.variant_id,
            count=args.count,
            output_dir=args.output_dir,
            enabled=args.enabled,
            force=args.force,
            use_llm=not args.no_llm,
        )
    except VariantGenerationError as exc:
        print(f"variant candidate generation failed: {exc}", file=sys.stderr)
        return 1

    key_state = "present" if has_openai_api_key() else "missing"
    print(f"{OPENAI_API_KEY_ENV}: {key_state}")
    for result in results:
        print(f"variantPath: {result.path.resolve()}")
        print(f"source: {result.source}")
        print(f"modelUsed: {result.model_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
