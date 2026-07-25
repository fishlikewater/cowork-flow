#!/usr/bin/env python3
"""Resolve precise quality context sources for review/check stages."""

from __future__ import annotations

import re
from pathlib import Path


SPEC_ROOT = ".cowork-flow/spec"
REFERENCE_DOD = f"{SPEC_ROOT}/references/definition-of-done.md"
REFERENCE_TESTING = f"{SPEC_ROOT}/references/testing-checklist.md"
REFERENCE_SECURITY = f"{SPEC_ROOT}/references/security-checklist.md"

_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")
_SECURITY_HINT_RE = re.compile(
    r"(?i)(auth|credential|jwt|oauth|password|permission|secret|security|session|token|\.env)"
)


def quality_source_entries(
    repo_root: Path,
    dev_type: str,
    *,
    paths: tuple[str, ...] = (),
) -> list[dict]:
    """Return narrow quality/spec sources a checker should read."""
    entries: list[dict] = []
    seen: set[str] = set()
    for source in quality_source_paths(repo_root, dev_type, paths=paths):
        if source in seen:
            continue
        seen.add(source)
        entries.append(
            {
                "file": source,
                "reason": _quality_source_reason(source),
            }
        )
    return entries


def quality_source_paths(
    repo_root: Path,
    dev_type: str,
    *,
    paths: tuple[str, ...] = (),
) -> list[str]:
    """Return existing repo-relative quality source paths."""
    root = Path(repo_root)
    sources: list[str] = []
    for category in _categories_for(dev_type):
        index = f"{SPEC_ROOT}/{category}/index.md"
        sources.extend(_existing_paths(root, (index,)))
        sources.extend(_linked_markdown_sources(root, index, category))

    sources.extend(_existing_paths(root, (REFERENCE_DOD, REFERENCE_TESTING)))
    if _security_relevant(paths):
        sources.extend(_existing_paths(root, (REFERENCE_SECURITY,)))
    return sources


def _categories_for(dev_type: str) -> tuple[str, ...]:
    if dev_type == "backend":
        return ("backend",)
    if dev_type == "frontend":
        return ("frontend",)
    if dev_type == "fullstack":
        return ("backend", "frontend")
    return ()


def _linked_markdown_sources(
    repo_root: Path,
    index_path: str,
    category: str,
) -> list[str]:
    index = repo_root / index_path
    if not index.is_file():
        return []
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    sources: list[str] = []
    for match in _MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip()
        if "://" in target or target.startswith("#"):
            continue
        normalized = _normalize_markdown_target(category, target)
        if normalized is not None:
            sources.extend(_existing_paths(repo_root, (normalized,)))
    return sources


def _normalize_markdown_target(category: str, target: str) -> str | None:
    without_anchor = target.split("#", 1)[0].strip()
    if not without_anchor.endswith(".md"):
        return None
    if without_anchor.startswith("./"):
        without_anchor = without_anchor[2:]
    if without_anchor.startswith("../") or without_anchor.startswith("/"):
        return None
    return f"{SPEC_ROOT}/{category}/{without_anchor}"


def _existing_paths(repo_root: Path, paths: tuple[str, ...]) -> list[str]:
    return [path for path in paths if (repo_root / path).is_file()]


def _security_relevant(paths: tuple[str, ...]) -> bool:
    return any(_SECURITY_HINT_RE.search(path) is not None for path in paths)


def _quality_source_reason(source: str) -> str:
    if source == REFERENCE_DOD:
        return "Verify Definition of Done evidence"
    if source == REFERENCE_TESTING:
        return "Verify test depth and anti-shallow-test coverage"
    if source == REFERENCE_SECURITY:
        return "Verify security-sensitive changes"
    return f"Verify {Path(source).name} quality rules"
