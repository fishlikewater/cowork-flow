#!/usr/bin/env python3
"""Task lifecycle application service."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from common.gates.gates import GateRunner
from common.storage.unit_of_work import (
    FaultInjector,
    UnitOfWork,
    UnitOfWorkError,
)
from common.task.active_task import build_active_task_session
from common.task.state_machine import transition_blockers
from common.task.task_repository import TaskRepository, TaskRepositoryError


@dataclass(frozen=True)
class LifecycleStage:
    """Immutable behavior differences between lifecycle stages."""

    name: str
    target_status: str
    gate_scope: str
    activates_session: bool = False
    records_completion_date: bool = False
    includes_coding_summary: bool = False


START_STAGE = LifecycleStage(
    name="start",
    target_status="in_progress",
    gate_scope="task_start",
    activates_session=True,
)
REVIEW_STAGE = LifecycleStage(
    name="review",
    target_status="review",
    gate_scope="task_review",
    includes_coding_summary=True,
)
COMPLETE_STAGE = LifecycleStage(
    name="complete",
    target_status="completed",
    gate_scope="task_complete",
    records_completion_date=True,
)


@dataclass(frozen=True)
class LifecyclePreflightFailure:
    """Structured stage-specific preflight failure."""

    code: str
    title: str
    blockers: tuple[str, ...]
    hint: str = ""


@dataclass(frozen=True)
class LifecycleResult:
    """Structured lifecycle outcome for delivery-layer rendering."""

    ok: bool
    code: str
    stage: LifecycleStage
    task_dir: Path
    blockers: tuple[str, ...] = ()
    title: str = ""
    hint: str = ""
    gate_result: object | None = None
    summary: str = ""
    active_task_path: str | None = None
    repository_error: TaskRepositoryError | None = None


Preflight = Callable[[Path], Optional[LifecyclePreflightFailure]]


class TaskLifecycleService:
    """Run lifecycle stages through one fail-closed execution pipeline."""

    def __init__(
        self,
        repo_root: Path,
        *,
        repository: TaskRepository | None = None,
        gate_runner: GateRunner | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.repository = repository or TaskRepository(self.repo_root)
        self.gate_runner = gate_runner or GateRunner(self.repo_root)
        self.fault_injector = fault_injector

    def start(
        self,
        task: str | Path,
        *,
        preflight: Preflight | None = None,
    ) -> LifecycleResult:
        return self.execute(START_STAGE, task, preflight=preflight)

    def review(
        self,
        task: str | Path,
        *,
        allow_spec_file_modifications: bool = False,
    ) -> LifecycleResult:
        return self.execute(
            REVIEW_STAGE,
            task,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )

    def complete(
        self,
        task: str | Path,
        *,
        completed_at: str | None = None,
    ) -> LifecycleResult:
        return self.execute(
            COMPLETE_STAGE,
            task,
            completed_at=completed_at,
        )

    def execute(
        self,
        stage: LifecycleStage,
        task: str | Path,
        *,
        preflight: Preflight | None = None,
        allow_spec_file_modifications: bool = False,
        completed_at: str | None = None,
    ) -> LifecycleResult:
        """Resolve, preflight, validate, gate, and persist one transition."""
        task_dir = self.repository.resolve(task)
        if not task_dir.is_dir():
            return self._failure(
                stage,
                task_dir,
                "LIFECYCLE-TASK-001",
                title="Task not found",
            )

        try:
            UnitOfWork.recover_all(self.repo_root)
        except UnitOfWorkError as error:
            return self._failure(
                stage,
                task_dir,
                "LIFECYCLE-RECOVERY-001",
                title=error.detail,
            )

        try:
            task_data = self.repository.load(task_dir)
        except TaskRepositoryError as error:
            return self._repository_failure(stage, task_dir, error)

        already_at_target = task_data.get("status") == stage.target_status
        if already_at_target and stage.name != REVIEW_STAGE.name:
            return LifecycleResult(
                ok=True,
                code="LIFECYCLE-IDEMPOTENT",
                stage=stage,
                task_dir=task_dir,
                active_task_path=(
                    self._display_task_path(task_dir)
                    if stage.activates_session
                    else None
                ),
            )

        if preflight is not None:
            failure = preflight(task_dir)
            if failure is not None:
                return self._failure(
                    stage,
                    task_dir,
                    failure.code,
                    title=failure.title,
                    blockers=failure.blockers,
                    hint=failure.hint,
                )

        blockers = transition_blockers(
            task_data.get("status"),
            stage.target_status,
        )
        if blockers:
            return self._failure(
                stage,
                task_dir,
                "LIFECYCLE-TRANSITION-001",
                blockers=tuple(blockers),
            )

        gate_result = self.gate_runner.run(
            stage.gate_scope,
            task_dir,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
        if gate_result.blocked:
            return self._failure(
                stage,
                task_dir,
                "LIFECYCLE-GATE-001",
                gate_result=gate_result,
            )

        summary = ""
        if stage.includes_coding_summary:
            summary = self.gate_runner.coding_standards_summary(task_dir)

        if already_at_target:
            return LifecycleResult(
                ok=True,
                code="LIFECYCLE-IDEMPOTENT-VALIDATED",
                stage=stage,
                task_dir=task_dir,
                gate_result=gate_result,
                summary=summary,
            )

        active_task_path = None
        session_state = None
        if stage.activates_session:
            active_task_path = self._display_task_path(task_dir)
            session_state = build_active_task_session(
                self.repo_root,
                active_task_path,
            )
            if session_state is None:
                return self._failure(
                    stage,
                    task_dir,
                    "LIFECYCLE-CONTEXT-001",
                    gate_result=gate_result,
                    summary=summary,
                )
            active_task_path = session_state[2].task_path

        persisted = dict(task_data)
        persisted["status"] = stage.target_status
        if stage.records_completion_date:
            persisted["completedAt"] = (
                completed_at or datetime.now().strftime("%Y-%m-%d")
            )

        operation_id = self._operation_id(
            stage,
            task_dir,
            task_data,
        )
        unit = UnitOfWork(
            self.repo_root,
            operation_id=operation_id,
            kind=f"task-lifecycle-{stage.name}",
            fault_injector=self.fault_injector,
        )
        if session_state is not None:
            unit.replace(session_state[0], session_state[1])
        unit.replace(
            self.repository.task_json_path(task_dir),
            persisted,
        )
        try:
            unit.commit()
        except UnitOfWorkError as error:
            return self._failure(
                stage,
                task_dir,
                "LIFECYCLE-UOW-001",
                title=error.detail,
                gate_result=gate_result,
                summary=summary,
            )

        return LifecycleResult(
            ok=True,
            code="LIFECYCLE-OK",
            stage=stage,
            task_dir=task_dir,
            gate_result=gate_result,
            summary=summary,
            active_task_path=active_task_path,
        )

    def _operation_id(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
    ) -> str:
        identity = "|".join(
            (
                str(task_dir.resolve()),
                str(task_data.get("createdAt") or ""),
                str(task_data.get("status") or ""),
                stage.target_status,
            )
        )
        digest = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]
        return f"task-{stage.name}-{digest}"

    def _display_task_path(self, task_dir: Path) -> str:
        try:
            return task_dir.resolve().relative_to(
                self.repo_root.resolve()
            ).as_posix()
        except ValueError:
            return str(task_dir)

    @staticmethod
    def _failure(
        stage: LifecycleStage,
        task_dir: Path,
        code: str,
        *,
        blockers: tuple[str, ...] = (),
        title: str = "",
        hint: str = "",
        gate_result: object | None = None,
        summary: str = "",
    ) -> LifecycleResult:
        return LifecycleResult(
            ok=False,
            code=code,
            stage=stage,
            task_dir=task_dir,
            blockers=blockers,
            title=title,
            hint=hint,
            gate_result=gate_result,
            summary=summary,
        )

    @staticmethod
    def _repository_failure(
        stage: LifecycleStage,
        task_dir: Path,
        error: TaskRepositoryError,
        *,
        gate_result: object | None = None,
        summary: str = "",
    ) -> LifecycleResult:
        return LifecycleResult(
            ok=False,
            code=error.code,
            stage=stage,
            task_dir=task_dir,
            gate_result=gate_result,
            summary=summary,
            repository_error=error,
        )
