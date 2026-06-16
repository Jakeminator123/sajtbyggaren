"""Tests for scripts/fetch_model_prices.py + backoffice/runtime_models.py.

Pins the honest contract for the token-price snapshot:

- the parser only extracts prices that literally appear on the pricing page
  (exact label match after stripping the parenthetical suffix, first
  occurrence wins, "-"/"Free"/null -> None) - never an invented number,
- the offline fallback never crashes, keeps existing values and flags
  ``needsRefresh: true``,
- the model list is derived dynamically (policy + parsed source fallbacks),
  never from a hardcoded model-name constant - so the parallel
  gpt-4o -> gpt-5.5 fallback bump needs no change here,
- the committed placeholder snapshot contains no invented prices.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "data" / "model-pricing.json"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_model_prices as fmp  # noqa: E402

# A faithful miniature of the pricing page's embedded row format (verified
# against a real fetch of developers.openai.com/api/docs/pricing 2026-06-11).
SAMPLE_PRICING_TEXT = """
        rows={[
          ["gpt-5.5 (<272K context length)", 5, 0.5, 30],
          ["gpt-5.5-pro (<272K context length)", 30, "", 180],
          ["gpt-5.4 (<272K context length)", 2.5, 0.25, 15],
          ["gpt-4o", 2.5, 1.25, 10],
          ["o1-pro", 150, null, 600],
        ]}
            rows: [
              ["text-embedding-3-small", 0.02, "-", "-"],
            ],
          rows={[
            ["gpt-5.5 (<272K context length)", 99, 9, 999],
          ]}
