#!/usr/bin/env python3
"""Task archive application service."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from infra.paths import DIR_ARCHIVE, get_tasks_dir
from runtime.session_state import clear_task_from_sessions
from infra.archive_utils import archive_directory_resumable
from services.context_jsonl import read_context_jsonl_entries
from services.task_repository import TaskRepository, TaskRepositoryError
from services.task_utils import find_task_by_name


from kernel.task_state import DONE_STATUSES  # noqa: F401
ArchiveFinalizer = Callable[[], bool]
PLAN_SNAPSHOT_NAME = "plan.md"


@dataclass(frozen=True)
class RollbackIssue:
    """Best-effort compensation issue that did not replace the primary error."""

    stage: str
    path: Path
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "path": str(self.path),
            "detail": self.detail,
        }


class TaskArchiveError(RuntimeError):
    """Raised when an archive_task action cannot complete safely."""

    def __init__(
        self,
        code: str,
        path: Path,
        detail: str,
        *,
        rollback_issues: tuple[RollbackIssue, ...] = (),
    ) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        self.rollback_issues = tuple(rollback_issues)
        super().__init__(f"{code}: {detail}: {path}")


@dataclass(frozen=True)
class TaskArchiveResult:
    source: Path
    destination: Path
    task_name: str
    archived_at: str


class TaskArchiveService:
    """Archive a completed task and reconcile active relationships."""

    def __init__(
        self,
        repo_root: Path,
        *,
        repository: TaskRepository | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.tasks_dir = get_tasks_dir(self.repo_root)
        self.repository = repository or TaskRepository(self.repo_root)

    def archive(
        self,
        task: str | Path,
        *,
        archived_at: str | None = None,
        finalize: ArchiveFinalizer | None = None,
    ) -> TaskArchiveResult:
        task_dir, task_data = self._load_completed_task(task)
        archive_date = archived_at or datetime.now().strftime("%Y-%m-%d")
        destination = self._archive_destination(task_dir, archive_date)
        relationship_updates = self._relationship_updates(
            task_dir.name,
            task_data,
        )
        context_snapshots = self._context_snapshots(task_dir)
        self._move_task(task_dir, destination)
        self._apply_archive_state(
            task_dir,
            destination,
            task_data,
            relationship_updates,
            context_snapshots,
            archive_date,
            finalize,
        )
        clear_task_from_sessions(
            self.repo_root,
            task_dir.relative_to(self.repo_root).as_posix(),
        )
        return TaskArchiveResult(
            source=task_dir,
            destination=destination,
            task_name=task_dir.name,
            archived_at=archive_date,
        )

    def _load_completed_task(self, task: str | Path) -> tuple[Path, dict]:
        task_dir = self.repository.resolve(task)
        if not task_dir.is_dir():
            raise TaskArchiveError(
                "TASK-ARCHIVE-NOT-FOUND-001",
                task_dir,
                "task directory does not exist",
            )

        try:
            task_data = self.repository.load(task_dir)
        except TaskRepositoryError as error:
            raise TaskArchiveError(
                "TASK-ARCHIVE-LOAD-001",
                error.path,
                error.detail,
            ) from error

        status = task_data.get("status", "unknown")
        if status not in DONE_STATUSES:
            raise TaskArchiveError(
                "TASK-ARCHIVE-STATUS-001",
                task_dir,
                f"task status is {status}",
            )
        return task_dir, task_data

    def _archive_destination(self, task_dir: Path, archive_date: str) -> Path:
        return (
            self.tasks_dir
            / DIR_ARCHIVE
            / archive_date[:7]
            / task_dir.name
        )

    @staticmethod
    def _move_task(task_dir: Path, destination: Path) -> None:
        move_result = archive_directory_resumable(task_dir, destination)
        if not move_result.ok:
            raise TaskArchiveError(
                "TASK-ARCHIVE-MOVE-001",
                destination,
                move_result.message,
            )

    def _apply_archive_state(
        self,
        task_dir: Path,
        destination: Path,
        task_data: dict,
        relationship_updates: list[tuple[Path, dict, dict]],
        context_snapshots: dict[str, bytes],
        archive_date: str,
        finalize: ArchiveFinalizer | None,
    ) -> None:
        try:
            self.repository.save(
                destination,
                {
                    "status": "completed",
                    "completedAt": archive_date,
                },
            )
            self._apply_relationship_updates(relationship_updates)
            self._normalize_context_paths(task_dir, destination)
            self._snapshot_plan_file(destination, task_data)
            if finalize is not None and not finalize():
                raise TaskArchiveError(
                    "TASK-ARCHIVE-FINALIZE-001",
                    destination,
                    "archive finalizer failed",
                )
        except Exception as error:
            rollback_issues = self._rollback(
                task_dir,
                destination,
                task_data,
                relationship_updates,
                context_snapshots,
            )
            if isinstance(error, TaskArchiveError):
                error.rollback_issues = tuple(
                    (*error.rollback_issues, *rollback_issues)
                )
                raise
            if isinstance(error, TaskRepositoryError):
                raise TaskArchiveError(
                    "TASK-ARCHIVE-WRITE-001",
                    error.path,
                    error.detail,
                    rollback_issues=rollback_issues,
                ) from error
            raise TaskArchiveError(
                "TASK-ARCHIVE-FINALIZE-001",
                destination,
                f"archive finalizer failed: {error}",
                rollback_issues=rollback_issues,
            ) from error

    def _relationship_updates(
        self,
        task_name: str,
        task_data: dict,
    ) -> list[tuple[Path, dict, dict]]:
        updates: list[tuple[Path, dict, dict]] = []
        parent_name = task_data.get("parent")
        if isinstance(parent_name, str) and parent_name.strip():
            parent_dir = find_task_by_name(parent_name, self.tasks_dir)
            if parent_dir is not None:
                try:
                    parent_data = self.repository.load(parent_dir)
                except TaskRepositoryError:
                    parent_data = {}
                if parent_data:
                    children = list(parent_data.get("children") or [])
                    if task_name in children:
                        children.remove(task_name)
                    updates.append(
                        (
                            parent_dir,
                            parent_data,
                            {"children": children},
                        )
                    )

        for child_name in task_data.get("children") or []:
            child_dir = find_task_by_name(str(child_name), self.tasks_dir)
            if child_dir is None:
                continue
            try:
                child_data = self.repository.load(child_dir)
            except TaskRepositoryError:
                continue
            updates.append(
                (
                    child_dir,
                    child_data,
                    {"parent": None},
                )
            )
        return updates

    @staticmethod
    def _context_snapshots(task_dir: Path) -> dict[str, bytes]:
        try:
            return {
                path.name: path.read_bytes()
                for path in task_dir.glob("*.jsonl")
                if path.is_file()
            }
        except OSError as error:
            raise TaskArchiveError(
                "TASK-ARCHIVE-CONTEXT-001",
                task_dir,
                f"failed to snapshot task context: {error}",
            ) from error

    @staticmethod
    def _discard_plan_snapshot(
        destination: Path,
        issues: list[RollbackIssue],
    ) -> None:
        plan_snapshot = destination / PLAN_SNAPSHOT_NAME
        if not plan_snapshot.exists():
            return
        try:
            plan_snapshot.unlink()
        except OSError as error:
            issues.append(
                RollbackIssue(
                    "plan_snapshot_remove",
                    plan_snapshot,
                    str(error),
                )
            )

    def _snapshot_plan_file(
        self,
        destination: Path,
        task_data: dict,
    ) -> None:
        meta = task_data.get("meta")
        plan_file = meta.get("planFile") if isinstance(meta, dict) else None
        if not isinstance(plan_file, str) or not plan_file.strip():
            return
        plan_path = self.repo_root / plan_file.strip()
        if not plan_path.is_file():
            return
        try:
            snapshot = plan_path.read_bytes()
            (destination / PLAN_SNAPSHOT_NAME).write_bytes(snapshot)
        except OSError as error:
            raise TaskArchiveError(
                "TASK-ARCHIVE-PLAN-001",
                plan_path,
                f"failed to snapshot plan file: {error}",
            ) from error

    def _normalize_context_paths(
        self,
        source: Path,
        destination: Path,
    ) -> None:
        source_path = source.relative_to(self.repo_root).as_posix()
        destination_path = destination.relative_to(self.repo_root).as_posix()
        for context_file in sorted(destination.glob("*.jsonl")):
            self._normalize_context_file(
                context_file,
                source_path,
                destination_path,
            )

    @staticmethod
    def _normalize_context_file(
        context_file: Path,
        source_path: str,
        destination_path: str,
    ) -> None:
        with context_file.open("r", encoding="utf-8", newline="") as stream:
            original = stream.read()
        entries_by_line = {
            entry.line: entry
            for entry in read_context_jsonl_entries(context_file).entries
        }
        rendered: list[str] = []
        changed = False
        for line_number, line in enumerate(original.splitlines(keepends=True), start=1):
            parsed = entries_by_line.get(line_number)
            if parsed is None or not isinstance(parsed.data, dict):
                rendered.append(line)
                continue
            file_path = parsed.data.get("file")
            normalized = TaskArchiveService._archived_context_path(
                file_path,
                source_path,
                destination_path,
            )
            if normalized == file_path:
                rendered.append(line)
                continue
            entry = dict(parsed.data)
            entry["file"] = normalized
            rendered.append(
                json.dumps(entry, ensure_ascii=False) + parsed.line_ending
            )
            changed = True
        if changed:
            with context_file.open("w", encoding="utf-8", newline="") as stream:
                stream.write("".join(rendered))

    @staticmethod
    def _archived_context_path(
        file_path: object,
        source_path: str,
        destination_path: str,
    ) -> object:
        if file_path == source_path:
            return destination_path
        if isinstance(file_path, str) and file_path.startswith(f"{source_path}/"):
            return destination_path + file_path[len(source_path):]
        return file_path

    def _apply_relationship_updates(
        self,
        updates: list[tuple[Path, dict, dict]],
    ) -> None:
        applied: list[tuple[Path, dict]] = []
        try:
            for task_dir, original, changes in updates:
                self.repository.save(task_dir, changes)
                applied.append((task_dir, original))
        except TaskRepositoryError as error:
            rollback_issues: list[RollbackIssue] = []
            for task_dir, original in reversed(applied):
                try:
                    self.repository.replace(task_dir, original)
                except Exception as rollback_error:
                    rollback_issues.append(
                        RollbackIssue(
                            "relationship_restore",
                            Path(str(getattr(rollback_error, "path", task_dir / "task.json"))),
                            str(getattr(rollback_error, "detail", rollback_error)),
                        )
                    )
            raise TaskArchiveError(
                "TASK-ARCHIVE-RELATIONSHIP-001",
                error.path,
                error.detail,
                rollback_issues=tuple(rollback_issues),
            ) from error

    def _rollback(
        self,
        source: Path,
        destination: Path,
        task_data: dict,
        relationship_updates: list[tuple[Path, dict, dict]],
        context_snapshots: dict[str, bytes],
    ) -> tuple[RollbackIssue, ...]:
        issues: list[RollbackIssue] = []
        for task_dir, original, _ in relationship_updates:
            try:
                self.repository.replace(task_dir, original)
            except Exception as error:
                issues.append(
                    RollbackIssue(
                        "relationship_restore",
                        Path(str(getattr(error, "path", task_dir / "task.json"))),
                        str(getattr(error, "detail", error)),
                    )
                )

        self._discard_plan_snapshot(destination, issues)

        directory_restore_attempted = False
        if destination.is_dir() and not source.exists():
            directory_restore_attempted = True
            try:
                move_result = archive_directory_resumable(destination, source)
            except Exception as error:  # best-effort compensation boundary
                issues.append(
                    RollbackIssue(
                        "directory_restore",
                        source,
                        f"failed to restore archived directory: {error}",
                    )
                )
            else:
                if not move_result.ok:
                    issues.append(
                        RollbackIssue(
                            "directory_restore",
                            move_result.destination,
                            move_result.message,
                        )
                    )
        if source.is_dir():
            for name, content in context_snapshots.items():
                context_path = source / name
                try:
                    context_path.write_bytes(content)
                except Exception as error:
                    issues.append(
                        RollbackIssue(
                            "context_restore",
                            context_path,
                            str(error),
                        )
                    )
            try:
                self.repository.replace(source, task_data)
            except Exception as error:
                issues.append(
                    RollbackIssue(
                        "task_json_restore",
                        Path(str(getattr(error, "path", source / "task.json"))),
                        str(getattr(error, "detail", error)),
                    )
                )
        elif not source.exists() and not directory_restore_attempted:
            issues.append(
                RollbackIssue(
                    "directory_restore",
                    source,
                    "source task directory was not restored",
                )
            )
        return tuple(issues)
