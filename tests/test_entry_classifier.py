"""Tests for dual-channel entry classifier (COWORK_ENTRY_CONTRACT_V2).

Covers:
  1. Structured signal takes priority over legacy fallback.
  2. Legacy fallback works when structured signal absent + enabled.
  3. Fail-closed (UNKNOWN) when structured signal absent + fallback disabled.
  4. Empty prompt → UNKNOWN.
  5. Signal conflict → structured signal wins.
  6. Opencode-style no-signal → falls back to legacy or UNKNOWN.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Ensure scripts dir is importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".cowork-flow" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from common.entry_classifier import (
    Classification,
    EntryKind,
    _classify_structured,
    _is_legacy_fallback_enabled,
    _legacy_text_fallback,
    classify_entry,
    extract_prompt,
)


class TestStructuredSignalClassification(unittest.TestCase):
    """Channel 1: structured signals from hook_input."""

    def test_session_role_main(self):
        result = _classify_structured({"sessionRole": "main"})
        self.assertIsNotNone(result)
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_session_role_command(self):
        result = _classify_structured({"sessionRole": "command"})
        self.assertIsNotNone(result)
        self.assertEqual(result.entry_kind, EntryKind.COMMAND_ONLY)

    def test_invocation_kind_read_only(self):
        result = _classify_structured({"invocationKind": "read_only"})
        self.assertIsNotNone(result)
        self.assertEqual(result.entry_kind, EntryKind.READ_ONLY)

    def test_invocation_kind_interactive(self):
        result = _classify_structured({"invocationKind": "interactive"})
        self.assertIsNotNone(result)
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)

    def test_no_structured_signals(self):
        result = _classify_structured({})
        self.assertIsNone(result)

    def test_empty_input(self):
        result = _classify_structured({"hook_input": {}})
        self.assertIsNone(result)


class TestLegacyFallback(unittest.TestCase):
    """Channel 2: text heuristic fallback."""

    def test_empty_prompt_unknown(self):
        result = _legacy_text_fallback({})
        self.assertEqual(result.entry_kind, EntryKind.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)

    def test_main_session_terms(self):
        result = _legacy_text_fallback({"prompt": "实现这个功能"})
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)

    def test_read_only_terms(self):
        result = _legacy_text_fallback({"prompt": "explain what this does"})
        self.assertEqual(result.entry_kind, EntryKind.READ_ONLY)

    def test_command_only_terms(self):
        result = _legacy_text_fallback({"prompt": "git status"})
        self.assertEqual(result.entry_kind, EntryKind.COMMAND_ONLY)

    def test_unclassified(self):
        result = _legacy_text_fallback({"prompt": "hello world"})
        self.assertEqual(result.entry_kind, EntryKind.UNKNOWN)


class TestDualChannelClassification(unittest.TestCase):
    """Full classify_entry: structured > fallback > UNKNOWN."""

    def setUp(self):
        # Save original env
        self._orig_fallback_env = os.environ.pop("COWORK_FLOW_LEGACY_FALLBACK", None)

    def tearDown(self):
        # Restore original env
        if self._orig_fallback_env is not None:
            os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = self._orig_fallback_env
        else:
            os.environ.pop("COWORK_FLOW_LEGACY_FALLBACK", None)

    def test_structured_wins_over_legacy(self):
        """Signal conflict: structured says MAIN_SESSION, prompt looks like subagent."""
        result = classify_entry({
            "sessionRole": "main",
            "prompt": "cowork_runtime_context_id: test-123",
        })
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)
        self.assertEqual(result.source, "structured_session_role")

    def test_fallback_enabled_returns_legacy(self):
        """No structured signal + fallback enabled → legacy classification."""
        os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = "1"
        result = classify_entry({"prompt": "实现这个功能"})
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)

    def test_fallback_disabled_returns_unknown(self):
        """No structured signal + fallback disabled → UNKNOWN (fail-closed)."""
        os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = "0"
        result = classify_entry({"prompt": "实现这个功能"})
        self.assertEqual(result.entry_kind, EntryKind.UNKNOWN)
        self.assertEqual(result.source, "no_signal_fallback_disabled")

    def test_empty_prompt_fallback_disabled(self):
        """Empty prompt + fallback disabled → UNKNOWN."""
        os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = "0"
        result = classify_entry({})
        self.assertEqual(result.entry_kind, EntryKind.UNKNOWN)

    def test_fallback_default_is_enabled(self):
        """Default (no env override) should enable fallback."""
        os.environ.pop("COWORK_FLOW_LEGACY_FALLBACK", None)
        self.assertTrue(_is_legacy_fallback_enabled())

    def test_opencode_no_signal_fallback(self):
        """Opencode-style input with no structured signals uses fallback."""
        result = classify_entry({"prompt": "继续做下去"})
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)

    def test_command_structured(self):
        """Structured command signal."""
        result = classify_entry({"sessionRole": "command"})
        self.assertEqual(result.entry_kind, EntryKind.COMMAND_ONLY)

    def test_read_only_structured(self):
        """Structured read-only signal."""
        result = classify_entry({"invocationKind": "read_only"})
        self.assertEqual(result.entry_kind, EntryKind.READ_ONLY)


class TestEnvOverride(unittest.TestCase):
    """Environment variable overrides for fallback toggle."""

    def setUp(self):
        self._orig = os.environ.pop("COWORK_FLOW_LEGACY_FALLBACK", None)

    def tearDown(self):
        if self._orig is not None:
            os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = self._orig
        else:
            os.environ.pop("COWORK_FLOW_LEGACY_FALLBACK", None)

    def test_env_disable_fallback(self):
        os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = "0"
        self.assertFalse(_is_legacy_fallback_enabled())
        result = classify_entry({"prompt": "实现这个功能"})
        self.assertEqual(result.entry_kind, EntryKind.UNKNOWN)

    def test_env_enable_fallback(self):
        os.environ["COWORK_FLOW_LEGACY_FALLBACK"] = "1"
        self.assertTrue(_is_legacy_fallback_enabled())
        result = classify_entry({"prompt": "实现这个功能"})
        self.assertEqual(result.entry_kind, EntryKind.MAIN_SESSION)


if __name__ == "__main__":
    unittest.main()
