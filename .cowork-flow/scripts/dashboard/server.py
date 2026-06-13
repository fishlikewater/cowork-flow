#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Flow dashboard server."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import TASK_DATE_PREFIX_PATTERN, get_db_path, get_repo_root
from flow.store import FlowStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
PATTERNS = [
    {"name": "generic", "label": "Generic", "description": "Linear task lifecycle"},
    {"name": "fan_out", "label": "Fan-out", "description": "Parent task with child progress"},
    {"name": "pipeline", "label": "Pipeline", "description": "Staged task execution"},
    {"name": "human_loop", "label": "Human-loop", "description": "Human decision pause/resume"},
]


def _task_to_dict(task) -> dict:
    return {
        "id": task.id,
        "artifact_dir": task.artifact_dir,
        "title": task.title,
        "status": task.status,
        "pattern": task.pattern,
        "priority": task.priority,
        "assignee": task.assignee,
        "parent_id": task.parent_id,
        "children": list(task.children),
        "meta": task.meta,
    }


def _resolve_task(store: FlowStore, target: str):
    candidates: list[str] = []
    raw = target.strip()
    if raw:
        candidates.append(raw)
    name = Path(raw).name if raw else ""
    if name and name not in candidates:
        candidates.append(name)
    if name and TASK_DATE_PREFIX_PATTERN.match(name):
        stripped = TASK_DATE_PREFIX_PATTERN.sub("", name)
        if stripped not in candidates:
            candidates.append(stripped)

    for candidate in candidates:
        task = store.get_task(candidate)
        if task:
            return task
        task = store.get_task_by_artifact_dir(candidate)
        if task:
            return task
    return None


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def make_handler(repo_root: Path):
    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "cowork-flow-dashboard/1"

        def log_message(self, format: str, *args) -> None:
            return

        def _send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: int, message: str) -> None:
            self._send_json({"error": message}, status)

        def _send_static(self, path: Path) -> None:
            if not path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)

            if path == "/":
                self._send_static(STATIC_DIR / "index.html")
                return
            if path.startswith("/static/"):
                relative = path.removeprefix("/static/")
                candidate = (STATIC_DIR / relative).resolve()
                try:
                    candidate.relative_to(STATIC_DIR.resolve())
                except ValueError:
                    self._send_error(HTTPStatus.NOT_FOUND, "not found")
                    return
                self._send_static(candidate)
                return

            if path == "/api/board":
                with FlowStore(str(get_db_path(repo_root))) as store:
                    self._send_json(store.board_view())
                return
            if path == "/api/patterns":
                self._send_json({"patterns": PATTERNS})
                return
            if path.startswith("/api/task/") and path.endswith("/children"):
                task_id = path.removeprefix("/api/task/").removesuffix("/children").strip("/")
                with FlowStore(str(get_db_path(repo_root))) as store:
                    task = _resolve_task(store, task_id)
                    if task is None:
                        self._send_error(HTTPStatus.NOT_FOUND, "task not found")
                        return
                    children = [_task_to_dict(child) for child in store.list_children(task.id)]
                self._send_json({"task_id": task.id, "children": children})
                return
            if path.startswith("/api/task/"):
                task_id = path.removeprefix("/api/task/").strip("/")
                with FlowStore(str(get_db_path(repo_root))) as store:
                    task = _resolve_task(store, task_id)
                    if task is None:
                        self._send_error(HTTPStatus.NOT_FOUND, "task not found")
                        return
                    payload = {
                        "task": _task_to_dict(task),
                        "children": [_task_to_dict(child) for child in store.list_children(task.id)],
                        "audit": store.get_audit_trail(task.id),
                        "activeBlock": store.get_active_block(task.id),
                        "agentRuns": store.list_agent_runs_for_task(task.id),
                    }
                self._send_json(payload)
                return

            self._send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self) -> None:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "dashboard is read-only")

        def do_PUT(self) -> None:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "dashboard is read-only")

        def do_DELETE(self) -> None:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "dashboard is read-only")

    return DashboardHandler


def _bind_server(host: str, port: int, handler) -> ThreadingHTTPServer:
    candidates = [0] if port == 0 else list(range(port, port + 10))
    last_error: OSError | None = None
    for candidate in candidates:
        try:
            return ThreadingHTTPServer((host, candidate), handler)
        except OSError as error:
            last_error = error
    raise RuntimeError(f"cannot bind dashboard port starting at {port}: {last_error}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start read-only cowork-flow dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = get_repo_root()
    handler = make_handler(repo_root)
    server = _bind_server(args.host, args.port, handler)
    actual_host, actual_port = server.server_address[:2]
    url_host = "127.0.0.1" if actual_host in {"0.0.0.0", ""} else actual_host
    print(f"Dashboard: http://{url_host}:{actual_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
