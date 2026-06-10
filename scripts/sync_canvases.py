"""Spegla delade canvases mellan docs/canvases/ och Cursors hanterade mapp.

Cursor renderar bara canvas-filer fran ~/.cursor/projects/<slug>/canvases/.
Repo-kopian i docs/canvases/ ar den kanoniska kallan (delas via git). Det har
skriptet kopierar repo -> Cursor som standard; --pull kopierar tillbaka
lokala andringar for filer som redan finns i repot.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "docs" / "canvases"
CANVAS_SUFFIX = ".canvas.tsx"


def derive_workspace_slug(repo_root: Path) -> str:
    """Harled Cursors workspace-slug fran repots absoluta sokvag.

    Exempel: C:/Users/jakem/Desktop/sajtbyggaren -> c-Users-jakem-Desktop-sajtbyggaren.
    """

    raw = str(repo_root)
    slug = re.sub(r"[:\\/]+", "-", raw).strip("-")
    if len(slug) >= 2 and raw[1:2] == ":":
        slug = slug[0].lower() + slug[1:]
    return slug


def find_managed_canvases_dir(repo_root: Path) -> Path | None:
    """Hitta ~/.cursor/projects/<slug>/canvases for det har repot."""

    projects = Path.home() / ".cursor" / "projects"
    if not projects.is_dir():
        return None

    slug = derive_workspace_slug(repo_root)
    exact = projects / slug
    if exact.is_dir():
        return exact / "canvases"

    lowered = slug.lower()
    for candidate in projects.iterdir():
        if candidate.is_dir() and candidate.name.lower() == lowered:
            return candidate / "canvases"
    return None


def list_canvases(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.name.endswith(CANVAS_SUFFIX))


def copy_if_changed(source: Path, target: Path) -> bool:
    if target.exists() and target.read_bytes() == source.read_bytes():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def push(target_dir: Path, *, check: bool) -> int:
    """Spegla repo -> Cursor. Med check=True skrivs inget; drift ger exit 1."""

    sources = list_canvases(SOURCE_DIR)
    if not sources:
        print(f"Inga canvas-filer i {SOURCE_DIR} - inget att spegla.")
        return 0

    drifted: list[str] = []
    for source in sources:
        target = target_dir / source.name
        if check:
            if not target.exists() or target.read_bytes() != source.read_bytes():
                drifted.append(source.name)
        elif copy_if_changed(source, target):
            print(f"  uppdaterad: {target}")
            drifted.append(source.name)

    if check:
        if drifted:
            print("Canvas-spegeln ligger efter repo-kopian for:")
            for name in drifted:
                print(f"  - {name}")
            print("Kor: python scripts/sync_canvases.py")
            return 1
        print(f"Canvas-spegeln ar i synk ({len(sources)} filer).")
        return 0

    if not drifted:
        print(f"Redan i synk ({len(sources)} filer, inget kopierat).")
    else:
        print(f"Klart: {len(drifted)} av {len(sources)} filer speglade till {target_dir}.")
    return 0


def pull(target_dir: Path) -> int:
    """Dra tillbaka lokala canvas-andringar till repot (bara kanda filer)."""

    known = {p.name for p in list_canvases(SOURCE_DIR)}
    if not known:
        print(f"Inga canvas-filer i {SOURCE_DIR} - --pull hamtar bara kanda filer.")
        return 0

    pulled = 0
    for candidate in list_canvases(target_dir):
        if candidate.name not in known:
            continue
        if copy_if_changed(candidate, SOURCE_DIR / candidate.name):
            print(f"  hamtad: {candidate.name}")
            pulled += 1

    if pulled:
        print(f"Klart: {pulled} filer hamtade till {SOURCE_DIR}. Granska diffen och committa.")
    else:
        print("Inga lokala canvas-andringar att hamta.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Cursors canvas-mapp (~/.cursor/projects/<slug>/canvases). Harleds annars automatiskt.",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Kopiera fran Cursor-mappen till repot i stallet (bara filer som redan finns i repot).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Skriv inget; exit 1 om Cursor-spegeln skiljer sig fran repo-kopian.",
    )
    args = parser.parse_args(argv)

    target_dir = args.target or find_managed_canvases_dir(REPO_ROOT)
    if target_dir is None:
        print(
            "Hittade ingen Cursor-projektmapp for det har repot under ~/.cursor/projects/.\n"
            "Peka ut den manuellt: python scripts/sync_canvases.py --target <sokvag>"
        )
        return 1

    if args.pull:
        return pull(target_dir)
    return push(target_dir, check=args.check)


if __name__ == "__main__":
    sys.exit(main())
