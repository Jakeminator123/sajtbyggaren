"""Tier 2 warm-sandbox reuse source-locks (ADR 0041).

Sandbox-preview kräver Vercel OIDC + auth, så vi kan inte köra en live-sandbox
i CI/agent-miljön. Precis som #263-testerna (pre-built upload, OIDC-refresh,
timings) låser vi i stället BETEENDET genom att läsa källan
(``apps/viewser/lib/vercel-sandbox-runner.ts``) och asserta mönstren. Live-
mätning av vinsten görs av operatören (se PR-beskrivningen).

Det som låses:
  1. Återanvändning är opt-in + kill-switchad (``VIEWSER_SANDBOX_REUSE``,
     default AV via ``=== "1"`` — aldrig ``!== "0"`` som skulle flippa default PÅ).
  2. Reconnect använder ``Sandbox.get({ ..., resume: false })`` (PR #156-lärdomen:
     i ``@vercel/sandbox`` v2 är ``resume`` default ``true`` → utan flaggan
     återupplivas en utgången sandbox tyst och rapporterar ``pending``).
  3. Endast en ``running`` sandbox återanvänds (``REUSABLE_SANDBOX_STATUSES``);
     allt annat (inkl. utgången/okänd) faller tillbaka.
  4. Det deterministiska reuse-namnet saknar ``Date.now()``; det icke-återanvända
     (efemära) namnet behåller ``Date.now()`` (oförändrat beteende).
  5. Miss/utgången faller tillbaka på den fulla vägen
     (``createSandboxPreview`` → ``createSandboxPreviewAttempt``).
  6. Reuse-vägen hoppar ``Sandbox.create`` men kör reconcile-``npm install``.
  7. ``reused``-fältet exponeras i timings (``true`` på reuse, ``false`` på full väg).
  8. Immutable-build-kontraktet: runnern muterar aldrig disk (ingen
     ``writeFileSync``/``rmSync``).
  9. Produktrouten (preview-runtime-server.ts) HOPPAR ``stopSandboxSessionForSite``
     i reuse-läge (``if (!isSandboxReuseEnabled())``) så den varma sandboxen inte
     dödas; default AV ⇒ stoppet körs som förr (ADR 0041 route-beslut).
 10. Namn-kollisionsstrategin: ren miss (``Sandbox.get`` kastar) → deterministiskt
     bootstrap-namn (ingen ephemeral-markering); funnen-men-död → stop/delete +
     ``pendingEphemeralFallbackSites.add`` → fulla vägen använder tidsstämplat namn.
"""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR

RUNNER_PATH = VIEWSER_DIR / "lib" / "vercel-sandbox-runner.ts"
WIRING_PATH = VIEWSER_DIR / "lib" / "preview-runtime-server.ts"


def _runner_text() -> str:
    return RUNNER_PATH.read_text(encoding="utf-8")


