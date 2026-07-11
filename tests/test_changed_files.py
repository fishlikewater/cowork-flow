#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for git_context.ChangedFile and get_changed_files."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".cowork-flow" / "scripts"
sys.path.insert(0, str(SCRIPTS))


class TestChangedFileDataclass(unittest.TestCase):
    """Tests for git_context.ChangedFile."""

    def test_creation(self):
        from common.git_context import ChangedFile
        f = ChangedFile(path="src/main.py", statuses=("staged",))
        self.assertEqual(f.path, "src/main.py")
        self.assertEqual(f.statuses, ("staged",))

    def test_frozen(self):
        from common.git_context import ChangedFile
        f = ChangedFile(path="src/main.py", statuses=("modified",))
        with self.assertRaises(AttributeError):
            f.path = "other.py"

    def test_multiple_statuses(self):
        from common.git_context import ChangedFile
        f = ChangedFile(path="src/main.py", statuses=("modified", "staged"))
        self.assertEqual(len(f.statuses), 2)


class TestGetChangedFiles(unittest.TestCase):
    """Tests for git_context.get_changed_files.

    Uses the actual project repo (which is a git repo).
    """

    def test_returns_list(self):
        from common.git_context import get_changed_files
        result = get_changed_files(ROOT)
        self.assertIsInstance(result, list)

    def test_items_are_changed_file(self):
        from common.git_context import ChangedFile, get_changed_files
        result = get_changed_files(ROOT)
        for item in result:
            self.assertIsInstance(item, ChangedFile)
            self.assertIsInstance(item.path, str)
            self.assertIsInstance(item.statuses, tuple)
            self.assertTrue(len(item.path) > 0)
            self.assertTrue(len(item.statuses) > 0)

    def test_known_statuses_only(self):
        from common.git_context import get_changed_files
        result = get_changed_files(ROOT)
        valid = {"staged", "modified", "untracked", "renamed"}
        for item in result:
            for s in item.statuses:
                self.assertIn(s, valid)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
