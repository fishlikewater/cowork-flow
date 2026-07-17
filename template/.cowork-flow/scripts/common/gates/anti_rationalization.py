#!/usr/bin/env python3
"""Anti-rationalization pattern detection for TDD exemptions."""

from __future__ import annotations

RATIONALIZATION_PATTERNS = (
    "太简单",
    "显而易",
    "没必要",
    "不需要测试",
    "已经有其他测试",
    "肉眼",
    "self-evident",
    "trivial",
    "obvious",
    "no need to test",
    "covered elsewhere",
    "already tested",
    "just a",
    "only a",
)


def validate_exemption_rationalization(reason: str) -> list[dict]:
    """Detect anti-rationalization patterns in TDD exemption reasons.

    Returns violation dicts with rule_id TDD-RATIONALIZE-001.
    Severity is warn (does not block task start/review).
    """
    violations: list[dict] = []
    if not reason:
        return violations
    lower = reason.lower()
    for pattern in RATIONALIZATION_PATTERNS:
        if pattern.lower() in lower:
            violations.append({
                "rule_id": "TDD-RATIONALIZE-001",
                "type": "tdd_evidence",
                "severity": "warn",
                "passed": False,
                "message": (
                    f"TDD exemption reason contains rationalization pattern: "
                    f"'{pattern}'. Replace with a concrete behavior test or "
                    f"specific verification command."
                ),
                "file": "<task>/check.jsonl",
                "fix_hint": (
                    "Remove rationalization from exemption reason. "
                    "Either write a failing behavior test for this AC "
                    "or provide a verification command that exercises "
                    "the claimed unchanged behavior."
                ),
            })
            break
    return violations
