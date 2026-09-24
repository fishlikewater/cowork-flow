#!/usr/bin/env python3
"""Task tree application service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from infra.paths import DIR_ARCHIVE, get_tasks_dir
from services.task_repository import TaskRepository, TaskRepositoryError
from infra.storage.unit_of_work import UnitOfWork, UnitOfWorkError


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
        parent_dir, parent_data, parent_revision = self._load_snapshot(
            parent, "parent"
        )
        child_dir, child_data, child_revision = self._load_snapshot(
            child, "child"
        )
        if parent_dir.resolve() == child_dir.resolve():
            raise TaskTreeError(
                "TASK-TREE-CYCLE-001",
                child_dir,
                "a task cannot be its own parent",
            )

        existing_parent = child_data.get("parent")
        if isinstance(existing_parent, str) and existing_parent.strip():
            if existing_parent.strip() == parent_dir.name:
                children = list(parent_data.get("children") or [])
                if child_dir.name in children:
                    return
            else:
                raise TaskTreeError(
                    "TASK-TREE-PARENT-001",
                    child_dir,
                    f"child already has parent {existing_parent}",
                )

        self._reject_cycle(parent_dir, child_dir)
        children = list(parent_data.get("children") or [])
        if child_dir.name not in children:
            children.append(child_dir.name)
        persisted_parent = dict(parent_data)
        persisted_parent["children"] = children
        persisted_child = dict(child_data)
        persisted_child["parent"] = parent_dir.name
        self._commit_relation(
            "link",
            parent_dir,
            parent_data,
            persisted_parent,
            parent_revision,
            child_dir,
            child_data,
            persisted_child,
            child_revision,
        )

    def unlink(self, parent: str | Path, child: str | Path) -> None:
        parent_dir, parent_data, parent_revision = self._load_snapshot(
            parent, "parent"
        )
        child_dir, child_data, child_revision = self._load_snapshot(
            child, "child"
        )
        existing_parent = child_data.get("parent")
        if isinstance(existing_parent, str) and existing_parent.strip():
            if existing_parent.strip() != parent_dir.name:
                raise TaskTreeError(
                    "TASK-TREE-PARENT-002",
                    child_dir,
                    f"child is linked to {existing_parent}, not {parent_dir.name}",
                )
        children = list(parent_data.get("children") or [])
        already_unlinked = (
            child_dir.name not in children
            and existing_parent in (None, "")
        )
        if already_unlinked:
            return
        if child_dir.name in children:
            children.remove(child_dir.name)
        persisted_parent = dict(parent_data)
        persisted_parent["children"] = children
        persisted_child = dict(child_data)
        persisted_child["parent"] = None
        self._commit_relation(
            "unlink",
            parent_dir,
            parent_data,
            persisted_parent,
            parent_revision,
            child_dir,
            child_data,
            persisted_child,
            child_revision,
        )

    def _load_snapshot(
        self,
        task: str | Path,
        role: str,
    ) -> tuple[Path, dict, int]:
        task_dir = self.repository.resolve(task)
        try:
            snapshot = self.repository.load_snapshot(task_dir)
        except TaskRepositoryError as error:
            raise TaskTreeError(
                f"TASK-TREE-{role.upper()}-LOAD-001",
                task_dir,
                f"{role} task metadata cannot be loaded",
            ) from error
        return task_dir, snapshot.data, snapshot.revision

    def _reject_cycle(self, parent_dir: Path, child_dir: Path) -> None:
        current = parent_dir
        visited: set[Path] = set()
        while True:
            resolved = current.resolve()
            if resolved == child_dir.resolve():
                raise TaskTreeError(
                    "TASK-TREE-CYCLE-001",
                    child_dir,
                    "link would create a parent cycle",
                )
            if resolved in visited:
                raise TaskTreeError(
                    "TASK-TREE-CYCLE-001",
                    current,
                    "existing task tree already contains a cycle",
                )
            visited.add(resolved)
            try:
                data = self.repository.load(current)
            except TaskRepositoryError:
                return
            parent = data.get("parent")
            if not isinstance(parent, str) or not parent.strip():
                return
            current = self.repository.resolve(parent.strip())

    def _commit_relation(
        self,
        action: str,
        parent_dir: Path,
        parent_data: dict,
        persisted_parent: dict,
        parent_revision: int,
        child_dir: Path,
        child_data: dict,
        persisted_child: dict,
        child_revision: int,
    ) -> None:
        try:
            UnitOfWork.recover_all(
                self.repo_root,
                state_store=self.repository.state_store,
            )
        except UnitOfWorkError as error:
            raise TaskTreeError(
                "TASK-TREE-RECOVERY-001",
                parent_dir,
                error.detail,
            ) from error

        identity = json.dumps(
            {
                "action": action,
                "parent": str(parent_dir.resolve()),
                "child": str(child_dir.resolve()),
                "parent_revision": parent_revision,
                "child_revision": child_revision,
                "parent_data": parent_data,
                "child_data": child_data,
                "persisted_parent": persisted_parent,
                "persisted_child": persisted_child,
                "attempt": uuid4().hex,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        operation_id = "task-tree-%s-%s" % (
            action,
            hashlib.sha256(identity).hexdigest()[:16],
        )
        unit = UnitOfWork(
            self.repo_root,
            operation_id=operation_id,
            kind=f"task-tree-{action}",
            state_store=self.repository.state_store,
        )
        unit.replace(
            self.repository.task_json_path(parent_dir),
            persisted_parent,
            expected_revision=parent_revision,
        )
        unit.replace(
            self.repository.task_json_path(child_dir),
            persisted_child,
            expected_revision=child_revision,
        )
        try:
            unit.commit()
        except UnitOfWorkError as error:
            raise TaskTreeError(
                "TASK-TREE-WRITE-001",
                parent_dir,
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
