"""Local stdio server for Sprintvakt V1.

This is a dependency-free MCP-compatible JSON-RPC stdio surface. It implements
the local tool names and safety model while avoiding an SDK dependency in V1.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from tooling.sprintvakt_mcp import core

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _wrap_noargs(function: Callable[[], dict[str, Any]]) -> ToolHandler:
    def handler(_arguments: dict[str, Any]) -> dict[str, Any]:
        return function()

    return handler


TOOLS: dict[str, tuple[str, dict[str, Any], ToolHandler]] = {
    "get_workboard": (
        "Read the full Sprintvakt workboard.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _wrap_noargs(core.get_workboard),
    ),
    "list_gaps": (
        "List gaps from the workboard and docs/gaps.",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "queued", "completed", "all"]}
            },
            "additionalProperties": False,
        },
        lambda arguments: core.list_gaps(status=arguments.get("status", "all")),
    ),
    "create_gap": (
        "Create a gap file and workboard entry. dryRun defaults to true; writes require confirm:true.",
        {"type": "object", "additionalProperties": True},
        core.create_gap,
    ),
    "activate_gap": (
        "Move a queued gap to activeGaps. dryRun defaults to true; writes require confirm:true.",
        {
            "type": "object",
            "properties": {
                "gapId": {"type": "string"},
                "dryRun": {"type": "boolean"},
                "confirm": {"type": "boolean"},
            },
            "required": ["gapId"],
            "additionalProperties": False,
        },
        core.activate_gap,
    ),
    "complete_gap": (
        "Move an active or queued gap to completedGaps. dryRun defaults to true; writes require confirm:true.",
        {
            "type": "object",
            "properties": {
                "gapId": {"type": "string"},
                "fixCommits": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "array", "items": {"type": "string"}},
                "dryRun": {"type": "boolean"},
                "confirm": {"type": "boolean"},
            },
            "required": ["gapId"],
            "additionalProperties": False,
        },
        core.complete_gap,
    ),
    "reserve_paths": (
        "Reserve paths for a gap. dryRun defaults to true; writes require confirm:true.",
        {"type": "object", "additionalProperties": True},
        core.reserve_paths,
    ),
    "detect_collisions": (
        "Detect path and lane collisions.",
        {"type": "object", "additionalProperties": True},
        core.detect_collisions,
    ),
    "suggest_next_gaps": (
        "Suggest up to three deterministic next gaps.",
        {"type": "object", "additionalProperties": True},
        core.suggest_next_gaps,
    ),
    "generate_agent_prompt": (
        "Generate a scoped Cursor/Cloud-agent prompt for a gap.",
        {"type": "object", "additionalProperties": True},
        core.generate_agent_prompt,
    ),
    "validate_workboard": (
        "Validate workboard fields, lane boundaries and path collisions.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _wrap_noargs(core.validate_workboard),
    ),
    "post_merge_sync_instructions": (
        "Return exact post-merge branch sync commands for working branches.",
        {"type": "object", "additionalProperties": True},
        core.post_merge_sync_instructions,
    ),
}


def tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }
        for name, (description, input_schema, _handler) in TOOLS.items()
    ]


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "sprintvakt-mcp", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            result = {"tools": tool_specs()}
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            if tool_name not in TOOLS:
                raise core.SprintvaktError(f"Unknown tool: {tool_name}")
            if not isinstance(arguments, dict):
                raise core.SprintvaktError("Tool arguments must be an object.")
            tool_result = TOOLS[tool_name][2](arguments)
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_result, ensure_ascii=False, indent=2, sort_keys=True),
                    }
                ],
                "structuredContent": tool_result,
                "isError": False,
            }
        else:
            return _error_response(request_id, -32601, f"Method not found: {method}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:  # noqa: BLE001 - JSON-RPC server must report tool errors.
        return _error_response(request_id, -32000, str(exc))


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as exc:
            response = _error_response(None, -32700, f"Parse error: {exc}")
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
