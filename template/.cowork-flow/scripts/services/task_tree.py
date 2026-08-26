#!/usr/bin/env python3
"""Task tree application service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from infra.paths import DIR_ARCHIVE, get_tasks_dir
from services.task_repository import TaskRepository, TaskRepositoryError


from kernel.task_state import DONE_STATUSES  # noqa: F401


class TaskTreeError(RuntimeError):
    """Raised when a task relationship mutation cannot be completed."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


@dataclass(frozen=True)
class TaskNode:
    name: str
    status: str
    assignee: str
    children: tuple[str, ...]
    parent: str | None


class TaskTreeService:
    """Manage task parent-child relationships and hierarchy queries."""

    def __init__(
        self,
        repo_root: Path,
        *,
        repository: TaskRepository | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.tasks_dir = get_tasks_dir(self.repo_root)
        self.repository = repository or TaskRepository(self.repo_root)

    def link(self, parent: str | Path, child: str | Path) -> None:
        parent_dir, parent_data = self._load(parent, "parent")
        child_dir, child_data = self._load(child, "child")
        existing_parent = child_data.get("parent")
        if isinstance(existing_parent, str) and existing_parent.strip():
            raise TaskTreeError(
                "TASK-TREE-PARENT-001",
                child_dir,
                f"child already has parent {existing_parent}",
            )

        children = list(parent_data.get("children") or [])
        if child_dir.name not in children:
            children.append(child_dir.name)

        try:
            self.repository.save(parent_dir, {"children": children})
            self.repository.save(child_dir, {"parent": parent_dir.name})
        except TaskRepositoryError as error:
            try:
                self.repository.replace(parent_dir, parent_data)
                self.repository.replace(child_dir, child_data)
            except TaskRepositoryError:
                pass
            raise TaskTreeError(
                "TASK-TREE-WRITE-001",
                error.path,
                error.detail,
            ) from error

    def unlink(self, parent: str | Path, child: str | Path) -> None:
        parent_dir, parent_data = self._load(parent, "parent")
        child_dir, child_data = self._load(child, "child")
        children = list(parent_data.get("children") or [])
        if child_dir.name in children:
            children.remove(child_dir.name)

        try:
            self.repository.save(parent_dir, {"children": children})
            self.repository.save(child_dir, {"parent": None})
        except TaskRepositoryError as error:
            try:
                self.repository.replace(parent_dir, parent_data)
                self.repository.replace(child_dir, child_data)
            except TaskRepositoryError:
                pass
            raise TaskTreeError(
                "TASK-TREE-WRITE-001",
                error.path,
                error.detail,
            ) from error

    def active_nodes(self) -> dict[str, TaskNode]:
        nodes: dict[str, TaskNode] = {}
        if not self.tasks_dir.is_dir():
            return nodes

        for task_dir in sorted(self.tasks_dir.iterdir()):
            if not task_dir.is_dir() or task_dir.name == DIR_ARCHIVE:
                continue
            try:
                data = self.repository.load(task_dir)
            except TaskRepositoryError:
                data = {}
            nodes[task_dir.name] = TaskNode(
                name=task_dir.name,
                status=str(data.get("status") or "unknown"),
                assignee=str(data.get("assignee") or "-"),
                children=tuple(data.get("children") or ()),
                parent=data.get("parent"),
            )
        return nodes

    @staticmethod
    def root_names(nodes: dict[str, TaskNode]) -> tuple[str, ...]:
        return tuple(
            sorted(name for name, node in nodes.items() if not node.parent)
        )

    @staticmethod
    def children_progress(
        children: tuple[str, ...] | list[str],
        nodes: dict[str, TaskNode],
    ) -> tuple[int, int]:
        done = sum(
            1
            for child in children
            if nodes.get(child)
            and nodes[child].status in DONE_STATUSES
        )
        return done, len(children)

    def archived_tasks(
        self,
        month: str | None = None,
    ) -> dict[str, tuple[str, ...]]:
        archive_dir = self.tasks_dir / DIR_ARCHIVE
        if month:
            month_dir = archive_dir / month
            return {
                month: self._directory_names(month_dir)
            } if month_dir.is_dir() else {}
        if not archive_dir.is_dir():
            return {}
        return {
            month_dir.name: self._directory_names(month_dir)
            for month_dir in sorted(archive_dir.iterdir())
            if month_dir.is_dir()
        }

    def _load(
        self,
        task: str | Path,
        role: str,
    ) -> tuple[Path, dict]:
        task_dir = self.repository.resolve(task)
        try:
            return task_dir, self.repository.load(task_dir)
        except TaskRepositoryError as error:
            raise TaskTreeError(
                f"TASK-TREE-{role.upper()}-LOAD-001",
                task_dir,
                f"{role} task metadata cannot be loaded",
            ) from error

    @staticmethod
    def _directory_names(directory: Path) -> tuple[str, ...]:
        return tuple(
            path.name
            for path in sorted(directory.iterdir())
            if path.is_dir()
        )
