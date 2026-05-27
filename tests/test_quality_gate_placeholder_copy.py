from pathlib import Path

from packages.generation.quality_gate import run_quality_gate
from packages.generation.quality_gate.checks import run_placeholder_copy_scan_check
from packages.generation.quality_gate.gate import _CHECKS_REGISTRY


def _page(root: Path, text: str) -> None:
    path = root / "app" / "page.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_placeholder_copy_scan_flags_each_pattern(tmp_path: Path) -> None:
    for copy in [
        "Lorem ipsum dolor sit amet",
        "This is TBD for launch",
        "PLATSHÅLLARE för ingress",
        "TODO: skriv om detta",
        "FIXME after review",
        "REPLACE_ME",
        "<insert customer quote here>",
    ]:
        _page(tmp_path, copy)
        result = run_placeholder_copy_scan_check(tmp_path)
        assert result.status == "failed"
        assert result.findings


def test_placeholder_copy_scan_avoids_false_positives(tmp_path: Path) -> None:
    _page(tmp_path, "Established contact copy. notbd replace_meeting är legitima ord.")
    assert run_placeholder_copy_scan_check(tmp_path).status == "ok"


def test_placeholder_copy_scan_registered_as_warning(tmp_path: Path) -> None:
    _page(tmp_path, "TODO: byt copy")
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
