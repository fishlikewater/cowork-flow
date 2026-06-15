#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime-context scoped subagent state."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from common.active_task import (
    bind_runtime_context,
    close_runtime_context,
    read_runtime_context,
    resolve_context_key,
    runtime_context_path,
    subagent_contexts_dir,
    write_runtime_context,
    write_subagent_logical_session,
)
from common.execution_context import build_internal_execution_context_parser
from common.paths import TASK_DATE_PREFIX_PATTERN, get_db_path, get_repo_root
from flow.store import FlowStore

VALID_STATUSES = {
    "pending",
    "bound",
    "active",
    "running",
    "success",
    "failed",
    "cancelled",
    "error",
    "needs_context",
    "blocked",
    "closed",
}
ACTIVE_AGENT_RUN_STATUSES = {"pending", "bound", "active", "running", "needs_context", "blocked", "success", "failed", "cancelled", "error"}
DONE_AGENT_RUN_STATUSES = {"success", "closed"}
FAILED_AGENT_RUN_STATUSES = {"failed", "cancelled", "error"}
DONE_TASK_STATUSES = {"completed", "archived"}
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


def _host_context_prefix(host: str) -> str:
    normalized = host.strip().lower()
    if normalized == "claude-code":
        return "claude"
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "host"

def _suggest_host_context_key(host: str, runtime_context_id: str) -> str:
    return f"{_host_context_prefix(host)}_{runtime_context_id}"

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


def _role_for_agent_type(agent_type: str) -> str:
    for role, mapped_agent_type in ROLE_AGENT_TYPE_ALIASES.items():
        if mapped_agent_type == agent_type:
            return role
    return agent_type

def _codex_task_name(runtime_context_id: str) -> str:
    task_name = re.sub(r"[^a-z0-9_]+", "_", runtime_context_id.lower()).strip("_")
    return task_name or "subagent"

