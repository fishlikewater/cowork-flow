from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import DIR_WORKFLOW


DIR_RUNTIME = ".runtime"
DIR_SESSIONS = "sessions"


@dataclass(frozen=True)
class ActiveTask:
    task_path: str | None
    context_key: str | None
    source: str


def _sanitize(raw: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip()).strip("._-")
    return safe[:160]


def resolve_context_key() -> str | None:
    explicit = os.environ.get("COWORK_FLOW_CONTEXT_ID")
    if explicit and explicit.strip():
        return _sanitize(explicit)

    codex_session = os.environ.get("CODEX_SESSION_ID")
    if codex_session and codex_session.strip():
        return f"codex_{_sanitize(codex_session)}"

    codex_thread = os.environ.get("CODEX_THREAD_ID")
    if codex_thread and codex_thread.strip():
        return f"codex_{_sanitize(codex_thread)}"

    return None


def sessions_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / DIR_RUNTIME / DIR_SESSIONS


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_path(repo_root: Path, context_key: str) -> Path:
    return sessions_dir(repo_root) / f"{context_key}.json"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_active_task(repo_root: Path, task_path: str) -> ActiveTask | None:
    context_key = resolve_context_key()
    if not context_key:
        return None
    normalized = task_path.replace("\\", "/")
    target = repo_root / normalized
    if not target.is_dir():
        return None
    _write_json(
        _session_path(repo_root, context_key),
        {
            "current_task": normalized,
            "platform": "codex" if context_key.startswith("codex_") else "manual",
            "last_seen_at": _now(),
        },
    )
    return ActiveTask(normalized, context_key, "session")


def get_active_task(repo_root: Path) -> ActiveTask:
    context_key = resolve_context_key()
    if not context_key:
        return ActiveTask(None, None, "missing-context")
    data = _read_json(_session_path(repo_root, context_key))
    task_path = data.get("current_task")
    if isinstance(task_path, str) and task_path.strip():
        return ActiveTask(task_path.strip(), context_key, "session")
    return ActiveTask(None, context_key, "empty-session")


def clear_active_task(repo_root: Path) -> ActiveTask:
    active = get_active_task(repo_root)
    if active.context_key:
        try:
            _session_path(repo_root, active.context_key).unlink()
        except FileNotFoundError:
            pass
    return active


def clear_task_from_sessions(repo_root: Path, task_path: str) -> int:
    cleared = 0
    root = sessions_dir(repo_root)
    if not root.is_dir():
        return 0
    normalized = task_path.replace("\\", "/")
    for path in root.glob("*.json"):
        data = _read_json(path)
        if data.get("current_task") == normalized:
            path.unlink()
            cleared += 1
    return cleared
