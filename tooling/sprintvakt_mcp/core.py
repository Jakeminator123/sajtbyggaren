"""Core functions for Sprintvakt V1.

The module is intentionally dependency-free and deterministic. It may read the
repository workboard and gap files, and mutating helpers may only write the
Sprintvakt files documented in ``docs/sprintvakt-mcp.md``.
"""

from __future__ import annotations

import fnmatch
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKBOARD = REPO_ROOT / "docs" / "workboard.json"
GAPS_DIR = REPO_ROOT / "docs" / "gaps"

ALLOWED_OWNERS = {"jakob", "christopher", "steward", "scout"}
PEOPLE_OWNERS = {"jakob", "christopher"}
ALLOWED_GAP_TYPES = {
    "Gap/UI",
    "Gap/Flow",
    "Gap/Guard",
    "Gap/Polish",
    "Gap/Docs",
    "Gap/Runtime",
}
ALLOWED_REVIEWERS = {"jakob", "christopher", "both"}
ALLOWED_STATUSES = {"queued", "active", "completed"}
ALLOWED_RISKS = {"green", "yellow", "red"}
VALID_GAP_ID_RE = re.compile(r"^GAP-[A-Za-z0-9][A-Za-z0-9_.-]*$")

CHRISTOPHER_RED_PATHS = (
    "scripts/**",
    "scripts/build_site.py",
    "packages/generation/**",
    "governance/policies/**",
    "tests/test_*.py",
)
CHRISTOPHER_CONTRACT_RISK_PATHS = (
    "apps/viewser/lib/**",
    "apps/viewser/app/api/**",
)
JAKOB_VIEWER_UI_PATHS = (
    "apps/viewser/components/**",
    "apps/viewser/app/**/*.tsx",
    "apps/viewser/app/**/*.css",
    "apps/viewser/public/**",
)
SPRINTVAKT_DOC_PATHS = (
    "docs/workboard.json",
    "docs/workboard.yaml",
    "docs/gaps/**",
    "docs/agent-prompts/sprintvakt.md",
    "docs/sprintvakt-mcp.md",
    "docs/sprintvakt-log.md",
)


class SprintvaktError(ValueError):
    """Raised when a Sprintvakt tool input is invalid or unsafe."""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workboard_path(path: Path | None = None) -> Path:
    return path or DEFAULT_WORKBOARD


def _repo_root_for(path: Path | None = None) -> Path:
    return _workboard_path(path).resolve().parent.parent


