#!/usr/bin/env python3
"""Task lifecycle application service."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from infra.storage.unit_of_work import (
    FaultInjector,
    UnitOfWork,
    UnitOfWorkError,
)
from runtime.session_state import build_active_task_session
from services.lifecycle_checks import LifecycleCheckResult, LifecycleCheckRunner
from services.lifecycle_policy import (
    LifecycleExecutionPolicy,
    LifecyclePolicyFailure,
    resolve_execution_policy,
    start_readiness_failure,
)
from kernel.task_state import transition_blockers
from services.task_repository import TaskRepository, TaskRepositoryError


@dataclass(frozen=True)
class LifecycleStage:
    """Immutable behavior differences between lifecycle stages."""

    name: str
    target_status: str
    activates_session: bool = False
    records_completion_date: bool = False


START_STAGE = LifecycleStage(
    name="start",
    target_status="in_progress",
    activates_session=True,
)
REVIEW_STAGE = LifecycleStage(
    name="review",
    target_status="review",
)
COMPLETE_STAGE = LifecycleStage(
    name="complete",
    target_status="completed",
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
class LifecycleTransition:
    """Stable status transition facts for lifecycle results."""

    previous_status: str | None
    next_status: str
    changed: bool


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
    check_result: object | None = None
    active_task_path: str | None = None
    repository_error: TaskRepositoryError | None = None
    transition: LifecycleTransition | None = None
    execution_policy: LifecycleExecutionPolicy | None = None
    emitted_events: tuple[str, ...] = ()


Preflight = Callable[
    [Path],
    Optional[Union[LifecyclePreflightFailure, LifecyclePolicyFailure]],
]


class TaskLifecycleService:
    """Run lifecycle stages through one fail-closed execution pipeline."""

    def __init__(
        self,
        repo_root: Path,
        *,
        repository: TaskRepository | None = None,
        check_runner: LifecycleCheckRunner | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.repository = repository or TaskRepository(self.repo_root)
        self.check_runner = check_runner or LifecycleCheckRunner(self.repo_root)
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
        allow_spec_file_modifications: bool | None = None,
        execution_context: object | None = None,
    ) -> LifecycleResult:
        return self.execute(
            REVIEW_STAGE,
            task,
            allow_spec_file_modifications=allow_spec_file_modifications,
            execution_context=execution_context,
        )

    def complete(
        self,
        task: str | Path,
        *,
        completed_at: str | None = None,
        allow_spec_file_modifications: bool | None = None,
        execution_context: object | None = None,
    ) -> LifecycleResult:
        return self.execute(
            COMPLETE_STAGE,
            task,
            completed_at=completed_at,
            allow_spec_file_modifications=allow_spec_file_modifications,
            execution_context=execution_context,
        )

    def execute(
        self,
        stage: LifecycleStage,
        task: str | Path,
        *,
        preflight: Preflight | None = None,
        allow_spec_file_modifications: bool | None = None,
        completed_at: str | None = None,
        execution_context: object | None = None,
    ) -> LifecycleResult:
        """Resolve, preflight, validate, check, and persist one transition."""
        task_dir = self.repository.resolve(task)
        execution_policy = resolve_execution_policy(
            self.repo_root,
            execution_context,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
        prepared = self._prepare_transition(stage, task_dir, preflight)
        if isinstance(prepared, LifecycleResult):
            return prepared
        task_data, already_at_target, transition = prepared

        checked = self._run_stage_checks(
            stage,
            task_dir,
            transition=transition,
            execution_policy=execution_policy,
        )
        if isinstance(checked, LifecycleResult):
            return checked
        check_result = checked

        if already_at_target:
            return self._validated_idempotent_result(
                stage,
                task_dir,
                check_result,
                transition=transition,
                execution_policy=execution_policy,
            )

        return self._persist_transition_result(
            stage,
            task_dir,
            task_data,
            check_result,
            completed_at,
            transition=transition,
            execution_policy=execution_policy,
        )

    def _prepare_transition(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        preflight: Preflight | None,
    ) -> tuple[dict, bool, LifecycleTransition] | LifecycleResult:
        task_data_or_failure = self._load_transition_task(stage, task_dir)
        if isinstance(task_data_or_failure, LifecycleResult):
            return task_data_or_failure
        task_data = task_data_or_failure

        transition = self._transition_for(stage, task_data)
        already_at_target = not transition.changed
        idempotent = self._early_idempotent_result(
            stage,
            task_dir,
            already_at_target,
            transition,
        )
        if idempotent is not None:
            return idempotent

        preflight_failure = self._run_preflight(
            stage,
            task_dir,
            preflight,
            transition,
        )
        if preflight_failure is not None:
            return preflight_failure

        transition_failure = self._validate_transition(
            stage,
            task_dir,
            task_data,
            transition,
        )
        if transition_failure is not None:
            return transition_failure
        return task_data, already_at_target, transition

    def _validated_idempotent_result(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        check_result: object,
        *,
        transition: LifecycleTransition,
        execution_policy: LifecycleExecutionPolicy,
    ) -> LifecycleResult:
        return LifecycleResult(
            ok=True,
            code="LIFECYCLE-IDEMPOTENT-VALIDATED",
            stage=stage,
            task_dir=task_dir,
            check_result=check_result,
            transition=transition,
            execution_policy=execution_policy,
            emitted_events=self._success_events(stage),
        )

    def _persist_transition_result(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
        check_result: object,
        completed_at: str | None,
        *,
        transition: LifecycleTransition,
        execution_policy: LifecycleExecutionPolicy,
    ) -> LifecycleResult:
        session_state_or_failure = self._build_session_state(
            stage,
            task_dir,
            check_result,
            transition,
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
            check_result,
        )
        if commit_failure is not None:
            return commit_failure

        return LifecycleResult(
            ok=True,
            code="LIFECYCLE-OK",
            stage=stage,
            task_dir=task_dir,
            check_result=check_result,
            active_task_path=active_task_path,
            transition=transition,
            execution_policy=execution_policy,
            emitted_events=self._success_events(stage),
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
        transition: LifecycleTransition,
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
            transition=transition,
            emitted_events=self._success_events(stage),
        )

    def _run_preflight(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        preflight: Preflight | None,
        transition: LifecycleTransition,
    ) -> LifecycleResult | None:
        if preflight is None and stage.name == START_STAGE.name:
            failure = start_readiness_failure(self.repo_root, task_dir)
        elif preflight is None:
            failure = None
        else:
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
            transition=transition,
        )

    def _validate_transition(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
        transition: LifecycleTransition,
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
            transition=transition,
        )

    def _run_stage_checks(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        *,
        transition: LifecycleTransition,
        execution_policy: LifecycleExecutionPolicy,
    ) -> object | LifecycleResult:
        if stage.name == START_STAGE.name:
            check_result = LifecycleCheckResult(stage=stage.name)
        elif stage.name == REVIEW_STAGE.name:
            check_result = self.check_runner.review(
                task_dir,
                allow_spec_file_modifications=(
                    execution_policy.allow_spec_file_modifications
                ),
                execution_policy=execution_policy,
            )
        elif stage.name == COMPLETE_STAGE.name:
            check_result = self.check_runner.complete(
                task_dir,
                allow_spec_file_modifications=(
                    execution_policy.allow_spec_file_modifications
                ),
                execution_policy=execution_policy,
            )
        else:
            check_result = LifecycleCheckResult(
                stage=stage.name,
                blockers=(f"unsupported lifecycle stage: {stage.name}",),
            )
        if not check_result.blocked:
            return check_result
        return self._failure(
            stage,
            task_dir,
            "LIFECYCLE-CHECK-001",
            blockers=tuple(check_result.blockers),
            check_result=check_result,
            transition=transition,
            execution_policy=execution_policy,
        )

    def _build_session_state(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        check_result: object,
        transition: LifecycleTransition,
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
                check_result=check_result,
                transition=transition,
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
        check_result: object,
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
                check_result=check_result,
            )
        return None

    def start_readiness(self, task: str | Path) -> LifecycleResult:
        """Check start readiness without mutating task or session state."""
        task_dir = self.repository.resolve(task)
        task_data_or_failure = self._load_transition_task(START_STAGE, task_dir)
        transition = None
        if isinstance(task_data_or_failure, LifecycleResult):
            return task_data_or_failure
        transition = self._transition_for(START_STAGE, task_data_or_failure)
        failure = start_readiness_failure(self.repo_root, task_dir)
        if failure is not None:
            return self._failure(
                START_STAGE,
                task_dir,
                failure.code,
                title=failure.title,
                blockers=failure.blockers,
                hint=failure.hint,
                transition=transition,
            )
        return LifecycleResult(
            ok=True,
            code="TASK-READINESS-OK",
            stage=START_STAGE,
            task_dir=task_dir,
            transition=transition,
        )

    def _transition_for(
        self,
        stage: LifecycleStage,
        task_data: dict,
    ) -> LifecycleTransition:
        previous = task_data.get("status")
        previous_status = previous if isinstance(previous, str) else None
        return LifecycleTransition(
            previous_status=previous_status,
            next_status=stage.target_status,
            changed=previous_status != stage.target_status,
        )

    @staticmethod
    def _success_events(stage: LifecycleStage) -> tuple[str, ...]:
        if stage.name == START_STAGE.name:
            return ("after_start",)
        return ()

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
        check_result: object | None = None,
        transition: LifecycleTransition | None = None,
        execution_policy: LifecycleExecutionPolicy | None = None,
        emitted_events: tuple[str, ...] = (),
    ) -> LifecycleResult:
        return LifecycleResult(
            ok=False,
            code=code,
            stage=stage,
            task_dir=task_dir,
            blockers=blockers,
            title=title,
            hint=hint,
            check_result=check_result,
            transition=transition,
            execution_policy=execution_policy,
            emitted_events=emitted_events,
        )

    @staticmethod
    def _repository_failure(
        stage: LifecycleStage,
        task_dir: Path,
        error: TaskRepositoryError,
        *,
        check_result: object | None = None,
        transition: LifecycleTransition | None = None,
        execution_policy: LifecycleExecutionPolicy | None = None,
        emitted_events: tuple[str, ...] = (),
    ) -> LifecycleResult:
        return LifecycleResult(
            ok=False,
            code=error.code,
            stage=stage,
            task_dir=task_dir,
            check_result=check_result,
            repository_error=error,
        )
