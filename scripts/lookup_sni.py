"""CLI för att söka i SNI 2025-taxonomispegeln.

Stdlib-only verktyg som ger uppslagning + sök i
``data/taxonomies/sni/sni-2025.v1.json`` utan att blåsa upp Cursors
sökindex eller agentens kontext med 25 000 rader JSON. Filen är
exkluderad från Cursor-indexering (samma kategori som lockfiles, se
``.cursorindexingignore``); det här scriptet är det sanktionerade
sättet att slå upp koder och labels.

Subkommandon (alla stöder ``--json`` för agent-konsumtion):

- ``code <CODE>``       Slå upp en specifik kod, visa parent-chain.
- ``text <QUERY>``      Substring-sök i ``labelSv`` (case-insensitive).
- ``section <LETTER>``  Lista items under en avdelning (A-U).
                        Filtrera vidare med ``--level``.
- ``level <NAME>``      Lista items på en nivå.
                        Filtrera vidare med ``--section``.
- ``stats``             Antal items per nivå.

Exempel::

    python scripts/lookup_sni.py code 562
    python scripts/lookup_sni.py text "frisor" --limit 10
    python scripts/lookup_sni.py section I --level group
    python scripts/lookup_sni.py stats
    python scripts/lookup_sni.py code 5610 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY = REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.v1.json"

LEVEL_NAMES: tuple[str, ...] = ("section", "division", "group", "class", "subclass")
"""Hierarkin uppifrån och ner. Index = djup i trädet."""


def load_taxonomy(path: Path) -> dict[str, Any]:
    """Läs JSON-spegeln eller skriv felmeddelande och avsluta med kod 2."""
    if not path.exists():
        print(f"FEL: SNI-taxonomi saknas: {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def build_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Code-uppercase -> item, för O(1) uppslag i parent-chain."""
    return {str(item.get("code", "")).upper(): item for item in items}


def find_by_code(index: dict[str, dict[str, Any]], code: str) -> dict[str, Any] | None:
    return index.get(code.strip().upper())


