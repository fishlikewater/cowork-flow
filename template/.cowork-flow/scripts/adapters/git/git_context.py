#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git and task context utilities.

Provides:
    output_json - Output context in JSON format
    output_text - Output context in text format
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from runtime.session_state import get_active_task
from infra.files import read_json_file as _read_json_file
from infra.paths import (
    DIR_SCRIPTS,
    DIR_SPEC,
    DIR_TASKS,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_developer,
    get_repo_root,
    get_tasks_dir,
)

CONTEXT_JSONL_FILES = ("implement.jsonl", "check.jsonl", "debug.jsonl")

# =============================================================================
# Helper Functions
# =============================================================================


@dataclass(frozen=True)
class GitSnapshot:
    branch: str
    status_count: int
    log_out: str
    recent_commits: list[dict]


@dataclass(frozen=True)
class ActiveTaskSnapshot:
    path: str | None
    data: dict | None
    has_decision_anchor: bool


def _run_git_command(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr).

    Uses UTF-8 encoding with -c i18n.logOutputEncoding=UTF-8 to ensure
    consistent output across all platforms (Windows, macOS, Linux).
    """
    try:
        # Force git to output UTF-8 for consistent cross-platform behavior
        git_args = ["git", "-c", "i18n.logOutputEncoding=UTF-8"] + args
        result = subprocess.run(
            git_args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def _iter_task_dirs(tasks_dir: Path, sort: bool = True):
    """Yield active task directories."""
    if not tasks_dir.is_dir():
        return

    dirs = sorted(tasks_dir.iterdir()) if sort else tasks_dir.iterdir()
    for d in dirs:
        if d.is_dir() and d.name != "archive":
            yield d


def _load_task_json_by_dir(tasks_dir: Path, sort: bool = True) -> dict[str, dict]:
    """Load task.json data keyed by task directory name."""
    tasks: dict[str, dict] = {}
    for d in _iter_task_dirs(tasks_dir, sort=sort):
        task_json = d / FILE_TASK_JSON
        if task_json.is_file():
            data = _read_json_file(task_json)
            if data:
                tasks[d.name] = data
    return tasks


def _parse_recent_commits(log_out: str, include_empty_message: bool = True) -> list[dict]:
    """Parse git log --oneline output into JSON-ready commit summaries."""
    commits = []
    for line in log_out.splitlines():
        if not line.strip():
            continue

        parts = line.split(" ", 1)
        if len(parts) >= 2:
            commits.append({"hash": parts[0], "message": parts[1]})
        elif include_empty_message:
            commits.append({"hash": parts[0], "message": ""})
    return commits


def _get_git_snapshot(
    repo_root: Path,
    include_empty_commit_message: bool = True,
) -> GitSnapshot:
    """Collect git data shared by JSON and text renderers."""
    _, branch_out, _ = _run_git_command(["branch", "--show-current"], cwd=repo_root)
    _, status_out, _ = _run_git_command(["status", "--porcelain"], cwd=repo_root)
    _, log_out, _ = _run_git_command(["log", "--oneline", "-5"], cwd=repo_root)

    status_lines = [line for line in status_out.splitlines() if line.strip()]
    return GitSnapshot(
        branch=branch_out.strip() or "unknown",
        status_count=len(status_lines),
        log_out=log_out,
        recent_commits=_parse_recent_commits(
            log_out,
            include_empty_message=include_empty_commit_message,
        ),
    )


def _git_json(git_snapshot: GitSnapshot) -> dict:
    """Build the git JSON object used by context output."""
    status_count = git_snapshot.status_count
    return {
        "branch": git_snapshot.branch,
        "isClean": status_count == 0,
        "uncommittedChanges": status_count,
        "recentCommits": git_snapshot.recent_commits,
    }


def _append_git_status(lines: list[str], git_snapshot: GitSnapshot, repo_root: Path) -> None:
    """Append the GIT STATUS section to text output."""
    lines.append("## GIT STATUS")
    lines.append(f"Branch: {git_snapshot.branch}")

    status_count = git_snapshot.status_count
    if status_count == 0:
        lines.append("Working directory: Clean")
    else:
        lines.append(f"Working directory: {status_count} uncommitted change(s)")
        lines.append("")
        lines.append("Changes:")
        _, short_out, _ = _run_git_command(["status", "--short"], cwd=repo_root)
        for line in short_out.splitlines()[:10]:
            lines.append(line)
    lines.append("")


def _append_recent_commits(lines: list[str], git_snapshot: GitSnapshot) -> None:
    """Append the RECENT COMMITS section to text output."""
    lines.append("## RECENT COMMITS")
    log_out = git_snapshot.log_out
    if log_out.strip():
        for line in log_out.splitlines():
            lines.append(line)
    else:
        lines.append("(no commits)")
    lines.append("")


def _get_active_task_snapshot(repo_root: Path) -> ActiveTaskSnapshot:
    """Collect active-task metadata once for text and JSON renderers."""
    active_task = get_active_task(repo_root).task_path
    if not active_task:
        return ActiveTaskSnapshot(path=None, data=None, has_decision_anchor=False)

    active_task_dir = repo_root / active_task
    task_json_path = active_task_dir / FILE_TASK_JSON
    data = None
    if task_json_path.is_file():
        data = _read_json_file(task_json_path)
    return ActiveTaskSnapshot(
        path=active_task,
        data=data,
        has_decision_anchor=(active_task_dir / "decision-anchor.md").is_file(),
    )


def _jsonl_file_references(jsonl_path: Path) -> list[str]:
    """读取 JSONL 中声明的文件引用，忽略损坏行。"""
    references: list[str] = []
    if not jsonl_path.is_file():
        return references

    try:
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    except (OSError, IOError):
        return references

    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        file_path = data.get("file")
        if isinstance(file_path, str) and file_path.strip():
            references.append(file_path.strip())

    return references


def _task_plan_references(repo_root: Path, snapshot: ActiveTaskSnapshot) -> list[str]:
    """从当前任务上下文中提取 plan 文件引用。"""
    if not snapshot.path:
        return []

    task_dir = repo_root / snapshot.path
    plan_refs: list[str] = []
    seen: set[str] = set()

    data = snapshot.data or {}
    metadata_candidates = [
        data.get("plan"),
        data.get("planFile"),
        data.get("meta", {}).get("plan") if isinstance(data.get("meta"), dict) else None,
        data.get("meta", {}).get("planFile") if isinstance(data.get("meta"), dict) else None,
    ]

    for candidate in metadata_candidates:
        if isinstance(candidate, str) and candidate.startswith(f"{DIR_WORKFLOW}/plans/"):
            seen.add(candidate)
            plan_refs.append(candidate)

    for jsonl_name in CONTEXT_JSONL_FILES:
        for reference in _jsonl_file_references(task_dir / jsonl_name):
            if not reference.startswith(f"{DIR_WORKFLOW}/plans/"):
                continue
            if reference in seen:
                continue
            seen.add(reference)
            plan_refs.append(reference)

    return plan_refs


def _build_resume_checklist(
    repo_root: Path,
    snapshot: ActiveTaskSnapshot,
) -> dict[str, list[str]]:
    """构建最小恢复清单，只返回路径和命令，不展开文件内容。"""
    commands = [f"./{DIR_WORKFLOW}/run resume"]
    read_files: list[str] = []
    notes: list[str] = []

    if not snapshot.path:
        notes.append("No active task in the current context. Use `task next --run --title <title>` or `task next <task-dir> --run` with COWORK_FLOW_CONTEXT_ID.")
        notes.append("Do not bulk-read `.cowork-flow/spec/`; read details only after a task is selected.")
        return {"commands": commands, "readFiles": read_files, "notes": notes}

    active_task = snapshot.path
    commands.append(f"Read task context JSONL files under {active_task} directly")

    if snapshot.has_decision_anchor:
        read_files.append(f"{active_task}/decision-anchor.md")

    read_files.extend(_task_plan_references(repo_root, snapshot))
    notes.append("Read current plan status only when continuing implementation.")
    notes.append("Do not bulk-read `.cowork-flow/spec/`; follow JSONL references on demand.")

    return {"commands": commands, "readFiles": read_files, "notes": notes}



def _append_resume_checklist(
    lines: list[str],
    repo_root: Path,
    snapshot: ActiveTaskSnapshot,
) -> None:
    """Append the minimal resume checklist to text output."""
    lines.append("## RESUME CHECKLIST")
    checklist = _build_resume_checklist(repo_root, snapshot)
    commands = checklist["commands"]
    read_files = checklist["readFiles"]

    lines.append(f"- Recovery entrypoint (rerun only if context is stale): {commands[0]}")

    if not snapshot.path:
        lines.append("- No active task in the current context. Use `task next --run --title <title>` or `task next <task-dir> --run` with COWORK_FLOW_CONTEXT_ID.")
        lines.append("- Do not bulk-read .cowork-flow/spec/; choose a task first.")
        lines.append("")
        return

    active_task = snapshot.path
    decision_anchor_path = f"{active_task}/decision-anchor.md"
    if decision_anchor_path in read_files:
        lines.append(f"- Read active task decision-anchor: {decision_anchor_path}")
    else:
        lines.append(f"- Active task decision-anchor missing: {decision_anchor_path}")

    lines.append(f"- List task context before reading details: {commands[1]}")

    plan_files = [path for path in read_files if path.startswith(f"{DIR_WORKFLOW}/plans/")]
    if plan_files:
        for plan_file in plan_files:
            lines.append(f"- Read current plan status: {plan_file}")
    else:
        lines.append("- No plan reference found in task context; do not search all plans unless needed.")

    lines.append("- Do not bulk-read .cowork-flow/spec/; follow JSONL references on demand.")
    lines.append("")


def _append_active_task(
    lines: list[str],
    snapshot: ActiveTaskSnapshot,
    include_created: bool = False,
    include_description: bool = False,
    include_decision_anchor_hint: bool = False,
) -> None:
    """Append the ACTIVE TASK section to text output."""
    lines.append("## ACTIVE TASK")
    active_task = snapshot.path
    if not active_task:
        lines.append("(none)")
        lines.append("")
        return

    lines.append(f"Path: {active_task}")
    data = snapshot.data
    if data:
        lines.append(f"Name: {data.get('name') or data.get('id') or 'unknown'}")
        lines.append(f"Status: {data.get('status', 'unknown')}")
        if include_created:
            lines.append(f"Created: {data.get('createdAt', 'unknown')}")
        if include_description:
            description = data.get("description", "")
            if description:
                lines.append(f"Description: {description}")

    if include_decision_anchor_hint and snapshot.has_decision_anchor:
        lines.append("")
        lines.append("[!] This task has decision-anchor.md - read it for task details")
    lines.append("")


def _load_task_context_by_dir(tasks_dir: Path) -> dict[str, dict]:
    """Load task display data, preserving dirs without task.json as unknown."""
    all_task_data: dict[str, dict] = {}
    for d in _iter_task_dirs(tasks_dir):
        data = _read_json_file(d / FILE_TASK_JSON) or {}
        all_task_data[d.name] = {
            "status": data.get("status", "unknown"),
            "my_status": data.get("status", "planning"),
            "assignee": data.get("assignee", "-"),
            "my_assignee": data.get("assignee", ""),
            "title": data.get("title") or data.get("name") or "unknown",
            "priority": data.get("priority", "P2"),
            "children": data.get("children", []),
            "parent": data.get("parent"),
        }
    return all_task_data


def _task_statuses(task_data_by_dir: dict[str, dict]) -> dict[str, str]:
    """Return task status lookup by directory name."""
    return {
        dir_name: data.get("status", "unknown")
        for dir_name, data in task_data_by_dir.items()
    }


def _children_done_count(children: list[str], statuses: dict[str, str]) -> int:
    """Count completed child tasks."""
    return sum(1 for child in children if statuses.get(child) in ("completed", "done"))


def _children_progress(children: list[str], statuses: dict[str, str]) -> str:
    """Render children progress like '[2/3 done]'."""
    if not children:
        return ""
    return f" [{_children_done_count(children, statuses)}/{len(children)} done]"


def _append_active_tasks(lines: list[str], tasks_dir: Path) -> None:
    """Append active task hierarchy to text output."""
    lines.append("## ACTIVE TASKS")
    task_count = 0

    all_task_data = _load_task_context_by_dir(tasks_dir)
    all_task_statuses = {
        dir_name: data["status"]
        for dir_name, data in all_task_data.items()
    }

    def _print_task_tree(name: str, indent: int = 0) -> None:
        nonlocal task_count
        info = all_task_data[name]
        progress = _children_progress(info["children"], all_task_statuses)
        prefix = "  " * indent
        lines.append(f"{prefix}- {name}/ ({info['status']}){progress} @{info['assignee']}")
        task_count += 1
        for child in info["children"]:
            if child in all_task_data:
                _print_task_tree(child, indent + 1)

    for dir_name in sorted(all_task_data.keys()):
        if not all_task_data[dir_name]["parent"]:
            _print_task_tree(dir_name)

    if task_count == 0:
        lines.append("(no active tasks)")
    lines.append(f"Total: {task_count} active task(s)")
    lines.append("")


def _append_my_tasks(lines: list[str], developer: str, tasks_dir: Path) -> None:
    """Append tasks assigned to the current developer."""
    lines.append("## MY TASKS (Assigned to me)")
    my_task_count = 0
    all_task_data = _load_task_context_by_dir(tasks_dir)
    all_task_statuses = _task_statuses(all_task_data)

    for dir_name in sorted(all_task_data.keys()):
        info = all_task_data[dir_name]
        assignee = info["my_assignee"]
        status = info["my_status"]

        if assignee == developer and status != "done":
            progress = _children_progress(info["children"], all_task_statuses)
            lines.append(f"- [{info['priority']}] {info['title']} ({status}){progress}")
            my_task_count += 1

    if my_task_count == 0:
        lines.append("(no tasks assigned to you)")
    lines.append("")



def _append_paths(lines: list[str]) -> None:
    """Append standard cowork-flow paths."""
    lines.append("## PATHS")
    lines.append(f"Tasks: {DIR_WORKFLOW}/{DIR_TASKS}/")
    lines.append(f"Spec: {DIR_WORKFLOW}/{DIR_SPEC}/")
    lines.append("")



def _context_tasks_json(tasks_dir: Path) -> list[dict]:
    """Build active task list for JSON output."""
    tasks = []
    for dir_name, data in _load_task_json_by_dir(tasks_dir, sort=False).items():
        tasks.append(
            {
                "dir": dir_name,
                "name": data.get("name") or data.get("id") or "unknown",
                "status": data.get("status", "unknown"),
                "children": data.get("children", []),
                "parent": data.get("parent"),
            }
        )
    return tasks


# =============================================================================
# JSON Output
# =============================================================================


def get_context_json(repo_root: Path | None = None) -> dict:
    """Get context as a dictionary.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        Context dictionary.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    developer = get_developer(repo_root)
    tasks_dir = get_tasks_dir(repo_root)
    git_snapshot = _get_git_snapshot(repo_root)
    active_task_snapshot = _get_active_task_snapshot(repo_root)

    return {
        "developer": developer or "",
        "git": _git_json(git_snapshot),
        "tasks": {
            "active": _context_tasks_json(tasks_dir),
            "directory": f"{DIR_WORKFLOW}/{DIR_TASKS}",
        },
        "resumeChecklist": _build_resume_checklist(repo_root, active_task_snapshot),
    }


