#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post-implementation validation — detects forbidden agent actions.

Checks:
- R-AG-002: Subagent modified spec files (.cowork-flow/spec/)
- R-AG-005: Premature abstraction (base_/Abstract/Generic/factory patterns)
- R-AG-006: Unrequested features (files not mentioned in PRD)
"""

from __future__ import annotations

import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_implementation(repo_root: Path, task_dir: Path) -> list[dict]:
    """Run all implementation checks.

    Returns a list of violation dicts with rule_id, severity, message, fix_hint.
    """
    violations: list[dict] = []
    violations.extend(_check_spec_file_modifications(repo_root, task_dir))
    violations.extend(_check_premature_abstraction(repo_root))
    violations.extend(_check_unrequested_features(repo_root, task_dir))
    return violations


# ---------------------------------------------------------------------------
# R-AG-002: Spec file modifications
# ---------------------------------------------------------------------------


def _check_spec_file_modifications(repo_root: Path, task_dir: Path) -> list[dict]:
    """Detect changes to .cowork-flow/spec/ in the working tree."""
    changed = _get_changed_files(repo_root)
    spec_violations: list[dict] = []
    for f in changed:
        if ".cowork-flow/spec/" in f or ".cowork-flow\\spec\\" in f:
            spec_violations.append({
                "rule_id": "R-AG-002",
                "severity": "block",
                "message": f"Subagent modified spec file: {f}",
                "fix_hint": "Revert spec changes — specs can only be modified by the main session.",
                "file": f,
            })
    return spec_violations


# ---------------------------------------------------------------------------
# R-AG-005: Premature abstraction
# ---------------------------------------------------------------------------


_PREMATURE_ABSTRACTION_PATTERNS = (
    "class base_", "class abstract", "class Base", "class Abstract",
    "class Generic", "class Factory", "def create_factory",
    "def get_instance", "def create_",
    "abstract_class", "base_class", "AbstractBase",
)


def _check_premature_abstraction(repo_root: Path) -> list[dict]:
    """Detect premature abstraction patterns in staged changes."""
    diff_text = _get_diff(repo_root, staged=True)
    if not diff_text:
        return []
    violations: list[dict] = []
    added_lines = [
        line[1:] for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    for line in added_lines:
        stripped = line.strip().lower()
        for pattern in _PREMATURE_ABSTRACTION_PATTERNS:
            if pattern.lower() in stripped:
                violations.append({
                    "rule_id": "R-AG-005",
                    "severity": "warn",
                    "message": f"Premature abstraction pattern: {pattern!r} in added line: {line.strip()[:80]}",
                    "fix_hint": "Keep code simple — only abstract when reuse is confirmed.",
                    "file": "",
                })
                break
    return violations


# ---------------------------------------------------------------------------
# R-AG-006: Unrequested features
# ---------------------------------------------------------------------------


def _check_unrequested_features(repo_root: Path, task_dir: Path) -> list[dict]:
    """Detect new files not referenced in PRD acceptance criteria."""
    prd_path = task_dir / "prd.md"
    if not prd_path.is_file():
        return []
    try:
        prd_text = prd_path.read_text(encoding="utf-8").lower()
    except OSError:
        return []
    changed = _get_changed_files(repo_root)
    # Filter to only new code files (not spec, not docs)
    code_files = [
        f for f in changed
        if not any(skip in f for skip in (
            ".cowork-flow/", "__pycache__", ".pyc",
            "prd.json", "quality.json", "change.yaml",
        ))
        and any(f.endswith(ext) for ext in (".py", ".ts", ".tsx", ".js", ".jsx"))
    ]
    violations: list[dict] = []
    for f in code_files:
        stem = Path(f).stem
        # Check if file name or key terms appear in PRD
        if stem and stem not in prd_text and stem.replace("_", " ") not in prd_text:
            violations.append({
                "rule_id": "R-AG-006",
                "severity": "warn",
                "message": f"New file '{f}' not clearly referenced in PRD — may be unrequested",
                "fix_hint": "Verify this file implements a PRD acceptance criterion or revert it.",
                "file": f,
            })
    return violations


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_changed_files(repo_root: Path) -> list[str]:
    """Get list of changed file paths from git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    files: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        path = line[3:].strip().strip('"')
        if path:
            # Handle rename: "old -> new"
            if " -> " in path:
                path = path.split(" -> ")[-1]
            files.append(path.replace("\\", "/"))
    return files


def _get_diff(repo_root: Path, staged: bool = True) -> str:
    """Get git diff text."""
    args = ["git", "diff"]
    if staged:
        args.append("--cached")
    args.append("--")
    try:
        result = subprocess.run(
            args,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout
