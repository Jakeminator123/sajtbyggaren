"""Hall begreppskartans fakta-block i synk med vad som faktiskt finns pa main.

Raknar scaffolds/dossiers pa disk och laser kvalitetsmalen fran
governance/policies/page-quality-traits.v1.json, och skriver sedan om
REPO_FACTS-blocket i docs/canvases/begreppskarta-sajtbyggaren.canvas.tsx.

Anvands av Steward (manuellt eller via steward-auto-bump-workflowet):
  python scripts/update_canvas_facts.py          # uppdatera blocket
  python scripts/update_canvas_facts.py --check  # exit 1 vid drift, skriver inget
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANVAS_PATH = REPO_ROOT / "docs" / "canvases" / "begreppskarta-sajtbyggaren.canvas.tsx"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
SCAFFOLD_CONTRACT = REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"
QUALITY_TRAITS = REPO_ROOT / "governance" / "policies" / "page-quality-traits.v1.json"

BLOCK_START = "// AUTOGEN_REPO_FACTS_START"
BLOCK_END = "// AUTOGEN_REPO_FACTS_END"
BLOCK_RE = re.compile(
    re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END),
    flags=re.DOTALL,
)


def count_scaffolds_on_disk() -> int:
    if not SCAFFOLDS_DIR.is_dir():
        return 0
    return sum(1 for p in SCAFFOLDS_DIR.iterdir() if (p / "scaffold.json").is_file())


def count_scaffolds_in_registry() -> int:
    contract = json.loads(SCAFFOLD_CONTRACT.read_text(encoding="utf-8"))
    registry = contract.get("primaryScaffoldRegistry", [])
    return len(registry)


def count_dossiers(class_name: str) -> int:
    class_dir = DOSSIERS_DIR / class_name
    if not class_dir.is_dir():
        return 0
    return sum(1 for p in class_dir.iterdir() if (p / "manifest.json").is_file())


def quality_target() -> dict[str, float]:
    traits = json.loads(QUALITY_TRAITS.read_text(encoding="utf-8"))
    target = traits.get("qualityTarget", {})
    return {
        "targetScore": float(target.get("targetScore", 0.0)),
        "gateScore": float(target.get("gateScore", 0.0)),
        "blockBelow": float(target.get("blockBelow", 0.0)),
    }


def format_number(value: float) -> str:
    """Skriv heltal utan decimal men behall en decimal for malvarden (9.0)."""

    if value == int(value):
        return f"{value:.1f}"
    return f"{value}"


def render_block(generated_at: str) -> str:
    quality = quality_target()
    lines = [
        BLOCK_START + " -- skrivs av scripts/update_canvas_facts.py, redigera inte for hand",
        "const REPO_FACTS = {",
        f'  generatedAt: "{generated_at}",',
        f"  scaffoldsOnDisk: {count_scaffolds_on_disk()},",
        f"  scaffoldsInRegistry: {count_scaffolds_in_registry()},",
        f"  softDossiers: {count_dossiers('soft')},",
        f"  hardDossiers: {count_dossiers('hard')},",
        f"  qualityTargetScore: {format_number(quality['targetScore'])},",
        f"  qualityGateScore: {format_number(quality['gateScore'])},",
        f"  qualityBlockBelow: {format_number(quality['blockBelow'])},",
        "} as const;",
        BLOCK_END,
    ]
    return "\n".join(lines)


def extract_generated_at(text: str) -> str | None:
    match = re.search(r'generatedAt: "(\d{4}-\d{2}-\d{2})"', text)
    return match.group(1) if match else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Skriv inget; exit 1 om fakta-blocket inte matchar repots faktiska innehall.",
    )
    args = parser.parse_args(argv)

    if not CANVAS_PATH.is_file():
        print(f"Hittar inte {CANVAS_PATH} - har begreppskartan flyttats?")
        return 1

    text = CANVAS_PATH.read_text(encoding="utf-8")
    if not BLOCK_RE.search(text):
        print(f"Hittar inte fakta-blocket ({BLOCK_START} ... {BLOCK_END}) i {CANVAS_PATH.name}.")
        return 1

    if args.check:
        # Behall befintligt datum vid jamforelse sa att enbart faktadrift flaggas.
        existing_date = extract_generated_at(text) or "0000-00-00"
        expected = render_block(existing_date)
        current = BLOCK_RE.search(text).group(0)  # type: ignore[union-attr]
        if current != expected:
            print("Fakta-blocket i begreppskartan matchar inte repot. Forvantat innehall:")
            print(expected)
            print("Kor: python scripts/update_canvas_facts.py")
            return 1
        print("Fakta-blocket i begreppskartan ar i synk med repot.")
        return 0

    # Skriv bara om sjalva fakta-vardena driftat - datumet ensamt ska inte
    # generera nya commits fran steward-auto-bump efter varje merge.
    existing_date = extract_generated_at(text) or "0000-00-00"
    current_block = BLOCK_RE.search(text).group(0)  # type: ignore[union-attr]
    if current_block == render_block(existing_date):
        print("Fakta-blocket ar redan uppdaterat - inget skrevs.")
        return 0

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    new_text = BLOCK_RE.sub(lambda _m: render_block(today), text, count=1)
    CANVAS_PATH.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"Fakta-blocket uppdaterat i {CANVAS_PATH.relative_to(REPO_ROOT)} (per {today}).")
    print("Glom inte: python scripts/sync_canvases.py for att spegla till Cursor-mappen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
