#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task Management Script for cowork-flow workflow.

Usage:
    ./.cowork-flow/run task create "<title>" [--slug <name>] [--assignee <dev>] [--priority P0|P1|P2|P3] [--parent <dir>]
    ./.cowork-flow/run task init-context <dir> <type>   # Initialize jsonl files
    ./.cowork-flow/run task add-context <dir> <file> <path> [reason] # Add jsonl entry
    ./.cowork-flow/run task validate <dir>              # Validate jsonl files
    ./.cowork-flow/run task list-context <dir>          # List jsonl entries
    ./.cowork-flow/run task start <dir>                 # Set active session task
    ./.cowork-flow/run task review [dir]                # Mark task ready for check
    ./.cowork-flow/run task complete [dir]              # Mark task completed
    ./.cowork-flow/run task current                     # Show active session task
    ./.cowork-flow/run task finish                      # Clear active session task
    ./.cowork-flow/run task archive <task-name>         # Archive completed task and linked changes
    ./.cowork-flow/run task list                        # List active tasks
    ./.cowork-flow/run task list-archive [month]        # List archived tasks
    ./.cowork-flow/run task add-subtask <parent-dir> <child-dir>     # Link child to parent
    ./.cowork-flow/run task remove-subtask <parent-dir> <child-dir>  # Unlink child from parent
