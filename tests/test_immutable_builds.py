"""Tests for B157 level 4, Stage A: immutable build-dir + atomic pointer-swap.

Three layers:

1. Unit tests for ``packages.generation.build.immutable_builds`` (build-id
   format + collision suffix, atomic ``current.json`` write via tmp+replace,
   ``read_active_build_dir`` with and without a valid pointer).
2. Build-flow tests for ``scripts.build_site.build``: a shippable run
   (``ok``/``degraded``) swaps ``current.json`` to the new build id; a
   ``failed``/``skipped`` run leaves the pointer untouched. The build-flow
   tests fake ``run_npm`` + ``run_phase3_quality_and_repair`` so they never
   shell out to ``npm`` or the real Quality Gate - they pin the pointer gate,
   not the framework build.
3. A structural lock on the Viewser preview resolver
   (``apps/viewser/lib/local-preview-server.ts``) since apps/viewser has no
   active TS test runner - the same pattern as
   ``tests/test_local_preview_server_b157_followup.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from packages.generation.build.immutable_builds import (
    POINTER_FILENAME,
    build_dir_for,
    new_build_id,
    read_active_build_dir,
    write_active_pointer,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PAINTER_PALMA = REPO_ROOT / "examples" / "painter-palma.project-input.json"
LOCAL_PREVIEW_SERVER = (
    REPO_ROOT / "apps" / "viewser" / "lib" / "local-preview-server.ts"
)
BUILD_RUNNER = REPO_ROOT / "apps" / "viewser" / "lib" / "build-runner.ts"


# ---------------------------------------------------------------------------
# new_build_id
# ---------------------------------------------------------------------------


def test_new_build_id_formats_utc_second_precision() -> None:
    moment = datetime(2026, 5, 31, 18, 45, 0, tzinfo=UTC)
    assert new_build_id(now=moment) == "20260531T184500Z"


def test_new_build_id_converts_aware_datetime_to_utc() -> None:
    # 20:45 in UTC+2 is 18:45 UTC; the id must be normalised to UTC.
    plus_two = timezone(timedelta(hours=2))
    moment = datetime(2026, 5, 31, 20, 45, 0, tzinfo=plus_two)
    assert new_build_id(now=moment) == "20260531T184500Z"


def test_new_build_id_default_now_is_utc_and_well_formed() -> None:
    build_id = new_build_id()
    # YYYYMMDDTHHMMSSZ -> 16 chars, ends with Z.
    assert len(build_id) == 16
    assert build_id.endswith("Z")
    # Parses back as a real UTC timestamp.
    datetime.strptime(build_id, "%Y%m%dT%H%M%SZ")


def test_new_build_id_appends_collision_suffix() -> None:
    moment = datetime(2026, 5, 31, 18, 45, 0, tzinfo=UTC)
    taken = {"20260531T184500Z", "20260531T184500Z-01"}
    assert new_build_id(now=moment, exists=lambda c: c in taken) == "20260531T184500Z-02"


def test_new_build_id_no_collision_returns_base() -> None:
    moment = datetime(2026, 5, 31, 18, 45, 0, tzinfo=UTC)
    assert new_build_id(now=moment, exists=lambda _c: False) == "20260531T184500Z"


# ---------------------------------------------------------------------------
# build_dir_for
# ---------------------------------------------------------------------------


def test_build_dir_for_layout(tmp_path: Path) -> None:
    build_dir = build_dir_for(tmp_path, "painter-palma", "20260531T184500Z")
    assert build_dir == tmp_path / "painter-palma" / "builds" / "20260531T184500Z"


# ---------------------------------------------------------------------------
# write_active_pointer (atomic) + read_active_build_dir
# ---------------------------------------------------------------------------


def test_write_active_pointer_writes_locked_schema(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    write_active_pointer(site_dir, "20260531T184500Z", "builds/20260531T184500Z")

    pointer = site_dir / POINTER_FILENAME
    assert pointer.is_file()
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    assert payload["activeBuildId"] == "20260531T184500Z"
    assert payload["buildPath"] == "builds/20260531T184500Z"
    assert isinstance(payload["updatedAt"], str) and payload["updatedAt"]
    # updatedAt must parse as an ISO-8601 UTC timestamp.
    parsed = datetime.fromisoformat(payload["updatedAt"])
    assert parsed.utcoffset() == timedelta(0)


def test_write_active_pointer_leaves_no_temp_file(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    write_active_pointer(site_dir, "20260531T184500Z", "builds/20260531T184500Z")
    leftovers = [p.name for p in site_dir.iterdir() if ".tmp-" in p.name]
    assert leftovers == [], f"temp pointer files leaked: {leftovers}"


def test_write_active_pointer_is_overwritten_atomically(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    write_active_pointer(site_dir, "20260531T184500Z", "builds/20260531T184500Z")
    write_active_pointer(site_dir, "20260531T185000Z", "builds/20260531T185000Z")
    payload = json.loads((site_dir / POINTER_FILENAME).read_text(encoding="utf-8"))
    assert payload["activeBuildId"] == "20260531T185000Z"


def test_read_active_build_dir_roundtrip(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    build_id = "20260531T184500Z"
    build_dir = site_dir / "builds" / build_id
    build_dir.mkdir(parents=True)
    write_active_pointer(site_dir, build_id, f"builds/{build_id}")
    assert read_active_build_dir(site_dir) == build_dir


def test_read_active_build_dir_missing_pointer_returns_none(tmp_path: Path) -> None:
    assert read_active_build_dir(tmp_path / "site") is None


def test_read_active_build_dir_invalid_json_returns_none(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / POINTER_FILENAME).write_text("{ not json", encoding="utf-8")
    assert read_active_build_dir(site_dir) is None


def test_read_active_build_dir_rejects_traversal_build_id(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / POINTER_FILENAME).write_text(
        json.dumps({"activeBuildId": "../../etc", "buildPath": "x"}),
        encoding="utf-8",
    )
    assert read_active_build_dir(site_dir) is None


def test_read_active_build_dir_missing_build_dir_returns_none(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    # Valid pointer, but the referenced build directory does not exist.
    write_active_pointer(site_dir, "20260531T184500Z", "builds/20260531T184500Z")
    assert read_active_build_dir(site_dir) is None


def test_read_active_build_dir_rejects_inconsistent_build_path(tmp_path: Path) -> None:
    # B-review 2026-05-31: activeBuildId is valid and its build dir exists, but
    # buildPath disagrees (tampered/half-updated pointer). Cross-validation must
    # treat the pointer as inconsistent and return None rather than silently
    # trusting activeBuildId.
    site_dir = tmp_path / "site"
    build_id = "20260531T184500Z"
    (site_dir / "builds" / build_id).mkdir(parents=True)
    (site_dir / POINTER_FILENAME).write_text(
        json.dumps(
            {
                "activeBuildId": build_id,
                "updatedAt": "2026-05-31T18:45:00+00:00",
                "buildPath": "builds/20260531T185000Z",
            }
        ),
        encoding="utf-8",
    )
    assert read_active_build_dir(site_dir) is None


# ---------------------------------------------------------------------------
# build() pointer-swap gate
# ---------------------------------------------------------------------------


def _fake_npm_step(*_args: object, **_kwargs: object) -> tuple[bool, float, str]:
    """Stand-in for run_npm: report success without shelling out to npm."""
    return (True, 0.1, "ok (mocked)")


def _fake_phase3(status: str):
    """Return a run_phase3_quality_and_repair stand-in fixed to ``status``."""

    def _inner(*_args: object, **_kwargs: object) -> tuple[dict, dict]:
        quality = {"status": status, "checks": []}
        repair = {"status": "no-fix-applied", "remainingErrors": []}
        return quality, repair

    return _inner


def _build_with_forced_status(
    status: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Run build() with npm + Quality Gate faked so overall_status == ``status``.

    ``do_build=True`` so the pointer-swap gate is reachable (do_build=False
    forces "skipped" before the gate). ``run_npm`` is faked to succeed and
    ``run_phase3_quality_and_repair`` is faked to return ``status`` so the run
    lands on the requested final state without npm or a real typecheck.
    """
    import scripts.build_site as build_site

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(build_site, "run_npm", _fake_npm_step)
    monkeypatch.setattr(build_site, "run_phase3_quality_and_repair", _fake_phase3(status))

    return build_site.build(
        PAINTER_PALMA,
        do_build=True,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )


