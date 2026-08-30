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
VERIFY_COMMAND_TRUNCATE = 120
VERIFY_COMMAND_MAX = 5
SCOPE_BOUNDARY_TRUNCATE = 160
ANCHOR_SECTIONS = ("目标", "验收标准", "被拒方案", "验证命令", "范围边界")
ACCEPTANCE_RE = re.compile(
    r"^\s*-\s*\[[ xX]?\]\s*(AC-[A-Za-z0-9-]+)\s*[:：]\s*(.+?)\s*$"
)
REJECTED_RE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^##\s*(.+?)\s*$")


def parse_decision_anchor(text: str) -> dict[str, Any]:
    """Extract goal / acceptance criteria / rejected option names / declared
    verification commands / scope boundary from a decision-anchor.md body.
    Section format is frozen by spec/contracts/decision-anchor.md; parsing is
    line-level and degrades to empty values when sections are missing."""
    goal_lines: list[str] = []
    acceptance: list[dict[str, str]] = []
    rejected: list[str] = []
    verify_commands: list[str] = []
    scope_boundary = ""
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
        elif section == "验证命令":
            command = raw.strip()
            if command.startswith("- "):
                command = command[2:].strip()
            if command and len(verify_commands) < VERIFY_COMMAND_MAX:
                verify_commands.append(command[:VERIFY_COMMAND_TRUNCATE])
        elif section == "范围边界":
            if raw.strip() and not scope_boundary:
                scope_boundary = raw.strip()[:SCOPE_BOUNDARY_TRUNCATE]
    return {
        "goal": "\n".join(goal_lines)[:GOAL_TRUNCATE],
        "acceptanceCriteria": acceptance,
        "rejectedOptions": rejected,
        "validationCommands": verify_commands,
        "scopeBoundary": scope_boundary,
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


def spec_pointer_files(task_dir: Path) -> list[str]:
    """spec/ pointer entries from implement.jsonl, in planning order — the
    reading list the implementing agent should consume before coding.
    Directory entries are context but not files to read, and entries the
    whitelist would reject (non-canonical paths) are skipped too, keeping the
    Specs row sourced from the same rules as the Scope row."""
    from services.context_paths import _is_valid_context_path

    path = task_dir / "implement.jsonl"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    files: list[str] = []
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
        if entry.get("type") == "directory":
            continue
        file_value = entry.get("file")
        if not isinstance(file_value, str):
            continue
        normalized = file_value.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if not normalized.startswith(".cowork-flow/spec/"):
            continue
        entry_type = entry.get("type", "file")
        segments = normalized.split("/")
        if not _is_valid_context_path(
            normalized, segments, file_value, entry_type
        ):
            continue
        files.append(normalized)
    return files


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


STAGE_CONTRACT_STATES = ("in_progress", "review")
STAGE_CONTRACT_SCOPE_LIMIT = 8
STAGE_CONTRACT_SPECS_LIMIT = 4
STAGE_CONTRACT_VERIFY_LIMIT = 3
STAGE_CONTRACT_BUDGET = 1200
GATES_TEXT = (
    "Gates: edits outside Scope are review blockers; CLAUDE.md and workflow "
    "files are protected; spec/ edits may be allowed by review policy; "
    "scope is agent-mutable (self-declared via task context add)"
)
# Delegated subtasks render the parent task's scope as a read-only reference:
# the child must not believe it can self-declare scope on the parent's behalf.
GATES_TEXT_READONLY = (
    "Gates: edits outside Scope are review blockers; CLAUDE.md and workflow "
    "files are protected; spec/ edits may be allowed by review policy; "
    "scope is inherited from the parent task (read-only reference)"
)


def _scope_row(entries: list[str], total: int, suffix: str) -> str:
    text = "; ".join(entries) if entries else "(empty)"
    more = total - len(entries)
    extra = f" (+{more} more in implement.jsonl)" if more > 0 else ""
    return f"Scope: {text}{extra} {suffix}"


def _fit_stage_contract(
    lines: list[str],
    scope_entries: list[str],
    scope_total: int,
    mutable: bool,
    budget: int = STAGE_CONTRACT_BUDGET,
) -> list[str]:
    """Degrade an over-budget block without ever emitting a malformed one:
    the closing tag and the guard rows (Scope/Gates) always survive. Order:
    1) drop removable rows (Specs/Verify) from the tail; 2) shrink Scope
    entries one by one (min 1); 3) last-resort codepoint cut that keeps the
    closing tag. Mirrored by the zcode/opencode JS implementations — keep
    the row-role rules and the drop order identical."""
    if len("\n".join(lines)) <= budget:
        return lines
    removable = [
        i
        for i in range(1, len(lines) - 1)
        if not lines[i].startswith(("Scope:", "Gates:"))
    ]
    for i in reversed(removable):
        reduced = [line for j, line in enumerate(lines) if j != i]
        if len("\n".join(reduced)) <= budget:
            return reduced
        lines = reduced
    suffix = "[agent-mutable]" if mutable else "[read-only]"
    pool = list(scope_entries)
    while len(pool) > 1:
        pool = pool[:-1]
        candidate = [
            _scope_row(pool, scope_total, suffix)
            if line.startswith("Scope:")
            else line
            for line in lines
        ]
        if len("\n".join(candidate)) <= budget:
            return candidate
        lines = candidate
    if len("\n".join(lines)) <= budget:
        return lines
    closing = lines[-1]
    # The final join inserts one newline between the cut body and the closing
    # tag — reserve it so the block stays within budget byte-for-byte.
    room = budget - len(closing) - 1
    body = "\n".join(lines[:-1])
    if len(body) <= room:
        return lines
    head = body[:room].rstrip()
    if not head:
        return lines
    return [head, closing]


def _stage_contract_lines(
    whitelist: list[dict],
    spec_files: list[str],
    anchor: dict[str, Any],
    mutable: bool = True,
    *,
    scope_limit: int = STAGE_CONTRACT_SCOPE_LIMIT,
    spec_limit: int = STAGE_CONTRACT_SPECS_LIMIT,
    verify_limit: int = STAGE_CONTRACT_VERIFY_LIMIT,
) -> list[str]:
    """Assemble the stage-contract body lines. Byte-for-byte mirrored by the
    zcode and opencode JS implementations — keep the formatting identical."""
    scope_suffix = "[agent-mutable]" if mutable else "[read-only]"
    lines: list[str] = []
    scope_items = [entry["file"] for entry in whitelist[:scope_limit]]
    lines.append(_scope_row(scope_items, len(whitelist), scope_suffix))
    if spec_files:
        spec_items = spec_files[:spec_limit]
        specs_text = "; ".join(spec_items)
        spec_more = len(spec_files) - len(spec_items)
        if spec_more > 0:
            specs_text += f" (+{spec_more} more)"
        lines.append(f"Specs: {specs_text}")
    lines.append(GATES_TEXT if mutable else GATES_TEXT_READONLY)
    verify = anchor.get("validationCommands") or []
    if verify:
        lines.append("Verify: " + "; ".join(verify[:verify_limit]))
    return lines


def xml_attr(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_stage_contract(
    task_path: str,
    whitelist: list[dict],
    spec_files: list[str],
    anchor: dict[str, Any],
    mutable: bool = True,
    rules: dict | None = None,
) -> str:
    """Assemble the stage-contract block. Byte-for-byte mirrored by the zcode
    and opencode JS implementations — keep the formatting identical. Over-
    budget inputs degrade through _fit_stage_contract, never emitting a half-
    closed block. `mutable=False` renders the parent scope as a read-only
    reference for delegated subtasks. `rules` comes from
    scope-rules.json (load_scope_rules) and carries budget and limits; None
    falls back to the module constants."""
    stage_contract = (rules or {}).get("stageContract") or {}
    budget = stage_contract.get("budget", STAGE_CONTRACT_BUDGET)
    scope_limit = stage_contract.get("scopeLimit", STAGE_CONTRACT_SCOPE_LIMIT)
    spec_limit = stage_contract.get("specLimit", STAGE_CONTRACT_SPECS_LIMIT)
    verify_limit = stage_contract.get("verifyLimit", STAGE_CONTRACT_VERIFY_LIMIT)
    lines = [f'<stage-contract task="{xml_attr(task_path)}">']
    lines.extend(
        _stage_contract_lines(
            whitelist,
            spec_files,
            anchor,
            mutable=mutable,
            scope_limit=scope_limit,
            spec_limit=spec_limit,
            verify_limit=verify_limit,
        )
    )
    lines.append("</stage-contract>")
    scope_entries = [entry["file"] for entry in whitelist[:scope_limit]]
    fitted = _fit_stage_contract(
        lines, scope_entries, len(whitelist), mutable, budget=budget
    )
    return "\n".join(fitted)


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