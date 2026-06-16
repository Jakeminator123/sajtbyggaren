"""Unit tests for the Generative Component V1 emit/materialise step (ADR 0061).

Locks the deterministic write-path contract of
``packages.generation.codegen.followup_emit.materialize_generative_components``:

- it writes ONLY under ``components/generated/<id>.tsx`` (the generated-components
  dir convention);
- it splices an import + a usage element into the route's ``page.tsx``;
- it is idempotent (re-running never double-inserts);
- it FAILS CLOSED on any path/policy violation (never package.json, never a path
  outside the build dir, never an unsafe id / unknown recipe).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.codegen.followup_emit import (  # noqa: E402
    GenerativeEmitError,
    _assert_safe_write_path,
    materialize_generative_components,
)

pytestmark = pytest.mark.tooling

_PAGE_TSX = (
    'import { Sparkles } from "lucide-react";\n'
    "\n"
    "export default function Home() {\n"
    "  return (\n"
    '    <main className="flex flex-1 flex-col">\n'
    '      <section className="hero">Hej</section>\n'
    "    </main>\n"
    "  );\n"
    "}\n"
)

_SPEC = {
    "recipe": "image-placeholder-grid",
    "count": 6,
    "routeId": "home",
    "id": "image-placeholder-grid",
}

_CTA_SPEC = {
    "recipe": "cta-contact-block",
    "count": 1,
    "routeId": "home",
    "id": "cta-contact-block",
}
_CTA_COMPONENT = "Generated" + "Cta" + "Contact" + "Block"


def _make_build(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal build dir with a home page.tsx to splice into."""
    target = tmp_path / "build"
    (target / "app").mkdir(parents=True)
    (target / "components").mkdir()
    page = target / "app" / "page.tsx"
    page.write_text(_PAGE_TSX, encoding="utf-8")
    return target, page


def test_writes_only_under_generated_components_dir(tmp_path: Path):
    target, _page = _make_build(tmp_path)
    written = materialize_generative_components(target, [_SPEC])

    assert written == ["components/generated/image-placeholder-grid.tsx"]
    component = target / "components" / "generated" / "image-placeholder-grid.tsx"
    assert component.exists()
    source = component.read_text(encoding="utf-8")
    # Deterministic recipe template: the component name + the requested tile count.
    assert "GeneratedImagePlaceholderGrid" in source
    assert "Array.from({ length: 6 }" in source
    # No external/new dependency import is emitted (V1 guard).
    assert "import" not in source.split("export")[0] or "from" not in source.split("export")[0]


def test_splices_import_and_usage_into_page(tmp_path: Path):
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [_SPEC])

    text = page.read_text(encoding="utf-8")
    assert (
        'import { GeneratedImagePlaceholderGrid } from '
        '"@/components/generated/image-placeholder-grid";' in text
    )
    assert "<GeneratedImagePlaceholderGrid />" in text
    # The usage lands before the closing </main>.
    assert text.index("<GeneratedImagePlaceholderGrid />") < text.index("</main>")


def test_cta_contact_block_writes_deterministic_component(tmp_path: Path):
    target, _page = _make_build(tmp_path)
    written = materialize_generative_components(target, [_CTA_SPEC])

    assert written == ["components/generated/cta-contact-block.tsx"]
    component = target / "components" / "generated" / "cta-contact-block.tsx"
    assert component.exists()
    source = component.read_text(encoding="utf-8")
    assert _CTA_COMPONENT in source
    assert "Redo att boka eller be om offert?" in source
    assert "Kontakta oss" in source
    assert "mailto:" not in source
    assert "tel:" not in source
    assert "@" not in source
    assert "+34" not in source
    assert "/kontakt" not in source


def test_cta_contact_block_splices_import_and_usage_into_page(tmp_path: Path):
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [_CTA_SPEC])

    text = page.read_text(encoding="utf-8")
    assert (
        f"import {{ {_CTA_COMPONENT} }} from "
        '"@/components/generated/cta-contact-block";' in text
    )
    assert f"<{_CTA_COMPONENT} />" in text
    assert text.index(f"<{_CTA_COMPONENT} />") < text.index("</main>")


