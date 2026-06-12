"""Source-level locks för hostad asset_set-forwarding (task A:s hostade halva).

Operatörs-GO 2026-06-11: strukturerade ``asset_set``-intents ska forwardas
även i den hostade byggvägen, med SAMMA sanering som den lokala spawn-vägen.
Kedjan som låses (källkods-lås, samma mönster som
``test_viewser_hosted_build_status.py``):

1. ``/api/prompt`` (hostat läge) trär ``payload.toolIntent`` in i
   ``startHostedBuild`` — payloaden är redan Zod-validerad av
   ``PromptPayloadSchema`` (followup-only via superRefine).
2. ``hosted-build-runner.ts`` återanvänder ``sanitizedAssetSetIntent``
   från ``prompt-runner.ts`` (en saneringskälla, två spawn-sömmar) och
   injicerar resultatet som env ``TOOL_INTENT_JSON`` — aldrig
   interpolerad i bash-koden.
3. Orkestrerings-skriptet skickar ``--tool-intent "$TOOL_INTENT_JSON"``
   till ``prompt_to_project_input.py`` ENBART i följdläge och ENBART när
   env-värdet är icke-tomt (set -u-säker array-expansion).

Hostade följdprompter failar fortfarande ärligt tills run-historiken
persisteras (B194) — det här är forward-kompatibel plumbing som aktiveras
när persistensen landar, medvetet skeppad nu så kontraktet inte driftar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling]

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
PROMPT_ROUTE = VIEWSER / "app" / "api" / "prompt" / "route.ts"
RUNNER = VIEWSER / "lib" / "hosted-build-runner.ts"
PROMPT_RUNNER = VIEWSER / "lib" / "prompt-runner.ts"


def test_sanitizer_is_exported_and_shared() -> None:
    """En saneringskälla: hosted-runnern importerar prompt-runnerns export."""
    prompt_runner = PROMPT_RUNNER.read_text(encoding="utf-8")
    assert "export function sanitizedAssetSetIntent" in prompt_runner, (
        "sanitizedAssetSetIntent måste vara exporterad så den hostade vägen "
        "kan återanvända EXAKT samma sanering som den lokala spawn-vägen."
    )
    runner = RUNNER.read_text(encoding="utf-8")
    # Importeras från prompt-runner.ts (samma modul; ev. tillsammans med
    # sanitizedMarkedSections efter commit 3) — ingen egen kopia som kan drifta.
    assert "sanitizedAssetSetIntent" in runner
    assert 'from "./prompt-runner";' in runner, (
        "hosted-build-runner.ts måste importera saneringen från "
        "prompt-runner.ts — ingen egen kopia som kan drifta."
    )


def test_runner_sanitizes_followup_only_and_injects_env() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    # Saneringen körs bara i följdläge — init-byggen har ingen toolIntent-yta.
    assert "req.followup && req.toolIntent" in runner, (
        "toolIntent får bara saneras/forwardas i följdläge (samma regel som "
        "API-schemats superRefine)."
    )
    # Env-injektionen: alltid definierad (set -u-säkert), tom när intentet
    # saknas eller underkändes i saneringen.
    assert (
        'TOOL_INTENT_JSON: safeToolIntent ? JSON.stringify(safeToolIntent) : ""'
        in runner
    ), (
        "TOOL_INTENT_JSON måste alltid sättas i sandboxEnv — tom sträng är "
        "den ärliga 'ingen flagga'-signalen till skriptet."
    )


def test_orchestration_script_forwards_flag_only_when_set() -> None:
    """Bash-sidan: flaggan läggs bara till när env-värdet är icke-tomt, via
    set -u-säker array-expansion, och bara i FOLLOWUP_MODE-grenen."""
    runner = RUNNER.read_text(encoding="utf-8")
    # Skriptet byggs i en JS-template-literal, så bash-${...} är \${...} i källan.
    assert 'if [ -n "\\${TOOL_INTENT_JSON:-}" ]; then' in runner
    assert 'TOOL_INTENT_ARGS=(--tool-intent "$TOOL_INTENT_JSON")' in runner, (
        "Intent-JSON:en får bara nå CLI:t som quotad env-expansion — aldrig "
        "interpolerad i bash-koden."
    )
    set_u_safe_expansion = '\\${TOOL_INTENT_ARGS[@]+"\\${TOOL_INTENT_ARGS[@]}"}'
    assert set_u_safe_expansion in runner, (
        "Array-expansionen måste vara set -u-säker (idiomet "
        '${arr[@]+"${arr[@]}"}) så ett bygge utan intent inte kraschar.'
    )
    # Flaggan hör hemma i den LEGACY followup-grenen (prompt_to_project_input
    # --followup-site-id), inte i init-anropet. OBS: efter commit 2 använder
    # OpenClaw apply-anropet också `--site-id "$SITE_ID"`, så vi ankrar på det
    # specifika init-PI-anropet i stället för bara `--site-id`.
    followup_call = runner.index("--followup-site-id")
    init_pi_call = runner.index(
        'prompt_to_project_input.py "$PROMPT_TEXT" --site-id "$SITE_ID"'
    )
    expansion_at = runner.index(set_u_safe_expansion)
    assert followup_call < expansion_at < init_pi_call, (
        "--tool-intent-expansionen måste ligga i den legacy followup-grenen "
        "av orkestrerings-skriptet."
    )


def test_prompt_route_threads_tool_intent_into_hosted_flow() -> None:
    source = PROMPT_ROUTE.read_text(encoding="utf-8")
    assert (
        "...(payload.toolIntent ? { toolIntent: payload.toolIntent } : {})"
        in source
    ), (
        "runHostedPromptFlow måste trä payload.toolIntent in i "
        "startHostedBuild — annars tappar hostade byggen den strukturerade "
        "intenten som den lokala vägen redan konsumerar."
    )
