from __future__ import annotations

import importlib
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
from tests.party_mode_test_support import PARTY_MODE_SCRIPT, PartyModeTestCase, ROOT, TEMPLATE_SCRIPTS


class PartyActionsTest(PartyModeTestCase):
    def test_parallel_posts_do_not_lose_updates_or_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            original_write_runtime_state = self.party_mode_v2._write_runtime_state

            def slow_write(base_dir: Path, board: dict[str, object]) -> None:
                time.sleep(0.05)
                original_write_runtime_state(base_dir, board)

            with patch.object(self.party_mode_v2, "_write_runtime_state", side_effect=slow_write):
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = [
                        executor.submit(
                            self.party_mode_v2.post_submission,
                            root,
                            discussion_id="demo",
                            agent_id=agent_id,
                            payload=self._post_payload(1, f"{agent_id} claim"),
                        )
                        for agent_id in ("arch", "runtime", "test")
                    ]
                    for future in futures:
                        future.result()

            view = self.party_mode_v2.view_discussion(root, discussion_id="demo")
            post_ids = [post["post_id"] for post in view["visible_posts"]]
            self.assertEqual(3, len(post_ids))
            self.assertEqual(3, len(set(post_ids)))

    def test_cli_post_waits_for_process_state_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            base = self._base_dir(root)
            payload_path = root / "arch-post.json"
            payload_path.write_text(
                json.dumps(self._post_payload(1, "arch claim"), ensure_ascii=False),
                encoding="utf-8",
            )
            with self.party_board_store.state_lock(base):
                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(PARTY_MODE_SCRIPT),
                        "--repo-root",
                        str(root),
                        "post",
                        "--discussion-id",
                        "demo",
                        "--agent-id",
                        "arch",
                        "--file",
                        str(payload_path),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.wait(timeout=1)

            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(0, process.returncode, stderr)
            self.assertIn('"post_id": "r1-arch-p1"', stdout)
            view = self.party_mode_v2.view_discussion(root, discussion_id="demo")
            self.assertEqual(["r1-arch-p1"], [post["post_id"] for post in view["visible_posts"]])

    def test_post_and_respond_require_explicit_current_round(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)

            post_payload = self._post_payload(1, "Runtime owns state")
            post_payload.pop("round")
            with self.assertRaisesRegex(ValueError, "missing_round"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id="arch",
                    payload=post_payload,
                )

            self._respond_to_phase(root)
            response_payload = self._maintain_payload("runtime", "r1-arch-p1")
            response_payload.pop("round")
            with self.assertRaisesRegex(ValueError, "missing_round"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=response_payload,
                )

    def test_respond_rejects_self_target_duplicate_and_excess_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  max_rebuttal_targets_per_agent: 1
