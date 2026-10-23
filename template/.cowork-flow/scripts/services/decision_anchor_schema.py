#!/usr/bin/env python3
"""Shared decision-anchor heading schema.

The runtime recognizes two heading sets for the same sections: the historical
Chinese set and the English aliases introduced for English-language task
artifacts. Recognition is language-independent so existing tasks and mixed
language projects keep working; the configured project language only decides
which set a newly generated anchor uses.
"""

from __future__ import annotations

import re

GOAL = "goal"
ACCEPTANCE = "acceptance"
REJECTED = "rejected"
ASSUMPTIONS = "assumptions"
SCOPE = "scope"
VERIFICATION = "verification"

REQUIRED_SECTIONS = (GOAL, ACCEPTANCE)

DEFAULT_LANGUAGE = "zh-CN"

SPEC_CHECK_LABELS: dict[str, str] = {
    "zh-CN": "规范核对：",
    "en-US": "Spec check:",
}

LANGUAGE_HEADINGS: dict[str, dict[str, str]] = {
    "zh-CN": {
        GOAL: "目标",
        ACCEPTANCE: "验收标准",
        REJECTED: "被拒方案",
        ASSUMPTIONS: "关键假设",
        SCOPE: "范围边界",
        VERIFICATION: "验证命令",
    },
    "en-US": {
        GOAL: "Goal",
        ACCEPTANCE: "Acceptance Criteria",
        REJECTED: "Rejected Options",
        ASSUMPTIONS: "Key Assumptions",
        SCOPE: "Scope Boundary",
        VERIFICATION: "Verification Commands",
    },
}

SECTION_ALIASES: dict[str, str] = {
    heading: section
    for headings in LANGUAGE_HEADINGS.values()
    for section, heading in headings.items()
}

HEADING_RE = re.compile(r"^##\s*(.+?)\s*$")
ACCEPTANCE_RE = re.compile(
    r"^\s*-\s*(?:\[([ xX])\]?\s*)?(AC-[A-Za-z0-9-]+)\s*[:：]\s*(.+?)\s*$"
)
LIST_ITEM_RE = re.compile(r"^\s*[-*]\s")
LIST_PREFIX_RE = re.compile(r"^\s*[-*+]\s*")
FENCE_MARKER_RE = re.compile(r"^(```|~~~)")
SPEC_CHECK_RESULT_RE = re.compile(r"(?i)\b(?:pass|not_applicable)\b")
ANGLE_SPAN_RE = re.compile(r"[<＜][^>＞]*[>＞]")


def canonical_section(heading: str) -> str | None:
    """Canonical section key for a recognized heading, or None."""
    return SECTION_ALIASES.get(heading)


def headings_for(language: str) -> dict[str, str]:
    """Heading set for a language, falling back to the default language."""
    return LANGUAGE_HEADINGS.get(language, LANGUAGE_HEADINGS[DEFAULT_LANGUAGE])


def heading_for(section: str, language: str) -> str:
    """One heading in the requested language, falling back to the default."""
    return headings_for(language)[section]


def section_headings(section: str) -> tuple[str, ...]:
    """Every recognized heading for one section, default language first."""
    return tuple(
        LANGUAGE_HEADINGS[language][section] for language in LANGUAGE_HEADINGS
    )


def spec_check_label(language: str) -> str:
    """The spec-check label for a language, falling back to the default."""
    return SPEC_CHECK_LABELS.get(language, SPEC_CHECK_LABELS[DEFAULT_LANGUAGE])


def _spec_check_remainder(line: str, language: str | None) -> str | None:
    text = LIST_PREFIX_RE.sub("", line.strip(), count=1)
    labels = (
        (spec_check_label(language),)
        if language is not None
        else tuple(SPEC_CHECK_LABELS.values())
    )
    for label in labels:
        if text.startswith(label):
            return text[len(label):]
    return None