"""

from __future__ import annotations

import sys

import argparse
import json
import re
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path

if __package__:
    from . import _bootstrap as _bootstrap  # noqa: F401
else:
    import _bootstrap  # noqa: F401
from common.core.files import (
    read_json_file as _read_json_file,
    read_text_utf8 as _read_text,
    write_json_file as _write_json_file,
)
from common.gates.gates import GateResult, GateRunner
from common.git.git_context import _run_git_command
from common.task.active_task import (
    clear_active_task,
    clear_task_from_sessions,
    get_active_task,
    set_active_task,
)
from common.core.paths import (
    DIR_WORKFLOW,
    DIR_AGENTS,
    DIR_CHANGES,
    DIR_TASKS,
    DIR_SPEC,
    DIR_ARCHIVE,
    FILE_TASK_JSON,
    get_repo_root,
    get_developer,
    get_tasks_dir,
    ensure_task_date_prefix,
)
from common.task.task_utils import (
    find_task_by_name,
    archive_task_complete,
)
from common.core.config import get_hooks
from common.core.execution_context import (
    build_internal_execution_context_parser,
    execution_context_from_namespace,
    worker_command_block_message,
)
from common.task.state_machine import transition_blockers

CONTEXT_JSONL_FILES = ["implement.jsonl", "check.jsonl", "debug.jsonl"]
DONE_STATUSES = ("completed", "done")
CHECK_STATUSES = ("review",)


# =============================================================================
# Colors
# =============================================================================

class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"


def colored(text: str, color: str) -> str:
    """Apply color to text."""
    return f"{color}{text}{Colors.NC}"


def _write_json_or_report(path: Path, data: dict, label: str) -> bool:
    """Write JSON data and print a concrete error on failure."""
    if _write_json_file(path, data):
        return True

    print(
        colored(f"Error: Failed to write {label}: {path}", Colors.RED),
        file=sys.stderr,
    )
    return False


def _gate_blocker_messages(result: GateResult) -> list[str]:
    messages: list[str] = []
    for violation in result.blockers:
        rule_id = violation.get("rule_id") or violation.get("id") or "unknown-rule"
        message = violation.get("message") or "Gate blocked"
        messages.append(f"{rule_id}: {message}")
    return messages


def _report_gate_block(
    title: str,
    result: GateResult,
    runner: GateRunner | None = None,
) -> int:
    print(colored(f"Error: {title}", Colors.RED), file=sys.stderr)
    for violation in result.violations:
        print(json.dumps(violation, ensure_ascii=False), file=sys.stderr)
    if runner is not None:
        runner.log(result)
    return result.exit_code


def _report_gate_warnings(title: str, result: GateResult) -> None:
    if not result.violations:
        return

    print(colored(f"Warning: {title}", Colors.YELLOW), file=sys.stderr)
    for violation in result.violations:
        print(json.dumps(violation, ensure_ascii=False), file=sys.stderr)


def _print_transition_blockers(blockers: list[str]) -> None:
    print(colored("Error: Task state transition blocked", Colors.RED), file=sys.stderr)
    for blocker in blockers:
        print(f"  - {blocker}", file=sys.stderr)


def _build_archived_task_relationship_updates(
    dir_name: str,
    task_data: dict,
    tasks_dir: Path,
) -> list[tuple[Path, dict, dict, str]]:
    """Prepare task relationship updates for an archived task."""
    updates: list[tuple[Path, dict, dict, str]] = []
    task_parent = task_data.get("parent")
    task_children = task_data.get("children", [])

    if task_parent:
        parent_dir = find_task_by_name(task_parent, tasks_dir)
        if parent_dir:
            parent_json = parent_dir / FILE_TASK_JSON
            if parent_json.is_file():
                parent_data = _read_json_file(parent_json)
                if parent_data:
                    parent_children = parent_data.get("children", [])
                    if dir_name in parent_children:
                        updated_parent_data = deepcopy(parent_data)
                        updated_children = list(parent_children)
                        updated_children.remove(dir_name)
                        updated_parent_data["children"] = updated_children
                        updates.append(
                            (
                                parent_json,
                                parent_data,
                                updated_parent_data,
                                f"parent task metadata for {parent_dir.name}",
                            )
                        )

    for child_name in task_children:
        child_dir_path = find_task_by_name(child_name, tasks_dir)
        if child_dir_path:
            child_json = child_dir_path / FILE_TASK_JSON
            if child_json.is_file():
                child_data = _read_json_file(child_json)
                if child_data:
                    updated_child_data = deepcopy(child_data)
                    updated_child_data["parent"] = None
                    updates.append(
                        (
                            child_json,
                            child_data,
                            updated_child_data,
                            f"child task metadata for {child_dir_path.name}",
                        )
                    )

    return updates


def _apply_json_updates_with_rollback(
    updates: list[tuple[Path, dict, dict, str]]
) -> bool:
    """Apply a batch of JSON updates and roll back any partial writes on failure."""
    applied: list[tuple[Path, dict, str]] = []

    for path, original_data, updated_data, label in updates:
        if not _write_json_or_report(path, updated_data, label):
            for rollback_path, rollback_data, rollback_label in reversed(applied):
                if not _write_json_file(rollback_path, rollback_data):
                    print(
                        colored(
                            f"Warning: Failed to roll back {rollback_label}: {rollback_path}",
                            Colors.YELLOW,
                        ),
                        file=sys.stderr,
                    )
            return False

        applied.append((path, original_data, label))

    return True


def _update_archived_task_relationships(
    dir_name: str,
    task_data: dict,
    tasks_dir: Path,
) -> bool:
    """Remove archived task references from active task relationships."""
    updates = _build_archived_task_relationship_updates(dir_name, task_data, tasks_dir)
    return _apply_json_updates_with_rollback(updates)


def _rollback_archived_task_or_report(
    task_dir: Path,
    archive_dest: Path,
    task_data: dict | None,
) -> None:
    """Try to restore the original task location and metadata after archive failure."""
    print(
        colored("Warning: Archive failed after partial progress; attempting rollback.", Colors.YELLOW),
        file=sys.stderr,
    )

    if archive_dest.exists() and not task_dir.exists():
        try:
            shutil.move(str(archive_dest), str(task_dir))
        except (OSError, IOError, shutil.Error) as e:
            print(
                colored(f"Error: Failed to move archived task back to source: {e}", Colors.RED),
                file=sys.stderr,
            )
    elif archive_dest.exists() and task_dir.exists():
        print(
            colored(
                f"Error: Both source and archive paths exist during rollback: {task_dir} | {archive_dest}",
                Colors.RED,
            ),
            file=sys.stderr,
        )

    if task_data and task_dir.is_dir():
        _write_json_or_report(task_dir / FILE_TASK_JSON, task_data, "restored task metadata")

def _finalize_archived_task_metadata(
    archive_dest: Path,
    task_data: dict | None,
    tasks_dir: Path,
    dir_name: str,
    today: str,
) -> bool:
    """Write archived task metadata after the directory move succeeds."""
    if not task_data:
        return True

    archived_json = archive_dest / FILE_TASK_JSON
    archived_task_data = deepcopy(task_data)
    archived_task_data["status"] = "completed"
    archived_task_data["completedAt"] = today
    if not _write_json_or_report(
        archived_json,
        archived_task_data,
        "archived task metadata",
    ):
        return False

    return _update_archived_task_relationships(dir_name, task_data, tasks_dir)


# =============================================================================
# Lifecycle Hooks
# =============================================================================

def _run_hooks(event: str, task_json_path: Path, repo_root: Path) -> None:
    """Run lifecycle hooks for an event.

    Args:
        event: Event name (e.g. "after_create").
        task_json_path: Absolute path to the task's task.json.
        repo_root: Repository root for cwd and config lookup.
    """
    import os
    import shlex
    import subprocess

    commands = get_hooks(event, repo_root)
    if not commands:
        return

    env = {**os.environ, "TASK_JSON_PATH": str(task_json_path)}

    for cmd in commands:
        try:
            result = subprocess.run(
                shlex.split(cmd),
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                print(
                    colored(f"[WARN] Hook failed ({event}): {cmd}", Colors.YELLOW),
                    file=sys.stderr,
                )
                if result.stderr.strip():
                    print(f"  {result.stderr.strip()}", file=sys.stderr)
        except Exception as e:
            print(
                colored(f"[WARN] Hook error ({event}): {cmd} - {e}", Colors.YELLOW),
                file=sys.stderr,
            )


def _slugify(title: str) -> str:
    """Convert title to slug (only works with ASCII)."""
    result = title.lower()
    result = re.sub(r"[^a-z0-9]", "-", result)
    result = re.sub(r"-+", "-", result)
    result = result.strip("-")
    return result


def _resolve_task_dir(target_dir: str, repo_root: Path) -> Path:
    """Resolve task directory to absolute path.

    Supports:
    - Absolute path: /path/to/task
    - Relative path: .cowork-flow/tasks/01-31-my-task
    - Task name: my-task (uses find_task_by_name for lookup)
    """
    if not target_dir:
        return Path()

    # Absolute path (Unix "/path" or Windows "C:\path")
    if target_dir.startswith("/") or Path(target_dir).is_absolute():
        return Path(target_dir)

    # Relative path (contains path separator or starts with workflow directory)
    if "/" in target_dir or target_dir.startswith(DIR_WORKFLOW):
        return repo_root / target_dir

    # Task name - try to find in tasks directory
    tasks_dir = get_tasks_dir(repo_root)
    found = find_task_by_name(target_dir, tasks_dir)
    if found:
        return found

    # Fallback to treating as relative path
    return repo_root / target_dir


# =============================================================================
# JSONL Default Content Generators
# =============================================================================

def get_implement_base() -> list[dict]:
    """Get base implement context entries."""
    return [
        {"file": "AGENTS.md", "reason": "Project collaboration rules and workflow gates"},
        {"file": f"{DIR_WORKFLOW}/workflow.md", "reason": "Project workflow and conventions"},
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/guides/index.md", "reason": "Pre-implementation thinking guides"},
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/guides/pre-implementation-checklist.md", "reason": "Mandatory pre-coding checklist"},
    ]


def get_implement_backend() -> list[dict]:
    """Get backend implement context entries."""
    return [
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/backend/index.md", "reason": "Backend development guide"},
    ]


def get_implement_frontend() -> list[dict]:
    """Get frontend implement context entries."""
    return [
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/frontend/index.md", "reason": "Frontend development guide"},
    ]


def get_implement_spec() -> list[dict]:
    """Get spec implement context entries."""
    return [
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/index.md", "reason": "Spec index — read before modifying spec/"},
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/contracts/index.md", "reason": "Contract definitions"},
        {"file": f"{DIR_WORKFLOW}/{DIR_SPEC}/schemas/index.md", "reason": "Schema definitions"},
    ]


def _detect_installed_platforms(repo_root: Path | None = None) -> list[str]:
    """Detect installed host platform assets in the current project."""
    root = repo_root or get_repo_root()
    platforms: list[str] = []
    if (root / ".codex").is_dir():
        platforms.append("codex")
    if (root / ".opencode").is_dir():
        platforms.append("opencode")
    if (root / ".claude").is_dir() or (root / "CLAUDE.md").is_file():
        platforms.append("claude-code")
    return platforms

def _use_claude_skill_context(repo_root: Path | None = None) -> bool:
    return _detect_installed_platforms(repo_root) == ["claude-code"]

def _skill_path(name: str, repo_root: Path | None = None) -> str:
    if _use_claude_skill_context(repo_root):
        return f".claude/skills/{name}/SKILL.md"
    return f"{DIR_AGENTS}/skills/{name}/SKILL.md"


def _discover_spec_files(repo_root: Path, dev_type: str) -> list[str]:
    """动态发现 spec/<dev_type>/ 下的所有 .md 文件。

    返回形如 ".cowork-flow/spec/backend/error-handling.md" 的相对路径列表，
    可直接写入 check.jsonl 条目。dev_type="spec" 时返回 spec/index.md。
    """
    if dev_type == "spec":
        return [f"{DIR_WORKFLOW}/{DIR_SPEC}/index.md"]

    spec_dir = Path(repo_root) / DIR_WORKFLOW / DIR_SPEC / dev_type
    if not spec_dir.is_dir():
        return []
    return sorted(
        f"{DIR_WORKFLOW}/{DIR_SPEC}/{dev_type}/{p.name}"
        for p in spec_dir.glob("*.md")
        if p.is_file()
    )


def get_check_context(repo_root: Path, dev_type: str) -> list[dict]:
    """Get check context entries.

    Injects skill guides and **所有** spec 子文件，使 check agent 可以对照
    .cowork-flow/spec/<dev_type>/ 的完整规范集逐项验证实现。
    spec 文件通过 _discover_spec_files 动态发现，新增/删除 spec 文件无需改代码。
    """
    base = [
        {"file": _skill_path("check"), "reason": "Quality, contract, and template consistency check"},
        {"file": _skill_path("finish-work"), "reason": "Finish, archive, and session recording gate"},
    ]
    for spec_file in _discover_spec_files(repo_root, dev_type):
        base.append({"file": spec_file, "reason": f"Verify {Path(spec_file).name} compliance"})
    return base


def get_debug_context(dev_type: str) -> list[dict]:
    """Get debug context entries."""
    return [
        {"file": _skill_path("break-loop"), "reason": "Deep bug analysis workflow"},
        {"file": _skill_path("update-spec"), "reason": "Capture implementation lessons and contracts"},
        {"file": _skill_path("check"), "reason": "Verify the fix and related contracts"},
    ]


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write entries to JSONL file."""
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _migrate_prd_to_anchor(task_dir: Path) -> bool:
    """将旧 prd.md 迁移到 decision-anchor.md。返回是否执行了迁移。"""
    prd_file = task_dir / "prd.md"
    anchor_file = task_dir / "decision-anchor.md"
    if not prd_file.exists() or anchor_file.exists():
        return False
    content = prd_file.read_text(encoding="utf-8").strip()
    if not content:
        content = "(empty legacy prd.md)"
    if "## 目标" not in content and "## Goal" not in content:
        content = "## 目标\n\n" + content
    if "## 验收标准" not in content and "## Acceptance" not in content:
        content += "\n\n## 验收标准\n- [ ] \n"
    anchor_file.write_text(content, encoding="utf-8")
    prd_file.unlink()
    print(
        colored("  [迁移] prd.md → decision-anchor.md", Colors.YELLOW),
        file=sys.stderr,
    )
    return True


def _task_start_blockers(task_dir: Path) -> list[str]:
    """返回启动任务前必须处理的准备阻塞项。

    注意：调用前应先执行 _migrate_prd_to_anchor()，
    本函数不再检查 prd.md（已被迁移处理）。
    """
    blockers: list[str] = []

    task_json = task_dir / FILE_TASK_JSON
    if not task_json.is_file():
        blockers.append("task.json is missing")

    # 只检查存在性 — R-WF-008 负责章节内容完整性
    if not _read_text(task_dir / "decision-anchor.md"):
        blockers.append("decision-anchor.md is missing or empty")

    for jsonl_name in CONTEXT_JSONL_FILES:
        jsonl_file = task_dir / jsonl_name
        if not _read_text(jsonl_file):
            blockers.append(f"{jsonl_name} is missing or empty")

    return blockers


def _report_jsonl_skip(path: Path, reason: str) -> None:
    """Report that a JSONL file was skipped (not overwritten)."""
    print(f"  {colored('[SKIP]', Colors.YELLOW)} {path.name}: {reason}")


