#!/usr/bin/env python3
"""Task creation application service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.task_tree import TaskTreeError, TaskTreeService
from services import task_graph
from infra.paths import (
    FILE_TASK_JSON,
    ensure_task_date_prefix,
    get_tasks_dir,
)
from services.plan_binding import PlanBindingError, bind_plan_file
from services.task_gate_profiles import GATE_PROFILE_STRICT
from services.task_repository import TaskRepository, TaskRepositoryError


class TaskCreationError(RuntimeError):
    """Raised when task creation cannot be completed."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


# The dev types that actually change what an implementer is told to read
# (`context_discovery.implement_spec_entries`): each one has a spec pack
# and/or a narrow `devTypes` skill rule behind it. Values without a
# dispatch effect are deliberately not offered, so the flag cannot
# promise a reading list it never produces.
VALID_DEV_TYPES: tuple[str, ...] = (
    "backend",
    "frontend",
    "fullstack",
    "test",
    "spec",
)


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
    depends_on: tuple[str, ...] = ()
    dev_type: str | None = None
    task_type: str | None = None
    created_at: str | None = None
    date_prefix: str | None = None


@dataclass(frozen=True)
class TaskCreationResult:
    task_dir: Path
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
        if task_dir.exists():
            raise TaskCreationError(
                "TASK-CREATE-EXISTS-001",
                task_dir,
                "task directory already exists; choose a different slug",
            )
        _validate_dev_type(request.dev_type, task_dir)
        plan_metadata, bound_plan_path = self._plan_metadata(request.from_plan)
        dependencies = self._resolve_dependencies(
            request.depends_on, task_name, request.slug
        )
        task_dir.mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []
        try:
            self._write_task_json(
                task_dir,
                self._task_data(request, task_name, plan_metadata, dependencies),
            )
            created_files.append(task_dir / FILE_TASK_JSON)

            linked_parent, missing_parent = self._link_parent(request, task_dir)
            generated_anchor = self._generate_anchor(
                task_dir,
                bound_plan_path,
            )
            if generated_anchor:
                created_files.append(task_dir / "decision-anchor.md")
        except Exception:
            self._remove_created_artifacts(task_dir, created_files)
            raise
        return TaskCreationResult(
            task_dir=task_dir,
            linked_parent=linked_parent,
            missing_parent=missing_parent,
            generated_anchor=generated_anchor,
        )

    def _task_data(
        self,
        request: TaskCreationRequest,
        task_name: str,
        plan_metadata: dict,
        dependencies: list[str],
    ) -> dict:
        created_at = request.created_at or datetime.now().strftime("%Y-%m-%d")
        meta = dict(plan_metadata) if isinstance(plan_metadata, dict) else {}
        meta.setdefault("gateProfile", GATE_PROFILE_STRICT)
        # The light profile is declarable at creation only: this is the sole
        # write of the field, and no lifecycle command changes it later.
        if request.task_type:
            meta["taskType"] = request.task_type
        return {
            "id": task_name,
            "name": task_name,
            "title": request.title,
            "description": request.description or "",
            "status": "planning",
            "dev_type": request.dev_type,
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
            "dependsOn": list(dependencies),
            "notes": "",
            "meta": meta,
        }

    def _resolve_dependencies(
        self,
        declared: tuple[str, ...],
        task_name: str,
        slug: str,
    ) -> list[str]:
        """Validate declared dependencies and return canonical task names.

        Fail-closed before anything is written: a missing target, a self
        dependency, or a dependency cycle rejects the whole creation.
        """
        resolved: list[str] = []
        for raw in declared:
            token = raw.strip() if isinstance(raw, str) else ""
            if not token:
                continue
            if token in {task_name, slug}:
                raise TaskCreationError(
                    "TASK-CREATE-DEPENDENCY-002",
                    self.repo_root,
                    f"task cannot depend on itself: {token}",
                )
            dependency_dir = task_graph.find_task_dir(self.repo_root, token)
            if dependency_dir is None:
                raise TaskCreationError(
                    "TASK-CREATE-DEPENDENCY-001",
                    self.repo_root,
                    "dependency task not found (use the full task directory "
                    f"name): {token}",
                )
            if dependency_dir.name not in resolved:
                resolved.append(dependency_dir.name)
        cycle = task_graph.dependency_cycle_for_new(
            self.repo_root, task_name, resolved
        )
        if cycle is not None:
            raise TaskCreationError(
                "TASK-CREATE-DEPENDENCY-003",
                self.repo_root,
                "dependency cycle: " + " -> ".join(cycle),
            )
        return resolved

    def _write_task_json(self, task_dir: Path, task_data: dict) -> None:
        """Write task.json, translating repository failures into create errors."""
        task_json = task_dir / FILE_TASK_JSON
        try:
            self.repository.replace(
                task_dir,
                task_data,
                expected_revision=0,
            )
        except TaskRepositoryError as error:
            if task_json.exists() or error.code == "TASK-SAVE-002":
                raise TaskCreationError(
                    "TASK-CREATE-EXISTS-001",
                    task_json,
                    "task metadata already exists; choose a different slug",
                ) from error
            raise TaskCreationError(
                "TASK-CREATE-SAVE-001",
                error.path,
                error.detail,
            ) from error

    def _link_parent(
        self,
        request: TaskCreationRequest,
        task_dir: Path,
    ) -> tuple[str | None, str | None]:
        """Link the requested parent; a requested parent that is gone is reported."""
        if not request.parent:
            return None, None
        parent_dir = self.repository.resolve(request.parent)
        if not (parent_dir / FILE_TASK_JSON).is_file():
            return None, str(request.parent)
        try:
            self.tree_service.link(parent_dir, task_dir)
        except TaskTreeError as error:
            raise TaskCreationError(
                "TASK-CREATE-LINK-001",
                error.path,
                error.detail,
            ) from error
        return parent_dir.name, None

    @staticmethod
    def _remove_created_artifacts(
        task_dir: Path,
        created_files: list[Path],
    ) -> None:
        """Remove only files this create call wrote, then an emptied directory."""
        for path in created_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
        try:
            task_dir.rmdir()
        except OSError:
            pass

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
                f"## 目标\n\n{goal}\n\n## 验收标准\n"
                "<!-- 至少一条，例如：- [ ] AC-001: ... -->\n",
                encoding="utf-8",
            )
        except OSError as error:
            try:
                anchor_file.unlink(missing_ok=True)
            except OSError:
                pass
            raise TaskCreationError(
                "TASK-CREATE-PLAN-002",
                anchor_file,
                "decision anchor could not be written",
            ) from error
        return True


