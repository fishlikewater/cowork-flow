#!/usr/bin/env python3
"""Task lifecycle application service."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from infra.paths import DIR_WORKFLOW
from infra.storage.unit_of_work import (
    FaultInjector,
    UnitOfWork,
    UnitOfWorkError,
)
from runtime.session_state import build_active_task_session
from infra.git_snapshot import current_head
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
        executor: str | None = None,
        takeover: bool = False,
    ) -> LifecycleResult:
        return self.execute(
            START_STAGE,
            task,
            preflight=preflight,
            executor=executor,
            takeover=takeover,
        )

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
        executor: str | None = None,
        takeover: bool = False,
    ) -> LifecycleResult:
        """Resolve, preflight, validate, check, and persist one transition."""
        task_dir = self.repository.resolve(task)
        execution_policy = resolve_execution_policy(
            self.repo_root,
            execution_context,
            allow_spec_file_modifications=allow_spec_file_modifications,
        )
        prepared = self._prepare_transition(
            stage, task_dir, preflight, executor=executor, takeover=takeover
        )
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

        executor_failure = self._check_executor(
            stage,
            task_dir,
            task_data,
            executor,
            takeover,
        )
        if executor_failure is not None:
            return executor_failure

        if already_at_target:
            takeover_result = self._apply_takeover_on_idempotent(
                stage,
                task_dir,
                task_data,
                executor,
                takeover,
            )
            if takeover_result is not None:
                return takeover_result
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
            executor=executor,
        )

    def _prepare_transition(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        preflight: Preflight | None,
        executor: str | None = None,
        takeover: bool = False,
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
            task_data=task_data,
            executor=executor,
            takeover=takeover,
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
        executor: str | None = None,
    ) -> LifecycleResult:
        explicit_executor = bool(executor and executor.strip())
        resolved_executor = (
            self._resolve_executor(executor) if stage.activates_session else None
        )
        session_state_or_failure = self._build_session_state(
            stage,
            task_dir,
            check_result,
            transition,
            executor_provided=explicit_executor,
        )
        if isinstance(session_state_or_failure, LifecycleResult):
            return session_state_or_failure
        session_state, active_task_path = session_state_or_failure

        commit_failure = self._commit_transition(
            stage,
            task_dir,
            task_data,
            self._persisted_task_data(
                stage, task_data, completed_at, executor=resolved_executor
            ),
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
        task_data: dict | None = None,
        executor: str | None = None,
        takeover: bool = False,
    ) -> LifecycleResult | None:
        if not already_at_target or stage.name != START_STAGE.name:
            return None
        # Executor gate runs before the idempotent shortcut: a foreign
        # session re-running start on an active task must not ride through
        # as a no-op success (stage 2 ownership semantics).
        current = task_data.get("executor") if isinstance(task_data, dict) else None
        current = (
            current.strip()
            if isinstance(current, str) and current.strip()
            else None
        )
        if stage.activates_session and current is not None:
            resolved = self._resolve_executor(executor)
            if resolved is None or resolved != current:
                if takeover and resolved is not None:
                    return self._apply_takeover_on_idempotent(
                        stage, task_dir, task_data, executor, takeover
                    )
                return self._failure(
                    stage,
                    task_dir,
                    "LIFECYCLE-EXECUTOR-001",
                    title=f"task is owned by executor '{current}'",
                    blockers=(
                        f"task is owned by executor '{current}', not "
                        f"'{resolved or '<no-identity>'}'; re-run with "
                        "--takeover to take over, or --executor <label> to "
                        "identify yourself",
                    ),
                )
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
        *,
        executor_provided: bool = False,
    ) -> tuple[object | None, str | None] | LifecycleResult:
        if not stage.activates_session:
            return None, None
        if executor_provided:
            # Sessionless (CI / headless) start: ownership is recorded via
            # the explicit executor; no host session file is bound.
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
        executor: str | None = None,
    ) -> dict:
        persisted = dict(task_data)
        persisted["status"] = stage.target_status
        if stage.records_completion_date:
            persisted["completedAt"] = (
                completed_at or datetime.now().strftime("%Y-%m-%d")
            )
        if stage.activates_session and executor:
            persisted["executor"] = executor
        if stage.activates_session:
            # Record the git baseline once: review merges baseline..HEAD with
            # the working tree, so committing mid-task can no longer hide
            # unlisted files. Already-present baselines are never overwritten
            # (repeated/covered starts must not shrink the review window).
            meta = dict(persisted.get("meta") or {})
            if not meta.get("baselineCommit"):
                head = current_head(self.repo_root)
                if head:
                    meta["baselineCommit"] = head
                    persisted["meta"] = meta
        return persisted

    def _resolve_executor(self, executor: str | None) -> str | None:
        """Explicit executor wins; otherwise fall back to the ambient
        session identity from the environment."""
        if executor and executor.strip():
            return executor.strip()
        try:
            from runtime.session_state import resolve_context_key

            key = resolve_context_key({})
        except Exception:
            return None
        return key or None

    def _apply_takeover_on_idempotent(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
        executor: str | None,
        takeover: bool,
    ) -> LifecycleResult | None:
        """Reassign ownership when an already-active task is taken over; a
        plain idempotent start performs no write."""
        if not stage.activates_session or not takeover:
            return None
        current = task_data.get("executor")
        if not isinstance(current, str) or not current.strip():
            return None
        resolved = self._resolve_executor(executor)
        if resolved is None or resolved == current.strip():
            return None
        persisted = dict(task_data)
        persisted["executor"] = resolved
        identity = (
            str(task_dir.resolve()),
            str(task_data.get("createdAt") or ""),
            resolved,
        )
        digest = hashlib.sha256("|".join(identity).encode("utf-8")).hexdigest()[:16]
        unit = UnitOfWork(
            self.repo_root,
            operation_id=f"task-{stage.name}-takeover-{digest}",
            kind=f"task-lifecycle-{stage.name}-takeover",
            fault_injector=self.fault_injector,
        )
        unit.replace(self.repository.task_json_path(task_dir), persisted)
        try:
            unit.commit()
        except UnitOfWorkError as error:
            return self._failure(
                stage,
                task_dir,
                "LIFECYCLE-UOW-001",
                title=error.detail,
            )
        return LifecycleResult(
            ok=True,
            code="LIFECYCLE-EXECUTOR-TAKEN-OVER",
            stage=stage,
            task_dir=task_dir,
            transition=LifecycleTransition(
                previous_status=task_data.get("status"),
                next_status=task_data.get("status"),
                changed=False,
            ),
            active_task_path=self._display_task_path(task_dir),
            emitted_events=self._success_events(stage),
        )

    def _check_executor(
        self,
        stage: LifecycleStage,
        task_dir: Path,
        task_data: dict,
        executor: str | None,
        takeover: bool,
    ) -> LifecycleResult | None:
        """Fail-closed ownership gate on the start activation point (stage 2
        multi-executor semantics). A task already owned by another executor
        needs an explicit takeover; review/complete stay session-free."""
        if not stage.activates_session:
            return None
        current = task_data.get("executor")
        if not isinstance(current, str) or not current.strip():
            return None
        current = current.strip()
        resolved = self._resolve_executor(executor)
        if resolved is not None and resolved == current:
            return None
        if takeover:
            return None
        return self._failure(
            stage,
            task_dir,
            "LIFECYCLE-EXECUTOR-001",
            title=f"task is owned by executor '{current}'",
            blockers=(
                f"task is owned by executor '{current}', not '{resolved or '<no-identity>'}'; "
                "re-run with --takeover to take over, or --executor <label> to identify yourself",
            ),
        )

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
        unit.replace(
            self.repo_root
            / DIR_WORKFLOW
            / ".runtime"
            / "state-snapshot.json",
            self._state_snapshot(stage, task_dir),
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

    def _state_snapshot(self, stage: LifecycleStage, task_dir: Path) -> dict:
        """Host-hook breadcrumb facts recorded atomically with the transition.

        breadcrumbKey intentionally equals target_status today: every current
        stage maps one status to one breadcrumb tag. The field exists so a
        future stage can diverge the two without changing hook consumers,
        which trust this key over their own status-derived convention.
        """
        return {
            "schemaVersion": 1,
            "generatedAt": (
                datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "activeTaskPath": self._display_task_path(task_dir),
            "status": stage.target_status,
            "breadcrumbKey": stage.target_status,
        }

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
