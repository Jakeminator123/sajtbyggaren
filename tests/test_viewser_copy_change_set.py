"""Viewser copy-directive och exakt change-set-wiring (ADR 0034 väg B + UI-gap-fix).

Utbruten ur ``test_viewser_floating_chat.py`` (1200-raders-taket i
``test_test_hygiene.py``, samma mönster som ``test_viewser_builder_dialogs.py``
och ``test_viewser_openclaw_slice3.py``): copy-direktiv-/change-set-låsen är
ett eget ämne (backend-läsare → /api/prompt → svenska success-rader), inte
chat-ämne, så de bor i en egen ämnesfokuserad fil per hygien-regeln.
"""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR


@pytest.mark.tooling
def test_b155_path_b_runs_lib_exports_applied_copy_directives() -> None:
    """ADR 0034 väg B (B155 path B): ``lib/runs.ts`` måste exportera
    ``readAppliedCopyDirectives`` + en strikt ``AppliedCopyDirective``-typ
    som speglar schema-enumen i
    ``governance/schemas/project-input.schema.json:directives.copyDirectives``.

    Locks:
      1. Funktionen finns och är exporterad så ``/api/prompt`` kan
         konsumera den utan att duplicera readern någonannanstans.
      2. Type-enumen matchar schema-värdena exakt
         (company-name | tagline; replace-text | include-token).
      3. Path-traversal-skyddet är på plats: läsaren begränsar
         dossierPath till ``data/prompt-inputs/`` eller ``examples/``
         under repo-root så en stulen ``input.json`` inte kan
         dirigera UI:t att läsa godtyckliga filer.
    """
    text = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")

    assert "export async function readAppliedCopyDirectives" in text, (
        "lib/runs.ts måste exportera ``readAppliedCopyDirectives`` så "
        "/api/prompt-routen kan inkludera direktiven på response. "
        "Annars måste FloatingChat duplicera readern på client-sidan."
    )
    assert "export type AppliedCopyDirective" in text, (
        "AppliedCopyDirective-typen måste exporteras strikt-typad så "
        "client och server delar exakt samma shape (target/operation/"
        "payload/source-enum)."
    )
    enum_pattern = re.compile(
        r'target:\s*"company-name"\s*\|\s*"tagline"\s*\|\s*"about-text"'
        r'\s*\|\s*"services"[\s\S]{0,200}?'
        r'operation:\s*"replace-text"\s*\|\s*"include-token"',
        re.MULTILINE,
    )
    assert enum_pattern.search(text), (
        "AppliedCopyDirective-enumen måste låsa alla fyra schema-targets "
        "(company-name|tagline|about-text|services) och operation="
        "replace-text|include-token så schema-drift fångas i typecheck "
        "istället för att läcka okända värden till UI:t."
    )
    assert "targetRef?: string" in text, (
        "AppliedCopyDirective måste bära ``targetRef`` (services[].id|label) "
        "så ett services-direktiv kan peka ut vilken tjänst som ändrades — "
        "schemat kräver fältet när target=services."
    )
    # Schemat (project-input.schema.json:226-234) gör targetRef OBLIGATORISK när
    # target=services. Läsaren måste enforca det och SLÄNGA services-direktiv som
    # saknar giltig targetRef — annars läcker de igenom och UI:t faller tillbaka
    # på den generiska "Jag uppdaterade en tjänst."-raden som tappar VILKEN
    # tjänst som ändrades (operatörskontext).
    drop_guard = re.compile(
        r'candidate\.target\s*===\s*"services"\s*&&\s*!targetRefValid',
        re.MULTILINE,
    )
    assert drop_guard.search(text), (
        "readAppliedCopyDirectives måste droppa services-direktiv utan giltig "
        "targetRef (schema-required) i stället för att visa den generiska "
        '"uppdaterade en tjänst"-raden. Saknas drop-guarden bryter UI:t mot '
        "schema-kontraktet och tappar operatörskontext."
    )
    assert 'path.resolve(root, "data", "prompt-inputs")' in text and (
        'path.resolve(root, "examples")' in text
    ), (
        "Path-traversal-skyddet i readAppliedCopyDirectives måste vitlista "
        "data/prompt-inputs/ + examples/ under repo-root. Utan denna guard "
        "kan en stulen input.json dirigera UI:t att läsa godtyckliga filer."
    )


