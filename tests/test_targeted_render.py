"""Tests for targeted render + version-build (KÖR-7d).

These lock the kor-7d "Definition of done":

- A capability apply (kor-7c) -> kor-7d derives the right affected route, builds
  a new immutable version, and the operator preview refreshes ONLY on a shippable
  build with a real visible change.
- A no-op (``appliedVisibleEffect`` false) -> ``previewShouldRefresh`` is False:
  no false success, no preview restart.
- ``projectId``/``siteId`` preserved; the ``current.json`` swap (build's job) is
  gated on ``ok``/``degraded`` (a skipped build never promotes); previous runs
  are left untouched.
- FYND2: kor-7d refuses (``TargetedRenderError``) a version that did not come
  from the internal kor-7b->kor-7c chain, so external/hand-built input never
  silently reaches the build path.

The pure derivation/diff/decision helpers are unit-tested directly; the
orchestrator is exercised both with an injected fake build (Node-free, to assert
the applied/no-op/skipped decisions and trace) and with the real ``build()`` at
``do_build=False`` (to prove the apply->build chain wires and stays immutable).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.build.targeted_render import (  # noqa: E402
    ROOT_ROUTE_ID,
    SHARED_ROUTE_ID,
    TargetedRenderError,
    TargetedRenderPlan,
    TargetedRenderResult,
    affected_routes_from_apply,
    changed_routes_between_snapshots,
    decide_preview_refresh,
    derive_targeted_render_plan,
    route_id_for_generated_file,
    route_id_from_patch_field,
)
from packages.generation.orchestration.apply import (  # noqa: E402
    AppliedCapability,
    ApplyResult,
    apply_patch_plan,
)
from packages.generation.orchestration.patch import (  # noqa: E402
    ArtifactPatch,
    PatchPlan,
)

GENPKG = "generation-package.json"
SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"
HOME_FIELD = "contentBlocks.home.service-summary.accessoryComponent"


# ---------------------------------------------------------------------------
# Pure: route id derivation
# ---------------------------------------------------------------------------


def test_route_id_from_patch_field() -> None:
    assert route_id_from_patch_field(HOME_FIELD) == "home"
    assert route_id_from_patch_field("contentBlocks.om-oss.hero.headline") == "om-oss"
    assert route_id_from_patch_field("visualDirection.mood") is None
    assert route_id_from_patch_field("") is None
    assert route_id_from_patch_field(None) is None


def test_route_id_for_generated_file() -> None:
    assert route_id_for_generated_file("app/page.tsx") == ROOT_ROUTE_ID
    assert route_id_for_generated_file("app/om-oss/page.tsx") == "om-oss"
    assert route_id_for_generated_file("app/a/b/page.tsx") == "a"
    assert route_id_for_generated_file("app/globals.css") == SHARED_ROUTE_ID
    assert route_id_for_generated_file("app/layout.tsx") == SHARED_ROUTE_ID
    assert route_id_for_generated_file("public/logo.svg") == SHARED_ROUTE_ID


# ---------------------------------------------------------------------------
# Pure: affected routes from apply
# ---------------------------------------------------------------------------


def _apply_result(*, fields: list[str]) -> ApplyResult:
    return ApplyResult(
        applied=True,
        siteId=SITE_ID,
        projectId=PROJECT_ID,
        previousVersion=1,
        version=2,
        appliedCapabilities=[
            AppliedCapability(patchField=field, capability="contact-form")
            for field in fields
        ],
    )


def test_affected_routes_from_apply() -> None:
    result = _apply_result(fields=[HOME_FIELD, "contentBlocks.home.hero.x"])
    # Deduped, ordered: both fields are on "home".
    assert affected_routes_from_apply(result) == ["home"]


def test_affected_routes_from_apply_empty() -> None:
    assert affected_routes_from_apply(_apply_result(fields=[])) == []


def test_derive_targeted_render_plan() -> None:
    plan = derive_targeted_render_plan(_apply_result(fields=[HOME_FIELD]))
    assert isinstance(plan, TargetedRenderPlan)
    assert plan.siteId == SITE_ID
    assert plan.version == 2
    assert plan.previousVersion == 1
    assert plan.affectedRoutes == ["home"]


def test_derive_targeted_render_plan_defaults_to_root() -> None:
    plan = derive_targeted_render_plan(_apply_result(fields=[]))
    assert plan.affectedRoutes == [ROOT_ROUTE_ID]
    assert "default" in plan.rationale.lower()


# ---------------------------------------------------------------------------
# Pure: per-route snapshot diff
# ---------------------------------------------------------------------------


def _write_snapshot(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def test_changed_routes_detects_home_change(tmp_path: Path) -> None:
    prev = _write_snapshot(
        tmp_path / "prev", {"app/page.tsx": "A", "app/om-oss/page.tsx": "B"}
    )
    cur = _write_snapshot(
        tmp_path / "cur", {"app/page.tsx": "CHANGED", "app/om-oss/page.tsx": "B"}
    )
    assert changed_routes_between_snapshots(prev, cur) == {"home"}


def test_changed_routes_detects_shared_change(tmp_path: Path) -> None:
    prev = _write_snapshot(tmp_path / "prev", {"app/globals.css": "x"})
    cur = _write_snapshot(tmp_path / "cur", {"app/globals.css": "y"})
    assert changed_routes_between_snapshots(prev, cur) == {SHARED_ROUTE_ID}


def test_changed_routes_empty_when_identical(tmp_path: Path) -> None:
    prev = _write_snapshot(tmp_path / "prev", {"app/page.tsx": "A"})
    cur = _write_snapshot(tmp_path / "cur", {"app/page.tsx": "A"})
    assert changed_routes_between_snapshots(prev, cur) == set()


def test_changed_routes_none_without_previous(tmp_path: Path) -> None:
    cur = _write_snapshot(tmp_path / "cur", {"app/page.tsx": "A"})
    assert changed_routes_between_snapshots(None, cur) is None
    assert changed_routes_between_snapshots(tmp_path / "missing", cur) is None


# ---------------------------------------------------------------------------
# Pure: preview-refresh decision (only ok|degraded + visible change)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "applied", "expected"),
    [
        ("ok", True, True),
        ("degraded", True, True),
        ("ok", False, False),
        ("skipped", True, False),
        ("failed", True, False),
        (None, True, False),
    ],
)
def test_decide_preview_refresh(status, applied, expected) -> None:
    assert decide_preview_refresh(build_status=status, applied_visible_effect=applied) is expected


# ---------------------------------------------------------------------------
# Orchestrator (injected fake build): applied / no-op / skipped decisions
# ---------------------------------------------------------------------------


def _generate():
    from scripts.prompt_to_project_input import generate

    return generate


def _capability_patch(*, capability: str = "contact-form") -> PatchPlan:
    return PatchPlan(
        patches=[
            ArtifactPatch(
                artifact=GENPKG,
                field=HOME_FIELD,
                value={"component": capability, "variant": None, "capability": capability},
            )
        ],
        valid=True,
    )


def _seed_applied_v2(monkeypatch: pytest.MonkeyPatch, prompt_inputs: Path) -> Path:
    """Generate v1 + apply a capability -> v2 (with kor-7c apply provenance)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate = _generate()
    generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    apply_patch_plan(_capability_patch(), site_id=SITE_ID, output_dir=prompt_inputs)
    return prompt_inputs / f"{SITE_ID}.v2.project-input.json"


