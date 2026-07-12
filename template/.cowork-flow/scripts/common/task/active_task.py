from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path

from common.core.paths import DIR_WORKFLOW


DIR_RUNTIME = ".runtime"
DIR_SESSIONS = "sessions"
DIR_SUBAGENTS = "subagents"
FIELD_ACTIVE_TASK_PATH = "active_task_path"
FIELD_RUNTIME_CONTEXT_ID = "runtime_context_id"
FIELD_SCOPE = "scope"
SCOPE_MAIN = "main"
SCOPE_SUBAGENT = "subagent"
RUNTIME_CONTEXT_PROMPT_RE = re.compile(
    r"(?im)^\s*cowork_runtime_context_id\s*:\s*([A-Za-z0-9._-]+)\s*$"
)
HOST_CONTEXT_PROMPT_RE = re.compile(
    r"(?im)^\s*cowork_host_context_key\s*:\s*([A-Za-z0-9._-]+)\s*$"
)


@dataclass(frozen=True)
class ActiveTask:
    task_path: str | None
    context_key: str | None
    source: str


def _sanitize(raw: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip()).strip("._-")
    return safe[:160]


def _first_input_value(values: Mapping[str, object] | None, names: tuple[str, ...]) -> str | None:
    if values is None:
        return None
    for name in names:
        value = values.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _first_prompt_value(values: Mapping[str, object] | None) -> str | None:
    return _first_input_value(values, ("prompt", "user_prompt", "userPrompt", "message", "input"))


def resolve_context_key(values: Mapping[str, object] | None = None) -> str | None:
    explicit = os.environ.get("COWORK_FLOW_CONTEXT_ID")
    if explicit and explicit.strip():
        return _sanitize(explicit)

    opencode_session = os.environ.get("OPENCODE_SESSION_ID")
    if opencode_session and opencode_session.strip():
        return f"opencode_{_sanitize(opencode_session)}"

    claude_session = os.environ.get("CLAUDE_SESSION_ID")
    if claude_session and claude_session.strip():
        return f"claude_{_sanitize(claude_session)}"

    claude_code_session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if claude_code_session and claude_code_session.strip():
        return f"claude_{_sanitize(claude_code_session)}"

    codex_session = os.environ.get("CODEX_SESSION_ID")
    if codex_session and codex_session.strip():
        return f"codex_{_sanitize(codex_session)}"

    codex_thread = os.environ.get("CODEX_THREAD_ID")
    if codex_thread and codex_thread.strip():
        return f"codex_{_sanitize(codex_thread)}"

    input_explicit = _first_input_value(
        values,
        (
            "COWORK_FLOW_CONTEXT_ID",
            "cowork_flow_context_id",
            "context_id",
        ),
    )
    if input_explicit:
        return _sanitize(input_explicit)

    input_opencode_session = _first_input_value(
        values,
        (
            "OPENCODE_SESSION_ID",
            "opencode_session_id",
            "sessionID",
            "sessionId",
        ),
    )
    if input_opencode_session:
        return f"opencode_{_sanitize(input_opencode_session)}"

    input_claude_session = _first_input_value(
        values,
        (
            "CLAUDE_SESSION_ID",
            "claude_session_id",
            "CLAUDE_CODE_SESSION_ID",
            "claude_code_session_id",
        ),
    )
    if input_claude_session:
        return f"claude_{_sanitize(input_claude_session)}"

    input_session = _first_input_value(
        values,
        (
            "CODEX_SESSION_ID",
            "codex_session_id",
            "session_id",
        ),
    )
    if input_session:
        return f"codex_{_sanitize(input_session)}"

    input_thread = _first_input_value(
        values,
        (
            "CODEX_THREAD_ID",
            "codex_thread_id",
            "thread_id",
            "conversation_id",
        ),
    )
    if input_thread:
        return f"codex_{_sanitize(input_thread)}"

    return None


def sessions_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / DIR_RUNTIME / DIR_SESSIONS


def subagent_contexts_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / DIR_RUNTIME / DIR_SUBAGENTS


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_path(repo_root: Path, context_key: str) -> Path:
    return sessions_dir(repo_root) / f"{context_key}.json"


def logical_subagent_context_key(runtime_context_id: str) -> str:
    return f"subagent_{_sanitize(runtime_context_id)}"


def runtime_context_path(repo_root: Path, runtime_context_id: str) -> Path:
    return subagent_contexts_dir(repo_root) / f"{_sanitize(runtime_context_id)}.json"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic: write to temp then os.replace
    json_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json_text, encoding="utf-8")
    os.replace(tmp_path, path)


def _platform_from_context_key(context_key: str) -> str:
    if context_key.startswith("codex_"):
        return "codex"
    if context_key.startswith("opencode_"):
        return "opencode"
    if context_key.startswith("claude_"):
        return "claude-code"
    return "manual"


def resolve_runtime_context_id(values: Mapping[str, object] | None = None) -> str | None:
    explicit = os.environ.get("COWORK_FLOW_RUNTIME_CONTEXT_ID")
    if explicit and explicit.strip():
        return _sanitize(explicit)

    input_explicit = _first_input_value(
        values,
        (
            "COWORK_FLOW_RUNTIME_CONTEXT_ID",
            "cowork_runtime_context_id",
            "runtime_context_id",
        ),
    )
    if input_explicit:
        return _sanitize(input_explicit)

    prompt = _first_prompt_value(values)
    if prompt:
        match = RUNTIME_CONTEXT_PROMPT_RE.search(prompt)
        if match:
            return _sanitize(match.group(1))

    return None

