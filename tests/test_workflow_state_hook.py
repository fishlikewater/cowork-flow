from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
HOOK_PATH = (
    SCRIPTS
    / "adapters"
    / "host"
    / "workflow_state_hook.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "workflow_state_hook_under_test", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_workflow_spec(root: Path) -> None:
    templates = root / ".cowork-flow" / "spec" / "contracts"
    templates.mkdir(parents=True)
    (templates / "workflow-state-templates.md").write_text(
        "\n".join(
            [
                "[workflow-state:no_task]",
                "STOP - no active task.",
                "[/workflow-state:no_task]",
                "",
                "[workflow-state:in_progress]",
                "活动任务正在执行。",
                "[/workflow-state:in_progress]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    registry_dir = root / ".cowork-flow" / "spec" / "runtime"
    registry_dir.mkdir(parents=True)
    (registry_dir / "contract-registry.json").write_text(
        json.dumps({"schemaVersion": 1, "contracts": []}), encoding="utf-8"
    )


class WorkflowStateHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module()

    def test_no_active_task_renders_no_task_breadcrumb_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workflow_spec(root)

            context = self.module.build_hook_context(
                root,
                {},
                host="codex",
                adapter="codex.hook",
                preamble=(),
            )

        self.assertIn("<workflow-state>", context)
        self.assertIn("Status: no_task", context)
        self.assertIn("STOP - no active task.", context)
        self.assertIn('<cowork-runtime host="codex" adapter="codex.hook">', context)
        self.assertIn('fingerprint="', context)

    def test_bound_session_renders_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workflow_spec(root)
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "probe.json").write_text(
                json.dumps(
                    {
                        "active_task_path": ".cowork-flow/tasks/07-10-demo",
                        "scope": "main",
                        "platform": "zcode",
                        "last_seen_at": "2026-07-10T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            task_dir = root / ".cowork-flow" / "tasks" / "07-10-demo"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"status": "in_progress"}', encoding="utf-8"
            )

            context = self.module.build_hook_context(
                root,
                {"COWORK_FLOW_CONTEXT_ID": "probe"},
                host="codex",
                adapter="codex.hook",
                preamble=(),
            )

        self.assertIn("Task: .cowork-flow/tasks/07-10-demo", context)
        self.assertIn("Status: in_progress", context)
        self.assertIn("活动任务正在执行。", context)

    def test_invalid_runtime_context_renders_guard_rail_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workflow_spec(root)

            context = self.module.build_hook_context(
                root,
                {"COWORK_FLOW_RUNTIME_CONTEXT_ID": "rtx-missing"},
                host="codex",
                adapter="codex.hook",
                preamble=(),
            )

        self.assertIn("Status: delegated_subtask", context)
        self.assertIn("Runtime context is missing, closed, or invalid.", context)

    def test_session_start_emits_full_digest_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workflow_spec(root)

            context = self.module.build_hook_context(
                root,
                {},
                host="codex",
                adapter="codex.hook",
                preamble=(),
                session_start=True,
            )

        self.assertIn('<cowork-runtime host="codex" adapter="codex.hook">', context)
        self.assertIn("<contract-digest fingerprint=", context)
        self.assertIn("<workflow-state>", context)

    def test_non_session_start_emits_fingerprint_line_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workflow_spec(root)

            context = self.module.build_hook_context(
                root,
                {},
                host="codex",
                adapter="codex.hook",
                preamble=(),
                session_start=False,
            )

        self.assertRegex(context, r'<contract-fingerprint value="[a-f0-9]{16}"/>')
        self.assertNotIn("<contract-digest", context)
        self.assertNotIn("<cowork-runtime", context)
        self.assertIn("<workflow-state>", context)

    def test_auto_shape_uses_session_state_file_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_workflow_spec(root)
            sessions = root / ".cowork-flow" / ".runtime" / "sessions"
            sessions.mkdir(parents=True)
            (sessions / "probe.json").write_text(
                json.dumps({"active_task_path": ".cowork-flow/tasks/07-10-demo"}),
                encoding="utf-8",
            )

            # No event signal + existing session state file -> slim.
            started = self.module.build_hook_context(
                root,
                {"COWORK_FLOW_CONTEXT_ID": "probe"},
                host="codex",
                adapter="codex.hook",
                preamble=(),
            )
            self.assertRegex(
                started,
                r'<contract-fingerprint value="[a-f0-9]{16}"/>',
            )
            self.assertNotIn("<contract-digest", started)

            # No event signal + no session state file -> full (first injection).
            (sessions / "probe.json").unlink()
            fresh = self.module.build_hook_context(
                root,
                {"COWORK_FLOW_CONTEXT_ID": "probe"},
                host="codex",
                adapter="codex.hook",
                preamble=(),
            )
            self.assertIn("<contract-digest fingerprint=", fresh)


if __name__ == "__main__":
    unittest.main()
