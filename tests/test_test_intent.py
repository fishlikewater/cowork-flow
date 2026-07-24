from __future__ import annotations

import importlib
import sys
import unittest

from tests.flow_test_support import SCRIPTS


class TestIntentTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.test_intent = importlib.import_module("common.gates.test_intent")

    def _cleanup_imports(self) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
        sys.modules.pop("common.gates.test_intent", None)

    def test_validate_test_intent_no_longer_reads_task_evidence(self) -> None:
        self.assertEqual([], self.test_intent.validate_test_intent(object(), object()))

    def test_classifier_blocks_shallow_assertions(self) -> None:
        content = (
            "import unittest\n\n"
            "class NoiseTest(unittest.TestCase):\n"
            "    def test_noise(self):\n"
            "        self.assertTrue(True)\n"
        )

        self.assertEqual(
            "block",
            self.test_intent.classify_test_content(content, "NoiseTest.test_noise"),
        )

    def test_classifier_warns_for_ambiguous_assertions(self) -> None:
        content = (
            "import unittest\n\n"
            "class AmbiguousTest(unittest.TestCase):\n"
            "    def test_result_exists(self):\n"
            "        result = {'status': 'blocked'}\n"
            "        self.assertIsNotNone(result)\n"
        )

        self.assertEqual(
            "warn",
            self.test_intent.classify_test_content(content, "AmbiguousTest.test_result_exists"),
        )

    def test_classifier_passes_meaningful_assertions(self) -> None:
        content = (
            "import unittest\n\n"
            "class BehaviorTest(unittest.TestCase):\n"
            "    def test_status_transition(self):\n"
            "        result = {'status': 'review'}\n"
            "        self.assertEqual('review', result['status'])\n"
        )

        self.assertEqual(
            "pass",
            self.test_intent.classify_test_content(content, "BehaviorTest.test_status_transition"),
        )


if __name__ == "__main__":
    unittest.main()
