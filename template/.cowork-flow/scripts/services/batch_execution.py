#!/usr/bin/env python3
"""Recoverable task-graph Batch execution state machine."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Callable

from services.workflow_runtime import (
    RuntimeContextError,
    RuntimeContextService,
)
from services.task_tree import TaskTreeService
from infra.storage.state_store import StateStore, StateStoreError


BATCH_STEPS = (
    "start_task",
    "init_implement_context",
    "await_implement_result",
    "review_task",
    "init_check_context",
    "await_check_result",
    "complete_task",
    "archive_task",
    "commit_task",
)
STEP_PHASES = {
    "start_task": "start",
    "await_implement_result": "implement",
    "review_task": "review",
    "await_check_result": "check",
    "complete_task": "complete",
    "archive_task": "archive",
    "commit_task": "commit",
}
LIFECYCLE_STATUSES = {
    "start_task": "in_progress",
    "review_task": "review",
    "complete_task": "completed",
    "archive_task": "completed",
}
RUNTIME_ROLES = {
    "init_implement_context": "implement",
    "await_implement_result": "implement",
    "init_check_context": "check",
    "await_check_result": "check",
}
CommitVerifier = Callable[[str], bool]


class BatchExecutionError(RuntimeError):
    """Raised when Batch graph, state, or host input is invalid."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class BatchExecutionService:
    """Publish and verify one host-neutral Batch action at a time."""

    def __init__(
        self,
        repo_root: Path,
        *,
        state_store: StateStore | None = None,
        commit_verifier: CommitVerifier | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.state_store = state_store or StateStore()
        self.tree = TaskTreeService(self.repo_root)
        self.runtime_contexts = RuntimeContextService(
            self.repo_root,
            state_store=self.state_store,
        )
        self.commit_verifier = commit_verifier or self._verify_git_commit

    def start(self, root_task: str) -> dict:
        ordered_tasks, graph_digest = self._plan(root_task)
        operation_id = f"batch-{root_task}"
        path = self._state_path(operation_id)
        snapshot = self._load(path)
        if snapshot.exists:
            state = dict(snapshot.data)
            if state.get("graph_digest") != graph_digest:
                raise BatchExecutionError(
                    "BATCH-GRAPH-CHANGED-001",
                    "task graph changed after Batch state was created",
                )
            return self._advance(path, state)

        state = {
            "schema_version": 2,
            "operation_id": operation_id,
            "root_task": root_task,
            "graph_digest": graph_digest,
            "ordered_tasks": list(ordered_tasks),
            "current_task": None,
            "completed_tasks": [],
            "commits": {},
            "retry_count": {},
            "task_phases": {},
            "task_steps": {},
            "runtime_contexts": {},
            "action_results": {},
            "next_action_sequence": 0,
            "next_action": None,
            "phase": "ready",
            "pause_reason": None,
        }
        self._save(path, state)
        return self._advance(path, state)

    def resume(self, operation_id: str) -> dict:
        path = self._state_path(operation_id)
        snapshot = self._load(path)
        if not snapshot.exists:
            raise BatchExecutionError(
                "BATCH-STATE-MISSING-001",
                f"Batch state does not exist: {operation_id}",
            )
        state = dict(snapshot.data)
        self._assert_graph_unchanged(state)
        if state.get("phase") == "paused":
            state["phase"] = "running"
            state["pause_reason"] = None
            state["next_action"] = None
            self._save(path, state)
        return self._advance(path, state)

    def record_result(self, operation_id: str, payload: dict) -> dict:
        path = self._state_path(operation_id)
        snapshot = self._load(path)
        if not snapshot.exists:
            raise BatchExecutionError(
                "BATCH-STATE-MISSING-001",
                f"Batch state does not exist: {operation_id}",
            )
        state = dict(snapshot.data)
        self._assert_graph_unchanged(state)
        result = self._normalize_result(payload)
        action_id = result["action_id"]
        previous = dict(state.get("action_results") or {}).get(action_id)
        if previous is not None:
            if previous != result:
                raise BatchExecutionError(
                    "BATCH-RESULT-CONFLICT-001",
                    f"action result changed after recording: {action_id}",
                )
            return state

        action = state.get("next_action")
        if not isinstance(action, dict):
            raise BatchExecutionError(
                "BATCH-ACTION-MISSING-001",
                "Batch is not waiting for a Host action",
            )
        if action_id != action.get("action_id"):
            raise BatchExecutionError(
                "BATCH-ACTION-MISMATCH-001",
                f"expected action {action.get('action_id')}, got {action_id}",
            )
        if result["type"] != action.get("type"):
            raise BatchExecutionError(
                "BATCH-ACTION-TYPE-001",
                f"expected action type {action.get('type')}, "
                f"got {result['type']}",
            )

        if result["outcome"] != "success":
            detail = self._optional_text(result, "detail")
            return self._pause(
                path,
                state,
                action,
                result,
                detail or "Host action reported failure",
            )

        try:
            self._verify_success(state, action, result)
        except (BatchExecutionError, RuntimeContextError) as error:
            detail = getattr(error, "detail", str(error))
            return self._pause(
                path,
                state,
                action,
                result,
                detail,
            )

        action_results = dict(state.get("action_results") or {})
        action_results[action_id] = result
        state["action_results"] = action_results
        self._mark_step_completed(state, action, result)
        state["next_action"] = None
        state["phase"] = "running"
        state["pause_reason"] = None
        self._save(path, state)
        return self._advance(path, state)

    def _advance(self, path: Path, state: dict) -> dict:
        if state.get("phase") in {"completed", "paused"}:
            return state
        if isinstance(state.get("next_action"), dict):
            return state

        completed_tasks = list(state.get("completed_tasks") or [])
        task_steps = dict(state.get("task_steps") or {})
        retry_count = dict(state.get("retry_count") or {})

        for task_name in state["ordered_tasks"]:
            if task_name in completed_tasks:
                continue
            state["current_task"] = task_name
            completed_steps = list(task_steps.get(task_name) or [])
            for step in BATCH_STEPS:
                if step in completed_steps:
                    continue
                action = self._build_action(state, task_name, step)
                state["next_action"] = action
                state["phase"] = "awaiting_host"
                self._save(path, state)
                return state

            completed_tasks.append(task_name)
            state["completed_tasks"] = completed_tasks
            retry_count[task_name] = 0
            state["retry_count"] = retry_count
            state["current_task"] = None
            self._save(path, state)

        state["phase"] = "completed"
        state["current_task"] = None
        state["next_action"] = None
        state["pause_reason"] = None
        self._save(path, state)
        return state

    def _build_action(
        self,
        state: dict,
        task_name: str,
        step: str,
    ) -> dict:
        sequence = int(state.get("next_action_sequence") or 0) + 1
        state["next_action_sequence"] = sequence
        action = {
            "action_id": (
                f"{state['operation_id']}:{sequence}:{task_name}:{step}"
            ),
            "type": step,
            "phase": self._phase_for_step(step),
            "task": task_name,
            "task_dir": f".cowork-flow/tasks/{task_name}",
        }
        role = RUNTIME_ROLES.get(step)
        if step.startswith("init_") and role:
            action.update(
                {
                    "role": role,
                    "agent_type": f"cowork-{role}",
                    "title": (
                        f"{role.capitalize()} Batch task {task_name}"
                    ),
                }
            )
        if step.startswith("await_") and role:
            runtime = self._runtime_for(state, task_name, role)
            action.update(
                {
                    "role": role,
                    "runtime_context_id": runtime["runtime_context_id"],
                    "host_context_key": runtime["host_context_key"],
                }
            )
        return action

    def _verify_success(
        self,
        state: dict,
        action: dict,
        result: dict,
    ) -> None:
        action_type = str(action["type"])
        task_name = str(action["task"])
        if action_type in LIFECYCLE_STATUSES:
            self._verify_task_status(
                task_name,
                LIFECYCLE_STATUSES[action_type],
                result,
            )
            return
        if action_type.startswith("init_"):
            self._verify_runtime_initialized(
                state,
                task_name,
                RUNTIME_ROLES[action_type],
                result,
            )
            return
        if action_type.startswith("await_"):
            self._verify_runtime_completed(
                state,
                task_name,
                RUNTIME_ROLES[action_type],
                action,
                result,
            )
            return
        if action_type == "commit_task":
            commit_id = self._required_text(
                result,
                "commit_id",
                "commit result is missing commit_id",
            )
            if not self.commit_verifier(commit_id):
                raise BatchExecutionError(
                    "BATCH-COMMIT-VERIFY-001",
                    f"commit could not be verified: {commit_id}",
                )
            return
        if action_type == "archive_task":
            self._verify_archive_result(task_name, result)
            return
        raise BatchExecutionError(
            "BATCH-ACTION-UNKNOWN-001",
            f"unsupported Batch action: {action_type}",
        )

    def _verify_task_status(
        self,
        task_name: str,
        expected_status: str,
        result: dict,
    ) -> None:
        reported = self._optional_text(result, "task_status")
        if reported and reported != expected_status:
            raise BatchExecutionError(
                "BATCH-TASK-STATUS-001",
                f"Host reported task status {reported}; "
                f"expected {expected_status}",
            )
        task_path = (
            self.repo_root
            / ".cowork-flow"
            / "tasks"
            / task_name
            / "task.json"
        )
        try:
            task_data = json.loads(
                task_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise BatchExecutionError(
                "BATCH-TASK-LOAD-001",
                f"cannot load task status for {task_name}: {error}",
            ) from error
        actual = task_data.get("status")
        if actual != expected_status:
            raise BatchExecutionError(
                "BATCH-TASK-STATUS-001",
                f"task status for {task_name} is {actual}; "
                f"expected {expected_status}",
            )

    def _verify_archive_result(
        self,
        task_name: str,
        result: dict,
    ) -> None:
        destination = self._optional_text(result, "archive_destination")
        if destination is None:
            return
        archive_path = self.repo_root / destination
        if not archive_path.exists():
            raise BatchExecutionError(
                "BATCH-ARCHIVE-VERIFY-001",
                f"archive destination does not exist: {destination}",
            )

    def _verify_runtime_initialized(
        self,
        state: dict,
        task_name: str,
        role: str,
        result: dict,
    ) -> None:
        runtime_context_id = self._required_text(
            result,
            "runtime_context_id",
            "runtime initialization result is missing runtime_context_id",
        )
        host_context_key = self._required_text(
            result,
            "host_context_key",
            "runtime initialization result is missing host_context_key",
        )
        context = self.runtime_contexts.load(runtime_context_id)
        self._verify_runtime_identity(
            context,
            task_name,
            role,
            runtime_context_id,
        )
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
                f"runtime context {runtime_context_id} is bound to "
                f"{bound_key}, not {host_context_key}",
            )
        runtime_contexts = dict(state.get("runtime_contexts") or {})
        task_contexts = dict(runtime_contexts.get(task_name) or {})
        task_contexts[role] = {
            "runtime_context_id": runtime_context_id,
            "host_context_key": host_context_key,
        }
        runtime_contexts[task_name] = task_contexts
        state["runtime_contexts"] = runtime_contexts

    def _verify_runtime_completed(
        self,
        state: dict,
        task_name: str,
        role: str,
        action: dict,
        result: dict,
    ) -> None:
        runtime = self._runtime_for(state, task_name, role)
        runtime_context_id = self._required_text(
            result,
            "runtime_context_id",
            "runtime result is missing runtime_context_id",
        )
        host_context_key = self._required_text(
            result,
            "host_context_key",
            "runtime result is missing host_context_key",
        )
        if runtime_context_id != runtime["runtime_context_id"]:
            raise BatchExecutionError(
                "BATCH-RUNTIME-ID-001",
                "runtime result does not match initialized context",
            )
        if host_context_key != runtime["host_context_key"]:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                "runtime result does not match expected host context",
            )
        if action.get("runtime_context_id") != runtime_context_id:
            raise BatchExecutionError(
                "BATCH-RUNTIME-ID-001",
                "pending action runtime context changed",
            )
        context = self.runtime_contexts.load(runtime_context_id)
        self._verify_runtime_identity(
            context,
            task_name,
            role,
            runtime_context_id,
        )
        status = context.get("status")
        if status not in {"bound", "closed"}:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                f"runtime context {runtime_context_id} is not bound",
            )
        if context.get("bound_context_key") != host_context_key:
            raise BatchExecutionError(
                "BATCH-RUNTIME-BIND-001",
                f"runtime context {runtime_context_id} has unexpected "
                "bound_context_key",
            )
        if status == "bound":
            if not self.runtime_contexts.close(runtime_context_id):
                raise BatchExecutionError(
                    "BATCH-RUNTIME-CLOSE-001",
                    "runtime context could not be closed: "
                    f"{runtime_context_id}",
                )
            closed = self.runtime_contexts.load(runtime_context_id)
            if closed.get("status") != "closed":
                raise BatchExecutionError(
                    "BATCH-RUNTIME-CLOSE-001",
                    f"runtime context did not close: {runtime_context_id}",
                )

    @staticmethod
    def _verify_runtime_identity(
        context: dict,
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
                f"runtime context is not subagent-scoped: "
                f"{runtime_context_id}",
            )
        if context.get("role") != role:
            raise BatchExecutionError(
                "BATCH-RUNTIME-ROLE-001",
                f"runtime context role is not {role}: "
                f"{runtime_context_id}",
            )
        expected_task_dir = f".cowork-flow/tasks/{task_name}"
        if context.get("task_dir") != expected_task_dir:
            raise BatchExecutionError(
                "BATCH-RUNTIME-TASK-001",
                f"runtime context task_dir is not {expected_task_dir}",
            )

    def _mark_step_completed(
        self,
        state: dict,
        action: dict,
        result: dict,
    ) -> None:
        task_name = str(action["task"])
        step = str(action["type"])
        task_steps = dict(state.get("task_steps") or {})
        completed_steps = list(task_steps.get(task_name) or [])
        if step not in completed_steps:
            completed_steps.append(step)
        task_steps[task_name] = completed_steps
        state["task_steps"] = task_steps

        phase = STEP_PHASES.get(step)
        if phase:
            task_phases = dict(state.get("task_phases") or {})
            completed_phases = list(task_phases.get(task_name) or [])
            if phase not in completed_phases:
                completed_phases.append(phase)
            task_phases[task_name] = completed_phases
            state["task_phases"] = task_phases

        if step == "commit_task":
            commits = dict(state.get("commits") or {})
            commits[task_name] = result["commit_id"].strip()
            state["commits"] = commits

    def _pause(
        self,
        path: Path,
        state: dict,
        action: dict,
        result: dict,
        detail: str,
    ) -> dict:
        task_name = str(action["task"])
        retry_count = dict(state.get("retry_count") or {})
        retry_count[task_name] = int(retry_count.get(task_name, 0)) + 1
        state["retry_count"] = retry_count
        action_results = dict(state.get("action_results") or {})
        action_results[result["action_id"]] = dict(result)
        state["action_results"] = action_results
        state["phase"] = "paused"
        state["current_task"] = task_name
        state["next_action"] = None
        state["pause_reason"] = (
            f"{task_name}:{action['type']}: {detail}"
        )
        self._save(path, state)
        return state

    def _runtime_for(
        self,
        state: dict,
        task_name: str,
        role: str,
    ) -> dict:
        runtime_contexts = dict(state.get("runtime_contexts") or {})
        task_contexts = dict(runtime_contexts.get(task_name) or {})
        runtime = task_contexts.get(role)
        if not isinstance(runtime, dict):
            raise BatchExecutionError(
                "BATCH-RUNTIME-MISSING-001",
                f"runtime context was not initialized for "
                f"{task_name}:{role}",
            )
        return runtime

    def _assert_graph_unchanged(self, state: dict) -> None:
        root_task = state.get("root_task")
        if not isinstance(root_task, str) or not root_task.strip():
            raise BatchExecutionError(
                "BATCH-STATE-ROOT-001",
                "Batch state is missing root_task",
            )
        _, graph_digest = self._plan(root_task)
        if state.get("graph_digest") != graph_digest:
            raise BatchExecutionError(
                "BATCH-GRAPH-CHANGED-001",
                "task graph changed after Batch state was created",
            )

    def _plan(self, root_task: str) -> tuple[tuple[str, ...], str]:
        nodes = self.tree.active_nodes()
        if root_task not in nodes:
            raise BatchExecutionError(
                "BATCH-GRAPH-MISSING-001",
                f"root task does not exist: {root_task}",
            )
        ordered: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise BatchExecutionError(
                    "BATCH-GRAPH-CYCLE-001",
                    f"task graph cycle detected at {name}",
                )
            if name in visited:
                return
            node = nodes.get(name)
            if node is None:
                raise BatchExecutionError(
                    "BATCH-GRAPH-MISSING-001",
                    f"task graph references missing task: {name}",
                )
            visiting.add(name)
            for child in node.children:
                visit(child)
            visiting.remove(name)
            visited.add(name)
            if not node.children:
                ordered.append(name)

        visit(root_task)
        graph_payload = {
            name: list(nodes[name].children)
            for name in sorted(visited)
        }
        digest = hashlib.sha256(
            json.dumps(
                graph_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return tuple(ordered), digest

    def _verify_git_commit(self, commit_id: str) -> bool:
        try:
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.repo_root),
                    "cat-file",
                    "-e",
                    f"{commit_id}^{{commit}}",
                ],
                check=False,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return False
        return completed.returncode == 0

    def _state_path(self, operation_id: str) -> Path:
        return (
            self.repo_root
            / ".cowork-flow"
            / "runtime"
            / "batches"
            / f"{operation_id}.json"
        )

    def _load(self, path: Path):
        try:
            return self.state_store.load(path, missing_ok=True)
        except StateStoreError as error:
            raise BatchExecutionError(
                "BATCH-STATE-LOAD-001",
                error.detail,
            ) from error

    def _save(self, path: Path, state: dict) -> None:
        try:
            snapshot = self.state_store.load(path, missing_ok=True)
            self.state_store.replace(
                path,
                state,
                expected_revision=snapshot.revision,
                operation_id=(
                    f"{state['operation_id']}:checkpoint:"
                    f"{snapshot.revision + 1}"
                ),
            )
        except StateStoreError as error:
            raise BatchExecutionError(
                "BATCH-STATE-SAVE-001",
                error.detail,
            ) from error

    @staticmethod
    def _phase_for_step(step: str) -> str:
        if "implement" in step:
            return "implement"
        if "check" in step:
            return "check"
        return STEP_PHASES[step]

    @staticmethod
    def _normalize_result(payload: dict) -> dict:
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

    @staticmethod
    def _required_text(
        payload: dict,
        key: str,
        detail: str,
    ) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise BatchExecutionError(
                "BATCH-RESULT-PAYLOAD-001",
                detail,
            )
        return value.strip()

    @staticmethod
    def _optional_text(payload: dict, key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None
