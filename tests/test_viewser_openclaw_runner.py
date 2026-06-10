"""Source-locks for the OpenClaw bridge stdout-parse contract (B174).

``scripts/run_openclaw_followup.py --apply`` shares stdout with
``build_site.build()``'s human progress, so the payload travels on a final
sentinel-prefixed line (``OPENCLAW_BRIDGE_JSON:``) that
``apps/viewser/lib/openclaw-runner.ts`` extracts with a backwards line scan
(bare-JSON fallback for the old format). These tests bind the TS<->Python
sentinel byte-identically and forbid the blind whole-stream JSON.parse that
caused B174's false degraded/QG warnings. The functional CLI half lives in
``tests/test_run_openclaw_followup.py``.
"""

from __future__ import annotations

import pytest

from tests.support.viewser import REPO_ROOT, VIEWSER_DIR


@pytest.mark.tooling
def test_openclaw_runner_extracts_bridge_json_from_noisy_stdout() -> None:
    """B174: ``--apply`` delar stdout med ``build_site.build()``:s mänskliga
    progress ("runId: ...", "Copying starter ...", npm-output) som skrivs FÖRE
    bridge-JSON:en. Den gamla blinda ``JSON.parse(stdout)`` kastade därför på
    VARJE lyckad apply -> ``null`` -> route:ns B164-recovery tvingade en falsk
    degraded/QG-varning trots grön build.

    Locks:
      1. Runnern har en backwards-skannande ``extractPayloadJson``-hjälpare
         (sista raden vinner — payloaden är alltid det SISTA scriptet skriver).
      2. Sentinel-kontraktet ``OPENCLAW_BRIDGE_JSON:`` finns och är byte-
         identiskt mellan TS-runnern och Python-seamen, och Python-sidan
         skriver payloaden med exakt ``print(f"{BRIDGE_SENTINEL_PREFIX}
         {payload}")``-formatet (en EGEN slutrad; formatet kan inte glida).
      3. Bare-JSON-fallbacken för det gamla formatet finns kvar
         (bakåtkompatibel: gammal Python-output parsas fortfarande).
      4. Ingen blind ``JSON.parse(stdout)`` finns kvar i runnern.
      5. Stream-cappen behåller SVANSEN (payloaden är sist) — head-keeping
         skulle tappa exakt payloaden vid overflow.
    """
    runner_text = (VIEWSER_DIR / "lib" / "openclaw-runner.ts").read_text(
        encoding="utf-8"
    )
    script_text = (REPO_ROOT / "scripts" / "run_openclaw_followup.py").read_text(
        encoding="utf-8"
    )

    sentinel = 'BRIDGE_SENTINEL_PREFIX = "OPENCLAW_BRIDGE_JSON:"'
    assert f"const {sentinel}" in runner_text, (
        "openclaw-runner.ts måste definiera sentinel-prefixet "
        "OPENCLAW_BRIDGE_JSON: (B174-kontraktet med Python-seamen)."
    )
    assert sentinel in script_text, (
        "run_openclaw_followup.py måste definiera SAMMA sentinel-prefix som "
        "TS-runnern (byte-identiskt literal) och skriva payloaden bakom det."
    )
    assert 'print(f"{BRIDGE_SENTINEL_PREFIX} {payload}")' in script_text, (
        "run_openclaw_followup.py:main() måste skriva payloaden på en EGEN "
        "slutrad med exakt formatet "
        'print(f"{BRIDGE_SENTINEL_PREFIX} {payload}") — glider formatet '
        "(annan separator/ordning) bryts sentinel-passet i TS-runnern tyst."
    )

    assert "function extractPayloadJson(" in runner_text, (
        "Runnern måste extrahera payloaden via extractPayloadJson i stället "
        "för blind JSON.parse på hela stdout."
    )
    extract_start = runner_text.index("function extractPayloadJson(")
    extract_body = runner_text[
        extract_start : runner_text.index("export type OpenClawDecisionPayload")
    ]
    assert "lines.length - 1" in extract_body and "i -= 1" in extract_body, (
        "extractPayloadJson måste skanna stdout-raderna BAKIFRÅN — payloaden "
        "är alltid det sista scriptet skriver."
    )
    assert "parseJsonObjectCandidate(lines[i])" in extract_body, (
        "Bare-JSON-fallbacken (gamla formatet utan sentinel) måste finnas kvar "
        "så en äldre Python-sida fortfarande parsas."
    )

    assert "JSON.parse(stdout)" not in runner_text, (
        "Blind JSON.parse på hela stdout-strömmen får inte återinföras — det "
        "är exakt B174-regressionen (progress-brus före JSON -> throw -> null "
        "-> falsk degraded via B164-recovery)."
    )

    # Stream-cappen: tail-keeping (shift äldsta chunken), inte head-keeping.
    assert "stdoutChunks.shift()" in runner_text, (
        "Stdout-cappen måste droppa de ÄLDSTA chunkarna vid overflow — "
        "payloaden ligger sist i strömmen, head-keeping tappar exakt den."
    )
