#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task fact view: one machine-readable aggregate of everything a session
needs to know about a task.

This is the fact-layer read entry (docs/direction.md, stage 1): task.json,
decision-anchor essentials, plan binding, bound sessions, and the trusted
state snapshot — assembled once so hosts, hooks, and tools stop re-deriving
them from file conventions.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GOAL_TRUNCATE = 300
ANCHOR_SECTIONS = ("目标", "验收标准", "被拒方案")
ACCEPTANCE_RE = re.compile(
    r"^\s*-\s*\[[ xX]?\]\s*(AC-[A-Za-z0-9-]+)\s*[:：]\s*(.+?)\s*$"
)
REJECTED_RE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^##\s*(.+?)\s*$")


def parse_decision_anchor(text: str) -> dict[str, Any]:
    """Extract goal / acceptance criteria / rejected option names from a
    decision-anchor.md body. Section format is frozen by
    spec/contracts/decision-anchor.md; parsing is line-level and degrades to
    empty lists when sections are missing."""
    goal_lines: list[str] = []
    acceptance: list[dict[str, str]] = []
    rejected: list[str] = []
    section: str | None = None
    for raw in text.splitlines():
        heading = _HEADING_RE.match(raw.strip())
        if heading:
            name = heading.group(1)
            section = name if name in ANCHOR_SECTIONS else None
            continue
        if section == "目标":
            if raw.strip():
                goal_lines.append(raw.strip())
        elif section == "验收标准":
            match = ACCEPTANCE_RE.match(raw)
            if match:
                acceptance.append(
                    {"id": match.group(1), "text": match.group(2)}
                )
        elif section == "被拒方案":
            match = REJECTED_RE.match(raw)
            if match:
                rejected.append(match.group(1).strip())
    return {
        "goal": "\n".join(goal_lines)[:GOAL_TRUNCATE],
        "acceptanceCriteria": acceptance,
        "rejectedOptions": rejected,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def file_scope_whitelist(repo_root: Path, task_dir: Path) -> list[dict]:
    """File-scope-only whitelist entries for one task.

    Single source of the edit-scope semantics the lifecycle gates enforce:
    directory entries are valid context but authorize nothing, so only
    file/planned-file/deleted-file entries appear here. MCP tooling and any
    other consumer must use this instead of re-parsing implement.jsonl.
    """
    from services.context_paths import normalize_context_file_scope_entry

    path = task_dir / "implement.jsonl"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    whitelist: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        normalized, error = normalize_context_file_scope_entry(
            repo_root, entry
        )
        if error is not None or normalized is None:
            continue
        whitelist.append(
            {
                "file": normalized,
                "type": entry.get("type", "file"),
            }
        )
    return whitelist


def path_in_scope(
    whitelist: list[dict], candidate: str
) -> dict:
    """Verdict for one candidate path against a file_scope_whitelist list."""
    value = candidate.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    matched = next(
        (entry for entry in whitelist if entry["file"] == value), None
    )
    return {
        "path": value,
        "inScope": matched is not None,
        "matched": matched,
    }


def _normalize_rel(path_value: str) -> str | None:
    value = path_value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value or None


def _bound_sessions(repo_root: Path, rel_task: str) -> list[dict[str, Any]]:
    """Sessions whose active_task_path points at this task."""
    from runtime.session_state import sessions_dir

    sessions_root = sessions_dir(repo_root)
    try:
        files = sorted(sessions_root.glob("*.json"))
    except OSError:
        return []
    bound: list[dict[str, Any]] = []
    for path in files:
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        active = data.get("active_task_path")
        if not isinstance(active, str) or _normalize_rel(active) != rel_task:
            continue
        bound.append(
            {
                "contextKey": path.stem,
                "scope": data.get("scope"),
                "platform": data.get("platform"),
                "lastSeenAt": data.get("last_seen_at"),
            }
        )
    return bound


def _matching_snapshot(
    repo_root: Path, rel_task: str, status: Any
) -> dict[str, Any] | None:
    """State snapshot only when it matches the task and the on-disk status —
    the same trust conditions the hooks apply."""
    snapshot = _read_json(
        repo_root / ".cowork-flow" / ".runtime" / "state-snapshot.json"
    )
    if not isinstance(snapshot, dict):
        return None
    active = snapshot.get("activeTaskPath")
    if not isinstance(active, str) or _normalize_rel(active) != rel_task:
        return None
    if snapshot.get("status") != status:
        return None
    return snapshot


def build_fact_view(repo_root: Path, task_dir: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    task_dir = task_dir.resolve()
    task = _read_json(task_dir / "task.json")
    rel_task = task_dir.relative_to(repo_root).as_posix()

    anchor_path = task_dir / "decision-anchor.md"
    if anchor_path.is_file():
        anchor: dict[str, Any] = {"exists": True}
        try:
            anchor.update(
                parse_decision_anchor(anchor_path.read_text(encoding="utf-8"))
            )
        except OSError:
            anchor = {"exists": False}
    else:
        anchor = {"exists": False}

    meta = task.get("meta") if isinstance(task, dict) else None
    plan_file = meta.get("planFile") if isinstance(meta, dict) else None
    plan: dict[str, Any] = {"bound": bool(plan_file)}
    if plan_file:
        plan["file"] = plan_file

    status = task.get("status") if isinstance(task, dict) else None
    return {
        "schemaVersion": 1,
        "generatedAt": _now_iso(),
        "taskPath": rel_task,
        "task": task,
        "decisionAnchor": anchor,
        "plan": plan,
        "whitelist": file_scope_whitelist(repo_root, task_dir),
        "sessions": _bound_sessions(repo_root, rel_task),
        "snapshot": _matching_snapshot(repo_root, rel_task, status),
    }