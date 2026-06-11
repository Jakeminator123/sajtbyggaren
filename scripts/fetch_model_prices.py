"""Hämta aktuella tokenpriser per modell till data/model-pricing.json.

Snapshotten (USD per 1M input-/output-tokens) läses READ-ONLY av
Dirigentpult-grupp G i backoffice. Källa i första hand: OpenAI:s officiella
docs-MCP på https://developers.openai.com/mcp (samma server som agenternas
``openai-docs``-uppslagsverk, se docs/openclaw-workspace/README.md). Skriptet
pratar MCP-over-HTTP själv (JSON-RPC via urllib, SSE-svar) så ingen lokal
MCP-klient behövs - fungerar både lokalt och på Cloud-VM så länge nätet når
endpointen.

Ärlig fallback: utan nät/MCP (eller om prissidan inte kan parsas) kraschar
skriptet ALDRIG - den befintliga snapshotten behålls, ``needsRefresh`` sätts
till true och exit-koden är 0. Prisfält uppdateras bara med siffror som
faktiskt hittats på prissidan; allt annat förblir null. Inga påhittade priser.

Modellistan härleds dynamiskt (inga hårdkodade modell-defaults):
  - distinkta ``model``-strängar ur governance/policies/llm-models.v1.json,
  - de ENV-styrda chatt-/vision-/discovery-modellerna: env-värdet om satt,
    annars fallbacken parsad ur källfilerna (backoffice/runtime_models.py),
  - extra kända modeller (gpt-5.5),
  - modeller som redan finns i snapshotten behålls.

Körs från repo-roten:

    python scripts/fetch_model_prices.py             # riktig hämtning
    python scripts/fetch_model_prices.py --offline   # bara fallback-vägen
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_OUTPUT = REPO_ROOT / "data" / "model-pricing.json"
LLM_MODELS_POLICY = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

MCP_ENDPOINT = "https://developers.openai.com/mcp"
PRICING_DOC_URL = "https://developers.openai.com/api/docs/pricing"
USER_AGENT = "sajtbyggaren-fetch-model-prices/1.0"

# Extra modeller som alltid ska ha en rad i snapshotten även när de (ännu)
# inte refereras av policy/env - operatören jämför mot dem i Dirigentpulten.
EXTRA_KNOWN_MODELS = ("gpt-5.5",)

# Prissidan bäddar in rader som JS-arrayer:
#   ["gpt-5.4 (<272K context length)", 2.5, 0.25, 15]
#   ["text-embedding-3-small", 0.02, "-", "-"]
# = [label, inputPer1M, cachedInputPer1M, outputPer1M] i USD. Värden kan vara
# tal, "-", "", null eller "Free".
_PRICE_ROW_RE = re.compile(
    r"\[\s*\"(?P<label>[^\"]+)\"\s*,\s*"
    r"(?P<input>-?[0-9.]+|\"[^\"]*\"|null)\s*,\s*"
    r"(?P<cached>-?[0-9.]+|\"[^\"]*\"|null)\s*,\s*"
    r"(?P<output>-?[0-9.]+|\"[^\"]*\"|null)\s*\]"
)

# Suffix i parentes ("(<272K context length)") strippas innan labeln jämförs
# EXAKT mot modell-id - prefix-match skulle blanda ihop gpt-5.5 / gpt-5.5-pro.
_LABEL_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ----- modellista ------------------------------------------------------------


def policy_models() -> list[str]:
    """Distinkta model-strängar ur llm-models.v1.json roles (ordningen bevaras)."""
    try:
        policy = json.loads(LLM_MODELS_POLICY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"varning: kunde inte läsa {LLM_MODELS_POLICY.name}: {exc}")
        return []
    seen: list[str] = []
    for role in policy.get("roles", []) or []:
        model = role.get("model")
        if isinstance(model, str) and model and model not in seen:
            seen.append(model)
    return seen


def env_driven_models() -> list[str]:
    """Chatt-/vision-/discovery-modellerna: env om satt, annars källkods-fallback.

    Härleds dynamiskt via backoffice.runtime_models (parsar fallbacken ur
    källfilerna) - inga hårdkodade modellnamn, så ett framtida fallback-byte
    plockas upp automatiskt. En modell som inte kan härledas hoppas över
    (ärligt) i stället för att gissas.
    """
    import os

    from backoffice.runtime_models import env_model_defaults

    models: list[str] = []
    for env_name, parsed_default in env_model_defaults().items():
        value = (os.environ.get(env_name) or "").strip() or parsed_default
        if value and value not in models:
            models.append(value)
    return models


def wanted_models(existing: list[dict]) -> list[str]:
    """Union: policy-modeller + env-modeller + extra kända + befintliga rader."""
    ordered: list[str] = []
    for model in (
        policy_models()
        + env_driven_models()
        + list(EXTRA_KNOWN_MODELS)
        + [m.get("model") for m in existing if isinstance(m.get("model"), str)]
    ):
        if model and model not in ordered:
            ordered.append(model)
    return ordered


# ----- MCP-over-HTTP ---------------------------------------------------------


def _mcp_post(payload: dict, *, timeout: float) -> dict:
    """POST:a en JSON-RPC-request till MCP-endpointen och packa upp SSE-svaret."""
    request = Request(
        MCP_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    # Streamable HTTP: svaret är antingen ren JSON eller SSE-rader (`data: {...}`).
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    return json.loads(body)


def fetch_pricing_markdown(*, timeout: float) -> str:
    """Hämta prissidans markdown via MCP-verktyget fetch_openai_doc."""
    # Tolerant handshake - servern är stateless för tools/call, men ett
    # misslyckat initialize ska inte stoppa försöket.
    try:
        _mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": USER_AGENT, "version": "1.0"},
                },
            },
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - handshake är best-effort
        print(f"info: MCP initialize misslyckades ({exc}); provar tools/call ändå.")

    result = _mcp_post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "fetch_openai_doc",
                "arguments": {"url": PRICING_DOC_URL},
            },
        },
        timeout=timeout,
    )
    if "error" in result:
        raise RuntimeError(f"MCP-fel: {result['error']}")
    content = result.get("result", {}).get("content", [])
    texts = [c.get("text", "") for c in content if isinstance(c, dict)]
    markdown = "\n".join(t for t in texts if t)
    if not markdown.strip():
        raise RuntimeError("MCP-svaret innehöll ingen text för prissidan.")
    return markdown


# ----- parsning --------------------------------------------------------------


def _to_price(raw: str) -> float | None:
    """Tolka ett pris-cellvärde: tal -> float, '-'/''/null/'Free' -> None."""
    raw = raw.strip()
    if raw in {"null", ""}:
        return None
    if raw.startswith('"') and raw.endswith('"'):
        inner = raw[1:-1].strip()
        try:
            return float(inner)
        except ValueError:
            return None  # "-", "Free", ...
    try:
        return float(raw)
    except ValueError:
        return None


def parse_prices(markdown: str, models: list[str]) -> dict[str, dict[str, float | None]]:
    """Plocka {model: {inputPer1M, outputPer1M}} ur prissidans text.

    Labeln matchas EXAKT mot modell-id efter att parentes-suffix strippats.
    FÖRSTA förekomsten per modell vinner (standard-prispanen kommer före
    batch-panen i dokumentet). Modeller utan träff utelämnas - aldrig en
    gissad siffra.
    """
    found: dict[str, dict[str, float | None]] = {}
    targets = set(models)
    for match in _PRICE_ROW_RE.finditer(markdown):
        label = _LABEL_PAREN_RE.sub("", match.group("label")).strip()
        if label not in targets or label in found:
            continue
        found[label] = {
            "inputPer1M": _to_price(match.group("input")),
            "outputPer1M": _to_price(match.group("output")),
        }
    return found


# ----- snapshot --------------------------------------------------------------


def load_snapshot(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f"varning: kunde inte läsa befintlig snapshot ({exc}); börjar om.")
    return {
        "version": 1,
        "purpose": (
            "Read-only pris-snapshot (USD per 1M tokens) for Dirigentpult "
            "grupp G i backoffice. Skrivs av scripts/fetch_model_prices.py - "
            "redigera aldrig for hand."
        ),
        "needsRefresh": True,
        "lastFetched": None,
        "source": "placeholder",
        "models": [],
    }


def write_snapshot(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def refresh_snapshot(
    snapshot: dict,
    models: list[str],
    prices: dict[str, dict[str, float | None]] | None,
) -> dict:
    """Bygg nästa snapshot: befintliga rader behålls, träffar uppdateras.

    ``prices=None`` = hämtningen misslyckades helt -> behåll allt men flagga
    ``needsRefresh``. Annars uppdateras matchade modeller med fetchedAt +
    källa; ``needsRefresh`` blir true om NÅGON modell saknar inputPer1M.
    """
    existing_by_model = {
        row.get("model"): row
        for row in snapshot.get("models", [])
        if isinstance(row, dict)
    }
    now = utcnow_iso()
    rows: list[dict] = []
    for model in models:
        row = dict(
            existing_by_model.get(model)
            or {
                "model": model,
                "inputPer1M": None,
                "outputPer1M": None,
                "source": None,
                "fetchedAt": None,
            }
        )
        if prices is not None and model in prices:
            row["inputPer1M"] = prices[model]["inputPer1M"]
            row["outputPer1M"] = prices[model]["outputPer1M"]
            row["source"] = PRICING_DOC_URL
            row["fetchedAt"] = now
        rows.append(row)

    snapshot = dict(snapshot)
    snapshot["models"] = rows
    if prices is None:
        snapshot["needsRefresh"] = True
    else:
        snapshot["lastFetched"] = now
        snapshot["source"] = PRICING_DOC_URL
        snapshot["needsRefresh"] = any(row.get("inputPer1M") is None for row in rows)
    return snapshot


# ----- main ------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Hoppa över nät/MCP - skriv bara fallback-snapshot (needsRefresh=true).",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Nät-timeout i sekunder.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Snapshot-fil (default: data/model-pricing.json).",
    )
    args = parser.parse_args(argv)

    snapshot = load_snapshot(args.output)
    models = wanted_models(snapshot.get("models", []))
    print(f"Modeller i snapshotten: {', '.join(models)}")

    prices: dict[str, dict[str, float | None]] | None = None
    if args.offline:
        print("Offline-läge: hoppar över hämtning, flaggar needsRefresh=true.")
    else:
        try:
            markdown = fetch_pricing_markdown(timeout=args.timeout)
            prices = parse_prices(markdown, models)
            if not prices:
                print(
                    "varning: prissidan hämtades men inga modellrader matchade - "
                    "behåller befintliga värden och flaggar needsRefresh=true."
                )
                prices = None
        except Exception as exc:  # noqa: BLE001 - fallback får aldrig krascha
            print(
                f"varning: live-hämtning misslyckades ({type(exc).__name__}: {exc}) - "
                "behåller befintlig snapshot och flaggar needsRefresh=true. "
                "Kör igen med nät/MCP-åtkomst för riktiga priser."
            )

    snapshot = refresh_snapshot(snapshot, models, prices)
    write_snapshot(args.output, snapshot)

    if prices is None:
        print(f"Snapshot skriven till {args.output} (needsRefresh=true, inga nya priser).")
    else:
        priced = sum(1 for r in snapshot["models"] if r.get("inputPer1M") is not None)
        print(
            f"Snapshot skriven till {args.output}: {priced}/{len(snapshot['models'])} "
            f"modeller fick pris från {PRICING_DOC_URL} "
            f"(needsRefresh={str(snapshot['needsRefresh']).lower()})."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
