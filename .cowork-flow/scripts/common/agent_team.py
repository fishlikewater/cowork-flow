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


DEFAULT_ROLE_TYPES = {
    "implementer": "worker",
    "spec-reviewer": "default",
    "quality-reviewer": "default",
}

ROLE_CAPABILITIES = {
    "implementer": {"implementation", "test-writing"},
    "spec-reviewer": {"spec-review", "acceptance-check"},
    "quality-reviewer": {"code-quality-review", "test-review", "verification"},
}

ROLE_TASK_TYPES = {
    "implementer": {"code", "test"},
    "spec-reviewer": {"review", "documentation"},
    "quality-reviewer": {"review", "verification"},
}


def _role_config(registry: dict[str, object] | None, role: str) -> dict[str, object]:
    agents = registry.get("agents", {}) if registry else {}
    if not isinstance(agents, dict):
        return {}
    config = agents.get(role, {})
    return config if isinstance(config, dict) else {}


def _ensure_agent_config(registry: dict[str, object], role: str) -> dict[str, object]:
    agents = registry.setdefault("agents", {})
    if not isinstance(agents, dict):
        registry["agents"] = {}
        agents = registry["agents"]
    config = agents.setdefault(role, {})
    if not isinstance(config, dict):
        agents[role] = {}
        config = agents[role]
    return config


