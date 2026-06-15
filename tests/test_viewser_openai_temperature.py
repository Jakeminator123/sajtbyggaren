"""Regressionslås: skicka aldrig `temperature` till reasoning-modeller (gpt-5.x).

Roten (2026-06-15): lib/openai.ts + lib/asset-store/vision.ts skickade ett
explicit `temperature`-värde på varje anrop. Det funkade med gpt-4o, men efter
modell-lyftet till gpt-5.5 (en reasoning-modell) avvisar OpenAI det med
HTTP 400 "Unsupported value: 'temperature' does not support 0.3 with this model.
Only the default (1) value is supported." -> varje chat-/vision-anrop kastade
och floating-chat/answer-only/bekräftelser gav "chat-anropet misslyckades".

OpenAI grupperar dessa som "gpt-5 and o-series models only" (reasoning), exakt
detektorn /^(gpt-5|o\\d)/ som koden använder. Source-lock i samma stil som
test_bug_sweep_b163_b171.py: temperature får BARA skickas till icke-reasoning-
modeller, så nästa modellbump inte tyst återinför regressionen.
"""

from __future__ import annotations

import pytest

from tests.support.viewser import VIEWSER_DIR

pytestmark = pytest.mark.source_lock

# Samma reasoning-detektor i båda TS-filerna (gpt-5.x + o-serien).
REASONING_DETECTOR = r"/^(gpt-5|o\d)/"


def _read(relative: str) -> str:
    return (VIEWSER_DIR / relative).read_text(encoding="utf-8")


@pytest.mark.tooling
def test_chat_helper_gates_temperature_behind_reasoning_check() -> None:
    text = _read("lib/openai.ts")
    assert REASONING_DETECTOR in text, (
        "lib/openai.ts måste detektera reasoning-modeller med "
        f"{REASONING_DETECTOR} (gpt-5.x/o-serien)."
    )
    assert "DEFAULT_MODEL_IS_REASONING" in text, (
        "lib/openai.ts måste härleda DEFAULT_MODEL_IS_REASONING ur DEFAULT_MODEL."
    )
    assert "DEFAULT_MODEL_IS_REASONING ? {} : { temperature: 0.3 }" in text, (
        "chatWithOpenAi måste GATA temperature bakom reasoning-checken — "
        "reasoning-modeller (gpt-5.x) avvisar temperature !== 1 med 400."
    )
    assert "temperature: 0.3," not in text, (
        "lib/openai.ts får inte skicka temperature ovillkorligt (det kastar mot "
        "gpt-5.x). Gata det bakom DEFAULT_MODEL_IS_REASONING."
    )


@pytest.mark.tooling
def test_vision_helper_gates_temperature_behind_reasoning_check() -> None:
    text = _read("lib/asset-store/vision.ts")
    assert REASONING_DETECTOR in text, (
        "lib/asset-store/vision.ts måste detektera reasoning-modeller med "
        f"{REASONING_DETECTOR}."
    )
    assert "VISION_MODEL_IS_REASONING ? {} : { temperature: 0.2 }" in text, (
        "vision-anropet måste GATA temperature bakom VISION_MODEL_IS_REASONING — "
        "gpt-5.x avvisar temperature !== 1 med 400."
    )
    assert "temperature: 0.2," not in text, (
        "vision.ts får inte skicka temperature ovillkorligt mot gpt-5.x."
    )
