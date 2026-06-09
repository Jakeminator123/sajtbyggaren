"""Viewser runs/versions UI: history, details, versions tab, UI infra (tiers/toasts)."""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR


@pytest.mark.tooling
def test_run_history_can_show_prompt_project_id_and_version() -> None:
    run_history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    assert "projectId?: string" in run_history and "version?: number" in run_history, (
        "RunHistoryItem måste kunna bära sidecar projectId/version för prompt-genererade runs."
    )
    assert "run.projectId" in run_history and "run.version" in run_history, (
        "RunHistory måste rendera projectId/version när /api/runs skickar dem."
    )
    assert "prompt-inputs" in runs_lib and "projectId" in runs_lib, (
        "listRuns måste enrich:a runs med data/prompt-inputs/<siteId>.meta.json."
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
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
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
def test_run_details_panel_surfaces_npm_failure_log_excerpt() -> None:
    """Build mismatch triage needs the original npm error in Run Details."""
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

    assert "devPreviewDir" in panel_text, (
        "RunDetailsPanel must show build-result.json:devPreviewDir so "
        "operators can compare the runnable preview dir with generatedFilesDir."
    )
    assert "logExcerpt" in panel_text, (
        "RunDetailsPanel must render npmSteps[].logExcerpt so transient "
        "npm build failures keep their first actionable error."
    )
    assert "whitespace-pre-wrap" in panel_text, (
        "npm failure excerpts must preserve line breaks when rendered."
    )


@pytest.mark.tooling
def test_run_details_panel_renders_placeholder_contact_warning() -> None:
    """B133: when scripts/build_site.py writes ``placeholderContactFields``
    into build-result.json (because scripts/prompt_to_project_input.py
    filled contact slots with the B88 dummy fallback), the Build section
    of RunDetailsPanel must render an operator-facing warning instead
    of silently letting "+46 8 000 00 00" / "kontakt@example.se" /
    "Adress lämnas på förfrågan" reach the published site without any
    signal. Verified live in Viewser Overlay E2E Scout Case 3a
    2026-05-19 (`docs/archive/2026-05-19/viewser-overlay-e2e-scout-2026-05-19.md`).
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

    assert "placeholderContactFields" in panel_text, (
        "RunDetailsPanel must read build-result.json:placeholderContactFields "
        "so the operator sees that the contact block is dummy data."
    )
    assert "Kontakt-fält är platshållare" in panel_text, (
        "Warning copy must include the Swedish phrase 'Kontakt-fält är "
        "platshållare' — operators see the badge but not the JSON."
    )
    # B158/B159 (2e0c55f, 2026-06-01): the published site no longer renders
    # the dummy values — it suppresses them and shows a generic contact CTA.
    # The warning copy must therefore say the fields are HIDDEN (real contact
    # info missing), not that visitors see dummies.
    assert "Sajten döljer fälten publikt" in panel_text, (
        "Warning copy must reflect post-B158/B159 behaviour: the site hides "
        "placeholder contact fields and shows a generic CTA instead of "
        "publishing dummy values. The old 'Slutanvändaren ser dummy-värden' "
        "copy is now factually wrong."
    )
    assert "Slutanvändaren ser dummy-värden" not in panel_text, (
        "Stale pre-suppression copy must be removed — it claims visitors see "
        "dummy contact values, which B158/B159 no longer do."
    )
    assert "placeholder-contact-warning" in panel_text, (
        "Warning element must carry data-testid='placeholder-contact-warning' "
        "so future Playwright/Vitest coverage can target it without DOM "
        "scraping."
    )
    assert "amber-500" in panel_text, (
        "Warning must use the existing amber-500 utility class so it "
        "matches the established 'warn' tone in STATUS_TONE."
    )


@pytest.mark.tooling
def test_run_details_panel_renders_site_plan_warnings() -> None:
    """B144: när Builder-sprinten 2026-05-21 (B137 + B138 + Intent Guard
    light) skrev ``pageCountWarning`` (route_plan trim på brief.pageCount)
    och ``intentGuardWarnings`` (wizard categoryId vs brief
    businessTypeGuess) till ``site-plan.json``, renderade Run Details
    inte fälten. Operatören saknade synlig signal trots att artefakten
    bar warnings — verifierat live mot sköldpaddssoppa-runen där
    intentGuardWarnings flaggade ``categoryId='fitness'`` mot
    ``conflictingTerm='mat'`` utan att Run Details visade det. Reviewer
    2026-05-21 (~7/10) öppnade B144 (Medel) som följd, med PR #49-
    inventeringen ``docs/archive/run-details-warnings-inventory-2026-05-21.md``
    som placeringsskissen.

    Mirror placeholderContactFields-mönstret i BuildSection
    (``test_run_details_panel_renders_placeholder_contact_warning``):
    amber-block, ``data-testid``, svensk operatörsrubrik. Den äldre
    ``pageIntentWarnings`` (B132) tas med i samma block eftersom den
    redan finns i schemat men aldrig fick en strukturerad rendering.

    Locks:

    1. ``site-plan.json`` är canonical källa — komponenten läser fälten
       från sitePlan-objektet, inte build-result.json. Lock både
       fältnamnen OCH att källan är sitePlan (inte build).
    2. ``data-testid='site-plan-warnings'`` så framtida Playwright/Vitest
       coverage kan targeta blocket utan DOM-scraping.
    3. Amber tone (STATUS_TONE.warn) matchar placeholderContactFields-
       blocket — ej röd/destructive, eftersom warnings är non-blocking.
    4. Svensk rubrik ``Site Plan-varningar`` så operatören förstår
       blockets ursprung utan att läsa JSON.
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

    for field in ("pageCountWarning", "intentGuardWarnings", "pageIntentWarnings"):
        assert field in panel_text, (
            f"RunDetailsPanel måste läsa site-plan.json:{field} så "
            f"operatören ser varningen i Site Plan-sektionen. Sprinten "
            f"2026-05-21 landade fälten i artefakten utan att rendera dem."
        )

    assert "sitePlan.pageCountWarning" in panel_text, (
        "Site Plan warning-blocket måste läsa pageCountWarning från "
        "sitePlan-objektet — site-plan.json är canonical källa enligt "
        "B144-skissen i docs/reports/run-details-warnings-inventory-"
        "2026-05-21.md. Build-result.json bär en kopia av "
        "pageIntentWarnings men plan-fältena (pageCountWarning + "
        "intentGuardWarnings) lever bara i site-plan.json."
    )
    assert "sitePlan.intentGuardWarnings" in panel_text, (
        "Site Plan warning-blocket måste läsa intentGuardWarnings från "
        "sitePlan-objektet (Intent Guard light skriver bara till "
        "site-plan.json, inte build-result.json — se B144-skissen)."
    )

    assert "site-plan-warnings" in panel_text, (
        "Site Plan warning-blocket måste bära "
        "data-testid='site-plan-warnings' så framtida Playwright/Vitest-"
        "coverage kan targeta det utan DOM-scraping. Mirror "
        "placeholder-contact-warning-mönstret från BuildSection."
    )

    assert "amber-500" in panel_text, (
        "Site Plan warning-blocket måste använda amber-500 "
        "(STATUS_TONE.warn), samma palett som placeholderContactFields-"
        "blocket. Warnings är non-blocking; röd/destructive skulle "
        "felaktigt signalera att builden stoppats."
    )

    assert "Site Plan-varningar" in panel_text, (
        "Site Plan warning-blocket måste ha en svensk rubrik så "
        "operatören förstår blockets innehåll utan att läsa JSON — "
        "mirror 'Kontakt-fält är platshållare'-mönstret från "
        "BuildSection. AGENTS.md kräver svenska operatörslabels."
    )

    assert "Build blockas inte" in panel_text, (
        "Site Plan warning-blocket måste förklara att varningarna är "
        "non-blocking så operatören inte tror att builden stoppats. "
        "Quality Gate/Repair-sektionerna driver build-status; planner-"
        "warnings är ren signalering."
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
        assert status in text, f"RunHistory saknar färg-mapping för status {status!r}."


@pytest.mark.tooling
def test_runs_lib_marks_stale_pending_runs_as_aborted() -> None:
    """Bug A: ett bygge som dödas mitt i (flik stängd, Cursor-omstart) hinner
    aldrig skriva build-result.json eller promota current.json, så runen
    fastnade `pending`/grå för evigt och vilseledde operatören. listRuns OCH
    readRunTrace måste i stället rapportera en pending-run som varit inaktiv
    längre än en timeout som `aborted` (röd), och båda måste dela samma gräns
    så Run History och trace-pollern är överens. Lås invarianterna här så en
    refactor inte tyst återinför grå-för-evigt-buggen.
    """
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")

    assert '"aborted"' in runs_lib, (
        "RunStatus måste innehålla 'aborted' för avbrutna/stale-pending byggen."
    )
    assert "isStalePending" in runs_lib and "STALE_PENDING_TIMEOUT_MS" in runs_lib, (
        "runs.ts måste härleda stale-pending via en delad timeout (isStalePending "
        "+ STALE_PENDING_TIMEOUT_MS) så listRuns och readRunTrace är överens."
    )
    assert "VIEWSER_STALE_PENDING_MS" in runs_lib, (
        "Stale-pending-timeouten ska gå att justera via VIEWSER_STALE_PENDING_MS."
    )
    # Båda kodvägarna (lista + trace) måste markera aborted, annars pollar
    # use-build-trace-polling ett dött bygge i all oändlighet.
    assert runs_lib.count('"aborted"') >= 2, (
        "Både listRuns/buildPendingMeta och readRunTrace måste sätta 'aborted'."
    )

    run_history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    assert "aborted:" in run_history, (
        "RunHistory STATUS_DOT_COLORS måste mappa 'aborted' till en röd prick "
        "(annars faller den tillbaka till samma grå som pending)."
    )

    details = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
    assert "aborted:" in details, (
        "RunDetailsPanel STATUS_TONE måste mappa 'aborted' till fail-ton, inte neutral."
    )


@pytest.mark.tooling
def test_run_details_panel_clears_bundle_on_run_change() -> None:
    """Stale-artefakt guard: when runId changes the effect must clear
    bundle before fetching so the panel never shows the previous run's
    build/quality cards under the new run badge.
    """
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
    pattern = re.compile(
        r"setBundle\(null\)[\s\S]{0,120}?setLoading\(true\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "run-details-panel.tsx måste nollställa bundle innan ny fetch "
        "vid runId-byte — annars visas gamla artefakter under laddning."
    )


# --- Tier 1 (robusthet, 2026-06-01) ---------------------------------------
#
# Tre regressionstester för Tier 1-frontend-paketet:
#   * ErrorBoundary måste finnas och wrappa fel-prona subtree:er i page.tsx
#   * ToastProvider måste vara mountat högst upp i Providers
#   * /api/runs-failure visar retry-card + toast (inte tyst stuck status)
#
# Syftet är att hindra framtida refactors från att tysta dessa fel-
# hanteringsytor utan att vi märker det. Att radera ErrorBoundary eller
# ToastProvider av misstag är en regression som är svår att upptäcka
# tills produktionen kraschar.


@pytest.mark.tooling
def test_tier1_error_boundary_component_exists() -> None:
    """ErrorBoundary-komponenten måste finnas i ``components/error-boundary.tsx``.

    Den är en klasskomponent (React 19 har inget hook-API för error
    boundaries) och måste exportera ``ErrorBoundary`` med en ``area``-
    prop så fallback-rubriken kan anpassas per call-site.
    """
    path = VIEWSER_DIR / "components" / "error-boundary.tsx"
    assert path.exists(), "ErrorBoundary-komponenten saknas"
    text = path.read_text(encoding="utf-8")

    assert "export class ErrorBoundary" in text, (
        "ErrorBoundary måste vara en exporterad klass — React 19 har "
        "fortfarande inget hook-API för error boundaries"
    )
    assert "getDerivedStateFromError" in text, (
        "ErrorBoundary måste implementera getDerivedStateFromError för att fånga rendering-fel"
    )
    assert "componentDidCatch" in text, (
        "ErrorBoundary måste implementera componentDidCatch för att "
        "logga fel till devtools/operatör-konsolen"
    )
    assert "area:" in text or "area: string" in text, (
        "ErrorBoundary måste ta en ``area``-prop så fallback-rubriken kan "
        "anpassas per call-site (t.ex. 'Builder', 'Wizard')"
    )


@pytest.mark.tooling
def test_tier1_page_wraps_subtrees_in_error_boundary() -> None:
    """``app/page.tsx`` måste wrappa ViewerPanel, PromptBuilder och
    BuilderShell i ErrorBoundary så ett crash i någon subtree inte
    ger vit skärm för hela appen.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert 'from "@/components/error-boundary"' in text, "page.tsx måste importera ErrorBoundary"

    # Räkna antal ErrorBoundary-öppningar i JSX. Tre boundaries:
    # ViewerPanel, PromptBuilder, BuilderShell. Mindre tolerant vore
    # bättre men gör testet sprödare; nuvarande gräns säger bara
    # "minst tre", vilket fångar borttagningar.
    boundary_opens = len(re.findall(r"<ErrorBoundary\s+area=", text))
    assert boundary_opens >= 3, (
        "page.tsx måste wrappa minst tre fel-prona subtree:er "
        "(ViewerPanel, PromptBuilder, BuilderShell) i ErrorBoundary "
        f"— hittade bara {boundary_opens}"
    )


@pytest.mark.tooling
def test_tier1_toast_system_exists_and_is_mounted() -> None:
    """Toast-systemet måste finnas i ``components/ui/toast.tsx`` med
    publika API:erna ``ToastProvider``, ``useToast`` och en viewport-
    region som mountas via Provider:n. Providers.tsx ska wrappa
    ToastProvider runt resten av app:en så ``useToast()`` är tillgängligt
    från hela komponentträdet.
    """
    toast_path = VIEWSER_DIR / "components" / "ui" / "toast.tsx"
    assert toast_path.exists(), "Toast-systemet saknas"
    toast_text = toast_path.read_text(encoding="utf-8")

    assert "export function ToastProvider" in toast_text, "toast.tsx måste exportera ToastProvider"
    assert "export function useToast" in toast_text, "toast.tsx måste exportera useToast()"
    # aria-live krävs för skärmläsar-uppläsning av toaster.
    assert "aria-live" in toast_text, (
        "Toast-regionen/items måste ha aria-live så skärmläsare läser upp dem när de visas"
    )
    # role="alert" eller role="status" krävs för att toaster ska
    # annonseras.
    assert 'role="alert"' in toast_text or "liveRole" in toast_text, (
        'Toast-items måste ha role="alert"/"status" beroende på variant'
    )

    providers_text = (VIEWSER_DIR / "app" / "providers.tsx").read_text(encoding="utf-8")
    assert "ToastProvider" in providers_text, (
        "Providers.tsx måste mounta ToastProvider så useToast() funkar från hela komponentträdet"
    )


@pytest.mark.tooling
def test_tier1_page_handles_runs_load_failure_with_retry() -> None:
    """``app/page.tsx`` måste visa en retry-yta när initial /api/runs
    failar — inte bara en tyst stuck loading-text. Vi söker efter
    ``runsLoadError``-state och en RunsLoadErrorCard- (eller
    motsvarande) -komponent med retry-knapp.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert "runsLoadError" in text, (
        "page.tsx måste ha runsLoadError-state för att visa retry-card vid /api/runs-failures"
    )
    assert "RunsLoadErrorCard" in text or "onRetry" in text, (
        "page.tsx måste rendera ett retry-card med onRetry-callback när runsLoadError är satt"
    )
    # Toast-feedback för failure-pathen så operatören ser felet även
    # om hen inte tittar på hero-ytan.
    assert 'variant: "error"' in text and "Kunde inte ladda runs" in text, (
        "page.tsx måste visa en error-toast med titel 'Kunde inte "
        "ladda runs' när initial fetch failar"
    )


# ---------------------------------------------------------------------------
# Tier 2 — skeleton-konsekvens + Cmd+K shortcut
# ---------------------------------------------------------------------------


def test_tier2_inspector_uses_skeleton_during_loading() -> None:
    """``site-inspector-sheet.tsx`` måste rendera Skeleton-block under
    artefact-loading istället för en spinner-only "Läser artefakter…"-
    rad. Skeleton-mönstret ger operatören en visuell preview av tab-
    strukturen som kommer dyka upp och förhindrar layout-hopp.
    """
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "site-inspector-sheet.tsx"
    ).read_text(encoding="utf-8")

    assert "InspectorLoadingSkeleton" in text, (
        "site-inspector-sheet.tsx måste ha en InspectorLoadingSkeleton-"
        "komponent som ersätter den gamla Loader2-spinnern"
    )
    assert "import { Skeleton }" in text, (
        "site-inspector-sheet.tsx måste importera Skeleton från @/components/ui/skeleton"
    )
    # Loader2 var den gamla spinnern — bekräfta att den är borta från
    # imports OCH från jsx-trädet i loading-blocket.
    assert "Loader2" not in text, (
        "site-inspector-sheet.tsx ska inte längre använda Loader2 — "
        "skeleton-tillståndet ersätter spinnern"
    )
    assert 'role="status"' in text and 'aria-live="polite"' in text, (
        "InspectorLoadingSkeleton måste ha role=status + aria-live så "
        "skärmläsare läser upp att vi laddar"
    )


def test_tier2_variants_tab_uses_skeleton_during_loading() -> None:
    """``variants-tab.tsx`` måste byta sin Loader2-spinner mot Skeleton-
    kort medan ``options === null``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "variants-tab.tsx").read_text(
        encoding="utf-8"
    )

    assert "import { Skeleton }" in text, "variants-tab.tsx måste importera Skeleton"
    assert "Loader2" not in text, "variants-tab.tsx ska inte använda Loader2 i loading-blocket"
    # 4 skeleton-kort matchar variant-grid (2 cols × 2 rader på sm+).
    assert "length: 4" in text, (
        "variants-tab.tsx måste rendera 4 Skeleton-kort som approximerar variant-grid"
    )


def test_tier2_versions_tab_uses_skeleton_for_init_and_diff() -> None:
    """``versions-tab.tsx`` måste byta båda Loader2-spinners (initial-
    load + diff-load) mot Skeleton-rader. Loader2 får finnas kvar för
    pågående-bygge-raden (annan use case).
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )

    assert "import { Skeleton }" in text, "versions-tab.tsx måste importera Skeleton"
    # Initial-load: text "Läser versioner" får finnas kvar som sr-only-
    # span, men måste sitta i ett block som också renderar Skeleton.
    init_idx = text.find("Läser versioner")
    assert init_idx != -1, (
        "versions-tab.tsx förväntas ha 'Läser versioner' som sr-only-text i loading-blocket"
    )
    init_block = text[init_idx - 400 : init_idx + 600]
    assert "Skeleton" in init_block and "sr-only" in init_block, (
        "Initial-loading-blocket i versions-tab.tsx måste rendera "
        "Skeleton + sr-only istället för en Loader2-spinner"
    )
    # Diff-load ("Räknar diff…") får inte längre kombineras med Loader2.
    diff_loading_idx = text.find("Räknar diff")
    if diff_loading_idx != -1:
        # Räknar bara om strängen finns kvar (sr-only). Då måste
        # samma block också använda Skeleton.
        block = text[diff_loading_idx - 400 : diff_loading_idx + 400]
        assert "Skeleton" in block, (
            "Diff-loading-blocket i versions-tab.tsx måste rendera Skeleton istället för Loader2"
        )


