#!/usr/bin/env python3
"""Transactional runtime-context application service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from infra.storage.state_store import StateStore, StateStoreError
from infra.storage.unit_of_work import (
    FaultInjector,
    UnitOfWork,
    UnitOfWorkError,
)
from runtime.session_state import (
    FIELD_ACTIVE_TASK_PATH,
    FIELD_RUNTIME_CONTEXT_ID,
    FIELD_SCOPE,
    SCOPE_SUBAGENT,
    logical_subagent_context_key,
    platform_from_context_key,
    resolve_context_key,
    resolve_host_context_key,
    runtime_context_path,
    sessions_dir,
)


class RuntimeContextError(RuntimeError):
    """Raised when runtime-context state cannot be read or changed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class RuntimeContextInitResult:
    """Files created for one runtime-context initialization."""

    context: dict
    logical_context_key: str


class RuntimeContextService:
    """Coordinate runtime-context and session state through one UoW."""

    def __init__(
        self,
        repo_root: Path,
        *,
        state_store: StateStore | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.state_store = state_store or StateStore()
        self.fault_injector = fault_injector

    def recover(self) -> tuple[str, ...]:
        try:
            return UnitOfWork.recover_all(
                self.repo_root,
                state_store=self.state_store,
            )
        except (StateStoreError, UnitOfWorkError) as error:
            raise RuntimeContextError(
                "RUNTIME-RECOVERY-001",
                error.detail,
            ) from error

    def load(self, runtime_context_id: str) -> dict:
        self.recover()
        snapshot = self._load(runtime_context_id)
        return snapshot.data if snapshot.exists else {}

    def initialize(
        self,
        runtime_context_id: str,
        context: dict,
    ) -> RuntimeContextInitResult:
        self.recover()
        context_path = runtime_context_path(
            self.repo_root,
            runtime_context_id,
        )
        logical_context_key = logical_subagent_context_key(
            runtime_context_id
        )
        logical_path = self._session_path(logical_context_key)
        context_snapshot = self._load_path(context_path)
        logical_snapshot = self._load_path(logical_path)

        if context_snapshot.exists and context_snapshot.data != context:
            raise RuntimeContextError(
                "RUNTIME-INIT-001",
                f"runtime context already exists: {runtime_context_id}",
            )
        if context_snapshot.exists and logical_snapshot.exists:
            return RuntimeContextInitResult(
                context=context_snapshot.data,
                logical_context_key=logical_context_key,
            )

        unit = self._unit(
            self._operation_id("init", runtime_context_id),
            "runtime-context-init",
        )
        unit.replace(context_path, context)
        unit.replace(
            logical_path,
            self._logical_session(runtime_context_id, context),
        )
        self._commit(unit)
        return RuntimeContextInitResult(
            context=dict(context),
            logical_context_key=logical_context_key,
        )

    def update(
        self,
        runtime_context_id: str,
        *,
        status: str,
        note: str | None = None,
    ) -> dict | None:
        self.recover()
        path = runtime_context_path(self.repo_root, runtime_context_id)
        snapshot = self._load_path(path)
        if not snapshot.exists:
            return None
        context = dict(snapshot.data)
        context["status"] = status
        context["updated_at"] = self._now()
        if note:
            context["note"] = note
        operation_id = self._operation_id(
            "update",
            runtime_context_id,
            status,
            str(snapshot.revision),
        )
        try:
            self.state_store.replace(
                path,
                context,
                expected_revision=snapshot.revision,
                operation_id=operation_id,
            )
        except StateStoreError as error:
            raise RuntimeContextError(
                "RUNTIME-UPDATE-001",
                error.detail,
            ) from error
        return context

    def bind(
        self,
        runtime_context_id: str,
        host_context_key: str,
    ) -> dict | None:
        self.recover()
        context_path = runtime_context_path(
            self.repo_root,
            runtime_context_id,
        )
        snapshot = self._load_path(context_path)
        if not snapshot.exists:
            return None
        context = dict(snapshot.data)
        if context.get(FIELD_SCOPE) != SCOPE_SUBAGENT:
            return None
        if context.get("status") == "closed":
            return None

        existing_key = context.get("bound_context_key")
        if (
            isinstance(existing_key, str)
            and existing_key.strip()
            and existing_key != host_context_key
        ):
            raise RuntimeContextError(
                "RUNTIME-BIND-001",
                "runtime context "
                f"{runtime_context_id} already bound to {existing_key}",
            )
        if existing_key == host_context_key and context.get("status") == "bound":
            return context

        now = self._now()
        session = {
            "schema_version": 2,
            FIELD_SCOPE: SCOPE_SUBAGENT,
            FIELD_RUNTIME_CONTEXT_ID: runtime_context_id,
            "platform": platform_from_context_key(host_context_key),
            "status": "bound",
            "last_seen_at": now,
        }
        task_path = context.get("task_dir")
        if isinstance(task_path, str) and task_path.strip():
            session[FIELD_ACTIVE_TASK_PATH] = task_path.strip()

        updated = dict(context)
        updated["status"] = "bound"
        updated["bound_context_key"] = host_context_key
        if not updated.get("bound_at"):
            updated["bound_at"] = now
        updated["last_seen_at"] = now

        unit = self._unit(
            self._operation_id(
                "bind",
                runtime_context_id,
                host_context_key,
            ),
            "runtime-context-bind",
        )
        unit.replace(self._session_path(host_context_key), session)
        unit.replace(context_path, updated)
        self._commit(unit)
        return updated

    def close(self, runtime_context_id: str) -> bool:
        self.recover()
        context_path = runtime_context_path(
            self.repo_root,
            runtime_context_id,
        )
        snapshot = self._load_path(context_path)
        if not snapshot.exists:
            return False
        context = dict(snapshot.data)
        if context.get("status") == "closed":
            return True

        bound_context_key = context.get("bound_context_key")
        updated = dict(context)
        updated["status"] = "closed"
        updated["closed_at"] = self._now()
        updated["last_seen_at"] = updated["closed_at"]

        unit = self._unit(
            self._operation_id(
                "close",
                runtime_context_id,
                str(bound_context_key or ""),
            ),
            "runtime-context-close",
        )
        deleted_paths: set[Path] = set()
        if isinstance(bound_context_key, str) and bound_context_key.strip():
            bound_path = self._session_path(bound_context_key)
            unit.delete(bound_path)
            deleted_paths.add(bound_path)
        logical_path = self._session_path(
            logical_subagent_context_key(runtime_context_id)
        )
        if logical_path not in deleted_paths:
            unit.delete(logical_path)
        unit.replace(context_path, updated)
        self._commit(unit)
        return True

    def replace(self, runtime_context_id: str, context: dict) -> dict:
        self.recover()
        path = runtime_context_path(self.repo_root, runtime_context_id)
        snapshot = self._load_path(path)
        operation_id = self._operation_id(
            "replace",
            runtime_context_id,
            str(snapshot.revision),
        )
        try:
            self.state_store.replace(
                path,
                context,
                expected_revision=snapshot.revision,
                operation_id=operation_id,
            )
        except StateStoreError as error:
            raise RuntimeContextError(
                "RUNTIME-SAVE-001",
                error.detail,
            ) from error
        return dict(context)

    def _load(self, runtime_context_id: str):
        return self._load_path(
            runtime_context_path(self.repo_root, runtime_context_id)
        )

    def _load_path(self, path: Path):
        try:
            return self.state_store.load(path, missing_ok=True)
        except StateStoreError as error:
            raise RuntimeContextError(
                "RUNTIME-LOAD-001",
                error.detail,
            ) from error

    def _unit(self, operation_id: str, kind: str) -> UnitOfWork:
        return UnitOfWork(
            self.repo_root,
            operation_id=operation_id,
            kind=kind,
            state_store=self.state_store,
            fault_injector=self.fault_injector,
        )

    @staticmethod
    def _commit(unit: UnitOfWork) -> None:
        try:
            unit.commit()
        except UnitOfWorkError as error:
            raise RuntimeContextError(
                "RUNTIME-UOW-001",
                error.detail,
            ) from error

    def _session_path(self, context_key: str) -> Path:
        return sessions_dir(self.repo_root) / f"{context_key}.json"

    def _logical_session(
        self,
        runtime_context_id: str,
        context: dict,
    ) -> dict:
        session: dict[str, object] = {
            "schema_version": 2,
            FIELD_SCOPE: SCOPE_SUBAGENT,
            FIELD_RUNTIME_CONTEXT_ID: runtime_context_id,
            "platform": str(context.get("host") or "manual"),
            "status": "pending_bind",
            "last_seen_at": self._now(),
        }
        task_path = context.get("task_dir")
        if isinstance(task_path, str) and task_path.strip():
            session[FIELD_ACTIVE_TASK_PATH] = task_path.strip()
        return session

    @staticmethod
    def _operation_id(kind: str, *parts: str) -> str:
        identity = "|".join(parts)
        digest = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]
        return f"runtime-{kind}-{digest}"

    @staticmethod
    def _now() -> str:
        return (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

def read_runtime_context(repo_root: Path, runtime_context_id: str) -> dict:
    return RuntimeContextService(repo_root).load(runtime_context_id)


def write_runtime_context(repo_root: Path, runtime_context_id: str, data: dict) -> None:
    RuntimeContextService(repo_root).replace(runtime_context_id, data)


def bind_runtime_context(
    repo_root: Path,
    runtime_context_id: str,
    host_context_key: str | None = None,
    values: dict[str, object] | None = None,
) -> dict | None:
    resolved_key = (
        host_context_key
        if host_context_key
        else resolve_host_context_key(values) or resolve_context_key(values)
    )
    if not resolved_key:
        return None
    try:
        return RuntimeContextService(repo_root).bind(
            runtime_context_id,
            resolved_key,
        )
    except RuntimeContextError:
        return None


def close_runtime_context(repo_root: Path, runtime_context_id: str) -> bool:
    return RuntimeContextService(repo_root).close(runtime_context_id)