def _create_runtime_context_payload(
    repo_root: Path,
    *,
    title: str,
    role: str,
    agent_type: str | None,
    task_dir: str | None,
    source: str,
    goal: str | None,
    expected_output: str,
    allowed_context: list[str],
    host: str,
    adapter: str,
    record_agent_run: bool = True,
) -> dict:
    base_dir = subagent_contexts_dir(repo_root)
    runtime_context_id = _next_id(base_dir, title)
    resolved_agent_type, dispatch_kind = _resolve_agent_type(role, agent_type)
    if dispatch_kind == "formal" and not task_dir:
        raise ValueError("fixed agent dispatch requires --execution-task-dir")

    allowed_context_entries = [{"file": item, "reason": "prompt-named context"} for item in allowed_context]
    parent_context_key = resolve_context_key()
    task_id = None
    if task_dir:
        try:
            with FlowStore(str(get_db_path(repo_root))) as store:
                task = _resolve_flow_task(store, task_dir)
                task_id = task.id if task else None
        except Exception:
            task_id = None
    context = {
        "schema_version": 2,
        "runtime_context_id": runtime_context_id,
        "scope": "subagent",
        "host": host,
        "adapter": adapter,
        "agent_type": resolved_agent_type,
        "role": role,
        "task_id": task_id,
        "task_dir": task_dir,
        "parent_context_key": parent_context_key,
        "transport": {
            "kind": "prompt",
            "key": "cowork_runtime_context_id",
        },
        "assignment": {
            "title": title,
            "goal": goal or title,
            "allowed_context": allowed_context_entries,
            "expected_output": expected_output,
            "source": source,
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
    write_runtime_context(repo_root, runtime_context_id, context)
    logical_context_key = write_subagent_logical_session(
        repo_root,
        runtime_context_id,
        task_dir,
        host,
    )
    host_context_key = _suggest_host_context_key(host, runtime_context_id)
    if record_agent_run:
        _record_agent_run_for_task(
            repo_root,
            runtime_context_id=runtime_context_id,
            task_dir=task_dir,
            agent_type=resolved_agent_type,
            dispatch_kind=dispatch_kind,
            host_context_key=host_context_key,
            created_at=context["created_at"],
        )

    return {
        "id": runtime_context_id,
        "runtimeContextId": runtime_context_id,
        "cowork_runtime_context_id": runtime_context_id,
        "hostContextKey": host_context_key,
        "cowork_host_context_key": host_context_key,
        "agentType": resolved_agent_type,
        "role": role,
        "taskDir": task_dir,
        "dispatchKind": dispatch_kind,
        "runtimeContextSource": "db",
        "runtimeContextFile": _relative(repo_root, runtime_context_path(repo_root, runtime_context_id)),
        "logicalSessionKey": logical_context_key,
        "promptTransport": (
            f"cowork_runtime_context_id: {runtime_context_id}\n"
            f"cowork_host_context_key: {host_context_key}"
        ),
        "bindCommand": f".cowork-flow/run subagent bind {runtime_context_id} {host_context_key}",
    }

def cmd_init(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    try:
        payload = _create_runtime_context_payload(
            repo_root,
            title=args.title,
            role=args.role,
            agent_type=getattr(args, "agent_type", None),
            task_dir=getattr(args, "execution_task_dir", None),
            source=args.source,
            goal=args.goal,
            expected_output=args.expected_output,
            allowed_context=args.allowed_context,
            host=args.host,
            adapter=args.adapter,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _codex_dispatch_message(payload: dict, expected_output: str) -> str:
    runtime_context_id = payload["runtimeContextId"]
    host_context_key = payload["hostContextKey"]
    bind_command = f".\\.cowork-flow\\run.cmd subagent bind {runtime_context_id} {host_context_key}"
    return "\n".join(
        [
            f"cowork_runtime_context_id: {runtime_context_id}",
            f"cowork_host_context_key: {host_context_key}",
            "",
            "First step:",
            bind_command,
            "",
            "Do not continue formal work if bind fails.",
            f"Task: {payload['taskDir']}",
            f"Role: {payload['role']}",
            f"Agent type: {payload['agentType']}",
            f"Expected output: {expected_output}",
        ]
    )

def cmd_dispatch_codex(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    try:
        runtime_payload = _create_runtime_context_payload(
            repo_root,
            title=args.title,
            role=args.role,
            agent_type=args.agent_type,
            task_dir=args.execution_task_dir,
            source=args.source,
            goal=args.goal,
            expected_output=args.expected_output,
            allowed_context=args.allowed_context,
            host="codex",
            adapter="codex.spawn_agent",
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if runtime_payload["dispatchKind"] != "formal":
        print("Error: dispatch-codex only supports formal cowork-* agents", file=sys.stderr)
        return 1

    payload = {
        **runtime_payload,
        "agent_type": runtime_payload["agentType"],
        "task_name": _codex_task_name(runtime_payload["runtimeContextId"]),
        "fork_turns": args.fork_turns,
        "message": _codex_dispatch_message(runtime_payload, args.expected_output),
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0

def _find_subagent(repo_root: Path, runtime_context_id: str) -> dict:
    context = read_runtime_context(repo_root, runtime_context_id)
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
    context["status"] = args.status
    context["updated_at"] = _now()
    if args.note:
        context["note"] = args.note
    write_runtime_context(repo_root, args.subagent_id, context)
    _update_agent_run_if_present(repo_root, args.subagent_id, args.status)
    print(f"subagent {args.subagent_id} status={args.status}")
    return 0


def cmd_bind(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    existing = read_runtime_context(repo_root, args.subagent_id)
    existing_key = existing.get("bound_context_key") if existing else None
    if isinstance(existing_key, str) and existing_key.strip() and existing_key != args.context_key:
        print(
            f"Error: runtime context {args.subagent_id} already bound to {existing_key}",
            file=sys.stderr,
        )
        return 1
    context = bind_runtime_context(repo_root, args.subagent_id, args.context_key)
    if context is None:
        print(f"Error: cannot bind runtime context: {args.subagent_id}", file=sys.stderr)
        return 1
    _update_agent_run_if_present(repo_root, args.subagent_id, "bound")
    print(json.dumps(context, ensure_ascii=False, indent=2) + "\n", end="")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    if not close_runtime_context(repo_root, args.subagent_id):
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    _update_agent_run_if_present(repo_root, args.subagent_id, "closed")
    print(f"subagent {args.subagent_id} closed")
    return 0


def _update_agent_run_if_present(repo_root: Path, run_id: str, status: str) -> None:
    db_path = get_db_path(repo_root)
    if not db_path.exists():
        return
    try:
        with FlowStore(str(db_path)) as store:
            store.update_agent_run_status(run_id, status)
    except Exception:
        return

def _record_agent_run_for_task(
    repo_root: Path,
    *,
    runtime_context_id: str,
    task_dir: str | None,
    agent_type: str,
    dispatch_kind: str,
    host_context_key: str,
    created_at: str,
) -> None:
    if dispatch_kind != "formal" or not task_dir:
        return
    db_path = get_db_path(repo_root)
    if not db_path.exists():
        return
    with FlowStore(str(db_path)) as store:
        task = _resolve_flow_task(store, task_dir)
        if task is None:
            return
        store.create_agent_run(
            id=runtime_context_id,
            task_id=task.id,
            agent_type=agent_type,
            status="pending",
            host_context_key=host_context_key,
            created_at=created_at,
        )

def _resolve_flow_task(store: FlowStore, target: str):
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

def _child_task_dir(child) -> str:
    return f".cowork-flow/tasks/{child.artifact_dir}"

def cmd_spawn_family(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    agent_type = args.agent_type
    role = args.role or _role_for_agent_type(agent_type)
    results: list[dict] = []

    with FlowStore(str(get_db_path(repo_root))) as store:
        parent = _resolve_flow_task(store, args.parent_id)
        if parent is None:
            print(f"Error: parent task not found: {args.parent_id}", file=sys.stderr)
            return 1
        children = store.list_children(parent.id)
        for child in children:
            if child.status in DONE_TASK_STATUSES:
                results.append(
                    {
                        "task_id": child.id,
                        "taskId": child.id,
                        "taskStatus": child.status,
                        "status": "skipped_done",
                    }
                )
                continue

            active_run = store.get_active_agent_run(child.id, agent_type)
            if active_run is not None:
                results.append(
                    {
                        "id": active_run["id"],
                        "runtimeContextId": active_run["id"],
                        "task_id": child.id,
                        "taskId": child.id,
                        "agentType": active_run["agent_type"],
                        "runStatus": active_run["status"],
                        "status": "already_running",
                        "hostContextKey": active_run.get("host_context_key"),
                    }
                )
                continue

            task_dir = _child_task_dir(child)
            try:
                payload = _create_runtime_context_payload(
                    repo_root,
                    title=f"{agent_type} {child.id}",
                    role=role,
                    agent_type=agent_type,
                    task_dir=task_dir,
                    source="spawn-family",
                    goal=args.goal or f"Execute child task {child.id}",
                    expected_output=args.expected_output,
                    allowed_context=[],
                    host=args.host,
                    adapter=args.adapter,
                    record_agent_run=False,
                )
            except ValueError as error:
                print(f"Error: {error}", file=sys.stderr)
                return 1

            store.create_agent_run(
                id=payload["runtimeContextId"],
                task_id=child.id,
                agent_type=agent_type,
                status="pending",
                host_context_key=payload["hostContextKey"],
                created_at=_now(),
            )
            payload.update(
                {
                    "task_id": child.id,
                    "taskId": child.id,
                    "taskStatus": child.status,
                    "status": "pending",
                }
            )
            results.append(payload)

    print(json.dumps(results, ensure_ascii=False))
    return 0

def cmd_check_family(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    pending: list[dict] = []
    done: list[dict] = []
    failed: list[dict] = []

    with FlowStore(str(get_db_path(repo_root))) as store:
        parent = _resolve_flow_task(store, args.parent_id)
        if parent is None:
            print(f"Error: parent task not found: {args.parent_id}", file=sys.stderr)
            return 1
        children = store.list_children(parent.id)
        runs_by_child: dict[str, dict] = {}
        for run in store.list_agent_runs_for_parent(parent.id):
            if args.agent_type and run["agent_type"] != args.agent_type:
                continue
            runs_by_child[run["task_id"]] = run

        for child in children:
            run = runs_by_child.get(child.id)
            if run is None:
                entry = {"task_id": child.id, "taskId": child.id, "taskStatus": child.status}
                if child.status in DONE_TASK_STATUSES:
                    done.append({**entry, "status": child.status})
                else:
                    pending.append({**entry, "status": "missing_run"})
                continue

            entry = {
                "id": run["id"],
                "runtimeContextId": run["id"],
                "task_id": child.id,
                "taskId": child.id,
                "agentType": run["agent_type"],
                "taskStatus": child.status,
                "status": run["status"],
                "hostContextKey": run.get("host_context_key"),
            }
            if run["status"] in FAILED_AGENT_RUN_STATUSES:
                failed.append(entry)
            elif run["status"] in DONE_AGENT_RUN_STATUSES or child.status in DONE_TASK_STATUSES:
                done.append(entry)
            else:
                pending.append(entry)

    payload = {
        "all_done": not pending and not failed,
        "pending": pending,
        "done": done,
        "failed": failed,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["all_done"] else 1

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
    init.add_argument("--host", default="codex")
    init.add_argument("--adapter", default="codex.spawn_agent")
    init.set_defaults(func=cmd_init)

    dispatch_codex = subparsers.add_parser(
        "dispatch-codex",
        help="Prepare a Codex spawn_agent payload with runtime-context binding",
    )
    dispatch_codex.add_argument("--title", required=True)
    dispatch_codex.add_argument("--role", required=True)
    dispatch_codex.add_argument("--agent-type", required=True, choices=sorted(FIXED_AGENT_TYPES))
    dispatch_codex.add_argument("--execution-task-dir", required=True)
    dispatch_codex.add_argument("--source", default="auto")
    dispatch_codex.add_argument("--goal")
    dispatch_codex.add_argument("--expected-output", default="Files changed, validation commands, and blockers.")
    dispatch_codex.add_argument("--allowed-context", action="append", default=[])
    dispatch_codex.add_argument("--fork-turns", default="none")
    dispatch_codex.set_defaults(func=cmd_dispatch_codex)

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

    spawn_family = subparsers.add_parser(
        "spawn-family",
        help="Create runtime contexts for child tasks of a parent task",
    )
    spawn_family.add_argument("parent_id")
    spawn_family.add_argument("--agent-type", default="cowork-implement", choices=sorted(FIXED_AGENT_TYPES))
    spawn_family.add_argument("--role")
    spawn_family.add_argument("--goal")
    spawn_family.add_argument("--expected-output", default="Files changed, validation commands, and blockers.")
    spawn_family.add_argument("--host", default="codex")
    spawn_family.add_argument("--adapter", default="codex.spawn_agent")
    spawn_family.set_defaults(func=cmd_spawn_family)

    check_family = subparsers.add_parser(
        "check-family",
        help="Check runtime completion for child tasks of a parent task",
    )
    check_family.add_argument("parent_id")
    check_family.add_argument("--agent-type")
    check_family.set_defaults(func=cmd_check_family)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
