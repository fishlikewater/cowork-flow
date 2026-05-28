#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent team runtime commands for cowork-flow."""

from __future__ import annotations

import argparse
import os
import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from common.agent_team import (
    build_adapter_payload,
    build_dispatch_plan,
    build_initial_metrics,
    build_initial_status,
    parse_plan,
    load_agent_registry,
    render_assignment_prompt,
    render_dispatch_plan,
    write_json,
)
from common.config import get_agent_team_enabled
from common.execution_context import (
    build_internal_execution_context_parser,
    execution_context_from_namespace,
    worker_command_block_message,
)
from common.paths import DIR_WORKFLOW, get_repo_root


DEFAULT_CONFIGS = {
    "agents.yaml": """# Agent Team Registry
# Project teams may customize this file after initialization.

default_adapter: codex

agents:
  implementer:
    agent_type: worker
    capabilities:
      - implementation
      - test-writing
    preferred_task_types:
      - code
      - test
    file_patterns:
      - "src/**"
      - "template/**"
      - "tests/**"
      - "test/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Implement the smallest change that satisfies the approved plan and tests.
      Write or update focused regression tests first, keep edits scoped, and report exact verification commands.

  tester:
    agent_type: worker
    capabilities:
      - test-writing
      - verification
    preferred_task_types:
      - test
      - verification
    file_patterns:
      - "tests/**"
      - "test/**"
      - "src/**"
      - "template/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Design tests that fail for the broken behavior and pass for the intended behavior.
      Prefer clear behavior assertions over implementation details, and include the command that proves the result.

  debugger:
    agent_type: worker
    capabilities:
      - debugging
      - implementation
      - verification
    preferred_task_types:
      - bugfix
      - code
    file_patterns:
      - "src/**"
      - "template/**"
      - "tests/**"
      - "test/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Find the root cause before changing code. Reproduce the failure, compare with nearby working patterns,
      then make the smallest fix and verify the original symptom.

  spec-reviewer:
    agent_type: worker
    capabilities:
      - spec-review
      - acceptance-check
    preferred_task_types:
      - review
      - documentation
    file_patterns:
      - ".cowork-flow/changes/**"
      - ".cowork-flow/plans/**"
      - "README.md"
      - "template/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Review the proposal, spec, plan, and task PRD for contradictions, missing acceptance criteria,
      unclear scope, and behavior that is not covered by verification.

  quality-reviewer:
    agent_type: worker
    capabilities:
      - code-quality-review
      - test-review
      - verification
    preferred_task_types:
      - review
      - verification
    file_patterns:
      - "src/**"
      - "template/**"
      - "tests/**"
      - "test/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Review the diff for correctness, maintainability, focused scope, and meaningful tests.
      Check that verification evidence matches the behavior being claimed.

  docs-agent:
    agent_type: worker
    capabilities:
      - documentation
      - workflow-writing
    preferred_task_types:
      - docs
      - documentation
    file_patterns:
      - "README.md"
      - "AGENTS.md"
      - ".cowork-flow/**/*.md"
      - ".agent/skills/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Write concise project documentation that reflects actual commands, files, and workflow behavior.
      Avoid aspirational text that is not backed by the implementation.

  release-reviewer:
    agent_type: default
    capabilities:
      - release-review
      - acceptance-check
      - verification
    preferred_task_types:
      - release
      - review
    file_patterns:
      - "package.json"
      - "package-lock.json"
      - "scripts/**"
      - "README.md"
      - ".cowork-flow/changes/**"
    risk_limits:
      max_parallel_write_conflicts: 0
    prompt: |
      Review release-facing changes for versioning, packaging, documentation, and command safety.
      Confirm that generated artifacts and publish steps are intentional.
""",
    "adapters.yaml": """# Agent Team Adapters

default: codex
fallback: manual

adapters:
  codex:
    mode: coordinator-dispatched
    description: 主 agent 使用 Codex 子 agent 工具执行脚本生成的 assignments。
    output_file: adapters/codex.json

  manual:
    mode: prompt-only
    description: 生成可复制的 assignment prompt，由人或其他宿主执行并回写结果。
    output_file: adapters/manual.json
""",
    "policy.yaml": """# Agent Team Policy

parallel:
  allow_parallel_batches: true
  disallow_file_write_conflicts: true
  require_coordinator_review: true

reviews:
  require_spec_review: true
  require_quality_review: true
  chain:
    - implementer
    - spec-reviewer
    - quality-reviewer

retry:
  max_attempts: 3
  retry_on:
    - needs_context
    - failed_verification
    - review_rejected
    - adapter_failed
  escalation: needs-coordinator-decision
""",
}

