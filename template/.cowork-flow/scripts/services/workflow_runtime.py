#!/usr/bin/env python3
"""Transactional runtime-context application service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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
    iter_subagent_contexts,
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


def normalize_relative_path(path: str) -> str:
    """Repository-relative form used to compare ownership claims."""
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def slice_paths_overlap(left: str, right: str) -> bool:
    """True when two owned paths are equal or one contains the other."""
    a = normalize_relative_path(left)
    b = normalize_relative_path(right)
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def owned_paths_overlap(
    left: tuple[str, ...] | list[str],
    right: tuple[str, ...] | list[str],
) -> list[tuple[str, str]]:
    """Every overlapping (left, right) pair of owned-path claims."""
    overlaps: list[tuple[str, str]] = []
    for a in left:
        if not isinstance(a, str):
            continue
        for b in right:
            if isinstance(b, str) and slice_paths_overlap(a, b):
                overlaps.append((a, b))
    return overlaps


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

        conflicts = self.slice_conflicts(runtime_context_id, context)
        if conflicts:
            raise RuntimeContextError(
                "SUBAGENT-SLICE-001",
                "owned_paths overlap an open implement context of this task: "
                + "; ".join(
                    f"{other_id} owns {other_path}, overlaps {claimed_path}"
                    for other_id, claimed_path, other_path in conflicts
                ),
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

    def slice_conflicts(
        self,
        runtime_context_id: str,
        context: dict,
    ) -> list[tuple[str, str, str]]:
        """(other_id, claimed_path, conflicting_path) for open sibling slices.

        Only implement contexts that declare `owned_paths` take part: an
        init without an ownership claim can neither conflict nor be
        conflicted with, and a closed context has released its paths.
        """
        if context.get("agent_type") != "cowork-implement":
            return []
        claimed = self._owned_paths(context)
        if not claimed:
            return []
        task_dir = self._normalized_task_dir(str(context.get("task_dir") or ""))
        if not task_dir:
            return []
        conflicts: list[tuple[str, str, str]] = []
        for other in iter_subagent_contexts(self.repo_root):
            other_id = str(other.get("runtime_context_id") or "")
            if not other_id or other_id == runtime_context_id:
                continue
            if other.get("agent_type") != "cowork-implement":
                continue
            if other.get("status") == "closed":
                continue
            if self._normalized_task_dir(str(other.get("task_dir") or "")) != task_dir:
                continue
            for claimed_path, other_path in owned_paths_overlap(
                claimed,
                self._owned_paths(other),
            ):
                conflicts.append((other_id, claimed_path, other_path))
        return conflicts

    @staticmethod
    def _task_dir_is_absolute(value: str) -> bool:
        """Decide on the raw value, before any slash stripping.

        Stripping first would turn a slash-rooted POSIX path into a
        relative-looking one and silently disable the same-task comparison.
        """
        raw = value.strip().replace("\\", "/")
        if raw.startswith("/"):
            return True
        return Path(raw).is_absolute()

    def _normalized_task_dir(self, value: str) -> str:
        """One task, one key: `--execution-task-dir` may arrive absolute."""
        raw = value.strip().replace("\\", "/")
        if self._task_dir_is_absolute(raw):
            try:
                return normalize_relative_path(
                    str(
                        Path(raw)
                        .resolve()
                        .relative_to(self.repo_root.resolve())
                    )
                )
            except ValueError:
                return normalize_relative_path(raw)
        return normalize_relative_path(raw)

    @staticmethod
    def _owned_paths(context: dict) -> list[str]:
        assignment = context.get("assignment")
        owned = (
            assignment.get("owned_paths")
            if isinstance(assignment, dict)
            else None
        )
        if not isinstance(owned, list):
            return []
        return [path for path in owned if isinstance(path, str) and path.strip()]

    def list_contexts(
        self,
        *,
        task_dir: str | None = None,
        open_only: bool = False,
    ) -> list[dict]:
        """Subagent runtime contexts for inventory views (read-only)."""
        wanted = self._normalized_task_dir(task_dir) if task_dir else None
        contexts: list[dict] = []
        for context in iter_subagent_contexts(self.repo_root):
            if open_only and context.get("status") == "closed":
                continue
            if wanted is not None and self._normalized_task_dir(
                str(context.get("task_dir") or "")
            ) != wanted:
                continue
            contexts.append(context)
        return contexts

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

    def evidence(
        self,
        runtime_context_id: str,
        *,
        note: str,
        artifact: str | None = None,
    ) -> dict | None:
        """Append an evidence entry to the runtime context (stage 2: the
        evidence rail advances independently of the task status machine).
        CAS-protected; allowed on closed contexts so late findings can be
        recorded."""
        self.recover()
        path = runtime_context_path(self.repo_root, runtime_context_id)
        snapshot = self._load_path(path)
        if not snapshot.exists:
            return None
        context = dict(snapshot.data)
        entries = context.get("evidence")
        entries = list(entries) if isinstance(entries, list) else []
        entry: dict = {"note": note, "at": self._now()}
        if artifact and artifact.strip():
            entry["artifact"] = artifact.strip()
        entries.append(entry)
        context["evidence"] = entries
        context["updated_at"] = self._now()
        operation_id = self._operation_id(
            "evidence",
            runtime_context_id,
            str(snapshot.revision),
            str(len(entries)),
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
                "RUNTIME-EVIDENCE-001",
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
        if self._bind_holds(context, host_context_key):
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
        bound_context_key = context.get("bound_context_key")

        session_paths: list[Path] = []
        if isinstance(bound_context_key, str) and bound_context_key.strip():
            session_paths.append(self._session_path(bound_context_key))
        logical_path = self._session_path(
            logical_subagent_context_key(runtime_context_id)
        )
        if logical_path not in session_paths:
            session_paths.append(logical_path)

        # A repeated close is a no-op only once its writes hold:
        # session files restored by hand (or a manual rollback)
        # still need removing.
        if context.get("status") == "closed" and not any(
            path.is_file() for path in session_paths
        ):
            return True

        updated = dict(context)
        if context.get("status") != "closed":
            updated["status"] = "closed"
            updated["closed_at"] = self._now()
        updated["last_seen_at"] = updated.get("closed_at") or self._now()

        unit = self._unit(
            self._operation_id("close", runtime_context_id),
            "runtime-context-close",
        )
        for path in session_paths:
            unit.delete(path)
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

    def _bind_holds(self, context: dict, host_context_key: str) -> bool:
        """A repeat bind is a no-op only while both of its writes hold."""
        return (
            context.get("bound_context_key") == host_context_key
            and context.get("status") == "bound"
            and self._session_path(host_context_key).is_file()
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
        # A new attempt gets a new identity: recovery reads the
        # operation log, so reusing an id would let a manual
        # rollback inherit an older committed result (or fail as a
        # reused request) instead of rewriting the files.
        identity = "|".join((*parts, uuid4().hex))
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
