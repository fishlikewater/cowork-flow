#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rules engine — loads rules.json and checks task lifecycle compliance.

Provides:
    load_rules         — load and self-validate rules.json
    check_scope        — filter violations by lifecycle scope
    check_all_scopes   — run all active scope checks
    format_violations  — human-readable violation output
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


def _get_rules_path(repo_root: Path) -> Path:
    return repo_root / ".cowork-flow" / "spec" / "runtime" / "rules.json"


def load_rules(repo_root: Path) -> list[dict]:
    """Load rules.json with minimal structural self-validation.

    Returns the list of rule dicts. Missing or unreadable file returns [].
    """
    rules_path = _get_rules_path(repo_root)
    if not rules_path.is_file():
        return []
    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        return []
    return [_validate_rule(r) for r in rules if _is_valid_rule(r)]


def _is_valid_rule(rule: object) -> bool:
    """Minimal structural check for a single rule dict."""
    if not isinstance(rule, dict):
        return False
    required = ("id", "type", "severity", "scope", "condition", "message", "fix_hint", "source_file", "enforcement")
    if not all(rule.get(f) for f in required):
        return False
    if not re.match(r"^R-[A-Z]+-\d{3}$", rule["id"]):
        return False
    if rule["type"] not in ("phase_gate", "forbidden_action"):
        return False
    if rule["severity"] not in ("block", "warn"):
        return False
    return True


def _validate_rule(rule: dict) -> dict:
    """Return a normalized rule with default optional fields."""
    rule.setdefault("source_excerpt", "")
    rule.setdefault("source_anchor", "")
    return rule


# ---------------------------------------------------------------------------
# Scope checking
# ---------------------------------------------------------------------------


SCOPE_TASK_START = frozenset({"task_start", "all"})
SCOPE_TASK_REVIEW = frozenset({"task_review", "all"})
SCOPE_TASK_COMPLETE = frozenset({"task_complete", "all"})
SCOPE_IMPLEMENT = frozenset({"implement", "all"})


def _rule_matches_scope(rule: dict, scope: str) -> bool:
    """Check if a rule applies to the given scope."""
    rule_scope = rule.get("scope", "")
    return rule_scope in {"all", scope}


def check_scope(
    rules: list[dict],
    scope: str,
    task_dir: Path,
    repo_root: Path,
) -> list[dict]:
    """Check all rules matching the given scope.

    Returns a list of violation dicts. Each violation has:
    rule_id, severity, message, fix_hint, file.
    """
    violations: list[dict] = []
    for rule in rules:
        if not _rule_matches_scope(rule, scope):
            continue
        enforcement = rule.get("enforcement", "")
        if enforcement in ("host_contract", "tdd_evidence", "metadata_only"):
            continue
        if enforcement == "validate_implementation" and scope in ("task_start", "task_review"):
            continue
        # phase_gate rules handled inline
        if rule["type"] == "phase_gate":
            violation = _check_phase_gate(rule, scope, task_dir, repo_root)
            if violation:
                violations.append(violation)
    return violations


# ---------------------------------------------------------------------------
# Phase gate checkers (by rule ID)
# ---------------------------------------------------------------------------


def _check_phase_gate(
    rule: dict,
    scope: str,
    task_dir: Path,
    repo_root: Path,
) -> dict | None:
    """Execute a phase_gate rule check. Returns violation dict or None."""
    rule_id = rule["id"]

    # R-WF-008: task directory must have prd.md + at least one jsonl
    if rule_id == "R-WF-008":
        return _check_prd_and_jsonl(rule, task_dir)

    # R-WF-001–005: L2 readiness (delegated links + file presence)
    if rule_id in ("R-WF-001", "R-WF-002", "R-WF-003", "R-WF-004", "R-WF-005"):
        return _check_l2_readiness(rule, task_dir, repo_root)

    # R-WF-007: task_complete requires prior review evidence
    if rule_id == "R-WF-007":
        return _check_review_evidence(rule, task_dir)

    # R-WF-009: L0 task with linked change.yaml → warn
    if rule_id == "R-WF-009":
        return _check_l0_change_link(rule, task_dir, repo_root)

    return None


def _check_prd_and_jsonl(rule: dict, task_dir: Path) -> dict | None:
    """R-WF-008: prd.md + at least one jsonl context file."""
    prd = task_dir / "prd.md"
    jsonl_files = ("implement.jsonl", "check.jsonl", "debug.jsonl")
    has_jsonl = any((task_dir / f).is_file() and (task_dir / f).stat().st_size > 0 for f in jsonl_files)
    if not prd.is_file() or prd.stat().st_size == 0 or not has_jsonl:
        return {
            "rule_id": rule["id"],
            "severity": rule["severity"],
            "message": rule["message"],
            "fix_hint": rule["fix_hint"],
            "file": "",
        }
    return None


