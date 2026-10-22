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
    lines: list[str] = []
    inside = False
    for raw in text.splitlines():
        heading = HEADING_RE.match(raw.strip())
        if heading:
            inside = canonical_section(heading.group(1)) == ACCEPTANCE
            continue
        if inside:
            lines.append(raw)
    return lines