def _task_context_validation_issues(
    task_dir: Path,
    repo_root: Path,
    quiet: bool = False,
) -> list[str]:
    """返回任务上下文文件的校验问题。"""
    issues: list[str] = []

    for jsonl_name in CONTEXT_JSONL_FILES:
        jsonl_file = task_dir / jsonl_name
        if not _read_text(jsonl_file):
            continue

        error_count = _validate_jsonl(jsonl_file, repo_root, quiet=quiet)
        if error_count > 0:
            issues.append(f"{jsonl_name} has {error_count} validation error(s)")

    return issues


def _iter_jsonl_lines(path: Path):
    """Yield line number and content from a JSONL file."""
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            yield line_num, line.rstrip("\n")


def _load_task_summary(task_dir: Path) -> dict:
    """Load task fields needed for tree/list output."""
    data = _read_json_file(task_dir / FILE_TASK_JSON) or {}
    return {
        "status": data.get("status", "unknown"),
        "assignee": data.get("assignee", "-"),
        "children": data.get("children", []),
        "parent": data.get("parent"),
    }


def _load_task_summaries(tasks_dir: Path) -> dict[str, dict]:
    """Load active task summaries keyed by directory name."""
    all_tasks: dict[str, dict] = {}
    if not tasks_dir.is_dir():
        return all_tasks

    for d in sorted(tasks_dir.iterdir()):
        if d.is_dir() and d.name != DIR_ARCHIVE:
            all_tasks[d.name] = _load_task_summary(d)
    return all_tasks


# =============================================================================
# Task Operations
# =============================================================================

def ensure_tasks_dir(repo_root: Path) -> Path:
    """Ensure tasks directory exists."""
    tasks_dir = get_tasks_dir(repo_root)
    archive_dir = tasks_dir / "archive"

    if not tasks_dir.exists():
        tasks_dir.mkdir(parents=True)
        print(colored(f"Created tasks directory: {tasks_dir}", Colors.GREEN), file=sys.stderr)

    if not archive_dir.exists():
        archive_dir.mkdir(parents=True)

    return tasks_dir


# =============================================================================
# Command: create
# =============================================================================

def cmd_create(args: argparse.Namespace) -> int:
    """Create a new task."""
    repo_root = get_repo_root()

    if not args.title:
        print(colored("Error: title is required", Colors.RED), file=sys.stderr)
        return 1

    # Default assignee to current developer
    assignee = args.assignee
    if not assignee:
        assignee = get_developer(repo_root)
        if not assignee:
            print(colored("Error: No developer set. Run init_developer.py first or use --assignee", Colors.RED), file=sys.stderr)
            return 1

    ensure_tasks_dir(repo_root)

    # Get current developer as creator
    creator = get_developer(repo_root) or assignee

    # Generate slug if not provided
    slug = args.slug or _slugify(args.title)
    if not slug:
        print(colored("Error: could not generate slug from title", Colors.RED), file=sys.stderr)
        return 1

    # Create task directory with MM-DD-slug format
    tasks_dir = get_tasks_dir(repo_root)
    dir_name = ensure_task_date_prefix(slug)
    task_dir = tasks_dir / dir_name
    task_json_path = task_dir / FILE_TASK_JSON

    if task_dir.exists():
        print(colored(f"Warning: Task directory already exists: {dir_name}", Colors.YELLOW), file=sys.stderr)
    else:
        task_dir.mkdir(parents=True)

    today = datetime.now().strftime("%Y-%m-%d")

    task_data = {
        "id": slug,
        "name": slug,
        "title": args.title,
        "description": args.description or "",
        "status": "planning",
        "dev_type": None,
        "scope": None,
        "priority": args.priority,
        "creator": creator,
        "assignee": assignee,
        "createdAt": today,
        "completedAt": None,
        "commit": None,
        "subtasks": [],
        "children": [],
        "parent": None,
        "relatedFiles": [],
        "notes": "",
        "meta": {},
    }

    _write_json_file(task_json_path, task_data)

    # Handle --parent: establish bidirectional link
    if args.parent:
        parent_dir = _resolve_task_dir(args.parent, repo_root)
        parent_json_path = parent_dir / FILE_TASK_JSON
        if not parent_json_path.is_file():
            print(colored(f"Warning: Parent task.json not found: {args.parent}", Colors.YELLOW), file=sys.stderr)
        else:
            parent_data = _read_json_file(parent_json_path)
            if parent_data:
                # Add child to parent's children list
                parent_children = parent_data.get("children", [])
                if dir_name not in parent_children:
                    parent_children.append(dir_name)
                    parent_data["children"] = parent_children
                    _write_json_file(parent_json_path, parent_data)

                # Set parent in child's task.json
                task_data["parent"] = parent_dir.name
                _write_json_file(task_json_path, task_data)

                print(colored(f"Linked as child of: {parent_dir.name}", Colors.GREEN), file=sys.stderr)

    # --from-plan: 自动生成 decision-anchor.md 骨架
    if getattr(args, "from_plan", None):
        plan_path = Path(args.from_plan)
        if plan_path.is_file():
            plan_text = plan_path.read_text(encoding="utf-8")
            goal = next(
                (line.split(":", 1)[1].strip() for line in plan_text.splitlines()
                 if line.startswith("**Goal:**") or line.startswith("**目标:**")),
                None,
            )
            if goal:
                anchor_file = task_dir / "decision-anchor.md"
                if not anchor_file.exists():
                    anchor_file.write_text(
                        f"## 目标\n\n{goal}\n\n## 验收标准\n- [ ] \n",
                        encoding="utf-8",
                    )
                    print(f"  {colored('[OK]', Colors.GREEN)} Generated decision-anchor.md from plan")

    print(colored(f"Created task: {dir_name}", Colors.GREEN), file=sys.stderr)
    print("", file=sys.stderr)
    print(colored("Next steps:", Colors.BLUE), file=sys.stderr)
    print("  1. Create decision-anchor.md with requirements", file=sys.stderr)
    print("  2. Run: ./.cowork-flow/run task init-context <dir> <dev_type>", file=sys.stderr)
    print("  3. Run: ./.cowork-flow/run task start <dir>", file=sys.stderr)
    print("", file=sys.stderr)

    # Output relative path for script chaining
    print(f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}")

    _run_hooks("after_create", task_json_path, repo_root)
    return 0


# =============================================================================
# Command: init-context
# =============================================================================

def cmd_init_context(args: argparse.Namespace) -> int:
    """Initialize JSONL context files for a task."""
    repo_root = get_repo_root()
    target_dir = _resolve_task_dir(args.dir, repo_root)
    dev_type = args.type

    if not dev_type:
        print(colored("Error: Missing arguments", Colors.RED))
        print("Usage: ./.cowork-flow/run task init-context <task-dir> <dev_type>")
        print("  dev_type: backend | frontend | fullstack | test | docs | spec")
        return 1

    if not target_dir.is_dir():
        print(colored(f"Error: Directory not found: {target_dir}", Colors.RED))
        return 1

    print(colored("=== Initializing Agent Context Files ===", Colors.BLUE))
    print(f"Target dir: {target_dir}")
    print(f"Dev type: {dev_type}")
    print()

    # implement.jsonl
    implement_file = target_dir / "implement.jsonl"
    if implement_file.is_file():
        # 已有内容时不覆盖 — 用户可能已自定义
        _report_jsonl_skip(implement_file, "already exists, skipping")
    else:
        print(colored("Creating implement.jsonl...", Colors.CYAN))
        implement_entries = get_implement_base()
        if dev_type in ("backend", "test"):
            implement_entries.extend(get_implement_backend())
        elif dev_type == "frontend":
            implement_entries.extend(get_implement_frontend())
        elif dev_type == "fullstack":
            implement_entries.extend(get_implement_backend())
            implement_entries.extend(get_implement_frontend())
        elif dev_type == "spec":
            implement_entries.extend(get_implement_spec())
        _write_jsonl(implement_file, implement_entries)
        print(f"  {colored('[OK]', Colors.GREEN)} {len(implement_entries)} entries")

    # check.jsonl
    check_file = target_dir / "check.jsonl"
    if check_file.is_file():
        _report_jsonl_skip(check_file, "already exists, skipping")
    else:
        print(colored("Creating check.jsonl...", Colors.CYAN))
        check_entries = get_check_context(repo_root, dev_type)
        _write_jsonl(check_file, check_entries)
        print(f"  {colored('[OK]', Colors.GREEN)} {len(check_entries)} entries")

    # debug.jsonl
    debug_file = target_dir / "debug.jsonl"
    if debug_file.is_file():
        _report_jsonl_skip(debug_file, "already exists, skipping")
    else:
        print(colored("Creating debug.jsonl...", Colors.CYAN))
        debug_entries = get_debug_context(dev_type)
        _write_jsonl(debug_file, debug_entries)
        print(f"  {colored('[OK]', Colors.GREEN)} {len(debug_entries)} entries")

    return 0