def _check_l2_readiness(rule: dict, task_dir: Path, repo_root: Path) -> dict | None:
    """R-WF-001–005: L2 change readiness checks.

    Only triggers when a linked change.yaml has level=L2.
    """
    changes_dir = repo_root / ".cowork-flow" / "changes"
    if not changes_dir.is_dir():
        return None
    for change_dir in changes_dir.iterdir():
        cy = change_dir / "change.yaml"
        if not cy.is_file():
            continue
        try:
            meta = _read_change_meta(cy)
        except Exception:
            continue
        if meta.get("level") != "L2":
            continue
        if meta.get("status") == "archived":
            continue
        # Check if this change references this task
        task_link = str(meta.get("task", ""))
        task_name = task_dir.name
        if task_link and task_name not in task_link and task_link not in str(task_dir):
            continue
        # Now check the specific rule
        if rule["id"] == "R-WF-001" and not (change_dir / "proposal.md").is_file():
            return _violation(rule, change_dir.name)
        if rule["id"] == "R-WF-002" and not (change_dir / "spec.md").is_file():
            return _violation(rule, change_dir.name)
        if rule["id"] == "R-WF-003" and not (change_dir / "design.md").is_file():
            return _violation(rule, change_dir.name)
        if rule["id"] == "R-WF-004" and not meta.get("plan"):
            return _violation(rule, change_dir.name)
        if rule["id"] == "R-WF-005" and not task_link:
            return _violation(rule, change_dir.name)
    return None


def _check_review_evidence(rule: dict, task_dir: Path) -> dict | None:
    """R-WF-007: task_complete requires check evidence in task dir."""
    check_jsonl = task_dir / "check.jsonl"
    review_json = task_dir / "review.json"
    has_review = (
        check_jsonl.is_file() and check_jsonl.stat().st_size > 0
    ) or review_json.is_file()
    if not has_review:
        return {
            "rule_id": rule["id"],
            "severity": rule["severity"],
            "message": rule["message"],
            "fix_hint": rule["fix_hint"],
            "file": "",
        }
    return None


def _check_l0_change_link(rule: dict, task_dir: Path, repo_root: Path) -> dict | None:
    """R-WF-009: L0 task with linked change.yaml → warn."""
    # Check if task has level=L0 (meta or directory marker)
    meta_file = task_dir / "task.json"
    level = "L1"
    if meta_file.is_file():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            level = meta.get("level", "L1")
        except Exception:
            pass
    if level != "L0":
        return None
    # Check if any change.yaml references this task
    changes_dir = repo_root / ".cowork-flow" / "changes"
    if not changes_dir.is_dir():
        return None
    for change_dir in changes_dir.iterdir():
        cy = change_dir / "change.yaml"
        if not cy.is_file():
            continue
        try:
            meta = _read_change_meta(cy)
        except Exception:
            continue
        task_link = str(meta.get("task", ""))
        if task_link and task_dir.name in task_link:
            return {
                "rule_id": rule["id"],
                "severity": "warn",
                "message": rule["message"],
                "fix_hint": rule["fix_hint"],
                "file": str(change_dir / "change.yaml"),
            }
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _violation(rule: dict, change_name: str) -> dict:
    return {
        "rule_id": rule["id"],
        "severity": rule["severity"],
        "message": f"{rule['message']} (change: {change_name})",
        "fix_hint": rule["fix_hint"],
        "file": change_name,
    }


def _read_change_meta(path: Path) -> dict:
    """Read change.yaml as flat metadata."""
    meta: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return meta
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value in ("null", "None"):
            meta[key] = None
        elif value in ("true", "True"):
            meta[key] = True
        elif value in ("false", "False"):
            meta[key] = False
        elif value.isdigit():
            meta[key] = int(value)
        else:
            meta[key] = value
    return meta


def format_violations(violations: list[dict]) -> str:
    """Format violations for human-readable output."""
    if not violations:
        return ""
    lines: list[str] = []
    for v in violations:
        tag = "[BLOCK]" if v.get("severity") == "block" else "[WARN]"
        line = f"  {tag} {v['rule_id']}: {v['message']}"
        if v.get("fix_hint"):
            line += f"\n    fix: {v['fix_hint']}"
        lines.append(line)
    return "\n".join(lines)
