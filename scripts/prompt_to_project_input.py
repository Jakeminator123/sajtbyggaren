"""Convert a free-form prompt into a minimal Project Input for build_site.py.

Wires Phase 1 (briefModel via packages.generation.brief.extract_site_brief)
to a deterministic Site Brief -> Project Input mapping so the operator can
go from "skriv en mening" -> riktig sajt-build via the existing builder.

Why this lives in scripts/ and not packages/generation/brief/:

- ``packages/generation/brief/`` owns prompt -> Site Brief (Phase 1
  Understand). Its mustNotDo list (repo-boundaries.v1.json) explicitly
  excludes "välja Scaffold". Picking a scaffoldId/variantId for the
  Project Input is a scaffold-selection-shaped decision, even when the
  heuristic is intentionally tiny.
- ``apps/viewser/`` mustNotDo includes writing to data/ or examples/.
  This script writes the generated Project Input to a scratch directory
  that viewser's POST /api/prompt route hands to scripts/build_site.py
  via the existing build-runner spawn pattern. Scripts may write to data/.

Output contract (for callers like apps/viewser/app/api/prompt/route.ts):

- Prints ``siteId: <id>`` and ``dossierPath: <abs-path>`` on stdout, one
  per line. Mirrors the ``runId: <id>`` contract that build_site.py uses
  so the same regex-based parser pattern works in build-runner.ts.
- Writes ``data/prompt-inputs/<siteId>.project-input.json`` (validates
  against governance/schemas/project-input.schema.json before writing).
- Writes ``data/prompt-inputs/<siteId>.meta.json`` with projectId,
  version, originalPrompt, briefSource. Follow-up mode reads that sidecar,
  reuses projectId, increments version and writes a fresh Project Input
  from the operator's latest prompt without changing the Project Input schema.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief import (  # noqa: E402
    detect_language,
    extract_site_brief,
    site_brief_to_artifact,
)
from packages.generation.brief.models import resolve_brief_model  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "prompt-inputs"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"

# Mirrors apps/viewser/lib/project-inputs.ts SITE_ID_PATTERN. Lower-case
# letters, digits and dashes, must start and end with alphanumeric.
# Centralising the pattern in two languages is a known duplication; a
# future sprint can hoist it into a shared policy if more tools need it.
_SITE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
_SLUG_DASHES = re.compile(r"-{2,}")

_SCAFFOLD_LOCAL_SERVICE = ("local-service-business", "nordic-trust")
_SCAFFOLD_ECOMMERCE = ("ecommerce-lite", "clean-store")

# Tokens that flip the default scaffold to ecommerce-lite. Kept tiny on
# purpose: real Scaffold Selector logic belongs in
# packages/generation/orchestration/selection/ (not in scripts/) and
# blocked behind an ADR. Until that lands, pick the more generic
# local-service-business scaffold unless the prompt clearly says "shop".
_ECOMMERCE_TOKENS = frozenset(
    {
        "butik",
        "butikssajt",
        "ehandel",
        "e-handel",
        "ecommerce",
        "checkout",
        "store",
        "produkter",
        "products",
        "shop",
        "webshop",
        "webbshop",
        "sortiment",
    }
)


def slugify_site_id(text: str, *, suffix: str | None = None) -> str:
    """Produce a siteId that satisfies _SITE_ID_PATTERN.

    The first 24 chars come from the prompt (or a fallback "site" when
    the prompt has no usable letters). A short uuid suffix is always
    appended so two prompts that slugify to the same stem do not collide
    in data/prompt-inputs/. Operators that already know the exact id
    they want can pass it via the meta-sidecar tooling in a later
    sprint.
    """
    lowered = text.lower().strip()
    cleaned = _SLUG_CLEAN.sub("-", lowered).strip("-")
    cleaned = _SLUG_DASHES.sub("-", cleaned)
    stem = cleaned[:24].strip("-") or "site"
    tail = suffix or uuid.uuid4().hex[:6]
    candidate = f"{stem}-{tail}"
    if not _SITE_ID_PATTERN.match(candidate):
        # Fallback: prompt produced something unusable (e.g. only
        # punctuation / non-Latin script). Use plain "site-<tail>".
        candidate = f"site-{tail}"
    return candidate


def pick_scaffold(prompt: str, brief_business_type: str | None) -> tuple[str, str]:
    """Heuristic Scaffold + Variant pick for the generated Project Input.

    Returns (scaffoldId, variantId). Defaults to local-service-business
    /nordic-trust because every Site Brief field can be mapped onto it
    and the renderer always produces a 4-page site with services /
    contact. Flips to ecommerce-lite only when the prompt or detected
    business type clearly mentions a shop. The intent is to keep the
    MVP loop honest: a wrong scaffold is editable in the generated
    Project Input file before the operator re-builds.
    """
    haystack = (prompt or "").lower()
    business = (brief_business_type or "").lower()
    if any(token in haystack for token in _ECOMMERCE_TOKENS):
        return _SCAFFOLD_ECOMMERCE
    if "shop" in business or "store" in business or "ecommerce" in business:
        return _SCAFFOLD_ECOMMERCE
    return _SCAFFOLD_LOCAL_SERVICE


def _company_name_from_prompt(prompt: str, fallback: str) -> str:
    """Derive a short, human-readable company name from the prompt.

    Truncates to 60 chars and strips control characters so the value
    never breaks the JSX-escape pipeline downstream. This is best-effort
    only - the operator typically edits the generated Project Input
    file before sharing the build with anyone.
    """
    cleaned = " ".join((prompt or "").split())
    if not cleaned:
        return fallback
    return cleaned[:60].rstrip(" ,.!?") or fallback


def _service_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _service_summary(slug: str, language: str) -> str:
    label = _service_label(slug)
    if language == "en":
        return (
            f"{label} - placeholder summary generated from your prompt. "
            "Edit the Project Input to refine."
        )
    return (
        f"{label} - kort beskrivning genererad från din prompt. "
        "Justera Project Input för att förbättra texten."
    )


def _placeholder_services(language: str) -> list[dict[str, str]]:
    if language == "en":
        return [
            {
                "id": "consultation",
                "label": "Consultation",
                "summary": "Initial consultation - placeholder generated from your prompt.",
            }
        ]
    return [
        {
            "id": "konsultation",
            "label": "Konsultation",
            "summary": (
                "Inledande konsultation - platshållare som genererats från din prompt. "
                "Justera Project Input för att förbättra texten."
            ),
        }
    ]


def _build_services(
    services_mentioned: list[str], language: str
) -> list[dict[str, str]]:
    """Map the brief's services_mentioned slugs onto Project Input services.

    Returns at least one service so the schema's ``services minItems: 1``
    constraint is satisfied even when the brief is empty (e.g. mock
    fallback). Caps at five so the home page services grid stays
    visually balanced.
    """
    seen: set[str] = set()
    services: list[dict[str, str]] = []
    for raw in services_mentioned[:8]:
        slug = _SLUG_CLEAN.sub("-", raw.lower()).strip("-")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        services.append(
            {
                "id": slug,
                "label": _service_label(slug),
                "summary": _service_summary(slug, language),
            }
        )
        if len(services) >= 5:
            break
    if not services:
        services = _placeholder_services(language)
    return services


def _placeholder_contact(language: str) -> dict[str, Any]:
    """Schema-required contact block when the brief has no real values.

    Every field has minLength=1 in the schema so we cannot leave them
    blank. The placeholder strings are deliberately obvious ("uppdatera
    Project Input") so the operator notices them in the generated site
    and replaces them before sharing the build externally.
    """
    if language == "en":
        return {
            "phone": "+46 8 000 00 00",
            "email": "contact@example.se",
            "addressLines": ["Address placeholder - update Project Input"],
            "openingHours": "Mon-Fri 09:00-17:00",
        }
    return {
        "phone": "+46 8 000 00 00",
        "email": "kontakt@example.se",
        "addressLines": ["Adress saknas - uppdatera Project Input"],
        "openingHours": "Mån-Fre 09:00-17:00",
    }


def _placeholder_location(
    location_hint: str | None, language: str
) -> dict[str, Any]:
    """Schema-required location block.

    serviceAreas requires at least one entry. When the brief has no
    location hint we fall back to a generic Swedish placeholder so the
    builder never crashes on a missing city.
    """
    city = location_hint or ("Sweden" if language == "en" else "Sverige")
    country = "Sweden" if language == "en" else "Sverige"
    return {
        "city": city,
        "country": country,
        "serviceAreas": [city],
    }


def site_brief_to_project_input(
    brief: dict[str, Any],
    *,
    site_id: str,
    scaffold_id: str,
    variant_id: str,
    original_prompt: str,
) -> dict[str, Any]:
    """Deterministic Site Brief -> Project Input mapping.

    Operates on the canonical Site Brief artefakt shape (the dict that
    site_brief_to_artifact returns) so this helper works regardless of
    whether briefModel ran as 'real', 'mock-no-key' or 'mock-llm-error'.
    Missing fields fall back to schema-valid placeholders that the
    operator can edit in the generated Project Input file before
    re-building.
    """
    language = brief.get("language") or "sv"
    business_type = brief.get("businessTypeGuess") or (
        "shop" if scaffold_id == "ecommerce-lite" else "service-provider"
    )
    services = _build_services(
        brief.get("servicesMentioned") or [], language
    )
    notes = brief.get("notesForPlanner")
    tagline_default = (
        "Site generated from your prompt - update tagline in Project Input."
        if language == "en"
        else "Sajt skapad från din prompt - justera tagline i Project Input."
    )
    story_source = original_prompt.strip() or notes or tagline_default
    story = " ".join(story_source.split())[:600]
    if not story:
        story = tagline_default

    tone_words = list(brief.get("tone") or [])
    project_input: dict[str, Any] = {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": site_id,
        "scaffoldId": scaffold_id,
        "variantId": variant_id,
        "language": language,
        "company": {
            "name": _company_name_from_prompt(
                original_prompt, fallback="Ny sajt"
            ),
            "businessType": business_type,
            "tagline": (notes or tagline_default)[:140],
            "story": story,
        },
        "location": _placeholder_location(
            brief.get("locationHint"), language
        ),
        "services": services,
        "tone": {
            "primary": tone_words[0] if tone_words else "trustworthy",
            "secondary": tone_words[1:5],
            "avoid": [],
        },
        "trustSignals": [],
        "conversionGoals": list(brief.get("conversionGoals") or []),
        "requestedCapabilities": list(
            brief.get("requestedCapabilities") or []
        ),
        "contact": _placeholder_contact(language),
        "selectedDossiers": {
            "required": [],
            "recommended": [],
            "rationale": (
                "Auto-generated from prompt; operator may add Dossiers in "
                "the Project Input file before re-building."
            ),
        },
    }
    return project_input


def _validate_against_schema(payload: dict[str, Any]) -> None:
    """Schema-lock the generated Project Input before writing to disk.

    A drift between this generator and project-input.schema.json must
    fail loudly here, not later inside build_site.py - the operator
    otherwise sees a confusing builder KeyError instead of a clear
    schema-validation message pointing at the missing field.
    """
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return
    first = errors[0]
    location = first.json_path or "$"
    raise SystemExit(
        f"Generated Project Input failed schema check at {location}: "
        f"{first.message} (and {len(errors) - 1} more)"
    )


def write_project_input(
    project_input: dict[str, Any],
    meta: dict[str, Any],
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write project-input.json + meta.json to the scratch directory.

    Returns the (project_input_path, meta_path) tuple so callers can
    print absolute paths on stdout for downstream spawn-based wiring.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    site_id = project_input["siteId"]
    project_input_path = output_dir / f"{site_id}.project-input.json"
    meta_path = output_dir / f"{site_id}.meta.json"
    project_input_path.write_text(
        json.dumps(project_input, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return project_input_path, meta_path


def read_existing_meta(site_id: str, *, output_dir: Path) -> dict[str, Any]:
    """Read the sidecar meta that anchors follow-up prompt versions."""
    if not _SITE_ID_PATTERN.match(site_id):
        raise SystemExit(
            f"Follow-up siteId {site_id!r} does not match the lower-case "
            "alphanumeric/dash pattern required by Viewser."
        )

    meta_path = output_dir / f"{site_id}.meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Follow-up meta sidecar saknas: {meta_path}. Kör först en "
            "prompt-build som skapar data/prompt-inputs/<siteId>.meta.json."
        ) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Follow-up meta sidecar är inte giltig JSON: {meta_path}"
        ) from exc

    project_id = meta.get("projectId")
    version = meta.get("version")
    if not isinstance(project_id, str) or not project_id.strip():
        raise SystemExit(f"Follow-up meta saknar projectId: {meta_path}")
    if not isinstance(version, int) or version < 1:
        raise SystemExit(f"Follow-up meta har ogiltig version: {meta_path}")

    meta_site_id = meta.get("siteId")
    if isinstance(meta_site_id, str) and meta_site_id != site_id:
        raise SystemExit(
            f"Follow-up meta siteId mismatch: path={site_id!r}, meta={meta_site_id!r}"
        )
    return meta


def _mock_brief_artifact_after_failure(
    prompt: str,
    *,
    language: str,
    model: str,
    error: Exception,
) -> dict[str, Any]:
    """Return a schema-shaped mock Site Brief when brief extraction fails.

    ``extract_site_brief`` already catches the expected OpenAI failure
    path, but this helper covers bugs or unexpected exceptions in either
    ``extract_site_brief`` itself or ``site_brief_to_artifact``. The
    prompt-driven flow should degrade to a schema-valid placeholder
    Project Input, not crash the whole Viewser request.
    """
    message = f"{type(error).__name__}: {error}"
    return {
        "runId": "prompt-helper",
        "language": language,
        "rawPrompt": prompt,
        "businessTypeGuess": None,
        "pageCount": None,
        "tone": [],
        "targetAudience": [],
        "requestedCapabilities": [],
        "locationHint": None,
        "conversionGoals": [],
        "servicesMentioned": [],
        "contentDepth": None,
        "notesForPlanner": f"Mock brief after prompt helper failure: {message}",
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-llm-error",
        "briefError": message,
        "attemptedModel": model,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def generate(
    prompt: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    site_id: str | None = None,
    project_id: str | None = None,
    version: int = 1,
    meta_overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    """End-to-end: prompt -> Site Brief -> Project Input on disk.

    Returns (project_input, meta, project_input_path, meta_path). Used
    by both the CLI main() and the unit tests so the test path doesn't
    have to assemble argv-shaped input.
    """
    language = detect_language(prompt)
    try:
        model = resolve_brief_model()
    except Exception:  # noqa: BLE001
        # Mirror dev_generate.py's tolerance: a misconfigured llm-models
        # policy must not block the prompt-driven loop entirely.
        model = "gpt-5.4"

    try:
        brief_result = extract_site_brief(
            prompt, model=model, language_hint=language
        )
        brief_artifact = site_brief_to_artifact(
            brief_result,
            run_id="prompt-helper",
            model=model,
        )
    except Exception as exc:  # noqa: BLE001
        brief_artifact = _mock_brief_artifact_after_failure(
            prompt,
            language=language,
            model=model,
            error=exc,
        )

    final_site_id = site_id or slugify_site_id(prompt)
    if not _SITE_ID_PATTERN.match(final_site_id):
        raise SystemExit(
            f"Generated siteId {final_site_id!r} does not match the "
            "lower-case alphanumeric/dash pattern required by "
            "apps/viewser/lib/project-inputs.ts and build_site.py."
        )

    scaffold_id, variant_id = pick_scaffold(
        prompt, brief_artifact.get("businessTypeGuess")
    )
    project_input = site_brief_to_project_input(
        brief_artifact,
        site_id=final_site_id,
        scaffold_id=scaffold_id,
        variant_id=variant_id,
        original_prompt=prompt,
    )
    _validate_against_schema(project_input)

    now = datetime.now(UTC).isoformat(timespec="seconds")
    meta = {
        "projectId": project_id or uuid.uuid4().hex,
        "version": version,
        "siteId": final_site_id,
        "originalPrompt": prompt,
        "scaffoldId": scaffold_id,
        "variantId": variant_id,
        "briefSource": brief_artifact.get("briefSource"),
        "briefError": brief_artifact.get("briefError"),
        "modelUsed": brief_artifact.get("modelUsed"),
        "createdAt": now,
    }
    if meta_overrides:
        meta.update(meta_overrides)

    project_input_path, meta_path = write_project_input(
        project_input, meta, output_dir=output_dir
    )
    return project_input, meta, project_input_path, meta_path


def generate_followup(
    prompt: str,
    *,
    site_id: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    """Generate a new Project Input version from an existing meta sidecar."""
    existing_meta = read_existing_meta(site_id, output_dir=output_dir)
    previous_version = existing_meta["version"]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    return generate(
        prompt,
        output_dir=output_dir,
        site_id=site_id,
        project_id=existing_meta["projectId"],
        version=previous_version + 1,
        meta_overrides={
            "originalPrompt": existing_meta.get("originalPrompt", prompt),
            "latestPrompt": prompt,
            "previousVersion": previous_version,
            "createdAt": existing_meta.get("createdAt", now),
            "updatedAt": now,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a minimal Project Input from a free-form prompt."
    )
    parser.add_argument("prompt", help="The operator prompt to convert.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=(
            "Where to write <siteId>.project-input.json + <siteId>.meta.json. "
            f"Default: {DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)}"
        ),
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help=(
            "Override the auto-generated siteId. Must match "
            "[a-z0-9](?:[a-z0-9-]*[a-z0-9])? - same pattern that "
            "apps/viewser/lib/project-inputs.ts enforces."
        ),
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help=(
            "Reuse an existing projectId for follow-up flows. Defaults "
            "to a fresh uuid hex when omitted."
        ),
    )
    parser.add_argument(
        "--followup-site-id",
        default=None,
        help=(
            "Read data/prompt-inputs/<siteId>.meta.json, reuse its projectId "
            "and increment version for a follow-up prompt."
        ),
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    if args.followup_site_id:
        if args.site_id or args.project_id:
            raise SystemExit(
                "--followup-site-id cannot be combined with --site-id "
                "or --project-id."
            )
        project_input, meta, project_input_path, meta_path = generate_followup(
            args.prompt,
            output_dir=output_dir,
            site_id=args.followup_site_id,
        )
    else:
        project_input, meta, project_input_path, meta_path = generate(
            args.prompt,
            output_dir=output_dir,
            site_id=args.site_id,
            project_id=args.project_id,
        )

    # Output contract: emit the same key/value shape that build_site.py
    # uses for runId so apps/viewser/lib/build-runner.ts can parse it
    # with the same regex pattern.
    print(f"siteId: {project_input['siteId']}")
    print(f"projectId: {meta['projectId']}")
    print(f"dossierPath: {project_input_path}")
    print(f"metaPath: {meta_path}")
    print(f"version: {meta['version']}")
    print(f"briefSource: {meta['briefSource']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
