from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TaskBoardTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.board = importlib.import_module("services.task_board")
        self.tree_commands = importlib.import_module(
            "adapters.cli.task_tree_commands"
        )

    def _cleanup_imports(self) -> None:
        for name in (
            "services.task_board",
            "services.task_graph",
            "services.ac_evidence",
            "adapters.cli.task_tree_commands",
            "services.task_tree",
            "services.task_repository",
            "services.task_utils",
            "runtime.session_state",
            "infra.paths",
            "infra.files",
            "common",
        ):
            sys.modules.pop(name, None)

    @staticmethod
    def _write_task(root: Path, name: str, **data) -> Path:
        task_dir = root / ".cowork-flow" / "tasks" / name
        task_dir.mkdir(parents=True, exist_ok=True)
        payload = {"id": name, "name": name, "title": name, "status": "in_progress"}
        payload.update(data)
        (task_dir / "task.json").write_text(json.dumps(payload), encoding="utf-8")
        return task_dir

    @staticmethod
    def _bind_session(root: Path, context_key: str, task_name: str) -> None:
        sessions = root / ".cowork-flow" / ".runtime" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / f"{context_key}.json").write_text(
            json.dumps(
                {
                    "active_task_path": f".cowork-flow/tasks/{task_name}",
                    "scope": "main",
                }
            ),
            encoding="utf-8",
        )

    def test_board_facts_track_owner_and_session_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            owned = self._write_task(root, "10-01-owned", executor="session-a")
            unowned = self._write_task(root, "10-02-unowned")
            self._bind_session(root, "session-a", "10-01-owned")

            owned_facts = self.board.board_facts(root, owned)
            self.assertEqual("session-a", owned_facts["executor"])
            self.assertTrue(owned_facts["ownerSessionActive"])

            unowned_facts = self.board.board_facts(root, unowned)
            self.assertIsNone(unowned_facts["executor"])
            self.assertFalse(unowned_facts["ownerSessionActive"])

            # A session working by explicit dir (never bound) keeps the hint
            # false without meaning the task is orphaned.
            (root / ".cowork-flow" / ".runtime" / "sessions" / "session-a.json").unlink()
            self.assertFalse(
                self.board.board_facts(root, owned)["ownerSessionActive"]
            )

    def test_board_facts_carry_evidence_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            no_anchor = self._write_task(root, "10-01-plain")
            self.assertIsNone(self.board.board_facts(root, no_anchor)["evidenceCoverage"])

            with_ac = self._write_task(root, "10-02-evidenced")
            (with_ac / "decision-anchor.md").write_text(
                "# Demo\n\n## 目标\n\nBoard.\n\n## 验收标准\n\n"
                "- [x] AC-001: Covered.\n- [ ] AC-002: Pending.\n",
                encoding="utf-8",
            )
            (with_ac / "evidence.jsonl").write_text(
                json.dumps(
                    {
                        "ac": "AC-001",
                        "kind": "test",
                        "ref": "tests/test_task_board.py",
                        "recordedAt": "2026-10-09",
                        "by": "tester",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                {"total": 2, "withEvidence": 1, "missing": ["AC-002"]},
                self.board.board_facts(root, with_ac)["evidenceCoverage"],
            )

    def test_board_facts_report_dependency_blockage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_task(root, "10-01-active", status="in_progress")
            self._write_task(root, "10-02-done", status="completed")
            blocked = self._write_task(
                root,
                "10-03-blocked",
                dependsOn=["10-01-active", "10-02-done"],
            )
            free = self._write_task(root, "10-04-free", dependsOn=["10-02-done"])

            blocked_facts = self.board.board_facts(root, blocked)
            self.assertTrue(blocked_facts["blocked"])
            self.assertEqual(["10-01-active"], blocked_facts["blockedBy"])

            free_facts = self.board.board_facts(root, free)
            self.assertFalse(free_facts["blocked"])
            self.assertEqual([], free_facts["blockedBy"])

    def test_cli_list_and_mcp_task_list_share_board_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_task(root, "10-01-active", status="in_progress")
            self._write_task(
                root,
                "10-02-feature",
                status="planning",
                executor="session-a",
                dependsOn=["10-01-active"],
            )
            self._bind_session(root, "session-a", "10-02-feature")

            records, error = self.tree_commands._list_task_records(
                root, mine=False, status=None
            )
            self.assertIsNone(error)
            by_name = {record["name"]: record for record in records}
            feature = by_name["10-02-feature"]
            self.assertEqual("session-a", feature["executor"])
            self.assertTrue(feature["ownerSessionActive"])
            self.assertTrue(feature["blocked"])
            self.assertEqual(["10-01-active"], feature["blockedBy"])
            self.assertIn("evidenceCoverage", feature)

            state_server = importlib.import_module("adapters.mcp.state_server")
            payload = state_server._tool_task_list(root, {})
            mcp_by_name = {task["name"]: task for task in payload["tasks"]}
            self.assertEqual(len(by_name), payload["count"])
            self.assertEqual(
                {name: record["blockedBy"] for name, record in by_name.items()},
                {
                    name: task["blockedBy"]
                    for name, task in mcp_by_name.items()
                },
                "both surfaces must render the same board facts",
            )
            self.assertEqual(
                feature["executor"],
                mcp_by_name["10-02-feature"]["executor"],
            )


if __name__ == "__main__":
    unittest.main()
