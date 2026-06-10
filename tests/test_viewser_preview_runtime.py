"""Viewser preview runtime: viewer panel, preview route, Vercel sandbox, dispatcher."""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import REPO_ROOT, VIEWSER_DIR


@pytest.mark.tooling
def test_viewer_panel_drives_preview_mode_through_descriptor() -> None:
    """Bite C (commit ee68add): ViewerPanel får INTE längre läsa
    ``NEXT_PUBLIC_VIEWSER_PREVIEW_MODE`` rått och härleda IS_*-booleanerna
    via ``=== "..."`` mot en lokal lower-cased sträng. Den client-säkra
    ``resolvePreviewRuntimeDescriptor`` (@preview-runtime) ska vara EN
    delad mode-normaliserare med host-transporten (``scripts/dev.mjs``).

    Fyra lås:
      1. ``resolvePreviewRuntimeDescriptor`` importeras från
         ``@preview-runtime``.
      2. Descriptorn drivs av ``process.env.NEXT_PUBLIC_VIEWSER_PREVIEW_MODE``
         (med behållen ``?? "local-next"``-default så en osatt env beter
         sig EXAKT som förr).
      3. KRITISKT — ``auto`` ≠ ``local-next``: ``IS_LOCAL_NEXT_MODE`` måste
         härledas ur ``PREVIEW_RUNTIME.rawMode`` (som bevarar distinktionen),
         ALDRIG ur ``.kind`` (som kollapsar local-next/auto/local till
         ``"local"`` och därmed skulle flippa ``auto`` till local-next och
         tappa StackBlitz-fallbacken).
      4. Det gamla råa mönstret
         ``const VIEWSER_PREVIEW_MODE = (...).toLowerCase()`` får inte vara
         kvar — annars finns två konkurrerande normaliserare igen.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    # Lock 1: importen från @preview-runtime.
    assert re.search(
        r'import\s*\{\s*resolvePreviewRuntimeDescriptor\s*\}\s*from\s*["\']@preview-runtime["\']',
        text,
    ), (
        "viewer-panel.tsx måste importera ``resolvePreviewRuntimeDescriptor`` "
        "från ``@preview-runtime`` (Bite C, ee68add) i stället för att läsa "
        "preview-mode rått."
    )

    # Lock 2: descriptorn drivs av NEXT_PUBLIC_VIEWSER_PREVIEW_MODE med
    # behållen local-next-default.
    assert re.search(
        r"resolvePreviewRuntimeDescriptor\(\s*process\.env\."
        r'NEXT_PUBLIC_VIEWSER_PREVIEW_MODE\s*\?\?\s*["\']local-next["\']',
        text,
    ), (
        "viewer-panel.tsx måste driva descriptorn med "
        "``resolvePreviewRuntimeDescriptor(process.env."
        "NEXT_PUBLIC_VIEWSER_PREVIEW_MODE ?? 'local-next')``. ``?? 'local-next'`` "
        "är beteende-bevarande: descriptorns egna tomma default är ``'local'``, "
        "men en osatt env ska fortsätta bete sig som local-next (COEP av, "
        "ingen StackBlitz-fallback)."
    )

    # Lock 3: auto ≠ local-next — IS_LOCAL_NEXT_MODE härleds ur rawMode.
    assert re.search(
        r'const\s+IS_LOCAL_NEXT_MODE\s*=\s*PREVIEW_RUNTIME\.rawMode\s*===\s*["\']local-next["\']',
        text,
    ), (
        "viewer-panel.tsx måste härleda ``IS_LOCAL_NEXT_MODE`` ur "
        "``PREVIEW_RUNTIME.rawMode === 'local-next'`` (INTE ur ``.kind``). "
        "``kind`` kollapsar local-next/auto/local till ``'local'`` — om "
        "IS_LOCAL_NEXT_MODE härleddes ur ``.kind`` skulle ``auto`` felaktigt "
        "flippas till local-next och tappa sin StackBlitz-fallback. "
        "``rawMode`` bevarar distinktionen auto ≠ local-next."
    )
    # Negativ guard: IS_LOCAL_NEXT_MODE får inte härledas ur ``.kind``.
    assert not re.search(
        r"const\s+IS_LOCAL_NEXT_MODE\s*=\s*PREVIEW_RUNTIME\.kind\b",
        text,
    ), (
        "viewer-panel.tsx: ``IS_LOCAL_NEXT_MODE`` får ALDRIG härledas ur "
        "``PREVIEW_RUNTIME.kind`` — det skulle slå ihop ``auto`` med "
        "``local-next`` (kind-kollaps) och bryta StackBlitz-fallbacken."
    )

    # Lock 4: det gamla råa env-mönstret är borta.
    assert not re.search(
        r"const\s+VIEWSER_PREVIEW_MODE\s*=\s*\(",
        text,
    ), (
        "viewer-panel.tsx får inte längre deklarera "
        "``const VIEWSER_PREVIEW_MODE = (...).toLowerCase()`` — den råa "
        "env-läsningen ersätts av resolvePreviewRuntimeDescriptor så klient "
        "och host delar en enda mode-normaliserare."
    )


@pytest.mark.tooling
def test_next_config_trusts_dispatcher_env_over_argv_for_https_check() -> None:
    """B145: ``process.argv`` är opålitlig under Turbopack — config laddas
    i worker-processer vars argv inte ärver parent-processens flaggor.
    Det gav falsk ``--experimental-https saknas``-varning i transport-
    mismatch-checken trots att dispatchern startat ``next dev`` med
    flaggan.

    Fix: ``next.config.ts`` konsulterar primärt
    ``process.env.VIEWSER_DISPATCHER_HTTPS === "1"`` (env-var som
    ``scripts/dev.mjs`` sätter när dispatchern valt https-grenen) och
    faller tillbaka till argv-checken för operatörer som kör
    ``next dev --experimental-https`` direkt utan dispatchern.

    Den dispatcher-managed env-varianten är auktoritativ signal — argv
    fungerar bara som fallback för manuell körning.
    """
    text = (VIEWSER_DIR / "next.config.ts").read_text(encoding="utf-8")
    pattern = re.compile(
        r"process\s*\.\s*env\s*\.\s*VIEWSER_DISPATCHER_HTTPS\s*===\s*[\"']1[\"']",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "next.config.ts: HTTPS-checken måste läsa "
        '``process.env.VIEWSER_DISPATCHER_HTTPS === "1"`` primärt — '
        "``process.argv``-grenen ger false-positiva varningar i "
        "Turbopack-workers vars argv inte ärver parent-processens "
        "flaggor (B145)."
    )


@pytest.mark.tooling
def test_dev_dispatcher_exports_https_signal_to_child() -> None:
    """Spegelfix till next.config.ts:s VIEWSER_DISPATCHER_HTTPS-check.
    ``scripts/dev.mjs`` MÅSTE exportera ``VIEWSER_DISPATCHER_HTTPS``
    baserat på ``useHttps`` så next.config.ts ser auktoritativ signal
    om dispatchern valt https-transport. Utan denna export ger
    transport-mismatch-checken false-positiva varningar i Turbopack-
    workers även när allt är korrekt konfigurerat.
    """
    text = (VIEWSER_DIR / "scripts" / "dev.mjs").read_text(encoding="utf-8")
    pattern = re.compile(
        r"VIEWSER_DISPATCHER_HTTPS\s*:\s*useHttps\s*\?\s*[\"']1[\"']\s*:\s*[\"']0[\"']",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "scripts/dev.mjs: child-env måste sätta "
        '``VIEWSER_DISPATCHER_HTTPS: useHttps ? "1" : "0"`` så '
        "next.config.ts kan verifiera transport-valet utan argv-"
        "gissning. Speglar den nya check:en i next.config.ts (B145)."
    )


@pytest.mark.tooling
def test_stackblitz_preview_keeps_containerref_mounted_across_status_transitions() -> None:
    """Stuck-state guard (flyttad till stackblitz-preview.tsx, ADR 0033):
    StackBlitz-embedden mountar in i en ``<div ref={containerRef}>``. Görs
    den divden conditional (t.ex. avmonteras vid loading/fallback/error)
    faller ``containerRef.current`` till null och effekten kan inte
    re-embeda vid nästa runId-byte (effekten har bara ``[runId]`` som dep).

    Tidigare bodde detta i ``viewer-panel.tsx`` och toggla:de mot
    ``unavailable``. Efter bundle-bloat-spliten äger ``StackblitzPreview``
    sin egen ``status``-state-maskin, så ref-divden måste vara
    ALWAYS-MOUNTED och bara döljas via Tailwind utifrån ``status``.

    Source-lock både negativa mönstret (ingen ternary-swap som avmonterar
    ref:en) och positiva mönstret (ref-divden styrs av ``status`` via ett
    observerbart JSX-attribut) så en framtida refactor inte regredierar.
    """
    text = (VIEWSER_DIR / "components" / "stackblitz-preview.tsx").read_text(
        encoding="utf-8"
    )

    # Negative: containerRef-div must NOT sit as the else-branch of a
    # `status... ? (...) : (<div ref={containerRef}>)` ternary. That
    # pattern unmounts the ref whenever status flips.
    forbidden = re.compile(
        r"status[\s\S]{0,40}?\?\s*\([\s\S]{0,400}?\)\s*:\s*\(\s*<div\s+ref=\{containerRef\}",
        re.MULTILINE,
    )
    assert not forbidden.search(text), (
        "stackblitz-preview.tsx: containerRef-div får inte sitta i else-grenen "
        "av en `status ? ... : <div ref>` ternary - det avmonterar ref:en och "
        "låser embedden i stuck state vid nästa runId-byte (effekten har bara "
        "`[runId]` som dep)."
    )

    # Positive (beteende, inte exakt syntax): containerRef måste vara
    # always-mounted via en `<div ... ref={containerRef} ... />` som finns
    # OAVSETT `status`-state, och visibility måste styras av `status` via
    # något observerbart JSX-attribut (className-toggle, cn(...), etc.).
    ref_element = re.search(
        r"<div\b[^>]*\bref=\{containerRef\}[^>]*/?>",
        text,
    )
    assert ref_element, (
        "stackblitz-preview.tsx: ingen `<div ... ref={containerRef} ... />` "
        "hittades. Always-mounted pattern kräver en self-closing eller "
        "kort JSX-tag med ref={containerRef}."
    )
    assert "status" in ref_element.group(0), (
        "stackblitz-preview.tsx: ref-div måste referera till `status` i "
        "ett JSX-attribut (t.ex. className-toggle som döljer den tills "
        "`status.kind === 'embedded'`). Det signalerar att status styr "
        "visibility utan att avmontera ref:en. Hittad ref-div:\n"
        f"{ref_element.group(0)!r}"
    )


@pytest.mark.tooling
def test_stackblitz_preview_guards_cancelled_after_dynamic_import_and_embed() -> None:
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
    appear between the StackBlitz import and the success terminator.

    Bundle-bloat-fix (ADR 0033): embedden bor numera i
    ``stackblitz-preview.tsx`` (lazy via next/dynamic). Success-path-
    terminatorn är ``setStatus({ kind: "embedded" })`` (StackblitzPreview:s
    egen state-maskin) i stället för ViewerPanel:s gamla ``setLoading(false)``.
    """
    text = (VIEWSER_DIR / "components" / "stackblitz-preview.tsx").read_text(
        encoding="utf-8"
    )

    block = re.search(
        r'const sdk = \(await import\("@stackblitz/sdk"\)\)[\s\S]*?'
        r'setStatus\(\{\s*kind:\s*"embedded"\s*\}\);\s*\n\s*\}\s*catch',
        text,
    )
    assert block, (
        "stackblitz-preview.tsx: kunde inte hitta success-path-blocket från "
        "StackBlitz-import till setStatus({ kind: 'embedded' })-terminatorn "
        "före catch. Refactor utan ekvivalent kommunikation av runId-success "
        "bryter detta test."
    )
    cancelled_checks = re.findall(r"\bcancelled\b", block.group(0))
    assert len(cancelled_checks) >= 2, (
        "stackblitz-preview.tsx success-path saknar tillräcklig cancelled-"
        "guard-täthet mellan StackBlitz-import och setStatus({ kind: "
        "'embedded' }). Förväntat minst 2 cancelled-referenser (en efter "
        f"import, en efter embedProject) - hittade {len(cancelled_checks)}. "
        "B43-fyndet: stale embed kan mountas i ref-divden om operatör byter "
        "runId mid-flight."
    )

    # Verify the node-cleanup on stale embed exists (otherwise we'd
    # just NOT setStatus but the iframe still sits in the DOM). The
    # cleanup uses replaceChildren() so the React-owned shell keeps a
    # cleaner DOM mutation pattern.
    assert re.search(
        r"if\s*\(\s*cancelled\s*\)\s*\{[\s\S]{0,300}?replaceChildren\(\)",
        text,
    ), (
        "stackblitz-preview.tsx: post-embed cancelled-grenen måste rensa "
        "containerRef.current så stale embed inte sitter kvar i "
        "den always-mounted ref-divden."
    )


