"""Dynamic reading of ENV-driven chat/page model defaults + chat limits.

The Viewser chat (``apps/viewser/lib/openai.ts``), vision classification
(``apps/viewser/lib/asset-store/vision.ts``) and discovery scrape
(``scripts/scrape_site.py``) resolve their models from ENV with a hardcoded
fallback IN THE SOURCE FILE - not from any governance policy. The fallback
model changes over time (gpt-4o -> gpt-5.5 happened 2026-06-11), so nothing
in the backoffice may hardcode it: this module regex-parses the CURRENT
fallback out of the source files at read time. A failed parse returns ``None``
("okänd"), never a guessed model name - the honest alternative to a stale
constant.

Used by the Dirigentpult cockpit (read-only display) and by
``scripts/fetch_model_prices.py`` (to know which models need price rows).
Pure logic, no Streamlit imports.
"""

from __future__ import annotations

import re
from pathlib import Path

from .paths import REPO_ROOT

VIEWSER_OPENAI_TS = REPO_ROOT / "apps" / "viewser" / "lib" / "openai.ts"
VIEWSER_VISION_TS = REPO_ROOT / "apps" / "viewser" / "lib" / "asset-store" / "vision.ts"
SCRAPE_SITE_PY = REPO_ROOT / "scripts" / "scrape_site.py"

# Env var names the three surfaces read. Single source for display labels.
CHAT_MODEL_ENV = "OPENAI_MODEL"
VISION_MODEL_ENV = "OPENAI_VISION_MODEL"
DISCOVERY_MODEL_ENV = "SAJTBYGGAREN_DISCOVERY_MODEL"
CHAT_TOKENS_ENV = "VIEWSER_MAX_CHAT_TOKENS"

# Tolerant patterns: they survive surrounding refactors as long as the
# resolution idiom (env ?? "fallback" / os.environ.get(..., "fallback"))
# stays. The fallback VALUE is intentionally not part of the pattern.
_CHAT_MODEL_RE = re.compile(
    r"openaiEnv\(\s*\"OPENAI_MODEL\"\s*\)\s*\?\?\s*\"([^\"]+)\""
)
_VISION_MODEL_RE = re.compile(
    r"openaiEnv\(\s*\"OPENAI_VISION_MODEL\"\s*\)\s*\?\?\s*\"([^\"]+)\""
)
_DISCOVERY_MODEL_RE = re.compile(
    r"os\.environ\.get\(\s*\"SAJTBYGGAREN_DISCOVERY_MODEL\"\s*,\s*\"([^\"]+)\"\s*\)"
)
_MAX_OUTPUT_TOKENS_RE = re.compile(r"DEFAULT_MAX_OUTPUT_TOKENS\s*=\s*(\d+)")
_MAX_INPUT_CHARS_RE = re.compile(r"MAX_INPUT_CHARS_PER_MESSAGE\s*=\s*(\d+)")
_MAX_MESSAGES_RE = re.compile(r"MAX_MESSAGES_PER_REQUEST\s*=\s*(\d+)")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _first_group(pattern: re.Pattern[str], text: str | None) -> str | None:
    if text is None:
        return None
    match = pattern.search(text)
    return match.group(1) if match else None


def _first_int(pattern: re.Pattern[str], text: str | None) -> int | None:
    raw = _first_group(pattern, text)
    return int(raw) if raw is not None else None


def chat_model_default(*, source: Path = VIEWSER_OPENAI_TS) -> str | None:
    """Viewser-chattens fallback-modell, parsad ur openai.ts. None = okänd."""
    return _first_group(_CHAT_MODEL_RE, _read(source))


def vision_model_default(*, source: Path = VIEWSER_VISION_TS) -> str | None:
    """Vision-klassificeringens fallback-modell, parsad ur vision.ts."""
    return _first_group(_VISION_MODEL_RE, _read(source))


def discovery_model_default(*, source: Path = SCRAPE_SITE_PY) -> str | None:
    """Discovery-scrapens fallback-modell, parsad ur scrape_site.py."""
    return _first_group(_DISCOVERY_MODEL_RE, _read(source))


def chat_limits(*, source: Path = VIEWSER_OPENAI_TS) -> dict[str, int | None]:
    """Viewser-chattens hårda gränser, parsade ur openai.ts.

    Keys: ``maxOutputTokensDefault`` (override via VIEWSER_MAX_CHAT_TOKENS),
    ``maxInputCharsPerMessage`` and ``maxMessagesPerRequest``. ``None`` for a
    limit that could not be located (honest "okänd", never a stale guess).
    """
    text = _read(source)
    return {
        "maxOutputTokensDefault": _first_int(_MAX_OUTPUT_TOKENS_RE, text),
        "maxInputCharsPerMessage": _first_int(_MAX_INPUT_CHARS_RE, text),
        "maxMessagesPerRequest": _first_int(_MAX_MESSAGES_RE, text),
    }


def env_model_defaults() -> dict[str, str | None]:
    """All three ENV-driven model fallbacks, keyed by env var name."""
    return {
        CHAT_MODEL_ENV: chat_model_default(),
        VISION_MODEL_ENV: vision_model_default(),
        DISCOVERY_MODEL_ENV: discovery_model_default(),
    }