def parent_chain(index: dict[str, dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    """Returnera de items vars koder ligger i item['path'] före item själv."""
    chain: list[dict[str, Any]] = []
    for code in item.get("path", [])[:-1]:
        match = index.get(str(code).upper())
        if match is not None:
            chain.append(match)
    return chain


def search_text(items: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    out: list[dict[str, Any]] = []
    for item in items:
        if needle in str(item.get("labelSv", "")).lower():
            out.append(item)
            if limit and len(out) >= limit:
                break
    return out


def filter_section(items: list[dict[str, Any]], section: str) -> list[dict[str, Any]]:
    needle = section.strip().upper()
    return [it for it in items if str(it.get("sectionCode", "")).upper() == needle]


def filter_level(items: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    return [it for it in items if it.get("level") == level]


def format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(inga träffar)\n"
    code_w = max(len("CODE"), max(len(str(r.get("code", ""))) for r in rows))
    level_w = max(len("LEVEL"), max(len(str(r.get("level", ""))) for r in rows))
    lines = [
        f"{'CODE':<{code_w}}  {'LEVEL':<{level_w}}  LABEL",
        "-" * (code_w + level_w + 32),
    ]
    for r in rows:
        lines.append(
            f"{str(r.get('code', '')):<{code_w}}  "
            f"{str(r.get('level', '')):<{level_w}}  "
            f"{r.get('labelSv', '')}"
        )
    return "\n".join(lines) + "\n"


def emit_list(rows: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_table(rows))


def emit_single(
    item: dict[str, Any] | None,
    chain: list[dict[str, Any]],
    *,
    as_json: bool,
) -> int:
    if item is None:
        if as_json:
            json.dump(None, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            sys.stdout.write("(ingen träff)\n")
        return 1
    if as_json:
        json.dump(
            {"item": item, "parents": chain},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0
    sys.stdout.write(f"{item.get('code')}  {item.get('level')}  {item.get('labelSv', '')}\n")
    sys.stdout.write(f"  parentCode:  {item.get('parentCode')}\n")
    sys.stdout.write(f"  sectionCode: {item.get('sectionCode')}\n")
    sys.stdout.write(f"  path:        {' > '.join(item.get('path', []))}\n")
    if chain:
        sys.stdout.write("\nParent chain (top down):\n")
        for parent in chain:
            try:
                depth = LEVEL_NAMES.index(str(parent.get("level", "")))
            except ValueError:
                depth = 0
            indent = "  " * depth
            sys.stdout.write(f"{indent}{parent.get('code')}  {parent.get('labelSv', '')}\n")
    return 0


def _common_parser() -> argparse.ArgumentParser:
    """Gemensamma flaggor som ska fungera både före och efter subkommando."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--file",
        default=str(DEFAULT_TAXONOMY),
        help=("Override JSON-källan (default: data/taxonomies/sni/sni-2025.v1.json)."),
    )
    common.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Skriv ut JSON istället för human-readable tabell.",
    )
    common.add_argument(
        "--limit",
        type=int,
        default=50,
        help=("Cappa antal träffar i text/section/level (0 = obegränsat). Default 50."),
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common_parser()
    parser = argparse.ArgumentParser(
        prog="lookup_sni",
        description=("Sök i SNI 2025-taxonomispegeln (data/taxonomies/sni/sni-2025.v1.json)."),
        parents=[common],
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_code = sub.add_parser("code", parents=[common], help="Slå upp en kod")
    p_code.add_argument("code", help="SNI-kod (bokstav eller siffror)")

    p_text = sub.add_parser("text", parents=[common], help="Substring-sök i labelSv")
    p_text.add_argument("query", help="Söktermen")

    p_section = sub.add_parser("section", parents=[common], help="Items under en avdelning")
    p_section.add_argument("section", help="Avdelningsbokstav (A-U)")
    p_section.add_argument(
        "--level",
        choices=LEVEL_NAMES,
        help="Filtrera på nivå",
    )

    p_level = sub.add_parser("level", parents=[common], help="Items på en nivå")
    p_level.add_argument("level", choices=LEVEL_NAMES)
    p_level.add_argument("--section", help="Filtrera på avdelning (A-U)")

    sub.add_parser("stats", parents=[common], help="Antal items per nivå")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    taxonomy = load_taxonomy(Path(args.file))
    items: list[dict[str, Any]] = taxonomy.get("items", [])
    index = build_index(items)

    if args.cmd == "code":
        match = find_by_code(index, args.code)
        chain = parent_chain(index, match) if match else []
        return emit_single(match, chain, as_json=args.as_json)

    if args.cmd == "text":
        hits = search_text(items, args.query, args.limit)
        emit_list(hits, as_json=args.as_json)
        return 0 if hits else 1

    if args.cmd == "section":
        hits = filter_section(items, args.section)
        if args.level:
            hits = [h for h in hits if h.get("level") == args.level]
        if args.limit:
            hits = hits[: args.limit]
        emit_list(hits, as_json=args.as_json)
        return 0 if hits else 1

    if args.cmd == "level":
        hits = filter_level(items, args.level)
        if args.section:
            section = args.section.strip().upper()
            hits = [h for h in hits if str(h.get("sectionCode", "")).upper() == section]
        if args.limit:
            hits = hits[: args.limit]
        emit_list(hits, as_json=args.as_json)
        return 0 if hits else 1

    if args.cmd == "stats":
        counts: dict[str, int] = {name: 0 for name in LEVEL_NAMES}
        for item in items:
            lvl = str(item.get("level", ""))
            if lvl in counts:
                counts[lvl] += 1
        if args.as_json:
            json.dump(
                {"total": sum(counts.values()), "perLevel": counts},
                sys.stdout,
                ensure_ascii=False,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            total = sum(counts.values())
            sys.stdout.write(f"Totalt: {total} items\n")
            for name in LEVEL_NAMES:
                level_label = taxonomy.get("levels", {}).get(name, name)
                sys.stdout.write(f"  {name:<10} ({level_label}): {counts[name]}\n")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
