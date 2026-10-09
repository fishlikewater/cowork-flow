from __future__ import annotations

import importlib
import sys
import unittest

from tests.flow_test_support import SCRIPTS


class TestIntentTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.test_intent = importlib.import_module("adapters.review.test_intent")

    def _cleanup_imports(self) -> None:
        sys.modules.pop("adapters.review.test_intent", None)

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

    def test_multiline_docstring_closing_with_non_ascii_is_classified(self) -> None:
        content = (
            "import unittest\n\n"
            "class DocTest(unittest.TestCase):\n"
            "    def test_non_ascii_docstring(self):\n"
            '        """head\n'
            '        tail — dash."""\n'
            "        result = {'status': 'review'}\n"
            "        self.assertEqual('review', result['status'])\n"
        )

        self.assertEqual(
            "pass",
            self.test_intent.classify_test_content(
                content, "DocTest.test_non_ascii_docstring"
            ),
        )

    def test_assigned_multiline_string_with_non_ascii_is_classified(self) -> None:
        content = (
            "import unittest\n\n"
            "class AssignedTest(unittest.TestCase):\n"
            "    def test_non_ascii_assigned_string(self):\n"
            '        note = """第一行\n'
            '        第二行——破折号"""\n'
            "        result = {'status': 'review', 'note': note}\n"
            "        self.assertEqual('review', result['status'])\n"
        )

        self.assertEqual(
            "pass",
            self.test_intent.classify_test_content(
                content, "AssignedTest.test_non_ascii_assigned_string"
            ),
        )

    def test_literal_content_is_still_stripped(self) -> None:
        content = (
            "import unittest\n\n"
            "class LiteralTest(unittest.TestCase):\n"
            "    def test_literal_markers_are_ignored(self):\n"
            "        note = 'mock-only assertion'\n"
            "        result = {'status': 'review'}\n"
            "        self.assertEqual('review', result['status'])\n"
        )

        self.assertEqual(
            "pass",
            self.test_intent.classify_test_content(
                content, "LiteralTest.test_literal_markers_are_ignored"
            ),
        )


if __name__ == "__main__":
    unittest.main()