def test_tier2_run_details_panel_uses_skeleton_during_loading() -> None:
    """``run-details-panel.tsx`` måste byta "Laddar artefakter…"-text
    mot Skeleton-rader.
    """
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

    assert "import { Skeleton }" in text, "run-details-panel.tsx måste importera Skeleton"
    # Säkerställ att den nakna text-only loading-paragrafen är borta.
    assert '<p className="text-sm text-muted-foreground">Laddar artefakter' not in text, (
        "run-details-panel.tsx ska inte längre rendera en text-only 'Laddar artefakter…'-paragraf"
    )


# ---------------------------------------------------------------------------
# Tier 3 — a11y-pass + fil-split (versions-tab + viewer-panel)
# ---------------------------------------------------------------------------


def test_tier3_sheet_and_dialog_use_swedish_close_label() -> None:
    """De svenska sr-only-labels för close-knappar i ``ui/sheet.tsx`` +
    ``ui/dialog.tsx`` måste vara "Stäng", inte engelska "Close". Resten
    av UI:t är konsekvent svenskt — sr-only-text får inte glida.
    """
    sheet = (VIEWSER_DIR / "components" / "ui" / "sheet.tsx").read_text(encoding="utf-8")
    dialog = (VIEWSER_DIR / "components" / "ui" / "dialog.tsx").read_text(encoding="utf-8")

    assert '<span className="sr-only">Stäng</span>' in sheet, (
        "ui/sheet.tsx måste använda 'Stäng' (inte 'Close') som sr-only-text på close-knappen"
    )
    assert '<span className="sr-only">Stäng</span>' in dialog, (
        "ui/dialog.tsx måste använda 'Stäng' (inte 'Close') som sr-only-text på close-knappen"
    )
    # Bekräfta att engelska "Close" inte ligger kvar i fixerade strängar.
    # Stränget kan dyka upp i kommentarer eller komponentnamn (`SheetClose`),
    # så vi söker bara sr-only-mönstret.
    assert '"sr-only">Close<' not in sheet, (
        "ui/sheet.tsx har fortfarande 'Close' i sr-only-text — ska vara 'Stäng'"
    )
    assert '"sr-only">Close<' not in dialog, (
        "ui/dialog.tsx har fortfarande 'Close' i sr-only-text — ska vara 'Stäng'"
    )