""",
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
            self._respond_to_phase(root)

            with self.assertRaisesRegex(ValueError, "self_target_response"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=self._maintain_payload("runtime", "r1-runtime-p2"),
                )

            self.party_mode_v2.respond_submission(
                root,
                discussion_id="demo",
                agent_id="runtime",
                payload=self._maintain_payload("runtime", "r1-arch-p1"),
            )
            with self.assertRaisesRegex(ValueError, "duplicate_target_response"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=self._maintain_payload("runtime", "r1-arch-p1"),
                )
            with self.assertRaisesRegex(ValueError, "too_many_rebuttal_targets"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=self._maintain_payload("runtime", "r1-test-p3"),
                )

    def test_response_records_preserve_decision_specific_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            self._respond_to_phase(root)

            revise = self.party_mode_v2.respond_submission(
                root,
                discussion_id="demo",
                agent_id="runtime",
                payload=self._revise_payload("runtime", "r1-arch-p1"),
            )
            maintain = self.party_mode_v2.respond_submission(
                root,
                discussion_id="demo",
                agent_id="test",
                payload=self._maintain_payload("test", "r1-arch-p1"),
            )
            concede = self.party_mode_v2.respond_submission(
                root,
                discussion_id="demo",
                agent_id="arch",
                payload=self._concede_payload("arch", "r1-runtime-p2"),
            )

            self.assertEqual("the board must remain runtime-owned", revise["accepted_part"])
            self.assertEqual("host primitives still must stay outside runtime", revise["rejected_part"])
            self.assertEqual(
                "runtime owns validation while host adapter executes actions",
                revise["updated_position"],
            )
            self.assertEqual(["host-neutral actions are required"], maintain["counter_evidence"])
            self.assertEqual(["runtime rejects malformed child submissions"], concede["accepted_evidence"])
            board = self._read_board(root)
            stored = board["rounds"][0]["responses"]
            self.assertEqual(
                {"accepted_part", "rejected_part", "updated_position"},
                {"accepted_part", "rejected_part", "updated_position"} & set(stored[0]),
            )

    def test_action_history_and_host_results_survive_completed_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            base = self._base_dir(root)
            actions = json.loads((base / "actions.json").read_text(encoding="utf-8"))
            dispatch = next(action for action in actions["next_actions"] if action["type"] == "dispatch_child")

            result = self.party_mode_v2.record_action_result(
                root,
                discussion_id="demo",
                payload={
                    "action_id": dispatch["action_id"],
                    "type": "dispatch_child",
                    "agent_id": dispatch["agent_id"],
                    "host_child_id": "child-123",
                    "outcome": "success",
                    "agent_status": "active",
                },
            )

            self.assertEqual("child-123", result["host_child_id"])
            agents = self._read_agents(root)
            arch = next(agent for agent in agents["agents"] if agent["agent_id"] == dispatch["agent_id"])
            self.assertEqual("active", arch["status"])
            self.assertEqual("child-123", arch["host_child_id"])
            history = (base / "action_history.jsonl").read_text(encoding="utf-8")
            self.assertIn("action-issued", history)
            self.assertIn("action-result", history)

            for agent_id in ("arch", "runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(1, f"{agent_id} claim"),
                )
            self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            for agent_id, target in {
                "arch": "r1-runtime-p2",
                "runtime": "r1-test-p3",
                "test": "r1-arch-p1",
            }.items():
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._concede_payload(agent_id, target),
                )
            terminal = self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            self.assertTrue(terminal["terminal"])
            self.assertIn(
                {
                    "action_id": dispatch["action_id"],
                    "type": "dispatch_child",
                    "outcome": "success",
                    "agent_id": dispatch["agent_id"],
                },
                terminal["action_results"],
            )
            self.assertEqual([], json.loads((base / "actions.json").read_text(encoding="utf-8"))["next_actions"])
            self.assertIn("action-issued", (base / "action_history.jsonl").read_text(encoding="utf-8"))

    def test_unsupported_host_uses_manual_fallback_without_advancing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self.party_mode_v2.init_discussion(
                root,
                discussion_id="demo",
                topic="Runtime board",
                agent_specs=[
                    "arch:architecture",
                    "runtime:runtime-control",
                    "test:testing",
                ],
                host_id="zcode",
            )
            base = self._base_dir(root)
            actions = json.loads((base / "actions.json").read_text(encoding="utf-8"))["next_actions"]

            self.assertEqual(["report_to_user"], [action["type"] for action in actions])
            fallback = actions[0]
            self.assertIn("party_board_action unsupported", fallback["reason"])
            self.assertIn("inline_or_manual", fallback["reason"])
            self.assertIn("unable_to_dispatch", fallback["reason"])
            self.assertTrue((base / "prompts" / "arch-r1-publish.md").is_file())

            result = self.party_mode_v2.record_action_result(
                root,
                discussion_id="demo",
                payload={
                    "action_id": fallback["action_id"],
                    "type": "report_to_user",
                    "outcome": "unable_to_dispatch",
                },
            )

            self.assertEqual("unable_to_dispatch", result["outcome"])
            self.assertEqual("publish", self._read_board(root)["round"]["phase"])
            self.assertEqual("pending", self._read_agents(root)["agents"][0]["status"])
            with self.assertRaisesRegex(ValueError, "publish_incomplete"):
                self.party_mode_v2.advance_discussion(root, discussion_id="demo")

    def test_malformed_action_result_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            base = self._base_dir(root)
            actions = json.loads((base / "actions.json").read_text(encoding="utf-8"))
            dispatch = next(action for action in actions["next_actions"] if action["type"] == "dispatch_child")
            agents_before = self._read_agents(root)
            history_before = (base / "action_history.jsonl").read_text(encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing_outcome"):
                self.party_mode_v2.record_action_result(
                    root,
                    discussion_id="demo",
                    payload={
                        "action_id": dispatch["action_id"],
                        "type": "dispatch_child",
                        "agent_id": dispatch["agent_id"],
                    },
                )

            self.assertEqual(agents_before, self._read_agents(root))
            self.assertEqual(history_before, (base / "action_history.jsonl").read_text(encoding="utf-8"))

    def test_action_contract_rejects_malformed_action_documents(self) -> None:
        valid = {
            "schema_version": 1,
            "discussion_id": "demo",
            "next_actions": [
                {
                    "action_id": "r1-publish-arch",
                    "type": "dispatch_child",
                    "agent_id": "arch",
                    "agent_kind": "advisory",
                    "lens": "architecture",
                    "message_kind": "board_publish",
                    "prompt_file": ".cowork-flow/.runtime/party-mode-v2/demo/prompts/arch-r1-publish.md",
                },
                {"action_id": "r1-publish-wait", "type": "wait_children", "agent_ids": ["arch"]},
            ],
        }
        self.assertIs(valid, self.party_action_contract.validate_actions_document(valid))

        missing_prompt = json.loads(json.dumps(valid))
        missing_prompt["next_actions"][0].pop("prompt_file")
        with self.assertRaisesRegex(
            self.party_action_contract.PartyActionContractError,
            "missing_action_field:0:prompt_file",
        ):
            self.party_action_contract.validate_actions_document(missing_prompt)

        unknown_type = json.loads(json.dumps(valid))
        unknown_type["next_actions"][0]["type"] = "spawn_agent"
        with self.assertRaisesRegex(
            self.party_action_contract.PartyActionContractError,
            "invalid_action_type:0:spawn_agent",
        ):
            self.party_action_contract.validate_actions_document(unknown_type)

        host_specific = json.loads(json.dumps(valid))
        host_specific["next_actions"][0]["host_child_id"] = "child-123"
        with self.assertRaisesRegex(
            self.party_action_contract.PartyActionContractError,
            "unexpected_action_field:0:host_child_id",
        ):
            self.party_action_contract.validate_actions_document(host_specific)

    def test_post_rejects_missing_evidence_and_accepts_valid_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)

            invalid = self._post_payload(1, "Runtime owns state")
            invalid["evidence"] = []
            with self.assertRaisesRegex(ValueError, "missing_evidence"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id="arch",
                    payload=invalid,
                )

            post = self.party_mode_v2.post_submission(
                root,
                discussion_id="demo",
                agent_id="arch",
                payload=self._post_payload(1, "Runtime owns state"),
            )

            self.assertEqual("r1-arch-p1", post["post_id"])
            view = self.party_mode_v2.view_discussion(root, discussion_id="demo")
            self.assertEqual(["r1-arch-p1"], [item["post_id"] for item in view["visible_posts"]])

    def test_advance_requires_all_publish_posts_then_enters_respond_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            self.party_mode_v2.post_submission(
                root,
                discussion_id="demo",
                agent_id="arch",
                payload=self._post_payload(1, "Runtime owns state"),
            )
            with self.assertRaisesRegex(ValueError, "publish_incomplete"):
                self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            for agent_id in ("runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(1, f"{agent_id} claim"),
                )

            result = self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            self.assertEqual("respond", result["board_status"]["phase"])
            self.assertIn(
                "send_control_message",
                {action["type"] for action in result["next_actions"]},
            )

    def test_respond_rejects_shallow_or_unsupported_position_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            for agent_id in ("arch", "runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(1, f"{agent_id} claim"),
                )
            self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            shallow_concede = {
                "round": 1,
                "target_post_id": "r1-arch-p1",
                "decision": "concede",
                "my_current_position": "runtime position",
                "opponent_claim": "arch claim",
                "opponent_evidence_i_checked": ["checked"],
                "reasoning": "sounds good",
            }
            with self.assertRaisesRegex(ValueError, "shallow_concession"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=shallow_concede,
                )

            unsupported_maintain = {
                "round": 1,
                "target_post_id": "r1-arch-p1",
                "decision": "maintain",
                "my_current_position": "runtime position",
                "opponent_claim": "arch claim",
                "opponent_evidence_i_checked": ["checked"],
                "reasoning": "no",
                "why_opponent_is_wrong": "not enough",
            }
            with self.assertRaisesRegex(ValueError, "unsupported_rebuttal"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=unsupported_maintain,
                )

            vague_revision = {
                "round": 1,
                "target_post_id": "r1-arch-p1",
                "decision": "revise",
                "my_current_position": "test position",
                "opponent_claim": "arch claim",
                "opponent_evidence_i_checked": ["checked"],
                "reasoning": "partly right",
            }
            with self.assertRaisesRegex(ValueError, "vague_revision"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="test",
                    payload=vague_revision,
                )

    def test_respond_rejects_non_current_round_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)
            for agent_id in ("arch", "runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(1, f"{agent_id} claim"),
                )
            self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            payload = self._maintain_payload("runtime", "r0-old-p1")
            with self.assertRaisesRegex(ValueError, "target_not_in_current_round"):
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id="runtime",
                    payload=payload,
                )
