#!/usr/bin/env python3
"""Plan template language and structure checks for strict task start.

The checks are intentionally structural: a plan must use the configured
language's title marker, the six template sections, task-heading prefixes and a
filled spec-check line. Prose, step status, acceptance text and evidence
matching stay out of scope.
"""

from __future__ import annotations

import re

from services.decision_anchor_schema import (
    DEFAULT_LANGUAGE,
    is_spec_check_result_line,
    spec_check_example,
    spec_check_label,
    structural_lines,
)

PLAN_TITLE_MARKERS: dict[str, str] = {
    "zh-CN": "实施计划",
    "en-US": "Implementation Plan",
}

PLAN_SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "zh-CN": (
        "目标",
        "验收标准",
        "全局约束",
        "文件边界",
        "任务",
        "最终验证",
    ),
    "en-US": (
        "Goal",
        "Acceptance Criteria",
        "Global Constraints",
        "File Boundaries",
        "Tasks",
        "Final Verification",
    ),
}

PLAN_TASK_PREFIXES: dict[str, str] = {
    "zh-CN": "任务",
    "en-US": "Task",
}

H1_RE = re.compile(r"^#(?!#)\s+(.+?)\s*$")
H2_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
H3_RE = re.compile(r"^###\s+(.+?)\s*$")

GOAL_LINE_RE = re.compile(r"^\*\*(?:Goal|目标):\*\*\s*(.+?)\s*$")
GOAL_BOLD_COLON_RE = re.compile(r"^\*\*(?:Goal|目标)\*\*:\s*(.+?)\s*$")
GOAL_TABLE_RE = re.compile(
    r"^\|\s*\*\*(?:Goal|目标)\*\*\s*\|\s*(.+?)\s*\|\s*$"
)
PLAN_AC_RE = re.compile(
    r"^\s*-\s*(?:\[[ xX]\]\s*)?(AC-\d{3})\s*[:：]\s*(.+?)\s*$"
)


def _language(language: str) -> str:
    return language if language in PLAN_SECTION_HEADINGS else DEFAULT_LANGUAGE


def _headings(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    h1: list[str] = []
    h2: list[str] = []
    h3: list[str] = []
    for raw in lines:
        line = raw.strip()
        match = H3_RE.match(line)
        if match:
            h3.append(match.group(1))
            continue
        match = H2_RE.match(line)
        if match:
            h2.append(match.group(1))
            continue
        match = H1_RE.match(line)
        if match:
            h1.append(match.group(1))
    return h1, h2, h3


def _section_lines(lines: list[str], heading: str) -> list[str]:
    body: list[str] = []
    inside = False
    for raw in lines:
        line = raw.strip()
        match = H2_RE.match(line)
        if match:
            inside = match.group(1) == heading
            continue
        if inside:
            body.append(raw)
    return body


def _task_prefix_blocker(heading: str, language: str, prefix: str) -> str | None:
    lowered = heading.lower()
    if not (heading.startswith("任务") or lowered.startswith("task")):
        return None
    if heading.startswith(prefix):
        return None
    return (
        f"plan task heading '### {heading}' must use the {language} prefix "
        f"'### {prefix} N：'"
        if language == "zh-CN"
        else f"plan task heading '### {heading}' must use the {language} prefix "
        f"'### {prefix} N:'"
    )


def plan_goal(text: str) -> str | None:
    """First machine-readable plan goal line, then the legacy table row."""
    for raw in structural_lines(text):
        line = raw.strip()
        for pattern in (GOAL_LINE_RE, GOAL_BOLD_COLON_RE, GOAL_TABLE_RE):
            match = pattern.match(line)
            if match:
                return match.group(1).strip()
    return None


def plan_acceptance_criteria(
    text: str,
    language: str,
) -> list[dict[str, str]]:
    """Acceptance rows declared by the plan, in document order."""
    resolved = _language(language)
    heading = PLAN_SECTION_HEADINGS[resolved][1]
    rows: list[dict[str, str]] = []
    for raw in _section_lines(structural_lines(text), heading):
        match = PLAN_AC_RE.match(raw)
        if match:
            rows.append({"id": match.group(1), "text": match.group(2).strip()})
    return rows


def section_body(text: str, heading: str) -> list[str]:
    """Raw lines under one `##` heading, excluding fenced code."""
    return _section_lines(structural_lines(text), heading)


def plan_template_blockers(
    text: str,
    language: str,
    *,
    dev_type: str | None = None,
) -> list[str]:
    """Why a plan does not match the configured-language template shape."""
    if not text.strip():
        return ["plan is empty"]
    resolved = _language(language)
    expected = PLAN_SECTION_HEADINGS[resolved]
    other = "en-US" if resolved == "zh-CN" else "zh-CN"
    other_headings = set(PLAN_SECTION_HEADINGS[other])
    lines = structural_lines(text)
    h1, h2, h3 = _headings(lines)
    blockers: list[str] = []

    marker = PLAN_TITLE_MARKERS[resolved]
    if not h1:
        blockers.append(
            f"plan is missing a top-level title; expected: # <功能> {marker}"
        )
    elif marker not in h1[0]:
        blockers.append(
            f"plan title must contain '{marker}' for {resolved}; "
            f"expected: # <功能> {marker}"
        )

    wrong_language = [heading for heading in h2 if heading in other_headings]
    if wrong_language:
        blockers.append(
            f"plan uses {other} plan headings in a {resolved} project: "
            + ", ".join(f"## {heading}" for heading in wrong_language)
            + "; expected: "
            + ", ".join(f"## {heading}" for heading in expected)
        )
    else:
        missing = [heading for heading in expected if heading not in h2]
        if missing:
            blockers.append(
                f"plan is missing required {resolved} template heading(s): "
                + ", ".join(f"## {heading}" for heading in missing)
            )
        else:
            positions = [h2.index(heading) for heading in expected]
            if positions != sorted(positions):
                blockers.append(
                    f"plan template headings are out of order; expected: "
                    + " -> ".join(f"## {heading}" for heading in expected)
                )

    prefix = PLAN_TASK_PREFIXES[resolved]
    for heading in h3:
        blocker = _task_prefix_blocker(heading, resolved, prefix)
        if blocker is not None:
            blockers.append(blocker)
            break

    final_heading = expected[-1]
    if final_heading in h2:
        body = _section_lines(lines, final_heading)
        if not any(
            spec_check_label(resolved) in line
            and is_spec_check_result_line(line, resolved)
            for line in body
        ):
            blockers.append(
                f"plan `## {final_heading}` is missing a filled spec-check "
                f"result; expected a line starting with '{spec_check_label(resolved)}' "
                f"and containing 'pass' or 'not_applicable', e.g. "
                f"{spec_check_example(resolved, dev_type)}"
            )

    return blockers