def test_tier3_versions_tab_diff_view_is_extracted() -> None:
    """``versions-tab.tsx`` växte till 1438 rader innan split — den
    delade ut DiffView + helpers + EmptyState till en egen fil. Vi
    kontrollerar att huvudfilen importerar från den nya filen istället
    för att definiera lokalt, och att den nya filen exporterar det
    förväntade publika API:et.
    """
    main = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )
    split = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab" / "diff-view.tsx"
    ).read_text(encoding="utf-8")

    # Importerar från den nya filen.
    assert 'from "@/components/builder/inspector/versions-tab/diff-view"' in main, (
        "versions-tab.tsx måste importera DiffView/CompareEmptyHint/"
        "VersionsEmptyState från den nya diff-view-filen"
    )
    # Lokala definitioner är borta — annars dubbeldefinition.
    assert "function DiffView(" not in main, (
        "versions-tab.tsx ska inte längre definiera DiffView lokalt"
    )
    assert "function ScalarChangeRow(" not in main, (
        "versions-tab.tsx ska inte längre definiera ScalarChangeRow lokalt"
    )
    assert "function ValueChip(" not in main, (
        "versions-tab.tsx ska inte längre definiera ValueChip lokalt"
    )
    assert "function ChipDiffRow(" not in main, (
        "versions-tab.tsx ska inte längre definiera ChipDiffRow lokalt"
    )
    assert "function ChangeChip(" not in main, (
        "versions-tab.tsx ska inte längre definiera ChangeChip lokalt"
    )
    assert "function CompareEmptyHint(" not in main, (
        "versions-tab.tsx ska inte längre definiera CompareEmptyHint lokalt"
    )

    # Splitfilen exporterar förväntat API.
    assert "export function DiffView(" in split, "diff-view.tsx måste exportera DiffView"
    assert "export function CompareEmptyHint(" in split, (
        "diff-view.tsx måste exportera CompareEmptyHint"
    )
    assert "export function VersionsEmptyState(" in split, (
        "diff-view.tsx måste exportera VersionsEmptyState"
    )