def test_build_writes_into_immutable_builds_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, _run_dir = _build_with_forced_status("ok", tmp_path, monkeypatch)
    # target == <generated>/<siteId>/builds/<buildId>
    assert target.parent.name == "builds"
    assert target.parent.parent.parent == tmp_path / "generated"
    assert target.is_dir()


@pytest.mark.parametrize("status", ["ok", "degraded"])
def test_build_shippable_status_swaps_pointer(
    status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, run_dir = _build_with_forced_status(status, tmp_path, monkeypatch)
    site_dir = target.parent.parent
    build_id = target.name

    pointer = site_dir / "current.json"
    assert pointer.is_file(), f"{status} run must publish current.json"
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    assert payload["activeBuildId"] == build_id
    assert payload["buildPath"] == f"builds/{build_id}"

    # The pointer resolves back to the directory this run built.
    assert read_active_build_dir(site_dir) == target

    build_result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert build_result["status"] == status
    assert build_result["activeBuildId"] == build_id
    # devPreviewDir must point at the immutable build dir, not the site root.
    assert build_result["devPreviewDir"].endswith(f"builds/{build_id}")


def test_build_skipped_leaves_pointer_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.build_site as build_site

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target, run_dir = build_site.build(
        PAINTER_PALMA,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )
    site_dir = target.parent.parent

    assert not (site_dir / "current.json").exists(), (
        "skipped (do_build=False) run must not publish current.json"
    )
    assert read_active_build_dir(site_dir) is None
    build_result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert build_result["status"] == "skipped"
    assert "activeBuildId" not in build_result


def test_build_failed_leaves_pointer_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit):
        _build_with_forced_status("failed", tmp_path, monkeypatch)

    # build() raised before returning; locate the run dir + site dir on disk.
    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1
    build_result = json.loads((runs[0] / "build-result.json").read_text(encoding="utf-8"))
    assert build_result["status"] == "failed"
    assert "activeBuildId" not in build_result

    site_dirs = [p for p in (tmp_path / "generated").iterdir() if p.is_dir()]
    assert len(site_dirs) == 1
    assert not (site_dirs[0] / "current.json").exists(), (
        "failed run must not publish current.json"
    )


