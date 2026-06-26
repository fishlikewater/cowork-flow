#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared agent safety policy rules for doctor --subagent-safety and tests.

Provides:
    ADVISORY_AGENTS         - agent names that must be advisory-only
    FIXED_AGENTS            - agent names for formal cowork-* dispatch
    check_advisory_agent    - verify an advisory agent config is safe
    check_fixed_agent       - verify a fixed agent config is safe
"""

from __future__ import annotations

from pathlib import Path

# -- Agent classification -----------------------------------------------------

ADVISORY_AGENTS = ("worker", "default", "explorer")
FIXED_AGENTS = ("cowork-research", "cowork-implement", "cowork-check")

# -- Advisory agent policy ----------------------------------------------------


REQUIRED_ADVISORY_SNIPPETS = (
    "bootstrap",
    "start",
    "resume",
    "advisory",
    "multi_agent = false",
    "enabled = false",
)

ADVISORY_FORBIDDEN_ACTIONS = (
    "MUST NOT spawn",
    "MUST NOT commit",
    "MUST NOT run task start",
)


def check_advisory_agent(
    toml_path: Path, text: str | None = None
) -> list[str]:
    """Check an advisory agent toml for policy violations.

    Returns a list of error strings (empty = clean).
    """
    errors: list[str] = []

    if text is None:
        try:
            text = toml_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [f"Cannot read {toml_path}"]

    rel = _rel(toml_path)

    for snippet in REQUIRED_ADVISORY_SNIPPETS:
        if snippet not in text:
            errors.append(f"{rel}: missing required snippet '{snippet}'")

    for action in ADVISORY_FORBIDDEN_ACTIONS:
        if action not in text:
            errors.append(f"{rel}: missing required prohibition '{action}'")

    # Check explicit multi-agent disable
    if "multi_agent = true" in text:
        errors.append(f"{rel}: multi_agent must be false for advisory agents")
    if "enabled = true" in text:
        errors.append(f"{rel}: features.multi_agent_v2.enabled must be false")

    return errors


# -- Fixed agent policy -------------------------------------------------------


REQUIRED_FIXED_SNIPPETS = (
    "multi_agent = false",
    "enabled = false",
    "MUST NOT spawn",
)

def check_fixed_agent(
    toml_path: Path, text: str | None = None
) -> list[str]:
    """Check a fixed agent toml for policy violations.

    Returns a list of error strings (empty = clean).
    """
    errors: list[str] = []

    if text is None:
        try:
            text = toml_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return [f"Cannot read {toml_path}"]

    rel = _rel(toml_path)

    for snippet in REQUIRED_FIXED_SNIPPETS:
        if snippet not in text:
            errors.append(f"{rel}: missing required snippet '{snippet}'")

    # Additional checks: runtime context markers
    runtime_markers = (
        "cowork_runtime_context_id: <runtime_context_id>",
        "cowork_host_context_key: <host_context_key>",
        "subagent bind <runtime_context_id> <host_context_key>",
        "bound runtime context",
        "report needs_context",
    )
    for marker in runtime_markers:
        if marker not in text:
            errors.append(f"{rel}: missing runtime context marker '{marker}'")

    return errors


def _rel(path: Path) -> str:
    try:
        return str(path)
    except Exception:
        return str(path)
