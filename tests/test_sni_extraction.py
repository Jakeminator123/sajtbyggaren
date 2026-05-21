"""Tests for ``scripts/extract_sni_2025.py`` and committed SNI reference JSON.

SNI 2025-källan är operatör-lokal (committas inte). Den committade
JSON-spegeln ``data/taxonomies/sni/sni-2025.v1.json`` är canonical
referens; testerna här låser att referensen håller den deterministiska
shape som extractorn skriver och att ``--check`` upptäcker drift.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import extract_sni_2025  # noqa: E402

SNI_JSON_PATH = REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.v1.json"


def _load_reference() -> dict:
    return json.loads(SNI_JSON_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Committed reference
# ---------------------------------------------------------------------------


def test_reference_json_envelope_locks_canonical_shape() -> None:
    payload = _load_reference()

    assert payload["taxonomyId"] == "sni-2025"
    assert payload["version"] == 1
    assert payload["sourceFile"] == "data/taxonomies/sni/sni-2025.source.xlsx"
    assert payload["levels"] == {
        "section": "Avdelning",
        "division": "Huvudgrupp",
        "group": "Grupp",
        "class": "Undergrupp",
        "subclass": "Detaljgrupp",
    }
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) >= 1500, (
        "SNI 2025 har 1500+ poster över avdelning/huvudgrupp/grupp/undergrupp/"
        "detaljgrupp; en kraftig minskning är drift."
    )


def test_reference_has_entries_at_all_five_levels() -> None:
    payload = _load_reference()
    levels = {item["level"] for item in payload["items"]}

    assert {"section", "division", "group", "class", "subclass"}.issubset(levels)


def test_reference_includes_known_codes_with_expected_labels() -> None:
    payload = _load_reference()
    by_code = {item["code"]: item for item in payload["items"]}

    assert by_code["56"]["level"] == "division"
    assert by_code["56"]["labelSv"].startswith("Restaurang")

    assert by_code["43"]["level"] == "division"
    assert by_code["43"]["labelSv"].startswith("Specialiserad")

    assert by_code["62"]["level"] == "division"
    assert "datakonsult" in by_code["62"]["labelSv"].lower()

    assert by_code["691"]["level"] == "group"
    assert by_code["691"]["labelSv"].startswith("Juridisk")

    assert by_code["962"]["level"] == "group"
    assert "skönhet" in by_code["962"]["labelSv"].lower()


def test_reference_items_are_sorted_by_level_then_code() -> None:
    payload = _load_reference()
    items = payload["items"]
    order = extract_sni_2025.LEVEL_ORDER

    pairs = [(order[item["level"]], item["code"]) for item in items]
    assert pairs == sorted(pairs)


def test_reference_uses_utf8_without_bom_and_ends_with_newline() -> None:
    raw = SNI_JSON_PATH.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf"), "JSON får inte ha UTF-8 BOM"
    assert raw.endswith(b"\n")


# ---------------------------------------------------------------------------
# Determinism + CLI
# ---------------------------------------------------------------------------


def _build_fake_xlsx(path: Path) -> None:
    """Bygg en miniatyr-OOXML-fil med fem SNI-blad för testet."""
    shared_strings = [
        "SNI2025Avdelning",
        "Aktivitetsart",
        "Huvudgrupp (Tvåsiffer)",
        "A",
        "Jordbruk, skogsbruk och fiske",
        "01-03",
        "SNI2025Huvudgrupp",
        "01",
        "Jordbruk och jakt samt stödverksamhet i anslutning härtill",
        "SNI2025Grupp (Officiell kodstruktur)",
        "SNI2025Grupp",
        "SNI2025Huvudgrupp",
        "01.1",
        "011",
        "Odling av ett- och tvååriga växter",
        "SNI2025Undergrupp (Officiell kodstruktur)",
        "SNI2025Undergrupp",
        "SNI2025Grupp",
        "01.11",
        "0111",
        "Odling av spannmål (utom ris), baljväxter och oljeväxter",
        "SNI2025Detaljgrupp (Officiell kodstruktur)",
        "SNI2025Detaljgrupp",
        "SNI2025Undergrupp",
        "01.110",
        "01110",
    ]

    def _sheet_rows(rows: list[list[str]]) -> str:
        body = ""
        for r_idx, row in enumerate(rows, start=1):
            cells = "".join(
                f'<c r="{chr(ord("A") + c_idx)}{r_idx}" t="s"><v>{shared_strings.index(value)}</v></c>'
                for c_idx, value in enumerate(row)
            )
            body += f'<row r="{r_idx}">{cells}</row>'
        return (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{body}</sheetData></worksheet>"
        )

    sheet1 = _sheet_rows(
        [
            ["SNI2025Avdelning", "Aktivitetsart", "Huvudgrupp (Tvåsiffer)"],
            ["A", "Jordbruk, skogsbruk och fiske", "01-03"],
        ]
    )
    sheet2 = _sheet_rows(
        [
            ["SNI2025Huvudgrupp", "Aktivitetsart", "SNI2025Avdelning"],
            [
                "01",
                "Jordbruk och jakt samt stödverksamhet i anslutning härtill",
                "A",
            ],
        ]
    )
    sheet3 = _sheet_rows(
        [
            [
                "SNI2025Grupp (Officiell kodstruktur)",
                "SNI2025Grupp",
                "Aktivitetsart",
                "SNI2025Huvudgrupp",
            ],
            [
                "01.1",
                "011",
                "Odling av ett- och tvååriga växter",
                "01",
            ],
        ]
    )
    sheet4 = _sheet_rows(
        [
            [
                "SNI2025Undergrupp (Officiell kodstruktur)",
                "SNI2025Undergrupp",
                "Aktivitetsart",
                "SNI2025Grupp",
            ],
            [
                "01.11",
                "0111",
                "Odling av spannmål (utom ris), baljväxter och oljeväxter",
                "011",
            ],
        ]
    )
    sheet5 = _sheet_rows(
        [
            [
                "SNI2025Detaljgrupp (Officiell kodstruktur)",
                "SNI2025Detaljgrupp",
                "Aktivitetsart",
                "SNI2025Undergrupp",
            ],
            [
                "01.110",
                "01110",
                "Odling av spannmål (utom ris), baljväxter och oljeväxter",
                "0111",
            ],
        ]
    )

    shared_xml = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        + "".join(f"<si><t xml:space=\"preserve\">{value}</t></si>" for value in shared_strings)
        + "</sst>"
    )

    workbook_xml = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Avdelning (Bokstav)" sheetId="1" r:id="rId1"/>'
        '<sheet name="Huvudgrupp (Tvåsiffer)" sheetId="2" r:id="rId2"/>'
        '<sheet name="Grupp (Tresiffer)" sheetId="3" r:id="rId3"/>'
        '<sheet name="Undergrupp (Fyrsiffer)" sheetId="4" r:id="rId4"/>'
        '<sheet name="Detaljgrupp (Femsiffer)" sheetId="5" r:id="rId5"/>'
        "</sheets></workbook>"
    )
    workbook_rels = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="sheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="sheet" Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" Type="sheet" Target="worksheets/sheet3.xml"/>'
        '<Relationship Id="rId4" Type="sheet" Target="worksheets/sheet4.xml"/>'
        '<Relationship Id="rId5" Type="sheet" Target="worksheets/sheet5.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        "</Types>"
    )

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/sharedStrings.xml", shared_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1)
        zf.writestr("xl/worksheets/sheet2.xml", sheet2)
        zf.writestr("xl/worksheets/sheet3.xml", sheet3)
        zf.writestr("xl/worksheets/sheet4.xml", sheet4)
        zf.writestr("xl/worksheets/sheet5.xml", sheet5)


def test_extract_workbook_produces_deterministic_items_across_levels(tmp_path: Path) -> None:
    source = tmp_path / "sni-2025.source.xlsx"
    _build_fake_xlsx(source)

    items = extract_sni_2025.extract_sni_workbook(source)

    by_level: dict[str, list[dict]] = {}
    for item in items:
        by_level.setdefault(item["level"], []).append(item)

    assert set(by_level) == {"section", "division", "group", "class", "subclass"}
    assert by_level["section"][0]["code"] == "A"
    assert by_level["division"][0]["code"] == "01"
    assert by_level["division"][0]["parentCode"] == "A"
    assert by_level["group"][0]["code"] == "011"
    assert by_level["group"][0]["parentCode"] == "01"
    assert by_level["class"][0]["code"] == "0111"
    assert by_level["class"][0]["parentCode"] == "011"
    assert by_level["subclass"][0]["code"] == "01110"
    assert by_level["subclass"][0]["parentCode"] == "0111"

    # Path should be the full chain from section down to entry.
    assert by_level["subclass"][0]["path"] == ["A", "01", "011", "0111", "01110"]


def test_extract_runs_are_byte_stable(tmp_path: Path) -> None:
    source = tmp_path / "sni-2025.source.xlsx"
    _build_fake_xlsx(source)

    payload_a = extract_sni_2025.build_payload(
        extract_sni_2025.extract_sni_workbook(source),
        source_relative="data/taxonomies/sni/sni-2025.source.xlsx",
    )
    payload_b = extract_sni_2025.build_payload(
        extract_sni_2025.extract_sni_workbook(source),
        source_relative="data/taxonomies/sni/sni-2025.source.xlsx",
    )

    assert extract_sni_2025.serialize_payload(payload_a) == (
        extract_sni_2025.serialize_payload(payload_b)
    )


def test_extract_missing_source_raises_helpful_error(tmp_path: Path) -> None:
    with pytest.raises(extract_sni_2025.SniExtractionError):
        extract_sni_2025.extract_sni_workbook(tmp_path / "missing.xlsx")


def test_main_check_skips_when_source_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_out = tmp_path / "sni-2025.v1.json"
    fake_out.write_text("{}\n", encoding="utf-8")

    rc = extract_sni_2025.main(
        [
            "--source",
            str(tmp_path / "no.xlsx"),
            "--out",
            str(fake_out),
            "--check",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert "SKIP" in captured.out


def test_main_check_detects_drift(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "sni-2025.source.xlsx"
    _build_fake_xlsx(source)
    out = tmp_path / "sni-2025.v1.json"

    rc_write = extract_sni_2025.main(["--source", str(source), "--out", str(out)])
    assert rc_write == 0

    out.write_text("{}\n", encoding="utf-8")
    rc_check = extract_sni_2025.main(
        ["--source", str(source), "--out", str(out), "--check"]
    )

    assert rc_check == 1
    captured = capsys.readouterr()
    assert "DRIFT" in captured.err


def test_main_check_passes_after_fresh_extraction(tmp_path: Path) -> None:
    source = tmp_path / "sni-2025.source.xlsx"
    _build_fake_xlsx(source)
    out = tmp_path / "sni-2025.v1.json"

    assert extract_sni_2025.main(["--source", str(source), "--out", str(out)]) == 0
    assert extract_sni_2025.main(
        ["--source", str(source), "--out", str(out), "--check"]
    ) == 0


def test_normalize_extracts_clean_string_values_only(tmp_path: Path) -> None:
    """Sanity-check att raden alltid har strängvärden, inga XML-objekt."""
    source = tmp_path / "sni-2025.source.xlsx"
    _build_fake_xlsx(source)

    items = extract_sni_2025.extract_sni_workbook(source)

    for item in items:
        for key in ("code", "level", "labelSv"):
            assert isinstance(item[key], str)
        assert item["parentCode"] is None or isinstance(item["parentCode"], str)
        assert isinstance(item["path"], list)
        assert all(isinstance(part, str) for part in item["path"])


def test_root_xml_can_round_trip_via_extract_helper() -> None:
    """Snabb sanity-check att Python stdlib XML kan läsa committad referens om vi gick tillbaka via OOXML."""
    # Inte en faktisk roundtrip; bara att vi kan parsa SNI labels via ET utan crash.
    payload = _load_reference()
    items = payload["items"]
    text = json.dumps(items[:5], ensure_ascii=False)
    ET.fromstring(f"<root>{text.replace('<', '&lt;').replace('>', '&gt;')}</root>")
