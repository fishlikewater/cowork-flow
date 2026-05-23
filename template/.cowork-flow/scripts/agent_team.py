#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent team runtime commands for cowork-flow."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from common.agent_team import (
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
    agent_type: default
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
    agent_type: default
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
MAX_ATTEMPTS = 3
GATED_COMMANDS = {
    "prepare",
    "status",
    "next",
    "record-result",
    "record-review",
    "retry",
    "complete",
}


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


def _runtime_dir(task_dir: Path) -> Path:
    return task_dir / "agent-team"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def _record_assignment(
    task_dir: Path,
    assignment_id: str,
    status: str,
    payload_file: str | None,
    *,
    review: bool,
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
    _copy_payload(payload_file, destination, assignment_id, attempt)

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
    print(f"recorded {assignment_id} status={status} attempt={attempt}")
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
        runtime_dir / "blockers",
        adapters_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    registry = load_agent_registry(_agent_team_config_dir(repo_root) / "agents.yaml")
    dispatch_plan = build_dispatch_plan(tasks, registry)
    (runtime_dir / "dispatch-plan.yaml").write_text(
        render_dispatch_plan(dispatch_plan),
        encoding="utf-8",
    )
    write_json(runtime_dir / "status.json", build_initial_status(dispatch_plan))
    write_json(runtime_dir / "metrics.json", build_initial_metrics(dispatch_plan))
    write_json(
        adapters_dir / f"{dispatch_plan['adapter']}.json",
        {
            "adapter": dispatch_plan["adapter"],
            "mode": "coordinator-dispatched",
            "assignmentCount": len(dispatch_plan["assignments"]),
        },
    )

    for assignment in dispatch_plan["assignments"]:
        prompt_path = assignments_dir / f"{assignment['id']}.md"
        prompt_path.write_text(render_assignment_prompt(assignment), encoding="utf-8")

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


def cmd_record_result(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        return _record_assignment(task_dir, args.assignment, args.status, args.file, review=False)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def cmd_record_review(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        return _record_assignment(task_dir, args.assignment, args.status, args.file, review=True)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def cmd_retry(args: argparse.Namespace) -> int:
    task_dir = _resolve_path(get_repo_root(), args.task_dir)
    try:
        status_data = _load_status(task_dir)
        metrics = _load_metrics(task_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

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
    parser = argparse.ArgumentParser(description="Manage Cowork Flow agent team runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize agent team configuration")
    init_parser.set_defaults(func=cmd_init)

    prepare_parser = subparsers.add_parser("prepare", help="Prepare agent team runtime from a plan")
    prepare_parser.add_argument("task_dir", help="Task directory")
    prepare_parser.add_argument("--plan", required=True, help="Implementation plan file")
    prepare_parser.set_defaults(func=cmd_prepare)

    status_parser = subparsers.add_parser("status", help="Show agent team status")
    status_parser.add_argument("task_dir", help="Task directory")
    status_parser.set_defaults(func=cmd_status)

    next_parser = subparsers.add_parser("next", help="Show ready assignments")
    next_parser.add_argument("task_dir", help="Task directory")
    next_parser.set_defaults(func=cmd_next)

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
    if args.command in GATED_COMMANDS and not get_agent_team_enabled(get_repo_root()):
        print(
            "Error: agent-team is disabled. Set agent_team.enabled: true in .cowork-flow/config.yaml.",
            file=sys.stderr,
        )
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
