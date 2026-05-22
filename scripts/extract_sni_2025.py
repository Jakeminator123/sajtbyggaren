"""Extract SNI 2025 hierarchy from the official Excel workbook to JSON.

SNI (Svensk näringsgrensindelning) 2025 är Statistikmyndigheten SCB:s
canonical bransch-taxonomi. Operatören drar ner originalfilen (Excel) och
det här scriptet skriver en deterministisk JSON-spegel som lever i repo:t
under ``data/taxonomies/sni/sni-2025.v1.json``. Excel-filen committas
inte; JSON:en är canonical referens.

Scriptet använder bara Python stdlib (``zipfile`` + ``xml.etree``) så
``openpyxl`` är inte en runtime-dependency.

CLI:
    python scripts/extract_sni_2025.py \
        --source data/taxonomies/sni/sni-2025.source.xlsx \
        --out data/taxonomies/sni/sni-2025.v1.json

    python scripts/extract_sni_2025.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.source.xlsx"
DEFAULT_OUT = REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.v1.json"

XL_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
PKG_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
REL_ID_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

LEVEL_ORDER: dict[str, int] = {
    "section": 0,
    "division": 1,
    "group": 2,
    "class": 3,
    "subclass": 4,
}
"""Stable sort order between SNI-nivåer. Lower = mer generell."""


class SniExtractionError(RuntimeError):
    """Raised when the SNI workbook cannot be parsed."""


def _column_index(cell_ref: str) -> int:
    """Convert ``A1``/``AB12`` style cell ref to 1-based column index."""
    letters = ""
    for ch in cell_ref:
        if ch.isalpha():
            letters += ch
        else:
            break
    out = 0
    for ch in letters:
        out = out * 26 + ord(ch.upper()) - 64
    return out


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in root.findall("a:si", XL_NS):
        text = "".join((node.text or "") for node in si.findall(".//a:t", XL_NS))
        out.append(text)
    return out


def _read_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("pr:Relationship", PKG_NS)
    }
    sheets: list[tuple[str, str]] = []
    for sheet in wb.findall("a:sheets/a:sheet", XL_NS):
        name = sheet.attrib.get("name", "")
        rel_id = sheet.attrib.get(REL_ID_ATTR)
        if not rel_id or rel_id not in rel_map:
            continue
        target = rel_map[rel_id].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheets.append((name, target))
    return sheets


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    v_elem = cell.find("a:v", XL_NS)
    if v_elem is None:
        inline = cell.find("a:is/a:t", XL_NS)
        return (inline.text or "") if inline is not None else ""
    raw = v_elem.text or ""
    if cell.attrib.get("t") == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def _iter_sheet_rows(
    archive: zipfile.ZipFile, target: str, shared: list[str]
) -> list[dict[int, str]]:
    root = ET.fromstring(archive.read(target))
    rows: list[dict[int, str]] = []
    for row in root.findall("a:sheetData/a:row", XL_NS):
        values: dict[int, str] = {}
        for cell in row.findall("a:c", XL_NS):
            ref = cell.attrib.get("r", "A1")
            col = _column_index(ref)
            values[col] = _cell_value(cell, shared)
        rows.append(values)
    return rows


def _clean(text: str) -> str:
    return (text or "").strip()


def extract_sni_workbook(source: Path) -> list[dict[str, Any]]:
    """Parse the SNI 2025 workbook and return a deterministic ``items`` list.

    Each entry has ``code`` (digit-only or section letter), ``level``,
    ``labelSv``, ``parentCode`` and ``sectionCode``. ``path`` is the chain
    of codes from section down to the entry itself; resolvers can use it
    to render breadcrumbs without re-running the workbook parse.
    """
    if not source.exists():
        raise SniExtractionError(
            f"SNI-källa saknas: {source}. Lägg in originalfilen från SCB innan körning."
        )

    with zipfile.ZipFile(source) as archive:
        shared = _read_shared_strings(archive)
        sheets = _read_sheet_targets(archive)
        if len(sheets) < 5:
            raise SniExtractionError(
                f"Förväntade minst fem blad i SNI-källan, hittade {len(sheets)}."
            )

        items: list[dict[str, Any]] = []

        # Sheet 1: Avdelning (section, bokstav)
        for row in _iter_sheet_rows(archive, sheets[0][1], shared)[1:]:
            code = _clean(row.get(1, ""))
            label = _clean(row.get(2, ""))
            if not code or not label:
                continue
            items.append(
                {
                    "code": code,
                    "level": "section",
                    "labelSv": label,
                    "parentCode": None,
                    "sectionCode": code,
                    "path": [code],
                }
            )

        # Sheet 2: Huvudgrupp (division, 2 siffror)
        for row in _iter_sheet_rows(archive, sheets[1][1], shared)[1:]:
            code = _clean(row.get(1, ""))
            label = _clean(row.get(2, ""))
            parent = _clean(row.get(3, ""))
            if not code or not label:
                continue
            items.append(
                {
                    "code": code,
                    "level": "division",
                    "labelSv": label,
                    "parentCode": parent or None,
                    "sectionCode": parent or None,
                    "path": [c for c in (parent, code) if c],
                }
            )

        section_by_division = {
            item["code"]: item["sectionCode"]
            for item in items
            if item["level"] == "division"
        }

        # Sheet 3: Grupp (group, 3 siffror). Kolumn 2 är digit-only (t.ex. "011"),
        # kolumn 1 är prickad ("01.1"). Vi använder digit-only som canonical kod.
        for row in _iter_sheet_rows(archive, sheets[2][1], shared)[1:]:
            code = _clean(row.get(2, ""))
            label = _clean(row.get(3, ""))
            parent = _clean(row.get(4, ""))
            if not code or not label:
                continue
            section = section_by_division.get(parent)
            chain = [section, parent, code] if section else [parent, code]
            items.append(
                {
                    "code": code,
                    "level": "group",
                    "labelSv": label,
                    "parentCode": parent or None,
                    "sectionCode": section,
                    "path": [c for c in chain if c],
                }
            )

        division_by_group = {
            item["code"]: item["parentCode"]
            for item in items
            if item["level"] == "group"
        }
        section_by_group = {
            item["code"]: item["sectionCode"]
            for item in items
            if item["level"] == "group"
        }

        # Sheet 4: Undergrupp (class, 4 siffror).
        for row in _iter_sheet_rows(archive, sheets[3][1], shared)[1:]:
            code = _clean(row.get(2, ""))
            label = _clean(row.get(3, ""))
            parent = _clean(row.get(4, ""))
            if not code or not label:
                continue
            division = division_by_group.get(parent)
            section = section_by_group.get(parent)
            chain = [section, division, parent, code]
            items.append(
                {
                    "code": code,
                    "level": "class",
                    "labelSv": label,
                    "parentCode": parent or None,
                    "sectionCode": section,
                    "path": [c for c in chain if c],
                }
            )

        division_by_class = {
            item["code"]: division_by_group.get(item["parentCode"] or "")
            for item in items
            if item["level"] == "class"
        }
        section_by_class = {
            item["code"]: item["sectionCode"]
            for item in items
            if item["level"] == "class"
        }
        group_by_class = {
            item["code"]: item["parentCode"]
            for item in items
            if item["level"] == "class"
        }

        # Sheet 5: Detaljgrupp (subclass, 5 siffror).
        for row in _iter_sheet_rows(archive, sheets[4][1], shared)[1:]:
            code = _clean(row.get(2, ""))
            label = _clean(row.get(3, ""))
            parent = _clean(row.get(4, ""))
            if not code or not label:
                continue
            group = group_by_class.get(parent)
            division = division_by_class.get(parent)
            section = section_by_class.get(parent)
            chain = [section, division, group, parent, code]
            items.append(
                {
                    "code": code,
                    "level": "subclass",
                    "labelSv": label,
                    "parentCode": parent or None,
                    "sectionCode": section,
                    "path": [c for c in chain if c],
                }
            )

    return sorted(items, key=lambda entry: (LEVEL_ORDER[entry["level"]], entry["code"]))


def build_payload(
    items: list[dict[str, Any]],
    *,
    source_relative: str,
) -> dict[str, Any]:
    """Wrap ``items`` in the canonical envelope written to JSON."""
    return {
        "taxonomyId": "sni-2025",
        "version": 1,
        "sourceFile": source_relative,
        "descriptionSv": (
            "Extraktion av SCB:s SNI 2025-hierarki. JSON:en är committad "
            "referens; Excel-källan lever utanför repo:t."
        ),
        "levels": {
            "section": "Avdelning",
            "division": "Huvudgrupp",
            "group": "Grupp",
            "class": "Undergrupp",
            "subclass": "Detaljgrupp",
        },
        "items": items,
    }


def serialize_payload(payload: dict[str, Any]) -> str:
    """Return deterministic JSON text (UTF-8, ingen BOM, en trailing newline)."""
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _relative_source_path(source: Path) -> str:
    """Returnera POSIX-stilen för ``source`` relativt repo-roten när möjligt.

    När scriptet körs i tester med en tmp-path utanför repo:t (Windows
    ``C:\\Windows\\Temp\\...``) failar ``Path.relative_to`` med
    ``ValueError``; helpern returnerar då canonical-namnet på den source-
    fil operatören har inne i repo:t istället så ``sourceFile`` i JSON
    stannar stabilt.
    """
    try:
        return source.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return "data/taxonomies/sni/sni-2025.source.xlsx"


def _resolve_source(source: Path) -> Path:
    if source.exists():
        return source
    # Tillåt fallback till den nakna ``sni-2025.xlsx``-filen som operatören
    # initialt drog ner — agenten döper om / städar bort vid commit.
    sibling = source.with_name("sni-2025.xlsx")
    if sibling.exists():
        return sibling
    raise SniExtractionError(
        f"Hittar varken {source} eller fallback {sibling}. "
        "Lägg in SCB:s SNI 2025-källfil innan körning."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract SNI 2025 hierarchy to deterministic JSON.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Excel source file (default: data/taxonomies/sni/sni-2025.source.xlsx).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output JSON path (default: data/taxonomies/sni/sni-2025.v1.json).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Verify that committed JSON matches a fresh extraction. Exits 0 "
            "with a SKIP note when the source file is absent (since the "
            "Excel is intentionally not committed)."
        ),
    )
    args = parser.parse_args(argv)

    try:
        source = _resolve_source(args.source)
    except SniExtractionError as exc:
        if args.check:
            print(f"SKIP: {exc}")
            return 0
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        items = extract_sni_workbook(source)
    except SniExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = build_payload(items, source_relative=_relative_source_path(source))
    text = serialize_payload(payload)

    out_path: Path = args.out
    if args.check:
        if not out_path.exists():
            print(
                f"ERROR: --check angiven men {out_path} saknas. Kör extraktorn först.",
                file=sys.stderr,
            )
            return 1
        on_disk = out_path.read_text(encoding="utf-8")
        if on_disk != text:
            print(
                f"DRIFT: {out_path} skiljer sig från färsk extraktion. "
                "Kör scriptet utan --check för att uppdatera JSON:en.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {out_path} matchar färsk extraktion ({len(items)} SNI-poster).")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"OK: skrev {out_path} ({len(items)} SNI-poster).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
