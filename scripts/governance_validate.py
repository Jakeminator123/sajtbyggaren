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

    if all_errors:
        print("Governance-validering misslyckades:\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print(f"OK: {len(policies)} policies validerade mot sina schemas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
