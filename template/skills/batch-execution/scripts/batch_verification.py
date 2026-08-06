#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch Host-result verification separated from state advancement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from batch_state_machine import (
    LIFECYCLE_STATUSES,
    RUNTIME_ROLES,
    BatchExecutionError,
    runtime_for,
)

CommitVerifier = Callable[[str], bool]


def normalize_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Host action result and fail closed on malformed input."""

    if not isinstance(payload, dict):
        raise BatchExecutionError(
            "BATCH-RESULT-PAYLOAD-001",
            "Host action result must be a JSON object",
        )
    result = dict(payload)
    for key in ("action_id", "type", "outcome"):
        value = result.get(key)
        if not isinstance(value, str) or not value.strip():
            raise BatchExecutionError(
                "BATCH-RESULT-PAYLOAD-001",
                f"Host action result is missing {key}",
            )
        result[key] = value.strip()
    return result


def required_text(payload: dict[str, Any], key: str, detail: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BatchExecutionError("BATCH-RESULT-PAYLOAD-001", detail)
    return value.strip()


def optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class BatchActionVerifier:
    """Verify Host facts for one Batch action without advancing the state machine."""

    def __init__(
        self,
        repo_root: Path,
        runtime_contexts: Any,
        commit_verifier: CommitVerifier,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.runtime_contexts = runtime_contexts
        self.commit_verifier = commit_verifier

    def verify_success(
        self,
        state: dict[str, Any],
        action: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        action_type = str(action["type"])
        task_name = str(action["task"])
        if action_type == "archive_task":
            self.verify_archive_result(task_name, result)
            return
        if action_type in LIFECYCLE_STATUSES:
            self.verify_task_status(task_name, LIFECYCLE_STATUSES[action_type], result)
            return
        if action_type.startswith("init_"):
            self.verify_runtime_initialized(
                state,
                task_name,
                RUNTIME_ROLES[action_type],
                result,
            )
            return
        if action_type.startswith("await_"):
            self.verify_runtime_completed(
                state,
                task_name,
                RUNTIME_ROLES[action_type],
                action,
                result,
            )
            return
        if action_type == "commit_task":
            commit_id = required_text(result, "commit_id", "commit result is missing commit_id")
            if not self.commit_verifier(commit_id):
                raise BatchExecutionError(
                    "BATCH-COMMIT-VERIFY-001",
                    f"commit_id could not be verified: {commit_id}",
                )
            return
        raise BatchExecutionError(
            "BATCH-ACTION-UNKNOWN-001",
            f"unsupported Batch action: {action_type}",
        )

    def verify_task_status(
        self,
        task_name: str,
        expected_status: str,
        result: dict[str, Any],
    ) -> None:
        reported = optional_text(result, "task_status")
        if reported and reported != expected_status:
            raise BatchExecutionError(
                "BATCH-TASK-STATUS-001",
                f"Host reported task status {reported}; expected {expected_status}",
            )
        task_path = self.repo_root / ".cowork-flow" / "tasks" / task_name / "task.json"
        try:
            task_data = json.loads(task_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BatchExecutionError(
                "BATCH-TASK-LOAD-001",
                f"cannot load task status for {task_name}: {error}",
            ) from error
        actual = task_data.get("status")
        if actual != expected_status:
            raise BatchExecutionError(
                "BATCH-TASK-STATUS-001",
                f"task status for {task_name} is {actual}; expected {expected_status}",
            )

    def verify_archive_result(self, task_name: str, result: dict[str, Any]) -> None:
        destination = required_text(
            result,
            "archive_destination",
            "archive result is missing archive_destination",
        )
        destination_path = Path(destination)
        if destination_path.is_absolute():
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                f"archive_destination must be relative: {destination}",
            )
        archive_root = (self.repo_root / ".cowork-flow" / "tasks" / "archive").resolve()
        archive_path = (self.repo_root / destination_path).resolve()
        try:
            archive_path.relative_to(archive_root)
        except ValueError as error:
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                "archive_destination must be under "
                f".cowork-flow/tasks/archive: {destination}",
            ) from error
        if archive_path.name != task_name:
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                f"archive_destination task name is {archive_path.name}; expected {task_name}",
            )
        if not archive_path.is_dir():
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                f"archive_destination does not exist: {destination}",
            )
        task_json = archive_path / "task.json"
        try:
            task_data = json.loads(task_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                f"archive_destination task.json cannot be loaded: {error}",
            ) from error
        logical_task_names = {task_name}
        if len(task_name) > 6 and task_name[2] == "-" and task_name[5] == "-":
            logical_task_names.add(task_name[6:])
        if not any(task_data.get(field) in logical_task_names for field in ("name", "id")):
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                "archive_destination task identity is "
                f"name={task_data.get('name')} id={task_data.get('id')}; "
                f"expected one of {sorted(logical_task_names)}",
            )
        if task_data.get("status") != "completed":
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                f"archive_destination task status is {task_data.get('status')}; expected completed",
            )

    def verify_runtime_initialized(
        self,
        state: dict[str, Any],
        task_name: str,
        role: str,
        result: dict[str, Any],
    ) -> None:
        runtime_context_id = required_text(
            result,
            "runtime_context_id",
            "runtime initialization result is missing runtime_context_id",
        )
        host_context_key = required_text(
            result,
            "host_context_key",
            "runtime initialization result is missing host_context_key",
        )
        context = self.runtime_contexts.load(runtime_context_id)
        self.verify_runtime_identity(context, task_name, role, runtime_context_id)
        status = context.get("status")
        if status == "closed":
            raise BatchExecutionError(
                "BATCH-RUNTIME-CLOSED-001",
                f"runtime context is already closed: {runtime_context_id}",
            )
        bound_key = context.get("bound_context_key")
        if bound_key and bound_key != host_context_key:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                f"runtime context {runtime_context_id} is bound to {bound_key}, not {host_context_key}",
            )
        runtime_contexts = dict(state.get("runtime_contexts") or {})
        task_contexts = dict(runtime_contexts.get(task_name) or {})
        task_contexts[role] = {
            "runtime_context_id": runtime_context_id,
            "host_context_key": host_context_key,
        }
        runtime_contexts[task_name] = task_contexts
        state["runtime_contexts"] = runtime_contexts

    def verify_runtime_completed(
        self,
        state: dict[str, Any],
        task_name: str,
        role: str,
        action: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        runtime = runtime_for(state, task_name, role)
        runtime_context_id = required_text(
            result,
            "runtime_context_id",
            "runtime result is missing runtime_context_id",
        )
        host_context_key = required_text(
            result,
            "host_context_key",
            "runtime result is missing host_context_key",
        )
        if runtime_context_id != runtime["runtime_context_id"]:
            raise BatchExecutionError(
                "BATCH-RUNTIME-ID-001",
                "runtime_context_id does not match initialized context: "
                f"{runtime_context_id}; expected {runtime['runtime_context_id']}",
            )
        if host_context_key != runtime["host_context_key"]:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                "host_context_key does not match initialized context: "
                f"{host_context_key}; expected {runtime['host_context_key']}",
            )
        if action.get("runtime_context_id") != runtime_context_id:
            raise BatchExecutionError(
                "BATCH-RUNTIME-ID-001",
                "runtime_context_id does not match pending action: "
                f"{runtime_context_id}; expected {action.get('runtime_context_id')}",
            )
        context = self.runtime_contexts.load(runtime_context_id)
        self.verify_runtime_identity(context, task_name, role, runtime_context_id)
        status = context.get("status")
        if status not in {"bound", "closed"}:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                f"runtime context {runtime_context_id} is not bound",
            )
        if context.get("bound_context_key") != host_context_key:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                f"runtime context {runtime_context_id} bound_context_key does not match result: "
                f"{context.get('bound_context_key')}; expected {host_context_key}",
            )
        if status == "bound":
            if not self.runtime_contexts.close(runtime_context_id):
                raise BatchExecutionError(
                    "BATCH-RUNTIME-CLOSE-001",
                    f"runtime context could not be closed: {runtime_context_id}",
                )
            closed = self.runtime_contexts.load(runtime_context_id)
            if closed.get("status") != "closed":
                raise BatchExecutionError(
                    "BATCH-RUNTIME-CLOSE-001",
                    f"runtime context did not close: {runtime_context_id}",
                )

    @staticmethod
    def verify_runtime_identity(
        context: dict[str, Any],
        task_name: str,
        role: str,
        runtime_context_id: str,
    ) -> None:
        if not context:
            raise BatchExecutionError(
                "BATCH-RUNTIME-MISSING-001",
                f"runtime context does not exist: {runtime_context_id}",
            )
        if context.get("scope") != "subagent":
            raise BatchExecutionError(
                "BATCH-RUNTIME-SCOPE-001",
                f"runtime context is not subagent-scoped: {runtime_context_id}",
            )
        if context.get("role") != role:
            raise BatchExecutionError(
                "BATCH-RUNTIME-ROLE-001",
                f"runtime context role is not {role}: {runtime_context_id}",
            )
        expected_task_dir = f".cowork-flow/tasks/{task_name}"
        if context.get("task_dir") != expected_task_dir:
            raise BatchExecutionError(
                "BATCH-RUNTIME-TASK-001",
                f"runtime context task_dir is not {expected_task_dir}",
            )