# =============================================================================
# Command: add-context
# =============================================================================

def cmd_add_context(args: argparse.Namespace) -> int:
    """Add entry to JSONL context file."""
    repo_root = get_repo_root()
    target_dir = _resolve_task_dir(args.dir, repo_root)

    jsonl_name = args.file
    path = args.path
    reason = args.reason or "Added manually"

    if not target_dir.is_dir():
        print(colored(f"Error: Directory not found: {target_dir}", Colors.RED))
        return 1

    # Support shorthand
    if not jsonl_name.endswith(".jsonl"):
        jsonl_name = f"{jsonl_name}.jsonl"

    jsonl_file = target_dir / jsonl_name
    full_path = repo_root / path

    entry_type = "file"
    if full_path.is_dir():
        entry_type = "directory"
        if not path.endswith("/"):
            path = f"{path}/"
    elif not full_path.is_file():
        print(colored(f"Error: Path not found: {path}", Colors.RED))
        return 1

    # Check if already exists
    if jsonl_file.is_file():
        for _, line in _iter_jsonl_lines(jsonl_file):
            if f'"{path}"' in line:
                print(colored(f"Warning: Entry already exists for {path}", Colors.YELLOW))
                return 0

    # Add entry
    entry: dict
    if entry_type == "directory":
        entry = {"file": path, "type": "directory", "reason": reason}
    else:
        entry = {"file": path, "reason": reason}

    with jsonl_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(colored(f"Added {entry_type}: {path}", Colors.GREEN))
    return 0


# =============================================================================
# Command: validate
# =============================================================================

def cmd_validate(args: argparse.Namespace) -> int:
    """Validate JSONL context files."""
    repo_root = get_repo_root()
    target_dir = _resolve_task_dir(args.dir, repo_root)

    if not target_dir.is_dir():
        print(colored("Error: task directory required", Colors.RED))
        return 1

    print(colored("=== Validating Context Files ===", Colors.BLUE))
    print(f"Target dir: {target_dir}")
    print()

    total_errors = 0
    for jsonl_name in CONTEXT_JSONL_FILES:
        jsonl_file = target_dir / jsonl_name
        errors = _validate_jsonl(jsonl_file, repo_root)
        total_errors += errors

    print()
    if total_errors == 0:
        print(colored("[OK] All validations passed", Colors.GREEN))
        return 0
    else:
        print(colored(f"[FAIL] Validation failed ({total_errors} errors)", Colors.RED))
        return 1


def _validate_jsonl(jsonl_file: Path, repo_root: Path, quiet: bool = False) -> int:
    """Validate a single JSONL file."""
    file_name = jsonl_file.name
    errors = 0

    if not jsonl_file.is_file():
        if not quiet:
            print(f"  {colored(f'{file_name}: not found (skipped)', Colors.YELLOW)}")
        return 0

    line_num = 0
    entry_count = 0
    for line_num, line in _iter_jsonl_lines(jsonl_file):
        if not line.strip():
            continue
        entry_count += 1

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            if not quiet:
                print(f"  {colored(f'{file_name}:{line_num}: Invalid JSON', Colors.RED)}")
            errors += 1
            continue

        file_path = data.get("file")
        entry_type = data.get("type", "file")

        if not file_path:
            if not quiet:
                print(f"  {colored(f'{file_name}:{line_num}: Missing file field', Colors.RED)}")
            errors += 1
            continue

        full_path = repo_root / file_path
        if entry_type == "directory":
            if not full_path.is_dir():
                if not quiet:
                    print(f"  {colored(f'{file_name}:{line_num}: Directory not found: {file_path}', Colors.RED)}")
                errors += 1
        else:
            if not full_path.is_file():
                if not quiet:
                    print(f"  {colored(f'{file_name}:{line_num}: File not found: {file_path}', Colors.RED)}")
                errors += 1

    if not quiet:
        if errors == 0:
            print(f"  {colored(f'{file_name}: [OK] ({entry_count} entries)', Colors.GREEN)}")
        else:
            print(f"  {colored(f'{file_name}: [FAIL] ({errors} errors)', Colors.RED)}")

    return errors


# =============================================================================
# Command: list-context
# =============================================================================

def cmd_list_context(args: argparse.Namespace) -> int:
    """List JSONL context entries."""
    repo_root = get_repo_root()
    target_dir = _resolve_task_dir(args.dir, repo_root)

    if not target_dir.is_dir():
        print(colored("Error: task directory required", Colors.RED))
        return 1

    print(colored("=== Context Files ===", Colors.BLUE))
    print()

    for jsonl_name in CONTEXT_JSONL_FILES:
        jsonl_file = target_dir / jsonl_name
        if not jsonl_file.is_file():
            continue

        print(colored(f"[{jsonl_name}]", Colors.CYAN))

        count = 0
        for _, line in _iter_jsonl_lines(jsonl_file):
            if not line.strip():
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            count += 1
            file_path = data.get("file", "?")
            entry_type = data.get("type", "file")
            reason = data.get("reason", "-")

            if entry_type == "directory":
                print(f"  {colored(f'{count}.', Colors.GREEN)} [DIR] {file_path}")
            else:
                print(f"  {colored(f'{count}.', Colors.GREEN)} {file_path}")
            print(f"     {colored('->', Colors.YELLOW)} {reason}")

        print()

    return 0


# =============================================================================
# Command: start / finish
# =============================================================================