def test_locked_previous_build_does_not_block_followup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B157 repro: a follow-up must not WinError 5 on a locked previous build.

    The original bug: a live preview held a Windows lock on a native
    ``.node`` binary under ``node_modules``, and the in-place rebuild's
    ``copy_starter()`` tried to ``shutil.rmtree`` that exact directory on
    lockfile drift -> ``PermissionError: [WinError 5]``. With immutable
    builds the follow-up writes into a brand-new ``builds/<buildId>/`` and
    never touches the previous build, so the lock is irrelevant.
    """
    import scripts.build_site as build_site

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generated_dir = tmp_path / "generated"
    runs_dir = tmp_path / "runs"

    target_v1, _ = build_site.build(
        PAINTER_PALMA, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )

    # Emulate the live preview's lock: a native .node binary plus a drifted
    # lockfile inside the first build (the exact B157 trigger).
    swc_dir = target_v1 / "node_modules" / "@next" / "swc-win32-x64-msvc"
    swc_dir.mkdir(parents=True)
    locked = swc_dir / "next-swc.win32-x64-msvc.node"
    locked.write_bytes(b"\x00fake-native-binary\x00")
    (target_v1 / "package-lock.json").write_text(
        '{"lockfileVersion": 3, "drifted": true}', encoding="utf-8"
    )

    handle = locked.open("rb")  # holds a Windows file lock for the build below
    try:
        target_v2, _ = build_site.build(
            PAINTER_PALMA, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
        )
    finally:
        handle.close()

    # Follow-up built into a NEW immutable dir; the locked previous build is
    # left fully intact -> no copy_starter rmtree, no WinError 5.
    assert target_v2 != target_v1
    assert target_v2.parent == target_v1.parent  # both under <site>/builds/
    assert locked.is_file(), "the locked previous build must be left untouched"
    assert locked.read_bytes() == b"\x00fake-native-binary\x00"


# ---------------------------------------------------------------------------
# cleanup_flat_layout (B157 level 4, flat-layout cleanup)
# ---------------------------------------------------------------------------


def _make_flat_layout_site(site_dir: Path) -> None:
    """Materialise a site root as it looked under the pre-immutable flat layout."""
    site_dir.mkdir(parents=True)
    (site_dir / ".next").mkdir()
    (site_dir / ".next" / "build-manifest.json").write_text("{}", encoding="utf-8")
    (site_dir / "node_modules").mkdir()
    (site_dir / "node_modules" / "keep.txt").write_text("x", encoding="utf-8")
    (site_dir / "app").mkdir()
    (site_dir / "app" / "page.tsx").write_text("export default null", encoding="utf-8")
    (site_dir / "package.json").write_text('{"name":"flat"}', encoding="utf-8")
    (site_dir / "package-lock.json").write_text('{"lockfileVersion":3}', encoding="utf-8")


def test_cleanup_flat_layout_removes_legacy_artefacts_keeps_pointer_and_builds(
    tmp_path: Path,
) -> None:
    from packages.generation.build.immutable_builds import (
        BUILDS_DIRNAME,
        POINTER_FILENAME,
    )
    from scripts.build_site import cleanup_flat_layout

    site_dir = tmp_path / "site"
    _make_flat_layout_site(site_dir)
    # The immutable world's two survivors: builds/ and current.json.
    (site_dir / BUILDS_DIRNAME).mkdir()
    (site_dir / BUILDS_DIRNAME / "20260531T184500Z").mkdir()
    (site_dir / POINTER_FILENAME).write_text("{}", encoding="utf-8")

    removed = cleanup_flat_layout(
        site_dir, keep={BUILDS_DIRNAME, POINTER_FILENAME}
    )

    # Legacy flat artefacts are gone.
    assert not (site_dir / ".next").exists()
    assert not (site_dir / "node_modules").exists()
    assert not (site_dir / "app").exists()
    assert not (site_dir / "package.json").exists()
    assert not (site_dir / "package-lock.json").exists()
    # The immutable build dir and the pointer survive untouched.
    assert (site_dir / BUILDS_DIRNAME / "20260531T184500Z").is_dir()
    assert (site_dir / POINTER_FILENAME).is_file()
    assert set(removed) == {
        ".next",
        "node_modules",
        "app",
        "package.json",
        "package-lock.json",
    }


def test_cleanup_flat_layout_is_noop_on_fresh_immutable_site(tmp_path: Path) -> None:
    from packages.generation.build.immutable_builds import (
        BUILDS_DIRNAME,
        POINTER_FILENAME,
    )
    from scripts.build_site import cleanup_flat_layout

    site_dir = tmp_path / "site"
    (site_dir / BUILDS_DIRNAME / "20260531T184500Z").mkdir(parents=True)
    (site_dir / POINTER_FILENAME).write_text("{}", encoding="utf-8")

    removed = cleanup_flat_layout(
        site_dir, keep={BUILDS_DIRNAME, POINTER_FILENAME}
    )

    assert removed == []
    assert (site_dir / BUILDS_DIRNAME / "20260531T184500Z").is_dir()
    assert (site_dir / POINTER_FILENAME).is_file()


def test_cleanup_flat_layout_missing_dir_returns_empty(tmp_path: Path) -> None:
    from scripts.build_site import cleanup_flat_layout

    assert cleanup_flat_layout(tmp_path / "nope", keep={"builds", "current.json"}) == []


def test_cleanup_flat_layout_skips_locked_artefact_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A locked/unremovable flat artefact must be skipped, not crash the build.

    Simulates the Windows ``WinError 5`` (a live preview still holding the old
    flat ``.next``/``node_modules`` open) by making ``shutil.rmtree`` raise for
    one directory. Cleanup must keep going and remove the rest.
    """
    import scripts.build_site as build_site

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / ".next").mkdir()
    (site_dir / "app").mkdir()
    (site_dir / "app" / "page.tsx").write_text("x", encoding="utf-8")

    real_rmtree = build_site.shutil.rmtree

    def _flaky_rmtree(path, *args, **kwargs):
        if Path(path).name == ".next":
            raise PermissionError("[WinError 5] locked .node binary")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(build_site.shutil, "rmtree", _flaky_rmtree)

    removed = build_site.cleanup_flat_layout(site_dir, keep=set())

    # The locked dir is left behind; the rest is cleaned; no exception bubbled.
    assert (site_dir / ".next").exists()
    assert not (site_dir / "app").exists()
    assert removed == ["app"]  # only the removable entry is reported


