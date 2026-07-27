#!/usr/bin/env python3
"""Task archive application service."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kernel.paths import DIR_ARCHIVE, get_tasks_dir
from kernel.session_state import clear_task_from_sessions
from kernel.archive_utils import archive_directory_resumable
from kernel.task_repository import TaskRepository, TaskRepositoryError
from kernel.task_utils import find_task_by_name


DONE_STATUSES = ("completed", "done")
ArchiveFinalizer = Callable[[], bool]


class TaskArchiveError(RuntimeError):
    """Raised when an archive_task action cannot complete safely."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
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
            if finalize is not None and not finalize():
                raise TaskArchiveError(
                    "TASK-ARCHIVE-FINALIZE-001",
                    destination,
                    "linked change archive failed",
                )
        except Exception as error:
            self._rollback(
                task_dir,
                destination,
                task_data,
                relationship_updates,
                context_snapshots,
            )
            if isinstance(error, TaskArchiveError):
                raise
            if isinstance(error, TaskRepositoryError):
                raise TaskArchiveError(
                    "TASK-ARCHIVE-WRITE-001",
                    error.path,
                    error.detail,
                ) from error
            raise TaskArchiveError(
                "TASK-ARCHIVE-FINALIZE-001",
                destination,
                f"archive finalizer failed: {error}",
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
        original = context_file.read_text(encoding="utf-8")
        rendered: list[str] = []
        changed = False
        for line in original.splitlines(keepends=True):
            content = line.rstrip("\r\n")
            ending = line[len(content):]
            try:
                entry = json.loads(content)
            except json.JSONDecodeError:
                rendered.append(line)
                continue
            file_path = entry.get("file") if isinstance(entry, dict) else None
            normalized = TaskArchiveService._archived_context_path(
                file_path,
                source_path,
                destination_path,
            )
            if normalized == file_path:
                rendered.append(line)
                continue
            entry["file"] = normalized
            rendered.append(
                json.dumps(entry, ensure_ascii=False) + ending
            )
            changed = True
        if changed:
            context_file.write_text("".join(rendered), encoding="utf-8")

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
            for task_dir, original in reversed(applied):
                try:
                    self.repository.replace(task_dir, original)
                except TaskRepositoryError:
                    pass
            raise TaskArchiveError(
                "TASK-ARCHIVE-RELATIONSHIP-001",
                error.path,
                error.detail,
            ) from error

    def _rollback(
        self,
        source: Path,
        destination: Path,
        task_data: dict,
        relationship_updates: list[tuple[Path, dict, dict]],
        context_snapshots: dict[str, bytes],
    ) -> None:
        for task_dir, original, _ in relationship_updates:
            try:
                self.repository.replace(task_dir, original)
            except TaskRepositoryError:
                pass

        if destination.is_dir() and not source.exists():
            archive_directory_resumable(destination, source)
        if source.is_dir():
            for name, content in context_snapshots.items():
                try:
                    (source / name).write_bytes(content)
                except OSError:
                    pass
            try:
                self.repository.replace(source, task_data)
            except TaskRepositoryError:
                pass
