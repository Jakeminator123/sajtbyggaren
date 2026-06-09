"""Deterministic golden-path SMOKE baseline for the four core branches.

This is a NARROW smoke test, not a scorecard. The scoring/eval platform lives
in ``scripts/run_golden_path_eval.py`` (+ ``tests/test_golden_path_eval.py``),
and ``tests/test_llm_golden_path_smoke.py`` already locks the coarse v1 -> v2
follow-up artefakt contract for a single prompt. The gap this file fills is the
per-branch *routing matrix*: that each of the four baseline prompts deterministically
pins the expected ``scaffoldId`` / ``variantId`` / ``starterId``, emits the
scaffold-correct routes (incl. clinic-healthcare's ``/behandlingar`` +
``/kontakta-oss`` rather than the local-service slugs), generates the expected
``app/**/page.tsx`` files, lands a non-failing build/quality status, and records
the deterministic mock truth-fields (``briefSource = mock-no-key`` from the brief,
``planSource = pinned`` because the builder pins scaffold/variant from the
Project Input).

Mock-safe + Node-free: ``OPENAI_API_KEY`` is removed so ``briefModel`` /
``planningModel`` fall back to the deterministic mock paths, and ``build`` runs
with ``do_build=False`` so it never shells out to ``npm install`` /
``npm run build``. All artefakts land under ``tmp_path`` so the canonical
``data/runs/`` history is never touched.

The four prompts and their expected routing signals mirror the deterministic
``BASELINE_CASES`` in ``scripts/run_golden_path_eval.py``. If the deterministic
routing for a baseline prompt changes, update ``_BRANCHES`` here rather than
weakening the assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_site import build
from scripts.prompt_to_project_input import generate

# The deterministic mock truth-fields. The mock brief path stamps
# ``briefSource = mock-no-key``; the builder pins scaffold/variant from the
# Project Input, so ``produce_site_plan`` returns ``planSource = pinned``
# (it never touches planningModel on the build path).
_EXPECTED_BRIEF_SOURCE = "mock-no-key"
_EXPECTED_PLAN_SOURCE = "pinned"

# A build with ``do_build=False`` keeps the blocking typecheck / build-status
# checks skipped, so for a clean deterministic baseline the aggregate quality
# status is exactly ``ok`` (route-scan + policy-compliance pass; the two warning
# checks never lower it), and the run-level build status is the honest
# ``skipped`` (npm never ran). We assert the EXACT values rather than a tolerant
# set so this smoke actually protects route-generation: a future regression that
# made route-scan fail (-> quality ``degraded``) or that accidentally ran the
# build path (-> build ``ok``/``failed`` under do_build=False) must trip here
# instead of silently passing a loose membership check.
_EXPECTED_QUALITY_STATUS = "ok"
_EXPECTED_BUILD_STATUS = "skipped"


class _Branch:
    """One baseline prompt and its expected deterministic routing signals."""

    def __init__(
        self,
        *,
        site_id: str,
        prompt: str,
        scaffold_id: str,
        variant_id: str,
        starter_id: str,
        routes: tuple[str, ...],
    ) -> None:
        self.site_id = site_id
        self.prompt = prompt
        self.scaffold_id = scaffold_id
        self.variant_id = variant_id
        self.starter_id = starter_id
        self.routes = routes


# The prompts are the EXACT diacritic Swedish strings from the deterministic
# ``BASELINE_CASES`` in scripts/run_golden_path_eval.py ("för", "Malmö",
# "Göteborg", "frisörsalong", "säljer"). Mirroring them verbatim is the point of
# a golden-path smoke: business-type detection keys on the real prompt text, so
# an ASCII-folded prompt could mask a routing/language regression that only
# triggers on diacritics. This file is UTF-8 Python source, so the characters
# are safe here regardless of any shell encoding.
_BRANCHES: tuple[_Branch, ...] = (
    _Branch(
        site_id="electrician-malmo",
        prompt="Skapa en hemsida för en elektriker i Malmö.",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        starter_id="marketing-base",
        routes=("/", "/tjanster", "/om-oss", "/kontakt"),
    ),
    _Branch(
        site_id="salon-goteborg",
        prompt="Skapa en hemsida för en frisörsalong i Göteborg.",
        scaffold_id="local-service-business",
        variant_id="nordic-trust",
        starter_id="marketing-base",
        routes=("/", "/tjanster", "/om-oss", "/kontakt"),
    ),
    _Branch(
        site_id="naprapat-stockholm",
        prompt="Skapa en hemsida för en naprapatklinik i Stockholm.",
        scaffold_id="clinic-healthcare",
        variant_id="clinic-calm",
        starter_id="marketing-base",
        routes=("/", "/behandlingar", "/om-oss", "/kontakta-oss"),
    ),
    _Branch(
        site_id="ceramics-shop",
        prompt="Skapa en hemsida för en liten e-handel som säljer keramik.",
        scaffold_id="ecommerce-lite",
        variant_id="clean-store",
        starter_id="commerce-base",
        routes=("/", "/produkter", "/om-oss", "/kontakt"),
    ),
)

_BRANCH_IDS = tuple(branch.site_id for branch in _BRANCHES)


def _route_to_page_path(route: str) -> Path:
    """Map a route path to its expected ``app/**/page.tsx`` snapshot location."""

    if route == "/":
        return Path("app") / "page.tsx"
    parts = [part for part in route.split("/") if part]
    return Path("app", *parts, "page.tsx")


def _list_generated_routes(run_dir: Path) -> list[str]:
    """List routes from generated ``app/**/page.tsx`` files (mirrors the eval)."""

    app_dir = run_dir / "generated-files" / "app"
    if not app_dir.is_dir():
        return []
    routes: list[str] = []
    for page_file in sorted(app_dir.rglob("page.tsx")):
        if page_file.parent == app_dir:
            routes.append("/")
            continue
        rel = page_file.parent.relative_to(app_dir).parts
        routes.append("/" + "/".join(rel))
    return routes


def _build_branch(branch: _Branch, tmp_path: Path) -> Path:
    """Run prompt -> Project Input -> build for one branch, returning the run dir."""

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _pi, _meta, project_input_path, _meta_path = generate(
        branch.prompt,
        output_dir=prompt_inputs_dir,
        site_id=branch.site_id,
    )
    _target, run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        auto_prune=False,
    )
    return run_dir


@pytest.mark.tooling
@pytest.mark.parametrize("branch", _BRANCHES, ids=_BRANCH_IDS)
def test_golden_path_branch_smoke(
    branch: _Branch,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Each baseline prompt routes deterministically through the whole flow.

    Free prompt -> Project Input -> brief -> plan -> generation package ->
    generated files -> quality gate. The test pins:

    1. ``site-plan.json`` selects the branch's expected scaffold / variant /
       starter (deterministic mock routing).
    2. The generation package + generated-files snapshot carry the same
       scaffold/variant (no drift between plan and what was rendered).
    3. ``app/page.tsx`` plus the branch's expected route pages exist on disk,
       and the rendered route set equals the expected set exactly.
    4. ``quality-result.json`` status is exactly ``ok`` (route-scan +
       policy-compliance pass) and ``build-result.json`` status is exactly the
       honest ``skipped`` under ``do_build=False``; route-scan check is ok/skipped.
    5. ``briefSource = mock-no-key`` (brief) and ``planSource = pinned`` (plan)
       — the deterministic mock truth-fields.
    """

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    run_dir = _build_branch(branch, tmp_path)

    site_brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    site_plan = json.loads((run_dir / "site-plan.json").read_text(encoding="utf-8"))
    generation_package = json.loads(
        (run_dir / "generation-package.json").read_text(encoding="utf-8")
    )
    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    quality_result = json.loads(
        (run_dir / "quality-result.json").read_text(encoding="utf-8")
    )

    # 1. Deterministic scaffold/variant/starter routing.
    assert site_plan.get("scaffoldId") == branch.scaffold_id, (
        f"{branch.site_id}: expected scaffoldId {branch.scaffold_id!r}, got "
        f"{site_plan.get('scaffoldId')!r}. If the deterministic routing for "
        "this baseline prompt changed, update _BRANCHES rather than the assertion."
    )
    assert site_plan.get("variantId") == branch.variant_id, (
        f"{branch.site_id}: expected variantId {branch.variant_id!r}, got "
        f"{site_plan.get('variantId')!r}."
    )
    assert site_plan.get("starterId") == branch.starter_id, (
        f"{branch.site_id}: expected starterId {branch.starter_id!r}, got "
        f"{site_plan.get('starterId')!r}."
    )

    # 2. The generation package agrees with the plan (no plan/render drift).
    assert generation_package.get("scaffoldId") == branch.scaffold_id
    assert generation_package.get("variantId") == branch.variant_id

    # 3. Generated files: home page + the expected route pages exist, and the
    #    rendered route set equals the expected set exactly.
    snapshot = run_dir / "generated-files"
    home_page = snapshot / "app" / "page.tsx"
    assert home_page.is_file(), (
        f"{branch.site_id}: missing generated home page at {home_page}. The "
        "snapshot must contain app/page.tsx so the preview can render."
    )
    for route in branch.routes:
        page_path = snapshot / _route_to_page_path(route)
        assert page_path.is_file(), (
            f"{branch.site_id}: missing generated page for route {route!r} at "
            f"{page_path}."
        )
    generated_routes = set(_list_generated_routes(run_dir))
    missing_routes = set(branch.routes) - generated_routes
    assert not missing_routes, (
        f"{branch.site_id}: expected routes {sorted(missing_routes)} are missing "
        f"from the generated route set {sorted(generated_routes)}. (Starters may "
        "ship extra routes, so this is a subset check, not exact equality.)"
    )

    # 4. Honest, EXACT build + quality status under do_build=False.
    assert build_result.get("status") == _EXPECTED_BUILD_STATUS, (
        f"{branch.site_id}: build-result.json status was "
        f"{build_result.get('status')!r}; expected exactly "
        f"{_EXPECTED_BUILD_STATUS!r} under do_build=False (npm never ran). A "
        "different value means the build path ran or the status was mis-stamped."
    )
    assert quality_result.get("status") == _EXPECTED_QUALITY_STATUS, (
        f"{branch.site_id}: quality-result.json status was "
        f"{quality_result.get('status')!r}; expected exactly "
        f"{_EXPECTED_QUALITY_STATUS!r}. A ``degraded`` here means a blocking "
        "check (route-scan / policy-compliance) failed - exactly the "
        "route-generation regression this smoke must catch."
    )
    # Belt-and-suspenders: the route-scan check itself must be EXACTLY ok. This
    # smoke relies on route-scan for the export-default verification, and
    # run_route_scan_check has no skip branch (it returns ok or failed), so
    # accepting "skipped" would only ever mask a future regression that
    # accidentally stopped running the check (Codex review fix).
    checks_by_name = {
        c.get("name"): c.get("status")
        for c in (quality_result.get("checks") or [])
        if isinstance(c, dict)
    }
    assert checks_by_name.get("route-scan") == "ok", (
        f"{branch.site_id}: route-scan check was "
        f"{checks_by_name.get('route-scan')!r}; expected exactly 'ok'."
    )

    # 5. Deterministic mock truth-fields.
    assert site_brief.get("briefSource") == _EXPECTED_BRIEF_SOURCE, (
        f"{branch.site_id}: expected briefSource {_EXPECTED_BRIEF_SOURCE!r} "
        f"(mock path), got {site_brief.get('briefSource')!r}."
    )
    assert site_plan.get("planSource") == _EXPECTED_PLAN_SOURCE, (
        f"{branch.site_id}: expected planSource {_EXPECTED_PLAN_SOURCE!r} "
        f"(builder pins scaffold/variant), got {site_plan.get('planSource')!r}."
    )