"""


@pytest.mark.tooling
def test_parse_prices_exact_label_match_and_first_occurrence_wins() -> None:
    prices = fmp.parse_prices(
        SAMPLE_PRICING_TEXT, ["gpt-5.5", "gpt-5.4", "gpt-4o", "text-embedding-3-small"]
    )
    # First occurrence (standard pane) wins over the later 99/999 row.
    assert prices["gpt-5.5"] == {"inputPer1M": 5.0, "outputPer1M": 30.0}
    assert prices["gpt-5.4"] == {"inputPer1M": 2.5, "outputPer1M": 15.0}
    assert prices["gpt-4o"] == {"inputPer1M": 2.5, "outputPer1M": 10.0}
    # "-" output -> honest None, never 0.
    assert prices["text-embedding-3-small"] == {"inputPer1M": 0.02, "outputPer1M": None}


@pytest.mark.tooling
def test_parse_prices_never_prefix_matches_or_invents() -> None:
    # gpt-5.5 must NOT pick up the gpt-5.5-pro row, and an absent model
    # yields no entry at all (no invented numbers).
    prices = fmp.parse_prices(SAMPLE_PRICING_TEXT, ["gpt-5.5-pro", "gpt-nope"])
    assert prices["gpt-5.5-pro"] == {"inputPer1M": 30.0, "outputPer1M": 180.0}
    assert "gpt-nope" not in prices


@pytest.mark.tooling
def test_to_price_handles_dash_free_null_and_numbers() -> None:
    assert fmp._to_price("2.5") == 2.5
    assert fmp._to_price('"0.25"') == 0.25
    assert fmp._to_price('"-"') is None
    assert fmp._to_price('"Free"') is None
    assert fmp._to_price("null") is None


@pytest.mark.tooling
def test_offline_run_keeps_values_and_flags_needs_refresh(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "model-pricing.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "version": 1,
                "needsRefresh": False,
                "lastFetched": "2026-06-01T00:00:00+00:00",
                "source": "https://example.test",
                "models": [
                    {
                        "model": "gpt-5.4",
                        "inputPer1M": 2.5,
                        "outputPer1M": 15,
                        "source": "https://example.test",
                        "fetchedAt": "2026-06-01T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = fmp.main(["--offline", "--output", str(snapshot_path)])
    assert exit_code == 0

    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert data["needsRefresh"] is True
    row = next(r for r in data["models"] if r["model"] == "gpt-5.4")
    # Existing real values survive an offline refresh untouched.
    assert row["inputPer1M"] == 2.5
    assert row["outputPer1M"] == 15


@pytest.mark.tooling
def test_offline_run_via_subprocess_never_crashes(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "model-pricing.json"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "fetch_model_prices.py"),
            "--offline",
            "--output",
            str(snapshot_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot_path.exists()
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert data["needsRefresh"] is True


@pytest.mark.tooling
def test_wanted_models_covers_policy_and_env_surfaces() -> None:
    models = fmp.wanted_models(existing=[])
    policy = json.loads(
        (REPO_ROOT / "governance" / "policies" / "llm-models.v1.json").read_text(
            encoding="utf-8"
        )
    )
    for role in policy["roles"]:
        assert role["model"] in models, f"policy model {role['model']} missing"

    # The env-driven chat/vision/discovery fallbacks are parsed from source -
    # assert presence WITHOUT asserting a specific model name (the fallback
    # changes over time; the dynamic read is the whole point).
    from backoffice.runtime_models import env_model_defaults

    for env_name, parsed in env_model_defaults().items():
        assert parsed, f"could not parse fallback for {env_name} from source"
        assert parsed in models


@pytest.mark.tooling
def test_committed_snapshot_has_no_invented_prices() -> None:
    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert isinstance(data.get("needsRefresh"), bool)
    assert "models" in data and data["models"]
    for row in data["models"]:
        for field in ("inputPer1M", "outputPer1M"):
            value = row.get(field)
            assert value is None or isinstance(value, (int, float)), (
                f"{row.get('model')}.{field} must be null or a number, got {value!r}"
            )
        # A price requires provenance: fetchedAt + source set together.
        if row.get("inputPer1M") is not None or row.get("outputPer1M") is not None:
            assert row.get("fetchedAt"), f"{row.get('model')} has a price but no fetchedAt"
            assert row.get("source"), f"{row.get('model')} has a price but no source"


@pytest.mark.tooling
def test_runtime_models_parses_all_env_defaults_and_limits() -> None:
    """The dynamic source parse must find every fallback + the chat limits.

    Deliberately does NOT assert which model the fallback is (a parallel PR
    bumps gpt-4o -> gpt-5.5 and future bumps must pass unchanged). The limits
    are pinned: they are stable contract values (15000/8000/40).
    """
    from backoffice import runtime_models

    defaults = runtime_models.env_model_defaults()
    assert set(defaults) == {
        "OPENAI_MODEL",
        "OPENAI_VISION_MODEL",
        "SAJTBYGGAREN_DISCOVERY_MODEL",
    }
    for env_name, value in defaults.items():
        assert isinstance(value, str) and value, f"no fallback parsed for {env_name}"

    limits = runtime_models.chat_limits()
    assert limits["maxOutputTokensDefault"] == 15000
    assert limits["maxInputCharsPerMessage"] == 8000
    assert limits["maxMessagesPerRequest"] == 40


@pytest.mark.tooling
def test_runtime_models_returns_none_on_unparseable_source(tmp_path: Path) -> None:
    from backoffice import runtime_models

    bogus = tmp_path / "openai.ts"
    bogus.write_text("// no model resolution here\n", encoding="utf-8")
    assert runtime_models.chat_model_default(source=bogus) is None
    missing = tmp_path / "does-not-exist.ts"
    assert runtime_models.vision_model_default(source=missing) is None
    limits = runtime_models.chat_limits(source=bogus)
    assert limits == {
        "maxOutputTokensDefault": None,
        "maxInputCharsPerMessage": None,
        "maxMessagesPerRequest": None,
    }


@pytest.mark.tooling
def test_read_non_secret_env_is_whitelisted(monkeypatch: pytest.MonkeyPatch) -> None:
    from backoffice import env_panel

    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    assert env_panel.read_non_secret_env("OPENAI_MODEL") == "gpt-test"

    # Anything outside the whitelist must raise - never leak a value.
    with pytest.raises(ValueError):
        env_panel.read_non_secret_env("OPENAI_API_KEY")
