"""Drift guard for the workflow hook's embedded fallback contract registry.

workflow_state_hook.py carries DEFAULT_CONTRACT_REGISTRY as the last-resort
digest source when the shipped registry file is unreadable. It is hand-copied
from spec/runtime/contract-registry.json, so this test pins every fallback
entry to the shipped source of truth.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
REGISTRY = ROOT / "template" / ".cowork-flow" / "spec" / "runtime" / "contract-registry.json"


class FallbackRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
            self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.addCleanup(
            lambda: sys.modules.pop("adapters.host.workflow_state_hook", None)
        )

    def test_fallback_registry_matches_shipped_registry(self) -> None:
        from adapters.host.workflow_state_hook import DEFAULT_CONTRACT_REGISTRY

        shipped = {
            entry["id"]: entry
            for entry in json.loads(REGISTRY.read_text(encoding="utf-8"))["contracts"]
        }
        fallback = DEFAULT_CONTRACT_REGISTRY["contracts"]
        self.assertTrue(fallback, "fallback registry must not be empty")
        for entry in fallback:
            with self.subTest(contract=entry["id"]):
                self.assertIn(entry["id"], shipped)
                self.assertEqual(shipped[entry["id"]]["path"], entry["path"])
                self.assertEqual(shipped[entry["id"]]["digest"], entry["digest"])
                self.assertEqual(shipped[entry["id"]]["readWhen"], entry["readWhen"])


class ShippedRegistryTest(unittest.TestCase):
    def test_host_install_inspection_contract_is_registered(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        entry = next(
            (
                contract
                for contract in registry["contracts"]
                if contract["id"] == "HOST_INSTALL_INSPECTION_V1"
            ),
            None,
        )
        self.assertIsNotNone(entry, "HOST_INSTALL_INSPECTION_V1 must be registered")
        self.assertEqual(
            ".cowork-flow/spec/contracts/host-install-inspection.md",
            entry["path"],
        )
        contract_path = ROOT / "template" / entry["path"]
        self.assertTrue(contract_path.is_file(), contract_path)
        self.assertTrue(entry["digest"], "a registered contract needs digest lines")
        self.assertTrue(all(line.strip() for line in entry["digest"]))
        self.assertIn("cwf host inspect", " ".join(entry["digest"]))
        self.assertTrue(entry["readWhen"], "a registered contract needs read-when hints")


if __name__ == "__main__":
    unittest.main()
