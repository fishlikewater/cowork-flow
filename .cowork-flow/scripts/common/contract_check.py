#!/usr/bin/env python3
"""Contract readWhen enforcement for registry.json.

Checks whether relevant spec files have been "referenced" before
allowing task mutations.  Security-critical contracts (ENTRY / DISPATCH)
block; others are advisory only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .files import read_json_file as _read_json_file

# Contracts whose readWhen is enforced as a hard block.
SECURITY_CONTRACT_IDS = frozenset({"entry", "dispatch"})


def _load_registry(root: Path) -> list[dict[str, Any]]:
    data = _read_json_file(root / ".cowork-flow" / "spec" / "registry.json")
    if not data or not isinstance(data.get("contracts"), list):
        return []
    return data["contracts"]


def _normalize_path(path_str: str) -> str:
    return path_str.replace("\\", "/").strip().lower()


def _path_matches_in_text(text: str, spec_path: str) -> bool:
    """Return True if text mentions anything resembling *spec_path*."""
    norm = _normalize_path(spec_path)
    if not norm:
        return False
    # exact match
    if norm in text.lower():
        return True
    # basename only
    basename = Path(norm).name.lower()
    if basename in text.lower():
        return True
    # stem of basename
    stem = Path(basename).stem.lower()
    if stem in text.lower():
        return True
    return False


def _git_recent_texts(root: Path, n: int = 50) -> list[str]:
    """Grep recent git log messages + changed paths."""
    try:
        from common.git_context import _run_git_command
    except ImportError:
        return []
    try:
        _, log_out, _ = _run_git_command(["log", f"-{n}", "--pretty=format:%s%n%b", "--"])
    except Exception:
        return []
    if not log_out:
        return []
    return [log_out]


def _git_diff_text(root: Path) -> str:
    """Unstaged + staged diff text (paths only)."""
    try:
        from common.git_context import _run_git_command
    except ImportError:
        return ""
    out: list[str] = []
    for cmd in [["diff", "--cached", "--name-only"], ["diff", "--name-only"]]:
        try:
            _, r, _ = _run_git_command(cmd)
            if r:
                out.append(r)
        except Exception:
            pass
    return "\n".join(out)


def _task_files_text(task_dir: Path) -> str:
    """Read all md/jsonl files in a task dir."""
    parts: list[str] = []
    for f in sorted(task_dir.iterdir()):
        if f.is_file() and f.suffix in (".md", ".jsonl", ".json", ".yaml", ".yml"):
            try:
                parts.append(f.read_text(encoding="utf-8"))
            except OSError:
                pass
    return "\n".join(parts)


def _has_been_referenced(root: Path, spec_path: str, task_dir: Path) -> bool:
    """Check whether *spec_path* has been referenced anywhere relevant."""
    git_diff = _git_diff_text(root)
    git_logs = "\n".join(_git_recent_texts(root))
    task_files = _task_files_text(task_dir)
    combined = git_diff + "\n" + git_logs + "\n" + task_files
    return _path_matches_in_text(combined, spec_path)


def check_read_when(
    root: Path,
    trigger: str,
    task_dir: Path | None = None,
) -> dict[str, list[str]]:
    """Return ``{"blockers": [...], "advisories": [...]}`` for *trigger*.

    *trigger* values: ``task_start`` | ``task_resume`` | ``task_archive``
    | ``subagent_dispatch`` | ``subagent_bind`` | ``prompt_conflict``.
    """
    contracts = _load_registry(root)
    blockers: list[str] = []
    advisories: list[str] = []

    td = (task_dir or Path.cwd())

    for contract in contracts:
        read_when = contract.get("readWhen")
        if not isinstance(read_when, list):
            continue
        # Does any readWhen entry match our trigger?
        matched = False
        # Split trigger into keywords (task_start -> ["task", "start"])
        trigger_keywords = set(re.split(r"[_\-]", trigger.lower()))
        for rw in read_when:
            if not isinstance(rw, str):
                continue
            rw_lower = rw.lower().strip()
            # Exact match
            if rw_lower == trigger:
                matched = True
                break
            # Keyword match: at least one trigger keyword appears in readWhen text
            if trigger_keywords & set(re.split(r"[\s/]+", rw_lower)):
                matched = True
                break
        if not matched:
            continue

        spec_path = contract.get("path", "")
        contract_id = contract.get("id", "")
        if not isinstance(spec_path, str) or not spec_path.strip():
            continue

        referenced = _has_been_referenced(root, spec_path, td)
        entry = f"spec: {spec_path} ({contract_id})"

        if not referenced:
            # Security contracts block
            if any(kw.upper() in contract_id.upper() for kw in SECURITY_CONTRACT_IDS):
                blockers.append(f"readWhen block — {entry} not referenced")
            else:
                advisories.append(f"readWhen advisory — {entry} not referenced")

    return {"blockers": blockers, "advisories": advisories}
