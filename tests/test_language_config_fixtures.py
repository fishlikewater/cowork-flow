from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "language-config"


class LanguageConfigFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        from infra import config

        cls.config = config
        cls.expected = json.loads(
            (FIXTURES / "expected.json").read_text(encoding="utf-8")
        )

    def test_every_fixture_has_an_expectation(self) -> None:
        names = {path.name for path in FIXTURES.glob("*.yaml")}
        self.assertEqual(names, set(self.expected))

    def test_python_reader_matches_shared_expectations(self) -> None:
        for name, expected in sorted(self.expected.items()):
            with self.subTest(fixture=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    (root / ".cowork-flow").mkdir()
                    shutil.copyfile(
                        FIXTURES / name,
                        root / ".cowork-flow" / "config.yaml",
                    )
                    raw, present, duplicate = self.config._read_language_setting(
                        root
                    )
                self.assertEqual(
                    {"present": present, "raw": raw, "duplicate": duplicate},
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