_PAGE_TSX_USE_CLIENT = (
    '"use client";\n'
    "\n"
    'import { Sparkles } from "lucide-react";\n'
    "\n"
    "export default function Home() {\n"
    "  return (\n"
    '    <main className="flex flex-1 flex-col">\n'
    '      <section className="hero">Hej</section>\n'
    "    </main>\n"
    "  );\n"
    "}\n"
)


def test_import_inserted_after_leading_use_client_directive(tmp_path: Path):
    """Bug fix (matris #2): a page starting with a 'use client' directive must keep
    that directive as the FIRST statement - the generated import goes AFTER it,
    never before (prepending an import before 'use client' breaks the Next build)."""
    target = tmp_path / "build"
    (target / "app").mkdir(parents=True)
    (target / "components").mkdir()
    page = target / "app" / "page.tsx"
    page.write_text(_PAGE_TSX_USE_CLIENT, encoding="utf-8")

    materialize_generative_components(target, [_SPEC])
    text = page.read_text(encoding="utf-8")

    # The "use client" directive is still the very first statement.
    assert text.lstrip().startswith('"use client";')
    # The generated import is present, but AFTER the directive (not before it).
    assert text.index('"use client";') < text.index("@/components/generated/")
    assert "<GeneratedImagePlaceholderGrid />" in text


def test_top_position_lands_after_opening_main_before_hero(tmp_path: Path):
    """Placement reuse: a 'top' position ('högst upp') splices the usage right
    after the opening <main> and BEFORE the hero <section>, instead of the default
    before-</main>."""
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [{**_SPEC, "position": "top"}])

    text = page.read_text(encoding="utf-8")
    assert "<GeneratedImagePlaceholderGrid />" in text
    usage = text.index("<GeneratedImagePlaceholderGrid />")
    opening_main = text.index("<main")
    hero = text.index('<section className="hero"')
    closing_main = text.index("</main>")
    # After the opening <main>, before the hero, and well before the closing tag.
    assert opening_main < usage < hero < closing_main


def test_cta_top_position_lands_after_opening_main_before_hero(tmp_path: Path):
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [{**_CTA_SPEC, "position": "top"}])

    text = page.read_text(encoding="utf-8")
    assert f"<{_CTA_COMPONENT} />" in text
    usage = text.index(f"<{_CTA_COMPONENT} />")
    opening_main = text.index("<main")
    hero = text.index('<section className="hero"')
    closing_main = text.index("</main>")
    assert opening_main < usage < hero < closing_main


def test_bottom_position_lands_before_closing_main(tmp_path: Path):
    """A 'bottom' position keeps the default before-</main> placement (the usage
    lands after the hero, just before the closing tag)."""
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [{**_SPEC, "position": "bottom"}])

    text = page.read_text(encoding="utf-8")
    hero = text.index('<section className="hero"')
    usage = text.index("<GeneratedImagePlaceholderGrid />")
    closing_main = text.index("</main>")
    assert hero < usage < closing_main


def test_absent_position_is_byte_identical_to_bottom_default(tmp_path: Path):
    """DEFAULT behaviour is unchanged: a spec with no 'position' produces the exact
    same page bytes as before this slice (before-</main> placement)."""
    target_a, page_a = _make_build(tmp_path / "a")
    materialize_generative_components(target_a, [_SPEC])
    target_b, page_b = _make_build(tmp_path / "b")
    materialize_generative_components(target_b, [{**_SPEC, "position": "bottom"}])
    assert page_a.read_text(encoding="utf-8") == page_b.read_text(encoding="utf-8")


def test_top_position_is_idempotent(tmp_path: Path):
    """A 'top' re-run on an already-spliced page never double-inserts."""
    target, page = _make_build(tmp_path)
    spec = {**_SPEC, "position": "top"}
    materialize_generative_components(target, [spec])
    first = page.read_text(encoding="utf-8")
    materialize_generative_components(target, [spec])
    second = page.read_text(encoding="utf-8")
    assert second.count("<GeneratedImagePlaceholderGrid />") == 1
    assert second.count("@/components/generated/image-placeholder-grid") == 1
    assert first == second


_PAGE_TSX_NO_OPENING_MAIN = (
    'import { Sparkles } from "lucide-react";\n'
    "\n"
    "export default function Home() {\n"
    "  return (\n"
    "    <Shell>\n"
    '      <section className="hero">Hej</section>\n'
    "    </main>\n"
    "  );\n"
    "}\n"
)


