"""Regressionslås för buggsvep 2026-06-10 (B163, B168, B170, B171).

Source-locks i samma stil som test_viewser_floating_chat.py: de låser de
exakta kodmönster som stänger respektive bugg, så en framtida refaktor
inte tyst kan återinföra dem.

- B163: OpenClaw-applyns early-return i /api/prompt måste stoppa den
  lokala preview-servern (legacy-vägen gör det via runBuild ->
  stopAndWaitPreviewServer; utan stoppet återanvänder startPreviewServer
  en levande ``next start`` mot GAMLA build-katalogen och iframen visar
  fel version efter en lyckad apply).
- B168: /api/generate-image måste läsa OpenAI-env via openaiEnv
  (process.env -> repo-rotens .env) precis som chatten — inte bara
  process.env, som gav "nyckel saknas" i single-source-setupen.
- B170: Token Meter-priserna (USD per 1K) måste gå via openaiEnv så de
  inte fastnar på $0 när priserna bara står i rotens .env.
- B171: OpenAI-klient-cacherna (lib/openai.ts + asset-store/vision.ts)
  måste återskapa klienten när nyckeln byts, annars 401 efter nyckelbyte
  tills next dev startas om.
"""

from __future__ import annotations

import pytest

from tests.support.viewser import VIEWSER_DIR


def _read(relative: str) -> str:
    return (VIEWSER_DIR / relative).read_text(encoding="utf-8")


@pytest.mark.tooling
def test_b163_openclaw_apply_early_return_stops_local_preview() -> None:
    """B163: apply-vägen måste stoppa previewn innan den re-surfar chain-runet."""
    text = _read("app/api/prompt/route.ts")
    assert (
        'import { stopAndWaitPreviewServer } from "@/lib/local-preview-server"'
        in text
    ), (
        "route.ts måste importera stopAndWaitPreviewServer — OpenClaw-applyns "
        "early-return ska stoppa den lokala previewn (B163)."
    )
    call_idx = text.find("await stopAndWaitPreviewServer(payload.siteId)")
    assert call_idx != -1, (
        "OpenClaw-apply-vägen i route.ts måste anropa "
        "stopAndWaitPreviewServer(payload.siteId) — annars återanvänder "
        "startPreviewServer en levande next start mot den GAMLA build-"
        "katalogen och iframen visar föregående version (B163)."
    )
    # Stoppet måste ligga INNE i chainRunId-blocket (efter att kedjan
    # bevisat en ny version) och FÖRE early-return:ens "return {".
    chain_idx = text.find("if (chainRunId) {")
    assert chain_idx != -1, "route.ts saknar chainRunId-early-return-blocket."
    return_idx = text.find("return {", chain_idx)
    assert chain_idx < call_idx < return_idx, (
        "stopAndWaitPreviewServer-anropet måste ske inne i chainRunId-"
        "blocket, före early-return:en — inte någon annanstans i filen."
    )


@pytest.mark.tooling
def test_b168_generate_image_uses_openai_env_fallback() -> None:
    """B168: generate-image måste dela chattens env-upplösning (rot-.env-fallback)."""
    text = _read("app/api/generate-image/route.ts")
    assert 'import { openaiEnv } from "@/lib/openai"' in text, (
        "generate-image/route.ts måste importera openaiEnv från @/lib/openai "
        "så bild-API:t delar chattens env-upplösning (B168)."
    )
    assert 'openaiEnv("OPENAI_API_KEY")' in text, (
        "generate-image måste läsa nyckeln via openaiEnv(\"OPENAI_API_KEY\") "
        "— inte bare process.env (B168)."
    )
    assert "process.env.OPENAI_API_KEY" not in text, (
        "generate-image får inte läsa process.env.OPENAI_API_KEY direkt — "
        "det missar repo-rotens .env (B168)."
    )
    assert 'openaiEnv("OPENAI_IMAGE_MODEL")' in text, (
        "OPENAI_IMAGE_MODEL ska också gå via openaiEnv (B168)."
    )


@pytest.mark.tooling
def test_b170_token_meter_prices_use_openai_env() -> None:
    """B170: USD-priserna måste falla tillbaka på repo-rotens .env."""
    text = _read("lib/openai.ts")
    assert "export function openaiEnv" in text, (
        "lib/openai.ts måste exportera openaiEnv så andra routes (generate-"
        "image) kan dela env-upplösningen (B168/B170)."
    )
    assert 'Number(openaiEnv("OPENAI_INPUT_USD_PER_1K") ?? "0")' in text, (
        "INPUT_USD_PER_1K måste läsas via openaiEnv — bare process.env ger "
        "$0 i Token Meter när priset bara står i rotens .env (B170)."
    )
    assert 'Number(openaiEnv("OPENAI_OUTPUT_USD_PER_1K") ?? "0")' in text, (
        "OUTPUT_USD_PER_1K måste läsas via openaiEnv (B170)."
    )


@pytest.mark.tooling
def test_b171_openai_clients_recreated_on_key_change() -> None:
    """B171: cachade OpenAI-klienter måste jämföra nyckeln, inte bara finnas."""
    chat = _read("lib/openai.ts")
    assert "openaiClientKey !== apiKey" in chat, (
        "lib/openai.ts:getClient måste återskapa klienten när nyckeln byts "
        "(jämför cachad nyckel) — annars 401 efter nyckelbyte tills next dev "
        "startas om (B171)."
    )
    vision = _read("lib/asset-store/vision.ts")
    assert "visionClientKey !== apiKey" in vision, (
        "vision.ts:getClient måste återskapa klienten när nyckeln byts (B171)."
    )
