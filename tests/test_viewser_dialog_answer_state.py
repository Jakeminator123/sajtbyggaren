"""B192: answer-only-svar via dialogvägen renderas som info, inte rött fel.

Conversation gate:n (small_talk / site_opinion / question) svarar utan att
bygga. FloatingChat renderade alltid svaret som info-bubbla, men dialogerna
(färgväljare, modul-dialog, inspector m.fl. som konsumerar
``use-followup-build``) la svarstexten i ``error``-state och stylade den
destructive — ett ärligt svar såg ut som ett fel.

Fixen (2026-06-11): hooken separerar ``answer`` från ``error`` och varje
dialog-caller renderar ``answer`` som neutral info (``role="status"``).
Resultatkontraktet (``{ok: false, error, isAnswer: true}``) är oförändrat
så builder-shellens toast-väg fortsätter fungera identiskt.

Källskannande lås (samma mönster som tests/test_viewser_runs_versions.py):
ingen jsdom-rendering, bara strukturella kontrakt mot TS-källan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling]

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_DIR = REPO_ROOT / "apps" / "viewser" / "components" / "builder"

HOOK_PATH = BUILDER_DIR / "use-followup-build.ts"

# Alla ytor som renderar hookens feedback-state inline. quick-prompt-button
# saknar egen rendering (builder-shellens toast tar svaret) och builder-shell
# låses separat nedan på toast-varianten.
INLINE_RENDER_SURFACES = [
    BUILDER_DIR / "dialogs" / "add-module-dialog.tsx",
    BUILDER_DIR / "dialogs" / "asset-uploader-dialog.tsx",
    BUILDER_DIR / "dialogs" / "color-picker-dialog.tsx",
    BUILDER_DIR / "dialogs" / "colorize-section-dialog.tsx",
    BUILDER_DIR / "dialogs" / "scrape-url-dialog.tsx",
    BUILDER_DIR / "dialogs" / "variant-picker-dialog.tsx",
    BUILDER_DIR / "inspector" / "site-inspector-sheet.tsx",
]


def test_hook_separates_answer_state_from_error() -> None:
    """Answer-only-grenen får ALDRIG landa i ``error``-state igen."""
    text = HOOK_PATH.read_text(encoding="utf-8")
    assert "const [answer, setAnswer] = useState<string | null>(null);" in text, (
        "B192-regression: hooken måste hålla answer-only-svar i ett separat "
        "``answer``-state — inte i ``error``."
    )
    # Den gamla buggen: svarstexten skrevs till error-state.
    assert "setError(answer)" not in text and "setError(answerReply)" not in text, (
        "B192-regression: answer-only-svaret får inte sättas via setError — "
        "då renderar dialogerna det som rött fel igen."
    )
    assert "setAnswer(answerReply)" in text, (
        "Answer-only-grenen måste sätta ``answer``-state (setAnswer)."
    )
    # Resultatkontraktet är oförändrat: isAnswer-diskriminatorn finns kvar
    # så builder-shellens toast (variant info) fortsätter fungera.
    assert "isAnswer: true" in text
    assert "return { runFollowup, isBusy, error, answer, clearError };" in text, (
        "Hooken måste exponera ``answer`` bredvid ``error`` till callers."
    )


def test_hook_clears_both_states_on_clear_and_new_run() -> None:
    text = HOOK_PATH.read_text(encoding="utf-8")
    clear_idx = text.index("const clearError = useCallback")
    clear_block = text[clear_idx : clear_idx + 200]
    assert "setError(null)" in clear_block and "setAnswer(null)" in clear_block, (
        "clearError måste rensa BÅDA tillstånden — callers använder den som "
        "'rensa feedback' vid stängning/återöppning."
    )
    run_idx = text.index("setIsBusy(true);")
    run_block = text[run_idx : run_idx + 200]
    assert "setError(null)" in run_block and "setAnswer(null)" in run_block, (
        "Ett nytt bygge måste nollställa både error och answer."
    )


@pytest.mark.parametrize(
    "surface", INLINE_RENDER_SURFACES, ids=lambda path: path.name
)
def test_dialog_surfaces_render_answer_as_neutral_info(surface: Path) -> None:
    """Varje inline-yta renderar ``answer`` som info (role=status), inte rött."""
    text = surface.read_text(encoding="utf-8")
    assert "answer" in text and 'role="status"' in text, (
        f"B192-regression i {surface.name}: answer-only-svar måste renderas "
        'som neutral info (role="status") — inte i den destructive '
        "error-rutan."
    )
    # Svaret får inte stylas destructive: status-blocket och alert-blocket
    # ska vara skilda — leta upp status-blocket och kontrollera att det
    # inte använder destructive-klasserna.
    status_idx = text.index('role="status"')
    # Status-blocket slutar där nästa alert-block (error) börjar — annars
    # läcker error-blockets destructive-klasser in i fönstret.
    alert_idx = text.find('role="alert"', status_idx)
    status_end = alert_idx if alert_idx != -1 else status_idx + 300
    status_block = text[status_idx:status_end]
    assert "text-destructive" not in status_block, (
        f"B192-regression i {surface.name}: status-blocket (answer) får inte "
        "använda destructive-styling."
    )


def test_builder_shell_keeps_info_toast_for_answers() -> None:
    """Toast-vägen (quick-prompts m.fl.) visar svar som info, inte error."""
    text = (BUILDER_DIR / "builder-shell.tsx").read_text(encoding="utf-8")
    assert 'result.isAnswer ? "info" : "error"' in text, (
        "builder-shell måste fortsätta välja toast-variant på isAnswer-"
        "diskriminatorn (info för svar, error för riktiga fel)."
    )