def test_tier3_versions_tab_shrunk_below_1300_lines() -> None:
    """Sanity-check: ``versions-tab.tsx`` ska vara mätbart mindre efter
    Tier 3-splittet. Var 1438 rader → mål under 1300 (faktiskt resultat:
    1184). Tröskeln är generös så framtida tilltäg i huvudfilen inte
    bryter testet förrän det är dags för nästa split.
    """
    path = VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx"
    line_count = sum(1 for _ in path.open(encoding="utf-8"))
    assert line_count < 1300, (
        f"versions-tab.tsx har växt till {line_count} rader — splitta "
        f"ytterligare innan vi går över 1300"
    )


# ----------------------------------------------------------------------
# Pre-push-fixar (efter Tier 3 scout)
# ----------------------------------------------------------------------
# Fem P1-fynd från pre-push-scouten:
#   1. ErrorBoundary måste applicera ``className`` även i success-render
#      så ``h-full w-full``-kedjan till ViewerPanel inte bryts.
#   2. Toast ``dismiss`` måste vara idempotent + rensa både auto-dismiss
#      och cleanup-timers så Map:en inte läcker entries.
#   3. ToastViewport flyttades från ``bottom-4`` till ``top-20`` för att
#      inte skymma FloatingChat-composern eller mobil bottom-sheet.
#   4. ``build-progress-card.tsx`` måste normalisera env-variabeln på
#      samma sätt som ``viewer-panel.tsx`` (``trim`` + ``toLowerCase``)
#      annars ljuger PREVIEW_PREP_HINT vid casing-varianter.
#   5. Cmd+K-listenern hoppar nu över ``SELECT``-element så ConsoleDrawer
#      inte togglar mitt i ett val.