def load_workboard(path: Path | None = None) -> dict[str, Any]:
    workboard_path = _workboard_path(path)
    try:
        return json.loads(workboard_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SprintvaktError(f"Workboard not found: {workboard_path}") from exc
    except json.JSONDecodeError as exc:
        raise SprintvaktError(f"Workboard is not valid JSON: {exc}") from exc


def write_workboard(workboard: dict[str, Any], path: Path | None = None) -> None:
    workboard_path = _workboard_path(path)
    _assert_allowed_write(workboard_path, path)
    workboard_path.write_text(
        json.dumps(workboard, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sanitize_repo_path(value: str) -> str:
    if not isinstance(value, str):
        raise SprintvaktError("Path values must be strings.")
    raw = value.strip().replace("\\", "/")
    if not raw:
        raise SprintvaktError("Path values must not be empty.")
    if "\x00" in raw:
        raise SprintvaktError("Path values must not contain NUL bytes.")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        raise SprintvaktError(f"Absolute paths are not allowed: {value}")
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise SprintvaktError(f"Parent traversal is not allowed: {value}")
    return "/".join(parts)


def sanitize_paths(values: list[str] | tuple[str, ...]) -> list[str]:
    if not isinstance(values, list | tuple):
        raise SprintvaktError("paths must be a list.")
    paths = [sanitize_repo_path(value) for value in values]
    if not paths:
        raise SprintvaktError("paths must contain at least one path.")
    return paths


def _is_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _matches(pattern: str, path: str) -> bool:
    if pattern == path:
        return True
    return fnmatch.fnmatchcase(path, pattern)


def paths_overlap(left: str, right: str) -> bool:
    left = sanitize_repo_path(left)
    right = sanitize_repo_path(right)
    if left == right:
        return True
    if _matches(left, right) or _matches(right, left):
        return True
    left_base = _literal_prefix(left)
    right_base = _literal_prefix(right)
    if not left_base or not right_base:
        return False
    return left_base.startswith(right_base) or right_base.startswith(left_base)


def _literal_prefix(pattern: str) -> str:
    wildcard_positions = [pattern.find(char) for char in "*?[" if char in pattern]
    if not wildcard_positions:
        if pattern.endswith("/"):
            return pattern
        if "/" in pattern:
            return pattern.rsplit("/", 1)[0] + "/"
        return pattern
    prefix = pattern[: min(wildcard_positions)]
    if "/" in prefix:
        return prefix.rsplit("/", 1)[0] + "/"
    return ""


def _all_docs_only(paths: list[str]) -> bool:
    return all(path.startswith("docs/") for path in paths)


def _all_sprintvakt_docs(paths: list[str]) -> bool:
    return all(any(paths_overlap(pattern, path) for pattern in SPRINTVAKT_DOC_PATHS) for path in paths)


def _risk_rank(risk: str) -> int:
    return {"green": 0, "yellow": 1, "red": 2}[risk]


def _max_risk(left: str, right: str) -> str:
    return left if _risk_rank(left) >= _risk_rank(right) else right


def _make_collision(
    *,
    path: str,
    with_owner: str,
    reason: str,
    with_gap_id: str | None = None,
    risk: str = "red",
) -> dict[str, str]:
    collision = {
        "path": path,
        "withOwner": with_owner,
        "reason": reason,
        "risk": risk,
    }
    if with_gap_id:
        collision["withGapId"] = with_gap_id
    return collision


def _iter_gap_lists(workboard: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    gaps: list[tuple[str, dict[str, Any]]] = []
    for list_name in ("queuedGaps", "activeGaps", "completedGaps"):
        for gap in workboard.get(list_name, []):
            if isinstance(gap, dict):
                gaps.append((list_name, gap))
    return gaps


def _gap_status_from_list(list_name: str) -> str:
    return {
        "queuedGaps": "queued",
        "activeGaps": "active",
        "completedGaps": "completed",
    }.get(list_name, "queued")


def get_workboard(*, workboard_path: Path | None = None) -> dict[str, Any]:
    return load_workboard(workboard_path)


def list_gaps(
    *,
    status: str = "all",
    workboard_path: Path | None = None,
) -> dict[str, Any]:
    if status not in {"active", "queued", "completed", "all"}:
        raise SprintvaktError("status must be active, queued, completed or all.")
    workboard = load_workboard(workboard_path)
    gaps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for list_name, gap in _iter_gap_lists(workboard):
        gap_status = str(gap.get("status") or _gap_status_from_list(list_name))
        if status in {"all", gap_status}:
            item = deepcopy(gap)
            item["status"] = gap_status
            item["source"] = f"workboard:{list_name}"
            gaps.append(item)
            if isinstance(item.get("id"), str):
                seen_ids.add(item["id"])

    gaps_dir = _repo_root_for(workboard_path) / "docs" / "gaps"
    if gaps_dir.is_dir():
        for path in sorted(gaps_dir.glob("*.md")):
            if path.name in {"README.md", "gap-template.md"}:
                continue
            gap_id = path.stem
            if gap_id in seen_ids:
                continue
            if status in {"all", "queued"}:
                gaps.append(
                    {
                        "id": gap_id,
                        "status": "queued",
                        "source": f"file:{path.relative_to(_repo_root_for(workboard_path)).as_posix()}",
                    }
                )
    return {"gaps": gaps}


def detect_collisions(
    payload: dict[str, Any],
    *,
    workboard_path: Path | None = None,
) -> dict[str, Any]:
    owner = str(payload.get("owner", "all"))
    if owner not in PEOPLE_OWNERS | {"all"}:
        raise SprintvaktError("owner must be jakob, christopher or all.")
    paths = sanitize_paths(payload.get("paths", []))
    include_existing = bool(payload.get("includeExistingGaps", True))
    workboard = load_workboard(workboard_path)

    collisions: list[dict[str, str]] = []
    risk = "green"

    if owner == "christopher":
        for path in paths:
            if any(paths_overlap(pattern, path) for pattern in CHRISTOPHER_RED_PATHS):
                risk = "red"
                collisions.append(
                    _make_collision(
                        path=path,
                        with_owner="jakob",
                        reason="Christopher default lane may not touch backend/generation/governance/test paths.",
                        risk="red",
                    )
                )
            elif any(paths_overlap(pattern, path) for pattern in CHRISTOPHER_CONTRACT_RISK_PATHS):
                risk = _max_risk(risk, "yellow")
                collisions.append(
                    _make_collision(
                        path=path,
                        with_owner="jakob",
                        reason="Viewser server/API path may affect run-shape or contract behavior.",
                        risk="yellow",
                    )
                )

    if owner == "jakob":
        for path in paths:
            if any(paths_overlap(pattern, path) for pattern in JAKOB_VIEWER_UI_PATHS):
                risk = _max_risk(risk, "yellow")
                collisions.append(
                    _make_collision(
                        path=path,
                        with_owner="christopher",
                        reason="Jakob touching Viewser presentation paths should be coordinated with Christopher.",
                        risk="yellow",
                    )
                )

    if owner in {"steward", "scout", "all"} and _all_sprintvakt_docs(paths):
        risk = _max_risk(risk, "green")
    elif _all_docs_only(paths):
        risk = _max_risk(risk, "green")

    for reservation in workboard.get("reservedPaths", []):
        reserved_owner = str(reservation.get("owner", "unknown"))
        reserved_paths = [sanitize_repo_path(path) for path in reservation.get("paths", [])]
        if owner != "all" and reserved_owner == owner:
            continue
        for path in paths:
            for reserved_path in reserved_paths:
                if not paths_overlap(path, reserved_path):
                    continue
                reservation_risk = "red"
                if owner == "jakob" and reserved_owner == "christopher":
                    reservation_risk = "yellow"
                risk = _max_risk(risk, reservation_risk)
                collisions.append(
                    _make_collision(
                        path=path,
                        with_owner=reserved_owner,
                        reason=str(reservation.get("reason", "reserved path overlap")),
                        risk=reservation_risk,
                    )
                )

    if include_existing:
        for list_name, gap in _iter_gap_lists(workboard):
            if _gap_status_from_list(list_name) != "active" and gap.get("status") != "active":
                continue
            gap_id = str(gap.get("id", "unknown"))
            gap_owner = str(gap.get("owner", "unknown"))
            gap_paths = [sanitize_repo_path(path) for path in gap.get("paths", [])]
            for path in paths:
                for gap_path in gap_paths:
                    if paths_overlap(path, gap_path):
                        risk = "red"
                        collisions.append(
                            _make_collision(
                                path=path,
                                with_owner=gap_owner,
                                with_gap_id=gap_id,
                                reason="overlaps an active gap",
                                risk="red",
                            )
                        )

    recommendation = {
        "green": "No blocker detected. The gap can be queued or reserved.",
        "yellow": "Coordinate ownership before work starts, then document the handoff.",
        "red": "Stop. Split the gap, change owner or request explicit handoff before writing.",
    }[risk]
    safe_next_action = {
        "green": "create_gap dryRun, then confirm if the plan is still correct",
        "yellow": "ask Jakob to approve the contract or ownership boundary",
        "red": "do not reserve these paths",
    }[risk]
    return {
        "collisionRisk": risk,
        "collisions": collisions,
        "recommendation": recommendation,
        "safeNextAction": safe_next_action,
    }


def validate_workboard(*, workboard_path: Path | None = None) -> dict[str, Any]:
    workboard = load_workboard(workboard_path)
    errors: list[str] = []
    warnings: list[str] = []
    collisions: list[dict[str, str]] = []

    for field in ("schemaVersion", "updatedAt", "updatedBy", "people", "rules", "reservedPaths"):
        if field not in workboard:
            errors.append(f"missing required field: {field}")
    for owner in PEOPLE_OWNERS:
        if owner not in workboard.get("people", {}):
            errors.append(f"missing person: {owner}")

    for list_name, gap in _iter_gap_lists(workboard):
        status = str(gap.get("status") or _gap_status_from_list(list_name))
        gap_id = str(gap.get("id", "unknown"))
        owner = str(gap.get("owner", ""))
        if owner not in ALLOWED_OWNERS:
            errors.append(f"{gap_id}: invalid owner {owner!r}")
        if not gap.get("title"):
            errors.append(f"{gap_id}: missing title")
        paths = gap.get("paths", [])
        if not paths:
            errors.append(f"{gap_id}: missing paths")
            continue
        try:
            sanitized_paths = sanitize_paths(paths)
        except SprintvaktError as exc:
            errors.append(f"{gap_id}: {exc}")
            continue
        if not gap.get("acceptanceCriteria") and not gap.get("acceptance"):
            errors.append(f"{gap_id}: missing acceptance criteria")
        if not gap.get("checks"):
            errors.append(f"{gap_id}: missing checks")
        if status == "active":
            result = detect_collisions(
                {"owner": owner if owner in PEOPLE_OWNERS else "all", "paths": sanitized_paths, "includeExistingGaps": False},
                workboard_path=workboard_path,
            )
            for collision in result["collisions"]:
                if collision["risk"] == "red":
                    errors.append(f"{gap_id}: {collision['reason']} ({collision['path']})")
                elif collision["risk"] == "yellow":
                    warnings.append(f"{gap_id}: {collision['reason']} ({collision['path']})")

    active_gaps = [
        gap
        for list_name, gap in _iter_gap_lists(workboard)
        if _gap_status_from_list(list_name) == "active" or gap.get("status") == "active"
    ]
    for index, left in enumerate(active_gaps):
        for right in active_gaps[index + 1 :]:
            for left_path in left.get("paths", []):
                for right_path in right.get("paths", []):
                    try:
                        overlap = paths_overlap(left_path, right_path)
                    except SprintvaktError as exc:
                        errors.append(str(exc))
                        continue
                    if overlap:
                        collision = _make_collision(
                            path=sanitize_repo_path(left_path),
                            with_owner=str(right.get("owner", "unknown")),
                            with_gap_id=str(right.get("id", "unknown")),
                            reason=f"active gap overlaps {left.get('id', 'unknown')}",
                            risk="red",
                        )
                        collisions.append(collision)
                        errors.append(
                            f"{left.get('id', 'unknown')} overlaps {right.get('id', 'unknown')}: {left_path}"
                        )

    for reservation in workboard.get("reservedPaths", []):
        owner = str(reservation.get("owner", ""))
        if owner not in PEOPLE_OWNERS:
            errors.append(f"reservedPaths: invalid owner {owner!r}")
        try:
            reserved = sanitize_paths(reservation.get("paths", []))
        except SprintvaktError as exc:
            errors.append(f"reservedPaths/{owner}: {exc}")
            continue
        for path in reserved:
            if path in {"packages/**", "apps/**", "governance/**", "tests/**"}:
                warnings.append(f"reservedPaths/{owner}: broad scope may be wider than needed: {path}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "collisions": collisions,
    }


def create_gap(
    payload: dict[str, Any],
    *,
    workboard_path: Path | None = None,
) -> dict[str, Any]:
    dry_run = bool(payload.get("dryRun", True))
    confirm = bool(payload.get("confirm", False))
    if not dry_run and not confirm:
        raise SprintvaktError("create_gap with dryRun:false requires confirm:true.")

    gap = _gap_from_payload(payload)
    collision_result = detect_collisions(
        {"owner": gap["owner"] if gap["owner"] in PEOPLE_OWNERS else "all", "paths": gap["paths"], "includeExistingGaps": True},
        workboard_path=workboard_path,
    )
    if collision_result["collisionRisk"] == "red":
        raise SprintvaktError(f"create_gap blocked by red collision: {collision_result['collisions']}")
    gap["collisionRisk"] = collision_result["collisionRisk"]

    repo_root = _repo_root_for(workboard_path)
    gap_path = repo_root / "docs" / "gaps" / f"{gap['id']}.md"
    _assert_allowed_write(gap_path, workboard_path)
    gap_markdown = render_gap_markdown(gap)

    workboard = load_workboard(workboard_path)
    target_list = f"{gap['status']}Gaps"
    if target_list not in {"queuedGaps", "activeGaps", "completedGaps"}:
        target_list = "queuedGaps"
    planned_workboard = deepcopy(workboard)
    for list_name in ("queuedGaps", "activeGaps", "completedGaps"):
        planned_workboard.setdefault(list_name, [])
        planned_workboard[list_name] = [
            existing for existing in planned_workboard[list_name] if existing.get("id") != gap["id"]
        ]
    planned_workboard[target_list].append(gap)
    planned_workboard["updatedAt"] = utc_now()
    planned_workboard["updatedBy"] = "sprintvakt-mcp"

    result = {
        "dryRun": dry_run,
        "gap": gap,
        "collision": collision_result,
        "plannedFiles": [
            gap_path.relative_to(repo_root).as_posix(),
            _workboard_path(workboard_path).relative_to(repo_root).as_posix(),
        ],
        "gapMarkdown": gap_markdown,
        "workboardDiff": {
            "addTo": target_list,
            "updatedAt": planned_workboard["updatedAt"],
            "updatedBy": planned_workboard["updatedBy"],
        },
    }
    if dry_run:
        return result

    gap_path.write_text(gap_markdown, encoding="utf-8")
    write_workboard(planned_workboard, workboard_path)
    return result | {"written": True}


def _gap_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gap_id = str(payload.get("id", "")).strip()
    if not VALID_GAP_ID_RE.match(gap_id):
        raise SprintvaktError("id must match GAP-<letters-numbers-dots-dashes>.")
    owner = str(payload.get("owner", "")).strip()
    if owner not in ALLOWED_OWNERS:
        raise SprintvaktError(f"owner must be one of {sorted(ALLOWED_OWNERS)}.")
    gap_type = str(payload.get("type", "")).strip()
    if gap_type not in ALLOWED_GAP_TYPES:
        raise SprintvaktError(f"type must be one of {sorted(ALLOWED_GAP_TYPES)}.")
    reviewer = str(payload.get("reviewer", "jakob")).strip()
    if reviewer not in ALLOWED_REVIEWERS:
        raise SprintvaktError("reviewer must be jakob, christopher or both.")
    status = str(payload.get("status", "queued")).strip()
    if status not in ALLOWED_STATUSES:
        raise SprintvaktError("status must be queued, active or completed.")

    title = str(payload.get("title", "")).strip()
    why_now = str(payload.get("whyNow", "")).strip()
    if not title or not why_now:
        raise SprintvaktError("title and whyNow are required.")
    acceptance = _string_list(payload.get("acceptanceCriteria", []), "acceptanceCriteria")
    checks = _string_list(payload.get("checks", []), "checks")
    if not acceptance:
        raise SprintvaktError("acceptanceCriteria must contain at least one item.")
    if not checks:
        raise SprintvaktError("checks must contain at least one item.")

    now = utc_now()
    return {
        "id": gap_id,
        "type": gap_type,
        "owner": owner,
        "title": title,
        "whyNow": why_now,
        "paths": sanitize_paths(payload.get("paths", [])),
        "doNotTouch": sanitize_paths(payload.get("doNotTouch", [])),
        "acceptanceCriteria": acceptance,
        "checks": checks,
        "collisionRisk": "green",
        "reviewer": reviewer,
        "status": status,
        "createdAt": str(payload.get("createdAt") or now),
        "updatedAt": str(payload.get("updatedAt") or now),
        "notes": _string_list(payload.get("notes", []), "notes", required=False),
    }


def _string_list(value: Any, field: str, *, required: bool = True) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list):
        raise SprintvaktError(f"{field} must be a list.")
    result = [str(item).strip() for item in value if str(item).strip()]
    if required and not result:
        raise SprintvaktError(f"{field} must contain at least one item.")
    return result


def render_gap_markdown(gap: dict[str, Any]) -> str:
    lines = [
        f"# {gap['id']} — {gap['title']}",
        "",
        f"- id: `{gap['id']}`",
        f"- type: `{gap['type']}`",
        f"- owner: `{gap['owner']}`",
        f"- reviewer: `{gap['reviewer']}`",
        f"- status: `{gap['status']}`",
        f"- collisionRisk: `{gap['collisionRisk']}`",
        f"- createdAt: `{gap['createdAt']}`",
        f"- updatedAt: `{gap['updatedAt']}`",
        "",
        "## Why now",
        "",
        gap["whyNow"],
        "",
        "## Paths",
        "",
    ]
    lines.extend(f"- `{path}`" for path in gap["paths"])
    lines.extend(["", "## Do not touch", ""])
    lines.extend(f"- `{path}`" for path in gap["doNotTouch"])
    lines.extend(["", "## Acceptance criteria", ""])
    lines.extend(f"- {item}" for item in gap["acceptanceCriteria"])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{item}`" for item in gap["checks"])
    if gap.get("notes"):
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {item}" for item in gap["notes"])
    lines.append("")
    return "\n".join(lines)


def reserve_paths(
    payload: dict[str, Any],
    *,
    workboard_path: Path | None = None,
) -> dict[str, Any]:
    owner = str(payload.get("owner", "")).strip()
    if owner not in PEOPLE_OWNERS:
        raise SprintvaktError("owner must be jakob or christopher.")
    gap_id = str(payload.get("gapId", "")).strip()
    if not VALID_GAP_ID_RE.match(gap_id):
        raise SprintvaktError("gapId must match GAP-<letters-numbers-dots-dashes>.")
    paths = sanitize_paths(payload.get("paths", []))
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        raise SprintvaktError("reason is required.")
    dry_run = bool(payload.get("dryRun", True))
    confirm = bool(payload.get("confirm", False))
    if not dry_run and not confirm:
        raise SprintvaktError("reserve_paths with dryRun:false requires confirm:true.")

    collision_result = detect_collisions(
        {"owner": owner, "paths": paths, "includeExistingGaps": True},
        workboard_path=workboard_path,
    )
    if not dry_run and collision_result["collisionRisk"] == "red":
        raise SprintvaktError("reserve_paths blocked by red collision.")

    reservation = {
        "owner": owner,
        "gapId": gap_id,
        "paths": paths,
        "reason": reason,
        "createdAt": utc_now(),
    }
    result = {
        "dryRun": dry_run,
        "reservation": reservation,
        **collision_result,
    }
    if dry_run:
        return result

    workboard = load_workboard(workboard_path)
    workboard.setdefault("reservedPaths", []).append(reservation)
    workboard["updatedAt"] = utc_now()
    workboard["updatedBy"] = "sprintvakt-mcp"
    write_workboard(workboard, workboard_path)
    return result | {"written": True}


def suggest_next_gaps(
    payload: dict[str, Any],
    *,
    workboard_path: Path | None = None,
) -> dict[str, Any]:
    count = int(payload.get("count", 3))
    count = max(1, min(count, 3))
    for_owner = str(payload.get("forOwner", "all"))
    if for_owner not in PEOPLE_OWNERS | {"all"}:
        raise SprintvaktError("forOwner must be jakob, christopher or all.")
    mode = str(payload.get("mode", "safe"))
    if mode not in {"safe", "balanced", "aggressive"}:
        raise SprintvaktError("mode must be safe, balanced or aggressive.")

    suggestions = [
        {
            "id": "GAP-sprintvakt-ci-hardening",
            "owner": "jakob",
            "type": "Gap/Guard",
            "title": "Harden Sprintvakt check in the developer loop",
            "paths": ["scripts/sprintvakt_check.py", "tests/test_sprintvakt_check.py", "docs/sprintvakt-mcp.md"],
            "doNotTouch": ["scripts/build_site.py", "packages/generation/**", "apps/viewser/**"],
            "acceptanceCriteria": ["Collision checks are documented and pass locally."],
            "checks": ["python scripts/sprintvakt_check.py", "python -m pytest tests/test_sprintvakt_check.py -q"],
            "collisionRisk": "green",
        },
        {
            "id": "GAP-viewser-empty-state-polish",
            "owner": "christopher",
            "type": "Gap/UI",
            "title": "Polish a narrow Viewser empty/loading state",
            "paths": ["apps/viewser/components/**"],
            "doNotTouch": ["apps/viewser/lib/**", "apps/viewser/app/api/**", "packages/generation/**", "scripts/**"],
            "acceptanceCriteria": ["Only presentation components change and no run-shape changes are needed."],
            "checks": ["cd apps/viewser && npm run lint"],
            "collisionRisk": "yellow",
        },
        {
            "id": "GAP-restaurant-runtime-extension",
            "owner": "jakob",
            "type": "Gap/Runtime",
            "title": "Evaluate section-driven renderer for restaurant-hospitality",
            "paths": ["docs/scaffold-runtime-extension-needed.md"],
            "doNotTouch": ["apps/viewser/**"],
            "acceptanceCriteria": ["Runtime activation scope is written as a separate Jakob-owned plan before code changes."],
            "checks": ["python scripts/sprintvakt_check.py"],
            "collisionRisk": "yellow",
            "note": "Bigger and riskier than Sprintvakt V1A; do after coordination guard is merged.",
        },
        {
            "id": "GAP-gap-docs-cleanup",
            "owner": "steward",
            "type": "Gap/Docs",
            "title": "Keep gap docs current after the next merge",
            "paths": ["docs/workboard.json", "docs/gaps/**", "docs/sprintvakt-mcp.md"],
            "doNotTouch": ["packages/generation/**", "apps/viewser/**"],
            "acceptanceCriteria": ["Docs match merged state and branch sync instructions are still correct."],
            "checks": ["python scripts/sprintvakt_check.py"],
            "collisionRisk": "green",
        },
    ]
    filtered = [
        suggestion
        for suggestion in suggestions
        if for_owner == "all" or suggestion["owner"] == for_owner
    ]
    if mode == "safe":
        filtered.sort(key=lambda item: (_risk_rank(item["collisionRisk"]), item["id"]))
    return {"suggestions": filtered[:count], "mode": mode}


def generate_agent_prompt(
    payload: dict[str, Any],
    *,
    workboard_path: Path | None = None,
) -> dict[str, Any]:
    gap_id = str(payload.get("gapId", "")).strip()
    agent_role = str(payload.get("agentRole", "Builder")).strip()
    owner = str(payload.get("owner", "")).strip()
    if agent_role not in {"Scout", "Builder", "Steward"}:
        raise SprintvaktError("agentRole must be Scout, Builder or Steward.")
    if owner not in PEOPLE_OWNERS:
        raise SprintvaktError("owner must be jakob or christopher.")
    gap = _find_gap(gap_id, workboard_path)
    branch = load_workboard(workboard_path)["people"][owner]["defaultBranch"]
    prompt = f"""Du är {agent_role}-agent för Jakeminator123/sajtbyggaren.

Owner: {owner}
Branch: {branch}
Gap: {gap['id']} — {gap['title']}

Läs i ordning:
1. docs/current-focus.md
2. docs/handoff.md
3. docs/ownership-map.md
4. docs/workboard.json
5. docs/gaps/{gap['id']}.md om filen finns

Scope paths:
{_bullet_list(gap['paths'])}

Do not touch:
{_bullet_list(gap.get('doNotTouch', []))}

Acceptance:
{_bullet_list(gap.get('acceptanceCriteria', gap.get('acceptance', [])))}

Checks:
{_bullet_list(gap.get('checks', []))}

PR/direct-main rule:
- Arbeta enligt repo-reglerna för din branch.
- Sprintvakt-infra går via PR mot main, inte mot jakob-be eller christopher-ui.
- Öppna inte PR mot arbetsbrancherna.

Stoppregler:
- Stoppa om scope kräver filer utanför paths.
- Stoppa om collisionRisk blir red.
- Stoppa om Christopher behöver backend/generation/governance/scripts/runtime.
- Stoppa om du behöver GitHub write-, merge- eller force-push-automation.
"""
    return {
        "gapId": gap_id,
        "agentRole": agent_role,
        "owner": owner,
        "prompt": prompt,
    }


def _find_gap(gap_id: str, workboard_path: Path | None) -> dict[str, Any]:
    if not VALID_GAP_ID_RE.match(gap_id):
        raise SprintvaktError("gapId must match GAP-<letters-numbers-dots-dashes>.")
    workboard = load_workboard(workboard_path)
    for _list_name, gap in _iter_gap_lists(workboard):
        if gap.get("id") == gap_id:
            return gap
    raise SprintvaktError(f"Gap not found in workboard: {gap_id}")


def _bullet_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- none"


def post_merge_sync_instructions(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    merged_pr = payload.get("mergedPr", 68)
    branches = payload.get("branches", ["jakob-be", "christopher-ui"])
    if not isinstance(branches, list) or not all(isinstance(branch, str) for branch in branches):
        raise SprintvaktError("branches must be a list of branch names.")
    commands = [
        "git switch main",
        "git fetch origin --prune",
        "git pull --ff-only origin main",
    ]
    for branch in branches:
        safe_branch = sanitize_repo_path(branch)
        if "/" in safe_branch or safe_branch == "main":
            raise SprintvaktError(f"Unsafe branch name: {branch}")
        commands.extend(
            [
                f"git switch {safe_branch}",
                "git reset --hard origin/main",
                f"git push --force-with-lease origin {safe_branch}",
            ]
        )
    warning = (
        "force-with-lease är bara OK på solo-ägda arbetsbranches enligt repo-reglerna. "
        "Använd aldrig force eller force-with-lease på main."
    )
    return {
        "mergedPr": merged_pr,
        "branches": branches,
        "commands": commands,
        "warning": warning,
    }


def _assert_allowed_write(path: Path, workboard_path: Path | None) -> None:
    repo_root = _repo_root_for(workboard_path)
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise SprintvaktError(f"Refusing to write outside repo: {path}") from exc
    allowed = (
        rel == "docs/workboard.json"
        or rel == "docs/workboard.yaml"
        or rel == "docs/agent-prompts/sprintvakt.md"
        or rel == "docs/sprintvakt-log.md"
        or rel.startswith("docs/gaps/")
    )
    if not allowed:
        raise SprintvaktError(f"Refusing to write outside Sprintvakt files: {rel}")

