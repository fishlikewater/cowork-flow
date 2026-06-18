#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for default task context generation."""

from __future__ import annotations

import json
from pathlib import Path

from .paths import DIR_AGENTS, DIR_SPEC, DIR_WORKFLOW, get_repo_root


def get_implement_base() -> list[dict]:
    """Get base implement context entries."""
    return [
        {
            "file": "AGENTS.md",
            "reason": "Project collaboration rules and workflow gates",
        },
        {
            "file": f"{DIR_WORKFLOW}/workflow.md",
            "reason": "Project workflow and conventions",
        },
    ]


def get_implement_backend() -> list[dict]:
    """Get backend implement context entries."""
    return [
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/core/backend/index.md",
            "reason": "Backend development guide",
        },
    ]


def get_implement_frontend() -> list[dict]:
    """Get frontend implement context entries."""
    return [
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/core/frontend/index.md",
            "reason": "Frontend development guide",
        },
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


def get_check_context(
    dev_type: str, repo_root: Path | None = None
) -> list[dict]:
    """Get check context entries."""
    return [
        {
            "file": _skill_path("check", repo_root),
            "reason": "Quality, contract, and template consistency check",
        },
        {
            "file": _skill_path("finish-work", repo_root),
            "reason": "Finish, archive, and session recording gate",
        },
    ]


def get_debug_context(
    dev_type: str, repo_root: Path | None = None
) -> list[dict]:
    """Get debug context entries."""
    return [
        {
            "file": _skill_path("break-loop", repo_root),
            "reason": "Deep bug analysis workflow",
        },
        {
            "file": _skill_path("update-spec", repo_root),
            "reason": "Capture implementation lessons and contracts",
        },
        {
            "file": _skill_path("check", repo_root),
            "reason": "Verify the fix and related contracts",
        },
    ]


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write entries to a JSONL file using UTF-8."""
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_context_files(
    target_dir: Path,
    dev_type: str,
    repo_root: Path | None = None,
) -> dict[str, int]:
    """Write default context files for a task and return entry counts."""
    implement_entries = get_implement_base()
    if dev_type in ("backend", "test"):
        implement_entries.extend(get_implement_backend())
    elif dev_type == "frontend":
        implement_entries.extend(get_implement_frontend())
    elif dev_type == "fullstack":
        implement_entries.extend(get_implement_backend())
        implement_entries.extend(get_implement_frontend())

    check_entries = get_check_context(dev_type, repo_root)
    debug_entries = get_debug_context(dev_type, repo_root)

    _write_jsonl(target_dir / "implement.jsonl", implement_entries)
    _write_jsonl(target_dir / "check.jsonl", check_entries)
    _write_jsonl(target_dir / "debug.jsonl", debug_entries)

    return {
        "implement": len(implement_entries),
        "check": len(check_entries),
        "debug": len(debug_entries),
    }
