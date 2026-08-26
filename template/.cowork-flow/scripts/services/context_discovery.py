#!/usr/bin/env python3
"""Task context discovery for specs, Skills, and installed platforms."""

from __future__ import annotations

from pathlib import Path

from infra.quality_sources import quality_source_entries
from infra.skill_manifest import context_entries
from infra.paths import (
    DIR_AGENTS,
    DIR_SPEC,
    DIR_WORKFLOW,
    get_repo_root,
)


def get_implement_base(repo_root: Path | None = None) -> list[dict]:
    root = Path(repo_root) if repo_root is not None else get_repo_root()
    entries = [
        {
            "file": "AGENTS.md",
            "reason": "Project collaboration rules and workflow checks",
        },
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/guides/index.md",
            "reason": "Pre-implementation thinking guides",
        },
        {
            "file": (
                f"{DIR_WORKFLOW}/{DIR_SPEC}/guides/"
                "pre-implementation-checklist.md"
            ),
            "reason": "Mandatory pre-coding checklist",
        },
    ]
    entries.extend(context_entries(root, context="implement"))
    return entries


def get_implement_backend() -> list[dict]:
    return [
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/backend/index.md",
            "reason": "Backend development guide",
        }
    ]


def get_implement_frontend() -> list[dict]:
    return [
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/frontend/index.md",
            "reason": "Frontend development guide",
        }
    ]


def get_implement_spec() -> list[dict]:
    return [
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/index.md",
            "reason": "Spec index — read before modifying spec/",
        },
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/contracts/index.md",
            "reason": "Contract definitions",
        },
        {
            "file": f"{DIR_WORKFLOW}/{DIR_SPEC}/schemas/index.md",
            "reason": "Schema definitions",
        },
    ]


def detect_installed_platforms(repo_root: Path | None = None) -> list[str]:
    repo_root = Path(repo_root) if repo_root is not None else get_repo_root()
    platforms: list[str] = []
    if (repo_root / ".codex").is_dir():
        platforms.append("codex")
    if (repo_root / ".opencode").is_dir():
        platforms.append("opencode")
    if (repo_root / ".claude").is_dir() or (repo_root / "CLAUDE.md").is_file():
        platforms.append("claude-code")
    return platforms


def use_claude_skill_context(repo_root: Path | None = None) -> bool:
    return detect_installed_platforms(repo_root) == ["claude-code"]


def skill_path(name: str, repo_root: Path | None = None) -> str:
    if use_claude_skill_context(repo_root):
        return f".claude/skills/{name}/SKILL.md"
    return f"{DIR_AGENTS}/skills/{name}/SKILL.md"


def get_domain_skill_context(
    repo_root: Path,
    *,
    dev_type: str | None = None,
    paths: tuple[str, ...] = (),
) -> list[dict]:
    return context_entries(
        repo_root,
        context="implement",
        dev_type=dev_type,
        paths=paths,
        include_wildcard=False,
    )


def is_skill_path(file_path: str) -> bool:
    return (
        file_path.startswith(f"{DIR_AGENTS}/skills/")
        or file_path.startswith(".claude/skills/")
        or ".skills/" in file_path
        or "/skills/" in file_path
    )


def discover_spec_files(repo_root: Path, dev_type: str) -> list[str]:
    if dev_type == "spec":
        return [f"{DIR_WORKFLOW}/{DIR_SPEC}/index.md"]

    spec_dir = repo_root / DIR_WORKFLOW / DIR_SPEC / dev_type
    if not spec_dir.is_dir():
        return []
    return sorted(
        f"{DIR_WORKFLOW}/{DIR_SPEC}/{dev_type}/{path.name}"
        for path in spec_dir.glob("*.md")
        if path.is_file()
    )


def get_check_context(repo_root: Path, dev_type: str) -> list[dict]:
    entries = context_entries(repo_root, context="check", dev_type=dev_type)
    entries.sort(key=lambda entry: entry["file"])
    if dev_type == "spec":
        entries.extend(
            {
                "file": spec_file,
                "reason": f"Verify {Path(spec_file).name} compliance",
            }
            for spec_file in discover_spec_files(repo_root, dev_type)
        )
    entries.extend(quality_source_entries(repo_root, dev_type))
    return entries


def get_debug_context(
    dev_type: str,
    repo_root: Path | None = None,
) -> list[dict]:
    root = Path(repo_root) if repo_root is not None else get_repo_root()
    return context_entries(root, context="debug", dev_type=dev_type)
