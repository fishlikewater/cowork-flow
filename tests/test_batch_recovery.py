#!/usr/bin/env python3
"""Recovery and fail-closed coverage for task-graph Batch execution."""

from __future__ import annotations

import importlib
import json
import tempfile
import sys
from pathlib import Path

from tests.flow_test_support import FlowScriptTestCase


ROOT = Path(__file__).resolve().parents[1]
BATCH_SCRIPTS = ROOT / "template" / "skills" / "batch-execution" / "scripts"


class BatchRecoveryTest(FlowScriptTestCase):
    def setUp(self) -> None:
        super().setUp()
        if str(BATCH_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(BATCH_SCRIPTS))
            self.addCleanup(sys.path.remove, str(BATCH_SCRIPTS))
        self.module = importlib.import_module("batch_execution")
        self.runtime_module = importlib.import_module(
            "services.workflow_runtime"
        )

    def test_batch_state_machine_advances_in_memory_without_store(self) -> None:
        state_machine = importlib.import_module("batch_state_machine")
        state = {
            "operation_id": "batch-parent",
            "ordered_tasks": ["child-a"],
            "completed_tasks": [],
            "retry_count": {},
            "task_steps": {},
            "task_phases": {},
            "runtime_contexts": {},
            "next_action_sequence": 0,
            "next_action": None,
            "phase": "ready",
            "pause_reason": None,
        }

        changed = state_machine.advance_state(state)

        self.assertTrue(changed)
        self.assertEqual("awaiting_host", state["phase"])
        self.assertEqual("child-a", state["current_task"])
        self.assertEqual("start_task", state["next_action"]["type"])
        self.assertEqual("batch-parent:1:child-a:start_task", state["next_action"]["action_id"])

    def _task(
        self,
        root: Path,
        name: str,
        *,
        children: tuple[str, ...] = (),
        parent: str | None = None,
        metadata_name: str | None = None,
    ) -> Path:
        task_dir = root / ".cowork-flow/tasks" / name
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "id": metadata_name or name,
                    "name": metadata_name or name,
                    "status": "planning",
                    "children": list(children),
                    "parent": parent,
                    "assignee": "tester",
                }
            ),
            encoding="utf-8",
        )
        return task_dir

    def _graph(self, root: Path) -> None:
        parent = self._task(
            root,
            "parent",
            children=("child-a", "child-b"),
        )
        self._task(root, "child-a", parent="parent")
        self._task(root, "child-b", parent="parent")
        (parent / "implement.jsonl").write_text(
            '{"file":"not-a-task","reason":"must be ignored"}\n',
            encoding="utf-8",
        )

    @staticmethod
    def _set_status(root: Path, task_name: str, status: str) -> None:
        path = root / ".cowork-flow/tasks" / task_name / "task.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = status
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _payload(state: dict, **extra: object) -> dict:
        action = state["next_action"]
        payload = {
            "action_id": action["action_id"],
            "type": action["type"],
            "outcome": "success",
        }
        payload.update(extra)
        return payload

    def _runtime_context(
        self,
        root: Path,
        task_name: str,
        role: str,
        *,
        bind: bool = True,
    ) -> tuple[str, str]:
        runtime_id = f"batch-{task_name}-{role}"
        host_key = f"codex_{runtime_id}"
        context = {
            "schema_version": 1,
            "scope": "subagent",
            "host": "codex",
            "adapter": "codex",
            "agent_type": f"cowork-{role}",
            "role": role,
            "task_dir": f".cowork-flow/tasks/{task_name}",
            "status": "pending",
            "bound_context_key": None,
        }
        runtime = self.runtime_module.RuntimeContextService(root)
        runtime.initialize(runtime_id, context)
        if bind:
            runtime.bind(runtime_id, host_key)
        return runtime_id, host_key

    def _record_lifecycle(
        self,
        service,
        root: Path,
        state: dict,
        status: str,
    ) -> dict:
        task_name = state["next_action"]["task"]
        self._set_status(root, task_name, status)
        return service.record_result(
            state["operation_id"],
            self._payload(state, task_status=status),
        )

    def _record_runtime_init(
        self,
        service,
        root: Path,
        state: dict,
        *,
        bind: bool = True,
    ) -> tuple[dict, str, str]:
        action = state["next_action"]
        role = action["role"]
        runtime_id, host_key = self._runtime_context(
            root,
            action["task"],
            role,
            bind=bind,
        )
        next_state = service.record_result(
            state["operation_id"],
            self._payload(
                state,
                runtime_context_id=runtime_id,
                host_context_key=host_key,
            ),
        )
        return next_state, runtime_id, host_key

    def _record_runtime_result(
        self,
        service,
        root: Path,
        state: dict,
    ) -> dict:
        action = state["next_action"]
        return service.record_result(
            state["operation_id"],
            self._payload(
                state,
                runtime_context_id=action["runtime_context_id"],
                host_context_key=action["host_context_key"],
            ),
        )

    def _archive_destination(
        self,
        root: Path,
        task_name: str,
        *,
        destination: str | None = None,
        move_active: bool = False,
    ) -> str:
        destination = (
            destination
            or f".cowork-flow/tasks/archive/2026-07/{task_name}"
        )
        archive_dir = root / destination
        active_dir = root / ".cowork-flow" / "tasks" / task_name
        active_task = active_dir / "task.json"
        task_data = json.loads(active_task.read_text(encoding="utf-8"))
        if move_active:
            archive_dir.parent.mkdir(parents=True, exist_ok=True)
            active_dir.rename(archive_dir)
            parent = task_data.get("parent")
            if isinstance(parent, str) and parent:
                parent_json = root / ".cowork-flow" / "tasks" / parent / "task.json"
                parent_data = json.loads(parent_json.read_text(encoding="utf-8"))
                parent_data["children"] = [
                    child
                    for child in parent_data.get("children", [])
                    if child != task_name
                ]
                parent_json.write_text(
                    json.dumps(parent_data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        else:
            archive_dir.mkdir(parents=True)
            archive_task = archive_dir / "task.json"
            archive_task.write_text(
                active_task.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        return destination

    def _advance_to_action(
        self,
        service,
        root: Path,
        state: dict,
        target_action: str,
    ) -> dict:
        while state["next_action"]["type"] != target_action:
            action_type = state["next_action"]["type"]
            if action_type == "start_task":
                state = self._record_lifecycle(
                    service,
                    root,
                    state,
                    "in_progress",
                )
            elif action_type == "review_task":
                state = self._record_lifecycle(
                    service,
                    root,
                    state,
                    "review",
                )
            elif action_type == "complete_task":
                state = self._record_lifecycle(
                    service,
                    root,
                    state,
                    "completed",
                )
            elif action_type.startswith("init_"):
                state, _, _ = self._record_runtime_init(
                    service,
                    root,
                    state,
                )
            elif action_type.startswith("await_"):
                state = self._record_runtime_result(service, root, state)
            elif action_type == "archive_task":
                archive_destination = self._archive_destination(
                    root,
                    state["next_action"]["task"],
                )
                state = service.record_result(
                    state["operation_id"],
                    self._payload(
                        state,
                        archive_destination=archive_destination,
                    ),
                )
            else:
                self.fail(f"unexpected action: {action_type}")
        return state

    def _complete_current_task(
        self,
        service,
        root: Path,
        state: dict,
    ) -> dict:
        task_name = state["next_action"]["task"]
        while task_name not in state["completed_tasks"]:
            action_type = state["next_action"]["type"]
            if action_type == "start_task":
                state = self._record_lifecycle(
                    service,
                    root,
                    state,
                    "in_progress",
                )
            elif action_type == "init_implement_context":
                state, _, _ = self._record_runtime_init(
                    service,
                    root,
                    state,
                )
            elif action_type == "await_implement_result":
                action = state["next_action"]
                state = service.record_result(
                    state["operation_id"],
                    self._payload(
                        state,
                        runtime_context_id=action["runtime_context_id"],
                        host_context_key=action["host_context_key"],
                    ),
                )
            elif action_type == "review_task":
                state = self._record_lifecycle(
                    service,
                    root,
                    state,
                    "review",
                )
            elif action_type == "init_check_context":
                state, _, _ = self._record_runtime_init(
                    service,
                    root,
                    state,
                )
            elif action_type == "await_check_result":
                action = state["next_action"]
                state = service.record_result(
                    state["operation_id"],
                    self._payload(
                        state,
                        runtime_context_id=action["runtime_context_id"],
                        host_context_key=action["host_context_key"],
                    ),
                )
            elif action_type == "complete_task":
                state = self._record_lifecycle(
                    service,
                    root,
                    state,
                    "completed",
                )
            elif action_type == "archive_task":
                archive_destination = self._archive_destination(
                    root,
                    task_name,
                )
                state = service.record_result(
                    state["operation_id"],
                    self._payload(
                        state,
                        archive_destination=archive_destination,
                    ),
                )
            elif action_type == "commit_task":
                state = service.record_result(
                    state["operation_id"],
                    self._payload(state, commit_id=f"commit-{task_name}"),
                )
            else:
                self.fail(f"unexpected action type: {action_type}")
        return state




    def test_resume_after_archive_verification_failure_tolerates_moved_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._advance_to_action(
                service,
                root,
                service.start("parent"),
                "archive_task",
            )
            self._archive_destination(root, "child-a", move_active=True)
            paused = dict(state)
            paused["phase"] = "paused"
            paused["current_task"] = "child-a"
            paused["next_action"] = None
            paused["pause_reason"] = "child-a:archive_task: old verifier failed"
            service._save(
                service._state_path(state["operation_id"]),
                paused,
            )

            resumed = service.resume(state["operation_id"])

        self.assertEqual("archive_task", resumed["next_action"]["type"])
        self.assertEqual("child-a", resumed["next_action"]["task"])

    def test_archive_result_accepts_dated_directory_with_logical_task_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._task(
                root,
                "parent",
                children=("08-06-child-a", "child-b"),
            )
            self._task(
                root,
                "08-06-child-a",
                parent="parent",
                metadata_name="child-a",
            )
            self._task(root, "child-b", parent="parent")
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._advance_to_action(
                service,
                root,
                service.start("parent"),
                "archive_task",
            )
            archive_destination = self._archive_destination(
                root,
                "08-06-child-a",
                move_active=True,
            )

            state = service.record_result(
                state["operation_id"],
                self._payload(state, archive_destination=archive_destination),
            )

        self.assertEqual("commit_task", state["next_action"]["type"])

    def test_archive_record_tolerates_real_task_move_before_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._advance_to_action(
                service,
                root,
                service.start("parent"),
                "archive_task",
            )
            archive_destination = self._archive_destination(
                root,
                "child-a",
                move_active=True,
            )

            state = service.record_result(
                state["operation_id"],
                self._payload(state, archive_destination=archive_destination),
            )
            self.assertEqual("commit_task", state["next_action"]["type"])
            state = service.record_result(
                state["operation_id"],
                self._payload(state, commit_id="commit-child-a"),
            )

        self.assertEqual(["child-a"], state["completed_tasks"])
        self.assertEqual("start_task", state["next_action"]["type"])
        self.assertEqual("child-b", state["next_action"]["task"])

    def test_batch_uses_task_graph_and_waits_for_real_host_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )

            state = service.start("parent")

        self.assertEqual(["child-a", "child-b"], state["ordered_tasks"])
        self.assertNotIn("not-a-task", state["ordered_tasks"])
        self.assertEqual([], state["completed_tasks"])
        self.assertEqual("awaiting_host", state["phase"])
        self.assertEqual("start_task", state["next_action"]["type"])
        self.assertEqual("child-a", state["next_action"]["task"])

    def test_inspect_reports_completed_state_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._task(root, "solo")
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._complete_current_task(
                service,
                root,
                service.start("solo"),
            )
            self.assertEqual("completed", state["phase"])
            state_path = (
                root
                / ".cowork-flow"
                / "runtime"
                / "batches"
                / f"{state['operation_id']}.json"
            )
            before = state_path.read_text(encoding="utf-8")

            report = service.inspect(state["operation_id"])
            after = state_path.read_text(encoding="utf-8")

        self.assertEqual(before, after)
        self.assertEqual(state["operation_id"], report["operationId"])
        self.assertEqual("completed", report["state"])
        self.assertEqual("solo", report["rootTask"])
        self.assertEqual("completed", report["currentPhase"])
        self.assertIsNone(report["currentTask"])
        self.assertEqual(["solo"], report["completedTasks"])
        self.assertIsNone(report["pausedReason"])
        self.assertIsNone(report["failedAction"])
        self.assertIsNone(report["nextAction"])
        self.assertEqual({}, report["recovery"])

    def test_placeholder_success_pauses_until_task_state_is_real(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            first_action_id = state["next_action"]["action_id"]

            paused = service.record_result(
                state["operation_id"],
                self._payload(state, task_status="in_progress"),
            )
            resumed = service.resume(state["operation_id"])

        self.assertEqual("paused", paused["phase"])
        self.assertIn("task status", paused["pause_reason"])
        self.assertEqual([], paused["completed_tasks"])
        self.assertEqual("start_task", resumed["next_action"]["type"])
        self.assertNotEqual(
            first_action_id,
            resumed["next_action"]["action_id"],
        )

    def test_unbound_runtime_result_pauses_and_blocks_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._record_lifecycle(
                service,
                root,
                service.start("parent"),
                "in_progress",
            )
            state, runtime_id, host_key = self._record_runtime_init(
                service,
                root,
                state,
                bind=False,
            )

            paused = service.record_result(
                state["operation_id"],
                self._payload(
                    state,
                    runtime_context_id=runtime_id,
                    host_context_key=host_key,
                ),
            )

        self.assertEqual("paused", paused["phase"])
        self.assertIn("bound", paused["pause_reason"])
        self.assertEqual([], paused["completed_tasks"])
        self.assertEqual("child-a", paused["current_task"])

    def test_duplicate_failure_result_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            payload = self._payload(
                state,
                outcome="failure",
                detail="Host adapter unavailable",
            )

            paused = service.record_result(
                state["operation_id"],
                payload,
            )
            duplicate = service.record_result(
                state["operation_id"],
                payload,
            )

        self.assertEqual(paused, duplicate)
        self.assertEqual("paused", duplicate["phase"])
        self.assertEqual(1, duplicate["retry_count"]["child-a"])

    def test_missing_runtime_init_field_pauses_with_field_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._record_lifecycle(
                service,
                root,
                service.start("parent"),
                "in_progress",
            )

            paused = service.record_result(
                state["operation_id"],
                self._payload(state, host_context_key="codex_missing"),
            )

        self.assertEqual("paused", paused["phase"])
        self.assertIn("runtime_context_id", paused["pause_reason"])
        self.assertEqual([], paused["completed_tasks"])

    def test_runtime_completion_host_key_mismatch_stays_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._record_lifecycle(
                service,
                root,
                service.start("parent"),
                "in_progress",
            )
            state, runtime_id, host_key = self._record_runtime_init(
                service,
                root,
                state,
            )

            paused = service.record_result(
                state["operation_id"],
                self._payload(
                    state,
                    runtime_context_id=runtime_id,
                    host_context_key=f"{host_key}-wrong",
                ),
            )
            runtime = self.runtime_module.RuntimeContextService(root).load(
                runtime_id
            )

        self.assertEqual("paused", paused["phase"])
        self.assertIn("host_context_key", paused["pause_reason"])
        self.assertEqual("bound", runtime["status"])

    def test_closed_runtime_context_recovers_pending_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._record_lifecycle(
                service,
                root,
                service.start("parent"),
                "in_progress",
            )
            state, runtime_id, host_key = self._record_runtime_init(
                service,
                root,
                state,
            )
            self.runtime_module.RuntimeContextService(root).close(
                runtime_id
            )

            recovered = service.record_result(
                state["operation_id"],
                self._payload(
                    state,
                    runtime_context_id=runtime_id,
                    host_context_key=host_key,
                ),
            )

        self.assertEqual("review_task", recovered["next_action"]["type"])
        self.assertEqual(
            ["start", "implement"],
            recovered["task_phases"]["child-a"],
        )

    def test_resume_rejects_task_graph_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            parent_path = (
                root
                / ".cowork-flow"
                / "tasks"
                / "parent"
                / "task.json"
            )
            parent = json.loads(
                parent_path.read_text(encoding="utf-8")
            )
            parent["children"].append("child-c")
            parent_path.write_text(
                json.dumps(parent, ensure_ascii=False),
                encoding="utf-8",
            )
            self._task(root, "child-c", parent="parent")

            with self.assertRaises(
                self.module.BatchExecutionError
            ) as raised:
                service.resume(state["operation_id"])

        self.assertEqual(
            "BATCH-GRAPH-CHANGED-001",
            raised.exception.code,
        )

    def test_resume_skips_completed_task_and_duplicate_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = self._complete_current_task(
                service,
                root,
                service.start("parent"),
            )
            self.assertEqual("child-b", state["next_action"]["task"])
            self._set_status(root, "child-b", "in_progress")
            payload = self._payload(state, task_status="in_progress")
            state = service.record_result(state["operation_id"], payload)
            expected_action_id = state["next_action"]["action_id"]
            duplicate = service.record_result(
                state["operation_id"],
                payload,
            )
            self.assertEqual(
                expected_action_id,
                duplicate["next_action"]["action_id"],
            )
            state, runtime_id, host_key = self._record_runtime_init(
                service,
                root,
                duplicate,
            )
            paused = service.record_result(
                state["operation_id"],
                self._payload(
                    state,
                    outcome="failure",
                    runtime_context_id=runtime_id,
                    host_context_key=host_key,
                    detail="implementation failed",
                ),
            )

            resumed = service.resume(paused["operation_id"])

        self.assertEqual(["child-a"], resumed["completed_tasks"])
        self.assertEqual(
            {"child-a": "commit-child-a"},
            resumed["commits"],
        )
        self.assertEqual("child-b", resumed["next_action"]["task"])
        self.assertEqual(
            "await_implement_result",
            resumed["next_action"]["type"],
        )

    def test_archive_task_runs_between_complete_and_commit(self) -> None:
        """Verify archive_task appears as next_action after complete_task succeeds."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")

            state = self._advance_to_action(
                service,
                root,
                state,
                "complete_task",
            )
            state = self._record_lifecycle(service, root, state, "completed")

            self.assertEqual("archive_task", state["next_action"]["type"])

    def test_archive_failure_pauses_batch(self) -> None:
        """Verify archive failure transitions state to paused."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            state = self._advance_to_action(
                service,
                root,
                state,
                "archive_task",
            )

            state = service.record_result(
                state["operation_id"],
                self._payload(state, outcome="failure", detail="archive failed"),
            )
            self.assertEqual("paused", state["phase"])
            self.assertIn("archive", state.get("pause_reason", ""))

    def test_archive_success_advances_to_commit(self) -> None:
        """Verify archive success leads to commit_task as next action."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            state = self._advance_to_action(
                service,
                root,
                state,
                "archive_task",
            )

            archive_destination = self._archive_destination(
                root,
                state["next_action"]["task"],
            )
            state = service.record_result(
                state["operation_id"],
                self._payload(
                    state,
                    archive_destination=archive_destination,
                ),
            )
            self.assertEqual("commit_task", state["next_action"]["type"])

    def test_archive_success_requires_archive_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            state = self._advance_to_action(
                service,
                root,
                state,
                "archive_task",
            )

            paused = service.record_result(
                state["operation_id"],
                self._payload(state),
            )

        self.assertEqual("paused", paused["phase"])
        self.assertIn("archive_destination", paused["pause_reason"])

    def test_archive_success_requires_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: True,
            )
            state = service.start("parent")
            state = self._advance_to_action(
                service,
                root,
                state,
                "archive_task",
            )

            paused = service.record_result(
                state["operation_id"],
                self._payload(
                    state,
                    archive_destination=(
                        ".cowork-flow/tasks/archive/2026-07/child-a"
                    ),
                ),
            )

        self.assertEqual("paused", paused["phase"])
        self.assertIn("archive_destination", paused["pause_reason"])
        self.assertIn("does not exist", paused["pause_reason"])

    def test_commit_verification_failure_pauses_without_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._graph(root)
            service = self.module.BatchExecutionService(
                root,
                commit_verifier=lambda _: False,
            )
            state = service.start("parent")
            state = self._advance_to_action(
                service,
                root,
                state,
                "commit_task",
            )

            paused = service.record_result(
                state["operation_id"],
                self._payload(state, commit_id="not-a-real-commit"),
            )

        self.assertEqual("paused", paused["phase"])
        self.assertIn("commit_id", paused["pause_reason"])
        self.assertEqual([], paused["completed_tasks"])
        self.assertEqual({}, paused["commits"])


if __name__ == "__main__":
    import unittest

    unittest.main()
