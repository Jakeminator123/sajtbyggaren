"""Spegla governance/rules/*.md till .cursor/rules/*.mdc.

governance/rules/ är källan. .cursor/rules/ är spegeln. Redigera aldrig spegeln direkt.

Körs från repo-roten:
    python scripts/rules_sync.py            # skriv om alla speglar
    python scripts/rules_sync.py --check    # exit-kod 1 om speglar är out-of-sync

Filer som ligger i .cursor/rules/ men saknar källa i governance/rules/ varnas men tas inte bort
automatiskt - operatören måste avgöra om de är legacy som ska migreras eller raderas.

Relativa markdown-länkar skrivs om automatiskt så att de funkar från
``.cursor/rules/``-djupet:

* ``[X](../policies/y.json)`` -> ``[X](../../governance/policies/y.json)`` (samma för ``../schemas/`` och ``../decisions/``).
* ``[X](sibling.md)`` -> ``[X](sibling.mdc)`` eftersom speglarna ligger som ``.mdc`` bredvid varandra.
* Absoluta URL:er (``http(s)://``, ``mailto:``), ankare (``#...``) och repo-root-paths (``/...``) lämnas orörda.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "governance" / "rules"
MIRROR_DIR = REPO_ROOT / ".cursor" / "rules"

MIRROR_HEADER = (
    "<!-- AUTO-GENERATED FROM governance/rules/{name}.md. Do not edit directly. "
    "Run: python scripts/rules_sync.py -->\n"
)

_MD_LINK_RE = re.compile(r"(?<!\!)\[([^\]]*)\]\(([^)]+)\)")
"""Match standard inline markdown-länkar. Negativ lookbehind hoppar över bild-länkar (``![alt](src)``)."""


def _rewrite_link_target(target: str) -> str:
    """Skriv om en länk-target så att den funkar från ``.cursor/rules/<name>.mdc``.

    Hanterar:

    * Parent-relativa länkar mot syster-mappar under ``governance/`` (``../policies/...``,
      ``../schemas/...``, ``../decisions/...``).
    * Sibling-länkar till andra regler (``term-discipline.md`` -> ``term-discipline.mdc``).
    * Bevarar query-/anchor-suffix (``file.md#section``) intakt.

    Lämnar orörda: absoluta URL:er, ``mailto:``, repo-root-paths som börjar med ``/``,
    djupare relativa paths som redan har ``../../`` eller liknande prefix.
    """
    cleaned = target.strip()
    if not cleaned:
        return target
    if cleaned.startswith(("http://", "https://", "mailto:", "tel:", "#", "/")):
        return target

    # Separera path från ev. ?query/#anchor så vi bara skriver om path-delen.
    suffix = ""
    for separator in ("#", "?"):
        idx = cleaned.find(separator)
        if idx != -1:
            suffix = cleaned[idx:]
            cleaned = cleaned[:idx]
            break

    if cleaned.startswith("../../"):
        rewritten = cleaned
    elif cleaned.startswith("../"):
        rewritten = "../../governance/" + cleaned[len("../"):]
    elif "/" not in cleaned and cleaned.endswith(".md"):
        rewritten = cleaned[: -len(".md")] + ".mdc"
    else:
        rewritten = cleaned

    return rewritten + suffix


def rewrite_links_for_mirror(source_text: str) -> str:
    """Returnera ``source_text`` med alla länk-targets normaliserade för spegeln."""

    def _sub(match: re.Match[str]) -> str:
        label = match.group(1)
        target = match.group(2)
        return f"[{label}]({_rewrite_link_target(target)})"

    return _MD_LINK_RE.sub(_sub, source_text)


def expected_mirror_text(name: str, source_text: str) -> str:
    return MIRROR_HEADER.format(name=name) + rewrite_links_for_mirror(source_text)


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
