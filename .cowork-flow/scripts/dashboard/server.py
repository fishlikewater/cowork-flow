#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Flow dashboard server."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import signal
import subprocess
import sys
import time
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

def _runtime_dir(repo_root: Path) -> Path:
    path = repo_root / ".cowork-flow" / ".runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path

def _state_path(repo_root: Path) -> Path:
    return _runtime_dir(repo_root) / "dashboard.json"

def _read_state(repo_root: Path) -> dict | None:
    path = _state_path(repo_root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

def _write_state(repo_root: Path, state: dict) -> None:
    _state_path(repo_root).write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def _remove_state(repo_root: Path) -> None:
    try:
        _state_path(repo_root).unlink()
    except FileNotFoundError:
        return

def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def _terminate_pid(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return

def _json_print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))

def _server_url(host: str, port: int) -> str:
    url_host = "127.0.0.1" if host in {"0.0.0.0", ""} else host
    return f"http://{url_host}:{port}"

def _serve_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser

def cmd_serve(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    handler = make_handler(repo_root)
    server = _bind_server(args.host, args.port, handler)
    actual_host, actual_port = server.server_address[:2]
    print(f"Dashboard: {_server_url(actual_host, actual_port)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0

def cmd_start(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    existing = _read_state(repo_root)
    if existing and _pid_alive(existing.get("pid")):
        _json_print({**existing, "running": True, "state_file": str(_state_path(repo_root))})
        return 0

    runtime_dir = _runtime_dir(repo_root)
    stdout_log = runtime_dir / "dashboard.out.log"
    stderr_log = runtime_dir / "dashboard.err.log"
    stderr_handle = stderr_log.open("a", encoding="utf-8")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    popen_kwargs = {
        "cwd": str(repo_root),
        "stdout": subprocess.PIPE,
        "stderr": stderr_handle,
        "text": True,
        "encoding": "utf-8",
        "creationflags": creationflags,
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "serve", "--host", args.host, "--port", str(args.port)],
        **popen_kwargs,
    )
    assert process.stdout is not None
    line = process.stdout.readline().strip()
    stderr_handle.close()
    if not line:
        process.poll()
        raise RuntimeError(f"dashboard failed to start; see {stderr_log}")
    stdout_log.write_text(line + "\n", encoding="utf-8")
    url = line.rsplit(" ", 1)[-1]
    state = {
        "pid": process.pid,
        "host": args.host,
        "port": int(url.rsplit(":", 1)[-1]),
        "url": url,
        "repo_root": str(repo_root),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }
    _write_state(repo_root, state)
    _json_print({**state, "running": True, "state_file": str(_state_path(repo_root))})
    return 0

def cmd_status(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    state = _read_state(repo_root)
    if not state:
        _json_print({"running": False, "state_file": str(_state_path(repo_root))})
        return 1
    running = _pid_alive(state.get("pid"))
    _json_print({**state, "running": running, "state_file": str(_state_path(repo_root))})
    return 0 if running else 1

def cmd_stop(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    state = _read_state(repo_root)
    if not state:
        _json_print({"stopped": True, "running": False, "state_file": str(_state_path(repo_root))})
        return 0
    pid = state.get("pid")
    if _pid_alive(pid):
        _terminate_pid(pid)
        for _ in range(20):
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
    _remove_state(repo_root)
    _json_print({"stopped": True, "running": False, "pid": pid, "state_file": str(_state_path(repo_root))})
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage read-only cowork-flow dashboard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run dashboard server in foreground")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.set_defaults(func=cmd_serve)

    start = subparsers.add_parser("start", help="Start dashboard server for this project")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=8080)
    start.set_defaults(func=cmd_start)

    status = subparsers.add_parser("status", help="Show this project's dashboard server status")
    status.set_defaults(func=cmd_status)

    stop = subparsers.add_parser("stop", help="Stop this project's dashboard server")
    stop.set_defaults(func=cmd_stop)
    return parser

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        args = _serve_parser("Start read-only cowork-flow dashboard").parse_args(argv)
        return cmd_serve(args)
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
