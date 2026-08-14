#!/usr/bin/env python3
"""Task workflow navigation and deterministic action contract."""

from __future__ import annotations

import json
from pathlib import Path

from services.task_context import TaskContextService
from adapters.cli.task_support import resolve_task_dir
from adapters.cli.execution_context_args import execution_context_from_namespace
from infra.paths import get_repo_root
from runtime.session_state import get_active_task
from services.readiness import task_readiness_blockers
from services.task_repository import TaskRepository, TaskRepositoryError


from services.task_routing import _default_intent
from services.task_routing import route_request as _route_request


RECOVERABLE_TASK_STATUSES = {
    "in_progress": "active_unbound",
    "review": "active_unbound",
    "completed": "completed_unarchived",
}


def _default_action_command(
    task_path: str | None,
    *,
    create: bool = False,
) -> str:
    parts = ["./.cowork-flow/run", "task", "next"]
    if task_path:
        parts.append(task_path)
    parts.append("--run")
    if create:
        parts.extend([
            "--title",
            '"<title>"',
            "--slug",
            "<task-name>",
            "--assignee",
            "<name>",
        ])
    return " ".join(parts)


def _render_command(
    action_id: str,
    task_path: str | None,
    template: object,
    blockers: object,
) -> str | None:
    if isinstance(template, str) and template.strip():
        return template.replace("<task-dir>", task_path or "<task-dir>")
    if action_id == "edit_planning_artifacts":
        items = [str(item) for item in (blockers or [])]
        if items and all(item.startswith("planFile") for item in items):
            return (
                f"./.cowork-flow/run task next {task_path or '<task-dir>'}"
                " --run --from-plan <plan-file>"
            )
        return None
    if action_id in {"start_task", "implement_change"}:
        return _default_action_command(task_path)
    return None


def _render_diagnostics(task_path: str | None, template: object) -> str | None:
    if isinstance(template, str) and template.strip():
        return template.replace("<task-dir>", task_path or "<task-dir>")
    return None


def _render_adapter_commands(payload: dict[str, object], task_path: str | None) -> dict[str, object]:
    action = payload.get("action")
    if not isinstance(action, dict):
        return payload
    action_id = str(action.get("id"))
    command = _render_command(
        action_id,
        task_path,
        action.get("command"),
        action.get("blockers"),
    )
    diagnostics = _render_diagnostics(task_path, action.get("diagnosticsCommand"))
    action["command"] = command
    action["diagnosticsCommand"] = diagnostics
    payload["actionCommand"] = command
    payload["diagnosticsCommand"] = diagnostics
    return payload


def _attach_runtime_gate_alias(payload: dict[str, object]) -> dict[str, object]:
    lifecycle_check = payload.get("lifecycleCheck")
    payload["runtimeGate"] = lifecycle_check
    action = payload.get("action")
    if isinstance(action, dict):
        action["runtimeGate"] = action.get("lifecycleCheck")
    return payload


