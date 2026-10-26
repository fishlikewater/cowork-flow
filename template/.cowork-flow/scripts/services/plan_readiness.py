#!/usr/bin/env python3
"""Plan readiness: completeness checks and the approved-plan snapshot."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from infra.config import get_language
from infra.files import read_text_utf8
from infra.paths import DIR_WORKFLOW
from services.decision_anchor_schema import (
    ANGLE_SPAN_RE,
    REQUIRED_SECTIONS,
    VERIFICATION,
    heading_for,
    headings,
    is_spec_check_result_line,
    present_sections,
    section_headings,
    spec_check_example,
    verification_section_lines,
)
from services.plan_binding import plan_file_blockers, plan_template_blockers
from services.plan_schema import (
    plan_acceptance_criteria,
    plan_goal,
)
from services.task_gate_profiles import (
    acceptance_row_blockers,
    declares_light_profile,
    dev_type_blocker,
)
from services.task_repository import TaskRepository, TaskRepositoryError


PLAN_READY_KEY = "planReady"
TASK_HEADING_RE = re.compile(r"^###\s+(?:任务|Task)\s+\d+\s*[:：]\s*(.+?)\s*$")
H2_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
BOLD_LABEL_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
FENCE_RE = re.compile(r"^(```|~~~)")
PLAN_TEMPLATE_PATH = f"{DIR_WORKFLOW}/templates/plan-template.md"

TASK_FIELDS = {
    "zh-CN": (
        "目的",
        "代码事实来源",
        "文件边界",
        "关键符号",
        "实现说明",
        "测试证明",
        "验证命令",
        "完成条件",
        "禁止漂移",
        "偏差条件",
    ),
    "en-US": (
        "Purpose",
        "Code Fact Sources",
        "File Boundaries",
        "Key Symbols",
        "Implementation Notes",
        "Test Proof",
        "Verification Command",
        "Completion Conditions",
        "Prohibited Drift",
        "Deviation Conditions",
    ),
}
TINY_TASK_FIELDS = {
    "zh-CN": ("文件边界", "验证命令", "完成条件"),
    "en-US": ("File Boundaries", "Verification Command", "Completion Conditions"),
}


class PlanReadinessError(RuntimeError):
    """Raised when a plan is not ready for human review."""

    def __init__(self, blockers: list[str]) -> None:
        self.blockers = tuple(blockers)
        super().__init__("plan is not ready")


class PlanReadinessService:
    """Validate planning artifacts and persist the reviewed snapshot."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.repository = TaskRepository(self.repo_root)

    def finalize(self, task_dir: Path) -> dict:
        task_dir = Path(task_dir)
        task_data = self._load_task(task_dir)
        language = get_language(self.repo_root)
        blockers = plan_readiness_blockers(
            self.repo_root,
            task_dir,
            task_data,
            language=language,
        )
        if blockers:
            raise PlanReadinessError(blockers)

        plan_path = _plan_path(self.repo_root, task_data)
        anchor_path = task_dir / "decision-anchor.md"
        snapshot = {
            "planDigest": _file_digest(plan_path),
            "anchorDigest": _file_digest(anchor_path),
            "readyAt": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "devType": _dev_type(task_data),
        }
        meta = dict(task_data.get("meta") or {})
        meta[PLAN_READY_KEY] = snapshot
        try:
            self.repository.save(task_dir, {"meta": meta})
        except TaskRepositoryError as error:
            raise PlanReadinessError(
                [f"task.json could not be updated with the plan-ready snapshot: {error}"]
            ) from error
        return snapshot

    def _load_task(self, task_dir: Path) -> dict:
        try:
            return self.repository.load(task_dir)
        except TaskRepositoryError as error:
            raise PlanReadinessError(
                [f"task.json could not be read: {error}"]
            ) from error


