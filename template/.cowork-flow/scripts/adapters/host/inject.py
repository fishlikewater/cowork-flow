#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host-neutral workflow-context injection entry.

Every process-hook host funnels through this module so the workflow facts are
rendered by a single Python source (workflow_state_hook.py + services.fact_view).
The entry keeps only transport duties: event routing and byte forwarding.
Per-host behavior differences (session aliases, preamble, digest policy
wording, edit warnings, envelope pretty-printing) ride the host policy
modules beside this file, selected by --host, exactly as frozen by
spec/contracts/context-injection.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# This file lives in <scripts>/adapters/host/; running it as a script puts
# only its own directory on sys.path. The module root is needed both for the
# root=None fallback (no project scripts dir exists) and so a stale project
# copy never shadows the importing module.
SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from runtime.host_identity import HOST_HINT_ENV, context_adapters


# Hosts that route through this entry, taken from the single declaration in
# runtime/host_identity.py. opencode is absent on purpose: its JS plugin
# renders context itself, so it is not an --host choice here.
HOST_ADAPTERS = context_adapters()

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


def _not_initialized_context(
    hook_input: dict[str, Any],
    event_name: str,
    host: str,
    policy: Any,
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
        prefix = _build_contract_digest(digest_root, policy, HOST_ADAPTERS[host])
    else:
        contracts, _warning = _load_contract_registry(digest_root)
        prefix = (
            f'<contract-fingerprint value="{contract_fingerprint(digest_root, contracts)}"/>'
        )
    return f"{prefix}\n\n{NOT_INITIALIZED_BODY}"


def _emit(
    context: str,
    event_name: str,
    output_format_name: str,
    policy: Any,
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
    indent = 2 if policy.emit_indent else None
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=indent))


def _handle_post_tool_use(
    root: Path | None,
    hook_input: dict[str, Any],
    policy: Any,
    output_format_name: str,
) -> int:
    if root is None:
        return 0
    if policy.post_tool_use is None:
        return 0
    context, exit_code = policy.post_tool_use(root, hook_input)
    if context:
        _emit(context, "PostToolUse", output_format_name, policy)
    return exit_code


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

    from adapters.host.workflow_state_hook import (
        build_hook_context,
        resolve_policy,
    )

    policy = resolve_policy(host)

    hook_input = _read_input()
    # The adapter states which host this payload came from, so the identity
    # resolver below never has to infer a host from key shapes.
    hook_input.setdefault(HOST_HINT_ENV, host)
    event_name = detect_event_name(hook_input)
    output_format_name = output_format()
    root = resolve_root(hook_input)

    if event_name == "PostToolUse":
        return _handle_post_tool_use(root, hook_input, policy, output_format_name)

    if root is None:
        if policy.emit_not_initialized:
            _emit(
                _not_initialized_context(hook_input, event_name, host, policy),
                event_name,
                output_format_name,
                policy,
            )
            return 0
        # Hosts without the not-initialized payload exit silently outside a
        # project.
        return 0

    scripts_dir = root / ".cowork-flow" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    # zcode / claude-code signal session start by event name; codex (and the
    # default policy) register UserPromptSubmit only, so their digest shape
    # derives from the session state file probe (session_start=None).
    if policy.session_start_event is None:
        session_start = None
    else:
        session_start = event_name == policy.session_start_event

    preamble = policy.preamble(root) if policy.preamble is not None else ()
    context = build_hook_context(
        root,
        hook_input,
        host=host,
        adapter=HOST_ADAPTERS[host],
        preamble=preamble,
        session_start=session_start,
        policy=policy,
    )
    _emit(context, event_name, output_format_name, policy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
