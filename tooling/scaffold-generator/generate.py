"""Generate a complete Sajtbyggaren scaffold from a single spec file.

Reads ``tooling/scaffold-generator/spec/<scaffoldId>.json`` and writes
the six required scaffold files plus every variant under
``packages/generation/orchestration/scaffolds/<scaffoldId>/``. Each
generated file is validated against the matching schema in
``governance/schemas/`` before it is written, so an invalid spec fails
fast rather than landing broken JSON on disk.

The output shape mirrors the canonical local-service-business scaffold
exactly (sections.json keyed by route id, routes.json with
defaultRoutes + optionalRoutes arrays, etc.). The generator's only
purpose is to lift authoring from "six hand-written JSON files per
scaffold" to "one declarative spec per scaffold".

Usage from repo root with .venv activated::

    python tooling/scaffold-generator/generate.py restaurant-hospitality
    python tooling/scaffold-generator/generate.py --check clinic-healthcare
    python tooling/scaffold-generator/generate.py --list

Exit codes:
    0 = success (or --check passed)
    1 = spec missing, invalid JSON, or schema validation failed
    2 = jsonschema not installed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print(
        "Saknar jsonschema. Installera med 'pip install -r requirements.txt' "
        "eller 'pip install jsonschema'.",
        file=sys.stderr,
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TOOL_DIR = Path(__file__).resolve().parent
SPEC_DIR = TOOL_DIR / "spec"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
SCHEMAS_DIR = REPO_ROOT / "governance" / "schemas"

SCAFFOLD_SCHEMA_RELATIVE = "../../../../../governance/schemas/scaffold.schema.json"
VARIANT_SCHEMA_RELATIVE = "../../../../../../governance/schemas/variant.schema.json"


# ---------- Spec loading ----------------------------------------------------


def load_spec(spec_id: str) -> dict[str, Any]:
    spec_path = SPEC_DIR / f"{spec_id}.json"
    if not spec_path.exists():
        available = sorted(p.stem for p in SPEC_DIR.glob("*.json") if not p.stem.startswith("_"))
        raise SystemExit(
            f"Spec hittades inte: {spec_path}\n"
            f"Tillgängliga specs: {', '.join(available) or '(inga)'}"
        )
    try:
        with spec_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Spec {spec_path.name} är ogiltig JSON: {exc}") from exc


REQUIRED_SPEC_KEYS = (
    "id",
    "label",
    "description",
    "buildIntent",
    "primaryJobs",
    "defaultPageCount",
    "routes",
    "sectionsPerRoute",
    "qualityContract",
    "compatibleDossiers",
    "selectionProfile",
    "variants",
)


def assert_spec_shape(spec: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_SPEC_KEYS if key not in spec]
    if missing:
        raise SystemExit(
            f"Spec saknar obligatoriska fält: {', '.join(missing)}. "
            f"Se tooling/scaffold-generator/spec/_TEMPLATE.json för exempel."
        )
    if not isinstance(spec["variants"], list) or not spec["variants"]:
        raise SystemExit("Spec.variants måste vara en icke-tom lista.")
    if not isinstance(spec["routes"], list) or not spec["routes"]:
        raise SystemExit("Spec.routes måste vara en icke-tom lista.")


# ---------- File builders ---------------------------------------------------


def build_scaffold_json(spec: dict[str, Any]) -> dict[str, Any]:
    """Match the canonical scaffold.json shape (additionalProperties: false)."""
    return {
        "$schema": SCAFFOLD_SCHEMA_RELATIVE,
        "id": spec["id"],
        "version": spec.get("scaffoldVersion", "1.0.0"),
        "label": spec["label"],
        "description": spec["description"],
        "buildIntent": list(spec["buildIntent"]),
        "primaryJobs": list(spec["primaryJobs"]),
        "defaultPageCount": int(spec["defaultPageCount"]),
        "supportsSinglePage": bool(spec.get("supportsSinglePage", False)),
        "supportsMultiPage": bool(spec.get("supportsMultiPage", True)),
        "supportsAppFeatures": bool(spec.get("supportsAppFeatures", False)),
    }


def build_routes_json(spec: dict[str, Any]) -> dict[str, Any]:
    """Match the canonical routes.json shape from local-service-business.

    Top-level: ``{defaultRoutes: [...], optionalRoutes: [...]}``.
    Default entries: ``{id, path, required, purpose}``.
    Optional entries: ``{id, path, when}``.
    """
    default_routes: list[dict[str, Any]] = []
    optional_routes: list[dict[str, Any]] = []
    for route in spec["routes"]:
        if not isinstance(route, dict):
            raise SystemExit(
                "Spec.routes-entry måste vara ett objekt med id, path, label, required."
            )
        if route.get("optional"):
            if not route.get("when"):
                raise SystemExit(
                    f"Optional route {route.get('id')!r} måste ha fältet 'when' "
                    "(natural-language villkor för aktivering)."
                )
            optional_routes.append(
                {
                    "id": route["id"],
                    "path": route["path"],
                    "when": route["when"],
                }
            )
        else:
            if not route.get("purpose"):
                raise SystemExit(
                    f"Default route {route.get('id')!r} måste ha fältet 'purpose' "
                    "(en mening om varför sidan finns)."
                )
            default_routes.append(
                {
                    "id": route["id"],
                    "path": route["path"],
                    "required": bool(route.get("required", False)),
                    "purpose": route["purpose"],
                }
            )
    result: dict[str, Any] = {"defaultRoutes": default_routes}
    if optional_routes:
        result["optionalRoutes"] = optional_routes
    return result


def build_sections_json(spec: dict[str, Any]) -> dict[str, Any]:
    """Match the canonical sections.json shape: top-level keys = route IDs.

    Each route: ``{requiredSections, optionalSections, sectionOrderRules}``.
    No ``$schema`` or wrapper object — locked by sections.schema.json
    (additionalProperties: false, patternProperties on route IDs).
    """
    out: dict[str, Any] = {}
    for route_id, payload in spec["sectionsPerRoute"].items():
        if not isinstance(payload, dict):
            raise SystemExit(
                f"sectionsPerRoute[{route_id}] måste vara ett objekt med "
                "requiredSections, optionalSections, sectionOrderRules."
            )
        for key in ("requiredSections", "optionalSections", "sectionOrderRules"):
            if key not in payload:
                raise SystemExit(
                    f"sectionsPerRoute[{route_id}] saknar fältet {key!r}."
                )
        out[route_id] = {
            "requiredSections": list(payload["requiredSections"]),
            "optionalSections": list(payload["optionalSections"]),
            "sectionOrderRules": list(payload["sectionOrderRules"]),
        }
    return out


def build_quality_contract_json(spec: dict[str, Any]) -> dict[str, Any]:
    qc = spec["qualityContract"]
    for key in ("scorecardWeights", "mustPass", "avoid"):
        if key not in qc:
            raise SystemExit(f"qualityContract saknar obligatoriskt fält {key!r}.")
    return {
        "scorecardWeights": dict(qc["scorecardWeights"]),
        "mustPass": list(qc["mustPass"]),
        "avoid": list(qc["avoid"]),
    }


def build_compatible_dossiers_json(spec: dict[str, Any]) -> dict[str, Any]:
    cd = spec["compatibleDossiers"]
    if "required" not in cd or not isinstance(cd["required"], list):
        raise SystemExit("compatibleDossiers.required måste vara en lista (kan vara tom).")
    out: dict[str, Any] = {}
    if cd.get("comment"):
        out["_comment"] = cd["comment"]
    out["required"] = list(cd["required"])
    out["recommended"] = list(cd.get("recommended", []))
    out["conditional"] = list(cd.get("conditional", []))
    out["disallowedByDefault"] = list(cd.get("disallowedByDefault", []))
    return out


def build_selection_profile_json(spec: dict[str, Any]) -> dict[str, Any]:
    sp = spec["selectionProfile"]
    required = (
        "embeddingText",
        "semanticSignals",
        "negativeSignals",
        "llmClassificationHints",
        "minConfidence",
        "requiresTieBreakWhenWithin",
    )
    missing = [k for k in required if k not in sp]
    if missing:
        raise SystemExit(f"selectionProfile saknar fält: {', '.join(missing)}")
    return {
        "id": spec["id"],
        "embeddingText": sp["embeddingText"],
        "semanticSignals": list(sp["semanticSignals"]),
        "negativeSignals": list(sp["negativeSignals"]),
        "llmClassificationHints": list(sp["llmClassificationHints"]),
        "minConfidence": float(sp["minConfidence"]),
        "requiresTieBreakWhenWithin": float(sp["requiresTieBreakWhenWithin"]),
    }


def build_variant_json(variant: dict[str, Any]) -> dict[str, Any]:
    for key in ("id", "label", "description", "tokens", "tone"):
        if key not in variant:
            raise SystemExit(
                f"Variant {variant.get('id', '?')!r} saknar obligatoriskt fält {key!r}."
            )
    return {
        "$schema": VARIANT_SCHEMA_RELATIVE,
        "id": variant["id"],
        "enabled": bool(variant.get("enabled", True)),
        "label": variant["label"],
        "description": variant["description"],
        "tokens": variant["tokens"],
        "tone": variant["tone"],
    }


# ---------- Schema validation ----------------------------------------------


def schema_validator_for(schema_name: str) -> Draft202012Validator | None:
    """Return a validator for the named schema, or None if not present.

    Several scaffold files (quality-contract.json, compatible-dossiers.json,
    selection-profile.json, routes.json) are governed by scaffold-contract.v1
    rather than per-file schemas, so a missing per-file schema is not a hard
    error — it just means we skip that specific validation step and rely on
    the runtime's own contract enforcement.
    """
    schema_path = SCHEMAS_DIR / schema_name
    if not schema_path.exists():
        return None
    with schema_path.open("r", encoding="utf-8") as fh:
        return Draft202012Validator(json.load(fh))


def validate(doc: dict[str, Any], schema_name: str, doc_label: str) -> list[str]:
    validator = schema_validator_for(schema_name)
    if validator is None:
        return []
    errors: list[str] = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"  - {doc_label} ({schema_name}) at {location}: {err.message}")
    return errors


# ---------- Writer ---------------------------------------------------------


def _write(path: Path, doc: dict[str, Any], *, dry_run: bool) -> None:
    serialised = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print(f"  [dry-run] would write {path.relative_to(REPO_ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(serialised)
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


def generate(spec_id: str, *, dry_run: bool) -> int:
    spec = load_spec(spec_id)
    assert_spec_shape(spec)
    if spec["id"] != spec_id:
        raise SystemExit(
            f"Spec.id ({spec['id']!r}) matchar inte filnamn ({spec_id!r}). "
            "Använd samma id i båda."
        )

    print(f"Generating scaffold {spec_id!r} ({'dry-run' if dry_run else 'writing'})")

    scaffold_dir = SCAFFOLDS_DIR / spec_id

    scaffold_doc = build_scaffold_json(spec)
    routes_doc = build_routes_json(spec)
    sections_doc = build_sections_json(spec)
    quality_doc = build_quality_contract_json(spec)
    compatible_doc = build_compatible_dossiers_json(spec)
    selection_doc = build_selection_profile_json(spec)
    variant_docs = [(variant["id"], build_variant_json(variant)) for variant in spec["variants"]]

    errors: list[str] = []
    errors.extend(validate(scaffold_doc, "scaffold.schema.json", "scaffold.json"))
    errors.extend(validate(sections_doc, "sections.schema.json", "sections.json"))
    for variant_id, variant_doc in variant_docs:
        errors.extend(validate(variant_doc, "variant.schema.json", f"variants/{variant_id}.json"))

    if errors:
        print(f"Schema validation failed ({len(errors)} issue(s)):", file=sys.stderr)
        for issue in errors:
            print(issue, file=sys.stderr)
        return 1

    _write(scaffold_dir / "scaffold.json", scaffold_doc, dry_run=dry_run)
    _write(scaffold_dir / "routes.json", routes_doc, dry_run=dry_run)
    _write(scaffold_dir / "sections.json", sections_doc, dry_run=dry_run)
    _write(scaffold_dir / "quality-contract.json", quality_doc, dry_run=dry_run)
    _write(scaffold_dir / "compatible-dossiers.json", compatible_doc, dry_run=dry_run)
    _write(scaffold_dir / "selection-profile.json", selection_doc, dry_run=dry_run)
    for variant_id, variant_doc in variant_docs:
        _write(scaffold_dir / "variants" / f"{variant_id}.json", variant_doc, dry_run=dry_run)

    total = 6 + len(variant_docs)
    print(
        f"\nDone. {total} fil(er) "
        + ("validerade (dry-run)." if dry_run else "skrivna och validerade.")
    )
    return 0


# ---------- CLI ------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Sajtbyggaren scaffold from a spec file."
    )
    parser.add_argument(
        "spec_id",
        nargs="?",
        help="Spec id (matches tooling/scaffold-generator/spec/<id>.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate spec and build files in memory, do not write.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available spec ids and exit.",
    )
    args = parser.parse_args(argv)

    if args.list:
        specs = sorted(p.stem for p in SPEC_DIR.glob("*.json") if not p.stem.startswith("_"))
        if not specs:
            print("(inga specs registrerade)")
            return 0
        print("Tillgängliga specs:")
        for spec_id in specs:
            print(f"  - {spec_id}")
        return 0

    if not args.spec_id:
        parser.error("spec_id krävs (eller använd --list).")
        return 2

    return generate(args.spec_id, dry_run=args.check)


if __name__ == "__main__":
    sys.exit(main())