def test_pre_push_toast_dismiss_is_idempotent() -> None:
    """``dismiss`` ska vara idempotent (hoppar över om cleanup redan
    pågår) och rensa både auto-dismiss-timern och cleanup-timern i
    ``removeToast`` så Map-entries inte läcker.
    """
    path = VIEWSER_DIR / "components" / "ui" / "toast.tsx"
    content = path.read_text(encoding="utf-8")
    assert re.search(
        r"timeoutsRef\.current\.has\(`\$\{id\}:cleanup`\)",
        content,
    ), "dismiss måste tidigt-returnera om cleanup-timern redan finns"
    assert "timeoutsRef.current.delete(`${id}:cleanup`)" in content, (
        "removeToast måste rensa ``${id}:cleanup``-nyckeln så Map:en "
        "inte växer obegränsat när manuell dismiss races med auto-timeout"
    )


def test_builder_followup_drives_buildstage_via_real_trace_signal() -> None:
    """Scout-fynd (P1): i builder-läge drevs ``buildStage`` aldrig under
    follow-ups (``onStageChange={builderActive ? undefined : setBuildStage}``
    stänger av PromptBuilder:s rapport), så ViewerPanel:s BuildProgressCard
    frös på föregående bygges sista stage och stegmarkören hoppade direkt
    till sista steget.

    Fixen trådar ``onStageChange`` page.tsx → BuilderShell → FloatingChat och
    driver stegen från den RIKTIGA trace.ndjson-signalen
    (``useBuildTracePolling.currentPhase``), inte en setTimeout-flip (jfr
    B122). Lås kedjan så den inte tyst kopplas bort igen.
    """
    page = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    shell = (VIEWSER_DIR / "components" / "builder" / "builder-shell.tsx").read_text(
        encoding="utf-8"
    )
    chat = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    # page.tsx måste skicka setBuildStage till BuilderShell (annars är
    # buildStage frusen under follow-ups).
    assert "onStageChange={setBuildStage}" in page, (
        "page.tsx måste skicka onStageChange={setBuildStage} till BuilderShell "
        "så follow-up-bygget driver BuildProgressCard"
    )
    # BuilderShell återställer stage vid VARJE byggstart (FloatingChat ELLER
    # dialog) + vidarebefordrar till FloatingChat.
    assert 'onStageChange?.("thinking")' in shell, (
        "BuilderShell.handleBuildStart måste återställa stage till 'thinking' "
        "så stegmarkören aldrig fryser på föregående bygges sista stage"
    )
    assert "onStageChange={onStageChange}" in shell, (
        "BuilderShell måste tråda onStageChange vidare till FloatingChat"
    )
    # FloatingChat förfinar från trace.ndjson-fasen (riktig signal).
    assert 'tracePolling.currentPhase === "build"' in chat, (
        "FloatingChat måste mappa trace.ndjson-fasen 'build' → buildStage "
        "'building' (riktig signal, inte setTimeout)"
    )
    assert 'onStageChange("building")' in chat, (
        "FloatingChat måste rapportera 'building' när trace når build-fasen"
    )
    # Avslut: success/degraded/failed rapporteras när bygget landar. Mappningen
    # delas med PromptBuilder via outcomeToStage (P2-fix #26: degraded/unknown
    # → "degraded", inte "success", så progress-cardet inte visar grönt medan
    # chatten rapporterar varning).
    assert "onStageChange?.(outcomeToStage(outcome));" in chat, (
        "FloatingChat måste rapportera stage via outcomeToStage när bygget landar"
    )


