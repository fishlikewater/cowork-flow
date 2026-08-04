from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"
PARTY_MODE_SCRIPT = ROOT / "template" / "skills" / "party-mode" / "scripts" / "party_mode_v2.py"


class PartyModeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(TEMPLATE_SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.config = importlib.import_module("infra.config")
        spec = importlib.util.spec_from_file_location("party_mode_v2", PARTY_MODE_SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"unable to load {PARTY_MODE_SCRIPT}")
        self.party_mode_v2 = importlib.util.module_from_spec(spec)
        sys.modules["party_mode_v2"] = self.party_mode_v2
        spec.loader.exec_module(self.party_mode_v2)
        self.party_board_store = importlib.import_module("party_board_store")

    def _cleanup_imports(self) -> None:
        if str(TEMPLATE_SCRIPTS) in sys.path:
            sys.path.remove(str(TEMPLATE_SCRIPTS))
        script_dir = str(PARTY_MODE_SCRIPT.parent)
        if script_dir in sys.path:
            sys.path.remove(script_dir)
        for module_name in (
            "party_board_store",
            "party_mode_v2",
            "infra.config",
            "infra.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _repo(self, temp_dir: Path, config_text: str | None = None) -> Path:
        repo = temp_dir / "repo"
        workflow = repo / ".cowork-flow"
        workflow.mkdir(parents=True)
        (workflow / "config.yaml").write_text(config_text or "", encoding="utf-8")
        return repo

    def _init_demo(self, root: Path, *, max_rounds: int = 5) -> None:
        (root / ".cowork-flow" / "config.yaml").write_text(
            f"""party_mode_v2:
  max_rounds: {max_rounds}
""",
            encoding="utf-8",
        )
        self.party_mode_v2.init_discussion(
            root,
            discussion_id="demo",
            topic="Runtime board",
            agent_specs=[
                "arch:architecture",
                "runtime:runtime-control",
                "test:testing",
            ],
        )

    def _post_payload(self, round_number: int, claim: str) -> dict[str, object]:
        return {
            "round": round_number,
            "claim": claim,
            "evidence": [f"evidence for {claim}"],
            "risk": "risk",
            "tradeoff": "tradeoff",
            "acceptance_signal": "acceptance",
            "what_would_change_my_mind": "stronger evidence",
        }

    def _maintain_payload(self, agent_id: str, target_post_id: str) -> dict[str, object]:
        return {
            "round": 1,
            "target_post_id": target_post_id,
            "decision": "maintain",
            "my_current_position": f"{agent_id} position",
            "opponent_claim": "opponent claim",
            "opponent_evidence_i_checked": ["checked"],
            "reasoning": "opponent missed the runtime boundary",
            "why_opponent_is_wrong": "the target claim ignores host-neutral actions",
            "counter_evidence": ["host-neutral actions are required"],
            "counter_reasoning": "runtime cannot call host primitives directly",
            "confidence_after_review": "high",
        }

    def _concede_payload(self, agent_id: str, target_post_id: str) -> dict[str, object]:
        return {
            "round": 1,
            "target_post_id": target_post_id,
            "decision": "concede",
            "my_current_position": f"{agent_id} earlier position",
            "opponent_claim": "opponent claim",
            "opponent_evidence_i_checked": ["runtime-owned board evidence"],
            "reasoning": "the checked evidence proves the opponent's boundary is stricter",
            "why_opponent_is_right": "the runtime is the only component validating board writes",
            "accepted_evidence": ["runtime rejects malformed child submissions"],
            "why_my_previous_position_failed": "it relied on moderator forwarding instead of board API writes",
            "confidence_after_review": "high",
        }

    def _revise_payload(self, agent_id: str, target_post_id: str) -> dict[str, object]:
        return {
            "round": 1,
            "target_post_id": target_post_id,
            "decision": "revise",
            "my_current_position": f"{agent_id} earlier position",
            "opponent_claim": "opponent claim",
            "opponent_evidence_i_checked": ["runtime-owned board evidence"],
            "reasoning": "the checked evidence narrows my claim",
            "accepted_part": "the board must remain runtime-owned",
            "rejected_part": "host primitives still must stay outside runtime",
            "updated_position": "runtime owns validation while host adapter executes actions",
            "position_delta": "narrowed",
            "still_disagree": True,
            "confidence_after_review": "medium",
        }

    def _base_dir(self, root: Path, discussion_id: str = "demo") -> Path:
        return root / ".cowork-flow" / ".runtime" / "party-mode-v2" / discussion_id

    def _read_board(self, root: Path, discussion_id: str = "demo") -> dict[str, object]:
        return json.loads((self._base_dir(root, discussion_id) / "board.json").read_text(encoding="utf-8"))

    def _read_agents(self, root: Path, discussion_id: str = "demo") -> dict[str, object]:
        return json.loads((self._base_dir(root, discussion_id) / "agents.json").read_text(encoding="utf-8"))

    def _read_final_report(self, root: Path, discussion_id: str = "demo") -> dict[str, object]:
        return json.loads(
            (self._base_dir(root, discussion_id) / "reports" / "final.json").read_text(
                encoding="utf-8"
            )
        )

    def _respond_to_phase(self, root: Path) -> None:
        for agent_id in ("arch", "runtime", "test"):
            self.party_mode_v2.post_submission(
                root,
                discussion_id="demo",
                agent_id=agent_id,
                payload=self._post_payload(1, f"{agent_id} claim"),
            )
        self.party_mode_v2.advance_discussion(root, discussion_id="demo")
