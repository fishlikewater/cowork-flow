#!/usr/bin/env python3
"""
R-AG-002 到 R-AG-009 的门禁检查器。

在 task_review 阶段运行：通过 git diff 获取工作树的未提交改动，逐项
检查 forbidden_action 规则。每项规则以 (repo_root, modified_files, diff_output,
rule_index) 为入参，返回 violation dict 列表。

结果汇总到 GateResult：存在 severity=block 的 violation 时阻断 review 流程，
warn 级别仅输出警告。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from common.git.git_snapshot import collect_changed_paths

try:
    from .validate_rules import (
        config_violation,
        load_rule_index,
        rule_violation,
        runtime_rules_path,
    )
except ImportError:  # pragma: no cover - direct script execution
    from validate_rules import (  # type: ignore[no-redef]
        config_violation,
        load_rule_index,
        rule_violation,
        runtime_rules_path,
    )


def validate_implementation(
    repo_root: Path,
    task_dir: Path,
    allow_spec_file_modifications: bool = False,
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

    rule_index, config_violations = load_rule_index(repo_root)
    if config_violations:
        return config_violations

    diff_output = _get_git_diff(repo_root, modified_files)

    # Check forbidden action rules
    violations.extend(
        _check_spec_file_modifications(
            repo_root,
            modified_files,
            rule_index,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
    )
    violations.extend(_check_premature_abstraction(repo_root, diff_output, rule_index))
    violations.extend(
        _check_unrequested_features(
            repo_root,
            diff_output,
            task_dir,
            rule_index,
            modified_files=modified_files,
        )
    )

    return violations


def _missing_rule(repo_root: Path, rule_id: str) -> dict:
    return config_violation(
        "RULES-CONFIG-004",
        f"Runtime workflow rule metadata is missing: {rule_id}",
        runtime_rules_path(repo_root),
        f"Add {rule_id} to .cowork-flow/spec/runtime/rules.json.",
    )


def _get_modified_files(repo_root: Path) -> list[str]:
    """Get staged, unstaged, and untracked files under repo_root."""
    changed_files = collect_changed_paths(repo_root)
    return [
        file_path
        for file_path in changed_files
        if _is_implementation_relevant(file_path)
    ]


def _is_implementation_relevant(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    if not normalized.startswith(".cowork-flow/"):
        return True
    return (
        normalized.startswith(".cowork-flow/spec/")
        or normalized == ".cowork-flow/workflow.md"
    )


def _get_git_diff(repo_root: Path, files: list[str]) -> str:
    """Get unstaged and staged diff output for changed files."""
    if not files:
        return ""

    try:
        outputs = []
        for extra_args in ((), ("--cached",)):
            diff_result = subprocess.run(
                ["git", "diff", *extra_args, "--", *files],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if diff_result.returncode == 0:
                outputs.append(diff_result.stdout)
        return "\n".join(outputs)
    except Exception:
        return ""


def _check_spec_file_modifications(
    repo_root: Path,
    modified_files: list[str],
    rule_index: dict[str, dict],
    *,
    allow_spec_file_modifications: bool,
) -> list[dict]:
    """R-AG-002: Check if spec files were modified"""
    violations = []

    if allow_spec_file_modifications:
        return violations

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
            rule = rule_index.get("R-AG-002")
            violations.append(
                rule_violation(rule, file_path) if rule else _missing_rule(repo_root, "R-AG-002")
            )

    return violations


def _check_premature_abstraction(
    repo_root: Path,
    diff_output: str,
    rule_index: dict[str, dict],
) -> list[dict]:
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
            rule = rule_index.get("R-AG-006")
            violations.append(
                rule_violation(rule, "", detail=f"detected pattern: {pattern}")
                if rule
                else _missing_rule(repo_root, "R-AG-006")
            )

    return violations


def _normalize_allowed_context_file(entry: dict) -> str | None:
    entry_type = entry.get("type", "file")
    file_path = entry.get("file")
    if entry_type not in ("file", "planned-file"):
        return None
    if not isinstance(file_path, str) or not file_path:
        return None
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    segments = normalized.split("/")
    invalid = (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or any(segment in ("", ".", "..") for segment in segments)
        or any(character in normalized for character in "*?[]")
    )
    return None if invalid else normalized


def _load_allowed_context_files(implement_jsonl: Path) -> set[str]:
    allowed_files: set[str] = set()
    try:
        for line in implement_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            normalized = _normalize_allowed_context_file(entry)
            if normalized is not None:
                allowed_files.add(normalized)
    except (OSError, UnicodeDecodeError):
        return set()
    return allowed_files


def _check_unrequested_features(
    repo_root: Path,
    diff_output: str,
    task_dir: Path,
    rule_index: dict[str, dict],
    *,
    modified_files: list[str] | None = None,
) -> list[dict]:
    """R-AG-005: Require modified files to be explicitly listed."""
    del diff_output
    violations = []
    implement_jsonl = task_dir / "implement.jsonl"
    if not implement_jsonl.exists():
        return violations

    allowed_files = _load_allowed_context_files(implement_jsonl)
    if not allowed_files:
        return violations

    # Get modified project files (exclude .cowork-flow/ metadata)
    changed_files = (
        modified_files
        if modified_files is not None
        else _get_modified_files(repo_root)
    )
    for file_path in changed_files:
        # Skip .cowork-flow metadata files and template files
        if ".cowork-flow/" in file_path:
            continue
        normalized = file_path.replace("\\", "/")
        # Check if file is in allowed list
        if normalized not in allowed_files:
            rule = rule_index.get("R-AG-005")
            violations.append(
                rule_violation(
                    rule, file_path,
                    detail=f"modified file not in implement.jsonl allowed list"
                )
                if rule
                else _missing_rule(repo_root, "R-AG-005")
            )

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
