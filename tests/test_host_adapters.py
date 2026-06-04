from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
            ROOT / ".cowork-flow" / "spec" / "adapter.schema.json",
            ROOT / "template" / ".cowork-flow" / "spec" / "adapter.schema.json",
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
                for key in (
                    "dispatchSubagent",
                    "freshChildContext",
                    "sendFollowup",
                    "waitChild",
                    "listChildren",
                    "cancelChild",
                    "stateInjection",
                    "backgroundChild",
                ):
                    self.assertIn(capabilities[key], {"native", "shim", "plugin", "external", "experimental"})

                contracts = adapter["contracts"]
                self.assertEqual("COWORK_ENTRY_CONTRACT_V1", contracts["entry"])
                self.assertEqual("COWORK_DISPATCH_V1", contracts["envelope"])
                self.assertEqual("COWORK_DELEGATION_V1", contracts["delegation"])
                self.assertIs(contracts["ackRequired"], True)
                self.assertIs(contracts["executeRequired"], True)
                self.assertIs(contracts["leafExecutor"], True)
                if host == "claude-code":
                    self.assertEqual(".claude/skills", adapter["dispatch"]["skillsPath"])
                    self.assertEqual(".claude/settings.json", adapter["dispatch"]["settingsPath"])
                    self.assertEqual(".claude/hooks", adapter["dispatch"]["hooksPath"])

    def test_workflow_is_host_neutral(self) -> None:
        banned = ("spawn_agent", "fork_turns", "wait_agent", "list_agents", "close_agent", "codex exec")
        for path in (
            ROOT / ".cowork-flow" / "workflow.md",
            ROOT / "template" / ".cowork-flow" / "workflow.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("宿主适配器契约", text)
            for marker in banned:
                self.assertNotIn(marker, text)

    def test_opencode_assets_encode_fixed_agent_contract(self) -> None:
        for base in (ROOT / ".opencode", ROOT / "template" / ".opencode"):
            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("mode: subagent", text)
                self.assertIn("task: deny", text)
                self.assertIn("COWORK_ENTRY_CONTRACT_V1", text)
                self.assertIn("COWORK_DISPATCH_V1", text)
                self.assertIn("COWORK_DELEGATION_V1", text)
                self.assertIn("COWORK_ACK", text)
                self.assertIn("EXECUTE <dispatch_id>", text)
                self.assertIn("leaf", text)

            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "commands" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn("subtask: true", text)
                self.assertIn(f"agent: {name}", text)
                self.assertIn("COWORK_DELEGATION_V1", text)

            plugin = (base / "plugins" / "cowork-flow.js").read_text(encoding="utf-8")
            self.assertIn("experimental.chat.system.transform", plugin)
            self.assertIn(".cowork-flow\", \"spec\", \"registry.json", plugin)
            self.assertIn("contract-digest", plugin)
            self.assertIn("fingerprint", plugin)
            self.assertIn("read_before", plugin)
            self.assertIn("COWORK_ENTRY_CONTRACT_V1", plugin)

    def test_claude_code_assets_encode_fixed_agent_contract(self) -> None:
        for base in (ROOT / ".claude", ROOT / "template" / ".claude"):
            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", text)
                self.assertIn("COWORK_ENTRY_CONTRACT_V1", text)
                self.assertIn("COWORK_DISPATCH_V1", text)
                self.assertIn("COWORK_DELEGATION_V1", text)
                self.assertIn("host: claude-code", text)
                self.assertIn("COWORK_ACK", text)
                self.assertIn("EXECUTE <dispatch_id>", text)
                self.assertIn("leaf", text)
                self.assertIn("Do not use the Task tool or invoke subagents", text)

            for name in ("cowork-research", "cowork-implement", "cowork-check"):
                text = (base / "commands" / f"{name}.md").read_text(encoding="utf-8")
                self.assertIn(f"Use the `{name}` agent", text)
                self.assertIn("COWORK_DELEGATION_V1", text)
                self.assertIn("host: claude-code", text)

            for name in ("start", "entry-boundary", "check"):
                text = (base / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("name:", text)
                self.assertIn("description:", text)

            settings = json.loads((base / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ".cowork-flow/run python .claude/hooks/inject-workflow-state.py",
                settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            )
            self.assertEqual(
                ".cowork-flow/run python .claude/hooks/inject-workflow-state.py",
                settings["hooks"]["SessionStart"][0]["hooks"][0]["command"],
            )
            hook = (base / "hooks" / "inject-workflow-state.py").read_text(encoding="utf-8")
            self.assertIn('<cowork-runtime host="claude-code" adapter="claude-code.hooks">', hook)
            self.assertIn("workflow-state-templates.md", hook)
            self.assertIn("common.entry_classifier", hook)
            self.assertIn("should_use_delegated_bootstrap", hook)
            self.assertIn("hookSpecificOutput", hook)
            self.assertIn("additionalContext", hook)

        for path in (ROOT / "CLAUDE.md", ROOT / "template" / "CLAUDE.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("@AGENTS.md", text)
            self.assertIn("<!-- COWORK-FLOW:START -->", text)
            self.assertIn("COWORK_DELEGATION_V1", text)
            self.assertIn(".claude/agents/cowork-implement.md", text)
            self.assertIn(".claude/skills/", text)