def route_request(
    status: str,
    intent: str,
    context: str,
    blockers: tuple[str, ...] | list[str],
    active_target: bool,
    task_path: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    payload = _route_request(
        status=status,
        intent=intent,
        context=context,
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
        repo_root=repo_root,
    )
    return _attach_runtime_gate_alias(_render_adapter_commands(payload, task_path))



def _display(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _status(repo_root: Path, task_dir: Path) -> str:
    try:
        data = TaskRepository(repo_root).load(task_dir)
    except TaskRepositoryError:
        return "stale"
    status = data.get("status")
    return status.strip() if isinstance(status, str) and status.strip() else "unknown"


def _blockers(repo_root: Path, task_dir: Path) -> list[str]:
    blockers = list(TaskContextService(repo_root).start_blockers(task_dir))
    blockers.extend(task_readiness_blockers(repo_root, task_dir))
    return blockers


def repository_recovery_signals(repo_root: Path) -> list[dict[str, str]]:
    tasks_dir = repo_root / ".cowork-flow" / "tasks"
    if not tasks_dir.is_dir():
        return []
    signals: list[dict[str, str]] = []
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir() or task_dir.name == "archive":
            continue
        status = _status(repo_root, task_dir)
        kind = RECOVERABLE_TASK_STATUSES.get(status)
        if kind is None:
            continue
        task = _display(repo_root, task_dir)
        hint = f"./.cowork-flow/run task next {task} --run"
        if kind == "completed_unarchived":
            hint = f"{hint} --intent archive"
        signals.append(
            {
                "kind": kind,
                "task": task,
                "status": status,
                "hint": hint,
            }
        )
    return signals


def _attach_recovery(payload: dict[str, object], repo_root: Path) -> dict[str, object]:
    signals = repository_recovery_signals(repo_root)
    if signals:
        payload["recovery"] = {
            "signals": signals,
            "listCommand": "./.cowork-flow/run task next --list --json",
        }
    return payload


def _add_read_first_entry(
    entries: list[dict[str, str]],
    seen: set[str],
    file_path: str,
    reason: str,
) -> None:
    normalized = file_path.replace("\\", "/").strip()
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    entry = {"file": normalized}
    if reason.strip():
        entry["reason"] = reason.strip()
    entries.append(entry)


def _attach_implement_read_first(
    payload: dict[str, object],
    repo_root: Path,
    task_path: str | None,
) -> dict[str, object]:
    action = payload.get("action")
    if not isinstance(action, dict) or action.get("id") != "implement_change":
        return payload
    if not task_path:
        return payload

    task_dir = repo_root / task_path
    if not task_dir.is_dir():
        return payload

    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    task_prefix = task_path.rstrip("/")
    _add_read_first_entry(
        entries,
        seen,
        f"{task_prefix}/decision-anchor.md",
        "Task decision anchor",
    )
    try:
        task_data = TaskRepository(repo_root).load(task_dir)
    except TaskRepositoryError:
        task_data = {}
    meta = task_data.get("meta") if isinstance(task_data, dict) else None
    plan_file = meta.get("planFile") if isinstance(meta, dict) else None
    if isinstance(plan_file, str):
        _add_read_first_entry(entries, seen, plan_file, "Linked implementation plan")
    _add_read_first_entry(
        entries,
        seen,
        f"{task_prefix}/implement.jsonl",
        "Implementation context index",
    )
    for context_entry in TaskContextService(repo_root).entries(task_dir, "implement"):
        file_value = context_entry.get("file")
        if not isinstance(file_value, str):
            continue
        reason = context_entry.get("reason")
        _add_read_first_entry(
            entries,
            seen,
            file_value,
            reason if isinstance(reason, str) else "Implementation context",
        )
    if entries:
        payload["readFirst"] = entries
    return payload


def _print_recovery(payload: dict[str, object]) -> None:
    recovery = payload.get("recovery")
    if not isinstance(recovery, dict):
        return
    signals = recovery.get("signals")
    if not isinstance(signals, list) or not signals:
        return
    print("Recovery:")
    for signal in signals:
        if isinstance(signal, dict):
            print(
                f"  - {signal.get('kind')}: {signal.get('task')} "
                f"({signal.get('status')})"
            )
            print(f"    Hint: {signal.get('hint')}")
    print(f"List: {recovery.get('listCommand')}")


def _print_blockers(blockers: list[str]) -> None:
    if not blockers:
        print("Blockers: none")
        return
    print("Blockers:")
    for blocker in blockers:
        print(f"  - {blocker}")


def _routing_context(args) -> str:
    execution_context = execution_context_from_namespace(args)
    if execution_context.is_worker or execution_context.is_subagent:
        return "delegated"
    return "main"


def build_navigation_payload(
    *,
    args,
    status: str,
    blockers: list[str],
    active_target: bool,
    task_path: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    intent = getattr(args, "intent", None) or _default_intent(
        status,
        blockers,
        active_target,
    )
    root = repo_root if repo_root is not None else get_repo_root()
    payload = route_request(
        status=status,
        intent=intent,
        context=_routing_context(args),
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
        repo_root=root,
    )
    return _attach_implement_read_first(payload, root, task_path)


def _print_json_route(
    *,
    args,
    status: str,
    blockers: list[str],
    active_target: bool,
    task_path: str | None = None,
    repo_root: Path | None = None,
) -> None:
    payload = build_navigation_payload(
        args=args,
        status=status,
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
        repo_root=repo_root,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=False))


def _print_text_payload(payload: dict[str, object]) -> None:
    action = payload["action"]
    if not isinstance(action, dict):
        raise TypeError("navigation payload action must be an object")
    print(f"Next action: {action['label']}")
    print(f"Skill: {action['activatedSkill'] or 'none'}")
    print(f"Command: {action['command'] or 'none'}")
    diagnostics_command = action.get("diagnosticsCommand")
    if diagnostics_command:
        print(f"Diagnostics: {diagnostics_command}")
    blockers = payload["blockers"]
    if not isinstance(blockers, list):
        raise TypeError("navigation payload blockers must be a list")
    _print_blockers([str(blocker) for blocker in blockers])


def _navigation_target(args, repo_root: Path, structured: bool):
    target = getattr(args, "dir", None)
    if target:
        task_dir = resolve_task_dir(target, repo_root)
        task_path = _display(repo_root, task_dir)
        return task_dir, task_path, "argument", False

    active = get_active_task(repo_root)
    source = f"{active.source}:{active.context_key or '-'}"
    if active.task_path:
        return repo_root / active.task_path, active.task_path, source, True
    if structured:
        payload = build_navigation_payload(
            args=args,
            status="no_task",
            blockers=[],
            active_target=False,
            task_path=None,
            repo_root=repo_root,
        )
        _attach_recovery(payload, repo_root)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=False))
    else:
        print("Status: no_task")
        print(f"Source: {source}")
        payload = build_navigation_payload(
            args=args,
            status="no_task",
            task_path=None,
            blockers=[],
            active_target=False,
            repo_root=repo_root,
        )
        _attach_recovery(payload, repo_root)
        _print_text_payload(payload)
        _print_recovery(payload)
    return None