def test_studio_preserves_iterate_base_on_failed_build() -> None:
    """Scout-fynd (P1, 2026-06-05): onBuildDone rensade pendingBaseRunId
    ovillkorligt — även för outcome=failed (failed returnerar en runId, så
    onBuildDone körs). Då tappade error-bubblans 'Försök igen' iterera-från-
    bas-läget och nästa retry grenade från latest i stället för vald bas, vilket
    motsäger onBuildEnd-kommentarens uttryckliga intent. Lås att base-run:en bara
    rensas när bygget producerade en riktig version (ok/degraded), inte vid failed.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    assert 'if (outcome !== "failed") setPendingBaseRunId(null);' in text, (
        "onBuildDone måste behålla pendingBaseRunId vid failed så error-bubblans "
        "'Försök igen' itererar från samma bas i stället för latest."
    )


def test_run_history_shows_skeleton_while_loading() -> None:
    """Wave 3 (Steg 8): under initial /api/runs-laddning visades tom-CTA:n
    ('Inga runs än') i förtid. RunHistory ska rendera en skeleton när
    loading och inga runs ännu finns, och page.tsx → ConsoleDrawer →
    RunHistory ska tråda loading-flaggan.
    """
    history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    drawer = (VIEWSER_DIR / "components" / "console-drawer.tsx").read_text(encoding="utf-8")
    page = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert "RunHistorySkeleton" in history and "Skeleton" in history, (
        "RunHistory måste ha en RunHistorySkeleton som använder Skeleton-primitiven"
    )
    assert "loading && runs.length === 0" in history, (
        "RunHistory måste visa skeleton när loading och inga runs ännu finns"
    )
    assert "loading={runsLoading}" in drawer, (
        "ConsoleDrawer måste tråda runsLoading → RunHistory.loading"
    )
    assert "runsLoading={runsLoading}" in page, (
        "page.tsx måste skicka runsLoading till ConsoleDrawer"
    )


def test_studio_empty_state_offers_starters() -> None:
    """Starters-banan: en tom /studio (ingen handoff) ska visa starter-
    onboarding i stället för en blank canvas, och kunna konsumera en
    wizard-seed från en yrkessida/hero-chip.
    """
    builder = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "consumeWizardSeed" in builder, "PromptBuildern ska konsumera wizard-seed vid mount"
    assert "openWizardFromPreset" in builder and "STARTER_PRESETS" in builder, (
        "Tom-läget ska erbjuda starter-chips som öppnar wizarden förvald"
    )
    assert "showStarters" in builder, "PromptBuildern ska ha ett tom-läges-onboarding-tillstånd"


# ---------------------------------------------------------------------------
# UX-batch (versionssynlighet / preview-tillstånd / FloatingChat / a11y).
# Source-lock-tester som låser de fyra in-lane-förbättringarna så de inte
# tyst tas bort i framtida UI-refactor.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_history_pending_dot_is_distinct_and_pulses() -> None:
    """S1: `pending` (faktiskt pågående bygge) ska ha en egen färg + puls
    så det inte konflateras med de grå terminal-statusarna skipped/unknown.
    """
    text = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    assert 'pending: "bg-sky-400"' in text, (
        "Run History ska ge pending en egen sky-färg, inte falla igenom "
        "till den grå muted-foreground-pricken."
    )
    assert 'status === "pending"' in text and "motion-safe:animate-pulse" in text, (
        "pending-pricken ska pulsera (motion-safe) för att signalera pågående bygge."
    )
    assert "formatAbsolute" in text and "toLocaleString" in text, (
        "Relativa tider ska ha en absolut tidsstämpel-tooltip (title) via formatAbsolute."
    )


@pytest.mark.tooling
def test_versions_tab_status_palette_and_absolute_timestamp() -> None:
    """S1: Versioner-tabbens status-palett ska vara konsekvent med
    run-history (pending + aborted) och visa absolut tidsstämpel-tooltip.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )
    assert 'pending: "bg-sky-400"' in text and 'aborted: "bg-destructive"' in text, (
        "Versioner-tabben ska spegla run-history-paletten (pending + aborted) "
        "så de två versionsvyerna är konsekventa."
    )
    assert "formatAbsolute" in text, (
        "Versioner-tabben ska ha samma absolut-tidsstämpel-tooltip som run-history."
    )