def _validate_dev_type(dev_type: str | None, path: Path) -> None:
    """Reject an unknown dev type before anything is written."""
    if dev_type is None:
        return
    if dev_type not in VALID_DEV_TYPES:
        raise TaskCreationError(
            "TASK-CREATE-DEVTYPE-001",
            path,
            f"unknown dev_type '{dev_type}'; expected one of: "
            f"{', '.join(VALID_DEV_TYPES)}",
        )


def set_task_dev_type(
    repo_root: Path,
    task_dir: Path,
    dev_type: str,
    *,
    repository: TaskRepository | None = None,
) -> dict:
    """Backfill `dev_type` on a task that has not started yet.

    Only a planning task is writable: a started task's dev_type belongs to
    the change already under way, and rewriting it would silently swap the
    reading list a reviewer worked against.
    """
    task_dir = Path(task_dir)
    _validate_dev_type(dev_type, task_dir)
    repo = repository or TaskRepository(Path(repo_root))
    task_json = repo.task_json_path(task_dir)
    if not task_json.is_file():
        raise TaskCreationError(
            "TASK-CREATE-DEVTYPE-003",
            task_json,
            "task.json is missing; cannot set dev_type",
        )
    status = repo.load(task_dir).get("status")
    if status != "planning":
        raise TaskCreationError(
            "TASK-CREATE-DEVTYPE-002",
            task_json,
            "dev_type can only be set while the task is planning "
            f"(current status: {status})",
        )
    return repo.save(task_dir, {"dev_type": dev_type})

