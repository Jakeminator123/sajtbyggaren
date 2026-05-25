"""Tests for Sprintvakt V1 coordination tooling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tooling.sprintvakt_mcp.core import (
    SprintvaktError,
    create_gap,
    detect_collisions,
    generate_agent_prompt,
    paths_overlap,
    post_merge_sync_instructions,
    render_gap_markdown,
    reserve_paths,
    validate_workboard,
)


def _base_workboard() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "updatedAt": "2026-05-24T00:00:00Z",
        "updatedBy": "test",
        "people": {
            "jakob": {
                "allocation": 0.75,
                "lanes": ["backend", "generation", "governance", "scripts", "runtime"],
                "defaultBranch": "jakob-be",
            },
            "christopher": {
                "allocation": 0.25,
                "lanes": ["ui", "frontend", "viewser", "visual-polish"],
                "defaultBranch": "christopher-ui",
            },
        },
        "rules": ["Mutating tools require dryRun and confirm:true."],
        "reservedPaths": [
            {
                "owner": "jakob",
                "paths": [
                    "scripts/build_site.py",
                    "packages/generation/**",
                    "governance/policies/**",
                    "tests/test_*.py",
                ],
                "reason": "backend/generation/governance ownership",
            },
            {
                "owner": "christopher",
                "paths": ["apps/viewser/components/**", "apps/viewser/app/**/*.tsx"],
                "reason": "UI/frontend ownership",
            },
        ],
        "queuedGaps": [],
        "activeGaps": [],
        "completedGaps": [],
        "decisions": [],
    }


def _write_workboard(tmp_path: Path, workboard: dict[str, object] | None = None) -> Path:
    docs = tmp_path / "docs"
    (docs / "gaps").mkdir(parents=True)
    path = docs / "workboard.json"
    path.write_text(
        json.dumps(workboard or _base_workboard(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _gap(
    gap_id: str,
    *,
    owner: str = "jakob",
    paths: list[str] | None = None,
    status: str = "active",
) -> dict[str, object]:
    return {
        "id": gap_id,
        "type": "Gap/Guard",
        "owner": owner,
        "title": f"{gap_id} title",
        "whyNow": "Needed now.",
        "paths": paths or ["docs/example.md"],
        "doNotTouch": ["packages/generation/**"],
        "acceptanceCriteria": ["Accepted when checked."],
        "checks": ["python scripts/sprintvakt_check.py"],
        "collisionRisk": "green",
        "reviewer": "jakob",
        "status": status,
        "createdAt": "2026-05-24T00:00:00Z",
        "updatedAt": "2026-05-24T00:00:00Z",
        "notes": [],
    }


@pytest.mark.tooling
def test_valid_workboard_passes(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)

    result = validate_workboard(workboard_path=workboard_path)

    assert result["ok"] is True
    assert result["errors"] == []


@pytest.mark.tooling
def test_two_active_gaps_with_same_path_block(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard["activeGaps"] = [
        _gap("GAP-one", paths=["docs/shared.md"]),
        _gap("GAP-two", paths=["docs/shared.md"]),
    ]
    workboard_path = _write_workboard(tmp_path, workboard)

    result = validate_workboard(workboard_path=workboard_path)

    assert result["ok"] is False
    assert any("GAP-one overlaps GAP-two" in error for error in result["errors"])


@pytest.mark.tooling
def test_two_active_gaps_with_different_literal_docs_do_not_block(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard["activeGaps"] = [
        _gap("GAP-one", paths=["docs/a.md"]),
        _gap("GAP-two", paths=["docs/b.md"]),
    ]
    workboard_path = _write_workboard(tmp_path, workboard)

    result = validate_workboard(workboard_path=workboard_path)

    assert result["ok"] is True
    assert result["errors"] == []


@pytest.mark.tooling
def test_paths_overlap_distinguishes_literals_and_globs() -> None:
    assert paths_overlap("docs/workboard.json", "docs/sprintvakt-mcp.md") is False
    assert paths_overlap("docs/workboard.json", "docs/workboard.json") is True
    assert paths_overlap("docs/gaps/**", "docs/gaps/GAP-docs.md") is True
    assert paths_overlap("docs/gaps/", "docs/gaps/GAP-docs.md") is True


@pytest.mark.tooling
def test_christopher_generation_gap_blocks(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard["activeGaps"] = [
        _gap("GAP-leak", owner="christopher", paths=["packages/generation/planning/plan.py"])
    ]
    workboard_path = _write_workboard(tmp_path, workboard)

    result = validate_workboard(workboard_path=workboard_path)

    assert result["ok"] is False
    assert any("Christopher default lane" in error for error in result["errors"])


@pytest.mark.tooling
def test_docs_only_gap_is_green(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)

    result = detect_collisions(
        {"owner": "all", "paths": ["docs/gaps/GAP-docs.md"], "includeExistingGaps": True},
        workboard_path=workboard_path,
    )

    assert result["collisionRisk"] == "green"
    assert result["collisions"] == []


@pytest.mark.tooling
def test_create_gap_dry_run_writes_nothing(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)

    result = create_gap(_create_payload(dry_run=True), workboard_path=workboard_path)

    assert result["dryRun"] is True
    assert not (tmp_path / "docs" / "gaps" / "GAP-docs.md").exists()
    persisted = json.loads(workboard_path.read_text(encoding="utf-8"))
    assert persisted["queuedGaps"] == []


@pytest.mark.tooling
def test_create_gap_without_confirm_when_writing_fails(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)

    with pytest.raises(SprintvaktError, match="requires confirm:true"):
        create_gap(_create_payload(dry_run=False, confirm=False), workboard_path=workboard_path)


@pytest.mark.tooling
def test_create_gap_allows_empty_do_not_touch(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)
    payload = _create_payload(dry_run=True)
    payload["doNotTouch"] = []

    result = create_gap(payload, workboard_path=workboard_path)

    assert result["gap"]["doNotTouch"] == []


@pytest.mark.tooling
def test_create_gap_defaults_missing_do_not_touch_to_empty(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)
    payload = _create_payload(dry_run=True)
    del payload["doNotTouch"]

    result = create_gap(payload, workboard_path=workboard_path)

    assert result["gap"]["doNotTouch"] == []


@pytest.mark.tooling
def test_generate_agent_prompt_contains_scope_fields(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard["queuedGaps"] = [_gap("GAP-prompt", paths=["docs/workboard.json"], status="queued")]
    workboard_path = _write_workboard(tmp_path, workboard)

    result = generate_agent_prompt(
        {"gapId": "GAP-prompt", "agentRole": "Builder", "owner": "jakob", "dryRun": True},
        workboard_path=workboard_path,
    )

    prompt = result["prompt"]
    assert "docs/workboard.json" in prompt
    assert "packages/generation/**" in prompt
    assert "python scripts/sprintvakt_check.py" in prompt
    assert "Accepted when checked." in prompt


@pytest.mark.tooling
def test_generate_agent_prompt_resolves_file_only_gap(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)
    gap_dict = _gap("GAP-fileonly", paths=["docs/file-only-scope.md"], status="queued")
    gap_dict["title"] = "File-only gap"
    gap_dict["whyNow"] = "Test the disk fallback."
    gap_dict["acceptanceCriteria"] = ["File-only gap is resolved."]
    gap_path = tmp_path / "docs" / "gaps" / "GAP-fileonly.md"
    gap_path.write_text(render_gap_markdown(gap_dict), encoding="utf-8")

    result = generate_agent_prompt(
        {"gapId": "GAP-fileonly", "agentRole": "Builder", "owner": "jakob"},
        workboard_path=workboard_path,
    )

    prompt = result["prompt"]
    assert "GAP-fileonly — File-only gap" in prompt
    assert "docs/file-only-scope.md" in prompt
    assert "File-only gap is resolved." in prompt


@pytest.mark.tooling
def test_find_gap_prefers_workboard_over_file(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard_gap = _gap("GAP-shared", paths=["docs/from-workboard.md"], status="queued")
    workboard_gap["title"] = "Workboard wins"
    workboard["queuedGaps"] = [workboard_gap]
    workboard_path = _write_workboard(tmp_path, workboard)

    file_gap = _gap("GAP-shared", paths=["docs/from-file.md"], status="queued")
    file_gap["title"] = "File loses"
    (tmp_path / "docs" / "gaps" / "GAP-shared.md").write_text(
        render_gap_markdown(file_gap), encoding="utf-8"
    )

    result = generate_agent_prompt(
        {"gapId": "GAP-shared", "agentRole": "Builder", "owner": "jakob"},
        workboard_path=workboard_path,
    )

    prompt = result["prompt"]
    assert "Workboard wins" in prompt
    assert "File loses" not in prompt
    assert "docs/from-workboard.md" in prompt
    assert "docs/from-file.md" not in prompt


@pytest.mark.tooling
def test_post_merge_sync_instructions_forbid_force_on_main() -> None:
    result = post_merge_sync_instructions(
        {"mergedPr": 68, "branches": ["jakob-be", "christopher-ui"]}
    )

    assert "git switch main" in result["commands"]
    assert "git push --force-with-lease origin jakob-be" in result["commands"]
    assert "git push --force-with-lease origin christopher-ui" in result["commands"]
    assert "Använd aldrig force eller force-with-lease på main" in result["warning"]


@pytest.mark.tooling
def test_absolute_and_parent_paths_are_rejected(tmp_path: Path) -> None:
    workboard_path = _write_workboard(tmp_path)

    with pytest.raises(SprintvaktError, match="Absolute paths"):
        detect_collisions(
            {"owner": "jakob", "paths": ["/tmp/outside"], "includeExistingGaps": False},
            workboard_path=workboard_path,
        )
    with pytest.raises(SprintvaktError, match="Parent traversal"):
        detect_collisions(
            {"owner": "jakob", "paths": ["docs/../secrets"], "includeExistingGaps": False},
            workboard_path=workboard_path,
        )


@pytest.mark.tooling
def test_reserve_paths_reports_existing_active_gap_collision(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard["activeGaps"] = [_gap("GAP-active", paths=["docs/workboard.json"])]
    workboard_path = _write_workboard(tmp_path, workboard)

    result = reserve_paths(
        {
            "owner": "jakob",
            "gapId": "GAP-new",
            "paths": ["docs/workboard.json"],
            "reason": "test overlap",
            "dryRun": True,
            "confirm": False,
        },
        workboard_path=workboard_path,
    )

    assert result["collisionRisk"] == "red"
    assert any(collision.get("withGapId") == "GAP-active" for collision in result["collisions"])


@pytest.mark.tooling
def test_reserve_paths_replaces_existing_gap_id(tmp_path: Path) -> None:
    workboard = _base_workboard()
    workboard["reservedPaths"].append(
        {
            "owner": "jakob",
            "gapId": "GAP-dup",
            "paths": ["docs/old-path.md"],
            "reason": "stale reservation",
            "createdAt": "2026-05-23T00:00:00Z",
        }
    )
    workboard_path = _write_workboard(tmp_path, workboard)

    result = reserve_paths(
        {
            "owner": "jakob",
            "gapId": "GAP-dup",
            "paths": ["docs/new-path.md"],
            "reason": "updated reservation",
            "dryRun": False,
            "confirm": True,
        },
        workboard_path=workboard_path,
    )

    assert result.get("written") is True
    persisted = json.loads(workboard_path.read_text(encoding="utf-8"))
    matching = [
        entry for entry in persisted["reservedPaths"] if entry.get("gapId") == "GAP-dup"
    ]
    assert len(matching) == 1
    assert matching[0]["paths"] == ["docs/new-path.md"]
    assert matching[0]["reason"] == "updated reservation"
    legacy = [
        entry for entry in persisted["reservedPaths"] if "gapId" not in entry
    ]
    assert len(legacy) == 2


def _create_payload(*, dry_run: bool, confirm: bool = False) -> dict[str, object]:
    return {
        "id": "GAP-docs",
        "owner": "steward",
        "type": "Gap/Docs",
        "title": "Docs gap",
        "whyNow": "Document a safe gap.",
        "paths": ["docs/gaps/GAP-docs.md"],
        "doNotTouch": ["packages/generation/**"],
        "acceptanceCriteria": ["Gap is documented."],
        "checks": ["python scripts/sprintvakt_check.py"],
        "reviewer": "jakob",
        "dryRun": dry_run,
        "confirm": confirm,
    }
