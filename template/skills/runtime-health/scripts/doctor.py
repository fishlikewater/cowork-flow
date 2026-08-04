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


def check_distribution(repo_root: Path) -> list[str]:
    errors: list[str] = []
    template = repo_root / "template"
    if _distribution_root(repo_root) == repo_root:
        return errors
    runtime_root = template / ".cowork-flow" / "scripts"
    for source in _distribution_files(runtime_root):
        relative = source.relative_to(template)
        target = repo_root / relative
        if target.is_file():
            _compare_file(
                source,
                target,
                errors,
                drift="local live runtime drift",
            )
    for relative in (Path(".cowork-flow/run"), Path(".cowork-flow/run.cmd")):
        source = template / relative
        target = repo_root / relative
        if source.is_file() and target.is_file():
            _compare_file(source, target, errors, drift="local live runtime drift")
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


def _run_checks(repo_root: Path) -> int:
    errors = []
    errors.extend(_host_errors(repo_root))
    errors.extend(check_runtime(repo_root))
    errors.extend(check_distribution(repo_root))
    _print_task_hygiene_issues(check_task_hygiene(repo_root))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
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
        return _run_checks(repo_root)
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
