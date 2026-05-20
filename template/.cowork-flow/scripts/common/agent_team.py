"""Helpers for the cowork-flow agent team runtime."""

from __future__ import annotations

import json
import re
from pathlib import Path


TASK_RE = re.compile(r"^### Task\s+(\d+):\s*(.+?)\s*$")
FILE_RE = re.compile(r"^-\s+(Create|Modify|Test):\s+`([^`]+)`")
DEP_RE = re.compile(r"depends on Task\s+(\d+)", re.IGNORECASE)


def parse_plan(text: str) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        task_match = TASK_RE.match(line)
        if task_match:
            current = {
                "number": int(task_match.group(1)),
                "id": f"T{int(task_match.group(1)):03d}",
                "title": task_match.group(2),
                "files": [],
                "steps": [],
                "commands": [],
                "explicit_dependencies": [],
            }
            tasks.append(current)
            continue

        if current is None:
            continue

        file_match = FILE_RE.match(line.strip())
        if file_match:
            current["files"].append(
                {
                    "kind": file_match.group(1).lower(),
                    "path": file_match.group(2),
                }
            )
            continue

        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            current["steps"].append(stripped)
            continue

        if stripped.startswith("Run:"):
            current["commands"].append(stripped.removeprefix("Run:").strip())

        dep_match = DEP_RE.search(stripped)
        if dep_match:
            current["explicit_dependencies"].append(f"T{int(dep_match.group(1)):03d}")

    return tasks


def _task_files(task: dict[str, object]) -> set[str]:
    files = task.get("files", [])
    if not isinstance(files, list):
        return set()
    paths = set()
    for item in files:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            paths.add(item["path"])
    return paths


def _task_dependencies(tasks: list[dict[str, object]]) -> list[dict[str, str]]:
    dependencies: list[dict[str, str]] = []
    for index, task in enumerate(tasks):
        task_id = str(task["id"])
        task_files = _task_files(task)

        explicit = task.get("explicit_dependencies", [])
        if isinstance(explicit, list):
            for dependency in explicit:
                dependencies.append(
                    {
                        "task": task_id,
                        "depends_on_task": str(dependency),
                        "reason": "explicit",
                    }
                )

        for previous in tasks[:index]:
            previous_files = _task_files(previous)
            if task_files.intersection(previous_files):
                dependencies.append(
                    {
                        "task": task_id,
                        "depends_on_task": str(previous["id"]),
                        "reason": "file-overlap",
                    }
                )

    return dependencies


def _role_agent(role: str) -> tuple[str, str]:
    if role == "implementer":
        return ("implementer", "worker")
    if role == "spec-reviewer":
        return ("spec-reviewer", "default")
    return ("quality-reviewer", "default")


def build_dispatch_plan(tasks: list[dict[str, object]]) -> dict[str, object]:
    assignments: list[dict[str, object]] = []
    task_dependencies = _task_dependencies(tasks)
    dependency_lookup: dict[str, list[str]] = {}
    for dependency in task_dependencies:
        dependency_lookup.setdefault(dependency["task"], []).append(dependency["depends_on_task"])

    for task in tasks:
        task_id = str(task["id"])
        task_dependency_assignments = [
            f"{dependency}-quality-reviewer"
            for dependency in dependency_lookup.get(task_id, [])
        ]
        chain = [
            ("implementer", task_dependency_assignments),
            ("spec-reviewer", [f"{task_id}-implementer"]),
            ("quality-reviewer", [f"{task_id}-spec-reviewer"]),
        ]
        for role, depends_on in chain:
            agent, codex_type = _role_agent(role)
            assignments.append(
                {
                    "id": f"{task_id}-{role}",
                    "task": task_id,
                    "title": task["title"],
                    "role": role,
                    "recommended_agent": agent,
                    "codex_type": codex_type,
                    "depends_on": depends_on,
                    "files": task.get("files", []),
                    "steps": task.get("steps", []),
                    "commands": task.get("commands", []),
                }
            )

    return {
        "version": 1,
        "adapter": "codex",
        "tasks": tasks,
        "task_dependencies": task_dependencies,
        "assignments": assignments,
    }


def render_dispatch_plan(dispatch_plan: dict[str, object]) -> str:
    lines = [
        "version: 1",
        f"adapter: {dispatch_plan['adapter']}",
        "task_dependencies:",
    ]
    for dependency in dispatch_plan["task_dependencies"]:
        lines.extend(
            [
                f"  - task: {dependency['task']}",
                f"    depends_on_task: {dependency['depends_on_task']}",
                f"    reason: {dependency['reason']}",
            ]
        )
    lines.append("assignments:")
    for assignment in dispatch_plan["assignments"]:
        lines.extend(
            [
                f"  - id: {assignment['id']}",
                f"    task: {assignment['task']}",
                f"    role: {assignment['role']}",
                f"    recommended_agent: {assignment['recommended_agent']}",
                f"    codex_type: {assignment['codex_type']}",
                "    depends_on:",
            ]
        )
        depends_on = assignment.get("depends_on", [])
        if depends_on:
            for dependency in depends_on:
                lines.append(f"      - {dependency}")
        else:
            lines.append("      - none")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_initial_status(dispatch_plan: dict[str, object]) -> dict[str, object]:
    assignments: dict[str, dict[str, object]] = {}
    for assignment in dispatch_plan["assignments"]:
        depends_on = [
            dependency
            for dependency in assignment.get("depends_on", [])
            if dependency != "none"
        ]
        assignments[assignment["id"]] = {
            "status": "ready" if not depends_on else "pending",
            "attempts": 0,
            "depends_on": depends_on,
            "role": assignment["role"],
            "task": assignment["task"],
            "recommended_agent": assignment["recommended_agent"],
            "codex_type": assignment["codex_type"],
        }

    return {"version": 1, "current_batch": 1, "assignments": assignments}


def build_initial_metrics(dispatch_plan: dict[str, object]) -> dict[str, object]:
    return {
        "assignments": len(dispatch_plan["assignments"]),
        "attempts": 0,
        "successfulAssignments": 0,
        "failedAssignments": 0,
        "reviewReworks": 0,
        "agents": {},
    }


def render_assignment_prompt(assignment: dict[str, object]) -> str:
    return "\n".join(
        [
            f"# {assignment['id']}",
            "",
            f"Role: {assignment['role']}",
            f"Recommended agent: {assignment['recommended_agent']}",
            f"Codex type: {assignment['codex_type']}",
            "",
            "You are not alone in this codebase. Respect the write boundary, do not revert other agents' edits, and report changed files.",
            "",
        ]
    )
