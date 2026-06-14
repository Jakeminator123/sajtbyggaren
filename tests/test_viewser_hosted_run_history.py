"""Source-level locks för hostad run-historik + artefakt-läsning (B199 v2).

Före B199 v2 var /api/runs hostat alltid tomt och
/api/runs/[runId]/{artifacts,trace,files} en medveten 404 + ``hostedNotice``
(latch-kontraktet i lib/hosted-run-artefacts.ts). #307 (B199 v1) persisterade
redan run-artefakterna som tarball i blob — men ingen UI-yta läste dem, och
builder-läget dog vid en hård omladdning.

B199 v2 stänger kedjan (källkods-lås, samma mönster som de andra
test_viewser_hosted_*-modulerna):

SKRIV-SIDAN (sandbox-orkestreringen i hosted-build-runner.ts)
  - Run-state-pekaren bär ``buildStatus`` (ärlig status i historiken).
  - Ett durabelt KV-index publiceras efter varje lyckat bygge:
    per-versions-posten ``viewser:site:<siteId>:run:v<N>`` + runId-indexet
    ``viewser:run:<runId>`` (HostedRunIndexEntry). Best-effort — fel faller
    aldrig ett publicerat bygge.
  - Init-byggen skriver result-blocket (engine=legacy) så svaret bär den
    KANONISKA build_site-runIden, inte orkestrerings-UUID:t.
  - Historisk ``baseRunId`` hydrerar SIN versions artefakter via runId-
    indexet (siteId-bunden — en stulen runId kan inte dra artefakter över
    sajtgränser), i stället för pekarens senaste.

LÄS-SIDAN (lib/hosted-run-history.ts + routes)
  - /api/runs?siteId= listar sajtens poster ur KV (RunMeta-paritet);
    UTAN siteId svaras tomt — siteId är capability-nyckeln (samma
    åtkomstmodell som B196), ingen global publik listning.
  - /api/runs/[runId]/{artifacts,trace} läser run-artifacts.tar.gz från
    blob och serverar samma bundle-/trace-former som lokalt.
  - En olösbar run svarar VANLIG 404 utan ``hostedNotice`` — latchen är
    reserverad för "hela förmågan saknas", vilket inte längre stämmer.

KLIENT-SIDAN (studio-sidan)
  - Builder-valet persisteras i sessionStorage och återställs efter en
    hård omladdning (B197-omladdningsluckan) — hostat via per-sajt-fetchen.
  - /api/runs-bannern bär fältet ``hostedBanner`` och armar ALDRIG latchen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
RUNNER = VIEWSER / "lib" / "hosted-build-runner.ts"
HISTORY_LIB = VIEWSER / "lib" / "hosted-run-history.ts"
RUNTIME_HELPER = VIEWSER / "lib" / "hosted-python-runtime.ts"
RUNS_ROUTE = VIEWSER / "app" / "api" / "runs" / "route.ts"
ARTIFACTS_ROUTE = VIEWSER / "app" / "api" / "runs" / "[runId]" / "artifacts" / "route.ts"
TRACE_ROUTE = VIEWSER / "app" / "api" / "runs" / "[runId]" / "trace" / "route.ts"
FILES_ROUTE = VIEWSER / "app" / "api" / "runs" / "[runId]" / "files" / "route.ts"
STUDIO_PAGE = VIEWSER / "app" / "(console)" / "studio" / "page.tsx"
TRACE_POLLING = VIEWSER / "components" / "builder" / "use-build-trace-polling.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- 1. Skriv-sidan: durabelt KV-index + buildStatus ---------------------------


def test_runner_exports_index_keys_and_entry_shape() -> None:
    source = _read(RUNNER)
    assert "export function hostedRunIndexKey" in source
    assert "return `viewser:run:${runId}`;" in source
    assert "export function hostedRunVersionKey" in source
    assert "return `viewser:site:${siteId}:run:v${version}`;" in source
    assert "export interface HostedRunIndexEntry" in source
    body = source.split("export interface HostedRunIndexEntry", 1)[1].split("\n}", 1)[0]
    for field in ("runId", "siteId", "version", "buildStatus?", "updatedAt", "runArtifactsUrl?"):
        assert field in body, f"HostedRunIndexEntry måste deklarera fältet {field!r}."


def test_script_publishes_run_index_after_build() -> None:
    source = _read(RUNNER)
    # Per-versions-post + runId-index skrivs ur samma entry-JSON.
    assert '"viewser:run:" + run_id' in source, (
        "Orkestrerings-skriptet måste skriva runId-indexet viewser:run:<runId>."
    )
    assert '"viewser:site:" + site_id + ":run:v" + version_raw' in source, (
        "Orkestrerings-skriptet måste skriva per-versions-posten "
        "viewser:site:<siteId>:run:v<N>."
    )
    # Båda SET:en går i EN pipeline-POST (inte två extra round-trips).
    assert '"$KV_REST_URL/pipeline"' in source
    # Indexet skrivs före den slutgiltiga done-statusen.
    index_at = source.index('"viewser:run:" + run_id')
    done_at = source.rindex('post_status "done"')
    assert index_at < done_at


def test_run_index_failure_never_fails_a_published_build() -> None:
    source = _read(RUNNER)
    marker_at = source.index("run-index publicerat (B199 v2")
    segment = source[marker_at - 400 : marker_at + 200]
    assert "fail " not in segment and 'fail "' not in segment, (
        "Index-publiceringen är best-effort — den får aldrig fälla ett "
        "redan publicerat bygge."
    )


def test_run_state_pointer_carries_build_status() -> None:
    source = _read(RUNNER)
    assert 'doc["buildStatus"] = _status' in source, (
        "Run-state-pekaren måste bära buildStatus (ärlig status i den "
        "hostade run-historiken, aldrig gissad)."
    )
    body = source.split("export interface HostedRunStatePointer", 1)[1].split("\n}", 1)[0]
    assert "buildStatus?" in body


# --- 2. Init-paritet: kanonisk runId även för initialbyggen --------------------


def test_init_build_writes_result_block_with_canonical_run_id() -> None:
    source = _read(RUNNER)
    assert (
        'if [ "$FOLLOWUP_MODE" = "1" ] && [ "$OPENCLAW_APPLIED" = "1" ]; then\n'
        '  write_hosted_result "openclaw"\n'
        "else\n"
        '  write_hosted_result "legacy"\n'
        "fi"
    ) in source, (
        "ÄVEN initialbygget måste skriva result-blocket (engine=legacy) så "
        "TS-svaret bär den kanoniska build_site-runIden i stället för "
        "orkestrerings-UUID:t — annars matchar selectedRunId aldrig den "
        "hostade run-historiken."
    )


# --- 3. Historisk baseRunId hydreras via runId-indexet -------------------------


def test_base_run_id_artifacts_resolved_via_index() -> None:
    source = _read(RUNNER)
    assert "hostedRunIndexKey(safeBaseRunId)" in source, (
        "startHostedBuild måste slå upp en historisk baseRunId i runId-"
        "indexet så DEN versionens artefakter hydreras (stänger #307:s "
        "'bara senaste versionen'-begränsning)."
    )
    assert "baseEntry.siteId === req.siteId" in source, (
        "baseRunId-uppslaget måste vara siteId-bundet (samma princip som "
        "B196) — en stulen runId får inte dra artefakter över sajtgränser."
    )
    # Befintliga env-kontraktet är oförändrat (runState muteras, inte env).
    assert 'RUN_ARTIFACTS_URL: runState?.runArtifactsUrl ?? ""' in source


# --- 4. Läs-sidan: lib + routes -------------------------------------------------


def test_history_lib_exists_with_expected_exports() -> None:
    assert HISTORY_LIB.exists(), "lib/hosted-run-history.ts saknas (B199 v2 läs-sida)."
    source = _read(HISTORY_LIB)
    for export in (
        "export async function listHostedRunsForSite",
        "export async function hostedProjectInputForSite",
        "export async function resolveHostedRunEntry",
        "export async function fetchHostedRunArtefactsTar",
        "export function hostedRunArtefactBundle",
        "export function hostedRunTrace",
    ):
        assert export in source, f"hosted-run-history.ts måste exportera {export!r}."
    # Tarballen packas upp i minnet med stdlib-gzip + egen ustar-läsare.
    assert "gunzipSync" in source
    assert 'source: "prompt-inputs"' in source, (
        "Hostade project-inputs måste få source 'prompt-inputs' så "
        "builderTarget-grinden i studio-sidan fungerar identiskt hostat."
    )
    # Trace-parsningen delas med den lokala disk-vägen.
    assert "parseTraceLine" in source


def test_runs_route_serves_hosted_history_per_site_only() -> None:
    source = _read(RUNS_ROUTE)
    assert "isHostedVercelRuntime()" in source
    assert "listHostedRunsForSite" in source, (
        "/api/runs måste läsa den hostade run-historiken ur KV-indexet."
    )
    # Capability-modellen: utan siteId listas INGENTING hostat (ingen
    # global publik enumeration av andras sajter).
    hosted_at = source.index("isHostedVercelRuntime()")
    no_site_at = source.index("if (!siteIdRaw) {", hosted_at)
    list_at = source.index("listHostedRunsForSite", no_site_at)
    assert hosted_at < no_site_at < list_at, (
        "Hostat måste tomma-svaret för saknad siteId komma FÖRE listningen "
        "— siteId är capability-nyckeln (samma åtkomstmodell som B196)."
    )
    # Bannern är ett EGET fält — aldrig latch-kontraktets hostedNotice.
    # (Fält-syntaxen "hostedNotice:" låses; ordet får nämnas i kommentarer.)
    assert "hostedBanner" in source
    assert "hostedNotice:" not in source, (
        "/api/runs får inte längre svara med hostedNotice-fältet — det armar "
        "404-latchen och skulle stänga av de fungerande artefakt-ytorna."
    )


def test_artifact_and_trace_routes_serve_hosted_runs_from_blob() -> None:
    for path, reader in ((ARTIFACTS_ROUTE, "hostedRunArtefactBundle"), (TRACE_ROUTE, "hostedRunTrace")):
        source = _read(path)
        assert "isHostedVercelRuntime()" in source
        assert "resolveHostedRunEntry" in source, (
            f"{path.name} måste lösa runId via KV-indexet hostat."
        )
        assert "fetchHostedRunArtefactsTar" in source
        assert reader in source
        assert "hostedNotice:" not in source, (
            f"{path.name} får inte svara med hostedNotice-fältet — en "
            "olösbar run är ett per-run-fel (vanlig 404), inte 'förmågan "
            "saknas'."
        )


def test_files_route_404_no_longer_arms_the_latch() -> None:
    source = _read(FILES_ROUTE)
    assert "isHostedVercelRuntime()" in source
    assert "hostedNotice:" not in source, (
        "files-routens hostade 404 får inte bära hostedNotice-fältet — "
        "latchen skulle stänga av artefakt-/trace-ytorna för resten av "
        "sessionen."
    )


# --- 5. Klient-sidan: banner-fältet + omladdnings-återställning -----------------


def test_studio_page_never_arms_latch_and_uses_hosted_banner() -> None:
    source = _read(STUDIO_PAGE)
    assert "rememberHostedRunNotice" not in source, (
        "studio-sidan får inte arma 404-latchen från /api/runs — hostade "
        "artefakt-/trace-fetchar ska gå precis som lokalt."
    )
    assert "hostedBanner" in source
    assert "HostedNoticeBanner" in source, "Info-bannern ska finnas kvar (ärlig drift)."


def test_studio_selection_survives_reload_via_session_storage() -> None:
    source = _read(STUDIO_PAGE)
    assert "STUDIO_SELECTION_STORAGE_KEY" in source
    assert "sessionStorage.setItem" in source and "sessionStorage.removeItem" in source, (
        "Builder-valet måste persisteras per flik och rensas vid 'Ny sajt'."
    )
    assert "readSavedStudioSelection" in source
    assert "restoredSelectionRef" in source, (
        "Återställningen får bara ske EN gång per sidvisning."
    )
    # Återställningen valideras mot den hämtade listan — aldrig blind.
    assert "data.nextRuns.some((run) => run.runId === saved.runId)" in source
    # Hostat hämtas den sparade sajtens historik (capability-modellen).
    assert "fetchRuns(saved.siteId)" in source
    assert "siteIdHint" in source


def test_trace_polling_stops_on_banner_without_arming_latch() -> None:
    source = _read(TRACE_POLLING)
    assert "payload.hostedBanner" in source, (
        "Trace-pollern ska avsluta tyst på hostedBanner (ingen pending-rad "
        "kan dyka upp hostat)."
    )
    assert "rememberHostedRunNotice" not in source, (
        "Trace-pollern får inte arma latchen — artefakt-ytorna fungerar "
        "numera hostat."
    )


# --- 6. Banner-texten speglar det nya läget -------------------------------------


def _notice_body(source: str, const_name: str) -> str:
    """Plocka ut värdet (alla strängliteraler) för en ``export const`` notis
    fram till nästa ``;`` så jargong-låset bara granskar UI-texten — inte
    tekniska kommentarer/JSDoc på andra ställen i filen."""
    marker = f"{const_name} =\n"
    assert marker in source, f"{const_name} ska definieras i hosted-python-runtime.ts"
    return source.split(marker, 1)[1].split(";", 1)[0]


def test_hosted_banner_text_reflects_b199_v2() -> None:
    source = _read(RUNTIME_HELPER)
    enabled = _notice_body(source, "HOSTED_BUILD_ENABLED_NOTICE")
    local_only = _notice_body(source, "HOSTED_LOCAL_ONLY_NOTICE")
    notices = enabled + "\n" + local_only
    # Kundvänlig ton: notisen ska beskriva att sajter sparas och kan förfinas,
    # i plain svenska. Den får INTE läcka teknisk jargong till slutanvändaren.
    assert "sparas automatiskt" in enabled, (
        "HOSTED_BUILD_ENABLED_NOTICE ska ärligt säga att sajter sparas så att "
        "användaren kan komma tillbaka och förfina dem."
    )
    for jargon in (
        "Vercel Sandbox",
        "molnlagring",
        "run-historik",
        "Filträdet",
        "backend-runtime",
    ):
        assert jargon not in notices, (
            f"UI-notisen läcker teknisk jargong {jargon!r} till slutanvändaren "
            "— håll den hostade banner-texten kundvänlig och jargongfri."
        )
    for stale in ("tomma hostat", "försvinner"):
        assert stale not in notices, (
            f"Banner-texten påstår fortfarande {stale!r} — det är inte "
            "längre sant efter B199 v2."
        )
    assert "läser dock" not in notices
