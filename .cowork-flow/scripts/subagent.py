#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generic subagent scoped recovery state."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from common.execution_context import build_internal_execution_context_parser
from common.paths import DIR_WORKFLOW, get_repo_root

VALID_STATUSES = {"active", "success", "needs_context", "blocked"}
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


def _subagents_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / "subagents"


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_event(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _next_id(base_dir: Path, title: str) -> str:
    prefix = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{prefix}-{_slug(title)}"
    candidate = base
    counter = 2
    while (base_dir / candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _resolve_agent_type(role: str, agent_type: str | None) -> tuple[str, str]:
    normalized_role = role.strip()
    requested = agent_type.strip() if isinstance(agent_type, str) else ""
    if requested:
        if requested in FIXED_AGENT_TYPES:
            if normalized_role in FIXED_AGENT_TYPES and normalized_role != requested:
                raise ValueError(f"agent-type {requested} cannot use role {normalized_role}")
            if normalized_role in ROLE_AGENT_TYPE_ALIASES and ROLE_AGENT_TYPE_ALIASES[normalized_role] != requested:
                raise ValueError(f"agent-type {requested} cannot use role {normalized_role}")
            return requested, "fixed"
        if requested == GENERIC_AGENT_TYPE:
            if normalized_role in FIXED_AGENT_TYPES or normalized_role in ROLE_AGENT_TYPE_ALIASES:
                raise ValueError("agent-type worker requires non-fixed role")
            return requested, "best-effort"
        raise ValueError("agent-type must be cowork-research, cowork-implement, cowork-check, or worker")
    if normalized_role in FIXED_AGENT_TYPES:
        return normalized_role, "fixed"
    if normalized_role in ROLE_AGENT_TYPE_ALIASES:
        return ROLE_AGENT_TYPE_ALIASES[normalized_role], "fixed"
    return GENERIC_AGENT_TYPE, "best-effort"


def _build_dispatch_message(
    *,
    dispatch_id: str,
    agent_type: str,
    role: str,
    task_dir: str | None,
    context_file: Path,
    ack_token: str,
    dispatch_reliability: str,
) -> str:
    lines = [
        "COWORK_DISPATCH_V1",
        f"dispatch_id: {dispatch_id}",
        f"agent_type: {agent_type}",
    ]
    if task_dir:
        lines.append(f"task_dir: {task_dir}")
    lines.extend(
        [
            f"role: {role}",
            f"context_file: {_relative(get_repo_root(), context_file)}",
            f"ack_token: {ack_token}",
            f"dispatch_reliability: {dispatch_reliability}",
            "COWORK_DISPATCH_END",
            "",
            f"Return only: COWORK_ACK {dispatch_id} {ack_token}",
        ]
    )
    if dispatch_reliability == "best-effort":
        lines.insert(7, "This generic worker dispatch is best-effort only.")
    return "\n".join(lines)


def _build_execute_message(dispatch_id: str, goal: str, dispatch_reliability: str) -> str:
    lines = [
        f"EXECUTE {dispatch_id}",
        "",
        goal,
    ]
    if dispatch_reliability == "best-effort":
        lines.extend(
            [
                "",
                "Treat this as best-effort.",
            ]
        )
    return "\n".join(lines)


def cmd_init(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    base_dir = _subagents_dir(repo_root)
    subagent_id = _next_id(base_dir, args.title)
    subagent_dir = base_dir / subagent_id
    task_dir = getattr(args, "execution_task_dir", None)
    try:
        agent_type, dispatch_reliability = _resolve_agent_type(args.role, getattr(args, "agent_type", None))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if dispatch_reliability == "fixed" and not task_dir:
        print("Error: fixed agent dispatch requires --execution-task-dir", file=sys.stderr)
        return 1
    subagent_dir.mkdir(parents=True, exist_ok=False)
    dispatch_id = subagent_id
    ack_token = f"ACK:{dispatch_id}:{secrets.token_hex(8)}"
    allowed_context = [{"file": item, "reason": "prompt-named context"} for item in args.allowed_context]
    status_file = subagent_dir / "status.json"
    events_file = subagent_dir / "events.jsonl"
    brief_file = subagent_dir / "brief.md"
    context_file = subagent_dir / "context.json"
    expected_ack = f"COWORK_ACK {dispatch_id} {ack_token}"
    dispatch_message = _build_dispatch_message(
        dispatch_id=dispatch_id,
        agent_type=agent_type,
        role=args.role,
        task_dir=task_dir,
        context_file=context_file,
        ack_token=ack_token,
        dispatch_reliability=dispatch_reliability,
    )
    execute_message = _build_execute_message(dispatch_id, args.goal or args.title, dispatch_reliability)

    brief_file.write_text(
        "\n".join(
            [
                dispatch_message,
                "",
                f"Do not execute the task until the coordinator sends EXECUTE {dispatch_id}.",
                "",
                f"# {args.title}",
                "",
                f"Role: {args.role}",
                f"Agent type: {agent_type}",
                f"Task directory: {task_dir or 'unknown'}",
                f"Dispatch reliability: {dispatch_reliability}",
                f"Source: {args.source}",
                "",
                "## Goal",
                "",
                args.goal or args.title,
                "",
                "## Scope Rules",
                "",
                "- Read only prompt-named files and allowed context unless more context is requested.",
                "- Do not run main-session start/resume or coordinator mutation commands.",
                "- Stop with success, needs_context, or blocked evidence.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    status = {
        "id": subagent_id,
        "status": "active",
        "title": args.title,
        "role": args.role,
        "agentType": agent_type,
        "taskDir": task_dir,
        "dispatchReliability": dispatch_reliability,
        "source": args.source,
        "goal": args.goal or args.title,
        "updatedAt": _now(),
        "note": "initialized",
        "dispatchId": dispatch_id,
        "dispatchStatus": "planned",
        "ackToken": ack_token,
        "expectedAck": expected_ack,
        "dispatchMessage": dispatch_message,
        "executeMessage": execute_message,
    }
    _write_json(status_file, status)
    context = {
        "mode": "subagent",
        "kind": "generic-subagent",
        "id": subagent_id,
        "agentType": agent_type,
        "taskDir": task_dir,
        "dispatchReliability": dispatch_reliability,
        "dispatchId": dispatch_id,
        "ackToken": ack_token,
        "expectedAck": expected_ack,
        "dispatchMessage": dispatch_message,
        "executeMessage": execute_message,
        "dispatchStatus": "planned",
        "title": args.title,
        "role": args.role,
        "source": args.source,
        "goal": args.goal or args.title,
        "allowedContext": allowed_context,
        "forbiddenActions": [
            "full-start",
            "unscoped-resume",
            "task-start",
            "task-finish",
            "task-archive",
            "spawn-agent",
        ],
        "briefFile": _relative(repo_root, brief_file),
        "statusFile": _relative(repo_root, status_file),
        "eventsFile": _relative(repo_root, events_file),
    }
    _write_json(context_file, context)
    _append_event(events_file, {"time": _now(), "event": "init", "status": "active", "title": args.title})

    index_path = base_dir / "index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {"subagents": []}
    else:
        index = {"subagents": []}
    subagents = index.setdefault("subagents", [])
    if isinstance(subagents, list):
        subagents.append(
            {
                "id": subagent_id,
                "dispatchId": dispatch_id,
                "agentType": agent_type,
                "taskDir": task_dir,
                "title": args.title,
                "contextFile": _relative(repo_root, context_file),
                "status": "active",
                "dispatchStatus": "planned",
                "dispatchReliability": dispatch_reliability,
            }
        )
    _write_json(index_path, index)

    print(
        json.dumps(
                {
                    "id": subagent_id,
                    "agentType": agent_type,
                    "taskDir": task_dir,
                    "dispatchReliability": dispatch_reliability,
                    "dispatchId": dispatch_id,
                    "ackToken": ack_token,
                    "expectedAck": expected_ack,
                    "dispatchMessage": dispatch_message,
                    "executeMessage": execute_message,
                    "contextFile": _relative(repo_root, context_file),
                },
                ensure_ascii=False,
            )
        )
    return 0


def _find_subagent(repo_root: Path, subagent_id: str) -> Path:
    path = _subagents_dir(repo_root) / subagent_id
    if not path.is_dir():
        raise FileNotFoundError(subagent_id)
    return path


def cmd_status(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    try:
        subagent_dir = _find_subagent(repo_root, args.subagent_id)
    except FileNotFoundError:
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    status_file = subagent_dir / "status.json"
    print(status_file.read_text(encoding="utf-8"), end="")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    if args.status not in VALID_STATUSES:
        print(f"Error: status must be one of {', '.join(sorted(VALID_STATUSES))}", file=sys.stderr)
        return 1
    repo_root = get_repo_root()
    try:
        subagent_dir = _find_subagent(repo_root, args.subagent_id)
    except FileNotFoundError:
        print(f"Error: subagent not found: {args.subagent_id}", file=sys.stderr)
        return 1
    status_file = subagent_dir / "status.json"
    status = json.loads(status_file.read_text(encoding="utf-8"))
    status["status"] = args.status
    status["updatedAt"] = _now()
    if args.note:
        status["note"] = args.note
    _write_json(status_file, status)
    _append_event(subagent_dir / "events.jsonl", {"time": _now(), "event": "update", "status": args.status, "note": args.note})
    print(f"subagent {args.subagent_id} status={args.status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generic subagent scoped recovery",
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create generic subagent context")
    init.add_argument("--title", required=True)
    init.add_argument("--role", default="subagent")
    init.add_argument("--agent-type")
    init.add_argument("--source", default="auto")
    init.add_argument("--goal")
    init.add_argument("--allowed-context", action="append", default=[])
    init.set_defaults(func=cmd_init)

    status = subparsers.add_parser("status", help="Print subagent status")
    status.add_argument("subagent_id")
    status.set_defaults(func=cmd_status)

    update = subparsers.add_parser("update", help="Update subagent status")
    update.add_argument("subagent_id")
    update.add_argument("--status", required=True)
    update.add_argument("--note")
    update.set_defaults(func=cmd_update)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
