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


def _parse_route_sections(raw: str | None) -> dict[str, list[str]]:
    """Parse the optional ``--route-sections`` JSON into RouterContext shape.

    ADR 0046: the caller (viewser /api/prompt) forwards the operator's
    preview markings as ``{routeId: [sectionId, ...]}`` — read-only
    prioritisation context the router may use for section resolution.
    Malformed payloads degrade to ``{}`` (never break classification).
    """
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    route_sections: dict[str, list[str]] = {}
    for route_id, section_ids in payload.items():
        if not isinstance(route_id, str) or not isinstance(section_ids, list):
            continue
        cleaned = [item for item in section_ids if isinstance(item, str)]
        if cleaned:
            route_sections[route_id] = cleaned
    return route_sections


def classify_to_json(
    message: str,
    site_id: str | None = None,
    route_sections: dict[str, list[str]] | None = None,
) -> str:
    """Classify ``message`` and return RouterDecision JSON (one line).

    Deferred import keeps the package dependency inside the function (mirrors
    scripts/dev_generate.py) so the module stays import-light and ruff-clean.
    """
    from packages.generation.orchestration.router import (
        RouterContext,
        classify_message,
    )

    context = (
        RouterContext(siteId=site_id, routeSections=route_sections or {})
        if site_id or route_sections
        else None
    )
    decision = classify_message(message, context=context)
    return json.dumps(decision.model_dump(), ensure_ascii=False)


def main() -> int:
    # Deferred import (same philosophy as classify_to_json above) keeps this
    # module import-light; scripts.cli_text only pulls in pathlib.
    from scripts.cli_text import resolve_cli_text

    parser = argparse.ArgumentParser(
        description=(
            "Classify a single user message into a schema-valid RouterDecision "
            "(deterministic KÖR-6a router; no LLM, no build, read-only)."
        )
    )
    parser.add_argument(
        "--message-file",
        default=None,
        help=(
            "Path to a UTF-8 file holding the message. Preferred over the "
            "positional arg so a non-ASCII leading character survives the "
            "viewser→CLI boundary intact (B204). Mutually exclusive with the "
            "positional message."
        ),
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
        "--route-sections",
        default=None,
        help=(
            "Optional JSON object {routeId: [sectionId, ...]} for "
            "RouterContext.routeSections (ADR 0046 preview markings). "
            "Read-only context; malformed payloads are ignored."
        ),
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="The user message to classify. Prefer --message-file (B204) or `--`.",
    )
    args = parser.parse_args()

    # B204: the message arrives via --message-file (a UTF-8 temp file) so a
    # non-ASCII leading character survives the viewser→CLI boundary. The
    # positional arg stays supported for back-compat (tests, `--` callers).
    try:
        message = resolve_cli_text(args.message, args.message_file, label="message")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        classify_to_json(
            message,
            site_id=args.site_id,
            route_sections=_parse_route_sections(args.route_sections),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
