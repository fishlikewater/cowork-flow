#!/usr/bin/env python3
"""Task context application service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from common.core.files import read_text_utf8
from common.core.paths import (
    DIR_AGENTS,
    DIR_SPEC,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)


CONTEXT_JSONL_FILES = ("implement.jsonl", "check.jsonl", "debug.jsonl")


class TaskContextError(RuntimeError):
    """Raised when a context mutation cannot be performed."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


@dataclass(frozen=True)
class ContextInitializationResult:
    created: tuple[str, ...]
    skipped: tuple[str, ...]
    entry_counts: dict[str, int]


@dataclass(frozen=True)
class ContextAddResult:
    added: bool
    entry_type: str
    path: str
    entry: dict


@dataclass(frozen=True)
class ContextValidationIssue:
    context_file: str
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class ContextFileValidation:
    context_file: str
    exists: bool
    entry_count: int
    issues: tuple[ContextValidationIssue, ...]


def get_implement_base() -> list[dict]:
    return [
        {
            "file": "AGENTS.md",
            "reason": "Project collaboration rules and workflow gates",
        },
        {
            "file": f"{DIR_WORKFLOW}/workflow.md",
            "reason": "Project workflow and conventions",
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
    entries = [
        {
            "file": skill_path("check", repo_root),
            "reason": "Quality, contract, and template consistency check",
        },
        {
            "file": skill_path("finish-work", repo_root),
            "reason": "Finish, archive, and session recording gate",
        },
    ]
    entries.extend(
        {
            "file": spec_file,
            "reason": f"Verify {Path(spec_file).name} compliance",
        }
        for spec_file in discover_spec_files(repo_root, dev_type)
    )
    return entries


def get_debug_context(
    dev_type: str,
    repo_root: Path | None = None,
) -> list[dict]:
    root = Path(repo_root) if repo_root is not None else get_repo_root()
    del dev_type
    return [
        {
            "file": skill_path("break-loop", root),
            "reason": "Deep bug analysis workflow",
        },
        {
            "file": skill_path("update-spec", root),
            "reason": "Capture implementation lessons and contracts",
        },
        {
            "file": skill_path("check", root),
            "reason": "Verify the fix and related contracts",
        },
    ]


def write_jsonl(path: Path, entries: list[dict]) -> None:
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def iter_jsonl_lines(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            yield line_number, line.rstrip("\n")


class TaskContextService:
    """Manage task JSONL context without CLI rendering."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def initialize(
        self,
        task_dir: Path,
        dev_type: str,
    ) -> ContextInitializationResult:
        task_dir = Path(task_dir)
        if not task_dir.is_dir():
            raise TaskContextError(
                "TASK-CONTEXT-DIR-001",
                task_dir,
                "task directory does not exist",
            )

        entries_by_file = {
            "implement.jsonl": self._implement_entries(dev_type),
            "check.jsonl": get_check_context(self.repo_root, dev_type),
            "debug.jsonl": get_debug_context(dev_type, self.repo_root),
        }
        created: list[str] = []
        skipped: list[str] = []
        entry_counts: dict[str, int] = {}
        for file_name, entries in entries_by_file.items():
            context_file = task_dir / file_name
            if context_file.is_file():
                skipped.append(file_name)
                continue
            write_jsonl(context_file, entries)
            created.append(file_name)
            entry_counts[file_name] = len(entries)

        return ContextInitializationResult(
            created=tuple(created),
            skipped=tuple(skipped),
            entry_counts=entry_counts,
        )

    def add(
        self,
        task_dir: Path,
        context_name: str,
        path: str,
        reason: str,
    ) -> ContextAddResult:
        task_dir = Path(task_dir)
        if not task_dir.is_dir():
            raise TaskContextError(
                "TASK-CONTEXT-DIR-001",
                task_dir,
                "task directory does not exist",
            )

        context_file = task_dir / self._context_file_name(context_name)
        full_path = self.repo_root / path
        entry_type = "file"
        normalized_path = path
        if full_path.is_dir():
            entry_type = "directory"
            if not normalized_path.endswith("/"):
                normalized_path = f"{normalized_path}/"
        elif not full_path.is_file():
            raise TaskContextError(
                "TASK-CONTEXT-PATH-001",
                full_path,
                "context path does not exist",
            )

        entry = {"file": normalized_path, "reason": reason}
        if entry_type == "directory":
            entry["type"] = "directory"

        if any(
            existing.get("file") == normalized_path
            for existing in self.entries(task_dir, context_name)
        ):
            return ContextAddResult(
                added=False,
                entry_type=entry_type,
                path=normalized_path,
                entry=entry,
            )

        with context_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return ContextAddResult(
            added=True,
            entry_type=entry_type,
            path=normalized_path,
            entry=entry,
        )

    def entries(self, task_dir: Path, context_name: str) -> list[dict]:
        context_file = Path(task_dir) / self._context_file_name(context_name)
        if not context_file.is_file():
            return []

        entries: list[dict] = []
        for _, line in iter_jsonl_lines(context_file):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                entries.append(data)
        return entries

    def validate(self, task_dir: Path) -> tuple[ContextValidationIssue, ...]:
        issues: list[ContextValidationIssue] = []
        for context_file in CONTEXT_JSONL_FILES:
            issues.extend(self.validate_file(task_dir, context_file).issues)
        return tuple(issues)

    def validate_file(
        self,
        task_dir: Path,
        context_name: str,
    ) -> ContextFileValidation:
        context_file = Path(task_dir) / self._context_file_name(context_name)
        if not context_file.is_file():
            return ContextFileValidation(
                context_file=context_file.name,
                exists=False,
                entry_count=0,
                issues=(),
            )

        issues: list[ContextValidationIssue] = []
        entry_count = 0
        for line_number, line in iter_jsonl_lines(context_file):
            if not line.strip():
                continue
            entry_count += 1
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                issues.append(
                    ContextValidationIssue(
                        context_file=context_file.name,
                        line=line_number,
                        code="invalid_json",
                        message="Invalid JSON",
                    )
                )
                continue

            if not isinstance(data, dict) or not data.get("file"):
                issues.append(
                    ContextValidationIssue(
                        context_file=context_file.name,
                        line=line_number,
                        code="missing_file_field",
                        message="Missing file field",
                    )
                )
                continue

            file_path = str(data["file"])
            if is_skill_path(file_path):
                continue

            full_path = self.repo_root / file_path
            entry_type = data.get("type", "file")
            if entry_type == "directory" and not full_path.is_dir():
                issues.append(
                    ContextValidationIssue(
                        context_file=context_file.name,
                        line=line_number,
                        code="directory_not_found",
                        message=f"Directory not found: {file_path}",
                    )
                )
            elif entry_type != "directory" and not full_path.is_file():
                issues.append(
                    ContextValidationIssue(
                        context_file=context_file.name,
                        line=line_number,
                        code="file_not_found",
                        message=f"File not found: {file_path}",
                    )
                )

        return ContextFileValidation(
            context_file=context_file.name,
            exists=True,
            entry_count=entry_count,
            issues=tuple(issues),
        )

    def migrate_legacy_prd(self, task_dir: Path) -> bool:
        task_dir = Path(task_dir)
        prd_file = task_dir / "prd.md"
        anchor_file = task_dir / "decision-anchor.md"
        if not prd_file.exists() or anchor_file.exists():
            return False

        content = prd_file.read_text(encoding="utf-8").strip()
        if not content:
            content = "(empty legacy prd.md)"
        if "## 目标" not in content and "## Goal" not in content:
            content = f"## 目标\n\n{content}"
        if "## 验收标准" not in content and "## Acceptance" not in content:
            content += "\n\n## 验收标准\n- [ ] \n"
        anchor_file.write_text(content, encoding="utf-8")
        prd_file.unlink()
        return True

    def start_blockers(self, task_dir: Path) -> tuple[str, ...]:
        task_dir = Path(task_dir)
        blockers: list[str] = []
        if not (task_dir / FILE_TASK_JSON).is_file():
            blockers.append("task.json is missing")
        if not read_text_utf8(task_dir / "decision-anchor.md"):
            blockers.append("decision-anchor.md is missing or empty")
        for context_file in CONTEXT_JSONL_FILES:
            if not read_text_utf8(task_dir / context_file):
                blockers.append(f"{context_file} is missing or empty")
        return tuple(blockers)

    def validation_issue_summaries(self, task_dir: Path) -> tuple[str, ...]:
        summaries: list[str] = []
        for context_file in CONTEXT_JSONL_FILES:
            result = self.validate_file(task_dir, context_file)
            if result.issues:
                summaries.append(
                    f"{context_file} has {len(result.issues)} validation error(s)"
                )
        return tuple(summaries)

    def _implement_entries(self, dev_type: str) -> list[dict]:
        entries = get_implement_base()
        if dev_type in ("backend", "test"):
            entries.extend(get_implement_backend())
        elif dev_type == "frontend":
            entries.extend(get_implement_frontend())
        elif dev_type == "fullstack":
            entries.extend(get_implement_backend())
            entries.extend(get_implement_frontend())
        elif dev_type == "spec":
            entries.extend(get_implement_spec())
        return entries

    @staticmethod
    def _context_file_name(context_name: str) -> str:
        if context_name.endswith(".jsonl"):
            return context_name
        return f"{context_name}.jsonl"