TERMINAL_STATUSES = {"done", "approved"}
RESULT_STATUSES = {"blocked", "done", "done_with_concerns", "needs_context"}
REVIEW_STATUSES = {"approved", "blocked", "changes_requested", "needs_context"}
REVIEW_ROLES = {"spec-reviewer", "quality-reviewer"}
MAX_ATTEMPTS = 3
LOCK_TIMEOUT_SECONDS = 10
LOCK_POLL_SECONDS = 0.05
GATED_COMMANDS = {
    "prepare",
    "status",
    "next",
    "record-spawn",
    "record-result",
    "record-review",
    "worker-report",
    "collect",
    "retry",
    "complete",
}
WORKER_ALLOWED_COMMANDS = {"worker-report"}
COORDINATOR_REQUIRED_COMMANDS = {
    "next",
    "record-spawn",
    "record-result",
    "record-review",
    "collect",
    "retry",
    "complete",
}
COORDINATOR_CAPABILITIES = [f"agent-team:{command}" for command in sorted(COORDINATOR_REQUIRED_COMMANDS)]


def _agent_team_config_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / "agent-team"


def _write_default_if_missing(path: Path, content: str) -> str:
    if path.exists():
        return "preserved"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "created"


def _resolve_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def _task_ready(task_dir: Path) -> list[str]:
    missing = []
    for name in ("prd.md", "implement.jsonl", "check.jsonl", "debug.jsonl"):
        path = task_dir / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            missing.append(name)
    return missing


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _task_context_entries(task_dir: Path, task_dir_relative: str) -> list[dict[str, str]]:
    entries = [
        {"file": f"{task_dir_relative}/prd.md", "reason": "Task PRD"},
        {"file": f"{task_dir_relative}/implement.jsonl", "reason": "Task implementation context index"},
        {"file": f"{task_dir_relative}/check.jsonl", "reason": "Task check context index"},
        {"file": f"{task_dir_relative}/debug.jsonl", "reason": "Task debug context index"},
    ]
    seen = {entry["file"] for entry in entries}
    for name, label in (
        ("implement.jsonl", "implement context"),
        ("check.jsonl", "check context"),
        ("debug.jsonl", "debug context"),
    ):
        context_index = task_dir / name
        if not context_index.is_file():
            continue
        for raw_line in context_index.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            file_value = item.get("file") if isinstance(item, dict) else None
            if not isinstance(file_value, str) or not file_value.strip():
                continue
            file_path = file_value.strip()
            if file_path in seen:
                continue
            seen.add(file_path)
            reason = item.get("reason") if isinstance(item.get("reason"), str) else file_path
            entries.append({"file": file_path, "reason": f"{label}: {reason}"})
    return entries


def _runtime_dir(task_dir: Path) -> Path:
    return task_dir / "agent-team"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


class AgentTeamLockTimeout(TimeoutError):
    pass


