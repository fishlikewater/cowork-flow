#!/usr/bin/env python3
"""Task context application service."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from infra.files import read_text_utf8
from infra.quality_sources import quality_source_entries
from infra.skill_manifest import context_entries
from infra.paths import (
    DIR_AGENTS,
    DIR_SPEC,
    DIR_WORKFLOW,
    FILE_TASK_JSON,
    get_repo_root,
)


CONTEXT_JSONL_FILES = ("implement.jsonl", "check.jsonl", "debug.jsonl")
CONTEXT_ENTRY_TYPES = frozenset(("file", "directory", "planned-file", "deleted-file"))


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
    _validate_context_entry_type(candidate, entry_type)
    normalized = _normalized_context_path(path, entry_type)
    segments = normalized.split("/")
    _validate_context_path(candidate, normalized, segments, path, entry_type)
    repo_root, full_path = _resolved_context_target(repo_root, segments)
    return _typed_context_path(normalized, full_path, repo_root, entry_type)


def _validate_context_entry_type(candidate: Path, entry_type: str) -> None:
    if entry_type not in CONTEXT_ENTRY_TYPES:
        raise TaskContextError(
            "TASK-CONTEXT-TYPE-001",
            candidate,
            f"unsupported context entry type: {entry_type}",
        )


def _normalized_context_path(path: str, entry_type: str) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if entry_type == "directory" and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _validate_context_path(
    candidate: Path,
    normalized: str,
    segments: list[str],
    path: str,
    entry_type: str,
) -> None:
    if not _is_valid_context_path(normalized, segments, path, entry_type):
        raise TaskContextError(
            "TASK-CONTEXT-PATH-002",
            candidate,
            "context path must be a canonical repository-relative path",
        )


def _is_valid_context_path(
    normalized: str,
    segments: list[str],
    path: str,
    entry_type: str,
) -> bool:
    return not (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in ("", ".", "..") for segment in segments)
        or any(character in normalized for character in "*?[]")
        or (entry_type in {"planned-file", "deleted-file"} and str(path).endswith(("/", "\\")))
    )


def _resolved_context_target(
    repo_root: Path,
    segments: list[str],
) -> tuple[Path, Path]:
    resolved_root = Path(repo_root).resolve()
    return resolved_root, resolved_root.joinpath(*segments).resolve(strict=False)


def _typed_context_path(
    normalized: str,
    full_path: Path,
    repo_root: Path,
    entry_type: str,
) -> tuple[str, Path]:
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
        "deleted-file": not full_path.is_dir(),
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


@dataclass(frozen=True)
class ContextJsonlEntry:
    context_file: str
    line: int
    data: object
    text: str
    line_ending: str


@dataclass(frozen=True)
class ContextJsonlReadResult:
    context_file: str
    exists: bool
    entry_count: int
    entries: tuple[ContextJsonlEntry, ...]
    issues: tuple[ContextValidationIssue, ...]


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


def write_jsonl(path: Path, entries: list[dict]) -> None:
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def iter_jsonl_lines(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            yield line_number, line.rstrip("\n")


def read_context_jsonl_entries(context_file: Path) -> ContextJsonlReadResult:
    """Parse a context JSONL file into reusable line-level facts."""
    context_file = Path(context_file)
    if not context_file.is_file():
        return ContextJsonlReadResult(
            context_file=context_file.name,
            exists=False,
            entry_count=0,
            entries=(),
            issues=(),
        )

    entries: list[ContextJsonlEntry] = []
    issues: list[ContextValidationIssue] = []
    entry_count = 0
    try:
        lines: list[tuple[int, str, str]] = []
        with context_file.open("r", encoding="utf-8", newline="") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                text = raw_line.rstrip("\r\n")
                line_ending = raw_line[len(text):]
                lines.append((line_number, text, line_ending))
    except (OSError, UnicodeDecodeError) as error:
        return ContextJsonlReadResult(
            context_file=context_file.name,
            exists=True,
            entry_count=0,
            entries=(),
            issues=(
                ContextValidationIssue(
                    context_file=context_file.name,
                    line=0,
                    code="read_error",
                    message=f"Cannot read {context_file.name}: {error}",
                ),
            ),
        )

    for line_number, line, line_ending in lines:
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
        entries.append(
            ContextJsonlEntry(
                context_file=context_file.name,
                line=line_number,
                data=data,
                text=line,
                line_ending=line_ending,
            )
        )

    return ContextJsonlReadResult(
        context_file=context_file.name,
        exists=True,
        entry_count=entry_count,
        entries=tuple(entries),
        issues=tuple(issues),
    )


def normalize_context_file_scope_entry(
    repo_root: Path,
    entry: dict,
) -> tuple[str | None, str | None]:
    """Return the file-scope path allowed by one context entry.

    Directory entries are valid context, but they do not authorize arbitrary
    changed files for lifecycle review.
    """
    entry_type = entry.get("type", "file")
    file_path = entry.get("file")
    if not isinstance(file_path, str) or not file_path:
        return None, "missing file path"
    if entry_type == "directory":
        return _normalize_context_file_scope_path(repo_root, file_path, entry_type)
    if entry_type not in ("file", "planned-file", "deleted-file"):
        return None, f"unsupported type {entry_type!r}"
    return _normalize_context_file_scope_path(repo_root, file_path, entry_type)


def _normalize_context_file_scope_path(
    repo_root: Path,
    file_path: str,
    entry_type: str,
) -> tuple[str | None, str | None]:
    try:
        normalized, _full_path = normalize_context_path(
            repo_root,
            file_path,
            entry_type,
        )
    except TaskContextError:
        return None, f"non-canonical path {file_path!r}"
    if entry_type == "directory":
        return None, None
    return normalized, None


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
        meta = task_data.get("meta")
        plan_file = meta.get("planFile") if isinstance(meta, dict) else None
        if not isinstance(plan_file, str) or not plan_file.strip():
            return ["planFile is required before implementation starts"]
        normalized = self._normalize_plan_file(plan_file)
        if normalized is None:
            return ["planFile must be a repo-relative .cowork-flow/plans path"]
        plan_path = self.repo_root / normalized
        if not plan_path.is_file():
            return [f"planFile does not exist: {normalized}"]
        if not read_text_utf8(plan_path).strip():
            return [f"planFile is empty: {normalized}"]
        return []

    @staticmethod
    def _normalize_plan_file(plan_file: str) -> str | None:
        normalized = plan_file.replace("\\", "/").strip()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        segments = normalized.split("/")
        if (
            not normalized
            or normalized.startswith("/")
            or any(segment in ("", ".", "..") for segment in segments)
            or not normalized.startswith(".cowork-flow/plans/")
        ):
            return None
        return normalized

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