def is_spec_check_line(line: str, language: str | None = None) -> bool:
    """Whether a line starts with the configured or any spec-check label."""
    return _spec_check_remainder(line, language) is not None


def is_spec_check_result_line(line: str, language: str | None = None) -> bool:
    """Whether a spec-check line carries an actual result.

    Angle-bracket spans are the template's placeholder syntax, so a result
    mentioned only inside `<...>`/`＜...＞` does not count.
    """
    remainder = _spec_check_remainder(line, language)
    if remainder is None:
        return False
    return SPEC_CHECK_RESULT_RE.search(ANGLE_SPAN_RE.sub("", remainder)) is not None


def _spec_scope(dev_type: str | None) -> str:
    """The spec source a task's dev_type dispatches to.

    `spec` is the whole-spec dev type and its reading list starts at the spec
    index, not at a `.cowork-flow/spec/spec/` directory.
    """
    if dev_type == "spec":
        return ".cowork-flow/spec/"
    return f".cowork-flow/spec/{dev_type or '<dev_type>'}/"


def spec_check_placeholder(language: str, dev_type: str | None = None) -> str:
    """The localized scaffold line that the start gate treats as unfilled."""
    spec_dir = _spec_scope(dev_type)
    if language == "en-US":
        return (
            f"- Spec check: clause-by-clause check against applicable "
            f"`{spec_dir}` rules -> <pass / not_applicable + reason>."
        )
    return (
        f"- 规范核对：逐条核对 `{spec_dir}` 适用规范 "
        "→ <pass / not_applicable + 理由>。"
    )


def spec_check_example(language: str, dev_type: str | None = None) -> str:
    """A filled spec-check example for start-gate error messages."""
    spec_dir = _spec_scope(dev_type)
    if language == "en-US":
        return (
            f"- Spec check: clause-by-clause check against applicable "
            f"`{spec_dir}` rules -> pass (reason: ...)"
        )
    return (
        f"- 规范核对：逐条核对 `{spec_dir}` 适用规范 → pass（理由：...）"
    )


def structural_lines(text: str) -> list[str]:
    """Lines outside fenced code blocks, for structural Markdown checks."""
    lines: list[str] = []
    fence: str | None = None
    for raw in text.splitlines():
        marker = FENCE_MARKER_RE.match(raw.strip())
        if marker is not None:
            if fence is None:
                fence = marker.group(1)
            elif marker.group(1) == fence:
                fence = None
            continue
        if fence is None:
            lines.append(raw)
    return lines


def section_lines(
    text: str,
    section: str,
    *,
    skip_fenced: bool = False,
) -> list[str]:
    """Raw lines under a recognized heading, up to the next `##` heading."""
    lines: list[str] = []
    inside = False
    source = structural_lines(text) if skip_fenced else text.splitlines()
    for raw in source:
        heading = HEADING_RE.match(raw.strip())
        if heading:
            inside = canonical_section(heading.group(1)) == section
            continue
        if inside:
            lines.append(raw)
    return lines


def verification_section_lines(text: str) -> list[str]:
    """Raw verification lines, ignoring fenced command examples."""
    return section_lines(text, VERIFICATION, skip_fenced=True)


def headings(text: str) -> tuple[str, ...]:
    """Every `##` heading text in the document order."""
    return tuple(
        heading.group(1)
        for raw in text.splitlines()
        if (heading := HEADING_RE.match(raw.strip()))
    )


def present_sections(text: str) -> set[str]:
    """Canonical keys of the recognized `##` sections present in the text."""
    present: set[str] = set()
    for raw in text.splitlines():
        heading = HEADING_RE.match(raw.strip())
        if not heading:
            continue
        section = canonical_section(heading.group(1))
        if section is not None:
            present.add(section)
    return present


def acceptance_section_lines(text: str) -> list[str]:
    """Raw lines under the acceptance heading, up to the next heading."""
    return section_lines(text, ACCEPTANCE)