@pytest.mark.tooling
def test_b155_path_b_prompt_route_exposes_applied_copy_directives() -> None:
    """``/api/prompt`` måste returnera ``appliedCopyDirectives`` på
    top-level efter en build så FloatingChat har direkt tillgång till
    fältet utan att behöva en separat round-trip.

    Auktoritetskedjan: build_site.py skriver project-input-snapshotet
    till dossierPath, prompt-routen läser via readAppliedCopyDirectives,
    UI:t härleder svenska success-rader. Vi kontrollerar det mellersta
    steget här.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    assert "readAppliedCopyDirectives" in text, (
        "/api/prompt måste anropa readAppliedCopyDirectives efter att "
        "runBuild returnerar — annars är fältet alltid undefined på "
        "wire och path B-success-raden kan aldrig skickas."
    )
    assert "appliedCopyDirectives" in text, (
        "Top-level-fältet måste finnas i return-objektet från "
        "runPromptBuildOnce. Utan det kan FloatingChat inte härleda "
        "några svenska success-rader."
    )


@pytest.mark.tooling
def test_b155_path_b_floating_chat_summarises_copy_directives() -> None:
    """ADR 0034 väg B (B155 path B): FloatingChat måste härleda en svensk
    success-rad per applicerat copy-direktiv enligt Jakobs handoff:
      - target=company-name → "Jag ändrade företagsnamnet till '...'."
      - target=tagline + operation=replace-text → "Jag uppdaterade rubriken till '...'."
      - target=tagline + operation=include-token → "Jag la in '...' i hero-texten."

    Pattern verifierar att payload renderas via template-strängen (textnod
    i React) och inte via ``dangerouslySetInnerHTML`` — payload kommer från
    operatören och måste alltid escapas.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "function summarizeCopyDirectives" in text, (
        "Helper ``summarizeCopyDirectives`` ska kapsla mappningen från "
        "AppliedCopyDirective[] till svenska rader så success-grenen i "
        "summarizeBuildResult inte blandar mappnings-logik med dispatch."
    )
    assert "Jag ändrade företagsnamnet till" in text, (
        "Mappningen för target=company-name saknas eller har bytt form. "
        "Jakobs handoff kräver exakt rad-prefix för operatör-igenkänning."
    )
    assert "Jag uppdaterade rubriken till" in text, (
        "Mappningen för target=tagline + operation=replace-text saknas eller har bytt form."
    )
    assert "Jag la in" in text and "i hero-texten" in text, (
        "Mappningen för target=tagline + operation=include-token saknas eller har bytt form."
    )
    # Slice 2a/2c: about-text + services måste också ge en ärlig rad nu när
    # backend-läsaren (lib/runs.ts) släpper igenom dem (annars syns följdprompt
    # mot om oss-texten/tjänster aldrig i FloatingChat — current-focus #5).
    assert "Jag skrev om om oss-texten" in text, (
        "Mappningen för target=about-text saknas. Om oss-följdprompter måste "
        "bekräftas i FloatingChat (utan att eka hela 600-teckens-payloaden)."
    )
    assert 'Jag uppdaterade tjänsten "' in text and "targetRef" in text, (
        "Mappningen för target=services saknas. Tjänst-följdprompter måste "
        "bekräftas med tjänstnamnet (targetRef), inte den långa summaryn."
    )
    assert "appliedCopyDirectives" in text, (
        "PromptApiResponse måste exponera ``appliedCopyDirectives`` så "
        "summarizeBuildResult kan plocka fältet utan att casta till "
        "Record<string, unknown>."
    )


