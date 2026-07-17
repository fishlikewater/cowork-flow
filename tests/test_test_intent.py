from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


from tests.flow_test_support import FlowScriptTestCase, ROOT, SCRIPTS


class TestIntentTest(FlowScriptTestCase):
    def test_cmd_review_blocks_shallow_tdd_test_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            shallow_assert = "self.assert" + "True(True)"
            (tests_dir / "test_noise.py").write_text(
                "import unittest\n\n"
                "class NoiseTest(unittest.TestCase):\n"
                "    def test_noise(self):\n"
                f"        {shallow_assert}\n",
                encoding="utf-8",
            )
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_noise.py",
                "testName": "test_noise",
                "redCommand": "python -m unittest tests.test_noise.NoiseTest.test_noise -v",
                "redExitCode": 1,
                "redOutputExcerpt": "review gate did not block shallow test",
                "failureReason": "test intent gate did not reject a trivial truth assertion",
                "whyThisTestMatters": "It proves shallow tests cannot satisfy TDD review.",
                "greenCommand": "python -m unittest tests.test_noise.NoiseTest.test_noise -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._write_session_task(root)

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(1, result)
            self.assertEqual("in_progress", data["status"])
            self.assertIn("assert " + "True", stderr.getvalue())

    def test_test_intent_warns_without_blocking_ambiguous_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_ambiguous.py").write_text(
                "import unittest\n\n"
                "class AmbiguousTest(unittest.TestCase):\n"
                "    def test_result_exists(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertIsNotNone(result)\n",
                encoding="utf-8",
            )
            (task_dir / "task.json").write_text(
                '{"status": "in_progress", "completedAt": null}\n',
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_ambiguous.py",
                "testName": "test_result_exists",
                "redCommand": "python -m unittest tests.test_ambiguous.AmbiguousTest.test_result_exists -v",
                "redExitCode": 1,
                "redOutputExcerpt": "test intent did not warn on weak assertion",
                "failureReason": "test intent gate did not flag ambiguous assertion depth",
                "whyThisTestMatters": "It proves suspicious-but-not-obviously-empty tests are reviewed without being blocked.",
                "greenCommand": "python -m unittest tests.test_ambiguous.AmbiguousTest.test_result_exists -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            self._write_session_task(root)
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}):
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()) as stderr,
                    ):
                        result = self.task.cmd_review(argparse.Namespace(dir=None))
            finally:
                os.chdir(previous_cwd)

            data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(0, result, stderr.getvalue())
            self.assertEqual("review", data["status"])
            self.assertIn("Warning: Test intent review warnings", stderr.getvalue())
            self.assertIn("assertIsNotNone", stderr.getvalue())

    def test_test_intent_ignores_shallow_fixture_outside_target_test(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_behavior.py").write_text(
                "import unittest\n\n"
                "SHALLOW_FIXTURE = 'self.assertTrue(True)'\n\n"
                "class BehaviorTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            self._write_behavior_prd(task_dir)
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_behavior.py",
                "testName": "test_real_behavior",
                "redCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves fixture text outside the target test does not cause false positives.",
                "greenCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_handles_utf8_bom_when_targeting_test_function(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_behavior.py").write_text(
                "\ufeffimport unittest\n\n"
                "SHALLOW_FIXTURE = 'self.assertTrue(True)'\n\n"
                "class BehaviorTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_behavior.py",
                "testName": "BehaviorTest.test_real_behavior",
                "redCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves UTF-8 BOM does not make test intent scan the whole file.",
                "greenCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_ignores_shallow_marker_inside_fixture_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_behavior.py").write_text(
                "import unittest\n\n"
                "class BehaviorTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        fixture = 'self.assertTrue(True)'\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_behavior.py",
                "testName": "BehaviorTest.test_real_behavior",
                "redCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves fixture strings do not masquerade as shallow test assertions.",
                "greenCommand": "python -m unittest tests.test_behavior.BehaviorTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_accepts_mock_plus_java_assert_equals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            test_file = root / "tests" / "BehaviorTest.java"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "class BehaviorTest {\n"
                "  void testBlocksInvalidState() {\n"
                "    Service service = mock(Service.class);\n"
                "    assertEquals(\"blocked\", result.status());\n"
                "  }\n"
                "}\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/BehaviorTest.java",
                "testName": "testBlocksInvalidState",
                "redCommand": "mvn test -Dtest=BehaviorTest#testBlocksInvalidState",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves Java assertEquals is treated as behavior assertion, not mock-only noise.",
                "greenCommand": "mvn test -Dtest=BehaviorTest#testBlocksInvalidState",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_accepts_mock_plus_assert_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            test_file = root / "tests" / "BehaviorTest.java"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "class BehaviorTest {\n"
                "  void testRejectsInvalidState() {\n"
                "    Service service = mock(Service.class);\n"
                "    assertFalse(result.allowed());\n"
                "  }\n"
                "}\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-002",
                "testFile": "tests/BehaviorTest.java",
                "testName": "testRejectsInvalidState",
                "redCommand": "mvn test -Dtest=BehaviorTest#testRejectsInvalidState",
                "redExitCode": 1,
                "redOutputExcerpt": "target behavior missing",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves assertFalse is treated as behavior assertion, not mock-only noise.",
                "greenCommand": "mvn test -Dtest=BehaviorTest#testRejectsInvalidState",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_flow_script_paths -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            self.assertEqual([], test_intent.validate_test_intent(root, task_dir))

    def test_test_intent_blocks_unresolved_test_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            test_file = root / "tests" / "test_real.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(
                "import unittest\n\n"
                "class RealTest(unittest.TestCase):\n"
                "    def test_real_behavior(self):\n"
                "        result = {'status': 'blocked'}\n"
                "        self.assertEqual('blocked', result['status'])\n",
                encoding="utf-8",
            )
            evidence = {
                "acceptanceId": "AC-001",
                "testFile": "tests/test_real.py",
                "testName": "MissingTest.test_real_behavior",
                "redCommand": "python -m unittest tests.test_real.MissingTest.test_real_behavior -v",
                "redExitCode": 1,
                "redOutputExcerpt": "missing target behavior",
                "failureReason": "target behavior was not implemented",
                "whyThisTestMatters": "It proves evidence points at the exact behavior test.",
                "greenCommand": "python -m unittest tests.test_real.RealTest.test_real_behavior -v",
                "greenExitCode": 0,
                "broaderVerification": "python -m unittest tests.test_real -v",
            }
            (task_dir / "check.jsonl").write_text(
                json.dumps(evidence, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            test_intent = importlib.import_module("common.gates.test_intent")

            violations = test_intent.validate_test_intent(root, task_dir)

            self.assertEqual(["TEST-INTENT-005"], [v["rule_id"] for v in violations])
