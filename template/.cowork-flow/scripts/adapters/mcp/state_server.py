#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only MCP stdio server exposing the cowork-flow fact layer.

Stage 3 of docs/direction.md: any MCP client can query task facts without
pulling the workflow into a prompt. Deliberately dependency-free — the MCP
stdio transport is newline-delimited JSON-RPC 2.0, small enough to serve on
the standard library while the ecosystem settles (see
spec/contracts/fact-layer-access.md).

Read-only guarantee: both tools only read repository state (fact view and
the active task tree); there is no write path here. Writes keep flowing
through the CLI lifecycle gates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401

from infra.paths import get_repo_root

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "cowork-flow-facts", "version": "1.0.0"}

TOOLS = [
    {
        "name": "task_state",
        "description": (
            "Fact view for one task: task.json (with revision), decision-anchor "
            "essentials (goal, acceptance criteria, rejected options), plan "
            "binding, bound sessions, and the trusted state snapshot. Omit "
            "`task` to use the caller's session-bound active task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task directory or name.",
                },
            },
        },
    },
    {
        "name": "task_list",
        "description": (
            "Active tasks overview: name, path, status, assignee, parent/child "
            "links, and which one the current session has bound."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "task_specs",
        "description": (
            "Spec files the implementing agent should read for a task, "
            "dispatched by its dev_type (base guides + domain skills + "
            "backend/frontend/spec pointers). Read them before coding."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task directory or name.",
                },
            },
        },
    },
    {
        "name": "task_scope",
        "description": (
            "Edit-scope verdict for a task. Without `path`: the file-scope "
            "whitelist summary (only file/planned-file/deleted-file entries "
            "authorize edits; directories authorize nothing). With `path`: "
            "an inScope verdict for that one file. Edits outside the scope "
            "are review blockers."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task directory or name.",
                },
                "path": {
                    "type": "string",
                    "description": "Repo-relative file path to check.",
                },
            },
        },
    },
]


def _tool_task_state(root: Path, arguments: dict) -> dict:
    from runtime.session_state import get_active_task
    from services.fact_view import build_fact_view
    from services.task_repository import TaskRepository, TaskRepositoryError

    target = arguments.get("task")
    if not target:
        target = get_active_task(root).task_path
        if not target:
            return {"schemaVersion": 1, "task": None, "reason": "no-active-task"}
    try:
        task_dir = TaskRepository(root).resolve(target)
    except TaskRepositoryError as error:
        raise ValueError(str(error)) from error
    if not (Path(task_dir) / "task.json").is_file():
        raise ValueError(f"task.json not found under {task_dir}")
    return build_fact_view(root, Path(task_dir))


def _tool_task_list(root: Path, _arguments: dict) -> dict:
    from adapters.cli.task_tree_commands import _list_task_records

    records, error = _list_task_records(root, mine=False, status=None)
    if error:
        return {"tasks": [], "count": 0, "error": error}
    return {"tasks": records, "count": len(records)}


def _resolve_task_dir(root: Path, target: str | None) -> Path:
    from runtime.session_state import get_active_task
    from services.task_repository import TaskRepository, TaskRepositoryError

    if not target:
        target = get_active_task(root).task_path
        if not target:
            raise ValueError("no-active-task")
    try:
        task_dir = TaskRepository(root).resolve(target)
    except TaskRepositoryError as error:
        raise ValueError(str(error)) from error
    if not (Path(task_dir) / "task.json").is_file():
        raise ValueError(f"task.json not found under {task_dir}")
    return Path(task_dir)


def _tool_task_scope(root: Path, arguments: dict) -> dict:
    from services.fact_view import file_scope_whitelist, path_in_scope

    task_dir = _resolve_task_dir(root, arguments.get("task"))
    whitelist = file_scope_whitelist(root, task_dir)
    candidate = arguments.get("path")
    if candidate:
        verdict = path_in_scope(whitelist, str(candidate))
        return {"taskDir": task_dir.name, **verdict}
    return {
        "taskDir": task_dir.name,
        "whitelist": whitelist,
        "count": len(whitelist),
    }


def _tool_task_specs(root: Path, arguments: dict) -> dict:
    from services.context_discovery import implement_spec_entries
    from services.fact_view import _read_json

    task_dir = _resolve_task_dir(root, arguments.get("task"))
    task = _read_json(task_dir / "task.json")
    dev_type = task.get("dev_type") if isinstance(task, dict) else None
    specs = implement_spec_entries(root, dev_type)
    return {
        "taskDir": task_dir.name,
        "devType": dev_type,
        "specs": specs,
        "count": len(specs),
    }


TOOL_HANDLERS = {
    "task_state": _tool_task_state,
    "task_list": _tool_task_list,
    "task_scope": _tool_task_scope,
    "task_specs": _tool_task_specs,
}


def handle_request(root: Path, request: dict) -> dict | None:
    """Dispatch one decoded JSON-RPC message. Notifications (no id) yield
    None and are never answered."""
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        requested = (request.get("params") or {}).get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": requested or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"unknown tool: {name}"}
                    ],
                    "isError": True,
                },
            }
        try:
            payload = handler(root, params.get("arguments") or {})
        except Exception as error:  # tool errors ride the result, not the frame
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"{type(error).__name__}: {error}",
                        }
                    ],
                    "isError": True,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            payload, ensure_ascii=False, indent=2
                        ),
                    }
                ]
            },
        }
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> int:
    root = get_repo_root()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as error:
            sys.stdout.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": str(error)},
                    }
                )
                + "\n"
            )
            sys.stdout.flush()
            continue
        if not isinstance(request, dict):
            continue
        response = handle_request(root, request)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())