def plan_readiness_blockers(
    repo_root: Path,
    task_dir: Path,
    task_data: dict,
    *,
    language: str | None = None,
) -> list[str]:
    """Why the planning artifacts are not ready for human review."""
    repo_root = Path(repo_root)
    task_dir = Path(task_dir)
    resolved_language = language or get_language(repo_root)
    blockers = _planning_status_blockers(task_data)

    blocking_plan_facts = plan_file_blockers(repo_root, task_data)
    blockers.extend(blocking_plan_facts)
    if blocking_plan_facts:
        return blockers
    blockers.extend(
        plan_template_blockers(repo_root, task_data, resolved_language)
    )

    plan_path = _plan_path(repo_root, task_data)
    plan_text = read_text_utf8(plan_path)
    if not plan_text.strip():
        blockers.append(f"plan is empty: {_display(repo_root, plan_path)}")
        return blockers

    goal, acceptance, content_blockers = _plan_content_blockers(
        plan_text, resolved_language
    )
    blockers.extend(content_blockers)

    template_path = repo_root / PLAN_TEMPLATE_PATH
    template_text = (
        read_text_utf8(template_path) if template_path.is_file() else ""
    )
    if not template_text.strip():
        blockers.append(
            "installed plan template is missing or empty; run "
            "`cwf project sync .` before finalizing"
        )
        return blockers
    blockers.extend(
        _plan_structure_blockers(
            plan_text,
            template_text,
            task_data,
            resolved_language,
        )
    )
    blockers.extend(
        _anchor_artifact_blockers(
            task_dir,
            task_data,
            goal,
            acceptance,
            resolved_language,
        )
    )
    return blockers


def _planning_status_blockers(task_data: dict) -> list[str]:
    status = task_data.get("status")
    if status == "planning":
        return []
    return [
        "plan finalize only runs on a planning task; "
        f"current status is {status or 'missing'}"
    ]


def _plan_content_blockers(
    plan_text: str,
    language: str,
) -> tuple[str | None, list[dict[str, str]], list[str]]:
    blockers: list[str] = []
    goal = plan_goal(plan_text)
    if not goal:
        blockers.append(
            "plan is missing its machine-readable goal line "
            "(`**目标:**` / `**Goal:**`)"
        )
    elif not _has_concrete_text(goal):
        blockers.append(
            "plan goal line still uses a template placeholder; "
            "replace it with the observable behavior"
        )

    acceptance = plan_acceptance_criteria(plan_text, language)
    if not acceptance:
        blockers.append(
            "plan `## 验收标准` / `## Acceptance Criteria` has no AC-NNN rows"
        )
    else:
        placeholder_rows = [
            row["id"]
            for row in acceptance
            if not _has_concrete_text(row["text"])
        ]
        if placeholder_rows:
            blockers.append(
                "plan acceptance criterion(s) still use template placeholders: "
                + ", ".join(placeholder_rows)
            )
    return goal, acceptance, blockers


def _expected_sections(language: str) -> tuple[str, ...]:
    return {
        "zh-CN": ("目标", "全局约束", "文件边界", "任务"),
        "en-US": ("Goal", "Global Constraints", "File Boundaries", "Tasks"),
    }.get(
        language,
        ("目标", "全局约束", "文件边界", "任务"),
    )


def _plan_structure_blockers(
    plan_text: str,
    template_text: str,
    task_data: dict,
    language: str,
) -> list[str]:
    expected_sections = _expected_sections(language)
    template_sections = {
        heading: _raw_section_lines(template_text, heading)
        for heading in expected_sections
    }
    template_fields = _task_fields(
        template_sections.get(expected_sections[-1], [])
    )
    blockers: list[str] = []

    for heading in expected_sections[:-1]:
        if not _has_meaningful_lines(
            _raw_section_lines(plan_text, heading),
            template_sections.get(heading, []),
        ):
            blockers.append(
                f"plan `## {heading}` has no concrete content; "
                "fill the template placeholder before finalizing"
            )

    task_blocks = _task_blocks(plan_text)
    if not task_blocks:
        blockers.append(
            "plan `## 任务` / `## Tasks` has no `### 任务 N` / `### Task N` block"
        )
    else:
        blockers.extend(
            _task_block_blockers(
                task_blocks,
                task_data,
                language,
                template_fields,
            )
        )
    return blockers


def _task_block_blockers(
    task_blocks: list[dict],
    task_data: dict,
    language: str,
    template_fields: dict[str, list[str]],
) -> list[str]:
    blockers: list[str] = []
    tiny = declares_light_profile(task_data)
    required_fields = TINY_TASK_FIELDS.get(
        language, TINY_TASK_FIELDS["zh-CN"]
    ) if tiny else TASK_FIELDS.get(
        language, TASK_FIELDS["zh-CN"]
    )
    missing_template_fields = [
        field for field in required_fields if field not in template_fields
    ]
    if missing_template_fields:
        blockers.append(
            "installed plan template is missing task brief field(s): "
            + ", ".join(missing_template_fields)
        )
    verification_field = (
        "Verification Command"
        if language == "en-US"
        else "验证命令"
    )
    for block in task_blocks:
        fields = _task_fields(block["lines"])
        missing = [
            field for field in required_fields if field not in fields
        ]
        if missing:
            blockers.append(
                f"plan task `### {block['heading']}` is missing brief "
                f"field(s): {', '.join(missing)}"
            )
            continue
        empty = [
            field
            for field in required_fields
            if (
                not _has_verification_command(fields[field])
                if field == verification_field
                else not _has_meaningful_lines(
                    fields[field], template_fields.get(field, [])
                )
            )
        ]
        if empty:
            blockers.append(
                f"plan task `### {block['heading']}` has empty brief "
                f"field(s): {', '.join(empty)}"
            )
    return blockers


