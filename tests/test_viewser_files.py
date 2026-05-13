"""Smoke tests for the Viewser MVP file layout and scope discipline."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
NAMING_PATH = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"


@pytest.mark.tooling
def test_viewser_expected_files_exist() -> None:
    expected = [
        "package.json",
        "app/layout.tsx",
        "app/page.tsx",
        "app/api/chat/route.ts",
        "app/api/build/route.ts",
        "app/api/runs/route.ts",
        "app/api/runs/[runId]/files/route.ts",
        # Builder UX MVP: artefact bundle endpoint feeds RunDetailsPanel
        # the four canonical Engine Run artefakter in one round-trip.
        "app/api/runs/[runId]/artifacts/route.ts",
        # Prompt-till-sajt MVP v1: free-prompt -> Project Input -> build.
        "app/api/prompt/route.ts",
        "components/chat-panel.tsx",
        "components/viewer-panel.tsx",
        "components/token-meter.tsx",
        "components/project-input-picker.tsx",
        "components/run-history.tsx",
        # Builder UX MVP: 5-section pedagogical render of build/quality/
        # repair/codegen/models with defensive fallbacks for older runs.
        "components/run-details-panel.tsx",
        # Prompt-till-sajt MVP v1: prompt textarea + status panel that
        # wires through /api/prompt to runBuild.
        "components/prompt-builder.tsx",
        "lib/openai.ts",
        "lib/build-runner.ts",
        "lib/localhost-guard.ts",
        "lib/project-inputs.ts",
        "lib/prompt-runner.ts",
        "lib/runs.ts",
        "lib/stackblitz-files.ts",
        ".env.example",
    ]
    missing = [path for path in expected if not (VIEWSER_DIR / path).exists()]
    assert not missing, f"Missing viewser files: {missing}"


@pytest.mark.tooling
def test_viewser_legacy_dossier_picker_removed() -> None:
    """Operator-mentalmodellen kräver Project Input - inte Dossier - picker."""
    assert not (VIEWSER_DIR / "components" / "dossier-picker.tsx").exists()
    assert not (VIEWSER_DIR / "lib" / "dossiers.ts").exists()


@pytest.mark.tooling
def test_viewser_env_file_is_not_committed() -> None:
    assert not (VIEWSER_DIR / ".env").exists()
    assert not (VIEWSER_DIR / ".env.local").exists()


@pytest.mark.tooling
def test_viewser_env_example_documents_localhost_and_token_cap() -> None:
    """Token cap och localhost-guard MÅSTE vara dokumenterade i .env.example."""
    text = (VIEWSER_DIR / ".env.example").read_text(encoding="utf-8")
    assert "VIEWSER_MAX_CHAT_TOKENS" in text
    assert "VIEWSER_ALLOW_NON_LOCALHOST" in text


@pytest.mark.tooling
def test_viewser_api_routes_call_localhost_guard() -> None:
    """Varje API route MÅSTE kalla localhost-guard innan den gör arbete."""
    routes = [
        "app/api/chat/route.ts",
        "app/api/build/route.ts",
        "app/api/runs/route.ts",
        "app/api/runs/[runId]/files/route.ts",
        "app/api/runs/[runId]/artifacts/route.ts",
        "app/api/prompt/route.ts",
    ]
    for route in routes:
        text = (VIEWSER_DIR / route).read_text(encoding="utf-8")
        assert "assertLocalhost" in text, f"{route} saknar localhost-guard"


@pytest.mark.tooling
def test_build_runner_whitelists_dossier_path_overrides() -> None:
    """Prompt-till-sajt MVP v1 låter API-routen `/api/prompt` skicka in en
    absolut dossier-path direkt till `runBuild`. Det är medvetet, men en
    crafted payload får ALDRIG kunna peka build_site.py mot en godtycklig
    fil utanför `examples/` eller `data/prompt-inputs/`. Lås whitelist-
    funktionen så en framtida refactor inte tar bort guarden."""
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    assert "ALLOWED_DOSSIER_ROOTS" in text, (
        "build-runner.ts saknar ALLOWED_DOSSIER_ROOTS-whitelist för "
        "dossier-path overrides från prompt-flödet."
    )
    assert "examples" in text and "prompt-inputs" in text, (
        "build-runner.ts whitelisten måste täcka både examples/ och "
        "data/prompt-inputs/ - de två rötter där en Project Input får ligga."
    )
    assert "assertDossierPathAllowed" in text, (
        "build-runner.ts saknar assertDossierPathAllowed-anrop som "
        "validerar override-paths innan spawn av build_site.py."
    )


@pytest.mark.tooling
def test_prompt_route_returns_400_for_zod_validation_errors() -> None:
    """Audit fynd 1: ogiltig payload (tom prompt, för lång prompt, fel
    typ) är ett klient-/valideringsfel, inte serverfel. Före fixen
    fångade en bred try alla fel som 500, vilket gjorde API-kontraktet
    missvisande och försvårade felsökning.

    Lås att routen särskiljer ZodError -> 400 från övriga fel -> 500
    så framtida refactor inte återinför den breda 500-grenen.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "instanceof z.ZodError" in text, (
        "/api/prompt måste skilja Zod-valideringsfel från serverfel via "
        "`error instanceof z.ZodError` och returnera 400 för validering, "
        "inte den breda 500-grenen."
    )
    assert re.search(r"status:\s*400", text), (
        "/api/prompt saknar `status: 400`-svar för Zod-validering. "
        "Klient-/valideringsfel ska aldrig returneras som 500."
    )


