"""Minimal MCP (Model Context Protocol) server exposing READ-ONLY status tools.

Hand-rolled stdio JSON-RPC 2.0 with zero new dependencies, consistent with
this project's supply-chain rules. Targets MCP protocol version 2024-11-05;
implements only the subset needed for tool serving (initialize, tools/list,
tools/call, ping). Verify against the current MCP specification before
extending: https://modelcontextprotocol.io

Security posture: every exposed tool is read-only by construction. The server
never imports a mutating function (project/enroll/promote/force are not
reachable), so an MCP client - or a prompt-injected AI driving one - cannot
mutate source or runtime state through this surface. Output is the same fixed
deterministic phrasing as the CLI.
"""

import json
import sys
from dataclasses import asdict

from .check import check
from .config import Config
from .sense import scan
from .status import status

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "sense",
        "description": "Read-only findings report: what changed across the "
        "managed AI runtimes and which command resolves it. Ask the operator "
        "before running any resolution command.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "check",
        "description": "Read-only pass/fail sync check: lists stale runtimes, "
        "empty when everything matches the source.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "status",
        "description": "Read-only per-target sync state for every managed "
        "instruction file and skill.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def _call_tool(config: Config, name: str) -> str:
    if name == "sense":
        findings = scan(config)
        return json.dumps(
            {"count": len(findings), "findings": [asdict(f) for f in findings]},
            indent=2,
        )
    if name == "check":
        return json.dumps({"stale": check(config)}, indent=2)
    if name == "status":
        return json.dumps(status(config), indent=2)
    raise ValueError(f"unknown tool '{name}'")


def handle_request(config: Config, req: dict) -> dict | None:
    """Handle one JSON-RPC request. Returns a response dict, or None for
    notifications (no id). Errors follow JSON-RPC 2.0 error objects."""
    method = req.get("method", "")
    req_id = req.get("id")
    if req_id is None:
        return None  # notification (e.g. notifications/initialized)

    def ok(result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agent-config-sync", "version": "2.0"},
            }
        )
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name", "")
        if name not in {t["name"] for t in TOOLS}:
            return err(-32602, f"unknown tool '{name}'")
        try:
            text = _call_tool(config, name)
        except Exception as exc:  # noqa: BLE001 - report, never crash the server
            return ok({"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
        return ok({"content": [{"type": "text", "text": text}]})
    return err(-32601, f"method '{method}' not supported (read-only status server)")


def serve(config: Config) -> int:
    """Blocking stdio loop: one JSON-RPC message per line."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": "parse error"}}), flush=True)
            continue
        resp = handle_request(config, req)
        if resp is not None:
            print(json.dumps(resp), flush=True)
    return 0
