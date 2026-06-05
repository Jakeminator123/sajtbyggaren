"""Deterministic router classification CLI (KÖR-6a bridge for /api/prompt).

Thin, read-only wrapper around
``packages.generation.orchestration.router.classify_message`` so the Viewser
operator UI can surface the router's *opinion* about a single message as a
schema-valid ``RouterDecision`` JSON object — WITHOUT importing ``packages/``
directly. apps/viewser shells out to ``scripts/`` for anything that touches the
generation packages (repo-boundaries.v1.json), exactly the same way
``scripts/prompt_to_project_input.py`` and ``scripts/build_site.py`` do.

Guarantees of this script:
    - DETERMINISTIC ONLY. Uses ``classify_message`` (KÖR-6a heuristics), never
      ``classify_message_with_llm_fallback``. No model role, no OpenAI call, no
      per-prompt cost.
    - READ-ONLY. Prints JSON to stdout; never touches disk, never starts a
      build or preview.
    - SCHEMA-STABLE. The emitted object is ``RouterDecision.model_dump()``,
      which tests/test_router_schema.py locks against
      governance/schemas/router-decision.schema.json.

Usage:
    python scripts/classify_message.py -- "vad är klockan?"
    python scripts/classify_message.py --site-id painter-palma -- "byt rubriken till X"

Conventions:
    - Code comments and identifiers in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Make packages/ importable when running this script directly.
sys.path.insert(0, str(REPO_ROOT))


def classify_to_json(message: str, site_id: str | None = None) -> str:
    """Classify ``message`` and return RouterDecision JSON (one line).

    Deferred import keeps the package dependency inside the function (mirrors
    scripts/dev_generate.py) so the module stays import-light and ruff-clean.
    """
    from packages.generation.orchestration.router import (
        RouterContext,
        classify_message,
    )

    context = RouterContext(siteId=site_id) if site_id else None
    decision = classify_message(message, context=context)
    return json.dumps(decision.model_dump(), ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify a single user message into a schema-valid RouterDecision "
            "(deterministic KÖR-6a router; no LLM, no build, read-only)."
        )
    )
    parser.add_argument(
        "--site-id",
        default=None,
        help=(
            "Optional siteId for RouterContext. Metadata only — the router never "
            "reads it from disk."
        ),
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="The user message to classify. Prefer passing after `--`.",
    )
    args = parser.parse_args()

    if args.message is None:
        print("classify_message.py requires a message argument.", file=sys.stderr)
        return 1

    print(classify_to_json(args.message, site_id=args.site_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