@pytest.mark.tooling
def test_quality_tab_reads_canonical_artefact_schema() -> None:
    """P0: Kvalitet-tabben måste läsa de canonical artefakt-shaparna, inte
    ett påhittat parallellt schema. Den läste tidigare qualityResult.findings
    / qualityResult.gates och repairResult.actions — fält som inte finns —
    vilket fick failade runs att visa "Quality Gate gick rent" och dolde
    hela Repair Pipeline-blocket.

    Sanningskällor:
      - packages/generation/quality_gate/models.py: QualityResult har
        status + checks[] (name/status/detail/severity/findings).
      - packages/generation/repair/models.py: RepairResult har status,
        iterations, mechanicalFixesApplied[], remainingErrors[],
        qualityStatusBefore.
      - build-result.json: runDurationMs (inte durationMs), inget exitCode.

    Source-lock så en framtida refaktor inte kan återinföra fel fältnamn
    och tysta gate-resultatet igen.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "quality-tab.tsx").read_text(
        encoding="utf-8"
    )

    # Quality Gate: måste läsa checks[] + status + summary (canonical), inte
    # findings/gates (det icke-existerande parallella schemat).
    assert "qualityResult.checks" in text, (
        "Kvalitet-tabben ska läsa qualityResult.checks[] (canonical), inte "
        "qualityResult.findings/gates."
    )
    assert "qualityResult.status" in text, (
        "Kvalitet-tabben ska visa gate-status från qualityResult.status."
    )
    assert "qualityResult.findings" not in text and "qualityResult.gates" not in text, (
        "Kvalitet-tabben får inte läsa det påhittade findings/gates-schemat — "
        "det var P0-buggen som fick failade runs att se rena ut."
    )
    assert 'check.status === "failed"' in text, (
        "Kvalitet-tabben ska härleda failade checks från check.status, inte "
        "anta att en tom findings-lista betyder rent gate."
    )

    # Repair Pipeline: canonical mechanicalFixesApplied/remainingErrors, inte actions.
    assert "repairResult.mechanicalFixesApplied" in text, (
        "Repair-blocket ska läsa repairResult.mechanicalFixesApplied[]."
    )
    assert "repairResult.remainingErrors" in text, (
        "Repair-blocket ska läsa repairResult.remainingErrors[]."
    )
    assert "repairResult.actions" not in text, (
        "Repair-blocket får inte läsa det icke-existerande repairResult.actions."
    )

    # Build: runDurationMs (inte durationMs), inget exitCode-fält.
    assert "buildResult.runDurationMs" in text, (
        "Build-statusen ska läsa runDurationMs (canonical), inte durationMs."
    )
    assert "buildResult.durationMs" not in text and "buildResult.exitCode" not in text, (
        "Build-statusen får inte läsa durationMs/exitCode — de finns inte i build-result.json."
    )

    # A1 (2026-06-05): kor-4a/4b copy-kritik läses från qualityResult.critic
    # (score/source/issues[]) — warning-lane som backend skriver men UI tidigare
    # aldrig visade. Source-lock så en refaktor inte tappar critic-ytan igen.
    assert "qualityResult.critic" in text, (
        "Kvalitet-tabben måste läsa qualityResult.critic (kor-4a/4b) — score, "
        "source och issues[] skrivs av critic-lanen men visades inte alls."
    )
    assert "repairHint" in text and "issue.target" in text, (
        "Critic-blocket ska visa issue.repairHint + issue.target så operatören "
        "ser var fyndet ligger och får ett konkret fix-förslag."
    )

    # A2 (2026-06-05): repair-telemetri som backend redan skriver men UI tappade
    # — gate-efter, reason, blueprint-repairs (kor-5), llm-fixes och per-check
    # severity/durationMs. Source-lock per fält.
    assert "repairResult.qualityStatusAfter" in text, (
        "Repair-blocket ska visa gate-status EFTER reparationen "
        "(qualityStatusAfter), inte bara qualityStatusBefore."
    )
    assert "repairResult.reason" in text, (
        "Repair-blocket ska visa repairResult.reason (operatörsförklaring av "
        "varför pipelinen stannade på sin status)."
    )
    assert "repairResult.blueprintRepairs" in text, (
        "Repair-blocket ska visa kor-5 blueprintRepairs[] (issueType/field/"
        "success) — annars är blueprint-repair-telemetrin osynlig."
    )
    assert "repairResult.llmFixesApplied" in text, (
        "Repair-blocket ska läsa llmFixesApplied[] (tomt idag, populeras "
        "Sprint 5+) så framtida LLM-fixar syns utan ny UI-deploy."
    )
    assert "check.durationMs" in text and "check.severity" in text, (
        "Check-raden ska visa severity (blocking/warning) och durationMs så "
        "operatören ser blockerande vs varning och gate-latens per check."
    )


@pytest.mark.tooling
def test_run_details_panel_repair_fix_reads_canonical_fields() -> None:
    """B3 (2026-06-05): RepairSection läste ``fix.status`` / ``fix.description``
    — fält som inte finns på RepairFix. Canonical shape
    (packages/generation/repair/models.py:RepairFix + repair-result.schema.json
    :$defs.repairFix) är ``kind``/``name``/``target``/``detail``/``success``.
    Effekten var att mekaniska fixar renderades namn-bara (success + operatörs-
    detalj tappades tyst). Source-lock att panelen läser de riktiga fälten.
    """
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
    assert "fix.status" not in text and "fix.description" not in text, (
        "run-details-panel får inte läsa fix.status/fix.description — de finns "
        "inte på RepairFix (canonical: success/detail/kind/target)."
    )
    assert "fix.success" in text and "fix.detail" in text, (
        "RepairSection ska visa fix.success (fixad/misslyckades) och fix.detail "
        "från den canonical RepairFix-shapen."
    )


@pytest.mark.tooling
def test_dossiers_tab_handles_flat_selected_dossiers() -> None:
    """P1: site-plan.json:selectedDossiers är ANTINGEN en platt id-lista
    (vanligast) eller objektformen { required, recommended, conditional,
    rejected }. Tabben castade tidigare alltid till objekt → den platta
    listan tappade alla fält och fyra tomma grupper visades på vanliga runs.
    Source-lock att båda formerna hanteras (Array.isArray-gren)."""
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "dossiers-tab.tsx").read_text(
        encoding="utf-8"
    )
    assert "Array.isArray(rawSelected)" in text, (
        "Dossiers-tabben måste detektera den platta listformen av "
        "selectedDossiers (Array.isArray), inte bara objektformen."
    )
    assert "isFlatList" in text, (
        "Dossiers-tabben ska rendera en 'Valda'-grupp för den platta listan "
        "istället för fyra tomma objekt-grupper."
    )


@pytest.mark.tooling
def test_site_inspector_tab_controlled_and_clears_error() -> None:
    """P2: <Tabs> använde defaultValue och av-/återmonterades vid refresh →
    aktiv tab nollades till 'Sidor'; och buildError överlevde sheet-stängning.
    Source-lock att tab-värdet är kontrollerat och clearError körs vid stängning."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "site-inspector-sheet.tsx"
    ).read_text(encoding="utf-8")
    assert "value={activeTab}" in text and "onValueChange={setActiveTab}" in text, (
        "Inspector-tabbarna ska vara kontrollerade så valet överlever refresh."
    )
    assert "if (!open) clearError();" in text, "buildError ska rensas när inspectorn stängs."