@pytest.mark.tooling
def test_prompt_payload_schema_trims_whitespace_before_length_check() -> None:
    """Audit fynd 2: en whitespace-only prompt (`"   "`) passerar
    `.string().min(1)` men trimmades senare i `runPromptToProjectInput`
    och kastades som "Prompt får inte vara tom." vilket sedan blev 500.
    UI:n stoppar normalfallet men API-gränsen gjorde inte det.

    Lås att schemat trimmar FÖRE min/max så whitespace-only fångas vid
    API-gränsen och returneras som 400 (via ZodError).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"z\s*\.\s*string\(\)\s*\.\s*trim\(\)\s*\.\s*min\(\s*1",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "PromptPayloadSchema.prompt måste vara `z.string().trim().min(1)..."
        ".max(4000)` så whitespace-only payloads fångas av `.min(1)` "
        "EFTER trim. Utan trim slipper `' '` igenom till helpern."
    )


@pytest.mark.tooling
def test_prompt_route_passes_dossier_override_to_run_build() -> None:
    """Prompt-flödet får inte falla tillbaka till `runBuild(siteId)` utan
    dossier-path override - det skulle leta i `examples/` istället för
    `data/prompt-inputs/` och misslyckas med 'Project Input saknas'.
    Lås kontraktet att routen alltid skickar in helper.dossierPath."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "runBuild(helper.siteId, helper.dossierPath)" in text, (
        "/api/prompt måste anropa runBuild med BÅDE siteId och "
        "helper.dossierPath. Utan path-override hamnar lookupen i "
        "examples/ och det prompt-genererade Project Inputet hittas "
        "inte (det ligger i data/prompt-inputs/)."
    )


