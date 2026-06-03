"""Tests for the read-only Context Assembler (KÖR-7a).

These lock the kor-7a "Definition of done":
- Every level returns the content it is supposed to and **respects its
  character cap** (``charCount <= charBudget`` always holds).
- ``external_reference`` is behind a permission gate (no fetch tool is
  called without the grant).
- The assembler performs **no writes**, creates **no run**, and starts **no
  build/preview** - ``preview_dom`` only reads an already-captured snapshot.

Fixtures live under ``tmp_path`` so the canonical ``data/`` tree is never
touched; the real scaffolds / dossiers / capability-map are read read-only
from the repo (they are static input, like the router tests read them).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.context import (  # noqa: E402
    DEFAULT_BUDGETS,
    AssembledContext,
    ContextPaths,
    PriorContext,
    ReferencePermission,
    assemble_artifacts,
    assemble_artifacts_plus_sections,
    assemble_component_registry,
    assemble_context,
    assemble_external_reference,
    assemble_manifest,
    assemble_none,
    assemble_preview_dom,
    assemble_project_dna,
    assemble_selected_files,
)
from packages.generation.orchestration.context.sources import sha256_bytes  # noqa: E402

FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "blueprints" / "elektriker-malmo.blueprint.json"
)
RUN_ID = "run-elektriker-malmo"
SITE_ID = "elektriker-malmo"
SCAFFOLD_ID = "local-service-business"


def _meta() -> dict:
    return {
        "projectId": "proj-elektriker-123",
        "version": 2,
        "mode": "followup",
        "siteId": SITE_ID,
        "originalPrompt": "Hemsida för en elektriker i Malmö.",
        "scaffoldId": SCAFFOLD_ID,
        "variantId": "nordic-trust",
        "briefSource": "mock-no-key",
        "projectDna": {
            "schemaVersion": 1,
            "createdAtVersion": 1,
            "tagline": {
                "value": "Trygg elektriker i Malmö",
                "lastUpdatedVersion": 1,
                "source": "brief",
            },
            "followUpIntent": {"id": "no-semantic-change"},
        },
    }


@pytest.fixture
def env(tmp_path: Path):
    """Write the run artefakts + prompt-inputs sidecar into a tmp sandbox.

    Returns ``(paths, tmp_path, fixture)``. The fixture also snapshots the set
    of paths that exist *after* setup so a test can assert the assembler added
    nothing.
    """
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    runs = tmp_path / "runs"
    run_dir = runs / RUN_ID
    run_dir.mkdir(parents=True)
    (run_dir / "site-brief.json").write_text(
        json.dumps(fixture["siteBrief"]), encoding="utf-8"
    )
    (run_dir / "site-plan.json").write_text(json.dumps(fixture["sitePlan"]), encoding="utf-8")
    (run_dir / "generation-package.json").write_text(
        json.dumps(fixture["generationPackage"]), encoding="utf-8"
    )

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir(parents=True)
    (prompt_inputs / f"{SITE_ID}.meta.json").write_text(json.dumps(_meta()), encoding="utf-8")

    paths = ContextPaths(
        repoRoot=REPO_ROOT,
        runsDir=runs,
        promptInputsDir=prompt_inputs,
    )
    return paths, tmp_path, fixture


def _make_generated_files(paths: ContextPaths) -> Path:
    """Create a small generated-files/ tree inside the run sandbox."""
    gen = paths.runs / RUN_ID / "generated-files"
    (gen / "app").mkdir(parents=True)
    (gen / "app" / "page.tsx").write_text(
        "export default function Page() {\n  return <main>Hej</main>;\n}\n", encoding="utf-8"
    )
    (gen / "app" / "layout.tsx").write_text(
        "export default function Layout() {\n  return null;\n}\n", encoding="utf-8"
    )
    (gen / "package.json").write_text(
        json.dumps({"name": "site", "version": "0.0.0"}), encoding="utf-8"
    )
    return gen


def _all_paths(root: Path) -> set[Path]:
    return set(root.rglob("*"))


# ---------------------------------------------------------------------------
# none
# ---------------------------------------------------------------------------


def test_none_is_empty_and_zero_budget():
    ctx = assemble_none()
    assert isinstance(ctx, AssembledContext)
    assert ctx.contextLevel == "none"
    assert ctx.payload == {}
    assert ctx.charBudget == 0
    assert ctx.charCount == 0
    assert ctx.truncated is False


# ---------------------------------------------------------------------------
# project_dna
# ---------------------------------------------------------------------------


def test_project_dna_returns_identity_and_dna(env):
    paths, _tmp, _fixture = env
    ctx = assemble_project_dna(SITE_ID, paths=paths)
    assert ctx.contextLevel == "project_dna"
    assert ctx.siteId == SITE_ID
    assert ctx.payload["projectId"] == "proj-elektriker-123"
    assert ctx.payload["version"] == 2
    assert ctx.payload["scaffoldId"] == SCAFFOLD_ID
    assert ctx.payload["variantId"] == "nordic-trust"
    assert ctx.payload["projectDna"]["tagline"]["value"] == "Trygg elektriker i Malmö"
    # Nothing more than the level requires: no run artefakts leaked in.
    assert "siteBrief" not in ctx.payload
    assert ctx.charCount <= ctx.charBudget


def test_project_dna_missing_meta_returns_note_and_creates_nothing(env):
    paths, tmp_path, _fixture = env
    before = _all_paths(tmp_path)
    ctx = assemble_project_dna("ghost-site", paths=paths)
    assert ctx.payload == {}
    assert ctx.notes and "ghost-site" in ctx.notes[0]
    assert _all_paths(tmp_path) == before


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_artifacts_returns_three_artifacts(env):
    paths, _tmp, fixture = env
    ctx = assemble_artifacts(RUN_ID, paths=paths)
    assert ctx.contextLevel == "artifacts"
    assert ctx.runId == RUN_ID
    assert ctx.payload["siteBrief"]["runId"] == RUN_ID
    assert ctx.payload["sitePlan"]["scaffoldId"] == SCAFFOLD_ID
    assert ctx.payload["generationPackage"]["engineMode"] == "init"
    assert ctx.truncated is False
    assert ctx.charCount <= ctx.charBudget


def test_artifacts_missing_run_returns_note_and_creates_nothing(env):
    paths, tmp_path, _fixture = env
    before = _all_paths(tmp_path)
    ctx = assemble_artifacts("does-not-exist", paths=paths)
    assert ctx.payload == {}
    assert ctx.notes
    # The ghost run directory must not be created just to read it.
    assert not (paths.runs / "does-not-exist").exists()
    assert _all_paths(tmp_path) == before


def test_artifacts_partial_missing_is_noted(env):
    paths, _tmp, _fixture = env
    (paths.runs / RUN_ID / "generation-package.json").unlink()
    ctx = assemble_artifacts(RUN_ID, paths=paths)
    assert "siteBrief" in ctx.payload
    assert "sitePlan" in ctx.payload
    assert "generationPackage" not in ctx.payload
    assert any("generation-package.json" in n for n in ctx.notes)


# ---------------------------------------------------------------------------
# artifacts_plus_sections
# ---------------------------------------------------------------------------


def test_artifacts_plus_sections_includes_section_map(env):
    paths, _tmp, _fixture = env
    ctx = assemble_artifacts_plus_sections(RUN_ID, paths=paths)
    assert ctx.contextLevel == "artifacts_plus_sections"
    assert "sitePlan" in ctx.payload
    # Raw scaffold sections.json is surfaced...
    assert "home" in ctx.payload["sections"]
    # ...plus the ordinal->sectionId projection the router (kor-6a) consumes.
    route_sections = ctx.payload["routeSections"]
    assert route_sections["home"][0] == "hero"
    assert route_sections["home"][1] == "service-summary"  # "andra sektionen" -> ordinal 2
    assert set(route_sections.keys()) == {"home", "services", "contact"}
    assert ctx.charCount <= ctx.charBudget


def test_artifacts_plus_sections_scaffold_override(env):
    paths, _tmp, _fixture = env
    # Remove the plan so scaffold must come from the explicit override.
    (paths.runs / RUN_ID / "site-plan.json").unlink()
    ctx = assemble_artifacts_plus_sections(RUN_ID, scaffold_id=SCAFFOLD_ID, paths=paths)
    assert "sections" in ctx.payload
    assert "home" in ctx.payload["sections"]


# ---------------------------------------------------------------------------
# component_registry
# ---------------------------------------------------------------------------


def test_component_registry_lists_capabilities_and_dossiers(env):
    paths, _tmp, _fixture = env
    ctx = assemble_component_registry(paths=paths)
    assert ctx.contextLevel == "component_registry"
    cap_slugs = {c["capability"] for c in ctx.payload["capabilities"]}
    assert "faq-section" in cap_slugs
    assert "contact-form" in cap_slugs
    dossier_ids = {d["id"] for d in ctx.payload["dossiers"]}
    assert "faq-accordion" in dossier_ids
    # Compact projection: heavy fields are not carried.
    for d in ctx.payload["dossiers"]:
        assert "files" not in d
        assert "$schema" not in d
    assert ctx.charCount <= ctx.charBudget


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


def test_manifest_lists_files_with_sizes(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    ctx = assemble_manifest(RUN_ID, paths=paths)
    assert ctx.contextLevel == "manifest"
    listed = {f["path"] for f in ctx.payload["files"]}
    assert listed == {"app/page.tsx", "app/layout.tsx", "package.json"}
    for f in ctx.payload["files"]:
        assert isinstance(f["bytes"], int) and f["bytes"] > 0
        assert "content" not in f  # manifest is a listing, not content
    assert ctx.charCount <= ctx.charBudget


def test_manifest_suppresses_known_paths(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    prior = PriorContext(knownFiles={"package.json": "", "app/layout.tsx": ""})
    ctx = assemble_manifest(RUN_ID, prior=prior, paths=paths)
    listed = {f["path"] for f in ctx.payload["files"]}
    assert listed == {"app/page.tsx"}
    assert set(ctx.suppressed) == {"package.json", "app/layout.tsx"}


def test_manifest_missing_generated_files_is_empty(env):
    paths, tmp_path, _fixture = env
    before = _all_paths(tmp_path)
    ctx = assemble_manifest(RUN_ID, paths=paths)
    assert ctx.payload["files"] == []
    assert _all_paths(tmp_path) == before  # no generated-files/ created


# ---------------------------------------------------------------------------
# selected_files
# ---------------------------------------------------------------------------


def test_selected_files_returns_content_and_digest(env):
    paths, _tmp, _fixture = env
    gen = _make_generated_files(paths)
    ctx = assemble_selected_files(RUN_ID, ["app/page.tsx"], paths=paths)
    assert ctx.contextLevel == "selected_files"
    assert len(ctx.payload["files"]) == 1
    entry = ctx.payload["files"][0]
    assert entry["path"] == "app/page.tsx"
    assert "Hej" in entry["content"]
    raw = (gen / "app" / "page.tsx").read_bytes()
    assert entry["sha256"] == sha256_bytes(raw)
    assert entry["bytes"] == len(raw)
    assert ctx.charCount <= ctx.charBudget


def test_selected_files_suppresses_unchanged_by_digest(env):
    paths, _tmp, _fixture = env
    gen = _make_generated_files(paths)
    raw = (gen / "app" / "page.tsx").read_bytes()
    prior = PriorContext(knownFiles={"app/page.tsx": sha256_bytes(raw)})
    ctx = assemble_selected_files(RUN_ID, ["app/page.tsx"], prior=prior, paths=paths)
    assert ctx.payload["files"] == []
    assert ctx.suppressed == ["app/page.tsx"]


def test_selected_files_changed_file_is_not_suppressed(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    # Known path but a stale (wrong) digest -> content changed -> still returned.
    prior = PriorContext(knownFiles={"app/page.tsx": "0" * 64})
    ctx = assemble_selected_files(RUN_ID, ["app/page.tsx"], prior=prior, paths=paths)
    assert [f["path"] for f in ctx.payload["files"]] == ["app/page.tsx"]
    assert ctx.suppressed == []


def test_selected_files_rejects_path_traversal(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    # The site-brief.json sits one level above generated-files/ in the run dir.
    ctx = assemble_selected_files(RUN_ID, ["../site-brief.json"], paths=paths)
    assert ctx.payload["files"] == []
    assert any("sandbox" in n for n in ctx.notes)


def test_selected_files_missing_file_is_noted(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    ctx = assemble_selected_files(RUN_ID, ["app/nope.tsx"], paths=paths)
    assert ctx.payload["files"] == []
    assert any("app/nope.tsx" in n for n in ctx.notes)


# ---------------------------------------------------------------------------
# preview_dom  (never starts a preview)
# ---------------------------------------------------------------------------


def test_preview_dom_reads_inline_snapshot():
    ctx = assemble_preview_dom(route="/", snapshot="<main>Hej</main>")
    assert ctx.contextLevel == "preview_dom"
    assert ctx.payload["route"] == "/"
    assert ctx.payload["snapshot"] == "<main>Hej</main>"
    assert ctx.charCount <= ctx.charBudget


def test_preview_dom_reads_snapshot_path(tmp_path: Path):
    snap = tmp_path / "snapshot.html"
    snap.write_text("<body>captured</body>", encoding="utf-8")
    ctx = assemble_preview_dom(snapshot_path=str(snap))
    assert ctx.payload["snapshot"] == "<body>captured</body>"


def test_preview_dom_without_snapshot_does_not_start_preview(tmp_path: Path):
    before = _all_paths(tmp_path)
    ctx = assemble_preview_dom(route="/")
    assert "snapshot" not in ctx.payload
    assert any("does not start a preview" in n for n in ctx.notes)
    assert _all_paths(tmp_path) == before


def test_preview_dom_missing_snapshot_file_is_noted(tmp_path: Path):
    ctx = assemble_preview_dom(snapshot_path=str(tmp_path / "absent.html"))
    assert "snapshot" not in ctx.payload
    assert any("not found" in n for n in ctx.notes)


# ---------------------------------------------------------------------------
# external_reference  (permission gate)
# ---------------------------------------------------------------------------


def test_external_reference_denied_without_permission_makes_no_fetch():
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        return "SHOULD NOT BE CALLED"

    ctx = assemble_external_reference(
        "aftonbladet.se", permission=ReferencePermission(allow=False), fetch=fetch
    )
    assert ctx.permissionRequired is True
    assert ctx.permissionGranted is False
    assert calls == []  # the gate prevented the tool call
    assert "content" not in ctx.payload
    assert ctx.payload["url"] == "aftonbladet.se"


def test_external_reference_default_permission_is_denied():
    calls: list[str] = []

    ctx = assemble_external_reference("aftonbladet.se", fetch=lambda u: calls.append(u) or "x")
    assert ctx.permissionGranted is False
    assert calls == []


def test_external_reference_granted_calls_fetch_tool():
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        return "<clock>12:00</clock>"

    ctx = assemble_external_reference(
        "aftonbladet.se", permission=ReferencePermission(allow=True), fetch=fetch
    )
    assert ctx.permissionGranted is True
    assert calls == ["aftonbladet.se"]
    assert ctx.payload["content"] == "<clock>12:00</clock>"
    assert any("do not copy the exact design" in n for n in ctx.notes)


def test_external_reference_granted_but_no_tool_makes_no_io():
    ctx = assemble_external_reference(
        "aftonbladet.se", permission=ReferencePermission(allow=True), fetch=None
    )
    assert ctx.permissionGranted is True
    assert "content" not in ctx.payload
    assert any("no fetch tool" in n for n in ctx.notes)


def test_dispatch_external_reference_is_gated():
    calls: list[str] = []
    ctx = assemble_context(
        "external_reference",
        url="aftonbladet.se",
        fetch=lambda u: calls.append(u) or "x",
    )
    assert ctx.contextLevel == "external_reference"
    assert ctx.permissionGranted is False
    assert calls == []


# ---------------------------------------------------------------------------
# Character-cap invariant + truncation
# ---------------------------------------------------------------------------


def test_artifacts_tiny_budget_truncates_within_cap(env):
    paths, _tmp, _fixture = env
    ctx = assemble_artifacts(RUN_ID, paths=paths, budgets={"artifacts": 200})
    assert ctx.truncated is True
    assert ctx.charCount <= 200


def test_artifacts_plus_sections_tiny_budget_truncates_within_cap(env):
    paths, _tmp, _fixture = env
    ctx = assemble_artifacts_plus_sections(
        RUN_ID, paths=paths, budgets={"artifacts_plus_sections": 300}
    )
    assert ctx.truncated is True
    assert ctx.charCount <= 300


def test_component_registry_tiny_budget_truncates_within_cap(env):
    paths, _tmp, _fixture = env
    ctx = assemble_component_registry(paths=paths, budgets={"component_registry": 200})
    assert ctx.truncated is True
    assert ctx.charCount <= 200


def test_manifest_tiny_budget_truncates_within_cap(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    ctx = assemble_manifest(RUN_ID, paths=paths, budgets={"manifest": 40})
    assert ctx.truncated is True
    assert ctx.charCount <= 40


def test_selected_files_tiny_budget_clips_content_within_cap(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    ctx = assemble_selected_files(
        RUN_ID, ["app/page.tsx"], paths=paths, budgets={"selected_files": 120}
    )
    assert ctx.truncated is True
    assert ctx.charCount <= 120


def test_preview_dom_tiny_budget_clips_within_cap():
    ctx = assemble_preview_dom(snapshot="x" * 5000, budgets={"preview_dom": 100})
    assert ctx.truncated is True
    assert ctx.charCount <= 100


def test_external_reference_tiny_budget_clips_within_cap():
    ctx = assemble_external_reference(
        "aftonbladet.se",
        permission=ReferencePermission(allow=True),
        fetch=lambda _u: "y" * 5000,
        budgets={"external_reference": 150},
    )
    assert ctx.truncated is True
    assert ctx.charCount <= 150


def test_every_level_respects_its_char_budget_invariant(env):
    """The hard kor-7a invariant for every level, at default + tiny budgets."""
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    tiny = {level: 64 for level in DEFAULT_BUDGETS}

    def all_levels(budgets):
        return [
            assemble_none(),
            assemble_project_dna(SITE_ID, paths=paths, budgets=budgets),
            assemble_artifacts(RUN_ID, paths=paths, budgets=budgets),
            assemble_artifacts_plus_sections(RUN_ID, paths=paths, budgets=budgets),
            assemble_component_registry(paths=paths, budgets=budgets),
            assemble_manifest(RUN_ID, paths=paths, budgets=budgets),
            assemble_selected_files(RUN_ID, ["app/page.tsx"], paths=paths, budgets=budgets),
            assemble_preview_dom(snapshot="x" * 4000, budgets=budgets),
            assemble_external_reference(
                "aftonbladet.se",
                permission=ReferencePermission(allow=True),
                fetch=lambda _u: "z" * 4000,
                budgets=budgets,
            ),
        ]

    for budgets in (None, tiny):
        for ctx in all_levels(budgets):
            assert ctx.charCount <= ctx.charBudget, ctx.contextLevel


# ---------------------------------------------------------------------------
# Read-only: no writes, no run created, across the whole battery
# ---------------------------------------------------------------------------


def test_assembler_writes_nothing_across_all_levels(env):
    paths, tmp_path, _fixture = env
    _make_generated_files(paths)
    before = _all_paths(tmp_path)

    assemble_none()
    assemble_project_dna(SITE_ID, paths=paths)
    assemble_artifacts(RUN_ID, paths=paths)
    assemble_artifacts_plus_sections(RUN_ID, paths=paths)
    assemble_component_registry(paths=paths)
    assemble_manifest(RUN_ID, paths=paths)
    assemble_selected_files(RUN_ID, ["app/page.tsx", "app/layout.tsx"], paths=paths)
    assemble_preview_dom(snapshot="<main/>")
    assemble_external_reference(
        "aftonbladet.se", permission=ReferencePermission(allow=True), fetch=lambda _u: "x"
    )
    # Ghost runs/sites must not be created just to be read.
    assemble_context("artifacts", run_id="ghost", paths=paths)
    assemble_context("project_dna", site_id="ghost", paths=paths)

    assert _all_paths(tmp_path) == before


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_dispatch_routes_each_level(env):
    paths, _tmp, _fixture = env
    _make_generated_files(paths)
    assert assemble_context("none").contextLevel == "none"
    assert assemble_context("project_dna", site_id=SITE_ID, paths=paths).payload["version"] == 2
    assert "siteBrief" in assemble_context("artifacts", run_id=RUN_ID, paths=paths).payload
    aps = assemble_context("artifacts_plus_sections", run_id=RUN_ID, paths=paths)
    assert "routeSections" in aps.payload
    assert assemble_context("component_registry", paths=paths).payload["capabilities"]
    assert "files" in assemble_context("manifest", run_id=RUN_ID, paths=paths).payload
    sel = assemble_context("selected_files", run_id=RUN_ID, rel_paths=["app/page.tsx"], paths=paths)
    assert len(sel.payload["files"]) == 1
    assert assemble_context("preview_dom", snapshot="<i/>").payload["snapshot"] == "<i/>"


def test_dispatch_missing_identifier_is_noted_not_raised(env):
    paths, _tmp, _fixture = env
    for level, _arg in (
        ("project_dna", "site_id"),
        ("artifacts", "run_id"),
        ("artifacts_plus_sections", "run_id"),
        ("manifest", "run_id"),
        ("selected_files", "run_id"),
        ("external_reference", "url"),
    ):
        ctx = assemble_context(level, paths=paths)
        assert ctx.contextLevel == level
        assert ctx.payload == {}
        assert ctx.notes and "missing required" in ctx.notes[0]