@pytest.mark.tooling
def test_b155_path_b_floating_chat_does_not_inject_payload_as_html() -> None:
    """Säkerhet: copyDirective.payload är en validerad sträng från
    backend men kommer ursprungligen från operatörens prompt. Den
    måste alltid renderas som textnod, aldrig via
    ``dangerouslySetInnerHTML``.

    Vi söker bara JSX-attribut-användning (``dangerouslySetInnerHTML=``
    eller ``dangerouslySetInnerHTML:``) — kommentar-referenser som
    förklarar varför vi *inte* använder det räknas inte. Om någon
    framtida feature behöver det måste den medvetet introduceras i en
    separat komponent och vi uppdaterar testet då.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    jsx_use_pattern = re.compile(r"dangerouslySetInnerHTML\s*[=:]")
    assert not jsx_use_pattern.search(text), (
        "floating-chat.tsx får inte använda dangerouslySetInnerHTML på "
        "JSX-element eller i config-object — copyDirective.payload härstammar "
        "från operatörens prompt och måste renderas som textnod via React's "
        "automatic escape."
    )


# --- UI-gap-fix: exakt change-set i FloatingChat (2026-06-02) --------------
#
# Jakobs flagga: listan "Troligen ändrat" i FloatingChat var en
# prompt-heuristik, inte en backend-diff. Christopher-lane efter PR:
# härled en EXAKT change-set serverside genom att diffa nya runen mot
# föregående och visa den under "Ändrat". Dessa source-lock-tester hindrar
# att den exakta vägen tystas bort i en framtida refactor.


@pytest.mark.tooling
def test_change_set_helper_reuses_run_diff() -> None:
    """``lib/run-change-set.ts`` ska härleda change-set:en genom att
    återanvända den pure ``computeRunDiff`` + ``readRunArtefacts`` — inte
    genom att duplicera diff-logik eller röra build_site.py.
    """
    path = VIEWSER_DIR / "lib" / "run-change-set.ts"
    assert path.exists(), "run-change-set.ts saknas — exakt change-set kan inte härledas."
    text = path.read_text(encoding="utf-8")
    assert "export async function readRunChangeSet" in text, (
        "readRunChangeSet måste exporteras så /api/prompt kan kalla den."
    )
    assert "computeRunDiff" in text and "readRunArtefacts" in text, (
        "Change-set:en ska byggas på befintliga artefakter via computeRunDiff "
        "+ readRunArtefacts — ingen ny diff-implementation, ingen "
        "build_site.py-ändring."
    )


@pytest.mark.tooling
def test_prompt_route_exposes_change_set() -> None:
    """``/api/prompt`` måste anropa ``readRunChangeSet`` och exponera
    ``changeSet`` på top-level för follow-ups så FloatingChat kan rendera
    exakta deltas utan en separat round-trip.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "readRunChangeSet" in text, (
        "/api/prompt måste anropa readRunChangeSet efter runBuild — annars "
        "är changeSet alltid undefined och den exakta vägen kan aldrig användas."
    )
    assert "changeSet" in text, "changeSet måste ligga i return-objektet från runPromptBuildOnce."


@pytest.mark.tooling
def test_floating_chat_prefers_exact_change_set_over_heuristic() -> None:
    """FloatingChat måste föredra den exakta change-set:en
    (``summarizeChangeSet``) framför prompt-heuristiken
    (``summarizeChangesFromPrompt``) och växla rubriken "Ändrat" /
    "Troligen ändrat" på ``changesExact`` så operatören ser om listan är
    bekräftad eller en uppskattning.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "summarizeChangeSet" in text, (
        "FloatingChat måste importera/anropa summarizeChangeSet — annars "
        "renderas aldrig den exakta change-set:en."
    )
    assert "changesExact" in text, (
        "ChatMessage måste bära changesExact så UI:t kan skilja exakt diff "
        "från heuristik i rubriken."
    )
    assert '"Ändrat"' in text and '"Troligen ändrat"' in text, (
        "Rubriken måste växla mellan 'Ändrat' (exakt) och 'Troligen ändrat' "
        "(heuristik) — annars går ärlighetssignalen förlorad."
    )
    # Den exakta grenen måste ligga FÖRE heuristik-fallbacken i
    # summarizeBuildResult, annars blir prompt-gissningen aldrig ersatt.
    exact_idx = text.find("summarizeChangeSet(payload.changeSet)")
    heuristic_idx = text.find("summarizeChangesFromPrompt(userPrompt)")
    assert exact_idx != -1 and heuristic_idx != -1, (
        "Båda vägarna måste finnas i summarizeBuildResult."
    )
    assert exact_idx < heuristic_idx, (
        "Den exakta change-set-grenen måste utvärderas före prompt-"
        "heuristiken så bekräftade deltas vinner."
    )


@pytest.mark.tooling
def test_floating_chat_copy_directive_keeps_exact_change_set() -> None:
    """P1: när en run har BÅDE copy-direktiv OCH en exakt change-set (routes/
    variant) ska den strukturella change-set:en fortfarande visas under
    'Ändrat'. Tidigare returnerade copy-grenen utan changes och dolde
    tillagda/borttagna sidor. Source-lock att exactChanges beräknas före
    copy-grenen och bifogas där."""
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    copy_idx = text.find("const copyLines = summarizeCopyDirectives")
    exact_idx = text.find("const exactChanges = summarizeChangeSet")
    assert exact_idx != -1 and copy_idx != -1, (
        "Både exactChanges och copyLines måste härledas i build-outcome-mappningen."
    )
    assert exact_idx < copy_idx, (
        "exactChanges måste beräknas FÖRE copy-grenen så copy-grenen kan "
        "bifoga den strukturella change-set:en."
    )
