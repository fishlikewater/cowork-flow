#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host-neutral workflow-context injection entry.

Every process-hook host funnels through this module so the workflow facts are
rendered by a single Python source (workflow_state_hook.py + services.fact_view).
Host adapters keep only transport duties: event routing, the cheap Bash filter,
and byte forwarding. Per-host output differences (digest policy wording,
preamble, envelope pretty-printing) are selected by --host here, exactly as
frozen by spec/contracts/context-injection.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

LIFECYCLE_BASH_RE = re.compile(r"\brun(?:\.cmd)?\s+(?:task|subagent|resume)\b")

# This file lives in <scripts>/adapters/host/; running it as a script puts
# only its own directory on sys.path. The module root is needed both for the
# root=None fallback (no project scripts dir exists) and so a stale project
# copy never shadows the importing module.
SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HOST_ADAPTERS = {
    "zcode": "zcode.plugin",
    "claude-code": "claude-code.hooks",
    "codex": "codex.spawn_agent",
    "dsh": "dsh.preset",
}

NOT_INITIALIZED_BODY = (
    "<workflow-state>\n"
    "Status: not_initialized\n"
    "Source: cowork-flow-plugin\n"
    "⚠️ 项目未初始化 cowork-flow 工作流。\n"
    "\n"
    "请通过显式 init/sync 安装 cowork-flow 模板后再继续；"
    "hook 不会在注入阶段创建或复制项目文件。\n"
    "</workflow-state>"
)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            # newline="" keeps payload bytes identical across platforms —
            # text-mode translation would turn the pretty JSON indentation
            # into CRLF on Windows.
            stream.reconfigure(encoding="utf-8", errors="replace", newline="")


def _read_input() -> dict[str, Any]:
    raw = sys.stdin.buffer.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _claude_session_alias(data: dict[str, Any]) -> dict[str, Any]:
    # Ported from the claude-code wrapper: bare session_id must resolve as a
    # claude session, not fall through to the codex session_id rule.
    if "claude_session_id" not in data:
        session_id = data.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            data["claude_session_id"] = session_id
    return data


def _zcode_session_alias(data: dict[str, Any]) -> dict[str, Any]:
    # Ported from the zcode hook's resolveSessionKey candidate order
    # (env wins inside session_state; input aliases only fill the gap).
    # Without this, a bare sessionId/session_id would resolve as a codex
    # session and lose the session's own binding.
    existing = data.get("zcode_session_id")
    if isinstance(existing, str) and existing.strip():
        return data
    for key in ("ZCODE_SESSION_ID", "sessionId", "session_id"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            data["zcode_session_id"] = value
            break
    return data


def detect_event_name(hook_input: dict[str, Any]) -> str:
    name = hook_input.get("hook_event_name") or hook_input.get("hookEventName")
    if isinstance(name, str) and name.strip():
        return name.strip()
    if os.environ.get("CURSOR_PLUGIN_ROOT"):
        return "SessionStart"
    return "UserPromptSubmit"


def output_format() -> str:
    if os.environ.get("CURSOR_PLUGIN_ROOT"):
        return "cursor"
    if os.environ.get("CLAUDE_PLUGIN_ROOT") and not os.environ.get("COPILOT_CLI"):
        return "claude"
    return "generic"


def find_workflow_root(start: Path | None) -> Path | None:
    if start is None:
        return None
    current = start.resolve()
    while True:
        if (current / ".cowork-flow").is_dir():
            return current
        if current == current.parent:
            return None
        current = current.parent


def resolve_root(hook_input: dict[str, Any]) -> Path | None:
    candidates = [
        hook_input.get("cwd"),
        os.environ.get("ZCODE_PROJECT_DIR"),
        os.environ.get("CLAUDE_PROJECT_DIR"),
        os.getcwd(),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            root = find_workflow_root(Path(candidate))
            if root is not None:
                return root
    return None


def _is_lifecycle_bash(hook_input: dict[str, Any]) -> bool:
    tool_input = hook_input.get("tool_input")
    command = (
        tool_input.get("command") if isinstance(tool_input, dict) else None
    )
    if not isinstance(command, str):
        return False
    normalized = command.replace("\\", "/")
    return ".cowork-flow/run" in normalized or bool(
        LIFECYCLE_BASH_RE.search(normalized)
    )


def _session_start_for_host(host: str, event_name: str) -> bool | None:
    # zcode / claude-code signal session start by event name; codex registers
    # UserPromptSubmit only, so its digest shape derives from the session
    # state file probe (build_hook_context session_start=None).
    if host in {"zcode", "claude-code"}:
        return event_name == "SessionStart"
    return None


def _host_preamble(root: Path, host: str) -> tuple[str, ...]:
    if host == "claude-code":
        return (
            (
                "<claude-code-runtime>\n"
                "hooks: UserPromptSubmit, SessionStart, PostToolUse\n"
                "</claude-code-runtime>"
            ),
        )
    if host == "codex":
        from adapters.host.workflow_state_hook import codex_dispatch_mode

        dispatch_mode = codex_dispatch_mode(root)
        return (
            f"<codex-dispatch-mode>{dispatch_mode}</codex-dispatch-mode>",
            (
                "<codex-runtime>\n"
                "dispatch_mode_meaning: workflow dispatch hint, not current "
                "thread role\n"
                "runtime_context_identity: formal subagent sessions bind "
                "before workflow-state injection\n"
                "</codex-runtime>"
            ),
        )
    return ()


def _not_initialized_context(
    hook_input: dict[str, Any], event_name: str, host: str
) -> str:
    from adapters.host.workflow_state_hook import (
        _build_contract_digest,
        _load_contract_registry,
        contract_fingerprint,
    )

    env_dir = (
        os.environ.get("ZCODE_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or hook_input.get("cwd")
        or os.getcwd()
    )
    digest_root = Path(env_dir)
    if event_name == "SessionStart":
        prefix = _build_contract_digest(digest_root, host, HOST_ADAPTERS[host])
    else:
        contracts, _warning = _load_contract_registry(digest_root)
        prefix = (
            f'<contract-fingerprint value="{contract_fingerprint(digest_root, contracts)}"/>'
        )
    return f"{prefix}\n\n{NOT_INITIALIZED_BODY}"


def _emit(
    context: str, event_name: str, host: str, output_format_name: str
) -> None:
    if output_format_name == "cursor":
        payload: dict[str, Any] = {"additional_context": context}
    else:
        payload = {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": context,
            }
        }
    indent = 2 if host == "zcode" else None
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=indent))