def _slice(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    assert start != -1, f"kunde inte hitta start-markören {start_marker!r} i runnern."
    end = text.find(end_marker, start + len(start_marker))
    assert end != -1, f"kunde inte hitta slut-markören {end_marker!r} efter {start_marker!r}."
    return text[start:end]


@pytest.mark.tooling
def test_reuse_is_opt_in_killswitch_default_off() -> None:
    """Lås 1: ``VIEWSER_SANDBOX_REUSE`` är opt-in, default AV. Grinden ska vara
    ``process.env[REUSE_ENV] === "1"`` så bara ett explicit ``1`` slår på den —
    INTE ``!== "0"`` (som skulle flippa default till PÅ och regressa dagens flöde).
    """
    text = _runner_text()

    assert 'REUSE_ENV = "VIEWSER_SANDBOX_REUSE"' in text, (
        "vercel-sandbox-runner.ts saknar kill-switch-env "
        "``REUSE_ENV = \"VIEWSER_SANDBOX_REUSE\"`` (ADR 0041)."
    )
    assert re.search(r'process\.env\[REUSE_ENV\]\s*===\s*["\']1["\']', text), (
        "Återanvändning måste vara opt-in: grinden ska vara "
        '``process.env[REUSE_ENV] === "1"`` (default AV).'
    )
    # Negativ: reuse-grinden får ALDRIG vara ``!== "0"`` (default PÅ-mönstret som
    # Tier 1:s UPLOAD_BUILT använder) — det skulle regressa dagens flöde.
    assert not re.search(r'process\.env\[REUSE_ENV\]\s*!==\s*["\']0["\']', text), (
        "Reuse-grinden får inte vara ``process.env[REUSE_ENV] !== \"0\"`` — "
        "det skulle göra Tier 2 default PÅ och bryta kravet på noll regression."
    )


@pytest.mark.tooling
def test_reconnect_uses_resume_false() -> None:
    """Lås 2 (PR #156-lärdomen): reconnect MÅSTE anropa
    ``Sandbox.get({ ..., resume: false })``. I ``@vercel/sandbox`` v2 är
    ``resume`` default ``true`` → utan ``resume: false`` återupplivas en utgången
    sandbox tyst och rapporterar ``pending`` i stället för ``stopped``/``expired``.
    """
    text = _runner_text()

    assert re.search(r"Sandbox\.get\(\{[\s\S]{0,120}?resume:\s*false", text), (
        "Reconnect-vägen måste anropa ``Sandbox.get({ ..., resume: false })`` "
        "(PR #156-lärdomen). Utan flaggan återupplivas en utgången sandbox tyst."
    )
    # Negativ: reuse-vägen får aldrig återansluta med ``resume: true``.
    assert not re.search(r"Sandbox\.get\(\{[\s\S]{0,120}?resume:\s*true", text), (
        "``Sandbox.get`` får aldrig anropas med ``resume: true`` i reuse-vägen — "
        "det är exakt den tysta återupplivningen #156-boten fångade."
    )


@pytest.mark.tooling
def test_only_running_sandbox_is_reused() -> None:
    """Lås 3: endast en ``running`` sandbox återanvänds. SDK:ns statusenum är
    ``aborted|failed|pending|running|stopping|stopped|snapshotting``; reuse-vägen
    guardar på en konservativ allowlist och faller tillbaka på allt annat
    (inkl. utgången/okänd status).
    """
    text = _runner_text()

    assert re.search(
        r'REUSABLE_SANDBOX_STATUSES\s*=\s*new Set<string>\(\s*\[\s*"running"\s*\]\s*\)',
        text,
    ), (
        "vercel-sandbox-runner.ts måste deklarera "
        '``REUSABLE_SANDBOX_STATUSES = new Set<string>(["running"])`` — bara en '
        "körande sandbox är säker att återanvända."
    )
    assert re.search(r"!REUSABLE_SANDBOX_STATUSES\.has\(status\)", text), (
        "Reuse-vägen måste guarda på ``!REUSABLE_SANDBOX_STATUSES.has(status)`` "
        "och falla tillbaka när status inte är ``running`` (utgången/okänd → miss)."
    )


@pytest.mark.tooling
def test_reuse_name_is_deterministic_without_timestamp() -> None:
    """Lås 4: det deterministiska reuse-namnet saknar ``Date.now()`` (så
    ``Sandbox.get`` kan återansluta), medan det efemära icke-reuse-namnet behåller
    ``Date.now()`` (oförändrat per-preview-unikt beteende).
    """
    text = _runner_text()

    reuse_fn = _slice(text, "function reuseSandboxName", "\nfunction ")
    assert "`sajtbyggaren-preview-${slug(siteId)}`" in reuse_fn, (
        "``reuseSandboxName`` ska returnera det deterministiska namnet "
        "``sajtbyggaren-preview-${slug(siteId)}`` (per sajt, utan tidsstämpel)."
    )
    assert "Date.now()" not in reuse_fn, (
        "``reuseSandboxName`` får INTE innehålla ``Date.now()`` — namnet måste vara "
        "deterministiskt per sajt så reconnect hittar samma varma sandbox."
    )

    ephemeral_fn = _slice(text, "function ephemeralSandboxName", "\nfunction ")
    assert "Date.now()" in ephemeral_fn, (
        "``ephemeralSandboxName`` (icke-reuse-läget) ska behålla ``Date.now()`` "
        "så varje preview får ett unikt namn — dagens oförändrade beteende."
    )


@pytest.mark.tooling
def test_miss_falls_back_to_full_create_path() -> None:
    """Lås 5: reuse-grenen ligger FÖRE den fulla vägen i ``createSandboxPreview``,
    och ``tryReuseSandboxPreview`` returnerar ``null`` vid miss/utgången så
    ``createSandboxPreview`` ärligt faller tillbaka på
    ``createSandboxPreviewAttempt`` (dagens fulla väg, oförändrad).
    """
    text = _runner_text()

    create_fn = _slice(
        text,
        "export async function createSandboxPreview(",
        "async function createSandboxPreviewAttempt(",
    )
    gate_idx = create_fn.find("isSandboxReuseEnabled()")
    reuse_call_idx = create_fn.find("tryReuseSandboxPreview(request)")
    full_path_idx = create_fn.find("createSandboxPreviewAttempt(request, true)")
    assert gate_idx != -1, "createSandboxPreview måste grena på ``isSandboxReuseEnabled()``."
    assert reuse_call_idx != -1, (
        "createSandboxPreview måste anropa ``tryReuseSandboxPreview(request)`` i reuse-läge."
    )
    assert full_path_idx != -1, (
        "createSandboxPreview måste fortsatt anropa ``createSandboxPreviewAttempt(request, true)`` "
        "som fulla vägen."
    )
    assert gate_idx < reuse_call_idx < full_path_idx, (
        "Ordningen måste vara: ``isSandboxReuseEnabled()``-grind → ``tryReuseSandboxPreview`` → "
        "(vid miss) ``createSandboxPreviewAttempt(request, true)``. Reuse är ett "
        "för-försök; fulla vägen är fallbacken."
    )
    assert re.search(r"if\s*\(\s*reused\s*\)\s*return\s+reused\s*;", create_fn), (
        "Vid träff ska createSandboxPreview returnera reuse-resultatet "
        "(``if (reused) return reused;``); annars faller den igenom till fulla vägen."
    )

    reuse_fn = _slice(
        text,
        "async function tryReuseSandboxPreview(",
        "\nexport async function stopSandboxPreview(",
    )
    assert reuse_fn.count("return null;") >= 3, (
        "``tryReuseSandboxPreview`` måste returnera ``null`` på alla miss-vägar "
        "(saknad källa/SDK/auth, ej hittad, ej running, install-fel, timeout) så "
        "fulla vägen tar över. Hittade färre ``return null;`` än väntat."
    )


@pytest.mark.tooling
def test_reuse_skips_create_but_runs_reconcile_install() -> None:
    """Lås 6: reuse-vägen hoppar ``Sandbox.create`` (vinsten) men kör en
    reconcile-``npm install`` (nära-no-op på oförändrad lockfile, men korrekt om
    beroenden ändrats) och startar om servern.
    """
    text = _runner_text()
    reuse_fn = _slice(
        text,
        "async function tryReuseSandboxPreview(",
        "\nexport async function stopSandboxPreview(",
    )

    assert "Sandbox.create(" not in reuse_fn, (
        "``tryReuseSandboxPreview`` får INTE anropa ``Sandbox.create(...)`` — att hoppa "
        "create (och kall install) är hela poängen med Tier 2-återanvändning. "
        "(Locket träffar själva anropet, inte en text-referens i en kommentar.)"
    )
    assert "Sandbox.get(" in reuse_fn, (
        "``tryReuseSandboxPreview`` måste återansluta via ``Sandbox.get(...)``."
    )
    assert '"install"' in reuse_fn, (
        "Reuse-vägen måste köra en reconcile-``npm install`` (korrekt om beroenden "
        "ändrats; no-op på oförändrad lockfile)."
    )
    assert re.search(r'"next",\s*"start"', reuse_fn), (
        "Reuse-vägen måste starta om servern med ``next start`` mot de nya filerna."
    )


@pytest.mark.tooling
def test_reused_flag_exposed_in_timings() -> None:
    """Lås 7: ``reused`` exponeras i timings — ``true`` på återanvändning,
    ``false`` på fulla vägen — så vinsten syns i preview-svaret (timings flödar
    oförändrat upp till POST /api/preview).
    """
    text = _runner_text()
    assert "reused: true" in text, (
        "Reuse-vägen måste sätta ``reused: true`` i timings."
    )
    assert "reused: false" in text, (
        "Fulla vägen måste sätta ``reused: false`` i timings."
    )


@pytest.mark.tooling
def test_runner_never_mutates_disk() -> None:
    """Lås 8: runnern (inkl. reuse-vägen) LÄSER bara disk — den immutable
    build-katalogen muteras aldrig (ingen ``writeFileSync``/``rmSync``). Filer
    skickas till sandboxen via SDK:ns ``writeFiles``, inte till lokal disk.
    """
    text = _runner_text()
    assert "writeFileSync" not in text and "rmSync" not in text, (
        "vercel-sandbox-runner.ts får aldrig mutera disk (B157 nivå 4) — "
        "reuse-vägen laddar upp via ``sandbox.writeFiles``, inte ``writeFileSync``."
    )


@pytest.mark.tooling
def test_route_gate_skips_stop_in_reuse_mode_default_unchanged() -> None:
    """Lås 9 (ADR 0041 route-beslut): DI-wiringen i preview-runtime-server.ts
    måste HOPPA ``stopSandboxSessionForSite(siteId)`` i reuse-läge — annars
    stoppar produktrouten just den varma sandbox reuse-vägen vill återanvända.
    Bakom samma default-AV-flagga: när reuse är av körs stoppet som förr
    (byte-identiskt). ``build-runner.ts`` lämnas orört (separat lås nedan).
    """
    text = WIRING_PATH.read_text(encoding="utf-8")

    assert re.search(
        r'import\s*\{[^}]*\bisSandboxReuseEnabled\b[^}]*\}\s*from\s*'
        r'["\']\./vercel-sandbox-runner["\']',
        text,
    ), (
        "preview-runtime-server.ts måste importera ``isSandboxReuseEnabled`` från "
        "``./vercel-sandbox-runner`` (en sanningskälla för reuse-flaggan)."
    )
    assert re.search(
        r"if\s*\(\s*!isSandboxReuseEnabled\(\)\s*\)\s*\{[\s\S]{0,160}?"
        r"stopSandboxSessionForSite\(siteId\)",
        text,
    ), (
        "preview-runtime-server.ts måste grena ``if (!isSandboxReuseEnabled()) "
        "{ await stopSandboxSessionForSite(siteId); }`` — i reuse-läge hoppas "
        "stoppet, annars (default AV) körs det som förr."
    )


@pytest.mark.tooling
def test_runner_exports_reuse_flag_for_wiring() -> None:
    """Lås 9-stöd: runnern exporterar ``isSandboxReuseEnabled`` så wiringen kan
    dela exakt samma flagg-grind (ingen andra-kopia av env-läsningen)."""
    text = _runner_text()
    assert re.search(r"export function isSandboxReuseEnabled\(\)", text), (
        "vercel-sandbox-runner.ts måste EXPORTERA ``isSandboxReuseEnabled()`` så "
        "preview-runtime-server.ts kan gata route-stoppet på samma flagga."
    )


@pytest.mark.tooling
def test_name_collision_strategy_locks_both_miss_branches() -> None:
    """Lås 10 (ADR 0041 namn-kollisionsstrategi): två miss-typer ger olika
    fallback-namn så ett create aldrig race:ar mot en just-raderad record.

      - REN miss (``Sandbox.get`` kastar): catch returnerar null UTAN att markera
        ephemeral → fulla vägen bootstrappar det DETERMINISTISKA namnet.
      - FUNNEN-MEN-DÖD (status ≠ running): ``pendingEphemeralFallbackSites.add`` +
        best-effort ``safeStopAndDelete`` → fulla vägen använder TIDSSTÄMPLAT namn.

    Namnvalet i ``createSandboxPreviewAttempt`` styrs av samma per-sajt-set.
    """
    text = _runner_text()

    assert "const pendingEphemeralFallbackSites = new Set<string>()" in text, (
        "Runnern måste deklarera den per-sajt-privata ``pendingEphemeralFallbackSites`` "
        "(Set) som bryggar miss-typ → fallback-namn."
    )

    # Namnvalet styrs av set:et (ephemeral när set har sajten ELLER reuse är av).
    assert re.search(
        r"pendingEphemeralFallbackSites\.has\(request\.siteId\)", text
    ), (
        "createSandboxPreviewAttempt måste välja namn via "
        "``pendingEphemeralFallbackSites.has(request.siteId)``."
    )

    reuse_fn = _slice(
        text,
        "async function tryReuseSandboxPreview(",
        "\nexport async function stopSandboxPreview(",
    )

    # FUNNEN-MEN-DÖD: markera ephemeral + städa.
    found_dead = re.search(
        r"!REUSABLE_SANDBOX_STATUSES\.has\(status\)\s*\)\s*\{[\s\S]{0,400}?"
        r"pendingEphemeralFallbackSites\.add\(request\.siteId\)[\s\S]{0,200}?"
        r"safeStopAndDelete\(sandbox\)",
        reuse_fn,
    )
    assert found_dead, (
        "Funnen-men-död-grenen måste ``pendingEphemeralFallbackSites.add(request.siteId)`` "
        "OCH ``safeStopAndDelete(sandbox)`` innan den returnerar null (tidsstämplad fallback)."
    )

    # REN miss: catch-grenen efter Sandbox.get returnerar null UTAN att markera.
    clean_miss = _slice(
        reuse_fn,
        "sandbox = await Sandbox.get(",
        "const status =",
    )
    assert "return null;" in clean_miss, (
        "Catch-grenen för en ren miss (Sandbox.get kastar) måste returnera null."
    )
    assert "pendingEphemeralFallbackSites.add" not in clean_miss, (
        "En REN miss får INTE markera ephemeral — fulla vägen ska bootstrappa det "
        "DETERMINISTISKA namnet (ingen kollision möjlig när inget finns)."
    )


@pytest.mark.tooling
def test_transient_reuse_failures_mark_ephemeral_fallback() -> None:
    """Lås (Vercel-bot-fynd på PR #276): ett TRANSIENT fel på en RUNNING
    sandbox (install-fel, ready-timeout, oväntad throw) lämnar recorden med
    det deterministiska namnet kvar efter ``safeStop`` — så varje sådan gren
    måste ``pendingEphemeralFallbackSites.add(request.siteId)`` innan den
    returnerar null, annars kolliderar fulla vägens ``Sandbox.create`` med
    namnet. Låser: VARJE ``safeStop(sandbox)`` i reuse-funktionen föregås av
    ephemeral-markeringen (clean-miss-grenen rör ingen safeStop och förblir
    omarkerad per lås 10)."""
    text = _runner_text()
    reuse_fn = _slice(
        text,
        "async function tryReuseSandboxPreview(",
        "\nexport async function stopSandboxPreview(",
    )
    stops = [m.start() for m in re.finditer(r"await safeStop\(sandbox\);", reuse_fn)]
    assert len(stops) >= 3, (
        "Reuse-funktionen ska ha minst tre transienta felgrenar med "
        "``await safeStop(sandbox);`` (install-fel, ready-timeout, catch)."
    )
    for stop_idx in stops:
        preceding = reuse_fn[max(0, stop_idx - 400) : stop_idx]
        assert "pendingEphemeralFallbackSites.add(request.siteId)" in preceding, (
            "En transient felgren anropar ``safeStop(sandbox)`` utan att först "
            "markera ``pendingEphemeralFallbackSites.add(request.siteId)`` — "
            "fulla vägen skapar då med det deterministiska namnet medan den "
            "stoppade recorden finns kvar → namnkollision (Vercel-bot-fyndet)."
        )


@pytest.mark.tooling
def test_reuse_totalms_measured_before_sandbox_get() -> None:
    """Lås (ADR 0041 §mätbarhet): reuse-vägens ``totalMs`` mäts från FÖRE
    ``Sandbox.get`` så den är jämförbar med fulla vägens ``totalMs`` (som mäts
    från före ``Sandbox.create``)."""
    text = _runner_text()
    reuse_fn = _slice(
        text,
        "async function tryReuseSandboxPreview(",
        "\nexport async function stopSandboxPreview(",
    )
    t_reuse_idx = reuse_fn.find("const tReuse = Date.now()")
    get_idx = reuse_fn.find("Sandbox.get(")
    total_idx = reuse_fn.find("Date.now() - tReuse")
    assert t_reuse_idx != -1 and get_idx != -1 and total_idx != -1, (
        "Reuse-vägen måste ha ``const tReuse = Date.now()``, ett ``Sandbox.get(`` "
        "och ``Date.now() - tReuse``."
    )
    assert t_reuse_idx < get_idx, (
        "``tReuse`` måste sättas FÖRE ``Sandbox.get`` så totalMs är jämförbar med "
        "fulla vägens totalMs (mätt från före Sandbox.create)."
    )
