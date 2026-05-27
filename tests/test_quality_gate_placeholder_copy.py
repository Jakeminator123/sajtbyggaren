from pathlib import Path

from packages.generation.quality_gate import run_quality_gate
from packages.generation.quality_gate.checks import run_placeholder_copy_scan_check
from packages.generation.quality_gate.gate import _CHECKS_REGISTRY


def _page(root: Path, text: str) -> None:
    path = root / "app" / "page.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_placeholder_copy_scan_flags_each_pattern(tmp_path: Path) -> None:
    # Strängarna är medvetet lowercase där det går (regex är re.IGNORECASE)
    # för att inte triggra check_term_coverage --strict på capitalized
    # multi-word phrases i Python-source.
    for copy in [
        "lorem ipsum dolor sit amet",
        "this is TBD for launch",
        "PLATSHÅLLARE för ingress",
        "REPLACE_ME",
        "<insert customer quote here>",
    ]:
        _page(tmp_path, copy)
        result = run_placeholder_copy_scan_check(tmp_path)
        assert result.status == "failed"
        assert result.findings


def test_placeholder_copy_scan_ignores_dev_markers(tmp_path: Path) -> None:
    """Dev-markers TODO:/FIXME triggar för mycket brus i kodkommentarer.

    Reviewer-fynd post PR #129 + #133: ett ``TODO:`` i en .tsx-kommentar är
    inte samma kategori som copy-placeholder-fraser i en hero-rubrik
    (lorem-ipsum, platshållare, etc.). Exkluderade från
    ``_PLACEHOLDER_PATTERNS``.
    """
    for dev_marker in ["TODO: skriv om detta", "FIXME after review"]:
        _page(tmp_path, dev_marker)
        assert run_placeholder_copy_scan_check(tmp_path).status == "ok"


def test_placeholder_copy_scan_avoids_false_positives(tmp_path: Path) -> None:
    _page(tmp_path, "Established contact copy. notbd replace_meeting är legitima ord.")
    assert run_placeholder_copy_scan_check(tmp_path).status == "ok"


def test_placeholder_copy_scan_registered_as_warning(tmp_path: Path) -> None:
    _page(tmp_path, "lorem ipsum dolor")
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    by_name = {check.name: check for check in result.checks}
    assert by_name["placeholder-copy-scan"].severity == "warning"
    assert result.status == "ok"
    assert dict(_CHECKS_REGISTRY)["placeholder-copy-scan"] == "warning"
