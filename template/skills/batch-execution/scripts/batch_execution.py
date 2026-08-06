#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recoverable task-graph Batch execution facade."""

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

from batch_recovery import inspect_projection
from batch_state_machine import (
    BATCH_STEPS,
    LIFECYCLE_STATUSES,
    RUNTIME_ROLES,
    STEP_PHASES,
    BatchExecutionError,
    advance_state,
    mark_step_completed,
    pause_state,
    phase_for_step,
)
from batch_verification import (
    BatchActionVerifier,
    normalize_result,
    optional_text,
    required_text,
)

CommitVerifier = Callable[[str], bool]


class BatchExecutionService:
    """Publish, persist, and verify one host-neutral Batch action at a time."""

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
        self.verifier = BatchActionVerifier(
            self.repo_root,
            self.runtime_contexts,
            self.commit_verifier,
        )

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

    def inspect(self, operation_id: str) -> dict:
        path = self._state_path(operation_id)
        snapshot = self._load(path)
        if not snapshot.exists:
            raise BatchExecutionError(
                "BATCH-STATE-MISSING-001",
                f"Batch state does not exist: {operation_id}",
            )
        return inspect_projection(operation_id, dict(snapshot.data))

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
        result = normalize_result(payload)
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
                f"expected action type {action.get('type')}, got {result['type']}",
            )

        if result["outcome"] != "success":
            detail = optional_text(result, "detail")
            return self._pause(
                path,
                state,
                action,
                result,
                detail or "Host action reported failure",
            )

        try:
            self.verifier.verify_success(state, action, result)
        except (BatchExecutionError, RuntimeContextError) as error:
            detail = getattr(error, "detail", str(error))
            return self._pause(path, state, action, result, detail)

        action_results = dict(state.get("action_results") or {})
        action_results[action_id] = result
        state["action_results"] = action_results
        mark_step_completed(state, action, result)
        state["next_action"] = None
        state["phase"] = "running"
        state["pause_reason"] = None
        self._save(path, state)
        return self._advance(path, state)

    def _advance(self, path: Path, state: dict) -> dict:
        if advance_state(state):
            self._save(path, state)
        return state

    def _pause(
        self,
        path: Path,
        state: dict,
        action: dict,
        result: dict,
        detail: str,
    ) -> dict:
        pause_state(state, action, result, detail)
        self._save(path, state)
        return state

    def _assert_graph_unchanged(self, state: dict) -> None:
        root_task = state.get("root_task")
        if not isinstance(root_task, str) or not root_task.strip():
            raise BatchExecutionError(
                "BATCH-STATE-ROOT-001",
                "Batch state is missing root_task",
            )
        try:
            ordered, graph_digest = self._plan(root_task)
        except BatchExecutionError as error:
            if getattr(error, "code", "") != "BATCH-GRAPH-MISSING-001":
                raise
            ordered = ()
            graph_digest = None
        if state.get("graph_digest") == graph_digest:
            return
        expected_remaining = self._remaining_ordered_tasks_after_archives(state)
        if tuple(ordered) == tuple(expected_remaining):
            return
        raise BatchExecutionError(
            "BATCH-GRAPH-CHANGED-001",
            "task graph changed after Batch state was created",
        )

    def _remaining_ordered_tasks_after_archives(self, state: dict) -> tuple[str, ...]:
        ordered = tuple(
            task
            for task in state.get("ordered_tasks", ())
            if isinstance(task, str) and task.strip()
        )
        task_steps = dict(state.get("task_steps") or {})
        completed = set(
            task
            for task in state.get("completed_tasks", ())
            if isinstance(task, str)
        )
        archived_candidates = set(completed)
        for task_name, steps in task_steps.items():
            if isinstance(task_name, str) and "archive_task" in list(steps or []):
                archived_candidates.add(task_name)
        action = state.get("next_action")
        if isinstance(action, dict) and action.get("type") in {"archive_task", "commit_task"}:
            task_name = action.get("task")
            if isinstance(task_name, str):
                archived_candidates.add(task_name)
        if state.get("phase") == "paused":
            current_task = state.get("current_task")
            if isinstance(current_task, str):
                archived_candidates.add(current_task)
        archived = {
            task_name
            for task_name in archived_candidates
            if self._archived_task_exists(task_name)
        }
        return tuple(task for task in ordered if task not in archived)

    def _archived_task_exists(self, task_name: str) -> bool:
        archive_root = self.repo_root / ".cowork-flow" / "tasks" / "archive"
        if not archive_root.is_dir():
            return False
        return any(
            task_dir.name == task_name and (task_dir / "task.json").is_file()
            for task_dir in archive_root.glob("*/*")
            if task_dir.is_dir()
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
            raise BatchExecutionError("BATCH-STATE-LOAD-001", error.detail) from error

    def _save(self, path: Path, state: dict) -> None:
        try:
            snapshot = self.state_store.load(path, missing_ok=True)
            self.state_store.replace(
                path,
                state,
                expected_revision=snapshot.revision,
                operation_id=(
                    f"{state['operation_id']}:checkpoint:{snapshot.revision + 1}"
                ),
            )
        except StateStoreError as error:
            raise BatchExecutionError("BATCH-STATE-SAVE-001", error.detail) from error

    _phase_for_step = staticmethod(phase_for_step)
    _normalize_result = staticmethod(normalize_result)
    _required_text = staticmethod(required_text)
    _optional_text = staticmethod(optional_text)


__all__ = [
    "BATCH_STEPS",
    "BatchExecutionError",
    "BatchExecutionService",
    "LIFECYCLE_STATUSES",
    "RUNTIME_ROLES",
    "STEP_PHASES",
]
