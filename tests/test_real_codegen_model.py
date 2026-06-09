"""E2E test for the real codegenModel call (Sprint 3B-next).

Gated on ``SAJTBYGGAREN_E2E=1`` + a working ``OPENAI_API_KEY`` so the
default test run never spends money. Mirrors
``tests/test_extract_site_brief.py:test_extract_site_brief_e2e_real_call``.

When the gating env vars are NOT set this file's only test is skipped,
keeping pytest deterministic and offline. The mocked-call paths
(success / error / no-key / unsupported-starter) are exercised by
``tests/test_codegen.py``.
"""

from __future__ import annotations

import os

import pytest

from packages.generation.codegen import produce_codegen_artefakt


@pytest.mark.tooling
@pytest.mark.e2e
@pytest.mark.skipif(
    os.environ.get("SAJTBYGGAREN_E2E") != "1"
    or not os.environ.get("OPENAI_API_KEY"),
    reason="SAJTBYGGAREN_E2E=1 and OPENAI_API_KEY required for real LLM call",
)
def test_real_codegen_model_call_marketing_base():
    """Real codegenModel call against marketing-base. Asserts:
    - source flips to 'real'
    - rationale is non-empty
    - usage tokens are non-zero (real call records prompt + completion)
    - error is None on the success path

    Uses a small but representative Generation Package so the LLM has
    enough context to produce a sensible rationale. Sprint 3B-next
    keeps the file list deterministic so we do not assert on files[]
    differing from the mock paths.
    """
    generation_package = {
        "siteBrief": {
            "businessTypeGuess": "electrician",
            "tone": ["trustworthy", "local"],
            "conversionGoals": ["call", "quote-request"],
            "servicesMentioned": ["akut-elservice", "laddbox-installation"],
        },
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "selectedDossiers": [],
    }
    result = produce_codegen_artefakt(
        generation_package,
        routes_written=["/", "/tjanster", "/om-oss", "/kontakt"],
        dossier_components=[],
        starter_id="marketing-base",
    )

    assert result.source == "real"
    assert result.error is None
    assert result.rationale.strip()
    assert result.usage.totalTokens > 0
    assert result.usage.promptTokens > 0
    # riskNotes may be empty if the model decided there were no risks;
    # 0-3 is the policy. Just check the cap holds.
    assert 0 <= len(result.riskNotes) <= 3
