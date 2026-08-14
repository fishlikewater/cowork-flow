from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path

from infra.paths import DIR_WORKFLOW


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
    context_key = _resolve_env_context_key() or _resolve_input_context_key(values)
    if context_key:
        return context_key
    # zcode 主会话（Bash CLI）无任何 host session id：用进程标签兜底，
    # 保证 task start / session 解析一次成功，不再回落到其它 host。
    process_label = os.environ.get("ZCODE_PROCESS_LABEL")
    if process_label and process_label.strip():
        return _prefixed_context_key("zcode", process_label)
    return None


def _prefixed_context_key(prefix: str, raw: str | None) -> str | None:
    if raw and raw.strip():
        return f"{prefix}_{_sanitize(raw)}"
    return None


def _resolve_env_context_key() -> str | None:
    explicit = os.environ.get("COWORK_FLOW_CONTEXT_ID")
    if explicit and explicit.strip():
        return _sanitize(explicit)

    for prefix, env_name in (
        ("zcode", "ZCODE_SESSION_ID"),
        ("opencode", "OPENCODE_SESSION_ID"),
        ("claude", "CLAUDE_SESSION_ID"),
        ("claude", "CLAUDE_CODE_SESSION_ID"),
        ("codex", "CODEX_SESSION_ID"),
        ("codex", "CODEX_THREAD_ID"),
    ):
        context_key = _prefixed_context_key(prefix, os.environ.get(env_name))
        if context_key:
            return context_key
    return None


def _resolve_input_context_key(values: Mapping[str, object] | None) -> str | None:
    explicit = _first_input_value(
        values,
        ("COWORK_FLOW_CONTEXT_ID", "cowork_flow_context_id", "context_id"),
    )
    if explicit:
        return _sanitize(explicit)

    # 真实 zcode hook env 带 ZCODE_SESSION_ID：input 的 sessionId/session_id
    # 归 zcode 前缀，避免被通用 key 误标成 opencode/codex；无 session 键直接短路。
    if os.environ.get("ZCODE_SESSION_ID"):
        zcode_session = _first_input_value(
            values,
            (
                "ZCODE_SESSION_ID",
                "zcode_session_id",
                "sessionId",
                "session_id",
            ),
        )
        if zcode_session:
            return _prefixed_context_key("zcode", zcode_session)
        return None

    for prefix, names in (
        ("zcode", ("ZCODE_SESSION_ID", "zcode_session_id")),
        ("opencode", ("OPENCODE_SESSION_ID", "opencode_session_id", "sessionID", "sessionId")),
        ("claude", ("CLAUDE_SESSION_ID", "claude_session_id", "CLAUDE_CODE_SESSION_ID", "claude_code_session_id")),
        ("codex", ("CODEX_SESSION_ID", "codex_session_id", "session_id")),
        ("codex", ("CODEX_THREAD_ID", "codex_thread_id", "thread_id", "conversation_id")),
    ):
        context_key = _prefixed_context_key(prefix, _first_input_value(values, names))
        if context_key:
            return context_key
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


def platform_from_context_key(context_key: str) -> str:
    if context_key.startswith("zcode_"):
        return "zcode"
    if context_key.startswith("codex_"):
        return "codex"
    if context_key.startswith("opencode_"):
        return "opencode"
    if context_key.startswith("claude_"):
        return "claude-code"
    if context_key.startswith("dsh_"):
        return "dsh"
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
        "platform": platform_from_context_key(context_key),
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
