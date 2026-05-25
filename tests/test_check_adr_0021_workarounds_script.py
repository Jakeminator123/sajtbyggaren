"""Tests for ``scripts/check_adr_0021_workarounds.py`` exit behavior.

Codex P2 fynd (PR #98 review): scriptet returnerade tidigare exit 0
även om EN del lookups failade (``state="unknown"``), så länge minst
en lookup lyckades. Det undergrävde scriptets syfte: automation/cron-
jobb skulle klassa en ofullständig check som healthy och missa att
ADR 0021-omprövningssignalen är opålitlig för den körningen.

Fixen ändrar ``main()`` så ALL ``state="unknown"`` (även partial)
ger exit 1. Closed/open är fortsatt informational (exit 0).

Dessa tester monkeypatchar ``fetch_issue_status`` så scriptet aldrig
gör riktiga GitHub-anrop. ``parse_issue_refs_from_adr()`` läser den
verkliga ADR 0021-filen för att producera realistiska ``IssueRef``-
objekt; det är en billig och stabil read som ej kräver nätverk.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


@pytest.fixture
def workarounds_module():
    """Importera scriptet som en modul utan att köra ``main()``.

    Scriptet ligger i ``scripts/`` (inte en package), så vi måste
    lägga till mappen på sys.path. Hela paret läggs till och tas
    bort i fixturen för att undvika sidoeffekter på andra tester.
    """
    str_scripts_dir = str(SCRIPTS_DIR)
    added = False
    if str_scripts_dir not in sys.path:
        sys.path.insert(0, str_scripts_dir)
        added = True
    try:
        # Re-import för att garantera att vi får en färsk modul
        # även om ett tidigare test redan importerat den.
        if "check_adr_0021_workarounds" in sys.modules:
            del sys.modules["check_adr_0021_workarounds"]
        module = importlib.import_module("check_adr_0021_workarounds")
        yield module
    finally:
        if added:
            sys.path.remove(str_scripts_dir)
        sys.modules.pop("check_adr_0021_workarounds", None)


def _make_status(module, ref, state, error=None):
    """Bygg ett ``IssueStatus`` med given state utan att röra HTTP."""
    return module.IssueStatus(
        ref=ref,
        state=state,
        title="(test)",
        closed_at="2026-04-11T00:00:00Z" if state == "closed" else None,
        error=error,
    )


def _patch_fetch(monkeypatch, module, state_sequence):
    """Patch:a ``parse_issue_refs_from_adr`` + ``fetch_issue_status`` så
    testet är oberoende av ADR-filens nuvarande antal issue-URL:er.

    ``state_sequence`` är en lista med strängar (``"open"`` / ``"closed"`` /
    ``"unknown"``). Tester med "unknown" lägger ``error="HTTP 403"`` så
    rendern visar en realistisk fel-rad och så scriptets unknown-gren
    triggas på samma sätt som den verkliga rate-limit-fallet skulle.

    Mockar också ``sys.argv`` så scriptets ``argparse.parse_args()``
    inte plockar upp pytest-flaggorna (``-v``, ``--tb`` etc.) och
    failar med "unrecognized arguments".
    """
    fake_refs = [
        module.IssueRef(owner="vercel", repo="next.js", number=92656),
        module.IssueRef(owner="stackblitz", repo="webcontainer-core", number=2045),
        module.IssueRef(owner="stackblitz", repo="webcontainer-core", number=1739),
    ]
    fake_refs = fake_refs[: len(state_sequence)]

    iterator = iter(state_sequence)

    def fake_fetch(ref):
        state = next(iterator)
        return _make_status(
            module,
            ref,
            state,
            error="HTTP 403: rate limited" if state == "unknown" else None,
        )

    monkeypatch.setattr(module, "parse_issue_refs_from_adr", lambda: list(fake_refs))
    monkeypatch.setattr(module, "fetch_issue_status", fake_fetch)
    monkeypatch.setattr(sys, "argv", ["check_adr_0021_workarounds.py"])


@pytest.mark.tooling
def test_main_exit_0_when_all_open(workarounds_module, monkeypatch, capsys):
    """Baseline: alla issues open → exit 0 (workarounds berättigade)."""
    _patch_fetch(
        monkeypatch,
        workarounds_module,
        ["open", "open", "open"],
    )
    exit_code = workarounds_module.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Alla issues är fortfarande öppna" in out


@pytest.mark.tooling
def test_main_exit_0_when_some_closed_none_unknown(
    workarounds_module, monkeypatch, capsys
):
    """En closed + två open → exit 0 (informational nudge, ingen CI gate)."""
    _patch_fetch(
        monkeypatch,
        workarounds_module,
        ["open", "closed", "open"],
    )
    exit_code = workarounds_module.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "ÅTGÄRD: ett eller flera issues är STÄNGDA" in out


@pytest.mark.tooling
def test_main_exit_1_when_all_unknown(workarounds_module, monkeypatch, capsys):
    """Bevara gammal behavior: alla unknown → exit 1 (totalt nätverksfel)."""
    _patch_fetch(
        monkeypatch,
        workarounds_module,
        ["unknown", "unknown", "unknown"],
    )
    exit_code = workarounds_module.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "VARNING" in out


@pytest.mark.tooling
def test_main_exit_1_when_partial_unknown(workarounds_module, monkeypatch, capsys):
    """Codex P2 kärnfix: en unknown bland två open → exit 1.

    Tidigare returnerade scriptet exit 0 så länge minst en lookup
    lyckades. Det betydde att en cron-körning som rate-limitades
    på en enskild request klassades som healthy, vilket är fel
    enligt scriptets dokumenterade syfte. Den här testet låser
    den nya behaviorn så framtida refactor inte kan återinföra
    den breda all-unknown-grenen.
    """
    _patch_fetch(
        monkeypatch,
        workarounds_module,
        ["open", "unknown", "open"],
    )
    exit_code = workarounds_module.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "VARNING" in out, (
        "Partial unknown ska visa VARNING-raden i text-rendern så "
        "operatören vet varför exit 1 skickas."
    )


@pytest.mark.tooling
def test_main_exit_1_when_closed_and_unknown_mix(
    workarounds_module, monkeypatch, capsys
):
    """Closed + unknown blandning → exit 1 (unknown vinner exit-koden).

    Texten ska visa BÅDE closed-åtgärden OCH unknown-varningen så
    operatören inte missar att checken är opålitlig för den
    closed-rapporten också.
    """
    _patch_fetch(
        monkeypatch,
        workarounds_module,
        ["closed", "unknown", "open"],
    )
    exit_code = workarounds_module.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "ÅTGÄRD: ett eller flera issues är STÄNGDA" in out
    assert "VARNING" in out, (
        "Render ska visa både closed-åtgärd och unknown-varning samtidigt "
        "när båda finns — annars förlorar operatören kontext om exit 1."
    )


@pytest.mark.tooling
def test_docstring_documents_partial_unknown_returns_1(workarounds_module):
    """Dokumentation ska matcha implementation: partial unknown → exit 1.

    Codex P2-fyndets ursprungliga oro var att docstring och exit-
    behavior skilde sig åt. Låsa att docstring nu nämner partial-
    failure-grenen så framtida läsare inte vilseledas.
    """
    doc = workarounds_module.__doc__ or ""
    assert "one or more issue lookups failed" in doc, (
        "Modul-docstring måste dokumentera att partial unknown ger "
        "exit 1, inte bara fullständig fetch-failure."
    )
    assert 'state="unknown"' in doc, (
        "Modul-docstring måste referera till state=\"unknown\" så "
        "framtida läsare förstår vilken klassificering som triggar exit 1."
    )