def cmd_start(args: argparse.Namespace) -> int:
    """Set active task for this session."""
    repo_root = get_repo_root()
    task_input = args.dir

    if not task_input:
        print(colored("Error: task directory or name required", Colors.RED))
        return 1

    # Resolve task directory (supports task name, relative path, or absolute path)
    full_path = _resolve_task_dir(task_input, repo_root)

    if not full_path.is_dir():
        print(colored(f"Error: Task not found: {task_input}", Colors.RED))
        print(f"Hint: Use task name (e.g., 'my-task') or full path (e.g., '{DIR_WORKFLOW}/tasks/01-31-my-task')")
        return 1

    # 1. 先迁移旧 prd.md（在 blocker 检查之前，确保迁移后 blocker 校验正确）
    _migrate_prd_to_anchor(full_path)

    # 2. 再检查准备阻塞项
    blockers = _task_start_blockers(full_path)
    if blockers:
        print(colored("Error: Task is not ready to start yet", Colors.RED), file=sys.stderr)
        for blocker in blockers:
            print(f"  - {blocker}", file=sys.stderr)
        print(
            "Hint: write decision-anchor.md, run ./.cowork-flow/run task init-context <dir> <dev_type>, then retry",
            file=sys.stderr,
        )
        return 1

    validation_issues = _task_context_validation_issues(full_path, repo_root)
    if validation_issues:
        print(colored("Error: Task context validation failed", Colors.RED), file=sys.stderr)
        for issue in validation_issues:
            print(f"  - {issue}", file=sys.stderr)
        print(
            "Hint: run ./.cowork-flow/run task validate <dir> and fix the reported issues",
            file=sys.stderr,
        )
        return 1

    readiness_blockers = _optional_readiness_blockers(repo_root, full_path)
    if readiness_blockers:
        print(colored("Error: Task readiness failed", Colors.RED), file=sys.stderr)
        for blocker in readiness_blockers:
            print(f"  - {blocker}", file=sys.stderr)
        print(
            "Hint: run ./.cowork-flow/run task next <dir> and complete the reported readiness artifacts",
            file=sys.stderr,
        )
        return 1

    if getattr(args, "auto", False):
        from common.task.batch_mode import run_batch_entry
        return run_batch_entry(repo_root, full_path, args)

    state_blockers = transition_blockers(_load_task_status(full_path), "in_progress")
    if state_blockers:
        _print_transition_blockers(state_blockers)
        return 1

    gate_runner = GateRunner(repo_root)
    gate_result = gate_runner.run("task_start", full_path)
    if gate_result.blocked:
        return _report_gate_block(
            "Spec enforcement blocked task start",
            gate_result,
            gate_runner,
        )

    task_json_path = full_path / FILE_TASK_JSON
    task_data = _load_task_data_or_report(full_path)
    if task_data is None:
        return 1

    # Convert to relative path for storage
    try:
        task_dir = full_path.relative_to(repo_root).as_posix()
    except ValueError:
        task_dir = str(full_path)

    active = set_active_task(repo_root, task_dir)
    if active is None:
        print(
            colored(
                "Error: Missing session context. Set COWORK_FLOW_CONTEXT_ID or run inside a supported host session.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 1

    task_data["status"] = "in_progress"
    if not _write_json_or_report(task_json_path, task_data, "task metadata"):
        clear_active_task(repo_root)
        return 1

    print(colored(f"[OK] Active session task set to: {task_dir}", Colors.GREEN))
    print()
    print(colored("Fixed agents will load context from this task's jsonl files.", Colors.BLUE))

    _run_hooks("after_start", task_json_path, repo_root)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Mark a task ready for check/review."""
    repo_root = get_repo_root()
    execution_context = execution_context_from_namespace(args)
    task_dir = _resolve_status_task_dir(args, repo_root)
    if task_dir is None:
        return 1

    state_blockers = transition_blockers(_load_task_status(task_dir), "review")
    if state_blockers:
        _print_transition_blockers(state_blockers)
        return 1

    # Validate implementation against forbidden action rules
    try:
        from common.gates.validate_implementation import validate_implementation
        violations = validate_implementation(
            repo_root,
            task_dir,
            allow_spec_file_modifications=execution_context.is_coordinator,
        )
        gate_result = GateResult.from_violations("task_review", violations, task_dir)
        if gate_result.blocked:
            return _report_gate_block(
                "Implementation gate blocked task review",
                gate_result,
            )
        if gate_result.violations:
            print(colored("Warning: Implementation violations detected", Colors.YELLOW), file=sys.stderr)
            for v in gate_result.violations:
                print(f"  - {v['message']}", file=sys.stderr)
    except ImportError:
        pass

    try:
        from common.gates.tdd_evidence import validate_tdd_evidence

        tdd_result = GateResult.from_violations(
            "task_review_tdd",
            validate_tdd_evidence(task_dir),
            task_dir,
        )
        if tdd_result.blocked:
            return _report_gate_block(
                "TDD evidence gate blocked task review",
                tdd_result,
            )
    except ImportError:
        pass

    try:
        from common.gates.test_intent import validate_test_intent

        intent_result = GateResult.from_violations(
            "task_review_test_intent",
            validate_test_intent(repo_root, task_dir),
            task_dir,
        )
        if intent_result.blocked:
            return _report_gate_block(
                "Test intent gate blocked task review",
                intent_result,
            )
        _report_gate_warnings("Test intent review warnings", intent_result)
    except ImportError:
        pass

    gate_runner = GateRunner(repo_root)
    gate_result = gate_runner.run("task_review", task_dir)
    if gate_result.blocked:
        return _report_gate_block(
            "Coding standards gate blocked task review",
            gate_result,
            gate_runner,
        )

    # Get coding standards summary for Agent review
    try:
        from common.gates.validate_coding_standards import get_coding_standards_summary
        summary = get_coding_standards_summary(repo_root, task_dir)
        if summary:
            print(colored("Coding Standards to Verify:", Colors.CYAN))
            print(summary)
    except ImportError:
        pass

    if not _set_task_status(task_dir, "review"):
        return 1

    task_path = _display_task_path(repo_root, task_dir)
    print(colored(f"[OK] Task marked for check: {task_path}", Colors.GREEN))
    print(f"Next: ./.cowork-flow/run task next {task_path}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """Mark a task completed after final check."""
    repo_root = get_repo_root()
    task_dir = _resolve_status_task_dir(args, repo_root)
    if task_dir is None:
        return 1

    current_status = _load_task_status(task_dir)
    state_blockers = transition_blockers(current_status, "completed")
    if state_blockers:
        _print_transition_blockers(state_blockers)
        print(
            "Hint: run ./.cowork-flow/run task review <task-dir> to mark the task ready for check",
            file=sys.stderr,
        )
        return 1

    try:
        from common.gates.tdd_evidence import validate_tdd_evidence

        tdd_result = GateResult.from_violations(
            "task_complete_tdd",
            validate_tdd_evidence(task_dir),
            task_dir,
        )
        if tdd_result.blocked:
            return _report_gate_block(
                "TDD evidence gate blocked task completion",
                tdd_result,
            )
    except ImportError:
        pass

    try:
        from common.gates.test_intent import validate_test_intent

        intent_result = GateResult.from_violations(
            "task_complete_test_intent",
            validate_test_intent(repo_root, task_dir),
            task_dir,
        )
        if intent_result.blocked:
            return _report_gate_block(
                "Test intent gate blocked task completion",
                intent_result,
            )
        _report_gate_warnings("Test intent completion warnings", intent_result)
    except ImportError:
        pass

    gate_runner = GateRunner(repo_root)
    gate_result = gate_runner.run("task_complete", task_dir)
    if gate_result.blocked:
        return _report_gate_block(
            "Spec enforcement blocked task completion",
            gate_result,
            gate_runner,
        )

    today = datetime.now().strftime("%Y-%m-%d")
    if not _set_task_status(task_dir, "completed", completed_at=today):
        return 1

    task_path = _display_task_path(repo_root, task_dir)
    print(colored(f"[OK] Task marked completed: {task_path}", Colors.GREEN))
    print(f"Next: ./.cowork-flow/run task next {task_path}")
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    """Clear active task for this session."""
    repo_root = get_repo_root()
    active = get_active_task(repo_root)

    if not active.task_path:
        print(colored("No active task set for this session", Colors.YELLOW))
        return 0

    # Resolve task.json path before clearing
    task_json_path = repo_root / active.task_path / FILE_TASK_JSON
    clear_active_task(repo_root)

    print(colored(f"[OK] Cleared active session task (was: {active.task_path})", Colors.GREEN))

    if task_json_path.is_file():
        _run_hooks("after_finish", task_json_path, repo_root)
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    """Show active session task."""
    repo_root = get_repo_root()
    active = get_active_task(repo_root)
    if not active.context_key:
        print(
            colored(
                "Error: Missing session context. Set COWORK_FLOW_CONTEXT_ID or run inside a supported host session.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        return 1
    if not active.task_path:
        print("Active task: (none)")
        return 0
    print(f"Active task: {active.task_path}")
    print(f"Source: {active.source}:{active.context_key}")
    return 0


def _display_task_path(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _load_task_status(task_dir: Path) -> str:
    task_json = task_dir / FILE_TASK_JSON
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "stale"
    status = data.get("status") if isinstance(data, dict) else None
    return status.strip() if isinstance(status, str) and status.strip() else "unknown"


def _load_task_data_or_report(task_dir: Path) -> dict | None:
    task_json = task_dir / FILE_TASK_JSON
    data = _read_json_file(task_json)
    if data is None:
        print(colored(f"Error: Failed to read task metadata: {task_json}", Colors.RED), file=sys.stderr)
        return None
    return data


def _set_task_status(task_dir: Path, status: str, completed_at: str | None = None) -> bool:
    task_json = task_dir / FILE_TASK_JSON
    data = _load_task_data_or_report(task_dir)
    if data is None:
        return False

    data["status"] = status
    if status in DONE_STATUSES:
        data["completedAt"] = completed_at or datetime.now().strftime("%Y-%m-%d")

    return _write_json_or_report(task_json, data, "task metadata")


def _resolve_status_task_dir(args: argparse.Namespace, repo_root: Path) -> Path | None:
    target_input = getattr(args, "dir", None)
    if target_input:
        task_dir = _resolve_task_dir(target_input, repo_root)
    else:
        active = get_active_task(repo_root)
        if not active.context_key:
            print(
                colored(
                    "Error: Missing session context. Set COWORK_FLOW_CONTEXT_ID or pass a task dir.",
                    Colors.RED,
                ),
                file=sys.stderr,
            )
            return None
        if not active.task_path:
            print(colored("Error: No active task set for this session", Colors.RED), file=sys.stderr)
            return None
        task_dir = repo_root / active.task_path

    if not task_dir.is_dir():
        print(colored(f"Error: Task not found: {target_input or task_dir}", Colors.RED), file=sys.stderr)
        return None
    if not (task_dir / FILE_TASK_JSON).is_file():
        print(colored(f"Error: task.json not found: {task_dir}", Colors.RED), file=sys.stderr)
        return None
    return task_dir


def _optional_readiness_blockers(repo_root: Path, task_dir: Path) -> list[str]:
    try:
        from common.task.readiness import task_readiness_blockers  # type: ignore[import-not-found]
    except Exception:
        return []
    try:
        blockers = task_readiness_blockers(repo_root, task_dir)
    except Exception:
        return ["readiness check failed; run task validate and inspect linked change"]
    return [str(blocker) for blocker in blockers if str(blocker).strip()]


def _task_next_blockers(repo_root: Path, task_dir: Path) -> list[str]:
    blockers = _task_start_blockers(task_dir)
    blockers.extend(_task_context_validation_issues(task_dir, repo_root, quiet=True))
    blockers.extend(_optional_readiness_blockers(repo_root, task_dir))
    status = _load_task_status(task_dir)
    gate_runner = GateRunner(repo_root)
    if status == "planning":
        blockers.extend(_gate_blocker_messages(gate_runner.run("task_start", task_dir)))
    elif status in CHECK_STATUSES:
        blockers.extend(_gate_blocker_messages(gate_runner.run("task_complete", task_dir)))
    return blockers


def _print_tdd_next_reminder(task_path: str) -> None:
    print(
        "TDD reminder: for behavior changes, write a failing test and record "
        f"red evidence in {task_path}/tdd.jsonl before modifying code."
    )


def _print_blockers(blockers: list[str]) -> None:
    if not blockers:
        print("Blockers: none")
        return
    print("Blockers:")
    for blocker in blockers:
        print(f"  - {blocker}")


def _is_git_dirty(repo_root: Path) -> bool:
    """Check if the git working tree has uncommitted changes."""
    try:
        rc, _, _ = _run_git_command(
            ["status", "--porcelain"], cwd=repo_root
        )
        return rc != 0
    except (OSError, Exception):
        return False


def _linked_active_changes_for_task(repo_root: Path, task_dir: Path) -> list[str]:
    from commands.change import linked_active_changes_for_task

    return linked_active_changes_for_task(repo_root, (task_dir,))


def _linked_changes_ready_for_archive(repo_root: Path, slugs: list[str]) -> bool:
    from commands.change import validate_change

    ready = True
    for slug in slugs:
        if not validate_change(repo_root, slug, quiet=True):
            print(
                colored(f"Error: Linked change is not ready to archive: {slug}", Colors.RED),
                file=sys.stderr,
            )
            ready = False
    return ready


def _archive_linked_changes(repo_root: Path, slugs: list[str]) -> bool:
    from commands.change import archive_change_by_slug

    for slug in slugs:
        if archive_change_by_slug(repo_root, slug) is None:
            print(
                colored(f"Error: Failed to archive linked change: {slug}", Colors.RED),
                file=sys.stderr,
            )
            return False
        print(colored(f"Archived linked change: {slug}", Colors.GREEN), file=sys.stderr)
    return True


def cmd_next(args: argparse.Namespace) -> int:
    """Print the next safe workflow action without mutating state."""
    repo_root = get_repo_root()
    target_input = getattr(args, "dir", None)
    is_active_task = False

    print("Workflow Next")
    if target_input:
        task_dir = _resolve_task_dir(target_input, repo_root)
        task_path = _display_task_path(repo_root, task_dir)
        source = "argument"
    else:
        active = get_active_task(repo_root)
        source = f"{active.source}:{active.context_key or '-'}"
        if not active.task_path:
            print("Status: no_task")
            print(f"Source: {source}")
            print("Next action: create or start a task before repository changes")
            print('Command: ./.cowork-flow/run task create "<title>" --slug <task-name>')
            print("Then: ./.cowork-flow/run task start <task-dir>")
            print("Runtime-context subagent state is injected by hook/plugin; do not infer it from prompt text.")
            return 0
        task_path = active.task_path
        task_dir = repo_root / task_path
        is_active_task = True

    print(f"Task: {task_path}")
    if not task_dir.is_dir():
        print("Status: stale")
        print(f"Source: {source}")
        print("Next action: clear or replace the missing active task")
        print("Command: ./.cowork-flow/run task list")
        print("Blockers:")
        print(f"  - task directory not found: {task_path}")
        return 0

    status = _load_task_status(task_dir)
    blockers = _task_next_blockers(repo_root, task_dir)
    print(f"Status: {status}")
    print(f"Source: {source}")

    if status == "planning":
        if blockers:
            print("Next action: finish planning prerequisites before starting task")
            print(f"Command: ./.cowork-flow/run task init-context {task_path} <dev_type>")
            print(f"Then: ./.cowork-flow/run task start {task_path}")
        elif is_active_task:
            print("Next action: execute implementation plan")
            _print_tdd_next_reminder(task_path)
            print(
                f"Command: ./.cowork-flow/run subagent init --role implement "
                f"--agent-type cowork-implement --execution-task-dir {task_path} "
                f"--title \"Implement {Path(task_path).name}\""
            )
            print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter")
            print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
            print("Then: verify status=bound and bound_context_key before accepting output")
            print(f"Then: wait, verify output, close runtime context, then ./.cowork-flow/run task review {task_path}")
        else:
            print("Next action: start task")
            print(f"Command: ./.cowork-flow/run task start {task_path}")
        _print_blockers(blockers)
        return 0

    if status == "in_progress":
        print("Next action: execute implementation plan")
        _print_tdd_next_reminder(task_path)
        print(
            f"Command: ./.cowork-flow/run subagent init --role implement "
            f"--agent-type cowork-implement --execution-task-dir {task_path} "
            f"--title \"Implement {Path(task_path).name}\""
        )
        print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter")
        print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
        print("Then: verify status=bound and bound_context_key before accepting output")
        print(f"Then: wait, verify output, close runtime context, then ./.cowork-flow/run task review {task_path}")
        _print_blockers(blockers)
        return 0

    if status in CHECK_STATUSES:
        print("Next action: verify implementation")
        print(
            f"Command: ./.cowork-flow/run subagent init --role check "
            f"--agent-type cowork-check --execution-task-dir {task_path} "
            f"--title \"Check {Path(task_path).name}\""
        )
        print("Then: pass cowork_runtime_context_id and cowork_host_context_key through the active Host Adapter or run equivalent inline check")
        print("Then: child first step runs ./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>")
        print("Then: verify status=bound and bound_context_key before accepting output")
        print(f"Then: ./.cowork-flow/run task complete {task_path}")
        _print_blockers(blockers)
        return 0

    if status in DONE_STATUSES:
        print("Next action: finalize, archive, commit, and record session")
        print("Command: git status --short")
        linked_changes = _linked_active_changes_for_task(repo_root, task_dir)
        print(f"Then: ./.cowork-flow/run task archive {Path(task_path).name}")
        for slug in linked_changes:
            print(f"Then: ./.cowork-flow/run change archive {slug} (handled by task archive)")
        _print_blockers(blockers)
        return 0

    print("Next action: inspect task status and repair workflow state")
    print(f"Command: ./.cowork-flow/run task validate {task_path}")
    _print_blockers(blockers)
    return 0


# =============================================================================
# Command: archive
# =============================================================================

def cmd_archive(args: argparse.Namespace) -> int:
    """Archive completed task and linked changes."""
    repo_root = get_repo_root()
    task_name = args.name

    if not task_name:
        print(colored("Error: Task name is required", Colors.RED), file=sys.stderr)
        return 1

    tasks_dir = get_tasks_dir(repo_root)

    # Find task directory
    task_dir = find_task_by_name(task_name, tasks_dir)

    if not task_dir or not task_dir.is_dir():
        print(colored(f"Error: Task not found: {task_name}", Colors.RED), file=sys.stderr)
        print("Active tasks:", file=sys.stderr)
        cmd_list(argparse.Namespace(mine=False, status=None))
        return 1

    dir_name = task_dir.name
    task_json_path = task_dir / FILE_TASK_JSON

    today = datetime.now().strftime("%Y-%m-%d")
    task_data = None
    if task_json_path.is_file():
        task_data = _read_json_file(task_json_path)

    # Guard: only completed tasks can be archived
    if task_data is None:
        print(colored(
            f"Error: Task '{task_name}' task.json is unreadable — refusing archive.",
            Colors.RED,
        ), file=sys.stderr)
        return 1
    current_status = task_data.get("status", "unknown")
    if current_status not in DONE_STATUSES:
        print(colored(
            f"Error: Task '{task_name}' is in status '{current_status}', not in {DONE_STATUSES}. "
            "Run `task complete` first, then retry archive.",
            Colors.RED,
        ), file=sys.stderr)
        return 1

    linked_changes = _linked_active_changes_for_task(repo_root, task_dir)
    if linked_changes and not _linked_changes_ready_for_archive(repo_root, linked_changes):
        return 1

    # R-WF-011: warn if uncommitted changes detected (archive should come before commit)
    if _is_git_dirty(repo_root):
        print(colored(
            "Warning: Uncommitted changes detected. "
            "Archive the task first, then commit the archived result.",
            Colors.YELLOW,
        ), file=sys.stderr)

    # Archive
    result = archive_task_complete(task_dir, repo_root)
    if "archived_to" not in result:
        return 1

    archive_dest = Path(result["archived_to"])
    if not _finalize_archived_task_metadata(
        archive_dest,
        task_data,
        tasks_dir,
        dir_name,
        today,
    ):
        _rollback_archived_task_or_report(
            task_dir,
            archive_dest,
            task_data,
        )
        return 1

    clear_task_from_sessions(repo_root, f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}")

    archived_json = archive_dest / FILE_TASK_JSON
    year_month = archive_dest.parent.name
    print(colored(f"Archived: {dir_name} -> archive/{year_month}/", Colors.GREEN), file=sys.stderr)

    if linked_changes and not _archive_linked_changes(repo_root, linked_changes):
        return 1

    # Auto-commit only when explicitly requested.
    if getattr(args, "commit", False):
        _auto_commit_archive(dir_name, repo_root)

    # Return the archive path
    print(f"{DIR_WORKFLOW}/{DIR_TASKS}/{DIR_ARCHIVE}/{year_month}/{dir_name}")

    # Run hooks with the archived path
    _run_hooks("after_archive", archived_json, repo_root)
    return 0


def _auto_commit_archive(task_name: str, repo_root: Path) -> None:
    """Stage task/change archive changes and commit after archive."""
    tasks_rel = f"{DIR_WORKFLOW}/{DIR_TASKS}"
    changes_rel = f"{DIR_WORKFLOW}/{DIR_CHANGES}"
    archive_rels = [
        rel
        for rel in (tasks_rel, changes_rel)
        if (repo_root / rel).exists()
    ]
    _run_git_command(["add", "-A", *archive_rels], cwd=repo_root)

    # Check if there are staged changes
    rc, _, _ = _run_git_command(
        ["diff", "--cached", "--quiet", "--", *archive_rels], cwd=repo_root
    )
    if rc == 0:
        print("[OK] No task changes to commit.", file=sys.stderr)
        return

    commit_msg = f"chore(task): archive {task_name}"
    rc, _, err = _run_git_command(["commit", "-m", commit_msg], cwd=repo_root)
    if rc == 0:
        print(f"[OK] Auto-committed: {commit_msg}", file=sys.stderr)
    else:
        print(f"[WARN] Auto-commit failed: {err.strip()}", file=sys.stderr)


# =============================================================================
# Command: add-subtask
# =============================================================================

def cmd_add_subtask(args: argparse.Namespace) -> int:
    """Link a child task to a parent task."""
    repo_root = get_repo_root()

    parent_dir = _resolve_task_dir(args.parent_dir, repo_root)
    child_dir = _resolve_task_dir(args.child_dir, repo_root)

    parent_json_path = parent_dir / FILE_TASK_JSON
    child_json_path = child_dir / FILE_TASK_JSON

    if not parent_json_path.is_file():
        print(colored(f"Error: Parent task.json not found: {args.parent_dir}", Colors.RED), file=sys.stderr)
        return 1

    if not child_json_path.is_file():
        print(colored(f"Error: Child task.json not found: {args.child_dir}", Colors.RED), file=sys.stderr)
        return 1

    parent_data = _read_json_file(parent_json_path)
    child_data = _read_json_file(child_json_path)

    if not parent_data or not child_data:
        print(colored("Error: Failed to read task.json", Colors.RED), file=sys.stderr)
        return 1

    # Check if child already has a parent
    existing_parent = child_data.get("parent")
    if existing_parent:
        print(colored(f"Error: Child task already has a parent: {existing_parent}", Colors.RED), file=sys.stderr)
        return 1

    # Add child to parent's children list
    parent_children = parent_data.get("children", [])
    child_dir_name = child_dir.name
    if child_dir_name not in parent_children:
        parent_children.append(child_dir_name)
        parent_data["children"] = parent_children

    # Set parent in child's task.json
    child_data["parent"] = parent_dir.name

    # Write both
    _write_json_file(parent_json_path, parent_data)
    _write_json_file(child_json_path, child_data)

    print(colored(f"Linked: {child_dir.name} -> {parent_dir.name}", Colors.GREEN), file=sys.stderr)
    return 0


# =============================================================================
# Command: remove-subtask
# =============================================================================

def cmd_remove_subtask(args: argparse.Namespace) -> int:
    """Unlink a child task from a parent task."""
    repo_root = get_repo_root()

    parent_dir = _resolve_task_dir(args.parent_dir, repo_root)
    child_dir = _resolve_task_dir(args.child_dir, repo_root)

    parent_json_path = parent_dir / FILE_TASK_JSON
    child_json_path = child_dir / FILE_TASK_JSON

    if not parent_json_path.is_file():
        print(colored(f"Error: Parent task.json not found: {args.parent_dir}", Colors.RED), file=sys.stderr)
        return 1

    if not child_json_path.is_file():
        print(colored(f"Error: Child task.json not found: {args.child_dir}", Colors.RED), file=sys.stderr)
        return 1

    parent_data = _read_json_file(parent_json_path)
    child_data = _read_json_file(child_json_path)

    if not parent_data or not child_data:
        print(colored("Error: Failed to read task.json", Colors.RED), file=sys.stderr)
        return 1

    # Remove child from parent's children list
    parent_children = parent_data.get("children", [])
    child_dir_name = child_dir.name
    if child_dir_name in parent_children:
        parent_children.remove(child_dir_name)
        parent_data["children"] = parent_children

    # Clear parent in child's task.json
    child_data["parent"] = None

    # Write both
    _write_json_file(parent_json_path, parent_data)
    _write_json_file(child_json_path, child_data)

    print(colored(f"Unlinked: {child_dir.name} from {parent_dir.name}", Colors.GREEN), file=sys.stderr)
    return 0


# =============================================================================
# Command: list
# =============================================================================

def _get_children_progress(children: list[str], all_tasks: dict[str, dict]) -> str:
    """Get children progress summary like '[2/3 done]'."""
    if not children:
        return ""
    done_count = 0
    total = len(children)
    for child_name in children:
        status = all_tasks.get(child_name, {}).get("status", "")
        if status in DONE_STATUSES:
            done_count += 1
    return f" [{done_count}/{total} done]"


def cmd_list(args: argparse.Namespace) -> int:
    """List active tasks."""
    repo_root = get_repo_root()
    tasks_dir = get_tasks_dir(repo_root)
    active_task = get_active_task(repo_root).task_path
    developer = get_developer(repo_root)
    filter_mine = args.mine
    filter_status = args.status

    if filter_mine:
        if not developer:
            print(colored("Error: No developer set. Run init_developer.py first", Colors.RED), file=sys.stderr)
            return 1
        print(colored(f"My tasks (assignee: {developer}):", Colors.BLUE))
    else:
        print(colored("All active tasks:", Colors.BLUE))
    print()

    all_tasks = _load_task_summaries(tasks_dir)

    # Second pass: display tasks hierarchically
    count = 0

    def _print_task(dir_name: str, indent: int = 0) -> None:
        nonlocal count
        info = all_tasks[dir_name]
        status = info["status"]
        assignee = info["assignee"]
        children = info["children"]

        # Apply --mine filter
        if filter_mine and assignee != developer:
            return

        # Apply --status filter
        if filter_status and status != filter_status:
            return

        relative_path = f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}"
        marker = ""
        if relative_path == active_task:
            marker = f" {colored('<- active', Colors.GREEN)}"

        # Children progress
        progress = _get_children_progress(children, all_tasks) if children else ""

        prefix = "  " * indent + "  - "

        if filter_mine:
            print(f"{prefix}{dir_name}/ ({status}){progress}{marker}")
        else:
            print(f"{prefix}{dir_name}/ ({status}){progress} [{colored(assignee, Colors.CYAN)}]{marker}")
        count += 1

        # Print children indented
        for child_name in children:
            if child_name in all_tasks:
                _print_task(child_name, indent + 1)

    # Display only top-level tasks (those without a parent)
    for dir_name in sorted(all_tasks.keys()):
        info = all_tasks[dir_name]
        if not info["parent"]:
            _print_task(dir_name)

    if count == 0:
        if filter_mine:
            print("  (no tasks assigned to you)")
        else:
            print("  (no active tasks)")

    print()
    print(f"Total: {count} task(s)")
    return 0


# =============================================================================
# Command: list-archive
# =============================================================================

def cmd_list_archive(args: argparse.Namespace) -> int:
    """List archived tasks."""
    repo_root = get_repo_root()
    tasks_dir = get_tasks_dir(repo_root)
    archive_dir = tasks_dir / "archive"
    month = args.month

    print(colored("Archived tasks:", Colors.BLUE))
    print()

    if month:
        month_dir = archive_dir / month
        if month_dir.is_dir():
            print(f"[{month}]")
            for d in sorted(month_dir.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}/")
        else:
            print(f"  No archives for {month}")
    else:
        if archive_dir.is_dir():
            for month_dir in sorted(archive_dir.iterdir()):
                if month_dir.is_dir():
                    month_name = month_dir.name
                    count = sum(1 for d in month_dir.iterdir() if d.is_dir())
                    print(f"[{month_name}] - {count} task(s)")

    return 0


# =============================================================================
# Help
# =============================================================================

def show_usage() -> None:
    """Show usage help."""
    print("""Task Management Script for cowork-flow workflow

Usage:
  ./.cowork-flow/run task create <title>                     Create new task directory
  ./.cowork-flow/run task create <title> --parent <dir>      Create task as child of parent
  ./.cowork-flow/run task init-context <dir> <dev_type>      Initialize jsonl files
  ./.cowork-flow/run task add-context <dir> <jsonl> <path> [reason]  Add entry to jsonl
  ./.cowork-flow/run task validate <dir>                     Validate jsonl files
  ./.cowork-flow/run task list-context <dir>                 List jsonl entries
  ./.cowork-flow/run task start <dir>                        Set active session task
  ./.cowork-flow/run task review [dir]                       Mark task ready for check
  ./.cowork-flow/run task complete [dir]                     Mark task completed
  ./.cowork-flow/run task finish                             Clear active session task
  ./.cowork-flow/run task next [dir]                         Show next safe workflow action
  ./.cowork-flow/run task archive <task-name>                Archive completed task and linked changes
  ./.cowork-flow/run task add-subtask <parent> <child>       Link child task to parent
  ./.cowork-flow/run task remove-subtask <parent> <child>    Unlink child from parent
  ./.cowork-flow/run task list [--mine] [--status <status>]  List tasks
  ./.cowork-flow/run task list-archive [YYYY-MM]             List archived tasks

Arguments:
  dev_type: backend | frontend | fullstack | test | docs

List options:
  --mine, -m           Show only tasks assigned to current developer
  --status, -s <s>     Filter by status (planning, in_progress, review, completed)

Examples:
  ./.cowork-flow/run task create "Add login feature" --slug add-login
  ./.cowork-flow/run task create "Child task" --slug child --parent .cowork-flow/tasks/01-21-parent
  ./.cowork-flow/run task init-context .cowork-flow/tasks/01-21-add-login backend
  ./.cowork-flow/run task next
  ./.cowork-flow/run task add-context <dir> implement .cowork-flow/spec/backend/auth.md "Auth guidelines"
  ./.cowork-flow/run task start .cowork-flow/tasks/01-21-add-login
  ./.cowork-flow/run task review
  ./.cowork-flow/run task complete
  ./.cowork-flow/run task finish
  ./.cowork-flow/run task archive add-login
  ./.cowork-flow/run task add-subtask parent-task child-task  # Link existing tasks
  ./.cowork-flow/run task remove-subtask parent-task child-task
  ./.cowork-flow/run task list                               # List all active tasks
  ./.cowork-flow/run task list --mine                        # List my tasks only
  ./.cowork-flow/run task list --mine --status in_progress   # List my in-progress tasks
""")


# =============================================================================
# Main Entry
# =============================================================================

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Task Management Script for cowork-flow workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[build_internal_execution_context_parser()],
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # create
    p_create = subparsers.add_parser("create", help="Create new task")
    p_create.add_argument("title", help="Task title")
    p_create.add_argument("--slug", "-s", help="Task slug")
    p_create.add_argument("--assignee", "-a", help="Assignee developer")
    p_create.add_argument("--priority", "-p", default="P2", help="Priority (P0-P3)")
    p_create.add_argument("--description", "-d", help="Task description")
    p_create.add_argument("--parent", help="Parent task directory (establishes subtask link)")
    p_create.add_argument("--from-plan", "-f", help="Path to plan file (auto-generate decision-anchor skeleton)")

    # init-context
    p_init = subparsers.add_parser("init-context", help="Initialize context files")
    p_init.add_argument("dir", help="Task directory")
    p_init.add_argument("type", help="Dev type: backend|frontend|fullstack|test|docs")

    # add-context
    p_add = subparsers.add_parser("add-context", help="Add context entry")
    p_add.add_argument("dir", help="Task directory")
    p_add.add_argument("file", help="JSONL file (implement|check|debug)")
    p_add.add_argument("path", help="File path to add")
    p_add.add_argument("reason", nargs="?", help="Reason for adding")

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate context files")
    p_validate.add_argument("dir", help="Task directory")

    # list-context
    p_listctx = subparsers.add_parser("list-context", help="List context entries")
    p_listctx.add_argument("dir", help="Task directory")

    # start
    p_start = subparsers.add_parser("start", help="Set active session task")
    p_start.add_argument("dir", help="Task directory")
    p_start.add_argument("--auto", action="store_true",
                         help="Enable batch mode (requires --approved)")
    p_start.add_argument("--approved", action="store_true",
                         help="User has approved the plan")

    # current
    subparsers.add_parser("current", help="Show active session task")

    # review
    p_review = subparsers.add_parser("review", help="Mark task ready for check")
    p_review.add_argument("dir", nargs="?", help="Task directory or name")

    # complete
    p_complete = subparsers.add_parser("complete", help="Mark task completed")
    p_complete.add_argument("dir", nargs="?", help="Task directory or name")

    # next
    p_next = subparsers.add_parser("next", help="Show next safe workflow action")
    p_next.add_argument("dir", nargs="?", help="Task directory or name")

    # finish
    subparsers.add_parser("finish", help="Clear active session task")

    # archive
    p_archive = subparsers.add_parser("archive", help="Archive task")
    p_archive.add_argument("name", help="Task name")
    p_archive.add_argument("--commit", action="store_true", help="Auto git commit after archive")
    # list
    p_list = subparsers.add_parser("list", help="List tasks")
    p_list.add_argument("--mine", "-m", action="store_true", help="My tasks only")
    p_list.add_argument("--status", "-s", help="Filter by status")

    # add-subtask
    p_addsub = subparsers.add_parser("add-subtask", help="Link child task to parent")
    p_addsub.add_argument("parent_dir", help="Parent task directory")
    p_addsub.add_argument("child_dir", help="Child task directory")

    # remove-subtask
    p_rmsub = subparsers.add_parser("remove-subtask", help="Unlink child task from parent")
    p_rmsub.add_argument("parent_dir", help="Parent task directory")
    p_rmsub.add_argument("child_dir", help="Child task directory")

    # list-archive
    p_listarch = subparsers.add_parser("list-archive", help="List archived tasks")
    p_listarch.add_argument("month", nargs="?", help="Month (YYYY-MM)")

    args = parser.parse_args()
    execution_context = execution_context_from_namespace(args)

    if not args.command:
        show_usage()
        return 1

    worker_blocked_commands = {
        "create",
        "init-context",
        "add-context",
        "start",
        "review",
        "complete",
        "finish",
        "archive",
        "add-subtask",
        "remove-subtask",
    }
    if execution_context.is_worker and args.command in worker_blocked_commands:
        print(
            worker_command_block_message(
                execution_context,
                f"task {args.command}",
                "Workers must not activate, archive, or mutate cowork-flow task state.",
            ),
            file=sys.stderr,
        )
        return 2

    commands = {
        "create": cmd_create,
        "init-context": cmd_init_context,
        "add-context": cmd_add_context,
        "validate": cmd_validate,
        "list-context": cmd_list_context,
        "start": cmd_start,
        "current": cmd_current,
        "review": cmd_review,
        "complete": cmd_complete,
        "next": cmd_next,
        "finish": cmd_finish,
        "archive": cmd_archive,
        "add-subtask": cmd_add_subtask,
        "remove-subtask": cmd_remove_subtask,
        "list": cmd_list,
        "list-archive": cmd_list_archive,
    }

    if args.command in commands:
        return commands[args.command](args)
    else:
        show_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())