def _print_stale_route(args, task_path: str, source: str, active_target: bool) -> None:
    blockers = [f"task directory not found: {task_path}"]
    if bool(getattr(args, "json", False)):
        _print_json_route(
            args=args,
            status="stale",
            blockers=blockers,
            active_target=active_target,
            task_path=task_path,
            repo_root=get_repo_root(),
        )
        return
    print("Status: stale")
    print(f"Source: {source}")
    payload = build_navigation_payload(
        args=args,
        status="stale",
        blockers=blockers,
        active_target=active_target,
        task_path=task_path,
    )
    _print_text_payload(payload)


def _print_text_route(
    args,
    task_path: str,
    status: str,
    source: str,
    blockers: list[str],
    active_target: bool,
) -> None:
    print(f"Status: {status}")
    print(f"Source: {source}")
    payload = build_navigation_payload(
        args=args,
        status=status,
        task_path=task_path,
        blockers=blockers,
        active_target=active_target,
        repo_root=get_repo_root(),
    )
    _print_text_payload(payload)


def cmd_next(args) -> int:
    repo_root = get_repo_root()
    structured = bool(getattr(args, "json", False))
    if not structured:
        print("Workflow Next")
    target = _navigation_target(args, repo_root, structured)
    if target is None:
        return 0
    task_dir, task_path, source, active_target = target

    if not structured:
        print(f"Task: {task_path}")
    if not task_dir.is_dir():
        _print_stale_route(args, task_path, source, active_target)
        return 0

    status = _status(repo_root, task_dir)
    blockers = _blockers(repo_root, task_dir) if status == "planning" else []
    if structured:
        _print_json_route(
            args=args,
            status=status,
            blockers=blockers,
            active_target=active_target,
            task_path=task_path,
            repo_root=repo_root,
        )
        return 0

    _print_text_route(
        args,
        task_path,
        status,
        source,
        blockers,
        active_target,
    )
    return 0
