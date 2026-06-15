"""Source-level locks för hostad run-state-persistens (B194).

Lokalt härleder ``prompt_to_project_input.py --followup-site-id`` föregående
version ur ``data/prompt-inputs/<siteId>.{project-input,meta}.json``. I en
färsk Vercel Sandbox fanns de filerna aldrig, så hostade följdprompter
failade ärligt (B194, extern granskning #284 fynd A). Kedjan som låses
(källkods-lås, samma mönster som ``test_viewser_hosted_tool_intent.py``):

1. Efter varje lyckat hostat bygge laddar orkestrerings-skriptet upp det
   färska PI/meta-paret VERSIONS-SCOPAT till blob under
   ``run-state/<siteId>/v<N>/`` och sätter den durabla KV-pekaren
   ``viewser:site:<siteId>:run-state`` — pekaren flyttas först när BÅDA
   filerna är uppe, så ett halvlyckat par aldrig kan refereras.
2. Vid followup läser ``startHostedBuild`` pekaren pre-flight: saknas eller
   ogiltig → ärlig fail FÖRE Sandbox.create (ingen dyr sandbox som dör på
   samma sak). Giltig → URL:erna når sandboxen som env
   ``RUN_STATE_PI_URL``/``RUN_STATE_META_URL``.
3. Skriptet curlar ner paret till ``data/prompt-inputs/`` innan
   followup-kommandot körs — exakt de paths Python-sidan redan läser.
4. Run-state-upload-fel efter ett lyckat bygge faller ALDRIG bygget (sajten
   är redan publicerad) men lämnar pekaren orörd: nästa följdprompt utgår
   från senast konsistenta paret.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = (
    REPO_ROOT / "apps" / "viewser" / "lib" / "hosted-build-runner.ts"
)


def _runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_run_state_key_and_pointer_shape_are_exported() -> None:
    """Pekarens nyckel + form är exporterade kontrakt (status-routes/tester)."""
    source = _runner_source()
    assert "export function hostedRunStateKey" in source
    assert "return `viewser:site:${siteId}:run-state`;" in source, (
        "Run-state-pekaren måste ligga i samma namnrymd som "
        "viewser:site:<siteId>:current — en sajt, en pekarfamilj."
    )
    assert "export interface HostedRunStatePointer" in source
    interface_body = source.split("export interface HostedRunStatePointer", 1)[1].split(
        "\n}", 1
    )[0]
    for field in ("version", "projectInputUrl", "metaUrl", "updatedAt"):
        assert field in interface_body, (
            f"HostedRunStatePointer måste deklarera fältet {field!r}."
        )
    # B199: de valfria artefakt-fälten ligger på SAMMA pekare (en sajt, en
    # pekarfamilj) — build_site-runId + tarball-URL för hydreringen.
    for field in ("runId?", "runArtifactsUrl?"):
        assert field in interface_body, (
            f"HostedRunStatePointer måste deklarera det valfria B199-fältet "
            f"{field!r}."
        )


def test_followup_preflight_fails_honestly_without_pointer() -> None:
    """Saknad/ogiltig pekare → ärlig fail FÖRE Sandbox.create."""
    source = _runner_source()
    assert "kvGetJson<HostedRunStatePointer>" in source, (
        "Followup-preflighten måste läsa pekaren via kv-store-adaptern "
        "(samma leverantörsneutralitet som run-statusen)."
    )
    assert 'projectInputUrl.startsWith("https://")' in source, (
        "Pekarens URL:er måste valideras (https) innan de skickas som env "
        "till sandboxen."
    )
    assert "Hostad följdprompt kräver persisterad run-state" in source, (
        "Felmeddelandet måste förklara VARFÖR följdprompten failar och vad "
        "operatören gör åt det (kör initialt hostat bygge)."
    )
    # Preflighten måste ske före sandbox-skapandet, inte i skriptet.
    preflight_at = source.index("Hostad följdprompt kräver persisterad run-state")
    create_at = source.index("sdk.Sandbox.create")
    assert preflight_at < create_at, (
        "Run-state-preflighten måste köras FÖRE Sandbox.create — annars "
        "betalar vi för en sandbox som dör på ett förutsägbart fel."
    )


def test_run_state_urls_reach_sandbox_as_env() -> None:
    """URL:erna injiceras alltid (set -u-säkert): tomma vid initialbygge."""
    source = _runner_source()
    assert 'RUN_STATE_PI_URL: runState?.projectInputUrl ?? ""' in source
    assert 'RUN_STATE_META_URL: runState?.metaUrl ?? ""' in source


def test_script_downloads_state_before_followup_command() -> None:
    """Bash-sidan: paret hämtas till data/prompt-inputs/ före followup-PI."""
    source = _runner_source()
    assert "fetch_run_state()" in source
    assert (
        'fetch_run_state "$RUN_STATE_PI_URL" "$REPO_DIR/data/prompt-inputs/$SITE_ID.project-input.json"'
        in source
    ), "PI-snapshotet måste landa på exakt den path Python-sidan läser."
    assert (
        'fetch_run_state "$RUN_STATE_META_URL" "$REPO_DIR/data/prompt-inputs/$SITE_ID.meta.json"'
        in source
    ), "Meta-snapshotet måste landa på exakt den path Python-sidan läser."
    download_at = source.index('fetch_run_state "$RUN_STATE_PI_URL"')
    followup_call_at = source.index("--followup-site-id")
    assert download_at < followup_call_at, (
        "Nedladdningen måste ske INNAN prompt_to_project_input.py "
        "--followup-site-id körs."
    )
    # set -u-säkra referenser i skriptet (template-literal-escapade i källan).
    assert '"\\${RUN_STATE_PI_URL:-}"' in source
    assert '"\\${RUN_STATE_META_URL:-}"' in source


def test_script_publishes_versioned_pair_and_pointer_after_build() -> None:
    """Paret publiceras versions-scopat och pekaren flyttas sist."""
    source = _runner_source()
    assert "run-state/$SITE_ID/v$RUN_STATE_VERSION/" in source, (
        "Run-state-blobben måste vara versions-scopad (v<N>) så ett "
        "halvlyckat upload-par aldrig kan refereras av en gammal pekare."
    )
    # Pekaren sätts bara när BÅDA uploads lyckats.
    assert (
        '[ -n "$RUN_STATE_PI_PUBLISHED" ] && [ -n "$RUN_STATE_META_PUBLISHED" ]'
        in source
    ), "KV-pekaren får bara flyttas när både PI och meta är uppladdade."
    assert '":run-state"' in source
    # Upload-ordningen: run-state publiceras EFTER manifestet (B195) och
    # current-pekaren men FÖRE den SLUTGILTIGA done-statusen. OBS: answer-only-
    # grenen (commit 2) postar en tidigare ``post_status "done"`` + exit, så vi
    # ankrar på den SISTA (rindex) som är den riktiga bygg-done.
    manifest_at = source.index('upload_file ".manifest.json"')
    run_state_at = source.index("upload_run_state()")
    done_at = source.rindex('post_status "done"')
    assert manifest_at < run_state_at < done_at


def test_run_state_failure_never_fails_a_published_build() -> None:
    """Upload-fel efter lyckat bygge → varning, inte fail (sajten är ute)."""
    source = _runner_source()
    warning_at = source.index(
        "run-state-paret kunde inte publiceras"
    )
    done_at = source.rindex('post_status "done"')
    assert warning_at < done_at, (
        "Run-state-felvägen måste leda vidare till done-status — bygget är "
        "redan publicerat och får inte rapporteras som failed."
    )
    # Felvägen får inte anropa fail() — hitta raden och verifiera.
    segment = source[warning_at - 200 : warning_at + 200]
    assert "fail " not in segment and 'fail "' not in segment, (
        "Run-state-upload-fel får inte trigga fail() — bara varning + orörd "
        "pekare."
    )


def test_run_artifacts_tarball_published_and_threaded_into_pointer() -> None:
    """B199: de kanoniska run-artefakterna tarballas och pekaren bär URL:en."""
    source = _runner_source()
    # build_site-stdout-runId fångas SKILT från orkestreringens KV-UUID.
    assert "RUN_ARTIFACT_RUN_ID=$(printf" in source, (
        "build_site.py-stdout-runId måste fångas (skild från KV-UUID $RUN_ID) "
        "så artefakt-tarballen och nästa followups hydrering hittar rätt "
        "data/runs/<runId>/."
    )
    # En tarball (1 PUT), versions-scopad under run-artifacts/<siteId>/v<N>/.
    assert "run-artifacts/$SITE_ID/v$RUN_STATE_VERSION/run-artifacts.tar.gz" in source
    assert (
        'tar -czf /tmp/run-artifacts.tar.gz -C "$REPO_DIR/data/runs" "$RUN_ARTIFACT_RUN_ID"'
        in source
    ), "Tarballens topp-katalog måste vara runId så extraktionen återställer data/runs/<runId>/."
    # Pekaren bär runId + runArtifactsUrl ENBART när tarballen publicerades.
    assert 'doc["runId"] = artifact_run_id' in source
    assert 'doc["runArtifactsUrl"] = artifacts_url' in source
    assert "if artifacts_url and artifact_run_id:" in source, (
        "Artefakt-fälten får bara skrivas till pekaren när tarballen faktiskt "
        "publicerades — annars tom URL = ingen hydrering (ärligt)."
    )


def test_run_artifacts_failure_never_fails_a_published_build() -> None:
    """B199: artefakt-upload-fel faller aldrig ett redan publicerat bygge."""
    source = _runner_source()
    warning_at = source.index("run-artefakt-tarballen kunde inte publiceras")
    done_at = source.rindex('post_status "done"')
    assert warning_at < done_at
    segment = source[warning_at - 200 : warning_at + 200]
    assert "fail " not in segment and 'fail "' not in segment, (
        "Artefakt-upload-fel får bara varna — bygget är redan publicerat."
    )