def test_top_position_falls_back_when_no_opening_main(tmp_path: Path):
    """A 'top' request on a page with no opening <main> falls back to the default
    before-</main> placement rather than skipping the splice."""
    target = tmp_path / "build"
    (target / "app").mkdir(parents=True)
    (target / "components").mkdir()
    page = target / "app" / "page.tsx"
    page.write_text(_PAGE_TSX_NO_OPENING_MAIN, encoding="utf-8")

    written = materialize_generative_components(target, [{**_SPEC, "position": "top"}])
    assert written == ["components/generated/image-placeholder-grid.tsx"]
    text = page.read_text(encoding="utf-8")
    usage = text.index("<GeneratedImagePlaceholderGrid />")
    closing_main = text.index("</main>")
    assert usage < closing_main


def test_materialise_is_idempotent(tmp_path: Path):
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [_SPEC])
    first = page.read_text(encoding="utf-8")
    # Re-run with the SAME directive: page.tsx is regenerated by write_pages in
    # the real build, but a defensive re-run on the already-spliced page must not
    # double-insert.
    materialize_generative_components(target, [_SPEC])
    second = page.read_text(encoding="utf-8")
    assert second.count("<GeneratedImagePlaceholderGrid />") == 1
    assert second.count("@/components/generated/image-placeholder-grid") == 1
    # A second run on an already-spliced page is a no-op (no further change).
    assert first == second


def test_cta_materialise_is_idempotent(tmp_path: Path):
    target, page = _make_build(tmp_path)
    materialize_generative_components(target, [_CTA_SPEC])
    first = page.read_text(encoding="utf-8")
    materialize_generative_components(target, [_CTA_SPEC])
    second = page.read_text(encoding="utf-8")
    assert second.count(f"<{_CTA_COMPONENT} />") == 1
    assert second.count("@/components/generated/cta-contact-block") == 1
    assert first == second


def test_unknown_recipe_fails_closed(tmp_path: Path):
    target, _page = _make_build(tmp_path)
    bad = {**_SPEC, "recipe": "free-llm-component", "id": "x"}
    with pytest.raises(GenerativeEmitError):
        materialize_generative_components(target, [bad])


def test_unsafe_id_fails_closed(tmp_path: Path):
    target, _page = _make_build(tmp_path)
    for unsafe_id in ["../escape", "a/b", "UPPER", ".env"]:
        with pytest.raises(GenerativeEmitError):
            materialize_generative_components(target, [{**_SPEC, "id": unsafe_id}])


def test_missing_route_page_is_honest_skip(tmp_path: Path):
    """A routeId whose page.tsx does not exist writes no orphan component file."""
    target, _page = _make_build(tmp_path)
    written = materialize_generative_components(
        target, [{**_SPEC, "routeId": "nonexistent"}]
    )
    assert written == []
    assert not (target / "components" / "generated").exists()


def test_assert_safe_write_path_refuses_protected_and_escaping_paths(tmp_path: Path):
    build_root = tmp_path / "build"
    build_root.mkdir()
    # package.json / lockfile / env files are refused.
    for name in ["package.json", "package-lock.json", ".env", ".env.local"]:
        with pytest.raises(GenerativeEmitError):
            _assert_safe_write_path(build_root, build_root / name)
    # node_modules is refused.
    with pytest.raises(GenerativeEmitError):
        _assert_safe_write_path(build_root, build_root / "node_modules" / "x.tsx")
    # A path outside the build dir is refused.
    with pytest.raises(GenerativeEmitError):
        _assert_safe_write_path(build_root, tmp_path / "outside.tsx")
    # A legitimate component path is allowed (no raise).
    ok = _assert_safe_write_path(
        build_root, build_root / "components" / "generated" / "image-placeholder-grid.tsx"
    )
    assert ok == (build_root / "components" / "generated" / "image-placeholder-grid.tsx").resolve()


def test_does_not_touch_package_json_during_materialise(tmp_path: Path):
    """A real-shaped build with a package.json is left byte-identical."""
    target, _page = _make_build(tmp_path)
    pkg = target / "package.json"
    pkg.write_text('{"name": "site"}\n', encoding="utf-8")
    before = pkg.read_text(encoding="utf-8")
    materialize_generative_components(target, [_SPEC])
    assert pkg.read_text(encoding="utf-8") == before