def test_build_shippable_status_cleans_flat_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shippable build must reclaim legacy flat-layout artefacts in the root.

    Pre-seeds the site root with pre-immutable flat-layout files, runs a build
    that lands ``ok`` (so the pointer swaps), and asserts the flat artefacts are
    gone while ``builds/`` and ``current.json`` remain.
    """
    generated_dir = tmp_path / "generated"
    # painter-palma is the dossier built by _build_with_forced_status.
    site_dir = generated_dir / "painter-palma"
    _make_flat_layout_site(site_dir)

    target, _run_dir = _build_with_forced_status("ok", tmp_path, monkeypatch)
    assert target.parent.parent == site_dir  # built under <site>/builds/<id>

    assert (site_dir / "builds").is_dir()
    assert (site_dir / "current.json").is_file()
    assert not (site_dir / ".next").exists()
    assert not (site_dir / "node_modules").exists()
    assert not (site_dir / "app").exists()
    assert not (site_dir / "package-lock.json").exists()
    # The new immutable build still resolves via the pointer.
    assert read_active_build_dir(site_dir) == target


def test_build_skipped_does_not_clean_flat_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skipped run never swaps the pointer, so it must NOT touch flat artefacts.

    Removing the flat ``.next`` before a pointer exists would strip the preview
    resolver's only fallback for a site that has not yet published an immutable
    build.
    """
    import scripts.build_site as build_site

    generated_dir = tmp_path / "generated"
    site_dir = generated_dir / "painter-palma"
    _make_flat_layout_site(site_dir)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    build_site.build(
        PAINTER_PALMA,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=generated_dir,
    )

    assert not (site_dir / "current.json").exists()
    # Flat fallback artefacts must survive an unshippable (skipped) run.
    assert (site_dir / ".next").exists()
    assert (site_dir / "node_modules").exists()


