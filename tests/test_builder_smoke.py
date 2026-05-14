"""Smoke test for the Builder MVP.

Runs `scripts.build_site.build` with `do_build=False` so the test does not
require Node, npm or network. Verifies that the deterministic happy path
writes:

- the four required Next.js page files under `.generated/painter-palma/app/`
- the six canonical Engine Run artefakter under `data/runs/<runId>/`
- a trace with at least three Engine Events covering all three phases
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.tooling
def test_builder_smoke_writes_routes_and_run_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from scripts.build_site import build  # imported lazily to avoid heavy import on collection

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = (
        REPO_ROOT / "examples" / "painter-palma.project-input.json"
    )
    assert project_input_path.exists(), "painter-palma project input must exist"

    target, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)

    # Generated routes
    expected_pages = [
        target / "app" / "page.tsx",
        target / "app" / "tjanster" / "page.tsx",
        target / "app" / "om-oss" / "page.tsx",
        target / "app" / "kontakt" / "page.tsx",
    ]
    for page in expected_pages:
        assert page.exists(), f"Expected page missing: {page}"

    # Engine Run artefakter under data/runs/<runId>/
    expected_artifacts = [
        "input.json",
        "site-brief.json",
        "site-plan.json",
        "generation-package.json",
        "build-result.json",
        "trace.ndjson",
    ]
    for name in expected_artifacts:
        assert (run_dir / name).exists(), f"Expected artefakt missing: {name}"

    # Trace must have engine events from all three phases
    events: list[dict] = []
    with (run_dir / "trace.ndjson").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    assert len(events) >= 3, f"Expected >=3 trace events, got {len(events)}"
    phases = {e["phase"] for e in events}
    assert {"understand", "plan", "build"}.issubset(phases), (
        f"Trace must cover all three phases. Got: {phases}"
    )

    # Build result reflects --skip-build and dossier identity
    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert result["siteId"] == "painter-palma"
    assert result["scaffoldId"] == "local-service-business"
    assert result["variantId"] == "nordic-trust"
    assert result["status"] == "skipped", "skip-build should mark status=skipped"
    assert result["npmSteps"] == []

    # Site brief mock contract
    brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    assert brief["briefSource"] == "mock-no-key"
    assert brief["modelUsed"] == "mock"
    assert brief["language"] == "sv"
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.out
    assert "mock Site Brief" in captured.out


@pytest.mark.tooling
def test_builder_assertion_blocks_env_writes() -> None:
    """Builder helper must refuse to write secret .env files."""
    from scripts.build_site import resolve_generated_dir, write

    preview_root = resolve_generated_dir()
    target = preview_root / "painter-palma" / ".env"
    with pytest.raises(AssertionError):
        write(target, "SECRET=oops\n")

    target_local = preview_root / "painter-palma" / ".env.local"
    with pytest.raises(AssertionError):
        write(target_local, "SECRET=oops\n")

    # `.env.example` must still be allowed - it is the canonical placeholder.
    safe = preview_root / "painter-palma" / ".env.example"
    write(safe, "# safe placeholder\n")
    assert safe.exists()
    safe.unlink()