def _parse_list_item(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None
    value = stripped[1:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def load_agent_registry(path: Path) -> dict[str, object]:
    registry: dict[str, object] = {"default_adapter": "codex", "agents": {}}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return registry

    current_role: str | None = None
    current_list: str | None = None
    current_nested: str | None = None
    prompt_role: str | None = None
    prompt_lines: list[str] = []
    in_agents = False

    def flush_prompt() -> None:
        nonlocal prompt_role, prompt_lines
        if prompt_role is None:
            return
        config = _ensure_agent_config(registry, prompt_role)
        config["prompt"] = "\n".join(prompt_lines).rstrip()
        prompt_role = None
        prompt_lines = []

    for raw_line in lines:
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = raw_line.strip()

        if prompt_role is not None:
            if raw_line.startswith("      ") or not stripped:
                prompt_lines.append(raw_line[6:] if raw_line.startswith("      ") else "")
                continue
            flush_prompt()

        if not stripped or stripped.startswith("#"):
            continue

        if indent == 0:
            current_role = None
            current_list = None
            current_nested = None
            in_agents = stripped == "agents:"
            if stripped.startswith("default_adapter:"):
                registry["default_adapter"] = stripped.partition(":")[2].strip() or "codex"
            continue

        if in_agents and indent == 2 and stripped.endswith(":"):
            current_role = stripped[:-1].strip()
            current_list = None
            current_nested = None
            _ensure_agent_config(registry, current_role)
            continue

        if not in_agents or current_role is None:
            continue

        config = _ensure_agent_config(registry, current_role)

        if indent == 4 and stripped == "prompt: |":
            current_list = None
            current_nested = None
            prompt_role = current_role
            prompt_lines = []
            continue

        if indent == 4 and stripped.endswith(":"):
            key = stripped[:-1].strip()
            current_list = key if key in {"capabilities", "preferred_task_types", "file_patterns"} else None
            current_nested = key if key == "risk_limits" else None
            if current_list:
                config[current_list] = []
            elif current_nested:
                config[current_nested] = {}
            continue

        if indent == 4 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            current_list = None
            current_nested = None
            if key == "agent_type":
                config[key] = value
            continue

        if indent == 6 and current_list:
            value = _parse_list_item(stripped)
            if value is not None:
                items = config.setdefault(current_list, [])
                if isinstance(items, list):
                    items.append(value)
            continue

        if indent == 6 and current_nested == "risk_limits" and ":" in stripped:
            key, _, value = stripped.partition(":")
            limits = config.setdefault("risk_limits", {})
            if isinstance(limits, dict):
                try:
                    limits[key.strip()] = int(value.strip())
                except ValueError:
                    limits[key.strip()] = value.strip()

    flush_prompt()
    return registry


def _as_string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _matches_pattern(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3])
    return Path(path).match(pattern)


def _file_match_count(config: dict[str, object], task: dict[str, object]) -> int:
    patterns = _as_string_set(config.get("file_patterns"))
    if not patterns:
        return 0
    count = 0
    for file_path in _task_files(task):
        if any(_matches_pattern(file_path, pattern) for pattern in patterns):
            count += 1
    return count


def _agent_score(role: str, name: str, config: dict[str, object], task: dict[str, object]) -> int:
    score = 0
    if name == role:
        score += 10
    score += 5 * len(_as_string_set(config.get("capabilities")).intersection(ROLE_CAPABILITIES.get(role, set())))
    score += 3 * len(_as_string_set(config.get("preferred_task_types")).intersection(ROLE_TASK_TYPES.get(role, set())))
    score += 2 * _file_match_count(config, task)
    return score


def _select_agent(role: str, task: dict[str, object], registry: dict[str, object] | None = None) -> tuple[str, str, str]:
    agents = registry.get("agents", {}) if registry else {}
    if not isinstance(agents, dict):
        agents = {}

    best_name = role
    best_config = _role_config(registry, role)
    best_score = _agent_score(role, role, best_config, task) if best_config else -1

    for name, config in agents.items():
        if not isinstance(name, str) or not isinstance(config, dict):
            continue
        score = _agent_score(role, name, config, task)
        if score > best_score or (score == best_score and name == role):
            best_name = name
            best_config = config
            best_score = score

    agent_type = DEFAULT_ROLE_TYPES.get(role, "default")
    configured_type = best_config.get("agent_type") if isinstance(best_config, dict) else None
    if isinstance(configured_type, str) and configured_type:
        agent_type = configured_type
    prompt = best_config.get("prompt") if isinstance(best_config, dict) else ""
    return best_name, agent_type, prompt if isinstance(prompt, str) else ""

def build_dispatch_plan(
    tasks: list[dict[str, object]],
    registry: dict[str, object] | None = None,
) -> dict[str, object]:
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
            agent, agent_type, agent_prompt = _select_agent(role, task, registry)
            assignments.append(
                {
                    "id": f"{task_id}-{role}",
                    "task": task_id,
                    "title": task["title"],
                    "role": role,
                    "recommended_agent": agent,
                    "agent_type": agent_type,
                    "agent_prompt": agent_prompt,
                    "depends_on": depends_on,
                    "files": task.get("files", []),
                    "steps": task.get("steps", []),
                    "commands": task.get("commands", []),
                }
            )

    return {
        "version": 1,
        "adapter": str(registry.get("default_adapter", "codex")) if registry else "codex",
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
                f"    agent_type: {assignment['agent_type']}",
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
            "agent_type": assignment["agent_type"],
            "agent_prompt": assignment.get("agent_prompt", ""),
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


def _render_named_items(title: str, items: object) -> list[str]:
    lines = [f"## {title}", ""]
    if isinstance(items, list) and items:
        for item in items:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    return lines


def render_assignment_prompt(assignment: dict[str, object]) -> str:
    lines = [
        f"# {assignment['id']}",
        "",
        f"Role: {assignment['role']}",
        f"Recommended agent: {assignment['recommended_agent']}",
        f"Agent type: {assignment['agent_type']}",
        f"Task: {assignment.get('title', '')}",
        "",
    ]
    agent_prompt = assignment.get("agent_prompt")
    if isinstance(agent_prompt, str) and agent_prompt.strip():
        lines.extend(["## Agent prompt", "", agent_prompt.strip(), ""])
    lines.append("You are not alone in this codebase. Respect the write boundary, do not revert other agents' edits, and report changed files.")
    lines.append("")
    lines.extend(_render_named_items("Files", assignment.get("files")))
    lines.extend(_render_named_items("Steps", assignment.get("steps")))
    lines.extend(_render_named_items("Commands", assignment.get("commands")))
    return "\n".join(lines)
