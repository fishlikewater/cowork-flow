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
        allow_spec_file_modifications: bool = False,
    ) -> LifecycleResult:
        return self.execute(
            COMPLETE_STAGE,
            task,
            completed_at=completed_at,
            allow_spec_file_modifications=allow_spec_file_modifications,
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
        prepared = self._prepare_transition(stage, task_dir, preflight)
        if isinstance(prepared, LifecycleResult):
            return prepared
        task_data, already_at_target = prepared

        gated = self._run_validated_gate(
            stage,
            task_dir,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
        if isinstance(gated, LifecycleResult):
            return gated
        gate_result, summary = gated

        if already_at_target:
            return self._validated_idempotent_result(
                stage,
                task_dir,
                gate_result,
                summary,
            )

        return self._persist_transition_result(
            stage,
            task_dir,
            task_data,
            gate_result,
            summary,
            completed_at,
        )

    def _prepare_transition(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        preflight: Preflight | None,
    ) -> tuple[dict, bool] | LifecycleResult:
        task_data_or_failure = self._load_transition_task(stage, task_dir)
        if isinstance(task_data_or_failure, LifecycleResult):
            return task_data_or_failure
        task_data = task_data_or_failure

        already_at_target = task_data.get("status") == stage.target_status
        idempotent = self._early_idempotent_result(
            stage,
            task_dir,
            already_at_target,
        )
        if idempotent is not None:
            return idempotent

        preflight_failure = self._run_preflight(stage, task_dir, preflight)
        if preflight_failure is not None:
            return preflight_failure

        transition_failure = self._validate_transition(stage, task_dir, task_data)
        if transition_failure is not None:
            return transition_failure
        return task_data, already_at_target

    def _run_validated_gate(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        *,
        allow_spec_file_modifications: bool,
    ) -> tuple[object, str] | LifecycleResult:
        gate_result_or_failure = self._run_stage_gate(
            stage,
            task_dir,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
        if isinstance(gate_result_or_failure, LifecycleResult):
            return gate_result_or_failure
        gate_result = gate_result_or_failure
        return gate_result, self._stage_summary(stage, task_dir)

    def _validated_idempotent_result(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        gate_result: object,
        summary: str,
    ) -> LifecycleResult:
        return LifecycleResult(
            ok=True,
            code="LIFECYCLE-IDEMPOTENT-VALIDATED",
            stage=stage,
            task_dir=task_dir,
            gate_result=gate_result,
            summary=summary,
        )

    def _persist_transition_result(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
        gate_result: object,
        summary: str,
        completed_at: str | None,
    ) -> LifecycleResult:
        session_state_or_failure = self._build_session_state(
            stage,
            task_dir,
            gate_result,
            summary,
        )
        if isinstance(session_state_or_failure, LifecycleResult):
            return session_state_or_failure
        session_state, active_task_path = session_state_or_failure

        commit_failure = self._commit_transition(
            stage,
            task_dir,
            task_data,
            self._persisted_task_data(stage, task_data, completed_at),
            session_state,
            gate_result,
            summary,
        )
        if commit_failure is not None:
            return commit_failure

        return LifecycleResult(
            ok=True,
            code="LIFECYCLE-OK",
            stage=stage,
            task_dir=task_dir,
            gate_result=gate_result,
            summary=summary,
            active_task_path=active_task_path,
        )

    def _load_transition_task(
        self,
        stage: LifecycleStage,
        task_dir: Path,
    ) -> dict | LifecycleResult:
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
            return self.repository.load(task_dir)
        except TaskRepositoryError as error:
            return self._repository_failure(stage, task_dir, error)

    def _early_idempotent_result(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        already_at_target: bool,
    ) -> LifecycleResult | None:
        if not already_at_target or stage.name != START_STAGE.name:
            return None
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

    def _run_preflight(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        preflight: Preflight | None,
    ) -> LifecycleResult | None:
        if preflight is None:
            return None
        failure = preflight(task_dir)
        if failure is None:
            return None
        return self._failure(
            stage,
            task_dir,
            failure.code,
            title=failure.title,
            blockers=failure.blockers,
            hint=failure.hint,
        )

    def _validate_transition(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
    ) -> LifecycleResult | None:
        blockers = transition_blockers(
            task_data.get("status"),
            stage.target_status,
        )
        if not blockers:
            return None
        return self._failure(
            stage,
            task_dir,
            "LIFECYCLE-TRANSITION-001",
            blockers=tuple(blockers),
        )

    def _run_stage_gate(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        *,
        allow_spec_file_modifications: bool,
    ) -> object | LifecycleResult:
        gate_result = self.gate_runner.run(
            stage.gate_scope,
            task_dir,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
        if not gate_result.blocked:
            return gate_result
        return self._failure(
            stage,
            task_dir,
            "LIFECYCLE-GATE-001",
            gate_result=gate_result,
        )

    def _stage_summary(self, stage: LifecycleStage, task_dir: Path) -> str:
        if not stage.includes_coding_summary:
            return ""
        return self.gate_runner.coding_standards_summary(task_dir)

    def _build_session_state(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        gate_result: object,
        summary: str,
    ) -> tuple[object | None, str | None] | LifecycleResult:
        if not stage.activates_session:
            return None, None
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
        return session_state, session_state[2].task_path

    def _persisted_task_data(
        self,
        stage: LifecycleStage,
        task_data: dict,
        completed_at: str | None,
    ) -> dict:
        persisted = dict(task_data)
        persisted["status"] = stage.target_status
        if stage.records_completion_date:
            persisted["completedAt"] = (
                completed_at or datetime.now().strftime("%Y-%m-%d")
            )
        return persisted

    def _commit_transition(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
        persisted: dict,
        session_state: object | None,
        gate_result: object,
        summary: str,
    ) -> LifecycleResult | None:
        operation_id = self._operation_id(stage, task_dir, task_data)
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
        return None

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