@pytest.mark.tooling
def test_run_details_panel_handles_missing_artefakter_defensively() -> None:
    """B38 / Builder UX MVP: ÄLDRE runs (pre-Sprint 3A) saknar
    quality-result.json + repair-result.json, och dev_generate-runs
    saknar routes / npmSteps / generatedFilesDir på top-level. UI:t
    måste rendera dessa fall som "saknas i äldre run" / "ej spårad än"
    istället för att krascha eller visa odefinierade fält som rå JSON.

    Locking the fallback strings here makes accidental regression
    surface as a string-mismatch rather than a runtime crash in the
    browser.
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )
    expected_fallbacks = [
        "saknas i äldre run",
        "ej spårad än",
        "saknas i denna run",
    ]
    for fallback in expected_fallbacks:
        assert fallback in panel_text, (
            f"RunDetailsPanel saknar defensiv fallback-text {fallback!r}. "
            "UI:t måste vara läsbart för pre-Sprint-3A runs och dev_generate-mocks."
        )


@pytest.mark.tooling
def test_chat_panel_marks_prompt_as_experimental() -> None:
    """Builder UX MVP scope: free-form prompt får visas men ska inte
    framstå som primary path. Project Input + Build är den stabila
    vägen tills en separat sprint kopplar promptens output till
    run-flödet.
    """
    text = (VIEWSER_DIR / "components" / "chat-panel.tsx").read_text(encoding="utf-8")
    assert "experimentell" in text.lower() or "experimental" in text.lower(), (
        "Promptfältet ska visa pedagogisk text om att det är experimentellt "
        "och inte påverkar run-flödet i denna runda."
    )


@pytest.mark.tooling
def test_build_runner_returns_structured_failure_instead_of_throwing() -> None:
    """B40: when scripts/build_site.py exits 1 because npm install /
    npm run build failed, it STILL writes the canonical artefakter
    (build-result.json with status=failed, plus quality-result.json +
    repair-result.json + the generated-files/ snapshot) per the
    Builder MVP contract. The dev wrapper used to throw on any
    non-zero exit, which dropped the runId on the floor and forced
    /api/build to return 500 with no way for the UI to surface a
    failed run. The defensive path now reads build-result.json from
    disk and returns it as a normal result so the Run History entry
    shows up with status=failed and the RunDetailsPanel can render
    the four artefakter for diagnosis. Only when there's no runId
    AND no structured artefakt does the wrapper throw.
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")

    # B40: the failure branch must read build-result.json from disk so
    # the UI sees a structured failed run instead of bare 500.
    assert re.search(r"exitCode\s*!==\s*0", text), (
        "build-runner.ts saknar exitCode !== 0-gren - hela B40-kontraktet "
        "hänger på den."
    )
    assert "readBuildResult" in text, (
        "build-runner.ts måste läsa build-result.json från disk i failure-"
        "grenen så failed runs når UI:t med strukturerad data istället för "
        "bare 500."
    )

    # B42 (post-review-2): the failure path must NOT fall back to
    # detectLatestRunIdByMtime() - that would return a PRIOR run-dir
    # whenever build_site.py crashes BEFORE printing `runId:`,
    # mislabeling someone else's run as the current failed build.
    # Only the success path may use the mtime fallback (where
    # exitCode === 0 guarantees the latest dir IS this build's).
    failure_block = re.search(
        r"if\s*\(\s*exitCode\s*!==\s*0\s*\)\s*\{[\s\S]*?\n\s{0,4}\}",
        text,
        re.MULTILINE,
    )
    assert failure_block, (
        "Kunde inte hitta `if (exitCode !== 0) { ... }`-blocket i "
        "build-runner.ts."
    )
    assert "detectLatestRunIdByMtime" not in failure_block.group(0), (
        "build-runner.ts failure-grenen får inte använda "
        "detectLatestRunIdByMtime() som fallback. När build_site.py "
        "kraschar FÖRE `print(runId:)` returnerar mtime-fallbacken en "
        "tidigare run och felaktigt märker den som denna build:s "
        "strukturerade failure (B42 post-review-2 fynd)."
    )


@pytest.mark.tooling
def test_page_useeffect_guards_success_path_with_cancelled_check() -> None:
    """Race-condition guard for app/page.tsx initial fetch:
    the success path of the useEffect-IIFE used to call refreshRuns()
    which itself ran setRuns / setProjectInputs / setSelectedRunId /
    setSelectedSiteId / setStatusText UNCONDITIONALLY after its own
    await. The cancelled-flag on the catch branch then only protected
    error-path stale updates, not success-path stale updates. If the
    component unmounted (or the dependency array changed) while
    /api/runs was in flight, a successful resolution arriving after
    unmount still wrote five setState calls onto a stale tree.

    The fix splits the call into a pure ``fetchRuns`` data fetcher
    and a separate ``applyRunsData`` state mutator, with the
    cancelled-guard sitting between them. Source-lock that ordering
    so a future refactor cannot collapse the two back into one
    function and silently drop the guard.
    """
    text = (VIEWSER_DIR / "app" / "page.tsx").read_text(encoding="utf-8")

    # Look for ``await fetchRuns()`` -> ``if (cancelled) return`` ->
    # ``applyRunsData`` (or ``setRuns(``) ordering inside the same
    # try-block. The 0-300 character window keeps the regex tight
    # against accidental matches across unrelated code.
    pattern = re.compile(
        r"await\s+fetchRuns\(\)[\s\S]{0,300}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,300}?(?:applyRunsData|setRuns\()",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "page.tsx useEffect saknar cancelled-guard mellan await fetchRuns() "
        "och applyRunsData / setRuns. Det skapar race condition där en "
        "stale success-resolution skriver state efter unmount."
    )