def resolve_host_context_key(values: Mapping[str, object] | None = None) -> str | None:
    explicit = os.environ.get("COWORK_FLOW_HOST_CONTEXT_KEY")
    if explicit and explicit.strip():
        return _sanitize(explicit)

    input_explicit = _first_input_value(
        values,
        (
            "cowork_host_context_key",
            "host_context_key",
            "COWORK_FLOW_HOST_CONTEXT_KEY",
        ),
    )
    if input_explicit:
        return _sanitize(input_explicit)

    prompt = _first_prompt_value(values)
    if prompt:
        match = HOST_CONTEXT_PROMPT_RE.search(prompt)
        if match:
            return _sanitize(match.group(1))

    return None


def read_runtime_context(repo_root: Path, runtime_context_id: str) -> dict:
    from application.runtime_context_service import RuntimeContextService

    return RuntimeContextService(repo_root).load(runtime_context_id)


def write_runtime_context(repo_root: Path, runtime_context_id: str, data: dict) -> None:
    from application.runtime_context_service import RuntimeContextService

    RuntimeContextService(repo_root).replace(runtime_context_id, data)


def write_subagent_logical_session(
    repo_root: Path,
    runtime_context_id: str,
    task_path: str | None,
    platform: str,
    status: str = "pending_bind",
) -> str:
    context_key = logical_subagent_context_key(runtime_context_id)
    data: dict[str, object] = {
        "schema_version": 2,
        FIELD_SCOPE: SCOPE_SUBAGENT,
        FIELD_RUNTIME_CONTEXT_ID: runtime_context_id,
        "platform": platform,
        "status": status,
        "last_seen_at": _now(),
    }
    if task_path:
        data[FIELD_ACTIVE_TASK_PATH] = task_path.replace("\\", "/")
    _write_json(_session_path(repo_root, context_key), data)
    return context_key


def bind_runtime_context(
    repo_root: Path,
    runtime_context_id: str,
    host_context_key: str | None = None,
    values: Mapping[str, object] | None = None,
) -> dict | None:
    resolved_key = (
        _sanitize(host_context_key)
        if host_context_key
        else resolve_host_context_key(values) or resolve_context_key(values)
    )
    if not resolved_key:
        return None

    from application.runtime_context_service import (
        RuntimeContextError,
        RuntimeContextService,
    )

    try:
        return RuntimeContextService(repo_root).bind(
            runtime_context_id,
            resolved_key,
        )
    except RuntimeContextError:
        return None


def close_runtime_context(repo_root: Path, runtime_context_id: str) -> bool:
    from application.runtime_context_service import RuntimeContextService

    return RuntimeContextService(repo_root).close(runtime_context_id)


def build_active_task_session(
    repo_root: Path,
    task_path: str,
) -> tuple[Path, dict, ActiveTask] | None:
    """Build the session state needed to activate a task."""
    context_key = resolve_context_key()
    if not context_key:
        return None
    normalized = task_path.replace("\\", "/")
    target = repo_root / normalized
    if not target.is_dir():
        return None
    data = {
        FIELD_ACTIVE_TASK_PATH: normalized,
        FIELD_SCOPE: SCOPE_MAIN,
        "platform": _platform_from_context_key(context_key),
        "last_seen_at": _now(),
    }
    return (
        _session_path(repo_root, context_key),
        data,
        ActiveTask(normalized, context_key, "session"),
    )


def set_active_task(repo_root: Path, task_path: str) -> ActiveTask | None:
    prepared = build_active_task_session(repo_root, task_path)
    if prepared is None:
        return None
    session_path, data, active = prepared
    _write_json(session_path, data)
    return active


def get_active_task(repo_root: Path, values: Mapping[str, object] | None = None) -> ActiveTask:
    context_key = resolve_context_key(values)
    if not context_key:
        return ActiveTask(None, None, "missing-context")
    data = _read_json(_session_path(repo_root, context_key))
    task_path = data.get(FIELD_ACTIVE_TASK_PATH)
    if isinstance(task_path, str) and task_path.strip():
        return ActiveTask(task_path.strip(), context_key, "session")
    return ActiveTask(None, context_key, "empty-session")


def is_main_session(repo_root: Path, values: Mapping[str, object] | None = None) -> bool:
    """Return whether the current host session is an unscoped main session."""
    context_key = resolve_context_key(values)
    if not context_key:
        return False
    data = _read_json(_session_path(repo_root, context_key))
    scope = data.get(FIELD_SCOPE)
    historical_unscoped_main_session = (
        scope is None
        and not context_key.startswith("subagent_")
    )
    return (
        (scope == SCOPE_MAIN or historical_unscoped_main_session)
        and not data.get(FIELD_RUNTIME_CONTEXT_ID)
    )


def clear_active_task(repo_root: Path) -> ActiveTask:
    active = get_active_task(repo_root)
    if active.context_key:
        try:
            _session_path(repo_root, active.context_key).unlink()
        except OSError:
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
        if data.get(FIELD_ACTIVE_TASK_PATH) == normalized:
            try:
                path.unlink()
            except OSError:
                pass
            else:
                cleared += 1
    return cleared
