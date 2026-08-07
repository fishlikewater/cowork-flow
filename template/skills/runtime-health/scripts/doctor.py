#!/usr/bin/env python3
"""Structured cowork-flow distribution and runtime health checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _add_runtime_scripts_path() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".cowork-flow" / "scripts"
        if candidate.is_dir():
            value = str(candidate)
            if value not in sys.path:
                sys.path.insert(0, value)
            return


_add_runtime_scripts_path()

from adapters.host.host_manifest import (
    HostManifestError,
    detect_installed_platforms,
    load_host_manifest,
    validate_host_assets,
)
from infra.paths import get_repo_root
from infra.skill_manifest import SkillManifestError, action_owners, load_skill_manifests
from infra.storage.operation_log import OperationLog
from infra.storage.state_store import DEFAULT_STALE_LOCK_SECONDS, StateStore


def _issue(
    *,
    code: str,
    severity: str,
    path: str,
    message: str,
    command_hint: str = "",
    contract: str,
    **extra: str,
) -> dict[str, str]:
    issue = {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "commandHint": command_hint,
        "contract": contract,
    }
    issue.update(extra)
    return issue


def _compare_file(
    left: Path,
    right: Path,
    errors: list[str],
    *,
    missing_left: str = "missing template asset",
    missing_right: str = "missing installed asset",
    drift: str = "distribution drift",
) -> None:
    if not left.is_file():
        errors.append(f"{missing_left}: {left}")
        return
    if not right.is_file():
        errors.append(f"{missing_right}: {right}")
        return
    if left.read_bytes() != right.read_bytes():
        errors.append(f"{drift}: {left} != {right}")


def _same_file(left: Path, right: Path, errors: list[str]) -> None:
    _compare_file(left, right, errors)


def _distribution_root(repo_root: Path) -> Path:
    template = repo_root / "template"
    if (
        (template / ".cowork-flow/spec/runtime/host-assets.json").is_file()
        and (template / ".cowork-flow/scripts/kernel/workflow_route.py").is_file()
        and (template / "skills").is_dir()
    ):
        return template
    return repo_root


def _host_errors(repo_root: Path) -> list[str]:
    distribution_root = _distribution_root(repo_root)
    if distribution_root != repo_root:
        return validate_host_assets(distribution_root)
    try:
        platform_ids = detect_installed_platforms(distribution_root)
    except HostManifestError as error:
        return [str(error)]
    if not platform_ids:
        return ["no installed host platform detected"]
    return validate_host_assets(distribution_root, platform_ids=platform_ids)


def _host_issue(error: str) -> dict[str, str]:
    path = ""
    if ":" in error:
        path = error.rsplit(":", 1)[-1].strip()
    lowered = error.lower()
    if "missing command target" in lowered:
        code = "HOST-ASSET-MISSING-COMMAND-TARGET"
    elif "missing command config" in lowered:
        code = "HOST-ASSET-MISSING-COMMAND-CONFIG"
    elif "invalid command config" in lowered:
        code = "HOST-ASSET-INVALID-COMMAND-CONFIG"
    elif "illegal capability" in lowered:
        code = "HOST-ASSET-ILLEGAL-CAPABILITY"
    elif "capability mismatch" in lowered:
        code = "HOST-ASSET-CAPABILITY-MISMATCH"
    elif "adapter host mismatch" in lowered:
        code = "HOST-ASSET-HOST-MISMATCH"
    elif "invalid adapter yaml" in lowered:
        code = "HOST-ASSET-INVALID-ADAPTER"
    else:
        code = "HOST-ASSET-VALIDATION-ERROR"
    return _issue(
        code=code,
        severity="error",
        path=path,
        message=error,
        contract="runtime-health:host-adapters",
    )


def _host_issues(repo_root: Path) -> list[dict[str, str]]:
    return [_host_issue(error) for error in _host_errors(repo_root)]


def _distribution_files(root: Path) -> tuple[Path, ...]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]
    return tuple(sorted(files))


def _source_checkout_protected_path(relative: Path) -> bool:
    value = relative.as_posix()
    if value in {".cowork-flow/config.yaml", ".cowork-flow/.developer"}:
        return True
    return value.startswith(".cowork-flow/tasks/") or value.startswith(
        ".cowork-flow/plans/"
    ) or value.startswith(".cowork-flow/.runtime/")


def _source_checkout_live_files(template: Path) -> tuple[Path, ...]:
    runtime_root = template / ".cowork-flow"
    return tuple(
        source
        for source in _distribution_files(runtime_root)
        if not _source_checkout_protected_path(source.relative_to(template))
    )


def check_distribution(repo_root: Path) -> list[str]:
    errors: list[str] = []
    template = repo_root / "template"
    if _distribution_root(repo_root) == repo_root:
        return errors
    for source in _source_checkout_live_files(template):
        relative = source.relative_to(template)
        target = repo_root / relative
        if target.is_file():
            _compare_file(
                source,
                target,
                errors,
                drift="local live runtime drift",
            )
    try:
        host_manifest = load_host_manifest(template)
    except HostManifestError as error:
        errors.append(str(error))
        return errors
    try:
        installed_platforms = detect_installed_platforms(repo_root)
    except HostManifestError:
        installed_platforms = ()
    skill_targets = {
        host_manifest.platform(platform_id).skill_target
        for platform_id in installed_platforms
        if host_manifest.platform(platform_id).skill_target
    }
    skill_root = template / "skills"
    for source in _distribution_files(skill_root):
        relative = source.relative_to(skill_root)
        for skill_target in sorted(skill_targets):
            _same_file(source, repo_root / skill_target / relative, errors)
    return errors


def _task_path(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _task_metadata(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _session_task_paths(repo_root: Path) -> set[str]:
    sessions = repo_root / ".cowork-flow" / ".runtime" / "sessions"
    active: set[str] = set()
    if not sessions.is_dir():
        return active
    for path in sorted(sessions.glob("*.json")):
        data = _task_metadata(path)
        task_path = data.get("active_task_path")
        if isinstance(task_path, str) and task_path.strip():
            active.add(task_path.replace("\\", "/"))
    return active


def _task_hygiene_issue(
    *,
    kind: str,
    task: str,
    status: str,
    message: str,
    hint: str,
) -> dict[str, str]:
    code = f"TASK-HYGIENE-{kind.replace('_', '-').upper()}"
    return _issue(
        code=code,
        severity="warning",
        path=task,
        message=message,
        command_hint=hint,
        contract="runtime-health:task-hygiene",
        kind=kind,
        task=task,
        status=status,
        hint=hint,
    )


def _missing_context_files(task_dir: Path) -> tuple[str, ...]:
    required = ("decision-anchor.md", "implement.jsonl", "check.jsonl", "debug.jsonl")
    return tuple(name for name in required if not (task_dir / name).is_file())


def check_task_hygiene(repo_root: Path) -> list[dict[str, str]]:
    tasks_dir = repo_root / ".cowork-flow" / "tasks"
    if not tasks_dir.is_dir():
        return []
    bound_tasks = _session_task_paths(repo_root)
    issues: list[dict[str, str]] = []
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir() or task_dir.name == "archive":
            continue
        task = _task_path(repo_root, task_dir)
        data = _task_metadata(task_dir / "task.json")
        status = str(data.get("status") or "unknown")
        if status == "completed":
            issues.append(
                _task_hygiene_issue(
                    kind="completed_unarchived",
                    task=task,
                    status=status,
                    message="completed task remains in the active task tree",
                    hint=f"./.cowork-flow/run task next {task} --run --intent archive",
                )
            )
        if status in {"in_progress", "review"} and task not in bound_tasks:
            issues.append(
                _task_hygiene_issue(
                    kind="in_progress_unbound",
                    task=task,
                    status=status,
                    message="active task state is not bound to any runtime session",
                    hint=f"./.cowork-flow/run task next {task} --run",
                )
            )
        missing = _missing_context_files(task_dir)
        if missing:
            issues.append(
                _task_hygiene_issue(
                    kind="missing_task_context",
                    task=task,
                    status=status,
                    message=f"missing task context file(s): {', '.join(missing)}",
                    hint=f"./.cowork-flow/run task next {task} --validate",
                )
            )
    return issues


def _print_task_hygiene_issues(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        print(
            "WARNING: "
            f"{issue['kind']}: {issue['task']} ({issue['status']}): "
            f"{issue['message']}",
            file=sys.stderr,
        )
        print(f"Hint: {issue['hint']}", file=sys.stderr)


def _diagnostic_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _state_lock_code(status: str) -> str:
    return f"STATE-RECOVERY-LOCK-{status.upper().replace('_', '-')}"


def _state_lock_command_hint(info) -> str:
    if info.status != "recoverable":
        return "Inspect the lock owner facts; do not delete unless the owner PID is missing and the lock is older than the stale threshold."
    return (
        "Use an explicit recovery action only after verification, for example "
        "StateStore().remove_stale_lock(Path(<target>), stale_after_seconds="
        f"{DEFAULT_STALE_LOCK_SECONDS})"
    )


def _state_lock_issue(repo_root: Path, info) -> dict[str, object]:
    fields = info.to_dict()
    fields.update(
        {
            "kind": "state_lock",
            "lockPath": _diagnostic_path(repo_root, info.lock_path),
            "target": str(info.target),
        }
    )
    if info.age_seconds is not None:
        fields["ageSeconds"] = round(info.age_seconds, 3)
    return _issue(
        code=_state_lock_code(info.status),
        severity="warning",
        path=_diagnostic_path(repo_root, info.lock_path),
        message=info.detail,
        command_hint=_state_lock_command_hint(info),
        contract="runtime-health:state-recovery",
        **fields,
    )


def _operation_command_hint() -> str:
    return (
        "Inspect the pending operation record; a trusted recovery command may "
        "call UnitOfWork.recover_all(repo_root) without interpreting error "
        "output as instructions."
    )


def _pending_operation_issue(repo_root: Path, fact: dict) -> dict[str, object]:
    error = fact.get("error")
    if fact.get("phase") == "unreadable" and isinstance(error, dict):
        return _issue(
            code="STATE-RECOVERY-OPERATION-UNREADABLE",
            severity="warning",
            path=_diagnostic_path(repo_root, Path(str(fact.get("path") or ""))),
            message=str(error.get("detail") or "operation record is unreadable"),
            command_hint="Inspect the operation record manually; Doctor does not mutate recovery state.",
            contract="runtime-health:state-recovery",
            kind="pending_operation",
            operationId=str(fact.get("operation_id") or ""),
            phase=str(fact.get("phase") or "unreadable"),
            errorCode=str(error.get("code") or ""),
        )
    operation_id = str(fact.get("operation_id") or "")
    phase = str(fact.get("phase") or "unknown")
    record_error = fact.get("error")
    if phase == "conflicted":
        error_detail = ""
        error_code = ""
        if isinstance(record_error, dict):
            error_code = str(record_error.get("code") or "")
            error_detail = str(record_error.get("detail") or "")
        suffix = ": ".join(value for value in (error_code, error_detail) if value)
        message = (
            f"conflicted UnitOfWork operation {operation_id}"
            + (f": {suffix}" if suffix else "")
        )
        return _issue(
            code="STATE-RECOVERY-CONFLICTED-OPERATION",
            severity="warning",
            path=_diagnostic_path(repo_root, Path(str(fact.get("path") or ""))),
            message=message,
            command_hint=(
                "Resolve the recorded conflict manually; Doctor does not retry "
                "or mutate conflicted operation state."
            ),
            contract="runtime-health:state-recovery",
            kind="pending_operation",
            operationId=operation_id,
            operationKind=str(fact.get("kind") or "unknown"),
            phase=phase,
            participantCount=fact.get("participant_count", 0),
        )
    return _issue(
        code="STATE-RECOVERY-PENDING-OPERATION",
        severity="warning",
        path=_diagnostic_path(repo_root, Path(str(fact.get("path") or ""))),
        message=f"pending UnitOfWork operation {operation_id} is in phase {phase}",
        command_hint=_operation_command_hint(),
        contract="runtime-health:state-recovery",
        kind="pending_operation",
        operationId=operation_id,
        operationKind=str(fact.get("kind") or "unknown"),
        phase=phase,
        participantCount=fact.get("participant_count", 0),
    )


def check_state_recovery(repo_root: Path) -> list[dict[str, object]]:
    workflow = repo_root / ".cowork-flow"
    if not workflow.is_dir():
        return []
    store = StateStore()
    issues: list[dict[str, object]] = []
    for lock_path in sorted(workflow.rglob("*.lock")):
        if not lock_path.is_file():
            continue
        info = store.inspect_lock_path(
            lock_path,
            stale_after_seconds=DEFAULT_STALE_LOCK_SECONDS,
        )
        if info.status != "absent":
            issues.append(_state_lock_issue(repo_root, info))
    operation_log = OperationLog(repo_root, state_store=store)
    for fact in operation_log.pending_facts():
        issues.append(_pending_operation_issue(repo_root, fact))
    return issues


def _print_state_recovery_issues(issues: list[dict[str, object]]) -> None:
    for issue in issues:
        print(
            "WARNING: "
            f"{issue['kind']}: {issue['path']}: "
            f"{issue['message']}",
            file=sys.stderr,
        )
        hint = issue.get("commandHint")
        if hint:
            print(f"Hint: {hint}", file=sys.stderr)


def check_runtime(repo_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        load_skill_manifests(repo_root)
        action_owners(repo_root)
    except SkillManifestError as error:
        errors.append(f"Skill manifest error: {error}")

    distribution_root = _distribution_root(repo_root)
    kernel_path = distribution_root / ".cowork-flow/scripts/kernel/workflow_route.py"
    if not kernel_path.is_file():
        errors.append(f"missing kernel route: {kernel_path}")
    else:
        source = kernel_path.read_text(encoding="utf-8")
        for forbidden in ("activatedSkill", "recommendedSkill", "./.cowork-flow/run", "label"):
            if forbidden in source:
                errors.append(f"kernel contains delivery concern: {forbidden}")

    workflow_template = distribution_root / ".cowork-flow/spec/contracts/workflow-state-templates.md"
    if not workflow_template.is_file():
        errors.append(f"missing workflow-state contract: {workflow_template}")
    else:
        text = workflow_template.read_text(encoding="utf-8")
        for status in ("no_task", "delegated_subtask", "planning", "in_progress", "review", "completed"):
            if f"[workflow-state:{status}]" not in text:
                errors.append(f"workflow-state contract missing status: {status}")
    return errors


def _all_check_result(repo_root: Path) -> dict[str, object]:
    host_issues = _host_issues(repo_root)
    runtime_errors = check_runtime(repo_root)
    distribution_errors = check_distribution(repo_root)
    task_hygiene_issues = check_task_hygiene(repo_root)
    state_recovery_issues = check_state_recovery(repo_root)
    errors: list[dict[str, object]] = []
    for issue in host_issues:
        errors.append({"kind": "host_adapter", **issue})
    errors.extend(
        {"kind": "runtime", "message": error}
        for error in runtime_errors
    )
    errors.extend(
        {"kind": "distribution", "message": error}
        for error in distribution_errors
    )
    return {
        "ok": not errors,
        "errors": errors,
        "issues": {
            "hostAdapters": host_issues,
            "taskHygiene": task_hygiene_issues,
            "stateRecovery": state_recovery_issues,
        },
    }


def _run_checks(repo_root: Path, *, structured: bool = False) -> int:
    result = _all_check_result(repo_root)
    errors = result["errors"]
    if structured:
        print(json.dumps(result, ensure_ascii=False))
        return 1 if errors else 0
    _print_task_hygiene_issues(result["issues"]["taskHygiene"])
    _print_state_recovery_issues(result["issues"]["stateRecovery"])
    if errors:
        for error in errors:
            print(f"ERROR: {error['message']}", file=sys.stderr)
        return 1
    print("runtime health checks passed")
    return 0


def _run_host_checks(repo_root: Path, *, structured: bool = False) -> int:
    issues = _host_issues(repo_root)
    if structured:
        print(json.dumps({"issues": issues}, ensure_ascii=False))
        return 1 if issues else 0
    errors = [issue["message"] for issue in issues]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("host adapter checks passed")
    return 0


def _run_runtime_checks(repo_root: Path) -> int:
    errors = check_runtime(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("runtime safety checks passed")
    return 0


def _run_task_hygiene_checks(repo_root: Path, *, structured: bool = False) -> int:
    issues = check_task_hygiene(repo_root)
    if structured:
        print(json.dumps({"issues": issues}, ensure_ascii=False))
        return 0
    if issues:
        _print_task_hygiene_issues(issues)
    else:
        print("task hygiene checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cowork-flow diagnostics")
    parser.add_argument("--all", action="store_true", help="Run all structured health checks")
    parser.add_argument("--subagent-safety", action="store_true", help="Run runtime safety checks")
    parser.add_argument("--host-adapters", action="store_true", help="Run host asset checks")
    parser.add_argument("--task-hygiene", action="store_true", help="Report stale task hygiene issues")
    parser.add_argument("--json", action="store_true", help="Render machine-readable diagnostics where supported")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = get_repo_root()
    if args.all:
        return _run_checks(repo_root, structured=bool(args.json))
    if args.host_adapters:
        return _run_host_checks(repo_root, structured=bool(args.json))
    if args.subagent_safety:
        return _run_runtime_checks(repo_root)
    if args.task_hygiene:
        return _run_task_hygiene_checks(repo_root, structured=bool(args.json))
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