@pytest.mark.tooling
def test_viewer_panel_keeps_containerref_mounted_across_unavailable_transitions() -> None:
    """Stuck-state guard: when a 404-driven setUnavailable(true) used to
    replace ``<div ref={containerRef}>`` with the pedagogic tips block
    via an ``unavailable ? tips : <div ref>`` ternary, containerRef.current
    fell to null. The effect's first-line check
    ``if (!runId || !containerRef.current) { ... return; }`` then
    short-circuited on the NEXT runId change, leaving the UI stale
    because useEffect only depends on ``[runId]`` - the dependency
    array does not re-trigger on ``unavailable``-transitions, so the
    fetch never runs for the new runId.

    Fix: render containerRef-div ALWAYS and toggle visibility via the
    Tailwind ``hidden`` class. That keeps containerRef.current bound
    across transitions so subsequent fetches can run normally.

    Source-lock both the negative pattern (no ternary swap) and the
    positive pattern (containerRef-div has ``unavailable``-conditional
    ``hidden`` in className) so a future refactor cannot regress.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Negative: containerRef-div must NOT sit as the else-branch of an
    # `unavailable ? tips : <div ref={containerRef}>` ternary. That
    # pattern unmounts the ref whenever unavailable flips to true.
    forbidden = re.compile(
        r"unavailable\s*\?\s*\([\s\S]{0,400}?\)\s*:\s*\(\s*<div\s+ref=\{containerRef\}",
        re.MULTILINE,
    )
    assert not forbidden.search(text), (
        "viewer-panel.tsx: containerRef-div får inte sitta i else-grenen "
        "av en `unavailable ? tips : <div ref>` ternary - det avmonterar "
        "ref när unavailable=true och låser UI:t i stuck state vid nästa "
        "runId-byte (effekten har bara `[runId]` som dep)."
    )

    # Positive (beteende, inte exakt syntax): containerRef måste
    # vara always-mounted via en `<div ... ref={containerRef} ... />`
    # som finns OAVSETT `unavailable`-state. Hitta `ref={containerRef}`
    # och kontrollera att JSX-elementet i samma element-block referar
    # till `unavailable` på något sätt (className-toggle, data-attr,
    # cn(...)-helper, eller annan visibility-mekanism) - alla
    # acceptabla refactorer som behåller beteendet.
    #
    # B43 (post-review-2): den tidigare regex låste exakt
    # `className="...unavailable...hidden"`-ordning + literal `"hidden"`
    # vilket gjorde att en harmlös `cn(...)` / template-literal-refactor
    # bröt testet. Nu testar vi bara att unavailable-flaggan påverkar
    # ref-divden via något observerbart JSX-attribut.
    ref_element = re.search(
        r"<div\b[^>]*\bref=\{containerRef\}[^>]*/?>",
        text,
    )
    assert ref_element, (
        "viewer-panel.tsx: ingen `<div ... ref={containerRef} ... />` "
        "hittades. Always-mounted pattern kräver en self-closing eller "
        "kort JSX-tag med ref={containerRef}."
    )
    assert "unavailable" in ref_element.group(0), (
        "viewer-panel.tsx: ref-div måste referera till `unavailable` i "
        "ett JSX-attribut (t.ex. className-toggle, data-attr, cn(...)). "
        "Det signalerar att unavailable-flaggan styr visibility utan att "
        "avmontera ref:en. Hittad ref-div:\n"
        f"{ref_element.group(0)!r}"
    )


@pytest.mark.tooling
def test_viewer_panel_guards_cancelled_after_dynamic_import_and_embed() -> None:
    """B43 (post-review-2): the StackBlitz embed path has TWO awaits
    after the initial cancelled-guard: ``await import("@stackblitz/sdk")``
    and ``await sdk.embedProject(...)``. If the operator switches runId
    between them, useEffect cleanup sets cancelled=true but the
    in-flight embedProject still mounts the STALE preview into the
    always-mounted ref-div. Reviewer flagged this in the post-review-2
    audit.

    Fix: re-check cancelled AFTER the dynamic import and AFTER the
    embedProject await. When cancelled is true post-embed, clear the
    node so the next runId starts from a clean slate.

    Source-lock the guard density: at least two cancelled-checks must
    appear between the StackBlitz import and the final setStatus call.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Isolate the success-path block from the dynamic import to the
    # final setStatus call.
    block = re.search(
        r"const sdk = \(await import\(\"@stackblitz/sdk\"\)\)[\s\S]*?setStatus\(`Förhandsvisning aktiv",
        text,
    )
    assert block, (
        "viewer-panel.tsx: kunde inte hitta success-path-blocket från "
        "StackBlitz-import till final setStatus. Refactor utan ekvivalent "
        "kommunikation av runId-success bryter detta test."
    )
    cancelled_checks = re.findall(r"\bcancelled\b", block.group(0))
    assert len(cancelled_checks) >= 2, (
        "viewer-panel.tsx success-path saknar tillräcklig cancelled-guard-"
        "täthet mellan StackBlitz-import och setStatus. Förväntat minst 2 "
        "cancelled-referenser (en efter import, en efter embedProject) - "
        f"hittade {len(cancelled_checks)}. B43-fyndet: stale embed kan "
        "mountas i ref-divden om operatör byter runId mid-flight."
    )

    # Verify the node-cleanup on stale embed exists (otherwise we'd
    # just NOT setStatus but the iframe still sits in the DOM). The
    # cleanup now uses replaceChildren() instead of innerHTML so the
    # React-owned shell keeps a cleaner DOM mutation pattern.
    assert re.search(
        r"if\s*\(\s*cancelled\s*\)\s*\{[\s\S]{0,300}?replaceChildren\(\)",
        text,
    ), (
        "viewer-panel.tsx: post-embed cancelled-grenen måste rensa "
        "containerRef.current så stale embed inte sitter kvar i "
        "den always-mounted ref-divden."
    )


