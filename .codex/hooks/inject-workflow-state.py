#!/usr/bin/env python3
"""Emit cowork-flow workflow context for Codex UserPromptSubmit hooks."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


TAG_RE = re.compile(
    r"\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*\[/workflow-state:\1\]",
    re.DOTALL,
)

def _find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".cowork-flow").is_dir():
            return current
        if current == current.parent:
            return None
        current = current.parent


def _read_hook_input() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_breadcrumbs(root: Path) -> dict[str, str]:
    workflow = root / ".cowork-flow" / "workflow.md"
    try:
        text = workflow.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {match.group(1): match.group(2).strip() for match in TAG_RE.finditer(text)}


def _load_common(root: Path) -> None:
    scripts_dir = root / ".cowork-flow" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _get_dispatch_mode(root: Path) -> str:
    _load_common(root)
    try:
        from common.config import get_codex_dispatch_mode  # type: ignore[import-not-found]
    except Exception:
        return "sub-agent"
    try:
        return get_codex_dispatch_mode(root)
    except Exception:
        return "sub-agent"


def _get_active_task(root: Path, hook_input: dict[str, Any]) -> tuple[str | None, str, str]:
    _load_common(root)
    try:
        from common.active_task import get_active_task  # type: ignore[import-not-found]
    except Exception:
        return None, "no_task", "unavailable"

    active = get_active_task(root, hook_input)
    if not active.task_path:
        return None, "no_task", active.source

    task_dir = root / active.task_path
    task_json = task_dir / "task.json"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return active.task_path, "stale", active.source

    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        status = "unknown"
    return active.task_path, status.strip(), active.source


def _build_context(
    task_path: str | None,
    status: str,
    source: str,
    breadcrumbs: dict[str, str],
    dispatch_mode: str,
) -> str:
    body = breadcrumbs.get(status) or "Refer to .cowork-flow/workflow.md for the current step."
    if task_path is None:
        header = f"Status: {status}\nSource: {source}"
    else:
        header = f"Task: {task_path}\nStatus: {status}\nSource: {source}"

    return "\n\n".join(
        [
            f"<codex-mode>{dispatch_mode}</codex-mode>",
            f"<workflow-state>\n{header}\n{body}\n</workflow-state>",
        ]
    )


def main() -> int:
    if os.environ.get("COWORK_FLOW_HOOKS") == "0" or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1":
        return 0

    hook_input = _read_hook_input()
    cwd_value = hook_input.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value.strip() else Path.cwd()
    root = _find_repo_root(cwd)
    if root is None:
        return 0

    breadcrumbs = _load_breadcrumbs(root)
    dispatch_mode = _get_dispatch_mode(root)
    task_path, status, source = _get_active_task(root, hook_input)
    additional_context = _build_context(task_path, status, source, breadcrumbs, dispatch_mode)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": additional_context,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
