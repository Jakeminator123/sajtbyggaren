"""Source guards for Viewser follow-up version metadata.

These tests intentionally avoid tests/test_viewser_files.py because the
follow-up sprint is scoped away from the StackBlitz file surface locked
there. They guard the Viewser-side contract only: RunHistory must prefer
immutable per-run metadata, and the Project Input picker must not list
version snapshot files as duplicate selectable sites.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"


@pytest.mark.tooling
def test_run_history_prefers_immutable_run_metadata_before_sidecar() -> None:
    runs_ts = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")

    build_result_project = runs_ts.index("stringOrUndefined(result.projectId)")
    input_meta_project = runs_ts.index("inputMeta.projectId")
    prompt_meta_project = runs_ts.index("promptMeta.projectId")
    assert build_result_project < input_meta_project < prompt_meta_project

    build_result_version = runs_ts.index("numberOrNull(result.version)")
    input_meta_version = runs_ts.index("inputMeta.version")
    prompt_meta_version = runs_ts.index("promptMeta.version")
    assert build_result_version < input_meta_version < prompt_meta_version


@pytest.mark.tooling
def test_project_input_picker_filters_version_snapshots() -> None:
    project_inputs_ts = (VIEWSER_DIR / "lib" / "project-inputs.ts").read_text(
        encoding="utf-8"
    )

    assert "VERSIONED_PROJECT_INPUT_PATTERN" in project_inputs_ts
    assert "!VERSIONED_PROJECT_INPUT_PATTERN.test(entry.name)" in project_inputs_ts


@pytest.mark.tooling
def test_viewser_python_runners_prefer_repo_venv() -> None:
    for relative in ("lib/prompt-runner.ts", "lib/build-runner.ts"):
        text = (VIEWSER_DIR / relative).read_text(encoding="utf-8")
        assert "existsSync" in text
        assert '".venv"' in text
        assert '"bin/python"' in text


@pytest.mark.tooling
def test_serialized_prompt_and_build_runners_clear_inflight_promises() -> None:
    """Lås att både prompt- och build-runners använder try/finally-mönstret
    (await + cleanup), INTE ``.finally(() => ...)``-callback som lätt
    skapar unhandled rejection.

    Båda runners använder numera samma per-site Map-mönster:
    registrera promise:n i Map:en FÖRE ``return await promise``, och
    rensa entry:t i ``finally`` bara om promise:n fortfarande är den
    aktiva (identity-guard via ``Map.get(...) === promise`` + delete),
    så en samtidig caller som hunnit skriva en ny entry för samma
    nyckel inte oavsiktligt nukas.

    NB: sentinel för build-runner.ts uppdaterades 2026-05-25 från
    ``inFlight = promise;`` (gammal global mutex) till
    ``inFlight.set(siteId, promise);`` (per-siteId Map-mutex),
    reviewer-fynd Round 2 #5 — den globala varianten blockerade
    orelaterade siteIds. B169 (2026-06) gav prompt-routen samma
    mönster: ``promptInFlight.set(queueKey, promise);`` där queueKey
    är siteId för follow-ups och en unik init-nyckel annars. Det
    dedikerade testet
    ``test_build_runner_uses_per_site_mutex_not_global_inflight``
    i ``test_viewser_files.py`` låser den fullständiga Map-strukturen;
    här bekräftar vi registrering-före-await + identity-guardad
    cleanup via try/finally.
    """
    for relative, register_sentinel, cleanup_guard in (
        (
            "app/api/prompt/route.ts",
            "promptInFlight.set(queueKey, promise);",
            "if (promptInFlight.get(queueKey) === promise) {",
        ),
        (
            "lib/build-runner.ts",
            "inFlight.set(siteId, promise);",
            "if (inFlight.get(siteId) === promise) {",
        ),
    ):
        text = (VIEWSER_DIR / relative).read_text(encoding="utf-8")
        assert register_sentinel in text, (
            f"{relative} saknar ``{register_sentinel}``-sentinel. "
            "Promise-registreringen i per-site-Map:en ska ske INNAN "
            "``return await promise`` så cleanup-grenen kan "
            "identitets-jämföra mot rätt instans."
        )
        assert "return await promise;" in text
        assert text.index(register_sentinel) < text.index(
            "return await promise;"
        ), (
            f"{relative}: Map-registreringen ``{register_sentinel}`` "
            "måste ske FÖRE ``return await promise;``."
        )
        assert cleanup_guard in text, (
            f"{relative} saknar identity-guard ``{cleanup_guard}`` i "
            "cleanup-grenen — entry:t får bara raderas om promise:n "
            "fortfarande är den aktiva."
        )
        assert ".finally(() =>" not in text
