"""Regression-tests för B157-follow-up — race i ``stopAndWaitPreviewServer``.

B157 (akut-fix ``adba139``) introducerade ``stopAndWaitPreviewServer``
för att stoppa en live ``next start``-process FÖRE
``build_site.py:copy_starter()`` försökte ``shutil.rmtree`` på
``node_modules``-mappen. Buggen som denna test täcker är ett
**reviewer-fynd post-adba139**:

  ``Promise.race([exited, timeoutPromise])`` resolverar omedelbart
  när ``timeoutPromise`` resolvar (efter att SIGKILL skickats), utan
  att vänta på faktiskt ``exit``-event från processen. Det bryter
  funktionens dokumenterade kontrakt att caller kan göra file-IO
  efter return — på Windows kan native ``.node``-binaries fortfarande
  vara file-låsta tills kerneln har reapat processen.

Fixen: efter SIGKILL skickats, vänta separat på ``exited``-promise
med en sekundär ``REAP_TIMEOUT_MS``-timeout (hard-floor 2s) innan
funktionen returnerar.

Testet är **strukturellt** — letar efter fix-mönster i source-filen
eftersom apps/viewser saknar en aktiv TS-test-runner. När en sådan
landas (Vitest/Node test runner-sprint) flyttas den faktiska
race-simuleringen dit.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_PREVIEW_SERVER = (
    REPO_ROOT / "apps" / "viewser" / "lib" / "local-preview-server.ts"
)


def _read_source() -> str:
    return LOCAL_PREVIEW_SERVER.read_text(encoding="utf-8")


def _stop_and_wait_body() -> str:
    """Returnera bara funktionsbodyn för ``stopAndWaitPreviewServer``.

    Vi vill inte att kommentarer eller jsdoc utanför funktionen
    triggar false positives. Funktionsstarten markeras av
    ``export async function stopAndWaitPreviewServer(`` och slutar
    vid första top-level ``}`` som matchar.
    """
    source = _read_source()
    start_match = re.search(
        r"export async function stopAndWaitPreviewServer\(",
        source,
    )
    assert start_match, (
        "Hittade inte ``stopAndWaitPreviewServer``-deklarationen i "
        "``apps/viewser/lib/local-preview-server.ts``. Filen kan ha "
        "refactor:ats — uppdatera detta test."
    )
    # Räkna brace-depth från ``{`` efter signature till matchande ``}``.
    body_start = source.find("{", start_match.end())
    assert body_start != -1
    depth = 0
    for i in range(body_start, len(source)):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[body_start : i + 1]
    raise AssertionError(
        "Kunde inte hitta matchande ``}`` för "
        "``stopAndWaitPreviewServer``-bodyn. Filen kan ha truncated "
        "eller saknad balansering."
    )


def test_b157_followup_waits_for_exit_after_sigkill() -> None:
    """Reviewer-fynd: efter SIGKILL måste vi vänta på exit-event.

    Den buggy versionen hade bara ``Promise.race([exited, timeoutPromise])``
    och returnerade direkt efter ``timeoutPromise`` resolvade (vilket
    sker omedelbart efter SIGKILL skickas). Fixen ska ha en separat
    väntan på ``exited`` efter SIGKILL — antingen en andra
    ``Promise.race`` eller motsvarande ``await exited``-konstruktion
    som blockar tills processen verkligen exitat (eller en sekundär
    reap-timeout träffat).
    """
    body = _stop_and_wait_body()

    # Bevis 1: vi måste skicka SIGKILL någonstans i bodyn (annars
    # är hela timeout-fallback-grenen borta — också en bugg).
    assert "SIGKILL" in body, (
        "``stopAndWaitPreviewServer`` saknar SIGKILL-fallback. "
        "Timeout-eskalering måste finnas för processer som vägrar SIGTERM."
    )

    # Bevis 2: efter SIGKILL-call måste det finnas en synkroniserings-
    # punkt där vi väntar på ``exited``-promise. Två godtagbara
    # mönster:
    #   (a) En andra ``Promise.race([exited, ...])`` efter SIGKILL
    #       (rekommenderat — låter oss sätta en hard-floor för reap).
    #   (b) Ett ensamt ``await exited`` efter SIGKILL (enklare men
    #       riskerar hänga om SIGKILL inte tar hem processen).
    #
    # Buggy versionen från ``adba139`` hade ENDAST en
    # ``Promise.race`` (innehållande ``timeoutPromise`` som resolvar
    # direkt efter SIGKILL). Vi kräver minst två race/await-punkter
    # som båda involverar ``exited``.
    race_with_exited = re.findall(
        r"Promise\.race\s*\(\s*\[\s*exited",
        body,
    )
    standalone_await_exited = re.findall(
        r"\bawait\s+exited\b",
        body,
    )
    sync_points = len(race_with_exited) + len(standalone_await_exited)
    assert sync_points >= 2, (
        "``stopAndWaitPreviewServer`` saknar separat exit-await efter "
        "SIGKILL. Den buggy versionen hade bara EN "
        "``Promise.race([exited, timeoutPromise])`` som synk-punkt — "
        "när timeout vann racet returnerades direkt efter SIGKILL utan "
        "att vänta på faktiskt exit-event. Lägg till en separat "
        "``Promise.race([exited, reapTimeout])`` (rekommenderat) eller "
        "``await exited`` efter SIGKILL-grenen.\n\n"
        f"Hittade {len(race_with_exited)} ``Promise.race(`exited``)`` + "
        f"{len(standalone_await_exited)} ``await exited`` i bodyn."
    )


def test_b157_followup_tracks_sigkill_state_for_reap_decision() -> None:
    """Fixen behöver veta OM SIGKILL skickades innan den väntar på reap.

    Annars måste vi alltid göra en sekundär ``await exited`` även
    när SIGTERM ensamt räckte för att stoppa processen — det skulle
    göra fast-path:en (process exitar inom ms) onödigt långsam.

    Strukturellt: leta efter ett boolean state (``sigkillSent`` eller
    motsvarande) som sätts inuti SIGKILL-grenen och senare avgör om
    reap-väntan ska köras.
    """
    body = _stop_and_wait_body()

    # Förenklad heuristik: en variabel som börjar med "sigkill" eller
    # "didKill" eller "reapNeeded" som muteras nära SIGKILL-callet.
    has_sigkill_flag = bool(
        re.search(
            r"\b(sigkill|didKill|reapNeeded|killSent)\w*\s*=\s*true\b",
            body,
            re.IGNORECASE,
        )
    )
    # Alternativt mönster: kollar exitCode efter race för att
    # avgöra om reap-väntan behövs (``if (child.exitCode === null)``
    # i en if/else-gren efter race).
    has_exitcode_check = bool(
        re.search(
            r"child\.exitCode\s*===?\s*null",
            body,
        )
    )
    assert has_sigkill_flag or has_exitcode_check, (
        "Fixen behöver spåra OM SIGKILL skickades (t.ex. via "
        "``sigkillSent = true`` i timeout-callbacken) eller kolla "
        "``child.exitCode`` direkt efter första racet. Annars kan vi "
        "inte skilja fast-path (SIGTERM räckte) från slow-path "
        "(SIGKILL-eskalering kräver reap-vänta)."
    )


def test_b157_followup_documents_reap_contract() -> None:
    """Fixen ska dokumentera kontraktet i kommentarerna.

    Den ursprungliga buggen var att kommentarerna SADE rätt sak
    ("Vi väntar fortfarande på exit-event efter SIGKILL") men koden
    inte gjorde det. Vi kräver att fix-komponenten kommenterar både
    VAD och VARFÖR — nästa agent ska inte kunna refactor:a tillbaka
    till buggy-formen utan att också radera kommentarerna.
    """
    body = _stop_and_wait_body()
    # Letar efter någon variant av "vänta på exit" + "SIGKILL" inom
    # samma bodyn. Behöver inte vara exakt formuleringen — bara
    # bevisen att intentet är dokumenterat i koden.
    has_intent_doc = bool(
        re.search(
            r"(reap|vänta(?:r)? på exit|wait for exit|exit-event efter SIGKILL)",
            body,
            re.IGNORECASE,
        )
    )
    assert has_intent_doc, (
        "``stopAndWaitPreviewServer`` saknar dokumentation av reap-"
        "kontraktet. Den ursprungliga B157-bugged versionen hade en "
        "kommentar som SADE rätt sak men kod som inte matchade. Lägg "
        "till en kommentar nära SIGKILL-grenen som förklarar varför "
        "vi väntar på exit-event efter SIGKILL (kernel reap-tid + "
        "Windows file-handle-release)."
    )


def test_b157_round3_uses_process_tree_kill_on_windows() -> None:
    """Round-3 reviewer-fynd: ``child.kill()`` på Windows räcker inte.

    Round 1 (akut, ``adba139``) + Round 2 (reap-fix, ``697cf4f``)
    löste timing-aspekten av B157 men missade rotorsaken: Node.js
    ``ChildProcess.kill()`` på Windows mappar internt till
    ``TerminateProcess(handle)`` som BARA dödar direct PID, inte
    descendants. För Sajtbyggarens preview-servrar är processträdet:

        npx (parent, i Viewser:s servers-map)
          └─ next start (barn, håller fil-låsen på .node-binaries)

    ``child.kill("SIGKILL")`` killar bara npx-shellen — barnet lever
    vidare och håller fil-lås på ``next-swc.win32-x64-msvc.node``.

    Verifierad reproduktion 2026-05-28 ~01:08 (PID 31472 ``next start``
    levde efter att Viewser:s ``child.kill()`` skickats till PID 27976
    ``npx``-parent).

    Round-3-fixen: ``killProcessTree``-helper som på Windows spawnar
    ``taskkill /PID <pid> /T /F``. ``/T`` = "tree" (alla descendants).
    På POSIX (Linux/macOS) använder den vanlig ``child.kill(signal)``
    eftersom process groups respekteras naturligt där.

    Detta test låser strukturellt att tree-kill-mönstret finns kvar
    så framtida agenter inte kan refactor:a bort det utan att också
    radera taskkill-anropet och dess kommentar.
    """
    source = _read_source()

    # Bevis 1: ``killProcessTree``-helper finns deklarerad någonstans
    # i filen (eller annan helper med liknande namn — vi accepterar
    # ``killProcessTree``, ``treeKill``, ``killTree``).
    has_helper = bool(
        re.search(
            r"\b(killProcessTree|treeKill|killTree)\s*\(",
            source,
        )
    )
    assert has_helper, (
        "``local-preview-server.ts`` saknar tree-kill-helper. Round 3 "
        "kräver en funktion (förslagsvis ``killProcessTree``) som på "
        "Windows använder ``taskkill /T /F`` istället för "
        "``child.kill()`` direkt."
    )

    # Bevis 2: ``taskkill`` med ``/T`` (tree-flag) spawnas någonstans.
    # ``/T`` är det avgörande Windows-flagget — utan det dödas bara
    # direct PID och vi är tillbaka i B157-orphan-territoriet.
    has_taskkill_tree = bool(
        re.search(
            r'taskkill[^\n]*"/T"',
            source,
        )
    )
    assert has_taskkill_tree, (
        "``local-preview-server.ts`` spawnar inte ``taskkill /T``. "
        "Utan ``/T``-flagget dödar taskkill bara direct PID, inte "
        "process-trädet — exakt det som B157 round 3 fixar. Lägg "
        "till ``/T`` (tree) och gärna ``/F`` (force) i taskkill-args."
    )

    # Bevis 3: helpern måste användas från ``stopAndWaitPreviewServer``
    # (annars är den död kod). Antingen direktanrop eller via
    # Windows-fast-path-grenen som ``await``:ar helpern.
    body = _stop_and_wait_body()
    has_helper_call = bool(
        re.search(
            r"\b(killProcessTree|treeKill|killTree)\s*\(",
            body,
        )
    )
    assert has_helper_call, (
        "``stopAndWaitPreviewServer`` anropar inte tree-kill-helpern. "
        "Helpern är död kod om den inte aktiveras från den faktiska "
        "shutdown-pathen. Lägg in ``await killProcessTree(child, ...)`` "
        "i Windows-grenen (där ``process.platform === \"win32\"``)."
    )


def test_read_active_build_dir_rejects_present_nonstring_buildpath() -> None:
    """``readActiveBuildDir`` måste spegla ``immutable_builds.read_active_build_dir``.

    B-Codex 2026-06-01 (TS/Python-paritetslucka): Python avvisar en närvarande
    ``buildPath`` som inte exakt är ``builds/<activeBuildId>`` oavsett typ
    (``build_path is not None and build_path != ...``). TS gated tidigare check:en
    på ``typeof buildPath === "string"``, så ett närvarande icke-string-värde
    (number/object i en manipulerad/korrupt ``current.json``) slank igenom. Den
    här strukturella regressionen låser att TS nu avvisar alla närvarande
    icke-matchande värden (bara ``undefined``/``null`` släpps igenom).
    """
    source = _read_source()
    # Den gamla string-only-gaten får inte finnas kvar.
    assert 'typeof buildPath === "string" && buildPath !==' not in source, (
        "``readActiveBuildDir`` gatar fortfarande buildPath-mismatch-check:en "
        'på ``typeof buildPath === "string"``, vilket släpper igenom ett '
        "närvarande icke-string buildPath. Spegla Python: avvisa varje "
        "närvarande buildPath som inte är exakt ``builds/${activeBuildId}``."
    )
    # Spegel-mönstret: avvisa när närvarande (undefined/null tillåtet) + mismatch.
    assert "buildPath !== undefined" in source and "buildPath !== null" in source, (
        "``readActiveBuildDir`` måste avvisa ett närvarande buildPath "
        "(undefined/null tillåtet) som inte är ``builds/${activeBuildId}`` — "
        "spegla ``immutable_builds.read_active_build_dir``."
    )