def _anchor_artifact_blockers(
    task_dir: Path,
    task_data: dict,
    goal: str | None,
    acceptance: list[dict[str, str]],
    language: str,
) -> list[str]:
    blockers: list[str] = []
    anchor_path = task_dir / "decision-anchor.md"
    anchor_text = read_text_utf8(anchor_path)
    if not anchor_text.strip():
        blockers.append("decision-anchor.md is missing or empty")
    else:
        blockers.extend(_anchor_blockers(anchor_text, language))
        blockers.extend(acceptance_row_blockers(anchor_text))
        blockers.extend(
            _anchor_spec_check_blockers(
                anchor_text,
                language,
                _dev_type(task_data),
            )
        )
        blockers.extend(_acceptance_sync_blockers(acceptance, anchor_text))
        blockers.extend(_goal_sync_blockers(goal, anchor_text))

    implement_index = task_dir / "implement.jsonl"
    if not read_text_utf8(implement_index).strip():
        blockers.append("implement.jsonl is missing or empty")

    blockers.extend(dev_type_blocker(task_data))
    return blockers


def plan_ready_snapshot_blockers(
    repo_root: Path,
    task_dir: Path,
    task_data: dict,
    *,
    required: bool,
) -> list[str]:
    """Why the stored plan-ready snapshot is absent or no longer current."""
    meta = task_data.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    snapshot = meta.get(PLAN_READY_KEY)
    if not isinstance(snapshot, dict):
        if not required:
            return []
        return [
            "strict task has no plan-ready snapshot; run plan finalize "
            f"`{_display(Path(repo_root), Path(task_dir))}` "
            "before human review/start"
        ]

    plan_path = _plan_path(Path(repo_root), task_data)
    anchor_path = Path(task_dir) / "decision-anchor.md"
    if not plan_path.is_file():
        return [
            "plan-ready snapshot is stale: the bound plan file is missing; "
            "restore it and rerun `plan finalize`"
        ]
    if not anchor_path.is_file():
        return [
            "plan-ready snapshot is stale: decision-anchor.md is missing; "
            "restore it and rerun `plan finalize`"
        ]
    if snapshot.get("planDigest") != _file_digest(plan_path) or snapshot.get(
        "anchorDigest"
    ) != _file_digest(anchor_path) or snapshot.get("devType") != _dev_type(
        task_data
    ):
        return [
            "plan-ready snapshot is stale: the plan, decision-anchor, or "
            "dev_type changed after finalize; rerun `plan finalize` and "
            "review the new version"
        ]
    return []


def _file_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dev_type(task_data: dict) -> str | None:
    value = task_data.get("dev_type")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _display(repo_root: Path, path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _plan_path(repo_root: Path, task_data: dict) -> Path:
    meta = task_data.get("meta")
    plan_file = meta.get("planFile") if isinstance(meta, dict) else None
    if not isinstance(plan_file, str) or not plan_file.strip():
        return repo_root / DIR_WORKFLOW / "plans" / "__missing__"
    return repo_root / plan_file.strip()


def _has_meaningful_lines(
    lines: list[str],
    template_lines: list[str] | tuple[str, ...] = (),
) -> bool:
    """Whether a section or field has content beyond its template body."""
    template = {
        normalized
        for raw in template_lines
        if (normalized := _normalize_placeholder_line(raw.strip()))
        and not normalized.startswith(("```", "~~~"))
    }
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line in ("```", "~~~") or line.startswith(("```", "~~~")):
            continue
        body = _normalize_placeholder_line(line)
        if not body or body in template:
            continue
        if _has_concrete_text(body):
            return True
    return False


def _has_verification_command(lines: list[str]) -> bool:
    """A verification field needs a concrete command inside a code fence."""
    fence: str | None = None
    for raw in lines:
        marker = FENCE_RE.match(raw.strip())
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1) == fence:
                fence = None
            continue
        if fence is None:
            continue
        command = raw.strip()
        if command.startswith(("#", "//")):
            continue
        if _has_concrete_text(command):
            return True
    return False


