"""Spegla governance/rules/*.md till .cursor/rules/*.mdc.

governance/rules/ är källan. .cursor/rules/ är spegeln. Redigera aldrig spegeln direkt.

Körs från repo-roten:
    python scripts/rules_sync.py            # skriv om alla speglar
    python scripts/rules_sync.py --check    # exit-kod 1 om speglar är out-of-sync

Filer som ligger i .cursor/rules/ men saknar källa i governance/rules/ varnas men tas inte bort
automatiskt - operatören måste avgöra om de är legacy som ska migreras eller raderas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "governance" / "rules"
MIRROR_DIR = REPO_ROOT / ".cursor" / "rules"

MIRROR_HEADER = (
    "<!-- AUTO-GENERATED FROM governance/rules/{name}.md. Do not edit directly. "
    "Run: python scripts/rules_sync.py -->\n"
)


def expected_mirror_text(name: str, source_text: str) -> str:
    return MIRROR_HEADER.format(name=name) + source_text


def sync(check_only: bool = False) -> int:
    if not SOURCE_DIR.exists():
        print(f"Hittar inte {SOURCE_DIR}", file=sys.stderr)
        return 1

    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    sources = sorted(SOURCE_DIR.glob("*.md"))
    if not sources:
        print(f"Inga *.md-filer i {SOURCE_DIR}")
        return 0

    out_of_sync: list[str] = []
    written: list[str] = []

    for source_path in sources:
        name = source_path.stem
        mirror_path = MIRROR_DIR / f"{name}.mdc"
        source_text = source_path.read_text(encoding="utf-8")
        target_text = expected_mirror_text(name, source_text)

        existing = mirror_path.read_text(encoding="utf-8") if mirror_path.exists() else None

        if existing == target_text:
            continue

        if check_only:
            out_of_sync.append(str(mirror_path.relative_to(REPO_ROOT)))
            continue

        mirror_path.write_text(target_text, encoding="utf-8")
        written.append(str(mirror_path.relative_to(REPO_ROOT)))

    extras = []
    expected_names = {p.stem + ".mdc" for p in sources}
    for mirror_file in MIRROR_DIR.glob("*.mdc"):
        if mirror_file.name not in expected_names:
            extras.append(mirror_file.name)

    if check_only:
        if out_of_sync:
            print("Speglar är out-of-sync:")
            for path in out_of_sync:
                print(f"  - {path}")
            return 1
        print("OK: alla speglar är i synk.")
        if extras:
            print(
                "Varning: filer i .cursor/rules/ som saknar källa i governance/rules/: "
                + ", ".join(extras)
            )
        return 0

    if written:
        print("Skrev om:")
        for path in written:
            print(f"  - {path}")
    else:
        print("Allt redan i synk.")
    if extras:
        print(
            "Varning: filer i .cursor/rules/ utan källa i governance/rules/: "
            + ", ".join(extras)
            + " (avgör manuellt om de ska migreras eller raderas)."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Spegla governance/rules/ till .cursor/rules/.")
    parser.add_argument("--check", action="store_true", help="Validera utan att skriva.")
    args = parser.parse_args()
    return sync(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