def output_json(repo_root: Path | None = None) -> None:
    """Output context in JSON format.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    context = get_context_json(repo_root)
    print(json.dumps(context, indent=2, ensure_ascii=False))


# =============================================================================
# Text Output
# =============================================================================


def _new_context_lines(title: str) -> list[str]:
    return [
        "========================================",
        title,
        "========================================",
        "",
    ]


def _append_developer(lines: list[str], developer: str | None) -> bool:
    lines.append("## DEVELOPER")
    if not developer:
        lines.append(
            f"ERROR: Not initialized. Run: ./{DIR_WORKFLOW}/run init-developer <name>"
        )
        return False
    lines.append(f"Name: {developer}")
    lines.append("")
    return True


def _append_default_context_sections(
    lines: list[str],
    repo_root: Path,
    developer: str,
) -> None:
    git_snapshot = _get_git_snapshot(repo_root)
    _append_git_status(lines, git_snapshot, repo_root)
    _append_recent_commits(lines, git_snapshot)
    active_task_snapshot = _get_active_task_snapshot(repo_root)
    _append_active_task(
        lines,
        active_task_snapshot,
        include_created=True,
        include_description=True,
        include_decision_anchor_hint=True,
    )
    _append_resume_checklist(lines, repo_root, active_task_snapshot)

    tasks_dir = get_tasks_dir(repo_root)
    _append_active_tasks(lines, tasks_dir)
    _append_my_tasks(lines, developer, tasks_dir)
    _append_paths(lines)


def get_context_text(repo_root: Path | None = None) -> str:
    """Get context as formatted text.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        Formatted text output.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    lines = _new_context_lines("COWORK-FLOW CONTEXT")
    developer = get_developer(repo_root)
    if not _append_developer(lines, developer):
        return "\n".join(lines)

    _append_default_context_sections(lines, repo_root, developer)
    lines.append("========================================")

    return "\n".join(lines)



def output_text(repo_root: Path | None = None) -> None:
    """Output context in text format.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    print(get_context_text(repo_root))


# =============================================================================
# Main Entry
# =============================================================================


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Get cowork-flow context for AI Agent")
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output in JSON format",
    )
    args = parser.parse_args()

    if args.json:
        output_json()
    else:
        output_text()


if __name__ == "__main__":
    main()