def _raw_section_lines(text: str, heading: str) -> list[str]:
    """Raw lines under one `##` heading, including fenced code."""
    body: list[str] = []
    inside = False
    for raw in text.splitlines():
        match = H2_RE.match(raw.strip())
        if match:
            inside = match.group(1) == heading
            continue
        if inside:
            body.append(raw)
    return body


def _normalize_placeholder_line(line: str) -> str:
    """Strip list and code-comment markers before template-line comparison."""
    body = line[2:].strip() if line.startswith("- ") else line
    body = body.lstrip("#> ").strip()
    return re.sub(r"\s+", " ", body)


def _has_concrete_text(text: str) -> bool:
    """Whether a line carries content beyond angle-bracket placeholders."""
    cleaned = ANGLE_SPAN_RE.sub("", text)
    return any(char.isalnum() for char in cleaned)


def _task_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None
    fence: str | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        marker = FENCE_RE.match(stripped)
        if marker:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1) == fence:
                fence = None
            if current is not None:
                current["lines"].append(raw)
            continue
        if fence is None:
            task = TASK_HEADING_RE.match(stripped)
            if task:
                if current is not None:
                    blocks.append(current)
                current = {"heading": task.group(1), "lines": []}
                continue
            if H2_RE.match(stripped):
                if current is not None:
                    blocks.append(current)
                    current = None
                continue
        if current is not None:
            current["lines"].append(raw)
    if current is not None:
        blocks.append(current)
    return blocks


def _task_fields(lines: list[str]) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for raw in lines:
        match = BOLD_LABEL_RE.match(raw.strip())
        if match:
            current = match.group(1).strip()
            fields.setdefault(current, [])
            continue
        if current is not None:
            fields[current].append(raw)
    return fields


def _anchor_blockers(anchor_text: str, language: str) -> list[str]:
    present = present_sections(anchor_text)
    blockers = [
        "decision-anchor.md missing required section: "
        + " (or ".join(f"## {heading}" for heading in section_headings(section))
        for section in REQUIRED_SECTIONS
        if section not in present
    ]
    expected = heading_for(VERIFICATION, language)
    if expected not in headings(anchor_text):
        other = heading_for(
            VERIFICATION,
            "en-US" if language == "zh-CN" else "zh-CN",
        )
        if other in headings(anchor_text):
            blockers.append(
                f"decision-anchor.md uses `## {other}`; a {language} task "
                f"requires `## {expected}`"
            )
        else:
            blockers.append(
                f"decision-anchor.md is missing `## {expected}`"
            )
    return blockers


def _anchor_spec_check_blockers(
    anchor_text: str,
    language: str,
    dev_type: str | None,
) -> list[str]:
    expected = heading_for(VERIFICATION, language)
    if expected not in headings(anchor_text):
        return []
    if not any(
        is_spec_check_result_line(line, language)
        for line in verification_section_lines(anchor_text)
    ):
        return [
            f"decision-anchor.md `## {expected}` is missing a filled "
            f"spec-check result, e.g. "
            f"{spec_check_example(language, dev_type)}"
        ]
    return []


def _acceptance_sync_blockers(plan_rows: list[dict[str, str]], anchor_text: str) -> list[str]:
    from services.fact_view import parse_decision_anchor

    anchor_rows = parse_decision_anchor(anchor_text).get("acceptanceCriteria") or []
    plan_ids = [row["id"] for row in plan_rows]
    anchor_ids = [row.get("id") for row in anchor_rows]
    if plan_ids != anchor_ids:
        return [
            "decision-anchor.md acceptance IDs do not match the plan: "
            f"plan={plan_ids or 'none'} anchor={anchor_ids or 'none'}"
        ]
    for plan_row, anchor_row in zip(plan_rows, anchor_rows):
        if plan_row["text"].strip() != str(anchor_row.get("text") or "").strip():
            return [
                f"decision-anchor.md {plan_row['id']} text differs from the plan; "
                "update the anchor before finalizing"
            ]
    return []


def _goal_sync_blockers(plan_goal_text: str | None, anchor_text: str) -> list[str]:
    if not plan_goal_text:
        return []
    from services.fact_view import parse_decision_anchor

    anchor_goal = str(parse_decision_anchor(anchor_text).get("goal") or "").strip()
    if not anchor_goal:
        return ["decision-anchor.md has no goal text"]
    normalized_plan = " ".join(plan_goal_text.split())
    normalized_anchor = " ".join(anchor_goal.split())
    if normalized_plan != normalized_anchor and not normalized_plan.startswith(
        normalized_anchor
    ):
        return [
            "decision-anchor.md goal differs from the plan goal; "
            "align the anchor before finalizing"
        ]
    return []
