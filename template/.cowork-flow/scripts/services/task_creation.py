#!/usr/bin/env python3
"""Task creation application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.task_tree import TaskTreeError, TaskTreeService
from infra.paths import (
    FILE_TASK_JSON,
    ensure_task_date_prefix,
    get_tasks_dir,
)
from services.plan_binding import PlanBindingError, bind_plan_file
from services.task_repository import TaskRepository, TaskRepositoryError


class TaskCreationError(RuntimeError):
    """Raised when task creation cannot be completed."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


@dataclass(frozen=True)
class TaskCreationRequest:
    title: str
    slug: str
    assignee: str
    priority: str
    description: str | None = None
    creator: str | None = None
    parent: str | Path | None = None
    from_plan: str | Path | None = None
    created_at: str | None = None
    date_prefix: str | None = None


@dataclass(frozen=True)
class TaskCreationResult:
    task_dir: Path
    directory_existed: bool
    linked_parent: str | None
    missing_parent: str | None
    generated_anchor: bool


def ensure_tasks_dir(repo_root: Path) -> Path:
    """Ensure active and archived task directories exist."""
    tasks_dir = get_tasks_dir(repo_root)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "archive").mkdir(parents=True, exist_ok=True)
    return tasks_dir


class TaskCreationService:
    """Create task metadata and optional parent/plan relationships."""

    def __init__(
        self,
        repo_root: Path,
        *,
        repository: TaskRepository | None = None,
        tree_service: TaskTreeService | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.repository = repository or TaskRepository(self.repo_root)
        self.tree_service = tree_service or TaskTreeService(
            self.repo_root,
            repository=self.repository,
        )

    def create(
        self,
        request: TaskCreationRequest,
    ) -> TaskCreationResult:
        tasks_dir = ensure_tasks_dir(self.repo_root)
        task_name = self._task_name(request)
        task_dir = tasks_dir / task_name
        plan_metadata, bound_plan_path = self._plan_metadata(request.from_plan)
        directory_existed = task_dir.exists()
        task_dir.mkdir(parents=True, exist_ok=True)

        created_at = request.created_at or datetime.now().strftime(
            "%Y-%m-%d"
        )
        task_data = {
            "id": task_name,
            "name": task_name,
            "title": request.title,
            "description": request.description or "",
            "status": "planning",
            "dev_type": None,
            "scope": None,
            "priority": request.priority,
            "creator": request.creator or request.assignee,
            "assignee": request.assignee,
            "createdAt": created_at,
            "completedAt": None,
            "commit": None,
            "subtasks": [],
            "children": [],
            "parent": None,
            "relatedFiles": [],
            "notes": "",
            "meta": plan_metadata,
        }
        try:
            self.repository.replace(task_dir, task_data)
        except TaskRepositoryError as error:
            raise TaskCreationError(
                "TASK-CREATE-SAVE-001",
                error.path,
                error.detail,
            ) from error

        linked_parent = None
        missing_parent = None
        if request.parent:
            parent_dir = self.repository.resolve(request.parent)
            if not (parent_dir / FILE_TASK_JSON).is_file():
                missing_parent = str(request.parent)
            else:
                try:
                    self.tree_service.link(parent_dir, task_dir)
                except TaskTreeError as error:
                    raise TaskCreationError(
                        "TASK-CREATE-LINK-001",
                        error.path,
                        error.detail,
                    ) from error
                linked_parent = parent_dir.name

        generated_anchor = self._generate_anchor(
            task_dir,
            bound_plan_path,
        )
        return TaskCreationResult(
            task_dir=task_dir,
            directory_existed=directory_existed,
            linked_parent=linked_parent,
            missing_parent=missing_parent,
            generated_anchor=generated_anchor,
        )

    @staticmethod
    def _task_name(request: TaskCreationRequest) -> str:
        if request.date_prefix:
            return f"{request.date_prefix}-{request.slug}"
        return ensure_task_date_prefix(request.slug)

    def _plan_metadata(self, from_plan: str | Path | None) -> tuple[dict, Path | None]:
        if not from_plan:
            return {}, None
        try:
            bound = bind_plan_file(
                self.repo_root,
                from_plan,
                allow_absolute=True,
                require_exists=True,
            )
        except PlanBindingError as error:
            raise self._plan_creation_error(error) from error
        return {"planFile": bound.normalized}, bound.path

    @staticmethod
    def _plan_creation_error(error: PlanBindingError) -> TaskCreationError:
        if error.code == "missing":
            return TaskCreationError(
                "TASK-CREATE-PLAN-003",
                error.path,
                "plan file does not exist",
            )
        if error.code == "outside_repository":
            return TaskCreationError(
                "TASK-CREATE-PLAN-004",
                error.path,
                "plan file must be inside the repository",
            )
        return TaskCreationError(
            "TASK-CREATE-PLAN-005",
            error.path,
            "plan file must live under .cowork-flow/plans",
        )

    @staticmethod
    def _generate_anchor(
        task_dir: Path,
        plan_path: Path | None,
    ) -> bool:
        if plan_path is None:
            return False
        if not plan_path.is_file():
            return False

        try:
            plan_text = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise TaskCreationError(
                "TASK-CREATE-PLAN-001",
                plan_path,
                "plan cannot be read as UTF-8",
            ) from error

        goal = next(
            (
                line.split(":", 1)[1].strip()
                for line in plan_text.splitlines()
                if line.startswith("**Goal:**")
                or line.startswith("**目标:**")
            ),
            None,
        )
        anchor_file = task_dir / "decision-anchor.md"
        if not goal or anchor_file.exists():
            return False
        try:
            anchor_file.write_text(
                f"## 目标\n\n{goal}\n\n## 验收标准\n- [ ] \n",
                encoding="utf-8",
            )
        except OSError as error:
            raise TaskCreationError(
                "TASK-CREATE-PLAN-002",
                anchor_file,
                "decision anchor could not be written",
            ) from error
        return True
