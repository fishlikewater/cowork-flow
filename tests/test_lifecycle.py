#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for lifecycle.py — state machine transitions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import lifecycle


class TestTransitionAllowed(unittest.TestCase):
    """Tests for lifecycle.transition_allowed."""

    def test_planning_to_in_progress(self):
        self.assertTrue(lifecycle.transition_allowed("planning", "in_progress"))

    def test_in_progress_to_review(self):
        self.assertTrue(lifecycle.transition_allowed("in_progress", "review"))

    def test_review_to_completed(self):
        self.assertTrue(lifecycle.transition_allowed("review", "completed"))

    def test_review_to_in_progress_roundtrip(self):
        self.assertTrue(lifecycle.transition_allowed("review", "in_progress"))

    def test_completed_to_archived(self):
        self.assertTrue(lifecycle.transition_allowed("completed", "archived"))

    def test_archived_to_completed_unarchive(self):
        self.assertTrue(lifecycle.transition_allowed("archived", "completed"))

    def test_any_to_blocked(self):
        self.assertTrue(lifecycle.transition_allowed("planning", "blocked"))
        self.assertTrue(lifecycle.transition_allowed("in_progress", "blocked"))
        self.assertTrue(lifecycle.transition_allowed("review", "blocked"))

    def test_blocked_to_in_progress(self):
        self.assertTrue(lifecycle.transition_allowed("blocked", "in_progress"))

    def test_same_status_not_allowed(self):
        self.assertFalse(lifecycle.transition_allowed("in_progress", "in_progress"))

    def test_invalid_transition(self):
        self.assertFalse(lifecycle.transition_allowed("planning", "completed"))
        self.assertFalse(lifecycle.transition_allowed("planning", "archived"))
        self.assertFalse(lifecycle.transition_allowed("completed", "in_progress"))
        self.assertFalse(lifecycle.transition_allowed("archived", "planning"))


class TestTransitionBlockers(unittest.TestCase):
    """Tests for lifecycle.transition_blockers."""

    def test_valid_returns_empty(self):
        self.assertEqual(lifecycle.transition_blockers("planning", "in_progress"), [])

    def test_invalid_returns_message(self):
        result = lifecycle.transition_blockers("planning", "completed")
        self.assertTrue(len(result) > 0)
        self.assertIn("Cannot transition", result[0])

    def test_same_status_message(self):
        result = lifecycle.transition_blockers("in_progress", "in_progress")
        self.assertTrue(len(result) > 0)
        self.assertIn("already in", result[0])


class TestGetAvailableTransitions(unittest.TestCase):
    """Tests for lifecycle.get_available_transitions."""

    def test_planning(self):
        result = lifecycle.get_available_transitions("planning")
        self.assertIn("in_progress", result)
        self.assertIn("blocked", result)
        self.assertNotIn("planning", result)

    def test_completed(self):
        result = lifecycle.get_available_transitions("completed")
        self.assertIn("archived", result)

    def test_blocked(self):
        result = lifecycle.get_available_transitions("blocked")
        self.assertIn("in_progress", result)
        self.assertIn("review", result)


class TestTerminalStatus(unittest.TestCase):
    """Tests for lifecycle.is_terminal."""

    def test_non_terminal(self):
        self.assertFalse(lifecycle.is_terminal("planning"))
        self.assertFalse(lifecycle.is_terminal("in_progress"))

    def test_archived_is_terminal(self):
        # archived can still un-archive, so not terminal
        self.assertFalse(lifecycle.is_terminal("archived"))


class TestStatusMetadata(unittest.TestCase):
    """Tests for lifecycle status metadata."""

    def test_known_statuses(self):
        for status in ("planning", "in_progress", "review", "completed", "archived", "blocked"):
            label = lifecycle.get_status_label(status)
            self.assertIsInstance(label, str)
            self.assertTrue(len(label) > 0)

    def test_unknown_status(self):
        self.assertEqual(lifecycle.get_status_label("unknown_status"), "unknown_status")

    def test_metadata_complete(self):
        for status, meta in lifecycle.STATUS_METADATA.items():
            self.assertIn("label", meta)
            self.assertIn("description", meta)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
