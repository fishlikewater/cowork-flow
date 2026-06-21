#!/usr/bin/env python3
"""
Rule validation script for cowork-flow workflow.

Validates rules at task start/complete checkpoints.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def validate_rules(
    repo_root: Path,
    scope: str,
    task_dir: Path | None = None,
) -> list[dict]:
    """
    Validate rules for given scope.

    Args:
        repo_root: Repository root path
        scope: Validation scope (task_start, task_complete, check, implement)
        task_dir: Optional task directory path

    Returns:
        List of violations (empty if all rules pass)
    """
    violations = []

    # Load rules
    rules_path = repo_root / ".cowork-flow" / "spec" / "rules.json"
    if not rules_path.exists():
        return violations

    with open(rules_path) as f:
        rules_data = json.load(f)

    rules = rules_data.get("rules", [])

    # Filter rules by scope
    applicable_rules = [
        r for r in rules
        if r["scope"] == scope or r["scope"] == "all"
    ]

    # Validate each rule
    for rule in applicable_rules:
        violation = _validate_rule(rule, repo_root, task_dir)
        if violation:
            violations.append(violation)

    return violations


def _validate_rule(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
) -> dict | None:
    """Validate a single rule. Returns violation dict if rule fails."""
    rule_type = rule["type"]

    if rule_type == "phase_gate":
        return _validate_phase_gate(rule, repo_root, task_dir)
    elif rule_type == "forbidden_action":
        # Forbidden actions are validated at runtime, not at checkpoints
        return None

    return None


def _validate_phase_gate(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
) -> dict | None:
    """Validate a phase_gate rule."""
    rule_id = rule["id"]

    # R-WF-001 to R-WF-005: L2 readiness checks
    if rule_id in ["R-WF-001", "R-WF-002", "R-WF-003", "R-WF-004", "R-WF-005"]:
        if task_dir is None:
            return None

        # Check if task has L2 change
        change_dir = _find_linked_change(repo_root, task_dir)
        if change_dir is None:
            return None

        # Validate specific file requirements
        if rule_id == "R-WF-001":
            return _check_file_exists(change_dir / "proposal.md", rule, "proposal.md")
        elif rule_id == "R-WF-002":
            return _check_file_exists(change_dir / "spec.md", rule, "spec.md")
        elif rule_id == "R-WF-003":
            return _check_file_exists(change_dir / "design.md", rule, "design.md")
        elif rule_id == "R-WF-004":
            return _check_plan_link(repo_root, change_dir, rule)
        elif rule_id == "R-WF-005":
            return _check_task_link(change_dir, rule)

    # R-WF-006: Implementation without failing test
    if rule_id == "R-WF-006":
        # This is a warn-level rule, just log
        return None

    # R-WF-007: Task completion without check
    if rule_id == "R-WF-007":
        if scope == "task_complete" and task_dir:
            task_json = task_dir / "task.json"
            if task_json.exists():
                with open(task_json) as f:
                    task_data = json.load(f)
                if task_data.get("status") != "review":
                    return {
                        "rule_id": rule_id,
                        "type": rule["type"],
                        "severity": rule["severity"],
                        "passed": False,
                        "message": rule["message"],
                        "file": str(task_json),
                        "fix_hint": rule["fix_hint"],
                    }

    return None


def _find_linked_change(repo_root: Path, task_dir: Path) -> Path | None:
    """Find the change directory linked to a task."""
    changes_dir = repo_root / ".cowork-flow" / "changes"
    if not changes_dir.exists():
        return None

    task_name = task_dir.name
    for change_dir in changes_dir.iterdir():
        if change_dir.is_dir() and change_dir.name != "archive":
            change_yaml = change_dir / "change.yaml"
            if change_yaml.exists():
                with open(change_yaml) as f:
                    content = f.read()
                if task_name in content:
                    return change_dir

    return None


def _check_file_exists(
    file_path: Path,
    rule: dict,
    filename: str,
) -> dict | None:
    """Check if a required file exists and is not empty."""
    if not file_path.exists():
        return {
            "rule_id": rule["id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "passed": False,
            "message": f"L2 readiness: {filename} is missing",
            "file": str(file_path),
            "fix_hint": rule["fix_hint"],
        }

    if file_path.stat().st_size == 0:
        return {
            "rule_id": rule["id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "passed": False,
            "message": f"L2 readiness: {filename} is empty",
            "file": str(file_path),
            "fix_hint": rule["fix_hint"],
        }

    return None


def _check_plan_link(
    repo_root: Path,
    change_dir: Path,
    rule: dict,
) -> dict | None:
    """Check if change has a plan link."""
    change_yaml = change_dir / "change.yaml"
    if not change_yaml.exists():
        return {
            "rule_id": rule["id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "passed": False,
            "message": "L2 readiness: change.yaml is missing",
            "file": str(change_yaml),
            "fix_hint": rule["fix_hint"],
        }

    with open(change_yaml) as f:
        content = f.read()

    if "plan:" not in content or "plan: null" in content:
        return {
            "rule_id": rule["id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "passed": False,
            "message": "L2 readiness: plan link is missing",
            "file": str(change_yaml),
            "fix_hint": rule["fix_hint"],
        }

    return None


def _check_task_link(
    change_dir: Path,
    rule: dict,
) -> dict | None:
    """Check if change has a task link."""
    change_yaml = change_dir / "change.yaml"
    if not change_yaml.exists():
        return {
            "rule_id": rule["id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "passed": False,
            "message": "L2 readiness: change.yaml is missing",
            "file": str(change_yaml),
            "fix_hint": rule["fix_hint"],
        }

    with open(change_yaml) as f:
        content = f.read()

    if "tasks:" not in content:
        return {
            "rule_id": rule["id"],
            "type": rule["type"],
            "severity": rule["severity"],
            "passed": False,
            "message": "L2 readiness: task link is missing",
            "file": str(change_yaml),
            "fix_hint": rule["fix_hint"],
        }

    return None


def log_violations(
    violations: list[dict],
    scope: str,
    task_dir: Path | None,
    repo_root: Path,
) -> None:
    """Log violations to rule-events.jsonl."""
    if not violations:
        return

    log_dir = repo_root / ".cowork-flow" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "rule-events.jsonl"

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "task_dir": str(task_dir) if task_dir else None,
        "violations": violations,
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate workflow rules")
    parser.add_argument("scope", choices=["task_start", "task_complete", "check", "implement"])
    parser.add_argument("--task-dir", help="Task directory path")
    parser.add_argument("--repo-root", default=".", help="Repository root path")

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    task_dir = Path(args.task_dir).resolve() if args.task_dir else None

    violations = validate_rules(repo_root, args.scope, task_dir)

    if violations:
        log_violations(violations, args.scope, task_dir, repo_root)
        for v in violations:
            print(json.dumps(v, ensure_ascii=False))
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
