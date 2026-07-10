#!/usr/bin/env python3
"""Task context application service."""

from __future__ import annotations

import json
import re
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
CONTEXT_ENTRY_TYPES = frozenset(("file", "directory", "planned-file"))


class TaskContextError(RuntimeError):
    """Raised when a context mutation cannot be performed."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


def normalize_context_path(
    repo_root: Path,
    path: str,
    entry_type: str,
) -> tuple[str, Path]:
    """Return a canonical repo-relative context path and its absolute target."""
    candidate = Path(repo_root) / str(path)
    if entry_type not in CONTEXT_ENTRY_TYPES:
        raise TaskContextError(
            "TASK-CONTEXT-TYPE-001",
            candidate,
            f"unsupported context entry type: {entry_type}",
        )

    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if entry_type == "directory" and normalized.endswith("/"):
        normalized = normalized[:-1]

    segments = normalized.split("/")
    invalid_path = (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in ("", ".", "..") for segment in segments)
        or any(character in normalized for character in "*?[]")
        or (entry_type == "planned-file" and str(path).endswith(("/", "\\")))
    )
    if invalid_path:
        raise TaskContextError(
            "TASK-CONTEXT-PATH-002",
            candidate,
            "context path must be a canonical repository-relative path",
        )

    repo_root = Path(repo_root).resolve()
    full_path = repo_root.joinpath(*segments).resolve(strict=False)
    try:
        full_path.relative_to(repo_root)
    except ValueError as error:
        raise TaskContextError(
            "TASK-CONTEXT-PATH-002",
            full_path,
            "context path resolves outside the repository",
        ) from error

    if entry_type == "directory":
        normalized = f"{normalized}/"
    return normalized, full_path


def prepare_context_entry(
    repo_root: Path,
    path: str,
    reason: str,
    requested_type: str | None,
) -> tuple[str, str, dict]:
    """Build one validated context entry without writing it."""
    entry_type = requested_type
    if entry_type is None:
        candidate = Path(repo_root) / path
        entry_type = "directory" if candidate.is_dir() else "file"

    normalized_path, full_path = normalize_context_path(
        repo_root,
        path,
        entry_type,
    )
    valid_target = {
        "directory": full_path.is_dir(),
        "planned-file": not full_path.is_dir(),
        "file": full_path.is_file(),
    }[entry_type]
    if not valid_target:
        raise TaskContextError(
            "TASK-CONTEXT-PATH-001",
            full_path,
            f"context {entry_type} path does not exist or has the wrong type",
        )

    entry = {"file": normalized_path, "reason": reason}
    if entry_type != "file":
        entry["type"] = entry_type
    return entry_type, normalized_path, entry


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
    try:
        normalized_path, full_path = normalize_context_path(
            repo_root,
            str(data["file"]),
            entry_type,
        )
    except TaskContextError as error:
        code = (
            "invalid_entry_type"
            if error.code == "TASK-CONTEXT-TYPE-001"
            else "invalid_path"
        )
        return _context_issue(context_file, line, code, error.detail)

    if is_skill_path(normalized_path):
        return None
    if entry_type == "planned-file":
        if full_path.is_dir():
            return _context_issue(
                context_file,
                line,
                "invalid_path",
                f"Planned file is a directory: {normalized_path}",
            )
        return None
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
        {
            "file": protocol_path("tdd"),
            "reason": "Behavior-change red-green evidence protocol",
        },
        {
            "file": protocol_path("decision-review"),
            "reason": "Structured decision review evidence contract",
        },
        {
            "file": protocol_path("spec-maintenance"),
            "reason": "Specification maintenance decision protocol",
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


def protocol_path(name: str) -> str:
    return f"{DIR_WORKFLOW}/{DIR_SPEC}/protocols/{name}.md"


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
            "file": protocol_path("review"),
            "reason": "Quality, contract, and template consistency check",
        },
        {
            "file": protocol_path("decision-review"),
            "reason": "Verify structured decision review evidence",
        },
        {
            "file": protocol_path("spec-maintenance"),
            "reason": "Verify specification maintenance decisions",
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
            "file": protocol_path("spec-maintenance"),
            "reason": "Capture implementation lessons and contracts",
        },
        {
            "file": protocol_path("review"),
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

            issue = validate_context_entry(
                self.repo_root,
                context_file.name,
                line_number,
                data,
            )
            if issue is not None:
                issues.append(issue)

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
