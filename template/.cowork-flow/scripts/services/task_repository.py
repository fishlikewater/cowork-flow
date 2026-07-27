#!/usr/bin/env python3
"""Task metadata persistence boundary."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from infra.paths import DIR_WORKFLOW, FILE_TASK_JSON, get_tasks_dir
from infra.storage.state_store import (
    StateSnapshot,
    StateStore,
    StateStoreError,
)
from services.task_utils import find_task_by_name


class TaskRepositoryError(RuntimeError):
    """Raised when task metadata cannot be loaded or persisted."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


class TaskRepository:
    """Resolve task directories and persist task metadata."""

    def __init__(
        self,
        repo_root: Path,
        *,
        state_store: StateStore | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.tasks_dir = get_tasks_dir(self.repo_root)
        self.state_store = state_store or StateStore()

    def resolve(self, target: str | Path) -> Path:
        """Resolve absolute paths, workflow-relative paths, or task names."""
        if isinstance(target, Path):
            if target.is_absolute():
                return target
            target_text = str(target)
        else:
            target_text = target

        if not target_text:
            return Path()

        target_path = Path(target_text)
        if target_text.startswith("/") or target_path.is_absolute():
            return target_path

        if "/" in target_text or target_text.startswith(DIR_WORKFLOW):
            return self.repo_root / target_path

        found = find_task_by_name(target_text, self.tasks_dir)
        if found:
            return found
        return self.repo_root / target_path

    def task_json_path(self, task: str | Path) -> Path:
        return self.resolve(task) / FILE_TASK_JSON

    def load_snapshot(self, task: str | Path) -> StateSnapshot:
        """Load task metadata together with its revision."""
        task_json = self.task_json_path(task)
        try:
            return self.state_store.load(task_json)
        except StateStoreError as error:
            raise self._translate_load_error(error) from error

    def load(self, task: str | Path) -> dict:
        """Load task metadata as UTF-8 JSON without rendering errors."""
        return self.load_snapshot(task).data

    def save(
        self,
        task: str | Path,
        changes: dict,
        *,
        expected_revision: int | None = None,
        operation_id: str | None = None,
    ) -> dict:
        """Merge and atomically persist task metadata as UTF-8 JSON."""
        task_json = self.task_json_path(task)
        snapshot = self.load_snapshot(task)
        persisted = dict(snapshot.data)
        persisted.update(changes)
        expected = (
            snapshot.revision
            if expected_revision is None
            else expected_revision
        )
        try:
            return self.state_store.replace(
                task_json,
                persisted,
                expected_revision=expected,
                operation_id=operation_id or f"task-save-{uuid4().hex}",
            ).data
        except StateStoreError as error:
            raise self._translate_save_error(error) from error

    def replace(
        self,
        task: str | Path,
        data: dict,
        *,
        expected_revision: int | None = None,
        operation_id: str | None = None,
    ) -> dict:
        """Atomically replace task metadata with an exact snapshot."""
        task_json = self.task_json_path(task)
        try:
            current = self.state_store.load(task_json, missing_ok=True)
            expected = (
                current.revision
                if expected_revision is None
                else expected_revision
            )
            return self.state_store.replace(
                task_json,
                dict(data),
                expected_revision=expected,
                operation_id=operation_id or f"task-replace-{uuid4().hex}",
            ).data
        except StateStoreError as error:
            raise self._translate_save_error(error) from error

    @staticmethod
    def _translate_load_error(
        error: StateStoreError,
    ) -> TaskRepositoryError:
        code = {
            "STATE-LOAD-001": "TASK-LOAD-001",
            "STATE-LOAD-002": "TASK-LOAD-002",
            "STATE-LOAD-005": "TASK-LOAD-002",
            "STATE-LOAD-003": "TASK-LOAD-003",
            "STATE-LOAD-004": "TASK-LOAD-003",
        }.get(error.code, "TASK-LOAD-003")
        return TaskRepositoryError(code, error.path, error.detail)

    @staticmethod
    def _translate_save_error(
        error: StateStoreError,
    ) -> TaskRepositoryError:
        code = (
            "TASK-SAVE-002"
            if error.code == "STATE-CONFLICT-001"
            else "TASK-SAVE-001"
        )
        return TaskRepositoryError(code, error.path, error.detail)
