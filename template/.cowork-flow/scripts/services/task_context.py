#!/usr/bin/env python3
"""Task context application service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from infra.files import read_text_utf8
from infra.paths import FILE_TASK_JSON
from services.context_discovery import (
    detect_installed_platforms,
    discover_spec_files,
    get_check_context,
    get_debug_context,
    get_domain_skill_context,
    get_implement_backend,
    get_implement_base,
    get_implement_frontend,
    get_implement_spec,
    is_skill_path,
    skill_path,
    use_claude_skill_context,
)
from services.context_jsonl import (
    ContextJsonlEntry,
    ContextJsonlReadResult,
    ContextValidationIssue,
    iter_jsonl_lines,
    read_context_jsonl_entries,
    write_jsonl,
)
from services.context_paths import (
    CONTEXT_ENTRY_TYPES,
    TaskContextError,
    normalize_context_file_scope_entry,
    normalize_context_path,
    prepare_context_entry,
)
from services.plan_binding import normalize_plan_file, plan_file_blockers


CONTEXT_JSONL_FILES = ("implement.jsonl", "check.jsonl", "debug.jsonl")


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
class ContextFileValidation:
    context_file: str
    exists: bool
    entry_count: int
    issues: tuple[ContextValidationIssue, ...]


def _context_issue(
    context_file: str,
    line: int,
    code: str,
    message: str,
) -> ContextValidationIssue:
    return ContextValidationIssue(
        context_file=context_file,
        line=line,
        code=code,
        message=message,
    )


def validate_context_entry(
    repo_root: Path,
    context_file: str,
    line: int,
    data: object,
) -> ContextValidationIssue | None:
    """Validate one parsed JSONL entry."""
    if not isinstance(data, dict) or not data.get("file"):
        return _context_issue(
            context_file,
            line,
            "missing_file_field",
            "Missing file field",
        )

    entry_type = data.get("type", "file")
    normalized = str(data["file"])
    try:
        normalized_path, full_path = normalize_context_path(
            repo_root,
            normalized,
            entry_type,
        )
    except TaskContextError as error:
        code = _context_error_issue_code(error)
        return _context_issue(context_file, line, code, error.detail)

    if is_skill_path(normalized_path):
        return None
    return _validate_context_entry_target(
        context_file,
        line,
        entry_type,
        normalized_path,
        full_path,
    )


def _context_error_issue_code(error: TaskContextError) -> str:
    if error.code == "TASK-CONTEXT-TYPE-001":
        return "invalid_entry_type"
    return "invalid_path"


def _validate_context_entry_target(
    context_file: str,
    line: int,
    entry_type: str,
    normalized_path: str,
    full_path: Path,
) -> ContextValidationIssue | None:
    if entry_type == "planned-file":
        return _planned_file_issue(context_file, line, normalized_path, full_path)
    if entry_type == "deleted-file":
        return _deleted_file_issue(context_file, line, normalized_path, full_path)
    if entry_type == "directory" and not full_path.is_dir():
        return _context_issue(
            context_file,
            line,
            "directory_not_found",
            f"Directory not found: {normalized_path}",
        )
    if entry_type == "file" and not full_path.is_file():
        return _context_issue(
            context_file,
            line,
            "file_not_found",
            f"File not found: {normalized_path}",
        )
    return None


def _planned_file_issue(
    context_file: str,
    line: int,
    normalized_path: str,
    full_path: Path,
) -> ContextValidationIssue | None:
    if not full_path.is_dir():
        return None
    return _context_issue(
        context_file,
        line,
        "invalid_path",
        f"Planned file is a directory: {normalized_path}",
    )


def _deleted_file_issue(
    context_file: str,
    line: int,
    normalized_path: str,
    full_path: Path,
) -> ContextValidationIssue | None:
    if not full_path.is_dir():
        return None
    return _context_issue(
        context_file,
        line,
        "invalid_path",
        f"Deleted file is a directory: {normalized_path}",
    )


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

        implement_entries = self._implement_entries(dev_type)
        entries_by_file = {
            "implement.jsonl": implement_entries,
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

        self.ensure_task_artifact_placeholders(task_dir)
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
        entry_type: str | None = None,
    ) -> ContextAddResult:
        task_dir = Path(task_dir)
        if not task_dir.is_dir():
            raise TaskContextError(
                "TASK-CONTEXT-DIR-001",
                task_dir,
                "task directory does not exist",
            )

        context_file = task_dir / self._context_file_name(context_name)
        entry_type, normalized_path, entry = prepare_context_entry(
            self.repo_root,
            path,
            reason,
            entry_type,
        )

        existing_entries = self.entries(task_dir, context_name)
        already_exists = any(
            existing.get("file") == normalized_path
            for existing in existing_entries
        )
        if not already_exists:
            with context_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if (
            entry_type != "planned-file"
            and self._context_file_name(context_name) == "implement.jsonl"
        ):
            self._append_domain_guides(
                context_file,
                paths=(normalized_path,),
            )
        return ContextAddResult(
            added=not already_exists,
            entry_type=entry_type,
            path=normalized_path,
            entry=entry,
        )

    def entries(self, task_dir: Path, context_name: str) -> list[dict]:
        context_file = Path(task_dir) / self._context_file_name(context_name)

        entries: list[dict] = []
        for entry in read_context_jsonl_entries(context_file).entries:
            data = entry.data
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
        parsed = read_context_jsonl_entries(context_file)
        if not parsed.exists:
            return ContextFileValidation(
                context_file=context_file.name,
                exists=False,
                entry_count=0,
                issues=(),
            )

        issues: list[ContextValidationIssue] = list(parsed.issues)
        for entry in parsed.entries:
            issue = validate_context_entry(
                self.repo_root,
                entry.context_file,
                entry.line,
                entry.data,
            )
            if issue is not None:
                issues.append(issue)

        return ContextFileValidation(
            context_file=context_file.name,
            exists=True,
            entry_count=parsed.entry_count,
            issues=tuple(issues),
        )

    def start_blockers(self, task_dir: Path) -> tuple[str, ...]:
        task_dir = Path(task_dir)
        blockers: list[str] = []
        task_data = self._task_data(task_dir)
        if not (task_dir / FILE_TASK_JSON).is_file():
            blockers.append("task.json is missing")
        anchor_text = read_text_utf8(task_dir / "decision-anchor.md")
        if not anchor_text:
            blockers.append("decision-anchor.md is missing or empty")
        else:
            blockers.extend(self._decision_anchor_section_blockers(anchor_text))
        for context_file in ("implement.jsonl",):
            if not read_text_utf8(task_dir / context_file):
                blockers.append(f"{context_file} is missing or empty")
        if (task_dir / FILE_TASK_JSON).is_file() and not self._is_tiny_task(task_data):
            blockers.extend(self._plan_file_blockers(task_data))
        return tuple(blockers)

    def _task_data(self, task_dir: Path) -> dict:
        text = read_text_utf8(Path(task_dir) / FILE_TASK_JSON)
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _decision_anchor_section_blockers(anchor_text: str) -> list[str]:
        blockers: list[str] = []
        for section in ("## 目标", "## 验收标准"):
            if section not in anchor_text:
                blockers.append(
                    f"decision-anchor.md missing required section: {section}"
                )
        return blockers

    @staticmethod
    def _is_tiny_task(task_data: dict) -> bool:
        meta = task_data.get("meta")
        candidates = [
            task_data.get("taskType"),
            task_data.get("task_type"),
            meta.get("taskType") if isinstance(meta, dict) else None,
            meta.get("task_type") if isinstance(meta, dict) else None,
        ]
        return any(str(candidate).lower() == "tiny" for candidate in candidates)

    def _plan_file_blockers(self, task_data: dict) -> list[str]:
        return plan_file_blockers(self.repo_root, task_data)

    @staticmethod
    def _normalize_plan_file(plan_file: str) -> str | None:
        return normalize_plan_file(plan_file)

    def validation_issue_summaries(self, task_dir: Path) -> tuple[str, ...]:
        summaries: list[str] = []
        for context_file in CONTEXT_JSONL_FILES:
            result = self.validate_file(task_dir, context_file)
            if result.issues:
                summaries.append(
                    f"{context_file} has {len(result.issues)} validation error(s)"
                )
        return tuple(summaries)

    def ensure_task_artifact_placeholders(self, task_dir: Path) -> tuple[str, ...]:
        """Create empty placeholders for planned task-local context files."""
        task_dir = Path(task_dir)
        created: list[str] = []
        for entry in self.entries(task_dir, "implement"):
            if entry.get("type") == "planned-file":
                continue
            file_path = str(entry.get("file", "")).strip()
            if not file_path:
                continue
            try:
                normalized, full_path = normalize_context_path(
                    self.repo_root,
                    file_path,
                    "planned-file",
                )
            except TaskContextError:
                continue
            if not _is_task_local_artifact(task_dir, full_path):
                continue
            if full_path.exists():
                continue
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("", encoding="utf-8")
            created.append(normalized)
        return tuple(created)

    def _implement_entries(self, dev_type: str) -> list[dict]:
        entries = get_implement_base(self.repo_root)
        entries.extend(
            get_domain_skill_context(
                self.repo_root,
                dev_type=dev_type,
            )
        )
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

    def _append_domain_guides(
        self,
        context_file: Path,
        *,
        paths: tuple[str, ...],
    ) -> None:
        guide_entries = get_domain_skill_context(
            self.repo_root,
            paths=paths,
        )
        if not guide_entries:
            return
        existing_files = {
            entry.get("file")
            for entry in self.entries(context_file.parent, context_file.name)
        }
        with context_file.open("a", encoding="utf-8") as stream:
            for guide in guide_entries:
                if guide["file"] in existing_files:
                    continue
                stream.write(json.dumps(guide, ensure_ascii=False) + "\n")
                existing_files.add(guide["file"])

    @staticmethod
    def _context_file_name(context_name: str) -> str:
        if context_name.endswith(".jsonl"):
            return context_name
        return f"{context_name}.jsonl"


def _is_task_local_artifact(task_dir: Path, full_path: Path) -> bool:
    try:
        full_path.resolve(strict=False).relative_to(task_dir.resolve(strict=False))
    except ValueError:
        return False
    return not full_path.exists() or full_path.is_file()
