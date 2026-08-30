from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from services.context_paths import (  # noqa: E402
    DEFAULT_SCOPE_RULES,
    _is_valid_context_path,
    load_scope_rules,
    normalize_context_file_scope_entry,
)
from services.fact_view import (  # noqa: E402
    build_stage_contract,
    file_scope_whitelist,
)

DEFAULT_RULES_TEXT = json.dumps(
    DEFAULT_SCOPE_RULES, ensure_ascii=False, indent=2
)


def _write_rules(root: Path, payload: dict | str) -> None:
    target = root / ".cowork-flow" / "spec" / "runtime"
    target.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        (target / "scope-rules.json").write_text(payload, encoding="utf-8")
    else:
        (target / "scope-rules.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _write_scope_task(root: Path) -> None:
    task_dir = root / ".cowork-flow" / "tasks" / "08-30-demo"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.json").write_text(
        json.dumps({"status": "in_progress"}), encoding="utf-8"
    )
    (task_dir / "implement.jsonl").write_text(
        "".join(
            json.dumps(entry) + "\n"
            for entry in (
                {"file": "src/a*.py", "reason": "wildcard"},
                {"file": "src/real.py", "reason": "real"},
            )
        ),
        encoding="utf-8",
    )


class ScopeRulesTest(unittest.TestCase):
    """scope-rules.json is the single source for scope filtering and the
    stage-contract limits: python and the JS mirrors consume the same file,
    missing/malformed files degrade to a byte-identical default."""

    def test_default_rules_match_shipped_file(self) -> None:
        shipped = json.loads(
            (ROOT / "template" / ".cowork-flow" / "spec" / "runtime" / "scope-rules.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(DEFAULT_SCOPE_RULES, shipped)

    def test_missing_rules_file_degrades_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules = load_scope_rules(root)
        self.assertEqual(DEFAULT_SCOPE_RULES, rules)

    def test_malformed_rules_file_degrades_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_rules(root, "{not json")
            rules = load_scope_rules(root)
        self.assertEqual(DEFAULT_SCOPE_RULES, rules)

    def test_default_equivalence_no_file_vs_default_content(self) -> None:
        default_outputs = []
        for write_file in (False, True):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                if write_file:
                    _write_rules(root, DEFAULT_RULES_TEXT)
                _write_scope_task(root)
                task_dir = root / ".cowork-flow" / "tasks" / "08-30-demo"
                whitelist = file_scope_whitelist(root, task_dir)
                rules = load_scope_rules(root)
                block = build_stage_contract(
                    ".cowork-flow/tasks/08-30-demo",
                    whitelist,
                    [],
                    {"validationCommands": []},
                    rules=rules,
                )
                default_outputs.append(block)
        self.assertEqual(default_outputs[0], default_outputs[1])

    def test_wildcard_chars_empty_admits_wildcard_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules = json.loads(DEFAULT_RULES_TEXT)
            rules["scopeFilter"]["wildcardChars"] = []
            _write_rules(root, rules)
            _write_scope_task(root)
            task_dir = root / ".cowork-flow" / "tasks" / "08-30-demo"

            whitelist = file_scope_whitelist(root, task_dir)

        files = [entry["file"] for entry in whitelist]
        self.assertIn("src/a*.py", files, "emptied wildcard list must admit it")

    def test_allowed_types_rule_rejects_planned_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules = json.loads(DEFAULT_RULES_TEXT)
            rules["scopeFilter"]["allowedTypes"] = ["file"]
            _write_rules(root, rules)

            normalized, error = normalize_context_file_scope_entry(
                root,
                {"file": "src/next.py", "type": "planned-file"},
            )

        self.assertIsNone(normalized)
        self.assertIn("unsupported type", error or "")

    def test_budget_rule_triggers_trimming(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rules = json.loads(DEFAULT_RULES_TEXT)
            # 400 fits open + Gates + close and forces Scope shrinking
            # (the default 1200 would not trim this fixture).
            rules["stageContract"]["budget"] = 400
            whitelist = [
                {"file": f"src/module-{i}/long-{'x' * 40}-name.py", "type": "file"}
                for i in range(8)
            ]
            block = build_stage_contract(
                ".cowork-flow/tasks/08-30-demo",
                whitelist,
                [],
                {"validationCommands": []},
                rules=rules,
            )

        self.assertLessEqual(len(block), 400)
        self.assertTrue(block.endswith("</stage-contract>"))
        self.assertIn("Gates:", block)
        self.assertIn("Scope: ", block)
        self.assertLess(block.count("; "), 8, "scope entries were shrunk")

    def test_direct_validator_consumes_rules(self) -> None:
        empty_wildcards = {"scopeFilter": {"wildcardChars": []}}
        self.assertTrue(
            _is_valid_context_path(
                "src/a*.py",
                ["src", "a*.py"],
                "src/a*.py",
                "file",
                rules=empty_wildcards,
            ),
            "emptied wildcard list must admit the path in the validator",
        )
        self.assertFalse(
            _is_valid_context_path(
                "src/a*.py",
                ["src", "a*.py"],
                "src/a*.py",
                "file",
            ),
            "default rules still reject wildcards",
        )


if __name__ == "__main__":
    unittest.main()