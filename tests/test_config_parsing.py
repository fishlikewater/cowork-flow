from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "template" / ".cowork-flow" / "scripts"


class ConfigInlineCommentTest(unittest.TestCase):
    """Inline comments in .cowork-flow/config.yaml.

    `#` starts a comment only outside quotes and only when it opens a token;
    a `#` glued to a word or sitting inside quotes is part of the value.
    """

    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.config = importlib.import_module("infra.config")

    def _cleanup_imports(self) -> None:
        for module_name in ("infra.config", "infra.paths"):
            sys.modules.pop(module_name, None)

    def _parse(self, content: str) -> dict:
        return self.config._parse_simple_yaml(content)

    def test_hash_inside_double_quotes_is_literal(self) -> None:
        self.assertEqual({"description": "a # b"}, self._parse('description: "a # b"\n'))

    def test_hash_inside_single_quotes_is_literal(self) -> None:
        self.assertEqual({"description": "a # b"}, self._parse("description: 'a # b'\n"))

    def test_quoted_url_fragment_survives(self) -> None:
        self.assertEqual(
            {"url": "http://example.test/#anchor"},
            self._parse('url: "http://example.test/#anchor"\n'),
        )

    def test_quoted_value_starting_with_hash_is_not_a_section(self) -> None:
        parsed = self._parse('note: "# keep"\n  stray: swallowed\nnext: 1\n')

        self.assertEqual({"note": "# keep", "next": "1"}, parsed)

    def test_hash_glued_to_a_word_is_literal(self) -> None:
        self.assertEqual({"tag": "v1#beta"}, self._parse("tag: v1#beta\n"))

    def test_apostrophe_does_not_open_a_quoted_region(self) -> None:
        parsed = self._parse("description: Sam's project  # owner\n")

        self.assertEqual({"description": "Sam's project"}, parsed)

    def test_stray_double_quote_does_not_open_a_quoted_region(self) -> None:
        parsed = self._parse('note: say "hi  # note\n')

        self.assertEqual({"note": 'say "hi'}, parsed)

    def test_escaped_quote_does_not_close_the_quoted_region(self) -> None:
        # The backslash itself is not unescaped (out of scope for this parser);
        # the point is that the `#` after it stays inside the value.
        self.assertEqual(
            {"cmd": 'say \\" then # x'},
            self._parse('cmd: "say \\" then # x"\n'),
        )

    def test_trailing_comment_after_whitespace_is_still_stripped(self) -> None:
        parsed = self._parse("codex:\n  dispatch_mode: inline  # note\n")

        self.assertEqual({"codex": {"dispatch_mode": "inline"}}, parsed)

    def test_hash_at_line_start_still_comments_the_whole_line(self) -> None:
        parsed = self._parse("# comment\nkey: value\n")

        self.assertEqual({"key": "value"}, parsed)

    def test_bare_hash_still_marks_an_empty_value(self) -> None:
        parsed = self._parse("party_mode_v2:  # note\n  min_agents: 4\n")

        self.assertEqual({"party_mode_v2": {"min_agents": "4"}}, parsed)

    def test_list_item_keeps_hash_inside_quotes(self) -> None:
        parsed = self._parse('hooks:\n  after_create:\n    - "python x.py --arg a#b"\n')

        self.assertEqual(
            {"hooks": {"after_create": ["python x.py --arg a#b"]}},
            parsed,
        )

    def test_list_item_drops_a_trailing_comment(self) -> None:
        parsed = self._parse('hooks:\n  after_create:\n    - "python x.py"  # note\n')

        self.assertEqual({"hooks": {"after_create": ["python x.py"]}}, parsed)

    def test_unquoted_list_item_drops_a_trailing_comment(self) -> None:
        parsed = self._parse("hooks:\n  after_create:\n    - python x.py  # note\n")

        self.assertEqual({"hooks": {"after_create": ["python x.py"]}}, parsed)


class ConfigHookCommandsTest(unittest.TestCase):
    """The same rule reached through the public config entry point."""

    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.config = importlib.import_module("infra.config")
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)

    def _cleanup_imports(self) -> None:
        for module_name in ("infra.config", "infra.paths"):
            sys.modules.pop(module_name, None)

    def _write_config(self, content: str) -> None:
        workflow_dir = self.root / ".cowork-flow"
        workflow_dir.mkdir(exist_ok=True)
        (workflow_dir / "config.yaml").write_text(content, encoding="utf-8")

    def test_hook_command_hash_argument_survives(self) -> None:
        self._write_config(
            'hooks:\n  after_finish:\n    - "python hook.py --color #ff8800"\n'
        )

        self.assertEqual(
            ["python hook.py --color #ff8800"],
            self.config.get_hooks("after_finish", self.root),
        )

    def test_hook_command_trailing_comment_is_dropped(self) -> None:
        self._write_config(
            'hooks:\n  after_create:\n    - "python hook.py"  # keep in sync with docs\n'
        )

        self.assertEqual(
            ["python hook.py"],
            self.config.get_hooks("after_create", self.root),
        )

    def test_dispatch_mode_ignores_a_trailing_comment(self) -> None:
        self._write_config('codex:\n  dispatch_mode: "inline"  # override\n')

        self.assertEqual("inline", self.config.get_codex_dispatch_mode(self.root))


if __name__ == "__main__":
    unittest.main()