@pytest.mark.tooling
def test_payload_popover_uses_effective_scaffold_hint() -> None:
    """P2: popover:n härledde scaffoldHint bara från family.scaffoldHint och
    missade sub-kategori-uppgraderingar → visade en annan hint än backend fick.
    Source-lock att den använder deriveEffectiveScaffoldHint (samma som
    buildDiscoveryPayload)."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "payload-alignment-popover.tsx"
    ).read_text(encoding="utf-8")
    assert "deriveEffectiveScaffoldHint(family, answers.siteType)" in text, (
        "Popover:n ska härleda scaffoldHint via deriveEffectiveScaffoldHint."
    )


@pytest.mark.tooling
def test_versions_tab_refetches_on_active_bundle_change() -> None:
    """P2: compare-diffen re-fetchade bara på id-byten → om ena sidan var den
    aktiva runen och dess bundle byggdes om visades en stale diff. Source-lock
    att en activeBundleSignal ingår i fetch-effektens deps."""
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )
    assert "activeBundleSignal" in text, (
        "CompareSection ska härleda en activeBundleSignal för den aktiva sidan."
    )
    assert "[runIdA, runIdB, currentRunId, activeBundleSignal]" in text, (
        "Fetch-effekten ska re-köra när den aktiva runens bundle ändras."
    )


@pytest.mark.tooling
def test_toast_dedupes_and_caps_stack() -> None:
    """P2: identiska toaster (t.ex. upprepade retry-fel) staplades obegränsat.
    Source-lock att show:en dedupar mot aktiva toaster och har ett max-stack-tak."""
    text = (VIEWSER_DIR / "components" / "ui" / "toast.tsx").read_text(encoding="utf-8")
    assert "MAX_VISIBLE_TOASTS" in text, (
        "Toast-systemet ska ha ett tak (MAX_VISIBLE_TOASTS) på samtidiga toaster."
    )
    assert "const duplicate = toastsRef.current.find(" in text, (
        "show() ska deduplicera identiska aktiva toaster i st.f. att stapla dubbletter."
    )


@pytest.mark.tooling
def test_followup_build_hook_supports_global_lock_and_base_run_id() -> None:
    """C1 + C2 (scout-fynd 2026-06-05): useFollowupBuild ägde varken globalt
    bygg-lås eller "Iterera från denna"-pin.

    C2: varje dialog hade bara sin egen lokala isBusy → två öppna dialoger
    (eller en dialog + FloatingChat) kunde starta parallella byggen mot samma
    siteId. Hooken måste ta emot ett globalt ``isBuilding`` och avvisa när det
    är sant.

    C1: FloatingChat skickade redan ``baseRunId`` men dialogerna gjorde det
    inte → en pinnad iteration tappades tyst när operatören bytte t.ex. färg.
    Hooken måste ta emot ``baseRunId`` och inkludera den i fetch-bodyn.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "use-followup-build.ts").read_text(
        encoding="utf-8"
    )
    assert "isBuilding?: boolean;" in text, (
        "useFollowupBuild måste exponera ett globalt isBuilding-bygg-lås (C2)."
    )
    assert "baseRunId?: string | null;" in text, (
        "useFollowupBuild måste ta emot baseRunId för 'Iterera från denna' (C1)."
    )
    assert "if (isBusy || isBuilding) {" in text, (
        "runFollowup måste avvisa när ett globalt bygge pågår, inte bara lokalt (C2)."
    )
    assert "...(baseRunId ? { baseRunId } : {})" in text, (
        "runFollowup måste skicka baseRunId i bodyn när en pin är aktiv (C1)."
    )


@pytest.mark.tooling
def test_builder_shell_threads_lock_and_base_run_id_into_dialogs() -> None:
    """C1 + C2: BuilderShell måste skicka både det globala isBuilding-låset och
    den aktiva baseRunId-pinnen till alla bygg-utlösande dialoger (variant/
    färg/bild/scrape). Utan detta är hookens nya parametrar döda på dialog-
    vägen och pin/lock gäller bara FloatingChat + Inspector.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "builder-shell.tsx").read_text(
        encoding="utf-8"
    )
    # Minst fyra dialoger (variant/color/asset/scrape) ska få bägge propsen.
    assert text.count("baseRunId={pendingBaseRunId?.baseRunId ?? null}") >= 4, (
        "Alla fyra bygg-dialoger måste få baseRunId från BuilderShell (C1)."
    )
    assert text.count("isBuilding={isBuilding}") >= 4, (
        "Alla fyra bygg-dialoger måste få det globala isBuilding-låset (C2)."
    )


@pytest.mark.tooling
def test_inspector_threads_base_run_id_into_followup_hook() -> None:
    """C1: Inspectorns quick-prompts (t.ex. 'Be om fix' i Kvalitet) gick via
    useFollowupBuild men skickade aldrig den pinnade baseRunId:n. Lås att
    SiteInspectorSheet trådar pendingBaseRunId in i hooken.
    """
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "site-inspector-sheet.tsx"
    ).read_text(encoding="utf-8")
    assert "baseRunId: pendingBaseRunId?.baseRunId ?? null," in text, (
        "SiteInspectorSheet måste skicka pendingBaseRunId till useFollowupBuild (C1)."
    )
