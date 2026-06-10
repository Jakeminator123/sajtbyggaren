"""Validera alla policies under governance/policies/ mot deras JSON Schema.

Körs från repo-roten:
    python scripts/governance_validate.py

Exit-kod 0 = allt valideras. Exit-kod 1 = minst ett fel.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print(
        "Saknar jsonschema. Installera med 'pip install -r requirements.txt' eller 'pip install jsonschema'.",
        file=sys.stderr,
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
POLICIES_DIR = REPO_ROOT / "governance" / "policies"
SCHEMAS_DIR = REPO_ROOT / "governance" / "schemas"
STARTERS_DIR = REPO_ROOT / "data" / "starters"
COMPONENT_MANIFEST_FILENAME = "component-manifest.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def schema_path_for(policy: dict, policy_file: Path) -> Path:
    schema_ref = policy.get("$schema")
    if not schema_ref:
        raise ValueError(f"Saknar $schema i {policy_file}")
    return (policy_file.parent / schema_ref).resolve()


def validate_policy(policy_file: Path) -> list[str]:
    errors: list[str] = []
    try:
        policy = load_json(policy_file)
    except json.JSONDecodeError as exc:
        return [f"{policy_file.name}: ogiltig JSON: {exc}"]

    try:
        schema_file = schema_path_for(policy, policy_file)
    except ValueError as exc:
        return [str(exc)]

    if not schema_file.exists():
        return [f"{policy_file.name}: schema saknas på {schema_file}"]

    schema = load_json(schema_file)
    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(policy), key=lambda e: list(e.path)):
        location = "/".join(str(p) for p in err.absolute_path) or "<rot>"
        errors.append(f"{policy_file.name} -> {location}: {err.message}")
    return errors


# Fält där förbjudna termer faktiskt SKA stå (eftersom själva poängen är att lista dem).
# Cross-checken ignorerar värden under dessa nycklar.
ANTI_PATTERN_KEYS = {
    "forbiddenTerms",
    "forbiddenLegacyTierNames",
    "forbiddenInScaffoldFiles",
    "forbiddenInDossierFiles",
    "forbiddenPatterns",
    "aliasesForbidden",
    "globallyForbidden",
    "mustNotDo",
    "avoid",
    "limitations",
    "negativeSignals",
}


def collect_text_outside_anti_patterns(node: object) -> list[str]:
    """Plocka ut alla strängvärden i en JSON-struktur utom de under ANTI_PATTERN_KEYS."""
    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ANTI_PATTERN_KEYS:
                continue
            out.extend(collect_text_outside_anti_patterns(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(collect_text_outside_anti_patterns(item))
    elif isinstance(node, str):
        out.append(node)
    return out


def cross_check_naming_dictionary(policies: dict[str, dict]) -> list[str]:
    """Säkerställ att inga policies använder ord som står i globallyForbidden,
    utöver i fält som uttryckligen listar förbjudna termer.
    """
    naming = policies.get("naming-dictionary.v1.json")
    if not naming:
        return ["naming-dictionary.v1.json saknas - kan inte cross-checka"]
    forbidden = [w for w in naming.get("globallyForbidden", []) if w]
    if not forbidden:
        return []

    errors: list[str] = []
    for name, policy in policies.items():
        if name == "naming-dictionary.v1.json":
            continue
        texts = collect_text_outside_anti_patterns(policy)
        for word in forbidden:
            for text in texts:
                if word in text:
                    errors.append(
                        f"{name}: aktiv användning av globallyForbidden-term '{word}' "
                        f"i fältet med text: \"{text[:80]}...\""
                    )
                    break
    return errors


def cross_check_capability_components(policies: dict[str, dict]) -> list[str]:
    """Säkerställ att varje capability-map components-namn finns i minst en
    enabled Starters component-manifest.json (Component Catalog lager 2).

    En mappning till en komponent som saknas i alla enabled Starters manifest
    är ett gate-fel, inte en tyst fallback (ADR 0040). Per-Starter-upplösning
    (vilken Starter som bär komponenten för ett visst bygge) är ett lager-3-
    problem; här krävs bara att komponenten är vendorerad någonstans.
    """
    capability_map = policies.get("capability-map.v1.json")
    if not capability_map:
        # capability-map saknas eller validerade inte mot sitt schema - då har
        # schema-steget redan rapporterat felet.
        return []

    registry = policies.get("starter-registry.v1.json")
    if not registry:
        return ["starter-registry.v1.json saknas - kan inte korskontrollera komponenter"]

    enabled_ids = [
        starter["id"]
        for starter in registry.get("starters", [])
        if starter.get("enabled", True)
    ]

    available: set[str] = set()
    errors: list[str] = []
    for starter_id in enabled_ids:
        manifest_path = STARTERS_DIR / starter_id / COMPONENT_MANIFEST_FILENAME
        if not manifest_path.exists():
            errors.append(
                f"data/starters/{starter_id}/{COMPONENT_MANIFEST_FILENAME} saknas - "
                "kör 'python scripts/generate_component_manifests.py' och committa"
            )
            continue
        try:
            manifest = load_json(manifest_path)
        except json.JSONDecodeError as exc:
            errors.append(f"{manifest_path.name} ({starter_id}): ogiltig JSON: {exc}")
            continue
        for component in manifest.get("components", []):
            name = component.get("name")
            if name:
                available.add(name)

    for slug, entry in capability_map.get("capabilities", {}).items():
        for component_name in entry.get("components", []) or []:
            if component_name not in available:
                errors.append(
                    f"capability-map.v1.json -> capabilities/{slug}/components: "
                    f"komponenten '{component_name}' saknas i alla enabled Starters "
                    "component-manifest.json (vendorera komponenten eller ta bort "
                    "mappningen)"
                )

    return errors


def main() -> int:
    if not POLICIES_DIR.exists():
        print(f"Hittar inte {POLICIES_DIR}", file=sys.stderr)
        return 1

    policies: dict[str, dict] = {}
    all_errors: list[str] = []

    for policy_file in sorted(POLICIES_DIR.glob("*.json")):
        errs = validate_policy(policy_file)
        if errs:
            all_errors.extend(errs)
            continue
        policies[policy_file.name] = load_json(policy_file)

    cross_errs = cross_check_naming_dictionary(policies)
    all_errors.extend(cross_errs)

    component_errs = cross_check_capability_components(policies)
    all_errors.extend(component_errs)

    if all_errors:
        print("Governance-validering misslyckades:\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print(f"OK: {len(policies)} policies validerade mot sina schemas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
