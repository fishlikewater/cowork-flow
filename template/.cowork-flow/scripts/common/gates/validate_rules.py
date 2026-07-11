#!/usr/bin/env python3
"""
Rule validation script for cowork-flow workflow.

Validates rules at task lifecycle checkpoints.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from common.task.decision_review import validate_decision_review_file


RULES_RELATIVE_PATH = ".cowork-flow/spec/runtime/rules.json"
REQUIRED_RULE_FIELDS = (
    "id",
    "type",
    "severity",
    "scope",
    "condition",
    "message",
    "fix_hint",
    "source_file",
    "enforcement",
    "validator",
)
ENUM_RULE_FIELDS = {
    "type": {"phase_gate", "forbidden_action"},
    "severity": {"block", "warn"},
    "scope": {"task_start", "task_review", "task_complete", "check", "implement", "all"},
    "enforcement": {
        "validate_rules",
        "validate_implementation",
        "tdd_evidence",
        "host_contract",
        "metadata_only",
    },
}


class RuleParameterError(ValueError):
    """Raised when runtime rule validator parameters are invalid."""


RuntimeRuleValidator = Callable[
    [dict, Path, Optional[Path], Mapping[str, object]],
    Optional[dict],
]


def runtime_rules_path(repo_root: Path) -> Path:
    """Return the runtime rules file path for a repository."""
    return repo_root / ".cowork-flow" / "spec" / "runtime" / "rules.json"


def config_violation(
    rule_id: str,
    message: str,
    file_path: Path,
    fix_hint: str,
) -> dict:
    """Build a block violation for invalid rule configuration."""
    return {
        "rule_id": rule_id,
        "type": "rules_config",
        "severity": "block",
        "passed": False,
        "message": message,
        "file": str(file_path),
        "fix_hint": fix_hint,
    }


def load_runtime_rules(repo_root: Path) -> tuple[list[dict], list[dict]]:
    """Load runtime rules and return (rules, configuration violations)."""
    rules_path = runtime_rules_path(repo_root)
    if not rules_path.exists():
        return [], [
            config_violation(
                "RULES-CONFIG-001",
                "Runtime workflow rules file is missing",
                rules_path,
                f"Restore {RULES_RELATIVE_PATH} from the cowork-flow template.",
            )
        ]

    try:
        with open(rules_path, encoding="utf-8") as f:
            rules_data = json.load(f)
    except json.JSONDecodeError as exc:
        return [], [
            config_violation(
                "RULES-CONFIG-002",
                f"Runtime workflow rules file is invalid JSON: {exc}",
                rules_path,
                f"Fix JSON syntax in {RULES_RELATIVE_PATH}.",
            )
        ]

    if not isinstance(rules_data, dict):
        return [], [
            config_violation(
                "RULES-CONFIG-003",
                "Runtime workflow rules file must contain an object",
                rules_path,
                f"Rewrite {RULES_RELATIVE_PATH} as an object with schemaVersion and rules.",
            )
        ]

    if rules_data.get("schemaVersion") != 1:
        return [], [
            config_violation(
                "RULES-CONFIG-004",
                "Runtime workflow rules file must declare schemaVersion 1",
                rules_path,
                f"Set schemaVersion to 1 in {RULES_RELATIVE_PATH}.",
            )
        ]

    rules = rules_data.get("rules")
    if not isinstance(rules, list):
        return [], [
            config_violation(
                "RULES-CONFIG-003",
                "Runtime workflow rules file must contain a rules array",
                rules_path,
                f"Add a rules array to {RULES_RELATIVE_PATH}.",
            )
        ]

    schema_violations = _validate_runtime_rule_metadata(rules, rules_path)
    if schema_violations:
        return [], schema_violations

    return rules, []


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _rule_schema_violation(rules_path: Path, detail: str) -> dict:
    return config_violation(
        "RULES-CONFIG-004",
        f"Runtime workflow rule metadata is invalid: {detail}",
        rules_path,
        f"Fix rule metadata in {RULES_RELATIVE_PATH}.",
    )


def _validate_runtime_rule_metadata(rules: list[object], rules_path: Path) -> list[dict]:
    violations: list[dict] = []
    seen_ids: set[str] = set()

    for index, raw_rule in enumerate(rules, start=1):
        label = f"rule #{index}"
        if not isinstance(raw_rule, dict):
            violations.append(_rule_schema_violation(rules_path, f"{label} must be an object"))
            continue

        rule_id = raw_rule.get("id")
        if _is_nonempty_string(rule_id):
            label = f"rule {rule_id}"
            if rule_id in seen_ids:
                violations.append(_rule_schema_violation(rules_path, f"{label} is duplicated"))
            seen_ids.add(rule_id)

        missing_fields = [
            field
            for field in REQUIRED_RULE_FIELDS
            if not _is_nonempty_string(raw_rule.get(field))
        ]
        if missing_fields:
            violations.append(
                _rule_schema_violation(
                    rules_path,
                    f"{label} is missing required metadata: {', '.join(missing_fields)}",
                )
            )

        if not isinstance(raw_rule.get("parameters"), dict):
            violations.append(
                _rule_schema_violation(
                    rules_path,
                    f"{label} must define parameters as an object",
                )
            )

        if not (
            _is_nonempty_string(raw_rule.get("source_anchor"))
            or _is_nonempty_string(raw_rule.get("source_excerpt"))
        ):
            violations.append(
                _rule_schema_violation(
                    rules_path,
                    f"{label} must define source_anchor or source_excerpt",
                )
            )

        for field, allowed_values in ENUM_RULE_FIELDS.items():
            value = raw_rule.get(field)
            if _is_nonempty_string(value) and value not in allowed_values:
                allowed = ", ".join(sorted(allowed_values))
                violations.append(
                    _rule_schema_violation(
                        rules_path,
                        f"{label} has invalid {field}: {value}; expected one of {allowed}",
                    )
                )

    return violations


def load_rule_index(repo_root: Path) -> tuple[dict[str, dict], list[dict]]:
    """Load runtime rules keyed by id."""
    rules, violations = load_runtime_rules(repo_root)
    return {
        str(rule.get("id")): rule
        for rule in rules
        if isinstance(rule.get("id"), str) and rule.get("id")
    }, violations


def rule_violation(rule: dict, file_path: Path | str, *, detail: str | None = None) -> dict:
    """Build a violation from runtime rule metadata."""
    violation = {
        "rule_id": rule["id"],
        "type": rule["type"],
        "severity": rule["severity"],
        "passed": False,
        "message": rule["message"],
        "file": str(file_path),
        "fix_hint": rule["fix_hint"],
    }
    for key in ("source_file", "source_anchor", "source_excerpt"):
        if key in rule:
            violation[key] = rule[key]
    if detail:
        violation["detail"] = detail
    return violation


def validate_rules(
    repo_root: Path,
    scope: str,
    task_dir: Path | None = None,
) -> list[dict]:
    """
    Validate rules for given scope.

    Args:
        repo_root: Repository root path
        scope: Validation scope such as task_start, task_review, or task_complete
        task_dir: Optional task directory path

    Returns:
        List of violations (empty if all rules pass)
    """
    rules, config_violations = load_runtime_rules(repo_root)
    if config_violations:
        return config_violations

    # Filter rules by scope
    applicable_rules = [
        r for r in rules
        if r["enforcement"] == "validate_rules"
        and (r["scope"] == scope or r["scope"] == "all")
    ]

    # Validate each rule
    violations = []
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
    """Validate one rule through its registered validator capability."""
    validator_key = rule["validator"]
    validator = RUNTIME_RULE_VALIDATORS.get(validator_key)
    if validator is None:
        return config_violation(
            "RULES-CONFIG-005",
            (
                f"Runtime workflow rule {rule['id']} references unknown "
                f"validator: {validator_key}"
            ),
            runtime_rules_path(repo_root),
            "Register the validator capability or fix the rule validator key.",
        )

    try:
        return validator(rule, repo_root, task_dir, rule["parameters"])
    except RuleParameterError as error:
        return config_violation(
            "RULES-CONFIG-006",
            (
                f"Runtime workflow rule {rule['id']} has invalid parameters "
                f"for {validator_key}: {error}"
            ),
            runtime_rules_path(repo_root),
            "Fix the validator parameters in the runtime rules file.",
        )


def _reject_unknown_parameters(
    parameters: Mapping[str, object],
    allowed: frozenset[str],
) -> None:
    unknown = sorted(set(parameters) - allowed)
    if unknown:
        raise RuleParameterError(
            f"unexpected parameters: {', '.join(unknown)}"
        )


def _string_parameter(
    parameters: Mapping[str, object],
    name: str,
) -> str:
    value = parameters.get(name)
    if not _is_nonempty_string(value):
        raise RuleParameterError(f"{name} must be a non-empty string")
    return str(value)


def _string_list_parameter(
    parameters: Mapping[str, object],
    name: str,
) -> list[str]:
    value = parameters.get(name)
    if not isinstance(value, list) or not value:
        raise RuleParameterError(f"{name} must be a non-empty string array")
    if not all(_is_nonempty_string(item) for item in value):
        raise RuleParameterError(f"{name} must contain only non-empty strings")
    return [str(item) for item in value]


def _validate_l2_required_file(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
    parameters: Mapping[str, object],
) -> dict | None:
    _reject_unknown_parameters(parameters, frozenset({"filename"}))
    filename = _string_parameter(parameters, "filename")
    if task_dir is None:
        return None
    change_dir = _find_linked_change(repo_root, task_dir)
    if change_dir is None:
        return None
    return _check_file_exists(change_dir / filename, rule, filename)


def _validate_l2_plan_link(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
    parameters: Mapping[str, object],
) -> dict | None:
    _reject_unknown_parameters(parameters, frozenset())
    if task_dir is None:
        return None
    change_dir = _find_linked_change(repo_root, task_dir)
    if change_dir is None:
        return None
    return _check_plan_link(repo_root, change_dir, rule)


def _validate_l2_task_link(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
    parameters: Mapping[str, object],
) -> dict | None:
    _reject_unknown_parameters(parameters, frozenset())
    if task_dir is None:
        return None
    change_dir = _find_linked_change(repo_root, task_dir)
    if change_dir is None:
        return None
    return _check_task_link(change_dir, task_dir, rule)


def _validate_l2_decision_review(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
    parameters: Mapping[str, object],
) -> dict | None:
    _reject_unknown_parameters(parameters, frozenset({"filename"}))
    filename = _string_parameter(parameters, "filename")
    if task_dir is None:
        return None
    change_dir = _find_linked_change(repo_root, task_dir)
    if change_dir is None or _read_change_level(change_dir) != "L2":
        return None
    evidence_path = task_dir / filename
    issues = validate_decision_review_file(evidence_path)
    if issues:
        return rule_violation(rule, evidence_path, detail=issues[0])
    return None


def _validate_task_status(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
    parameters: Mapping[str, object],
) -> dict | None:
    del repo_root
    _reject_unknown_parameters(parameters, frozenset({"allowed_statuses"}))
    allowed_statuses = _string_list_parameter(parameters, "allowed_statuses")
    if task_dir is None:
        return None
    task_json = task_dir / "task.json"
    if not task_json.exists():
        return None
    with open(task_json, encoding="utf-8") as f:
        task_data = json.load(f)
    if task_data.get("status") not in allowed_statuses:
        return rule_violation(rule, task_json)
    return None


def _validate_decision_anchor(
    rule: dict,
    repo_root: Path,
    task_dir: Path | None,
    parameters: Mapping[str, object],
) -> dict | None:
    del repo_root
    _reject_unknown_parameters(parameters, frozenset({"required_sections"}))
    required_sections = _string_list_parameter(
        parameters,
        "required_sections",
    )
    if task_dir is None:
        return None
    anchor_path = task_dir / "decision-anchor.md"
    if not anchor_path.exists():
        return rule_violation(
            rule,
            anchor_path,
            detail="decision-anchor.md is missing",
        )
    with open(anchor_path, encoding="utf-8") as f:
        content = f.read()
    missing_sections = [
        section
        for section in required_sections
        if f"## {section}" not in content
    ]
    if missing_sections:
        return rule_violation(
            rule,
            anchor_path,
            detail=(
                "decision-anchor.md is missing sections: "
                + ", ".join(missing_sections)
            ),
        )
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
                with open(change_yaml, encoding="utf-8") as f:
                    content = f.read()
                if task_name in content:
                    return change_dir

    return None


def _read_change_level(change_dir: Path) -> str | None:
    change_yaml = change_dir / "change.yaml"
    if not change_yaml.is_file():
        return None
    with change_yaml.open("r", encoding="utf-8") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if line.startswith("level:"):
                return line.split(":", 1)[1].strip()
    return None


def _metadata_has_link(content: str, keys: tuple[str, ...]) -> bool:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() not in keys:
            continue
        normalized_value = value.strip()
        if normalized_value and normalized_value != "null":
            return True
    return False


def _check_file_exists(
    file_path: Path,
    rule: dict,
    filename: str,
) -> dict | None:
    """Check if a required file exists and is not empty."""
    if not file_path.exists():
        return rule_violation(rule, file_path, detail=f"{filename} is missing")

    if file_path.stat().st_size == 0:
        return rule_violation(rule, file_path, detail=f"{filename} is empty")

    return None


def _check_plan_link(
    repo_root: Path,
    change_dir: Path,
    rule: dict,
) -> dict | None:
    """Check if change has a plan link."""
    change_yaml = change_dir / "change.yaml"
    if not change_yaml.exists():
        return rule_violation(rule, change_yaml, detail="change.yaml is missing")

    with open(change_yaml, encoding="utf-8") as f:
        content = f.read()

    if not _metadata_has_link(content, ("plan",)):
        return rule_violation(rule, change_yaml, detail="plan link is missing")

    return None


def _check_task_link(
    change_dir: Path,
    task_dir: Path,
    rule: dict,
) -> dict | None:
    """Check if change references ``task_dir`` via ``task:``/``tasks:`` or any
    list-item match in ``change.yaml``."""
    change_yaml = change_dir / "change.yaml"
    if not change_yaml.exists():
        return rule_violation(rule, change_yaml, detail="change.yaml is missing")

    with open(change_yaml, encoding="utf-8") as f:
        content = f.read()

    if _metadata_has_link(content, ("task", "tasks")):
        return None

    task_name = task_dir.name
    for raw in content.splitlines():
        stripped = raw.strip().lstrip("-").strip().strip("#").strip().strip('"').strip("'").strip(",")
        if stripped == task_name:
            return None

    return rule_violation(rule, change_yaml, detail="task link is missing")


RUNTIME_RULE_VALIDATORS: dict[str, RuntimeRuleValidator] = {
    "runtime.l2_required_file": _validate_l2_required_file,
    "runtime.l2_plan_link": _validate_l2_plan_link,
    "runtime.l2_task_link": _validate_l2_task_link,
    "runtime.l2_decision_review": _validate_l2_decision_review,
    "runtime.task_status": _validate_task_status,
    "runtime.decision_anchor": _validate_decision_anchor,
}


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

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate workflow rules")
    parser.add_argument("scope", choices=["task_start", "task_review", "task_complete", "check", "implement"])
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