def _make_fake_build(*, status: str, applied_visible_effect: bool):
    """Return a build_fn stand-in that writes a run + build-result.json."""

    def fake_build(dossier_path, *, do_build=True, runs_dir=None, generated_dir=None):
        run_dir = Path(runs_dir) / f"run-fake-{status}"
        snapshot = run_dir / "generated-files" / "app"
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "page.tsx").write_text("export default 1", encoding="utf-8")
        (run_dir / "trace.ndjson").write_text("", encoding="utf-8")
        build_result = {
            "siteId": SITE_ID,
            "status": status,
            "version": 2,
            "appliedVisibleEffect": applied_visible_effect,
            "prompt": {"previousVersion": 1},
        }
        if status in ("ok", "degraded"):
            build_result["activeBuildId"] = "20260603T120000Z"
        (run_dir / "build-result.json").write_text(
            json.dumps(build_result), encoding="utf-8"
        )
        target = run_dir / "target"
        target.mkdir(exist_ok=True)
        return target, run_dir

    return fake_build


def _trace_events(run_dir: Path) -> list[dict]:
    path = run_dir / "trace.ndjson"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_orchestrator_applied_refreshes_preview(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.build_site import build_targeted_version

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    v2_path = _seed_applied_v2(monkeypatch, prompt_inputs)

    result = build_targeted_version(
        v2_path,
        do_build=True,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
        build_fn=_make_fake_build(status="ok", applied_visible_effect=True),
    )
    assert isinstance(result, TargetedRenderResult)
    assert result.outcome == "applied"
    assert result.previewShouldRefresh is True
    assert result.affectedRoutes == ["home"]
    assert result.buildStatus == "ok"
    assert result.activeBuildId == "20260603T120000Z"

    events = _trace_events(tmp_path / "runs" / "run-fake-ok")
    outcome_events = [e for e in events if e["event"] == "targeted_render.outcome"]
    assert len(outcome_events) == 1
    assert outcome_events[0]["status"] == "done"


def test_orchestrator_no_op_does_not_refresh_preview(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.build_site import build_targeted_version

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    v2_path = _seed_applied_v2(monkeypatch, prompt_inputs)

    result = build_targeted_version(
        v2_path,
        do_build=True,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
        build_fn=_make_fake_build(status="ok", applied_visible_effect=False),
    )
    assert result.outcome == "no-op"
    assert result.previewShouldRefresh is False
    assert result.appliedVisibleEffect is False
    events = _trace_events(tmp_path / "runs" / "run-fake-ok")
    outcome = [e for e in events if e["event"] == "targeted_render.outcome"][0]
    assert outcome["status"] == "warning"


def test_orchestrator_skipped_build_never_promotes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.build_site import build_targeted_version

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    v2_path = _seed_applied_v2(monkeypatch, prompt_inputs)

    result = build_targeted_version(
        v2_path,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
        build_fn=_make_fake_build(status="skipped", applied_visible_effect=True),
    )
    assert result.outcome == "skipped"
    assert result.previewShouldRefresh is False
    assert result.activeBuildId is None


# ---------------------------------------------------------------------------
# FYND2: internal-chain guard (revalidation assumption)
# ---------------------------------------------------------------------------


def test_orchestrator_refuses_non_internal_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A version with no kor-7c apply provenance is refused (STOP and report)."""
    from scripts.build_site import build_targeted_version

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    generate = _generate()
    _, _, v1_path, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    # v1 is an init version (no appliedPatchPlan provenance) -> refused.
    with pytest.raises(TargetedRenderError, match="interna kedjan"):
        build_targeted_version(
            v1_path,
            do_build=False,
            runs_dir=tmp_path / "runs",
            generated_dir=tmp_path / "gen",
            build_fn=_make_fake_build(status="ok", applied_visible_effect=True),
        )


def test_orchestrator_allows_internal_provenance_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.build_site import build_targeted_version

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    v2_path = _seed_applied_v2(monkeypatch, prompt_inputs)
    # v2 carries meta.appliedPatchPlan.source == "kor-7c-artifact-apply" -> allowed.
    result = build_targeted_version(
        v2_path,
        do_build=True,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
        build_fn=_make_fake_build(status="ok", applied_visible_effect=True),
    )
    assert result.outcome == "applied"


def test_orchestrator_allows_explicit_apply_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit apply_result satisfies the internal-chain guard."""
    from scripts.build_site import build_targeted_version

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    generate = _generate()
    _, _, v1_path, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    result = build_targeted_version(
        v1_path,
        apply_result=_apply_result(fields=[HOME_FIELD]),
        do_build=True,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "gen",
        build_fn=_make_fake_build(status="ok", applied_visible_effect=True),
    )
    assert result.affectedRoutes == ["home"]


# ---------------------------------------------------------------------------
# Real chain (do_build=False): apply v2 -> targeted build -> identity + immutability
# ---------------------------------------------------------------------------


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_real_chain_preserves_identity_and_old_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.build_site import build, build_targeted_version

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"

    generate = _generate()
    _, _, v1_path, _ = generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    # Build v1 (real build, skip npm) so a previous run exists.
    _target_v1, run_dir_v1 = build(
        v1_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )
    run_v1_before = _hash_tree(run_dir_v1)

    # kor-7c apply -> v2, then kor-7d targeted version-build (real build, skip npm).
    apply_patch_plan(_capability_patch(), site_id=SITE_ID, output_dir=prompt_inputs)
    v2_path = prompt_inputs / f"{SITE_ID}.v2.project-input.json"
    result = build_targeted_version(
        v2_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )

    # do_build=False -> status skipped -> no promotion, no preview refresh.
    assert result.outcome == "skipped"
    assert result.previewShouldRefresh is False
    assert result.version == 2
    assert result.runId is not None

    # Identity preserved: same project track, new run.
    build_result_v2 = json.loads(
        (runs_dir / result.runId / "build-result.json").read_text(encoding="utf-8")
    )
    assert build_result_v2["projectId"] == PROJECT_ID
    assert build_result_v2["version"] == 2
    assert build_result_v2["engineMode"] == "followup"

    # Old run untouched (byte-for-byte) and a distinct new run was created.
    assert result.runId != run_dir_v1.name
    assert _hash_tree(run_dir_v1) == run_v1_before