def _handle_post_tool_use(
    root: Path | None,
    hook_input: dict[str, Any],
    host: str,
    output_format_name: str,
) -> int:
    if root is None:
        return 0
    tool_name = str(hook_input.get("tool_name") or "")
    tool_input = hook_input.get("tool_input")
    file_path = (
        tool_input.get("file_path") if isinstance(tool_input, dict) else None
    )
    event_name = "PostToolUse"
    if host == "zcode":
        if (
            tool_name in {"Edit", "Write", "MultiEdit"}
            and isinstance(file_path, str)
            and file_path.strip()
        ):
            from adapters.host.workflow_state_hook import merged_edit_warning

            context = merged_edit_warning(root, hook_input)
            if context:
                _emit(context, event_name, host, output_format_name)
            return 0
        # Edit storms must not multiply the injection payload; only lifecycle
        # commands trigger a mid-turn state refresh (the shim pre-filters the
        # common case, this branch keeps the entry correct standalone).
        if not _is_lifecycle_bash(hook_input):
            return 0
        from adapters.host.workflow_state_hook import build_hook_context

        context = build_hook_context(
            root,
            hook_input,
            host=host,
            adapter=HOST_ADAPTERS[host],
            preamble=(),
            session_start=False,
        )
        _emit(context, event_name, host, output_format_name)
        return 0

    # claude-code / codex: spec-check short path only — at most one advisory
    # line on stderr (exit 2 surfaces it to the model); the edit itself has
    # already happened.
    from adapters.host.workflow_state_hook import spec_edit_warning

    warning = spec_edit_warning(root, hook_input, host)
    if warning:
        print(warning, file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    if (
        os.environ.get("COWORK_FLOW_HOOKS") == "0"
        or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1"
    ):
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=sorted(HOST_ADAPTERS))
    args = parser.parse_args(argv)
    host = args.host

    hook_input = _read_input()
    if host == "claude-code":
        hook_input = _claude_session_alias(hook_input)
    elif host == "zcode":
        hook_input = _zcode_session_alias(hook_input)
    event_name = detect_event_name(hook_input)
    output_format_name = output_format()
    root = resolve_root(hook_input)

    if event_name == "PostToolUse":
        return _handle_post_tool_use(root, hook_input, host, output_format_name)

    if root is None:
        if host == "zcode":
            _emit(
                _not_initialized_context(hook_input, event_name, host),
                event_name,
                host,
                output_format_name,
            )
            return 0
        # claude-code / codex wrappers exit silently outside a project.
        return 0

    scripts_dir = root / ".cowork-flow" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from adapters.host.workflow_state_hook import build_hook_context

    context = build_hook_context(
        root,
        hook_input,
        host=host,
        adapter=HOST_ADAPTERS[host],
        preamble=_host_preamble(root, host),
        session_start=_session_start_for_host(host, event_name),
    )
    _emit(context, event_name, host, output_format_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
