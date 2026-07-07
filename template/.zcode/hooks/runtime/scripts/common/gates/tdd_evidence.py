#!/usr/bin/env python3
"""
TDD 红绿证据校验（task_review / task_complete 阶段）。

读取 <task>/tdd.jsonl，验证每条 evidence 或 exemption 记录的结构完整
性与业务意图。验证结果分两类出口：
- validate_tdd_evidence: 全量校验（review 阶段）
- validate_tdd_red_evidence: 仅检查 red 证据完整性（implement 入口提醒）

acceptanceId 的提取同时支持 AC-001、AC-1、验收标准：1 三种写法。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

EVIDENCE_FILE = "tdd.jsonl"

REQUIRED_EVIDENCE_FIELDS = (
    "acceptanceId",
    "testFile",
    "testName",
    "redCommand",
    "redExitCode",
    "redOutputExcerpt",
    "failureReason",
    "whyThisTestMatters",
    "greenCommand",
    "greenExitCode",
    "broaderVerification",
)

REQUIRED_RED_EVIDENCE_FIELDS = REQUIRED_EVIDENCE_FIELDS[:8]

REQUIRED_EXEMPTION_FIELDS = (
    "acceptanceId",
    "exemptionType",
    "reason",
    "verificationCommand",
)

TDD_REQUIRED_MARKERS = (
    "behavior",
    "bug",
    "cli",
    "runtime",
    "gate",
    "protocol",
    "state",
    "workflow",
    "行为",
    "行为变更",
    "修复",
    "状态",
    "状态机",
    "协议",
    "门禁",
    "阻断",
    "数据格式",
    "错误处理",
    "实现",
    "新增",
    "修改",
)

NON_BEHAVIOR_MARKERS = (
    "docs-only",
    "documentation_only",
    "documentation only",
    "纯文档",
    "仅文档",
    "注释",
    "格式化",
)

SETUP_FAILURE_MARKERS = (
    "syntax",
    "import",
    "environment",
    "setup",
    "fixture",
    "语法",
    "导入",
    "环境",
    "测试设置",
)


def validate_tdd_evidence(task_dir: Path) -> list[dict]:
    """Return TDD evidence violations for a task directory."""
    task_dir = Path(task_dir)
    prd_text = _read_text(task_dir / "decision-anchor.md")
    evidence_path = task_dir / EVIDENCE_FILE

    if not evidence_path.is_file():
        if _task_requires_tdd(prd_text):
            return [
                _violation(
                    "TDD-RED-001",
                    "TDD evidence file is missing for a behavior-change task",
                    evidence_path,
                    "Create tdd.jsonl with red/green evidence. For doc-only tasks, add an exemption: "
                    '{"acceptanceId":"AC-001","type":"exemption","exemptionType":"doc_only",'
                    '"reason":"why no behavior test","verificationCommand":"ls <expected files>"}',
                )
            ]
        return []

    entries, parse_violations = _read_jsonl(evidence_path)
    if parse_violations:
        return parse_violations

    if not entries:
        return [
            _violation(
                "TDD-RED-002",
                "TDD evidence file is empty",
                evidence_path,
                "Add at least one evidence or exemption record.",
            )
        ]

    acceptance_ids = _acceptance_ids(prd_text)
    violations: list[dict] = []
    for index, entry in enumerate(entries, start=1):
        if entry.get("type") == "exemption":
            violations.extend(_validate_exemption(entry, evidence_path, index, acceptance_ids))
        else:
            violations.extend(_validate_evidence(entry, evidence_path, index, acceptance_ids))

    return violations


def validate_tdd_red_evidence(task_dir: Path) -> list[dict]:
    """Return violations when implementation would start without red evidence."""
    task_dir = Path(task_dir)
    prd_text = _read_text(task_dir / "decision-anchor.md")
    if not _task_requires_tdd(prd_text):
        return []

    evidence_path = task_dir / EVIDENCE_FILE
    if not evidence_path.is_file():
        return [_missing_red_evidence_violation(evidence_path)]

    entries, parse_violations = _read_jsonl(evidence_path)
    if parse_violations:
        return parse_violations

    red_entries = [entry for entry in entries if entry.get("type") != "exemption"]
    if not red_entries:
        return [_missing_red_evidence_violation(evidence_path)]

    acceptance_ids = _acceptance_ids(prd_text)
    violations: list[dict] = []
    for index, entry in enumerate(entries, start=1):
        if entry.get("type") == "exemption":
            continue
        violations.extend(_validate_red_evidence(entry, evidence_path, index, acceptance_ids))
    return violations


def _task_requires_tdd(prd_text: str) -> bool:
    lower = prd_text.lower()
    if not lower:
        return False
    if any(marker.lower() in lower for marker in NON_BEHAVIOR_MARKERS):
        return False
    return any(marker.lower() in lower for marker in TDD_REQUIRED_MARKERS)


from common.core.files import read_text_utf8 as _read_text


def _read_jsonl(path: Path) -> tuple[list[dict], list[dict]]:
    entries: list[dict] = []
    violations: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return entries, [
            _violation(
                "TDD-READ-001",
                "Failed to read TDD evidence as UTF-8",
                path,
                "Rewrite tdd.jsonl with UTF-8 encoding.",
            )
        ]

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            violations.append(
                _violation(
                    "TDD-FORMAT-001",
                    f"Invalid JSON in tdd.jsonl line {line_number}",
                    path,
                    "Write one valid JSON object per line.",
                )
            )
            continue
        if not isinstance(data, dict):
            violations.append(
                _violation(
                    "TDD-FORMAT-002",
                    f"tdd.jsonl line {line_number} must be a JSON object",
                    path,
                    "Replace non-object entries with structured evidence records.",
                )
            )
            continue
        entries.append(data)

    return entries, violations


def _acceptance_ids(prd_text: str) -> set[str]:
    """提取验收标准 ID，支持 AC-001、AC-1、验收标准：1 等格式。"""
    ids = set(re.findall(r"\bAC-(\d{1,4})\b", prd_text, re.IGNORECASE))
    ids |= set(re.findall(r"验收标准[：:]\s*(\d+)", prd_text))
    return {f"AC-{n}" for n in ids}


def _validate_evidence(
    entry: dict,
    evidence_path: Path,
    index: int,
    acceptance_ids: set[str],
) -> list[dict]:
    violations = _validate_red_evidence(entry, evidence_path, index, acceptance_ids)
    missing = [
        field
        for field in REQUIRED_EVIDENCE_FIELDS
        if field not in REQUIRED_RED_EVIDENCE_FIELDS and not _has_value(entry, field)
    ]
    if missing:
        violations.append(
            _violation(
                "TDD-FIELD-001",
                f"TDD evidence record {index} is missing required fields: {', '.join(missing)}",
                evidence_path,
                "Fill all red/green evidence fields before review.",
            )
        )

    if entry.get("greenExitCode") != 0:
        violations.append(
            _violation(
                "TDD-GREEN-001",
                f"TDD evidence record {index} greenExitCode must be 0",
                evidence_path,
                "Run the same behavior test after implementation and record success.",
            )
        )

    return violations


def _validate_red_evidence(
    entry: dict,
    evidence_path: Path,
    index: int,
    acceptance_ids: set[str],
) -> list[dict]:
    violations: list[dict] = []
    missing = [field for field in REQUIRED_RED_EVIDENCE_FIELDS if not _has_value(entry, field)]
    if missing:
        violations.append(
            _violation(
                "TDD-FIELD-001",
                f"TDD evidence record {index} is missing required fields: {', '.join(missing)}",
                evidence_path,
                "Fill all red/green evidence fields before review.",
            )
        )

    acceptance_id = str(entry.get("acceptanceId", "")).strip()
    if acceptance_ids and acceptance_id not in acceptance_ids:
        violations.append(
            _violation(
                "TDD-AC-001",
                f"TDD evidence record {index} references unknown acceptanceId: {acceptance_id}",
                evidence_path,
                "Map evidence to a PRD acceptance ID such as AC-001.",
            )
        )

    if entry.get("redExitCode") == 0:
        violations.append(
            _violation(
                "TDD-RED-003",
                f"TDD evidence record {index} redExitCode must be non-zero",
                evidence_path,
                "Capture the failing test result before implementation.",
            )
        )

    failure_reason = str(entry.get("failureReason", "")).lower()
    if any(marker in failure_reason for marker in SETUP_FAILURE_MARKERS):
        violations.append(
            _violation(
                "TDD-RED-004",
                f"TDD evidence record {index} red failure is not target behavior",
                evidence_path,
                "Red failure must come from the missing/incorrect target behavior, not setup noise.",
            )
        )

    return violations


def _missing_red_evidence_violation(evidence_path: Path) -> dict:
    return _violation(
        "TDD-RED-001",
        "TDD red evidence is missing for a behavior-change task",
        evidence_path,
        "Write a failing behavior test and record its red command before implementation.",
    )


def _validate_exemption(
    entry: dict,
    evidence_path: Path,
    index: int,
    acceptance_ids: set[str],
) -> list[dict]:
    violations: list[dict] = []
    missing = [field for field in REQUIRED_EXEMPTION_FIELDS if not _has_value(entry, field)]
    if missing:
        violations.append(
            _violation(
                "TDD-EXEMPT-001",
                f"TDD exemption record {index} is missing required fields: {', '.join(missing)}",
                evidence_path,
                "Record exemptionType, reason, acceptanceId, and verificationCommand.",
            )
        )

    acceptance_id = str(entry.get("acceptanceId", "")).strip()
    if acceptance_ids and acceptance_id not in acceptance_ids:
        violations.append(
            _violation(
                "TDD-EXEMPT-002",
                f"TDD exemption record {index} references unknown acceptanceId: {acceptance_id}",
                evidence_path,
                "Map the exemption to a PRD acceptance ID such as AC-001.",
            )
        )

    from .anti_rationalization import validate_exemption_rationalization
    violations.extend(validate_exemption_rationalization(str(entry.get("reason", ""))))

    return violations


def _has_value(entry: dict, field: str) -> bool:
    value = entry.get(field)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _violation(rule_id: str, message: str, file_path: Path, fix_hint: str) -> dict:
    return {
        "rule_id": rule_id,
        "type": "tdd_evidence",
        "severity": "block",
        "passed": False,
        "message": message,
        "file": str(file_path),
        "fix_hint": fix_hint,
    }
