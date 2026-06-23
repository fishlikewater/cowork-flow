#!/usr/bin/env python3
"""
Implementation validation script.

Validates code changes against forbidden action rules after task implementation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def validate_implementation(
    repo_root: Path,
    task_dir: Path,
) -> list[dict]:
    """
    Validate code changes against implementation rules.

    Args:
        repo_root: Repository root directory
        task_dir: Task directory

    Returns:
        List of violations
    """
    violations = []

    modified_files = _get_modified_files(repo_root)
    if not modified_files:
        return violations

    diff_output = _get_git_diff(repo_root, modified_files)

    # Check forbidden action rules
    violations.extend(_check_spec_file_modifications(modified_files))
    violations.extend(_check_premature_abstraction(diff_output))
    violations.extend(_check_unrequested_features(diff_output, task_dir))

    return violations


def _get_modified_files(repo_root: Path) -> list[str]:
    """Get git-tracked modified files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return [file_path for file_path in result.stdout.strip().split("\n") if file_path]
        return []
    except Exception:
        return []


def _get_git_diff(repo_root: Path, files: list[str]) -> str:
    """Get git diff output"""
    if not files:
        return ""

    try:
        diff_result = subprocess.run(
            ["git", "diff", "--", *files],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return diff_result.stdout
    except Exception:
        return ""


def _check_spec_file_modifications(modified_files: list[str]) -> list[dict]:
    """R-AG-002: Check if spec files were modified"""
    violations = []

    # Spec file path patterns
    spec_patterns = [
        r"(^|/)\.cowork-flow/spec/",
        r"(^|/)\.cowork-flow/workflow\.md$",
        r"(^|/)AGENTS\.md$",
        r"(^|/)CLAUDE\.md$",
    ]

    for file_path in modified_files:
        normalized_path = file_path.replace("\\", "/")
        if any(re.search(pattern, normalized_path) for pattern in spec_patterns):
            violations.append(
                {
                    "rule_id": "R-AG-002",
                    "type": "forbidden_action",
                    "severity": "block",
                    "passed": False,
                    "message": "Subagent attempted to modify spec files",
                    "file": file_path,
                    "fix_hint": "Spec files can only be modified by main session",
                }
            )

    return violations


def _check_premature_abstraction(diff_output: str) -> list[dict]:
    """R-AG-006: Check if premature abstraction was used"""
    violations = []

    # Detection patterns for abstraction
    abstraction_patterns = [
        r"def\s+base_",           # base_ prefixed functions
        r"class\s+Abstract",      # Abstract prefixed classes
        r"class\s+Base",          # Base prefixed classes
        r"class\s+Generic",       # Generic prefixed classes
        r"def\s+create_factory",  # Factory pattern
        r"def\s+get_instance",    # Singleton pattern
    ]

    for pattern in abstraction_patterns:
        matches = re.findall(pattern, diff_output)
        if matches:
            violations.append({
                "rule_id": "R-AG-006",
                "type": "forbidden_action",
                "severity": "warn",
                "passed": False,
                "message": f"Premature abstraction detected: {pattern}",
                "file": "",
                "fix_hint": "Keep code simple and direct, only abstract when reuse is confirmed",
            })

    return violations


def _check_unrequested_features(
    diff_output: str,
    task_dir: Path,
) -> list[dict]:
    """R-AG-005: Check if unrequested features were introduced"""
    violations = []

    # Read PRD
    prd_path = task_dir / "prd.md"
    if not prd_path.exists():
        return violations

    prd_content = prd_path.read_text(encoding="utf-8")

    # Check for obvious extra features
    # This is a simple heuristic check, actual implementation may need more complex NLP analysis
    feature_indicators = [
        r"Added.*feature",
        r"New.*functionality",
        r"Implemented.*module",
    ]

    for pattern in feature_indicators:
        if re.search(pattern, diff_output) and not re.search(pattern, prd_content):
            violations.append({
                "rule_id": "R-AG-005",
                "type": "forbidden_action",
                "severity": "block",
                "passed": False,
                "message": "Unrequested feature introduced",
                "file": "",
                "fix_hint": "Only implement features explicitly required by the PRD",
            })

    return violations


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate implementation against spec")
    parser.add_argument("--task-dir", required=True, help="Task directory path")
    parser.add_argument("--repo-root", default=".", help="Repository root path")

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    task_dir = Path(args.task_dir).resolve()

    violations = validate_implementation(repo_root, task_dir)

    if violations:
        for v in violations:
            print(json.dumps(v, ensure_ascii=False))
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