@pytest.mark.tooling
def test_stackblitz_preview_404_branch_guards_cancelled_before_setstate() -> None:
    """Race-condition guard: when /api/runs/<runId>/files returns 404,
    the in-flight async effect must not write setState for a runId
    that has already been replaced by a newer one. Without the
    cancelled-guard a stale 404 from a previous runId overwrites the
    UI state for the currently selected run (e.g. flips it to
    "preview saknas" even though the new run has preview files).

    Source-lock the cancelled-check inside the 404 branch so a future
    refactor cannot drop it. The other branches (success, catch) are
    already guarded; this brings the 404 path in line with them.

    Bundle-bloat-fix (ADR 0033): files-fetchen + 404-grenen bor numera i
    ``stackblitz-preview.tsx`` (lazy via next/dynamic) och skriver
    ``setStatus({ kind: "unavailable", ... })`` i stället för ViewerPanel:s
    gamla ``setUnavailable``.
    """
    text = (VIEWSER_DIR / "components" / "stackblitz-preview.tsx").read_text(
        encoding="utf-8"
    )

    # Find the 404 branch and verify a `cancelled` guard sits between
    # the `response.status === 404` check and the call to setStatus.
    # ``setStatus\([\s\S]+?\)`` är medvetet permissivt (kräver minst ett
    # tecken inuti parenteserna så ett tomt anrop inte matchar). Race-
    # condition-låset är ``if (cancelled) return;`` MELLAN 404-checken
    # och setStatus; argumentets exakta form är inte poängen.
    pattern = re.compile(
        r"response\.status\s*===\s*404[\s\S]{0,400}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,400}?setStatus\([\s\S]+?\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "stackblitz-preview.tsx 404-branch saknar cancelled-guard innan "
        "setStatus. Det skapar race-condition mellan snabba runId-byten där "
        "en stale 404 skriver över state för en nyladdad run."
    )


@pytest.mark.tooling
def test_viewer_panel_local_next_failure_branches_guard_cancelled() -> None:
    """Same race-condition guard som test_viewer_panel_404_branch_guards_
    cancelled_before_setstate, fast för de TRE nya local-next-failure-
    grenarna som fix-fallback-headers introducerade:

      1. POST /api/preview/<siteId> returnerar non-OK i local-next-mode
         → setUnavailable med strukturerad info från
           unavailableForPreviewError(errPayload).
      2. POST /api/preview/<siteId> kastar (network error) i
         local-next-mode → setUnavailable("Lokal preview-server kunde
         inte nås").
      3. siteId saknas men runId finns i local-next-mode →
         setUnavailable("Saknar siteId för lokal preview").

    Alla tre måste guarda mot stale runId-switch via ``cancelled``
    INNAN de skriver UI-state. Utan denna lock kan en framtida
    refactor släppa guarden och åter introducera samma race som
    den ursprungliga 404-fixen redan stoppat.

    Vi söker efter mönstret ``IS_LOCAL_NEXT_MODE`` följt inom 300 chars
    av ``if (cancelled) return;`` följt inom 200 chars av
    ``setUnavailable(``. Förväntar minst 3 sådana matchningar (en per
    failure-gren).
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    # Limits är frikostiga (800/600) så regex tål både kompakta varianter
    # och de pedagogiska inline-kommentarer som dokumenterar varför
    # cancelled-guarden behövs i respektive gren. Testets syfte är att
    # låsa ATT guarden finns — inte att tvinga fram en kompakt stil.
    pattern = re.compile(
        r"IS_LOCAL_NEXT_MODE[\s\S]{0,800}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,600}?setUnavailable\([\s\S]+?\)",
        re.MULTILINE,
    )
    matches = pattern.findall(text)
    assert len(matches) >= 3, (
        f"Förväntade ≥3 IS_LOCAL_NEXT_MODE-grenar med cancelled-guard "
        f"före setUnavailable, hittade {len(matches)}. "
        f"De tre grenarna är: (a) non-OK från POST /api/preview/<siteId>, "
        f"(b) network-error från samma fetch, (c) siteId saknas men "
        f"runId finns. Alla tre måste skydda mot stale runId-switch "
        f"så att en sen async-respons inte skriver över state för en "
        f"nyladdad run."
    )


@pytest.mark.tooling
def test_viewer_panel_local_next_non_ok_branch_reguards_after_json_parse() -> None:
    """Codex P2 (PR #97 review): i ``IS_LOCAL_NEXT_MODE``-grenen för
    non-OK response från ``POST /api/preview/<siteId>`` kollas
    ``cancelled`` FÖRE ``await previewResponse.json()`` men inte
    EFTER. Om operatören byter run under JSON-parsen kan den stale
    requesten fortfarande anropa ``setUnavailable(...)`` /
    ``setLoading(false)`` och skriva över state för den nyvalda runen
    — exakt samma race-condition som den ursprungliga 404-fixen
    redan stoppat på StackBlitz-vägen.

    Lås mönstret: mellan ``await previewResponse.json()`` (som ger
    ``errPayload``) och ``setUnavailable(unavailableForPreviewError``
    måste det finnas en ``if (cancelled) return;``. Source-lock så
    framtida refactor inte tar bort den.

    Implementationsdetalj: vi hittar errPayload-deklarationen (unik
    lokal variabel som bara existerar i denna gren), söker fram till
    ``setUnavailable(unavailableForPreviewError``, och verifierar att
    en ``if (cancelled) return;`` sitter mellan dem. Mer robust än
    en ren one-shot regex eftersom det inte bryts av inline-kommentarer
    eller indenterings-refactors.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    err_payload_idx = text.find("errPayload = (await previewResponse")
    assert err_payload_idx != -1, (
        "viewer-panel.tsx saknar `errPayload = (await previewResponse...` "
        "i IS_LOCAL_NEXT_MODE non-OK-grenen. Annars test kan inte ankra "
        "mellan parsen och state-skrivningen."
    )
    setunavail_idx = text.find("setUnavailable(unavailableForPreviewError", err_payload_idx)
    assert setunavail_idx != -1, (
        "viewer-panel.tsx saknar `setUnavailable(unavailableForPreviewError(...))` "
        "efter errPayload-deklarationen — non-OK-grenen måste rendera "
        "strukturerad felinfo via unavailableForPreviewError."
    )
    between = text[err_payload_idx:setunavail_idx]
    assert re.search(r"if\s*\(\s*cancelled\s*\)\s*return\s*;", between), (
        "viewer-panel.tsx IS_LOCAL_NEXT_MODE non-OK-grenen saknar "
        "`if (cancelled) return;` mellan `await previewResponse.json()` "
        "och `setUnavailable(unavailableForPreviewError(...))`. Utan "
        "denna re-check kan en stale request som passerar den pre-await "
        "cancelled-checken fortfarande skriva över UI-state för en "
        "nyvald run (Codex P2 fynd, PR #97 review). Mirror samma mönster "
        "som success-grenen redan har efter `await previewResponse.json() "
        "as PreviewServerInfo`."
    )


@pytest.mark.tooling
def test_b152_compare_modal_pane_width_accounts_for_gap() -> None:
    """B152: compare-preview-modal PreviewPane använder
    ``w-[calc(100%-0.5rem)]`` istället för ``w-full`` så bredden
    kompenserar för parent-flex-rowens ``gap-2`` (0.5rem). Med ``w-full``
    + ``gap-2`` overflowade scrollern (200 % + 0.5rem) vilket lät pane-
    A:s högra kant smyga in i viewporten när snappat till pane B.
    AI Bug Review (P 88 %, impact 7/10) flaggade detta på PR #117.

    Lock: PreviewPane <section>-elementets className ska INTE innehålla
    ``flex min-h-0 w-full`` (gamla mönstret) utan ``w-[calc(100%-0.5rem)]``.
    """
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "compare-preview-modal.tsx"
    ).read_text(encoding="utf-8")

    pattern_fix = re.compile(
        r"w-\[calc\(100%-0\.5rem\)\][\s\S]{0,200}?snap-start",
        re.MULTILINE,
    )
    assert pattern_fix.search(text), (
        "compare-preview-modal.tsx PreviewPane måste använda "
        "``w-[calc(100%-0.5rem)]`` så pane-bredden + gap-2 = 100 % per "
        "snap-segment. ``w-full`` + ``gap-2`` overflowar scrollern och "
        "bryter one-pane-snap (B152)."
    )

    # Negative: säkerställ att gamla mönstret ``w-full shrink-0 snap-start``
    # inte finns kvar (skulle vara regression).
    pattern_regression = re.compile(
        r"w-full\s+shrink-0\s+snap-start",
        re.MULTILINE,
    )
    assert not pattern_regression.search(text), (
        "compare-preview-modal.tsx har återgått till ``w-full shrink-0 "
        "snap-start`` per pane (B152-regression). Måste vara "
        "``w-[calc(100%-0.5rem)]`` för att kompensera för parent gap-2."
    )


# ---------------------------------------------------------------------------
# Bite C — vercel-sandbox preview wiring (ADR 0033)
# ---------------------------------------------------------------------------
# Källåls-lås så local-next-vägen förblir oförändrad medan vercel-sandbox-
# vägen wiras in: route via currentViewserRuntime, ViewerPanel-iframe av den
# returnerade publika URL:en, tom-header-gren i next.config, dev-dispatcher
# som inte kastar, ärlig auth-degradering och sandbox-livscykel (stoppa gamla).


@pytest.mark.tooling
def test_preview_route_dispatches_via_current_viewser_runtime() -> None:
    """Bite C task 1: ``app/api/preview/[siteId]/route.ts`` ska gå via
    ``currentViewserRuntime()`` (DI) i stället för att hårdkoda local-
    preview-server. local-next-grenen MÅSTE behålla sitt exakta beteende
    (``startPreviewServer`` + strukturerad felshape), och en
    ``vercel_auth``-felkod måste finnas så UI:t kan visa pedagogiskt fel
    i stället för tyst fallback."""
    text = (VIEWSER_DIR / "app" / "api" / "preview" / "[siteId]" / "route.ts").read_text(
        encoding="utf-8"
    )

    assert "currentViewserRuntime" in text, (
        "route.ts måste resolva runtime via currentViewserRuntime() (DI), "
        "inte hårdkoda local-preview-server."
    )
    assert 'from "@/lib/preview-runtime-server"' in text, (
        "route.ts måste importera currentViewserRuntime från @/lib/preview-runtime-server."
    )
    # local-next-grenen oförändrad: startPreviewServer + classifyStartError.
    assert "await startPreviewServer(siteId)" in text, (
        "route.ts local-grenen måste fortsatt anropa startPreviewServer(siteId) "
        "så local-next-beteendet är oförändrat."
    )
    assert 'runtime.kind !== "local"' in text, (
        "route.ts måste grena på runtime.kind så icke-lokala adaptrar "
        "(vercel-sandbox) går via adapterns start/stop."
    )
    # Ärlig degradering: vercel_auth-felkod finns.
    assert '"vercel_auth"' in text, (
        "route.ts PreviewErrorCode måste innehålla 'vercel_auth' för "
        "saknad/utgången Vercel-token (ärlig degradering, inte tyst fallback)."
    )
    # DELETE stoppar sandbox-sessionen i vercel-sandbox-läge (livscykel/kostnad).
    assert "stopSandboxSessionForSite" in text, (
        "route.ts DELETE måste stoppa sandbox-sessionen i vercel-sandbox-läge "
        "(stopSandboxSessionForSite) så vi inte läcker sandboxar."
    )


@pytest.mark.tooling
def test_viewer_panel_has_vercel_sandbox_branch() -> None:
    """Bite C task 2: ViewerPanel måste behandla vercel-sandbox EXAKT som
    local-next-vägen (POST /api/preview → iframe:a returnerad URL) och visa
    pedagogiskt fel vid miss i stället för att falla till StackBlitz.

    Lås:
      1. ``IS_VERCEL_SANDBOX_MODE``-konstant.
      2. Failure-grenarna gated på ``IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE``
         (≥3 ggr — non-OK, network-error, siteId-saknas).
      3. ``vercel_auth`` hanteras i unavailableForPreviewError.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    pattern_const = re.compile(
        r'const\s+IS_VERCEL_SANDBOX_MODE\s*=\s*PREVIEW_RUNTIME\.kind\s*===\s*["\']vercel-sandbox["\']',
        re.MULTILINE,
    )
    assert pattern_const.search(text), (
        "viewer-panel.tsx saknar ``const IS_VERCEL_SANDBOX_MODE = "
        "PREVIEW_RUNTIME.kind === 'vercel-sandbox'`` (Bite C, ee68add)."
    )

    combined = len(re.findall(r"IS_LOCAL_NEXT_MODE\s*\|\|\s*IS_VERCEL_SANDBOX_MODE", text))
    assert combined >= 3, (
        "viewer-panel.tsx: de tre preview-failure-grenarna (non-OK, "
        "network-error, siteId-saknas) måste vara gated på "
        "``IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE`` så vercel-sandbox "
        f"visar pedagogiskt fel i stället för StackBlitz-fallback. Hittade {combined}."
    )

    assert 'code === "vercel_auth"' in text, (
        "viewer-panel.tsx unavailableForPreviewError måste hantera "
        "'vercel_auth' med ett pedagogiskt svenskt inloggningsfel."
    )


@pytest.mark.tooling
def test_next_config_vercel_sandbox_gets_empty_headers() -> None:
    """Bite C task 3: ``vercel-sandbox`` måste få TOMMA headers (som
    local-next), INTE COEP/COOP. En publik https-iframe behöver ingen
    cross-origin-isolation (det krävs bara av StackBlitz/WebContainers)."""
    text = (VIEWSER_DIR / "next.config.ts").read_text(encoding="utf-8")

    pattern = re.compile(
        r'if\s*\(\s*effectiveMode\s*===\s*["\']local-next["\']\s*\|\|\s*'
        r'effectiveMode\s*===\s*["\']vercel-sandbox["\']\s*\)\s*\{\s*return\s*\[\s*\]\s*;',
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "next.config.ts headers() måste returnera [] för BÅDE local-next och "
        "vercel-sandbox (``if (effectiveMode === 'local-next' || effectiveMode "
        "=== 'vercel-sandbox') { return []; }``). Annars hamnar vercel-sandbox "
        "i COEP/COOP-grenen som blockerar en cross-origin iframe."
    )


@pytest.mark.tooling
def test_dev_dispatcher_allows_vercel_sandbox_over_http() -> None:
    """Bite C task 4: ``scripts/dev.mjs`` får INTE kasta på
    ``VIEWSER_PREVIEW_MODE=vercel-sandbox`` — det ska köra vanlig
    ``next dev`` (http, COEP off), samma transport som local-next."""
    text = (VIEWSER_DIR / "scripts" / "dev.mjs").read_text(encoding="utf-8")

    assert '"vercel-sandbox"' in text, (
        "dev.mjs VALID_MODES måste innehålla 'vercel-sandbox' så dispatchern "
        "inte kastar på det läget."
    )
    # http/COEP-off: vercel-sandbox måste ge useHttps=false (ingen
    # --experimental-https), precis som local-next.
    assert "HTTP_COEP_OFF_MODES" in text, (
        "dev.mjs måste ha en HTTP_COEP_OFF_MODES-mängd som styr useHttps."
    )
    pattern = re.compile(
        r"HTTP_COEP_OFF_MODES\s*=\s*new\s+Set\(\s*\[[^\]]*['\"]vercel-sandbox['\"]",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "dev.mjs: 'vercel-sandbox' måste ligga i HTTP_COEP_OFF_MODES så "
        "useHttps=false (http, COEP off) — sandbox-URL:en är en publik "
        "https-iframe som bäddas utan cross-origin-isolation."
    )
    assert "!HTTP_COEP_OFF_MODES.has(mode)" in text, (
        "dev.mjs useHttps måste härledas ur HTTP_COEP_OFF_MODES."
    )


@pytest.mark.tooling
def test_vercel_sandbox_sessions_module_bridges_siteid_to_sandbox() -> None:
    """Bite C task 6: en sessionsmodul bryggar ``siteId -> sandboxId`` så
    build-runner och DELETE kan stoppa en sandbox via siteId (de känner inte
    sandboxId). Modulen delegerar stop till runnern."""
    path = VIEWSER_DIR / "lib" / "vercel-sandbox-sessions.ts"
    assert path.exists(), (
        "apps/viewser/lib/vercel-sandbox-sessions.ts saknas — registret som "
        "bryggar siteId -> sandboxId för sandbox-livscykeln."
    )
    text = path.read_text(encoding="utf-8")
    assert "recordSandboxSession" in text
    assert "getSandboxSession" in text
    assert "export async function stopSandboxSessionForSite" in text
    assert 'from "./vercel-sandbox-runner"' in text and "stopSandboxPreview" in text, (
        "sessionsmodulen måste delegera stop till runnerns stopSandboxPreview."
    )


@pytest.mark.tooling
def test_preview_runtime_server_records_and_stops_old_sandbox() -> None:
    """Bite C task 5+6: DI-wiringen registrerar en ny sandbox-session och
    stoppar en ev. tidigare sandbox för samma siteId innan en ny skapas (så
    vi aldrig kör två parallellt → läcker inte kostnad)."""
    text = (VIEWSER_DIR / "lib" / "preview-runtime-server.ts").read_text(encoding="utf-8")
    assert "recordSandboxSession" in text, (
        "preview-runtime-server.ts måste registrera den nya sandbox-sessionen "
        "efter en lyckad createSandboxPreview."
    )
    assert "stopSandboxSessionForSite(siteId)" in text, (
        "preview-runtime-server.ts vercelSandbox.start måste stoppa en ev. "
        "tidigare sandbox för samma siteId innan en ny skapas."
    )


@pytest.mark.tooling
def test_build_runner_stops_sandbox_session_before_rebuild() -> None:
    """Bite C task 6: ett nytt bygge/följdprompt ska stoppa den gamla
    sandboxen — wirat där local-next:s ``stopAndWaitPreviewServer`` anropas
    idag. Idempotent no-op i local-next-läge (tomt register)."""
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    assert "stopSandboxSessionForSite(siteId)" in text, (
        "build-runner.ts måste anropa stopSandboxSessionForSite(siteId) "
        "(bredvid stopAndWaitPreviewServer) så en gammal sandbox stoppas "
        "innan en ny build — annars läcker sandboxar (TTL ~15 min, kostar ören)."
    )


@pytest.mark.tooling
def test_vercel_sandbox_runner_autoloads_env_vercel_local() -> None:
    """Bite C task 5 (auth-wiring): Next auto-laddar inte ``.env.vercel.local``
    (filen vercel env pull skapar för OIDC-token). Runnern måste därför läsa
    den filen själv så den körande viewser-processen hittar VERCEL_OIDC_TOKEN —
    annars visar iframen bara 'credentials saknas' trots en pullad token."""
    text = (VIEWSER_DIR / "lib" / "vercel-sandbox-runner.ts").read_text(encoding="utf-8")
    assert ".env.vercel.local" in text, (
        "vercel-sandbox-runner.ts måste läsa apps/viewser/.env.vercel.local "
        "så OIDC-token från `vercel env pull` hittas (Next auto-laddar den inte)."
    )
    assert "VERCEL_OIDC_TOKEN" in text


@pytest.mark.tooling
def test_viewer_panel_iframe_has_load_state_overlay() -> None:
    """S2: preview-iframen ska flippa ett iframeLoaded-state via onLoad och
    visa en skelett-overlay tills dokumentet laddat, gate:ad mot
    isBuilding/isFinalizing så den inte dubblerar BuildProgressCard.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
    assert "iframeLoaded" in text and "setIframeLoaded" in text, (
        "ViewerPanel ska spåra iframens laddningsstatus."
    )
    assert "onLoad={() => setIframeLoaded(true)}" in text, (
        "Iframens onLoad ska flippa iframeLoaded → overlayn döljs."
    )
    assert "!iframeLoaded && !isBuilding && !isFinalizing" in text, (
        "Skelett-overlayn ska gate:as mot build-tillstånd så den inte dubblerar BuildProgressCard."
    )


@pytest.mark.tooling
def test_viewer_panel_unavailable_banner_has_retry() -> None:
    """P2: otillgänglig-bannern var helt pointer-events-none utan retry —
    operatören tvingades välja om runen för att hämta om previewn. Source-lock
    att kortet är klickbart (pointer-events-auto) och bumpar en retryNonce som
    ingår i preview-effektens deps."""
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
    assert "retryNonce" in text and "[runId, siteId, retryNonce]" in text, (
        "Preview-effekten ska köra om när retryNonce bumpas."
    )
    assert "setRetryNonce((n) => n + 1)" in text and "Försök igen" in text, (
        "Otillgänglig-bannern ska ha en 'Försök igen'-knapp som bumpar retryNonce."
    )


@pytest.mark.tooling
def test_compare_modal_sets_cross_origin_isolated() -> None:
    """P2: jämförelse-embedden saknade crossOriginIsolated (paritet med
    ViewerPanel) → WebContainern kunde faila att boota. Source-lock att flaggan
    sätts."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "compare-preview-modal.tsx"
    ).read_text(encoding="utf-8")
    assert "crossOriginIsolated: true," in text, (
        "Compare-modalens embed ska sätta crossOriginIsolated för paritet med ViewerPanel."
    )


@pytest.mark.tooling
def test_viewer_panel_site_id_follows_selected_run() -> None:
    """C4 (P0, scout-fynd 2026-06-05): ViewerPanel fick siteId={selectedSiteId}
    medan runId={selectedRunId}. Project Input-väljaren kan sätta selectedSiteId
    utan att rensa selectedRunId → previewen (/api/preview/<siteId>) startade
    fel .generated/<siteId>/ medan runId pekade på en annan sajt. Lås att
    siteId följer den valda runens faktiska site (runSiteId) med picker-sajten
    som fallback.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    assert "siteId={runSiteId ?? selectedSiteId}" in text, (
        "ViewerPanel:s siteId måste följa den valda runens site (runSiteId) så "
        "preview-POST:en inte desynkar mot runId (C4)."
    )


# ---------------------------------------------------------------------------
# Tier 1 sandbox-smidighet (operatörsbeslut 2026-06-10): pre-built upload (B3),
# OIDC-token-refresh före Sandbox.create (B1a), synliga timings (B6-light).
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_vercel_sandbox_runner_prebuilt_upload_auto_killswitch_and_fallback() -> None:
    """B3: när den aktiva immutable builden har en färdig ``.next/`` på disk
    ska runnern ladda upp byggartefakterna och köra ENBART ``next start`` i
    sandboxen (ingen ``next build``, prod-deps-install via ``--omit=dev``).
    Sparar ~10-15 s av dagens ~25 s cold-start per preview.

    Sex lås:
      1. AUTO-beteende med kill-switch: ``VIEWSER_SANDBOX_UPLOAD_BUILT=0``
         återställer dagens fulla väg — allt annat värde (inkl. osatt) ger
         pre-built när ``.next`` finns. Låses som ``!== "0"``.
      2. Readiness-signal: ``.next/BUILD_ID`` (skrivs sist i en lyckad build)
         på den resolvade käll-katalogen — inte bara att ``.next/`` existerar.
      3. Pre-built-grenen installerar prod-deps (``--omit=dev`` — typescript/
         tailwind/eslint behövs bara av next build) och hoppar över
         ``next build`` (gated på ``!prebuilt``).
      4. ``.next/cache`` (webpack-disk-cache, merparten av .next-bytes) och
         ``.next/trace`` (build-telemetri med operatörens absoluta paths)
         laddas ALDRIG upp.
      5. Ärlig en-gångs-fallback: failar pre-built-vägen i sandboxen körs
         fulla vägen om EXAKT en gång (ingen loop), gated på
         ``fallbackEligible && status === "failed"``.
      6. Immutable-build-kontraktet: runnern muterar aldrig build-katalogen
         (ingen writeFileSync/rmSync mot källan).
    """
    text = (VIEWSER_DIR / "lib" / "vercel-sandbox-runner.ts").read_text(encoding="utf-8")

    # Lock 1: kill-switch-env + AUTO-default (!== "0" → på när osatt).
    assert "VIEWSER_SANDBOX_UPLOAD_BUILT" in text, (
        "vercel-sandbox-runner.ts saknar kill-switch-env "
        "VIEWSER_SANDBOX_UPLOAD_BUILT (B3). =0 måste återställa fulla vägen."
    )
    assert re.search(r'process\.env\[UPLOAD_BUILT_ENV\]\s*!==\s*["\']0["\']', text), (
        "Pre-built-läget måste vara AUTO (på när .next finns): gaten ska vara "
        '``process.env[UPLOAD_BUILT_ENV] !== "0"`` så bara ett explicit ``0`` '
        "stänger av."
    )

    # Lock 2: BUILD_ID-detektion på käll-katalogen.
    assert re.search(
        r'join\(\s*sourceDir,\s*["\']\.next["\'],\s*["\']BUILD_ID["\']\s*\)', text
    ), (
        "Pre-built-detektionen måste kolla ``<sourceDir>/.next/BUILD_ID`` "
        "(skrivs sist i en lyckad next build) — en halvfärdig/avbruten build "
        "får inte trigga pre-built-vägen."
    )

    # Lock 3: prod-deps-install + skippad next build i pre-built-grenen.
    assert '"--omit=dev"' in text, (
        "Pre-built-grenen ska installera med ``--omit=dev`` — dev-deps "
        "(typescript/tailwind/eslint) behövs bara av next build, som hoppas över."
    )
    assert re.search(r'if\s*\(\s*!prebuilt\s*\)\s*\{[\s\S]{0,500}?"next",\s*"build"', text), (
        "``npx next build`` måste vara gated på ``if (!prebuilt)`` så "
        "pre-built-vägen aldrig bygger om i sandboxen."
    )

    # Lock 4: .next/cache + .next/trace exkluderas alltid.
    assert '".next/cache"' in text, (
        "``.next/cache`` (webpack-disk-cache, 60+ MB) får aldrig laddas upp — "
        "den läses inte av next start."
    )
    assert '".next/trace"' in text, (
        "``.next/trace`` (build-telemetri med operatörens absoluta paths) får "
        "aldrig laddas upp."
    )

    # Lock 5: en-gångs-fallback utan loop.
    assert len(re.findall(r"createSandboxPreviewAttempt\(request,\s*false\)", text)) == 1, (
        "Fallbacken till fulla vägen ska ske EXAKT en gång "
        "(createSandboxPreviewAttempt(request, false)) — ingen loop."
    )
    assert len(re.findall(r"createSandboxPreviewAttempt\(request,\s*true\)", text)) == 1, (
        "Första försöket (allowPrebuilt=true) ska ske exakt en gång."
    )
    assert re.search(
        r'first\.fallbackEligible\s*&&\s*first\.result\.status\s*===\s*["\']failed["\']',
        text,
    ), (
        "Fallbacken måste vara gated på fallbackEligible && status === 'failed' "
        "— auth-/valideringsfel (som failar identiskt på fulla vägen) får inte "
        "trigga en andra kostsam sandbox-körning."
    )

    # Lock 6: immutable-build-kontraktet — runnern bara LÄSER källan.
    assert "writeFileSync" not in text and "rmSync" not in text, (
        "vercel-sandbox-runner.ts får aldrig mutera den immutable "
        "build-katalogen på disk (B157 nivå 4)."
    )


@pytest.mark.tooling
def test_vercel_sandbox_runner_refreshes_oidc_token_before_sandbox_create() -> None:
    """B1a: OIDC-token från ``vercel env pull`` lever ~12 h lokalt — en lång
    viewser-session överlever den gränsen och previews dör då med ett
    kryptiskt SDK-fel. Refresh-logiken extraherades ur ``scripts/dev.mjs``
    till den DELADE modulen ``lib/vercel-oidc-refresh.mjs`` och runnern
    anropar den FÖRE ``Sandbox.create`` när OIDC-vägen används och JWT-exp
    har < 1 h kvar.

    Fem lås:
      1. Delad modul finns med 1 h-margin och äger det enda
         ``vercel env pull``-anropet.
      2. ``scripts/dev.mjs`` importerar den delade modulen och har INGEN egen
         inline-kopia kvar (två drift-känsliga kopior var hela problemet).
      3. Runnern anropar guarden FÖRE ``Sandbox.create`` (index-ordning i
         källan), gated på ``credentials.mode === "oidc"``.
      4. Vid misslyckad refresh + död token: ärligt fel som behåller
         ``VERCEL_OIDC_TOKEN`` i meddelandet (→ routens ``vercel_auth``-
         klassning) OCH inkluderar ``expiresIn`` + hur-fixar-info.
      5. En fräschare token från filen adopteras in i ``process.env`` —
         det är därifrån SDK:n läser vid ``Sandbox.create``.
    """
    shared_path = VIEWSER_DIR / "lib" / "vercel-oidc-refresh.mjs"
    assert shared_path.exists(), (
        "apps/viewser/lib/vercel-oidc-refresh.mjs saknas — den delade "
        "OIDC-refresh-modulen (B1a) som dev.mjs och sandbox-runnern delar."
    )
    shared = shared_path.read_text(encoding="utf-8")
    dev = (VIEWSER_DIR / "scripts" / "dev.mjs").read_text(encoding="utf-8")
    runner = (VIEWSER_DIR / "lib" / "vercel-sandbox-runner.ts").read_text(
        encoding="utf-8"
    )

    # Lock 1: margin + det enda env-pull-anropet bor i den delade modulen.
    assert re.search(
        r"OIDC_REFRESH_MARGIN_SECONDS\s*=\s*60\s*\*\s*60", shared
    ), "Den delade modulen ska refresha vid < 1 h kvar (60 * 60 s margin)."
    assert re.search(r'\[\s*"env",\s*"pull"', shared), (
        "vercel-oidc-refresh.mjs ska äga själva `vercel env pull`-spawnen."
    )

    # Lock 2: dev.mjs delegerar — ingen inline-kopia kvar.
    assert re.search(
        r'import\s*\{[^}]*ensureFreshVercelOidcToken[^}]*\}\s*from\s*'
        r'["\']\.\./lib/vercel-oidc-refresh\.mjs["\']',
        dev,
    ), (
        "scripts/dev.mjs måste importera ensureFreshVercelOidcToken från "
        "../lib/vercel-oidc-refresh.mjs (delad implementation, B1a)."
    )
    assert "ensureFreshVercelOidcToken(" in dev, (
        "scripts/dev.mjs måste fortsatt anropa refreshen i vercel-sandbox-läge "
        "(predev-auth-beteendet är oförändrat)."
    )
    assert "function ensureFreshVercelOidcToken" not in dev, (
        "scripts/dev.mjs får inte ha kvar en egen inline-implementation — "
        "två drift-känsliga kopior av refresh-logiken var hela problemet."
    )
    assert not re.search(r'\[\s*"env",\s*"pull"', dev), (
        "`vercel env pull`-spawnen får bara finnas i den delade modulen."
    )

    # Lock 3: runnern anropar guarden före Sandbox.create, gated på oidc.
    assert re.search(
        r'import\s*\{[^}]*ensureFreshVercelOidcToken[^}]*\}\s*from\s*'
        r'["\']\./vercel-oidc-refresh\.mjs["\']',
        runner,
    ), (
        "vercel-sandbox-runner.ts måste importera den delade refreshen från "
        "./vercel-oidc-refresh.mjs."
    )
    guard_call_idx = runner.find("ensureFreshOidcTokenBeforeCreate(logs)")
    create_idx = runner.find("Sandbox.create({")
    assert guard_call_idx != -1, (
        "Runnern saknar ensureFreshOidcTokenBeforeCreate(logs)-anropet (B1a)."
    )
    assert create_idx != -1 and guard_call_idx < create_idx, (
        "OIDC-guarden måste anropas FÖRE Sandbox.create — efteråt är "
        "token-utgången redan ett kryptiskt SDK-fel."
    )
    gate_idx = runner.find('credentials.mode === "oidc"')
    assert gate_idx != -1 and gate_idx < guard_call_idx, (
        "Guarden ska bara köras på OIDC-vägen (credentials.mode === 'oidc') — "
        "access-token-trion har ingen exp att refresha."
    )

    # Lock 4: ärligt fel med expiresIn + fix-info, klassbart som vercel_auth.
    failure_block = re.search(
        r"VERCEL_OIDC_TOKEN är utgången[\s\S]{0,400}?expiresIn[\s\S]{0,400}?vercel env pull",
        runner,
    )
    assert failure_block, (
        "Misslyckad refresh + död token måste ge ett ärligt fel som nämner "
        "VERCEL_OIDC_TOKEN (routens vercel_auth-regex), expiresIn och "
        "hur-fixar-info (`vercel env pull ...`)."
    )

    # Lock 5: fräschare fil-token adopteras in i process.env före create.
    assert re.search(
        r"process\.env\.VERCEL_OIDC_TOKEN\s*=\s*fileToken", runner
    ), (
        "Runnern måste adoptera en fräschare token från .env.vercel.local in i "
        "process.env — ensureVercelEnvLocalLoaded fyller bara tomma nycklar en "
        "gång per process och räcker inte efter en refresh."
    )


@pytest.mark.tooling
def test_preview_post_response_exposes_sandbox_timings() -> None:
    """B6-light: runnern mäter redan createMs/uploadMs/installMs/buildMs/
    readyMs/totalMs — kedjan upp till ``POST /api/preview/<siteId>``-svaret
    ska exponera timings-objektet (additivt fält) så UI/operatör kan se var
    cold-start-tiden går (och verifiera pre-built-vinsten i B3).

    Kedjan har fyra länkar som alla låses:
      1. ``PreviewResult`` (packages/preview-runtime) har ett additivt
         ``timings?: PreviewTimings``-fält.
      2. Adaptern (adapters/vercel-sandbox.ts) mappar ``info.timings`` vidare.
      3. DI-wiringen (preview-runtime-server.ts) skickar runnerns
         ``result.timings`` in i adaptern.
      4. Routen lägger ``timings: result.timings`` i POST-svaret
         (``PreviewStartOk``). local-next-grenen är OFÖRÄNDRAD (den svarar
         via ``startPreviewServer`` precis som förr).
    """
    types_text = (
        REPO_ROOT / "packages" / "preview-runtime" / "src" / "types.ts"
    ).read_text(encoding="utf-8")
    adapter_text = (
        REPO_ROOT / "packages" / "preview-runtime" / "src" / "adapters" / "vercel-sandbox.ts"
    ).read_text(encoding="utf-8")
    wiring_text = (VIEWSER_DIR / "lib" / "preview-runtime-server.ts").read_text(
        encoding="utf-8"
    )
    route_text = (
        VIEWSER_DIR / "app" / "api" / "preview" / "[siteId]" / "route.ts"
    ).read_text(encoding="utf-8")

    # Lock 1: additivt timings-fält i PreviewResult.
    assert re.search(r"timings\?:\s*PreviewTimings", types_text), (
        "packages/preview-runtime/src/types.ts: PreviewResult måste ha ett "
        "additivt ``timings?: PreviewTimings``-fält (B6-light)."
    )
    assert "interface PreviewTimings" in types_text, (
        "packages/preview-runtime/src/types.ts saknar PreviewTimings-interfacet."
    )

    # Lock 2: adaptern släpper igenom runnerns timing.
    assert "timings: info.timings" in adapter_text, (
        "adapters/vercel-sandbox.ts måste mappa handler-resultatets timings "
        "in i PreviewResult — annars dör kedjan i adapterlagret."
    )

    # Lock 3: DI-wiringen skickar runnerns timings till adaptern.
    assert "timings: result.timings" in wiring_text, (
        "preview-runtime-server.ts vercelSandbox.start måste returnera "
        "``timings: result.timings`` från createSandboxPreview."
    )

    # Lock 4: routen exponerar timings i POST-svaret, additivt.
    assert re.search(r"timings\?:\s*PreviewTimings", route_text), (
        "route.ts PreviewStartOk måste ha det additiva timings-fältet."
    )
    assert "timings: result.timings" in route_text, (
        "route.ts POST-svaret (icke-lokala adaptrar) måste inkludera "
        "``timings: result.timings`` så operatören ser var cold-start-tiden går."
    )
    # local-next-grenen oförändrad (svarar via startPreviewServer som förr).
    assert "await startPreviewServer(siteId)" in route_text, (
        "local-next-grenen ska vara orörd av timings-exponeringen."
    )
