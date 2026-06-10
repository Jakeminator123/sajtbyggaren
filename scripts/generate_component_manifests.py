"""Generera component-manifest.json per Starter ur components.json + components/ui/.

Källan är varje Starters egna filer på disk (samma mönster som rules_sync.py:
deterministisk källa, genererad artefakt, synk-check i CI). Manifestet bor hos
Startern det beskriver: data/starters/<starterId>/component-manifest.json.

Inga LLM-anrop. Ren disk-scan: vi listar de vendorerade shadcn-komponenterna
direkt under components/ui/ (filstam + relativ sökväg) plus några fält ur
components.json (style, iconLibrary, aliases.ui). Starters som saknar
components/ui/ (commerce-base, saas-base) får en ärlig tom components-lista -
det är en tom inventering, inte ett saknat manifest.

Körs från repo-roten:
    python scripts/generate_component_manifests.py            # skriv/uppdatera alla
    python scripts/generate_component_manifests.py --check    # exit 1 vid drift

Synk-checken (--check) skrivs INTE; den jämför disk mot vad generatorn skulle
producera och faller med exit 1 om något manifest är out-of-sync. Drift fångas
även av tests/test_component_manifests.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTERS_DIR = REPO_ROOT / "data" / "starters"
REGISTRY_PATH = REPO_ROOT / "governance" / "policies" / "starter-registry.v1.json"
MANIFEST_FILENAME = "component-manifest.json"
GENERATED_BY = "scripts/generate_component_manifests.py"
# Relativ sökväg från data/starters/<id>/ tillbaka till governance/schemas/.
SCHEMA_REF = "../../../governance/schemas/component-manifest.schema.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def starter_ids() -> list[str]:
    """Starter-ID:n i registrets ordning (deterministisk)."""
    registry = _load_json(REGISTRY_PATH)
    return [starter["id"] for starter in registry.get("starters", [])]


def scan_ui_components(starter_dir: Path) -> list[dict]:
    """Lista *.tsx-filer direkt under components/ui/ som {name, path}, sorterat.

    Undermappar och *.test.tsx hoppas över. ``name`` = filstam, ``path`` =
    POSIX-relativ sökväg från Starter-roten.
    """
    ui_dir = starter_dir / "components" / "ui"
    out: list[dict] = []
    if ui_dir.is_dir():
        for child in sorted(ui_dir.iterdir()):
            if not child.is_file() or child.suffix != ".tsx":
                continue
            name = child.stem
            if name.endswith(".test"):
                continue
            out.append(
                {"name": name, "path": child.relative_to(starter_dir).as_posix()}
            )
    out.sort(key=lambda component: component["name"])
    return out


def build_manifest(starter_id: str) -> dict:
    """Bygg manifest-dicten för en Starter (insertion-order = filordning)."""
    starter_dir = STARTERS_DIR / starter_id
    components_json = starter_dir / "components.json"
    present = components_json.is_file()
    config: dict = _load_json(components_json) if present else {}

    manifest: dict = {
        "$schema": SCHEMA_REF,
        "starterId": starter_id,
        "generatedBy": GENERATED_BY,
        "componentsJsonPresent": present,
    }

    style = config.get("style")
    if isinstance(style, str) and style:
        manifest["style"] = style
    icon_library = config.get("iconLibrary")
    if isinstance(icon_library, str) and icon_library:
        manifest["iconLibrary"] = icon_library
    ui_alias = (config.get("aliases") or {}).get("ui")
    if isinstance(ui_alias, str) and ui_alias:
        manifest["uiAlias"] = ui_alias

    manifest["components"] = scan_ui_components(starter_dir)
    return manifest


def manifest_text(starter_id: str) -> str:
    """Deterministisk serialisering (indent=2, trailing newline)."""
    return json.dumps(build_manifest(starter_id), indent=2, ensure_ascii=False) + "\n"


def sync(check_only: bool = False) -> int:
    if not STARTERS_DIR.exists():
        print(f"Hittar inte {STARTERS_DIR}", file=sys.stderr)
        return 1

    ids = starter_ids()
    if not ids:
        print(f"Inga starters i {REGISTRY_PATH}", file=sys.stderr)
        return 1

    out_of_sync: list[str] = []
    written: list[str] = []
    missing_dirs: list[str] = []

    for starter_id in ids:
        starter_dir = STARTERS_DIR / starter_id
        if not starter_dir.is_dir():
            missing_dirs.append(starter_id)
            continue

        target_text = manifest_text(starter_id)
        manifest_path = starter_dir / MANIFEST_FILENAME
        existing = (
            manifest_path.read_text(encoding="utf-8")
            if manifest_path.exists()
            else None
        )

        if existing == target_text:
            continue

        rel = manifest_path.relative_to(REPO_ROOT).as_posix()
        if check_only:
            out_of_sync.append(rel)
            continue

        manifest_path.write_text(target_text, encoding="utf-8")
        written.append(rel)

    if missing_dirs:
        print(
            "Varning: starter-registry listar ID utan mapp under data/starters/: "
            + ", ".join(missing_dirs),
            file=sys.stderr,
        )

    if check_only:
        if out_of_sync:
            print("Komponent-manifest är out-of-sync:")
            for path in out_of_sync:
                print(f"  - {path}")
            print("Kör 'python scripts/generate_component_manifests.py' och committa.")
            return 1
        print("OK: alla komponent-manifest är i synk.")
        return 1 if missing_dirs else 0

    if written:
        print("Skrev om:")
        for path in written:
            print(f"  - {path}")
    else:
        print("Allt redan i synk.")
    return 1 if missing_dirs else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera component-manifest.json per Starter ur disk."
    )
    parser.add_argument("--check", action="store_true", help="Validera utan att skriva.")
    args = parser.parse_args()
    return sync(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
