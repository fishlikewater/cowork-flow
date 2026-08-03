#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime-context scoped subagent state."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401
from runtime.session_state import (
    resolve_context_key,
    runtime_context_path,
    sessions_dir,
    subagent_contexts_dir,
)
from services.workflow_runtime import (
    RuntimeContextError,
    RuntimeContextService,
)
from adapters.cli.execution_context_args import build_internal_execution_context_parser
from infra.paths import get_repo_root

VALID_STATUSES = {"pending", "bound", "active", "success", "needs_context", "blocked", "closed"}
FIXED_AGENT_TYPES = {"cowork-research", "cowork-implement", "cowork-check"}
GENERIC_AGENT_TYPE = "worker"
ROLE_AGENT_TYPE_ALIASES = {
    "research": "cowork-research",
    "implement": "cowork-implement",
    "check": "cowork-check",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "subagent"


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _next_id(base_dir: Path, title: str) -> str:
    prefix = datetime.now().strftime("rtx_%Y%m%d_%H%M%S")
    base = f"{prefix}_{_slug(title)}"
    candidate = base
    counter = 2
    while (base_dir / f"{candidate}.json").exists():
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _detect_host() -> str:
    env = os.environ
    if env.get("CLAUDE_CODE_SESSION_ID") or env.get("CLAUDE_SESSION_ID"):
        return "claude-code"
    if env.get("CODEX_SESSION_ID") or env.get("CODEX_THREAD_ID"):
        return "codex"
    if env.get("ZCODE_SESSION_ID"):
        return "zcode"
    if env.get("OPENCODE_SESSION_ID"):
        return "opencode"
    return "codex"


def _detect_adapter(host: str) -> str:
    adapters = {
        "claude-code": "claude-code.hooks",
        "codex": "codex.spawn_agent",
        "opencode": "opencode.task",
        "zcode": "zcode.plugin",
    }
    return adapters.get(host, "codex.spawn_agent")


def _host_context_prefix(host: str) -> str:
    normalized = host.strip().lower()
    if normalized == "claude-code":
        return "claude"
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "host"

def _suggest_host_context_key(host: str, runtime_context_id: str) -> str:
    return f"{_host_context_prefix(host)}_{runtime_context_id}"

def _print_runtime_error(error: RuntimeContextError) -> None:
    print(f"Error: {error.code}: {error.detail}", file=sys.stderr)

def _resolve_agent_type(role: str, agent_type: str | None) -> tuple[str, str]:
    normalized_role = role.strip()
    requested = agent_type.strip() if isinstance(agent_type, str) else ""
    if requested:
        if requested in FIXED_AGENT_TYPES:
            if normalized_role in FIXED_AGENT_TYPES and normalized_role != requested:
                raise ValueError(f"agent-type {requested} cannot use role {normalized_role}")
            if normalized_role in ROLE_AGENT_TYPE_ALIASES and ROLE_AGENT_TYPE_ALIASES[normalized_role] != requested:
                raise ValueError(f"agent-type {requested} cannot use role {normalized_role}")
            return requested, "formal"
        if requested == GENERIC_AGENT_TYPE:
            if normalized_role in FIXED_AGENT_TYPES or normalized_role in ROLE_AGENT_TYPE_ALIASES:
                raise ValueError("agent-type worker requires non-fixed role")
            return requested, "advisory"
        raise ValueError("agent-type must be cowork-research, cowork-implement, cowork-check, or worker")
    if normalized_role in FIXED_AGENT_TYPES:
        return normalized_role, "formal"
    if normalized_role in ROLE_AGENT_TYPE_ALIASES:
        return ROLE_AGENT_TYPE_ALIASES[normalized_role], "formal"
    return GENERIC_AGENT_TYPE, "advisory"


def cmd_init(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    base_dir = subagent_contexts_dir(repo_root)
    runtime_context_id = _next_id(base_dir, args.title)
    task_dir = getattr(args, "execution_task_dir", None)
    host = args.host or _detect_host()
    adapter = args.adapter or _detect_adapter(host)
    try:
        agent_type, dispatch_kind = _resolve_agent_type(args.role, getattr(args, "agent_type", None))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if dispatch_kind == "formal" and not task_dir:
        print("Error: fixed agent dispatch requires --execution-task-dir", file=sys.stderr)
        return 1

    allowed_context = [{"file": item, "reason": "prompt-named context"} for item in args.allowed_context]
    parent_context_key = resolve_context_key()
    context = {
        "schema_version": 2,
        "runtime_context_id": runtime_context_id,
        "scope": "subagent",
        "host": host,
        "adapter": adapter,
        "agent_type": agent_type,
        "role": args.role,
        "task_dir": task_dir,
        "parent_context_key": parent_context_key,
        "transport": {
            "kind": "prompt",
            "key": "cowork_runtime_context_id",
        },
        "assignment": {
            "title": args.title,
            "goal": args.goal or args.title,
            "allowed_context": allowed_context,
            "expected_output": args.expected_output,
            "source": args.source,
        },
        "authority": {
            "may_start_task": False,
            "may_resume_main": False,
            "may_archive": False,
            "may_commit": False,
            "may_spawn": False,
        },
        "status": "pending",
        "dispatch_kind": dispatch_kind,
        "created_at": _now(),
        "bound_context_key": None,
        "closed_at": None,
    }
    try:
        initialized = RuntimeContextService(repo_root).initialize(
            runtime_context_id,
            context,
        )
    except RuntimeContextError as error:
        _print_runtime_error(error)
        return 1
    logical_context_key = initialized.logical_context_key
    host_context_key = _suggest_host_context_key(host, runtime_context_id)

    print(
        json.dumps(
            {
                "id": runtime_context_id,
                "runtimeContextId": runtime_context_id,
                "cowork_runtime_context_id": runtime_context_id,
                "hostContextKey": host_context_key,
                "cowork_host_context_key": host_context_key,
                "agentType": agent_type,
                "role": args.role,
                "taskDir": task_dir,
                "dispatchKind": dispatch_kind,
                "runtimeContextFile": _relative(repo_root, runtime_context_path(repo_root, runtime_context_id)),
                "logicalSessionFile": _relative(repo_root, sessions_dir(repo_root) / f"{logical_context_key}.json"),
                "promptTransport": (
                    f"cowork_runtime_context_id: {runtime_context_id}\n"
                    f"cowork_host_context_key: {host_context_key}"
                ),
                "bindCommand": f".cowork-flow/run subagent bind {runtime_context_id} {host_context_key}",
            },
            ensure_ascii=False,
        )
    )
    return 0


def _find_subagent(repo_root: Path, runtime_context_id: str) -> dict:
    context = RuntimeContextService(repo_root).load(runtime_context_id)
    if not context:
        raise FileNotFoundError(runtime_context_id)
    return context


def cmd_status(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    try:
        context = _find_subagent(repo_root, args.subagent_id)
    except FileNotFoundError:
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    print(json.dumps(context, ensure_ascii=False, indent=2) + "\n", end="")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    if args.status not in VALID_STATUSES:
        print(f"Error: status must be one of {', '.join(sorted(VALID_STATUSES))}", file=sys.stderr)
        return 1
    repo_root = get_repo_root()
    try:
        context = _find_subagent(repo_root, args.subagent_id)
    except FileNotFoundError:
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    try:
        context = RuntimeContextService(repo_root).update(
            args.subagent_id,
            status=args.status,
            note=args.note,
        )
    except RuntimeContextError as error:
        _print_runtime_error(error)
        return 1
    if context is None:
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    print(f"subagent {args.subagent_id} status={args.status}")
    return 0


def cmd_bind(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    try:
        context = RuntimeContextService(repo_root).bind(
            args.subagent_id,
            args.context_key,
        )
    except RuntimeContextError as error:
        _print_runtime_error(error)
        return 1
    if context is None:
        print(f"Error: cannot bind runtime context: {args.subagent_id}", file=sys.stderr)
        return 1
    print(json.dumps(context, ensure_ascii=False, indent=2) + "\n", end="")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    try:
        closed = RuntimeContextService(repo_root).close(args.subagent_id)
    except RuntimeContextError as error:
        _print_runtime_error(error)
        return 1
    if not closed:
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    print(f"subagent {args.subagent_id} closed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Runtime-context scoped subagent state",
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create runtime subagent context")
    init.add_argument("--title", required=True)
    init.add_argument("--role", default="subagent")
    init.add_argument("--agent-type")
    init.add_argument("--execution-task-dir", default=argparse.SUPPRESS)
    init.add_argument("--source", default="auto")
    init.add_argument("--goal")
    init.add_argument("--expected-output", default="Files changed, validation commands, and blockers.")
    init.add_argument("--allowed-context", action="append", default=[])
    init.add_argument("--host", default=None)
    init.add_argument("--adapter", default=None)
    init.set_defaults(func=cmd_init)

    status = subparsers.add_parser("status", help="Print subagent runtime context")
    status.add_argument("subagent_id")
    status.set_defaults(func=cmd_status)

    update = subparsers.add_parser("update", help="Update subagent runtime status")
    update.add_argument("subagent_id")
    update.add_argument("--status", required=True)
    update.add_argument("--note")
    update.set_defaults(func=cmd_update)

    bind = subparsers.add_parser("bind", help="Bind host session to runtime context")
    bind.add_argument("subagent_id")
    bind.add_argument("context_key")
    bind.set_defaults(func=cmd_bind)

    close = subparsers.add_parser("close", help="Close subagent runtime context")
    close.add_argument("subagent_id")
    close.set_defaults(func=cmd_close)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
