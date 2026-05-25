#!/usr/bin/env python3
"""Validate Sprintvakt workboard and path collisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tooling.sprintvakt_mcp.core import SprintvaktError, validate_workboard

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workboard",
        type=Path,
        default=REPO_ROOT / "docs" / "workboard.json",
        help="Path to docs/workboard.json.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_workboard(workboard_path=args.workboard)
    except SprintvaktError as exc:
        result = {
            "ok": False,
            "errors": [str(exc)],
            "warnings": [],
            "collisions": [],
        }

    if args.strict and result["warnings"]:
        result = {
            **result,
            "ok": False,
            "errors": [*result["errors"], *[f"strict warning: {item}" for item in result["warnings"]]],
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(result)

    return 0 if result["ok"] else 1


def _print_human(result: dict[str, object]) -> None:
    if result["ok"]:
        print("Sprintvakt check: OK")
    else:
        print("Sprintvakt check: BLOCKED")

    errors = list(result.get("errors", []))
    warnings = list(result.get("warnings", []))
    collisions = list(result.get("collisions", []))

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error}")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    if collisions:
        print("\nCollisions:")
        for collision in collisions:
            print(f"- {collision}")


if __name__ == "__main__":
    raise SystemExit(main())
