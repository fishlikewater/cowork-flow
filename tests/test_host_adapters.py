from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_BOUNDARY = "entry" + "-boundary"
LEGACY_DISPATCH = "COWORK_" + "DISPATCH_V1"
LEGACY_ACK = "COWORK_" + "ACK"
CLAUDE_HOOK_COMMAND = (
    '"${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run" python '
    '"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/inject-workflow-state.py"'
)


def parse_simple_yaml(path: Path) -> dict[str, object]:
    data: dict[str, object] = {}
    current: dict[str, object] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = raw_line.strip()
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if indent == 0:
            if value:
                data[key] = _parse_scalar(value)
                current = None
            else:
                section: dict[str, object] = {}
                data[key] = section
                current = section
        elif indent == 2 and current is not None:
            current[key] = _parse_scalar(value)

    return data


def _parse_scalar(value: str) -> object:
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdecimal():
        return int(value)
    return value


class HostAdaptersTest(unittest.TestCase):
    def test_adapter_schema_declares_capability_enum(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "spec" / "schemas" / "adapter.schema.json",
            ROOT / "template" / ".cowork-flow" / "spec" / "schemas" / "adapter.schema.json",
        ):
            schema = json.loads(path.read_text(encoding="utf-8"))
            enum = schema["$defs"]["capability"]["enum"]
            self.assertEqual(
                ["native", "shim", "plugin", "external", "experimental", "unsupported"],
                enum,
            )

    def test_host_adapters_match_contract(self) -> None:
        for base in (
            ROOT / ".cowork-flow" / "adapters",
            ROOT / "template" / ".cowork-flow" / "adapters",
        ):
            for host in ("codex", "opencode", "claude-code"):
                adapter = parse_simple_yaml(base / host / "adapter.yaml")
                self.assertEqual(1, adapter["schemaVersion"])
                self.assertEqual(host, adapter["host"])
                self.assertEqual("inline_or_manual", adapter["fallback"]["whenRequiredCapabilityMissing"])

                capabilities = adapter["capabilities"]
                self.assertEqual("shim", capabilities["runtimeContextBinding"])
                for key in (
                    "dispatchSubagent",
                    "freshChildContext",
                    "sendFollowup",
                    "waitChild",
                    "listChildren",
                    "cancelChild",
                    "stateInjection",
                    "backgroundChild",
                    "runtimeContextDispatch",
                    "runtimeContextBinding",
                    "runtimeContextCleanup",
                ):
                    self.assertIn(capabilities[key], {"native", "shim", "plugin", "external", "experimental"})

                contracts = adapter["contracts"]
                self.assertNotIn("entry", contracts)
                self.assertEqual("RUNTIME_CONTEXT_DISPATCH_V2", contracts["dispatch"])
                self.assertIs(contracts["leafExecutor"], True)
                runtime_context = adapter["runtimeContext"]
                self.assertEqual("cowork_runtime_context_id", runtime_context["promptKey"])
                self.assertEqual("COWORK_FLOW_RUNTIME_CONTEXT_ID", runtime_context["envKey"])
                self.assertEqual("cowork_runtime_context_id", runtime_context["metadataKey"])
                self.assertEqual("fail_closed", adapter["fallback"]["whenRuntimeContextMissing"])
                if host == "claude-code":
                    self.assertEqual(".claude/skills", adapter["dispatch"]["skillsPath"])
                    self.assertEqual(".claude/settings.json", adapter["dispatch"]["settingsPath"])
                    self.assertEqual(".claude/hooks", adapter["dispatch"]["hooksPath"])

    def test_party_mode_v2_action_schema_is_host_neutral(self) -> None:
        expected_actions = {
            "dispatch_child",
            "send_control_message",
            "wait_children",
            "list_children",
            "close_child",
            "report_to_user",
        }
        banned_primitives = (
            "spawn_agent",
            "followup_task",
            "send_message",
            "wait_agent",
            "list_agents",
            "close_agent",
            "Claude Task",
            "OpenCode task primitive",
            "codex exec",
        )
        for path in (
            ROOT / ".cowork-flow" / "spec" / "schemas" / "party-mode-v2-actions.schema.json",
            ROOT / "template" / ".cowork-flow" / "spec" / "schemas" / "party-mode-v2-actions.schema.json",
        ):
            text = path.read_text(encoding="utf-8")
            schema = json.loads(text)
            actions = set(schema["$defs"]["action"]["properties"]["type"]["enum"])
            self.assertEqual(expected_actions, actions)
            self.assertFalse(
                set(schema["$defs"]["action"]["properties"]) - {
                    "action_id",
                    "type",
                    "agent_id",
                    "agent_ids",
                    "agent_kind",
                    "lens",
                    "message_kind",
                    "prompt_file",
                    "reason",
                }
            )
            self.assertIn("action_id", schema["$defs"]["action"]["required"])
            rendered = json.dumps(schema, ensure_ascii=False)
            for required in (
                "dispatch_child",
                "send_control_message",
                "wait_children",
                "close_child",
                "report_to_user",
                "prompt_file",
                "agent_ids",
            ):
                self.assertIn(required, rendered)
            for marker in banned_primitives:
                self.assertNotIn(marker, text, f"{marker} leaked into {path}")

    def test_party_mode_v2_uses_existing_adapter_capability_or_fallback(self) -> None:
        required_capabilities = (
            "dispatchSubagent",
            "freshChildContext",
            "sendFollowup",
            "waitChild",
            "listChildren",
            "cancelChild",
        )
        usable_values = {"native", "shim", "plugin", "external", "experimental"}
        for base in (
            ROOT / ".cowork-flow" / "adapters",
            ROOT / "template" / ".cowork-flow" / "adapters",
        ):
            for host in ("codex", "opencode", "claude-code"):
                adapter = parse_simple_yaml(base / host / "adapter.yaml")
                self.assertEqual(
                    "inline_or_manual",
                    adapter["fallback"]["whenRequiredCapabilityMissing"],
                    host,
                )
                for key in required_capabilities:
                    self.assertIn(adapter["capabilities"][key], usable_values, f"{host}:{key}")

    def test_party_mode_v2_root_and_template_assets_are_synced(self) -> None:
        pairs = (
            (
                ROOT / ".cowork-flow" / "spec" / "schemas" / "party-mode-v2-actions.schema.json",
                ROOT / "template" / ".cowork-flow" / "spec" / "schemas" / "party-mode-v2-actions.schema.json",
            ),
            (
                ROOT / ".cowork-flow" / "spec" / "contracts" / "party-mode-v2-board.md",
                ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "party-mode-v2-board.md",
            ),
            (
                ROOT / ".opencode" / "commands" / "party-mode-v2.md",
                ROOT / "template" / ".opencode" / "commands" / "party-mode-v2.md",
            ),
            (
                ROOT / ".cowork-flow" / "workflow.md",
                ROOT / "template" / ".cowork-flow" / "workflow.md",
            ),
            (
                ROOT / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
                ROOT / "template" / ".cowork-flow" / "spec" / "contracts" / "subagent-dispatch.md",
            ),
        )
        for root_path, template_path in pairs:
            self.assertEqual(
                root_path.read_text(encoding="utf-8"),
                template_path.read_text(encoding="utf-8"),
                f"{root_path} differs from {template_path}",
            )

    def test_workflow_is_host_neutral(self) -> None:
        banned = ("spawn_agent", "fork_turns", "wait_agent", "list_agents", "close_agent", "codex exec")
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("宿主适配器契约", text)
            self.assertIn("subagent-dispatch.md", text)
            self.assertIn("runtime context", text)
            self.assertNotIn(LEGACY_DISPATCH, text)
            self.assertNotIn(LEGACY_ACK, text)
            for marker in banned:
                self.assertNotIn(marker, text)

    def test_opencode_assets_encode_fixed_agent_contract(self) -> None:
        for base in (ROOT / ".opencode", ROOT / "template" / ".opencode"):
            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("mode: subagent", text)
                self.assertIn("task: deny", text)
                self.assertNotIn("COWORK_ENTRY_CONTRACT_V1", text)
                self.assertIn("cowork_runtime_context_id: <runtime_context_id>", text)
                self.assertIn("cowork_host_context_key: <host_context_key>", text)
                self.assertIn("subagent bind <runtime_context_id> <host_context_key>", text)
                self.assertIn("bound runtime context", text)
                self.assertIn("needs_context", text)
                self.assertIn("leaf", text)

            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "commands" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("subtask: true", text)
                self.assertIn(f"agent: {name}", text)
                self.assertIn(".cowork-flow/run subagent init", text)
                self.assertIn("cowork_runtime_context_id: <runtime_context_id>", text)
                self.assertIn("cowork_host_context_key: <host_context_key>", text)
                self.assertIn("subagent bind <runtime_context_id> <host_context_key>", text)

            plugin = (base / "plugins" / "cowork-flow.js").read_text(encoding="utf-8")
            self.assertIn("experimental.chat.system.transform", plugin)
            self.assertIn('"shell.env"', plugin)
            self.assertIn("sessionID", plugin)
            self.assertIn("COWORK_FLOW_CONTEXT_ID", plugin)
            self.assertIn("OPENCODE_SESSION_ID", plugin)
            self.assertIn(".cowork-flow\", \"spec\", \"runtime\", \"contract-registry.json", plugin)
            self.assertIn("contract-digest", plugin)
            self.assertIn("fingerprint", plugin)
            self.assertIn("read_before", plugin)
            self.assertNotIn("COWORK_ENTRY_CONTRACT_V1", plugin)
            self.assertIn("RUNTIME_CONTEXT_DISPATCH_V2", plugin)
            self.assertIn("resolveRuntimeContextId", plugin)
            self.assertIn("bindRuntimeContext", plugin)
            self.assertIn("runtime-context-invalid", plugin)

    def test_claude_code_assets_encode_fixed_agent_contract(self) -> None:
        for base in (ROOT / ".claude", ROOT / "template" / ".claude"):
            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", text)
                self.assertNotIn("COWORK_ENTRY_CONTRACT_V1", text)
                self.assertIn("cowork_runtime_context_id: <runtime_context_id>", text)
                self.assertIn("cowork_host_context_key: <host_context_key>", text)
                self.assertIn("subagent bind <runtime_context_id> <host_context_key>", text)
                self.assertIn("bound runtime context", text)
                self.assertIn("needs_context", text)
                self.assertIn("leaf", text)
                self.assertTrue(
                    "Do not use the" in text and "tool or invoke subagents" in text,
                    f"Missing subagent restriction in {name}.md"
                )

            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "commands" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn(f"Use the `{name}` agent", text)
                self.assertIn(".cowork-flow/run subagent init", text)
                self.assertIn("cowork_runtime_context_id: <runtime_context_id>", text)
                self.assertIn("cowork_host_context_key: <host_context_key>", text)
                self.assertIn("subagent bind <runtime_context_id> <host_context_key>", text)

            for name in ("start", "check"):
                for skills_base in (ROOT / "skills", ROOT / "template" / "skills"):
                    text = (skills_base / name / "SKILL.md").read_text(encoding="utf-8")
                    self.assertIn("name:", text)
                    self.assertIn("description:", text)
                self.assertFalse((ROOT / "skills" / ENTRY_BOUNDARY / "SKILL.md").exists())
                self.assertFalse((ROOT / "template" / "skills" / ENTRY_BOUNDARY / "SKILL.md").exists())

            settings = json.loads((base / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(
                CLAUDE_HOOK_COMMAND,
                settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            )
            self.assertEqual(
                CLAUDE_HOOK_COMMAND,
                settings["hooks"]["SessionStart"][0]["hooks"][0]["command"],
            )
            hook = (base / "hooks" / "inject-workflow-state.py").read_text(encoding="utf-8")
            self.assertIn('<cowork-runtime host="claude-code" adapter="claude-code.hooks">', hook)
            self.assertIn("workflow-state-templates.md", hook)
            self.assertIn("resolve_runtime_context_id", hook)
            self.assertIn("bind_runtime_context", hook)
            self.assertIn("runtime-context-invalid", hook)
            self.assertIn("hookSpecificOutput", hook)
            self.assertIn("additionalContext", hook)

        for path in (ROOT / "CLAUDE.md", ROOT / "template" / "CLAUDE.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("@AGENTS.md", text)
            self.assertIn("<!-- COWORK-FLOW:START -->", text)
            self.assertNotIn(".cowork-flow/run subagent init", text)
            self.assertNotIn("cowork_runtime_context_id: <runtime_context_id>", text)
            self.assertNotIn(".claude/agents/cowork-implement.md", text)
            self.assertNotIn("skills/", text)
