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

    def test_codex_and_opencode_adapters_match_contract(self) -> None:
        for base in (
            ROOT / ".cowork-flow" / "adapters",
            ROOT / "template" / ".cowork-flow" / "adapters",
        ):
            for host in ("codex", "opencode"):
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
            self.assertIn("COWORK_ENTRY_CONTRACT_V1", plugin)
