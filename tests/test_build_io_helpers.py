"""Focused tests for the builder IO helper extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.build import io_helpers

pytestmark = pytest.mark.tooling


def test_load_json_reads_utf8_object(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps({"name": "Måleri", "enabled": True}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert io_helpers.load_json(source) == {"name": "Måleri", "enabled": True}


def test_write_creates_parent_dirs_and_preserves_text(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "output.txt"

    io_helpers.write(target, "rad ett\nrad två\n")

    assert target.read_text(encoding="utf-8") == "rad ett\nrad två\n"


def test_write_json_pretty_prints_utf8_with_trailing_newline(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "payload.json"

    io_helpers.write_json(target, {"label": "Grön", "items": [1, 2]})

    assert target.read_text(encoding="utf-8") == (
        '{\n  "label": "Grön",\n  "items": [\n    1,\n    2\n  ]\n}\n'
    )
    assert io_helpers.load_json(target) == {"label": "Grön", "items": [1, 2]}


def test_write_blocks_real_env_files_but_allows_example(tmp_path: Path) -> None:
    with pytest.raises(AssertionError):
        io_helpers.write(tmp_path / ".env", "SECRET=oops\n")
    with pytest.raises(AssertionError):
        io_helpers.write(tmp_path / ".env.local", "SECRET=oops\n")

    safe = tmp_path / ".env.example"
    io_helpers.write(safe, "# placeholder only\n")
    assert safe.read_text(encoding="utf-8") == "# placeholder only\n"


def test_build_site_re_exports_moved_helpers_by_identity() -> None:
    import scripts.build_site as build_site

    assert build_site._FORBIDDEN_ENV_PATTERN is io_helpers._FORBIDDEN_ENV_PATTERN
    assert build_site._ALLOWED_ENV_NAMES is io_helpers._ALLOWED_ENV_NAMES
    assert build_site.load_json is io_helpers.load_json
    assert build_site.assert_not_env_secret is io_helpers.assert_not_env_secret
    assert build_site.write is io_helpers.write
    assert build_site.write_json is io_helpers.write_json


def test_resolve_generated_dir_explicit_override_stays_build_site_facade(
    tmp_path: Path,
) -> None:
    import scripts.build_site as build_site

    assert build_site.resolve_generated_dir(tmp_path) == tmp_path.resolve()