# ---------------------------------------------------------------------------
# Structural lock: Viewser preview resolver (no TS runner in repo)
# ---------------------------------------------------------------------------


def test_preview_server_resolves_active_build_with_legacy_fallback() -> None:
    """local-preview-server.ts must resolve the pointer build, then fall back.

    Locks the B157 level 4 contract structurally:
      - a resolver reads current.json (readActiveBuildDir),
      - a resolveActivePreviewDir prefers the pointed build but falls back to
        the legacy flat <siteRoot>/.next layout,
      - doStartPreviewServer runs `next start` in the resolved dir.
    """
    source = LOCAL_PREVIEW_SERVER.read_text(encoding="utf-8")

    assert "function readActiveBuildDir(" in source, (
        "local-preview-server.ts must define readActiveBuildDir (mirror of "
        "immutable_builds.read_active_build_dir) so preview honours the "
        "current.json pointer."
    )
    assert 'path.join(siteRoot, "current.json")' in source, (
        "readActiveBuildDir must read <siteRoot>/current.json."
    )
    assert "function resolveActivePreviewDir(" in source, (
        "local-preview-server.ts must define resolveActivePreviewDir to pick "
        "the build directory `next start` runs in."
    )
    assert 'existsSync(path.join(siteRoot, ".next"))' in source, (
        "resolveActivePreviewDir must keep the legacy flat-layout fallback "
        "(<siteRoot>/.next) for sites built before level 4."
    )
    assert "const siteDir = resolveActivePreviewDir(siteRoot)" in source, (
        "doStartPreviewServer must resolve the preview dir via "
        "resolveActivePreviewDir (pointer + legacy fallback) before spawning "
        "next start."
    )


def test_build_runner_posix_tree_kills_build_process() -> None:
    """build-runner.ts must POSIX tree-kill build_site.py + its descendants.

    Locks the B157 follow-up "POSIX tree-kill" contract structurally (no TS
    runner in repo):
      - build_site.py is spawned in its own process group on POSIX
        (``detached: process.platform !== "win32"``),
      - a build-specific tree-killer signals the whole group via the NEGATIVE
        pid (``process.kill(-child.pid, ...)``) so npm/next grandchildren die
        too, instead of the direct-child-only ``child.kill`` that leaked them,
      - the timeout path uses that tree-killer for both SIGTERM and SIGKILL.
    """
    source = BUILD_RUNNER.read_text(encoding="utf-8")

    assert 'detached: process.platform !== "win32"' in source, (
        "build_site.py must be spawned detached on POSIX so it leads its own "
        "process group and a killpg can reach its npm/next descendants."
    )
    assert "function killBuildProcessTree(" in source, (
        "build-runner.ts must define killBuildProcessTree for the build process "
        "tree-kill (POSIX killpg + Windows taskkill)."
    )
    assert "process.kill(-child.pid" in source, (
        "killBuildProcessTree must signal the NEGATIVE pid (process group / "
        "killpg) on POSIX so python's npm/next descendants are killed too."
    )
    assert 'void killBuildProcessTree(child, "SIGTERM")' in source, (
        "the build timeout must escalate via killBuildProcessTree (SIGTERM)."
    )
    assert 'void killBuildProcessTree(child, "SIGKILL")' in source, (
        "the build timeout must escalate via killBuildProcessTree (SIGKILL)."
    )
