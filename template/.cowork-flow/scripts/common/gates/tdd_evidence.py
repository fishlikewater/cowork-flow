#!/usr/bin/env python3
"""
TDD 红绿证据校验（task_review / task_complete 阶段）。

新任务从 <task>/check.jsonl 读取 TDD evidence 记录，旧任务已有
<task>/tdd.jsonl 时继续兼容读取并校验。普通行为变更缺少显式 red/green
证据只产生 warning；高风险行为变更仍要求显式 red/green evidence。

acceptanceId 的提取同时支持 AC-001、AC-1、验收标准：1 三种写法。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CHECK_EVIDENCE_FILE = "check.jsonl"
LEGACY_EVIDENCE_FILE = "tdd.jsonl"
EVIDENCE_FILE = CHECK_EVIDENCE_FILE

TDD_EVIDENCE_TYPES = frozenset({"tdd", "tdd_evidence"})
TDD_EXEMPTION_TYPES = frozenset({"tdd_exemption", "exemption"})

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

STRICT_TDD_MARKERS = (
    "security",
    "permission",
    "auth",
    "protocol",
    "state machine",
    "migration",
    "public contract",
    "file format",
    "安全",
    "权限",
    "认证",
    "协议",
    "状态机",
    "迁移",
    "公共契约",
    "文件格式",
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
    decision_anchor_text = _read_text(task_dir / "decision-anchor.md")
    records, parse_violations, legacy_file_present, legacy_entry_count = _load_tdd_records(task_dir)
    if parse_violations:
        return parse_violations

    if legacy_file_present and legacy_entry_count == 0:
        return [
            _violation(
                "TDD-RED-002",
                "Legacy TDD evidence file is empty",
                task_dir / LEGACY_EVIDENCE_FILE,
                "Remove the empty legacy file or record TDD evidence in check.jsonl.",
            )
        ]

    if not records:
        if _task_requires_explicit_tdd(decision_anchor_text):
            return [_missing_red_evidence_violation(task_dir / CHECK_EVIDENCE_FILE)]
        if _task_requires_tdd(decision_anchor_text):
            return [_missing_red_evidence_warning(task_dir / CHECK_EVIDENCE_FILE)]
        return []

    acceptance_ids = _acceptance_ids(decision_anchor_text)
    violations: list[dict] = []
    for record_index, (evidence_path, _line_number, entry) in enumerate(records, start=1):
        if is_tdd_exemption(entry):
            violations.extend(_validate_exemption(entry, evidence_path, record_index, acceptance_ids))
        else:
            violations.extend(_validate_evidence(entry, evidence_path, record_index, acceptance_ids))

    return violations


def validate_tdd_red_evidence(task_dir: Path) -> list[dict]:
    """Return violations or warnings for missing red evidence before implementation."""
    task_dir = Path(task_dir)
    decision_anchor_text = _read_text(task_dir / "decision-anchor.md")
    if not _task_requires_tdd(decision_anchor_text):
        return []

    records, parse_violations, _legacy_file_present, _legacy_entry_count = _load_tdd_records(task_dir)
    if parse_violations:
        return parse_violations

    red_records = [
        record
        for record in records
        if not is_tdd_exemption(record[2])
    ]
    if not red_records:
        if _task_requires_explicit_tdd(decision_anchor_text):
            return [_missing_red_evidence_violation(task_dir / CHECK_EVIDENCE_FILE)]
        return [_missing_red_evidence_warning(task_dir / CHECK_EVIDENCE_FILE)]

    acceptance_ids = _acceptance_ids(decision_anchor_text)
    violations: list[dict] = []
    for record_index, (evidence_path, _line_number, entry) in enumerate(red_records, start=1):
        violations.extend(_validate_red_evidence(entry, evidence_path, record_index, acceptance_ids))
    return violations


def tdd_evidence_records(task_dir: Path) -> list[tuple[Path, int, dict]]:
    """Return check.jsonl and legacy tdd.jsonl records that represent TDD evidence."""
    records, _violations, _legacy_file_present, _legacy_entry_count = _load_tdd_records(Path(task_dir))
    return records


def migrate_legacy_tdd_records(task_dir: Path) -> dict:
    """Migrate legacy tdd.jsonl records to check.jsonl and remove the legacy file.

    Returns a summary dict with:
      - migrated: number of records moved
      - skipped: number of duplicate acceptanceIds already in check.jsonl
      - legacy_removed: whether the legacy file was deleted
    """
    task_dir = Path(task_dir)
    legacy_path = task_dir / LEGACY_EVIDENCE_FILE
    check_path = task_dir / CHECK_EVIDENCE_FILE

    if not legacy_path.is_file():
        return {"migrated": 0, "skipped": 0, "legacy_removed": False}

    migrated = 0
    skipped = 0

    # Load existing check.jsonl acceptanceIds for dedup
    existing_ids: set[str] = set()
    if check_path.is_file():
        check_entries, _ = _read_jsonl(check_path, report_invalid=False)
        for _, entry in check_entries:
            aid = str(entry.get("acceptanceId", "")).strip()
            if aid:
                existing_ids.add(aid)

    # Read legacy records
    legacy_entries, _ = _read_jsonl(legacy_path, report_invalid=True)
    new_records: list[dict] = []

    for _, entry in legacy_entries:
        aid = str(entry.get("acceptanceId", "")).strip()
        if aid and aid in existing_ids:
            skipped += 1
            continue
        new_records.append(entry)
        if aid:
            existing_ids.add(aid)
        migrated += 1

    # Append to check.jsonl
    if new_records:
        with check_path.open("a", encoding="utf-8") as stream:
            for record in new_records:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Remove legacy file
    legacy_path.unlink()

    return {
        "migrated": migrated,
        "skipped": skipped,
        "legacy_removed": True,
    }


def is_tdd_exemption(entry: dict) -> bool:
    entry_type = str(entry.get("type") or "").strip()
    return entry_type in TDD_EXEMPTION_TYPES and _has_value(entry, "exemptionType")


def _task_requires_tdd(decision_anchor_text: str) -> bool:
    lower = decision_anchor_text.lower()
    if not lower:
        return False
    if any(marker.lower() in lower for marker in NON_BEHAVIOR_MARKERS):
        return False
    return any(marker.lower() in lower for marker in TDD_REQUIRED_MARKERS)


def _task_requires_explicit_tdd(decision_anchor_text: str) -> bool:
    lower = decision_anchor_text.lower()
    if not _task_requires_tdd(decision_anchor_text):
        return False
    return any(marker.lower() in lower for marker in STRICT_TDD_MARKERS)


from common.core.files import read_text_utf8 as _read_text


def _load_tdd_records(task_dir: Path) -> tuple[list[tuple[Path, int, dict]], list[dict], bool, int]:
    records: list[tuple[Path, int, dict]] = []
    violations: list[dict] = []

    legacy_path = task_dir / LEGACY_EVIDENCE_FILE
    legacy_entry_count = 0
    if legacy_path.is_file():
        legacy_entries, legacy_violations = _read_jsonl(legacy_path, report_invalid=True)
        violations.extend(legacy_violations)
        legacy_entry_count = len(legacy_entries)
        records.extend((legacy_path, line_number, entry) for line_number, entry in legacy_entries)
        violations.append(
            {
                "rule_id": "TDD-LEGACY-001",
                "type": "tdd_legacy_detection",
                "severity": "warn",
                "passed": False,
                "message": (
                    "Legacy tdd.jsonl detected. Migrate evidence to check.jsonl "
                    "using migrate_legacy_tdd_records(task_dir)."
                ),
                "file": str(legacy_path),
                "fix_hint": (
                    "Run migrate_legacy_tdd_records(task_dir) to move records "
                    "to check.jsonl and remove the legacy file."
                ),
            }
        )

    check_path = task_dir / CHECK_EVIDENCE_FILE
    if check_path.is_file():
        check_entries, _check_violations = _read_jsonl(check_path, report_invalid=False)
        records.extend(
            (check_path, line_number, entry)
            for line_number, entry in check_entries
            if _is_tdd_check_record(entry)
        )

    return records, violations, legacy_path.is_file(), legacy_entry_count


def _is_tdd_check_record(entry: dict) -> bool:
    entry_type = str(entry.get("type") or "").strip()
    if entry_type in TDD_EVIDENCE_TYPES or entry_type == "tdd_exemption":
        return True
    if is_tdd_exemption(entry):
        return True
    return any(field in entry for field in ("redCommand", "greenCommand", "redExitCode", "greenExitCode"))


def _read_jsonl(path: Path, *, report_invalid: bool) -> tuple[list[tuple[int, dict]], list[dict]]:
    entries: list[tuple[int, dict]] = []
    violations: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        if report_invalid:
            violations.append(
                _violation(
                    "TDD-READ-001",
                    "Failed to read TDD evidence as UTF-8",
                    path,
                    "Rewrite the evidence file with UTF-8 encoding.",
                )
            )
        return entries, violations

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            if report_invalid:
                violations.append(
                    _violation(
                        "TDD-FORMAT-001",
                        f"Invalid JSON in TDD evidence line {line_number}",
                        path,
                        "Write one valid JSON object per line.",
                    )
                )
            continue
        if not isinstance(data, dict):
            if report_invalid:
                violations.append(
                    _violation(
                        "TDD-FORMAT-002",
                        f"TDD evidence line {line_number} must be a JSON object",
                        path,
                        "Replace non-object entries with structured evidence records.",
                    )
                )
            continue
        entries.append((line_number, data))

    return entries, violations


def _acceptance_ids(decision_anchor_text: str) -> set[str]:
    """提取验收标准 ID，支持 AC-001、AC-1、验收标准：1 等格式。"""
    ids = set(re.findall(r"\bAC-(\d{1,4})\b", decision_anchor_text, re.IGNORECASE))
    ids |= set(re.findall(r"验收标准[：:]\s*(\d+)", decision_anchor_text))
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
                "Map evidence to a decision-anchor acceptance criterion such as AC-001.",
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
        "TDD red-green evidence is missing for a high-risk behavior-change task",
        evidence_path,
        "Record a tdd evidence object in check.jsonl with redCommand, redExitCode, greenCommand, greenExitCode, and acceptanceId.",
    )


def _missing_red_evidence_warning(evidence_path: Path) -> dict:
    return _violation(
        "TDD-RED-WARN-001",
        "TDD red-green evidence is not recorded for this behavior-change task",
        evidence_path,
        "Prefer recording red/green evidence in check.jsonl when the change was developed TDD-first.",
        severity="warn",
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
                "Map the exemption to a decision-anchor acceptance criterion such as AC-001.",
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


def _violation(
    rule_id: str,
    message: str,
    file_path: Path,
    fix_hint: str,
    *,
    severity: str = "block",
) -> dict:
    return {
        "rule_id": rule_id,
        "type": "tdd_evidence",
        "severity": severity,
        "passed": False,
        "message": message,
        "file": str(file_path),
        "fix_hint": fix_hint,
    }