@contextmanager
def _agent_team_state_lock(task_dir: Path):
    lock_dir = _runtime_dir(task_dir) / ".state.lock"
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_dir.mkdir()
            break
        except FileExistsError as error:
            if time.monotonic() >= deadline:
                raise AgentTeamLockTimeout(f"timed out waiting for agent-team state lock: {lock_dir}") from error
            time.sleep(LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        try:
            lock_dir.rmdir()
        except FileNotFoundError:
            pass


def _lock_error(error: AgentTeamLockTimeout) -> int:
    print(f"Error: {error}", file=sys.stderr)
    return 1


def _load_status(task_dir: Path) -> dict[str, object]:
    status_path = _runtime_dir(task_dir) / "status.json"
    if not status_path.is_file():
        raise FileNotFoundError(f"agent-team status not found: {status_path}")
    return _load_json(status_path)


def _load_metrics(task_dir: Path) -> dict[str, object]:
    metrics_path = _runtime_dir(task_dir) / "metrics.json"
    if not metrics_path.is_file():
        raise FileNotFoundError(f"agent-team metrics not found: {metrics_path}")
    return _load_json(metrics_path)


def _unlock_ready_assignments(status_data: dict[str, object]) -> None:
    assignments = status_data["assignments"]
    for assignment in assignments.values():
        if assignment.get("status") != "pending":
            continue
        depends_on = assignment.get("depends_on", [])
        if all(assignments[dependency]["status"] in TERMINAL_STATUSES for dependency in depends_on):
            assignment["status"] = "ready"


def _copy_payload(source: str | None, destination_dir: Path, assignment_id: str, attempt: int) -> None:
    if not source:
        return
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"payload file not found: {source}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_dir / f"{assignment_id}-attempt-{attempt}.json")


def _write_payload(payload: object, destination_dir: Path, assignment_id: str, attempt: int) -> None:
    if payload is None:
        return
    destination_dir.mkdir(parents=True, exist_ok=True)
    (destination_dir / f"{assignment_id}-attempt-{attempt}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _status_error(command: str, allowed: set[str]) -> str:
    return f"{command} status must be one of: {', '.join(sorted(allowed))}"


def _validate_status(command: str, status: str, allowed: set[str]) -> bool:
    if status in allowed:
        return True
    print(f"Error: {_status_error(command, allowed)}", file=sys.stderr)
    return False


def _read_payload_file(payload_file: str) -> tuple[bool, object | None]:
    path = Path(payload_file)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: payload file not found: {payload_file}", file=sys.stderr)
        return False, None
    except json.JSONDecodeError:
        print(f"Error: payload file is not valid JSON: {payload_file}", file=sys.stderr)
        return False, None
    except OSError as error:
        print(f"Error: failed to read payload file: {error}", file=sys.stderr)
        return False, None
    return True, payload


def _validate_approved_review_payload_data(payload: object) -> bool:
    if not isinstance(payload, dict):
        print("Error: approved review payload must be a JSON object", file=sys.stderr)
        return False

    decision = payload.get("decision")
    status = payload.get("status")
    if decision == "approved" or status == "approved":
        return True

    print(
        "Error: approved review payload must include decision=approved or status=approved",
        file=sys.stderr,
    )
    return False


def _validate_approved_review_payload(payload_file: str | None) -> bool:
    if not payload_file:
        print("Error: approved review requires --file with a JSON review payload", file=sys.stderr)
        return False

    ok, payload = _read_payload_file(payload_file)
    if not ok:
        return False
    return _validate_approved_review_payload_data(payload)


def _role_statuses(role: str) -> set[str]:
    return REVIEW_STATUSES if role in REVIEW_ROLES else RESULT_STATUSES


def _outbox_file(task_dir: Path, assignment_id: str) -> Path:
    return _runtime_dir(task_dir) / "outbox" / f"{assignment_id}.json"


def _assignment_display_label(assignment_id: str, assignment: dict[str, object]) -> str:
    nickname = assignment.get("spawn_nickname")
    if isinstance(nickname, str) and nickname.strip():
        return nickname.strip()
    task_name = assignment.get("spawn_task_name")
    if isinstance(task_name, str) and task_name.strip():
        return task_name.strip()
    return assignment_id


def _record_assignment(
    task_dir: Path,
    assignment_id: str,
    status: str,
    payload_file: str | None,
    *,
    review: bool,
    payload_data: object | None = None,
    verb: str = "recorded",
) -> int:
    try:
        with _agent_team_state_lock(task_dir):
            return _record_assignment_unlocked(
                task_dir,
                assignment_id,
                status,
                payload_file,
                review=review,
                payload_data=payload_data,
                verb=verb,
            )
    except AgentTeamLockTimeout as error:
        return _lock_error(error)


def _record_assignment_unlocked(
    task_dir: Path,
    assignment_id: str,
    status: str,
    payload_file: str | None,
    *,
    review: bool,
    payload_data: object | None = None,
    verb: str = "recorded",
) -> int:
    status_data = _load_status(task_dir)
    metrics = _load_metrics(task_dir)
    assignments = status_data["assignments"]
    if assignment_id not in assignments:
        print(f"Error: assignment not found: {assignment_id}", file=sys.stderr)
        return 1

    assignment = assignments[assignment_id]
    assignment["attempts"] = int(assignment.get("attempts", 0)) + 1
    assignment["status"] = status
    attempt = int(assignment["attempts"])

    destination = _runtime_dir(task_dir) / ("reviews" if review else "results")
    if payload_data is None:
        _copy_payload(payload_file, destination, assignment_id, attempt)
    else:
        _write_payload(payload_data, destination, assignment_id, attempt)

    metrics["attempts"] = int(metrics.get("attempts", 0)) + 1
    if status in TERMINAL_STATUSES:
        metrics["successfulAssignments"] = int(metrics.get("successfulAssignments", 0)) + 1
    else:
        metrics["failedAssignments"] = int(metrics.get("failedAssignments", 0)) + 1
        if review:
            metrics["reviewReworks"] = int(metrics.get("reviewReworks", 0)) + 1

    _unlock_ready_assignments(status_data)
    _save_json(_runtime_dir(task_dir) / "status.json", status_data)
    _save_json(_runtime_dir(task_dir) / "metrics.json", metrics)
    print(f"{verb} {assignment_id} status={status} attempt={attempt}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    config_dir = _agent_team_config_dir(repo_root)
    outcomes = {
        name: _write_default_if_missing(config_dir / name, content)
        for name, content in DEFAULT_CONFIGS.items()
    }
    created = sum(1 for outcome in outcomes.values() if outcome == "created")
    preserved = sum(1 for outcome in outcomes.values() if outcome == "preserved")
    print(f"initialized agent-team config created={created} preserved={preserved}")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    task_dir = _resolve_path(repo_root, args.task_dir)
    plan_file = _resolve_path(repo_root, args.plan)

    if not task_dir.is_dir():
        print(f"Error: task directory not found: {task_dir}", file=sys.stderr)
        return 1
    if not plan_file.is_file():
        print(f"Error: plan file not found: {plan_file}", file=sys.stderr)
        return 1

    missing = _task_ready(task_dir)
    if missing:
        print(f"Error: task context is incomplete: {', '.join(missing)}", file=sys.stderr)
        return 1

    tasks = parse_plan(plan_file.read_text(encoding="utf-8"))
    if not tasks:
        print(f"Error: unable to parse plan tasks from: {plan_file}", file=sys.stderr)
        return 1

    runtime_dir = task_dir / "agent-team"
    assignments_dir = runtime_dir / "assignments"
    adapters_dir = runtime_dir / "adapters"
    for directory in (
        runtime_dir,
        assignments_dir,
        runtime_dir / "results",
        runtime_dir / "reviews",
        runtime_dir / "outbox",
        runtime_dir / "blockers",
        adapters_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    registry = load_agent_registry(_agent_team_config_dir(repo_root) / "agents.yaml")
    dispatch_plan = build_dispatch_plan(tasks, registry)
    task_dir_relative = _relative_to_repo(repo_root, task_dir)
    allowed_context = _task_context_entries(task_dir, task_dir_relative)
    for assignment in dispatch_plan["assignments"]:
        assignment_id = str(assignment["id"])
        assignment["worker_context_file"] = (
            f"{task_dir_relative}/agent-team/assignments/{assignment_id}.context.json"
        )
        assignment["worker_prompt_file"] = (
            f"{task_dir_relative}/agent-team/assignments/{assignment_id}.md"
        )
    (runtime_dir / "dispatch-plan.yaml").write_text(
        render_dispatch_plan(dispatch_plan),
        encoding="utf-8",
    )
    write_json(runtime_dir / "status.json", build_initial_status(dispatch_plan))
    write_json(runtime_dir / "metrics.json", build_initial_metrics(dispatch_plan))
    write_json(
        runtime_dir / "coordinator.context.json",
        {
            "mode": "coordinator",
            "kind": "agent-team-coordinator",
            "taskDir": task_dir_relative,
            "capabilities": COORDINATOR_CAPABILITIES,
        },
    )
    write_json(adapters_dir / f"{dispatch_plan['adapter']}.json", build_adapter_payload(dispatch_plan))

    for assignment in dispatch_plan["assignments"]:
        prompt_path = assignments_dir / f"{assignment['id']}.md"
        context_path = assignments_dir / f"{assignment['id']}.context.json"
        prompt_path.write_text(render_assignment_prompt(assignment), encoding="utf-8")
        worker_forbidden = [
            "full-start",
            "unscoped-resume",
            "task-start",
            "agent-team:next",
            "agent-team:collect",
            "agent-team:retry",
            "agent-team:complete",
        ]
        write_json(
            context_path,
            {
                "version": 1,
                "mode": "worker",
                "taskDir": task_dir_relative,
                "assignment": assignment["id"],
                "promptFile": assignment["worker_prompt_file"],
                "allowedContext": allowed_context,
                "forbiddenActions": worker_forbidden,
            },
        )

    print(f"prepared agent-team runtime assignments={len(dispatch_plan['assignments'])}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        status_data = _load_status(task_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for assignment in status_data["assignments"].values():
        assignment_status = assignment.get("status", "unknown")
        counts[assignment_status] = counts.get(assignment_status, 0) + 1

    for status_name in sorted(counts):
        print(f"{status_name}: {counts[status_name]}")
    if getattr(args, "verbose", False):
        for assignment_id in sorted(status_data["assignments"]):
            assignment = status_data["assignments"][assignment_id]
            display_label = _assignment_display_label(assignment_id, assignment)
            parts = [
                assignment_id,
                f"status={assignment.get('status', 'unknown')}",
                f"role={assignment.get('role', 'unknown')}",
                f"label={display_label}",
            ]
            spawn_task_name = assignment.get("spawn_task_name")
            if isinstance(spawn_task_name, str) and spawn_task_name.strip():
                parts.append(f"task_name={spawn_task_name.strip()}")
            spawn_nickname = assignment.get("spawn_nickname")
            if isinstance(spawn_nickname, str) and spawn_nickname.strip():
                parts.append(f"nickname={spawn_nickname.strip()}")
            print("\t".join(parts))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        status_data = _load_status(task_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    ready = [
        (assignment_id, assignment)
        for assignment_id, assignment in status_data["assignments"].items()
        if assignment.get("status") == "ready"
    ]
    if not ready:
        print("No ready assignments")
        return 0

    for assignment_id, assignment in ready:
        print(
            f"{assignment_id}\trole={assignment['role']}\t"
            f"agent={assignment['recommended_agent']}\tagent_type={assignment['agent_type']}"
        )
    return 0


def cmd_record_spawn(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        with _agent_team_state_lock(task_dir):
            status_data = _load_status(task_dir)
            assignments = status_data["assignments"]
            if args.assignment not in assignments:
                print(f"Error: assignment not found: {args.assignment}", file=sys.stderr)
                return 1

            assignment = assignments[args.assignment]
            if assignment.get("status") != "ready":
                print(
                    f"Error: assignment is not ready: {args.assignment} status={assignment.get('status', 'unknown')}",
                    file=sys.stderr,
                )
                return 1

            assignment["status"] = "in_progress"
            assignment["spawn_task_name"] = args.task_name
            assignment["spawn_nickname"] = args.nickname.strip() if args.nickname else None
            _save_json(_runtime_dir(task_dir) / "status.json", status_data)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except AgentTeamLockTimeout as error:
        return _lock_error(error)

    label = _assignment_display_label(args.assignment, assignment)
    print(
        f"recorded spawn {args.assignment} task_name={args.task_name} label={label}"
    )
    return 0


def cmd_record_result(args: argparse.Namespace) -> int:
    if not _validate_status("record-result", args.status, RESULT_STATUSES):
        return 1
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        return _record_assignment(task_dir, args.assignment, args.status, args.file, review=False)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def cmd_record_review(args: argparse.Namespace) -> int:
    if not _validate_status("record-review", args.status, REVIEW_STATUSES):
        return 1
    if args.status == "approved" and not _validate_approved_review_payload(args.file):
        return 1
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        return _record_assignment(task_dir, args.assignment, args.status, args.file, review=True)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def cmd_worker_report(args: argparse.Namespace) -> int:
    execution_context = execution_context_from_namespace(args)
    if not execution_context.is_worker:
        print("Error: worker-report requires worker execution context", file=sys.stderr)
        return 2

    context_assignment = execution_context.assignment
    assignment_id = args.assignment or context_assignment
    if assignment_id != context_assignment:
        print("Error: worker-report assignment must match worker context", file=sys.stderr)
        return 1
    if not execution_context.task_dir or not assignment_id:
        print("Error: worker-report requires task dir and assignment context", file=sys.stderr)
        return 2

    task_dir = _resolve_path(get_repo_root(), execution_context.task_dir)
    try:
        status_data = _load_status(task_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    assignments = status_data["assignments"]
    if assignment_id not in assignments:
        print(f"Error: assignment not found: {assignment_id}", file=sys.stderr)
        return 1

    assignment = assignments[assignment_id]
    if assignment.get("status") not in {"ready", "in_progress"}:
        print(
            f"Error: assignment is not ready or in_progress: {assignment_id} status={assignment.get('status', 'unknown')}",
            file=sys.stderr,
        )
        return 1

    role = str(assignment.get("role", ""))
    if not _validate_status("worker-report", args.status, _role_statuses(role)):
        return 1

    if role in REVIEW_ROLES and args.status == "approved" and not args.file:
        print("Error: approved review requires --file with a JSON review payload", file=sys.stderr)
        return 1

    payload: object | None = None
    if args.file:
        ok, payload = _read_payload_file(args.file)
        if not ok:
            return 1
    if role in REVIEW_ROLES and args.status == "approved" and not _validate_approved_review_payload_data(payload):
        return 1

    report = {
        "version": 1,
        "source": "worker-report",
        "assignment": assignment_id,
        "role": role,
        "status": args.status,
        "payload": payload,
    }
    outbox = _outbox_file(task_dir, assignment_id)
    outbox.parent.mkdir(parents=True, exist_ok=True)
    _save_json(outbox, report)
    print(f"worker report saved {assignment_id} status={args.status}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        with _agent_team_state_lock(task_dir):
            status_data = _load_status(task_dir)
            assignments = status_data["assignments"]
            if args.assignment not in assignments:
                print(f"Error: assignment not found: {args.assignment}", file=sys.stderr)
                return 1

            outbox = _outbox_file(task_dir, args.assignment)
            if not outbox.is_file():
                print(f"Error: worker report not found: {outbox}", file=sys.stderr)
                return 1

            try:
                report = _load_json(outbox)
            except json.JSONDecodeError:
                print(f"Error: worker report is not valid JSON: {outbox}", file=sys.stderr)
                return 1

            if report.get("assignment") != args.assignment:
                print("Error: worker report assignment does not match requested assignment", file=sys.stderr)
                return 1

            assignment = assignments[args.assignment]
            if assignment.get("status") not in {"ready", "in_progress"}:
                print(
                    f"Error: assignment is not ready or in_progress: {args.assignment} status={assignment.get('status', 'unknown')}",
                    file=sys.stderr,
                )
                return 1

            role = str(assignment.get("role", ""))
            if report.get("role") != role:
                print("Error: worker report role does not match assignment role", file=sys.stderr)
                return 1

            status = report.get("status")
            if not isinstance(status, str) or not _validate_status("collect", status, _role_statuses(role)):
                return 1

            payload = report.get("payload")
            if role in REVIEW_ROLES and status == "approved" and not _validate_approved_review_payload_data(payload):
                return 1

            return _record_assignment_unlocked(
                task_dir,
                args.assignment,
                status,
                None,
                review=role in REVIEW_ROLES,
                payload_data=payload,
                verb="collected",
            )
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except AgentTeamLockTimeout as error:
        return _lock_error(error)


def cmd_retry(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        with _agent_team_state_lock(task_dir):
            status_data = _load_status(task_dir)
            metrics = _load_metrics(task_dir)
            assignments = status_data["assignments"]
            if args.assignment not in assignments:
                print(f"Error: assignment not found: {args.assignment}", file=sys.stderr)
                return 1

            assignment = assignments[args.assignment]
            assignment["attempts"] = int(assignment.get("attempts", 0)) + 1
            assignment["last_retry_reason"] = args.reason
            if int(assignment["attempts"]) >= MAX_ATTEMPTS:
                assignment["status"] = "needs-coordinator-decision"
            else:
                assignment["status"] = "ready"

            metrics["attempts"] = int(metrics.get("attempts", 0)) + 1
            metrics["failedAssignments"] = int(metrics.get("failedAssignments", 0)) + 1
            _save_json(_runtime_dir(task_dir) / "status.json", status_data)
            _save_json(_runtime_dir(task_dir) / "metrics.json", metrics)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except AgentTeamLockTimeout as error:
        return _lock_error(error)
    print(f"retry recorded {args.assignment} attempt={assignment['attempts']}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        status_data = _load_status(task_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    pending = [
        assignment_id
        for assignment_id, assignment in status_data["assignments"].items()
        if assignment.get("status") not in TERMINAL_STATUSES
    ]
    if pending:
        print(f"Error: pending assignments: {', '.join(pending)}", file=sys.stderr)
        return 1

    print("agent team complete")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Cowork Flow agent team runtime",
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize agent team configuration")
    init_parser.set_defaults(func=cmd_init)

    prepare_parser = subparsers.add_parser("prepare", help="Prepare agent team runtime from a plan")
    prepare_parser.add_argument("task_dir", help="Task directory")
    prepare_parser.add_argument("--plan", required=True, help="Implementation plan file")
    prepare_parser.set_defaults(func=cmd_prepare)

    status_parser = subparsers.add_parser("status", help="Show agent team status")
    status_parser.add_argument("task_dir", help="Task directory")
    status_parser.add_argument("--verbose", action="store_true", help="Show per-assignment details")
    status_parser.set_defaults(func=cmd_status)

    next_parser = subparsers.add_parser("next", help="Show ready assignments")
    next_parser.add_argument("task_dir", help="Task directory")
    next_parser.set_defaults(func=cmd_next)

    record_spawn_parser = subparsers.add_parser("record-spawn", help="Record spawned agent details")
    record_spawn_parser.add_argument("task_dir", help="Task directory")
    record_spawn_parser.add_argument("--assignment", required=True, help="Assignment id")
    record_spawn_parser.add_argument("--task-name", required=True, help="Canonical task_name returned by spawn_agent")
    record_spawn_parser.add_argument("--nickname", help="Host-provided nickname returned by spawn_agent")
    record_spawn_parser.set_defaults(func=cmd_record_spawn)

    record_result_parser = subparsers.add_parser("record-result", help="Record assignment result")
    record_result_parser.add_argument("task_dir", help="Task directory")
    record_result_parser.add_argument("--assignment", required=True, help="Assignment id")
    record_result_parser.add_argument("--status", required=True, help="Result status")
    record_result_parser.add_argument("--file", help="JSON payload file")
    record_result_parser.set_defaults(func=cmd_record_result)

    record_review_parser = subparsers.add_parser("record-review", help="Record assignment review")
    record_review_parser.add_argument("task_dir", help="Task directory")
    record_review_parser.add_argument("--assignment", required=True, help="Assignment id")
    record_review_parser.add_argument("--status", required=True, help="Review status")
    record_review_parser.add_argument("--file", help="JSON payload file")
    record_review_parser.set_defaults(func=cmd_record_review)

    worker_report_parser = subparsers.add_parser("worker-report", help="Write worker report to assignment outbox")
    worker_report_parser.add_argument("--assignment", help="Assignment id; defaults to worker context assignment")
    worker_report_parser.add_argument("--status", required=True, help="Worker report status")
    worker_report_parser.add_argument("--file", help="JSON payload file")
    worker_report_parser.set_defaults(func=cmd_worker_report)

    collect_parser = subparsers.add_parser("collect", help="Collect a worker outbox report")
    collect_parser.add_argument("task_dir", help="Task directory")
    collect_parser.add_argument("--assignment", required=True, help="Assignment id")
    collect_parser.set_defaults(func=cmd_collect)

    retry_parser = subparsers.add_parser("retry", help="Record assignment retry")
    retry_parser.add_argument("task_dir", help="Task directory")
    retry_parser.add_argument("--assignment", required=True, help="Assignment id")
    retry_parser.add_argument("--reason", required=True, help="Retry reason")
    retry_parser.set_defaults(func=cmd_retry)

    complete_parser = subparsers.add_parser("complete", help="Check whether agent team work is complete")
    complete_parser.add_argument("task_dir", help="Task directory")
    complete_parser.set_defaults(func=cmd_complete)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    execution_context = execution_context_from_namespace(args)
    if execution_context.is_worker and args.command not in WORKER_ALLOWED_COMMANDS:
        print(
            worker_command_block_message(
                execution_context,
                f"agent-team {args.command}",
                "Workers must not inspect or mutate agent-team coordinator state.",
            ),
            file=sys.stderr,
        )
        return 2
    if execution_context.is_subagent and args.command in COORDINATOR_REQUIRED_COMMANDS:
        print(
            f"Error: agent-team {args.command} requires coordinator execution context",
            file=sys.stderr,
        )
        return 2
    if args.command in COORDINATOR_REQUIRED_COMMANDS and not execution_context.is_coordinator:
        print(
            f"Error: agent-team {args.command} requires coordinator execution context",
            file=sys.stderr,
        )
        return 2
    if not execution_context.is_worker and args.command in WORKER_ALLOWED_COMMANDS:
        print("Error: worker-report requires worker execution context", file=sys.stderr)
        return 2
    if args.command in GATED_COMMANDS and not get_agent_team_enabled(get_repo_root()):
        print(
            "Error: agent-team is disabled. Set agent_team.enabled: true in .cowork-flow/config.yaml.",
            file=sys.stderr,
        )
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
