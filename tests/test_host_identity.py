from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
MANIFEST = (
    ROOT
    / "template"
    / ".cowork-flow"
    / "spec"
    / "runtime"
    / "host-assets.json"
)


class HostIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.host_identity = importlib.import_module("runtime.host_identity")

    def _cleanup_imports(self) -> None:
        sys.modules.pop("runtime.host_identity", None)

    def test_registry_ids_match_host_asset_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest_ids = {platform["id"] for platform in manifest["platforms"]}
        self.assertEqual(manifest_ids, set(self.host_identity.host_ids()))

    def test_detect_host_returns_none_without_evidence(self) -> None:
        self.assertIsNone(self.host_identity.detect_host({}))

    def test_detect_host_maps_each_session_env_var(self) -> None:
        cases = (
            ("ZCODE_SESSION_ID", "zcode"),
            ("OPENCODE_SESSION_ID", "opencode"),
            ("CLAUDE_SESSION_ID", "claude-code"),
            ("CLAUDE_CODE_SESSION_ID", "claude-code"),
            ("CODEX_SESSION_ID", "codex"),
            ("CODEX_THREAD_ID", "codex"),
            ("DSH_SESSION_ID", "dsh"),
        )
        for env_name, expected_host in cases:
            with self.subTest(env_name=env_name):
                self.assertEqual(
                    expected_host,
                    self.host_identity.detect_host({env_name: "sess-1"}),
                )

    def test_generic_session_keys_are_ambiguous(self) -> None:
        self.assertIsNone(self.host_identity.sole_owner_of("session_id"))
        self.assertIsNone(self.host_identity.sole_owner_of("sessionId"))
        self.assertEqual(
            {"session_id", "sessionId"},
            set(self.host_identity.ambiguous_input_keys()),
        )

    def test_claude_declares_the_generic_session_key_without_owning_it(self) -> None:
        # claude payloads carry session_id, so the row must declare it — but
        # codex and zcode declare it too, so claude may never resolve it alone.
        claude = self.host_identity.identity_for("claude-code")
        self.assertEqual(
            (
                "CLAUDE_SESSION_ID",
                "claude_session_id",
                "CLAUDE_CODE_SESSION_ID",
                "claude_code_session_id",
                "session_id",
            ),
            claude.input_keys,
        )
        self.assertEqual(
            (
                "CLAUDE_SESSION_ID",
                "claude_session_id",
                "CLAUDE_CODE_SESSION_ID",
                "claude_code_session_id",
            ),
            self.host_identity.sole_owned_input_keys("claude-code"),
        )

    def test_host_specific_keys_have_a_single_owner(self) -> None:
        cases = (
            ("sessionID", "opencode"),
            ("thread_id", "codex"),
            ("conversation_id", "codex"),
            ("codex_session_id", "codex"),
            ("zcode_session_id", "zcode"),
            ("opencode_session_id", "opencode"),
            ("claude_session_id", "claude-code"),
            ("claude_code_session_id", "claude-code"),
        )
        for key, expected_host in cases:
            with self.subTest(key=key):
                self.assertEqual(expected_host, self.host_identity.sole_owner_of(key))

    def test_sole_owned_keys_exclude_the_ambiguous_ones(self) -> None:
        codex = self.host_identity.identity_for("codex")
        self.assertEqual(
            tuple(key for key in codex.input_keys if key != "session_id"),
            self.host_identity.sole_owned_input_keys("codex"),
        )

        zcode = self.host_identity.identity_for("zcode")
        self.assertEqual(
            tuple(
                key
                for key in zcode.input_keys
                if key not in {"sessionId", "session_id"}
            ),
            self.host_identity.sole_owned_input_keys("zcode"),
        )

    def test_dsh_declares_no_payload_keys(self) -> None:
        self.assertEqual((), self.host_identity.sole_owned_input_keys("dsh"))

    def test_kimi_code_declares_the_generic_session_key_without_owning_it(
        self,
    ) -> None:
        # Kimi Code hook payloads carry only the generic session_id, shared
        # with codex and claude-code, so the row may declare it and still
        # never resolve it alone. Its Bash tool exports no session id, so no
        # env var may claim the host either.
        kimi = self.host_identity.identity_for("kimi-code")
        self.assertEqual("kimi", kimi.prefix)
        self.assertEqual(("session_id",), kimi.input_keys)
        self.assertEqual((), kimi.session_env)
        self.assertEqual(
            (), self.host_identity.sole_owned_input_keys("kimi-code")
        )
        self.assertEqual(
            "kimi-code", self.host_identity.identity_for_prefix("kimi").id
        )

    def test_adapter_labels_are_preserved(self) -> None:
        self.assertEqual(
            {
                "zcode": "zcode.plugin",
                "claude-code": "claude-code.hooks",
                "codex": "codex.spawn_agent",
                "dsh": "dsh.preset",
                "kimi-code": "kimi-code.hooks",
            },
            self.host_identity.context_adapters(),
        )
        self.assertEqual(
            "opencode.task",
            self.host_identity.identity_for("opencode").adapter,
        )

    def test_prefix_mapping_keeps_the_claude_quirk(self) -> None:
        self.assertEqual(
            "claude-code",
            self.host_identity.identity_for_prefix("claude").id,
        )
        self.assertEqual(
            "codex",
            self.host_identity.identity_for_prefix("codex").id,
        )


if __name__ == "__main__":
    unittest.main()