@pytest.mark.tooling
def test_viewer_panel_404_branch_guards_cancelled_before_setstate() -> None:
    """Race-condition guard: when /api/runs/<runId>/files returns 404,
    the in-flight async effect must not write setState for a runId
    that has already been replaced by a newer one. Without the
    cancelled-guard a stale 404 from a previous runId overwrites the
    UI state for the currently selected run (e.g. flips it to
    "preview saknas" even though the new run has preview files).

    Source-lock the cancelled-check inside the 404 branch so a future
    refactor cannot drop it. The other branches (success, catch) are
    already guarded; this brings the 404 path in line with them.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Find the 404 branch and verify a `cancelled` guard sits between
    # the `response.status === 404` check and `setUnavailable(true)`.
    # Multi-line regex is more robust than substring tricks here.
    pattern = re.compile(
        r"response\.status\s*===\s*404[\s\S]{0,400}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,200}?setUnavailable\(true\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "viewer-panel.tsx 404-branch saknar cancelled-guard innan "
        "setUnavailable / setStatus. Det skapar race-condition mellan "
        "snabba runId-byten där en stale 404 skriver över state för en "
        "nyladdad run."
    )


@pytest.mark.tooling
def test_run_history_uses_status_dot_colors() -> None:
    """UX-prioritet 2 (GPT-reviewer): Run History ska visa per-run
    status-färgning, inte bara en select med textstatus. Lås det
    färgkonceptet så framtida refactor inte återgår till plain
    select.
    """
    text = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    assert "STATUS_DOT_COLORS" in text, (
        "RunHistory ska mappa status -> färgklass via STATUS_DOT_COLORS-tabellen."
    )
    for status in ("ok", "failed", "degraded", "mock-complete"):
        assert status in text, (
            f"RunHistory saknar färg-mapping för status {status!r}."
        )


@pytest.mark.tooling
def test_viewser_does_not_register_ui_components_in_naming_dictionary() -> None:
    """v9 tar bort chatPanel/viewerPanel/tokenMeter; viewser stannar kvar."""
    naming = json.loads(NAMING_PATH.read_text(encoding="utf-8"))
    term_ids = {term["id"] for term in naming["terms"]}
    assert "viewser" in term_ids, "viewser ska vara canonical operator-yta"
    for forbidden in ["chatPanel", "viewerPanel", "tokenMeter"]:
        assert forbidden not in term_ids, (
            f"{forbidden} ska inte vara canonical term i naming-dictionary v9; "
            "det är en lokal UI-komponent i apps/viewser/"
        )


@pytest.mark.tooling
def test_viewser_scope_excludes_canonical_runtime_features() -> None:
    """Viewser MVP får INTE innehålla Dossier-edit, DNA, follow-up, repair, quality."""
    forbidden_substrings = [
        "ProjectDna",
        "RepairPipeline",
        "QualityGate",
        "FollowUp",
        "DossierEditor",
    ]
    for path in VIEWSER_DIR.rglob("*.ts*"):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_substrings:
            assert needle not in text, (
                f"{path.relative_to(REPO_ROOT)} innehåller out-of-scope-symbol "
                f"'{needle}'. Viewser MVP är localhost-prototype, inte canonical runtime."
            )
