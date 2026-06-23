#!/usr/bin/env python3
"""
Coding standards helper.

Summarizes relevant standards and validates changed files for lifecycle gates.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .coding_standards import validate_changed_files
from .git_snapshot import collect_changed_files, collect_changed_paths


def get_coding_standards_summary(
    repo_root: Path,
    task_dir: Path,
) -> str:
    """
    Get coding standards summary based on changed files.

    Args:
        repo_root: Repository root directory
        task_dir: Task directory

    Returns:
        Summary string of relevant coding standards
    """
    modified_files = collect_changed_paths(repo_root)
    if not modified_files:
        return ""

    # Classify files
    backend_files = [f for f in modified_files if _is_backend_file(f)]
    frontend_files = [f for f in modified_files if _is_frontend_file(f)]

    summaries = []

    # Get backend standards summary
    if backend_files:
        backend_summary = _get_standards_summary(repo_root, "backend")
        if backend_summary:
            summaries.append(f"=== Backend Coding Standards ===\n{backend_summary}")

    # Get frontend standards summary
    if frontend_files:
        frontend_summary = _get_standards_summary(repo_root, "frontend")
        if frontend_summary:
            summaries.append(f"=== Frontend Coding Standards ===\n{frontend_summary}")

    return "\n\n".join(summaries)


def validate_coding_standards(
    repo_root: Path,
    task_dir: Path | None = None,
) -> list[dict]:
    """Validate coding standards for changed files."""
    return validate_changed_files(repo_root, collect_changed_files(repo_root))


def _is_backend_file(file_path: str) -> bool:
    """Check if file is a backend file"""
    backend_patterns = [
        r"\.py$",
        r"\.java$",
        r"\.go$",
        r"\.rs$",
        r"\.rb$",
    ]
    return any(re.search(p, file_path) for p in backend_patterns)


def _is_frontend_file(file_path: str) -> bool:
    """Check if file is a frontend file"""
    frontend_patterns = [
        r"\.tsx$",
        r"\.jsx$",
        r"\.vue$",
        r"\.svelte$",
    ]
    return any(re.search(p, file_path) for p in frontend_patterns)


def _get_standards_summary(repo_root: Path, category: str) -> str:
    """
    Get summary of coding standards from markdown files.

    Args:
        repo_root: Repository root directory
        category: 'backend' or 'frontend'

    Returns:
        Summary string
    """
    spec_dir = repo_root / ".cowork-flow" / "spec" / category
    if not spec_dir.exists():
        return ""

    summaries = []

    for md_file in sorted(spec_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue

        content = md_file.read_text(encoding="utf-8")
        rules = _extract_key_rules(content)

        if rules:
            summaries.append(f"File: {md_file.name}")
            for rule in rules[:5]:  # Limit to top 5 rules per file
                summaries.append(f"  - {rule}")
            summaries.append("")

    return "\n".join(summaries)


def _extract_key_rules(content: str) -> list[str]:
    """Extract key rules from markdown content"""
    rules = []

    # Extract forbidden patterns (Must not, Should not, Do not, etc.)
    # Also match Chinese patterns
    forbidden_patterns = [
        r"[-*]\s*(Must not|Should not|Do not|Never|Avoid)\s+(.+)",
        r"[-*]\s*(禁止|不得|不能|不应|避免|不要|不可)\s*(.+)",
        r"[-*]\s*(.+不得|.+不能|.+不应|.+避免|.+不要)\s*(.+)",
    ]

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        for pattern in forbidden_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Extract the rule text
                rule_text = line.lstrip("-* ").strip()
                if len(rule_text) > 5:  # Skip very short rules
                    rules.append(rule_text[:80])  # Limit length
                    break  # Only match one pattern per line

    return rules[:10]  # Return top 10 rules


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Get coding standards summary")
    parser.add_argument("--task-dir", required=True, help="Task directory path")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--validate", action="store_true", help="Fail on coding standards violations")

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    task_dir = Path(args.task_dir).resolve()

    if args.validate:
        violations = validate_coding_standards(repo_root, task_dir)
        if violations:
            for violation in violations:
                print(json.dumps(violation, ensure_ascii=False))
            sys.exit(1)
        sys.exit(0)

    summary = get_coding_standards_summary(repo_root, task_dir)
    if summary:
        print(summary)
    else:
        print("No relevant coding standards found for changed files.")


if __name__ == "__main__":
    main()
