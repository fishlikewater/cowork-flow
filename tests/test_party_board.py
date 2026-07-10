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
from tests.party_mode_test_support import PartyModeTestCase, ROOT, TEMPLATE_SCRIPTS


class PartyBoardTest(PartyModeTestCase):
    def test_init_creates_runtime_state_and_host_neutral_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))

            result = self.party_mode_v2.init_discussion(
                root,
                discussion_id="demo",
                topic="Runtime board",
                agent_specs=[
                    "arch:architecture",
                    "runtime:runtime-control",
                    "test:testing",
                ],
            )

            base = root / ".cowork-flow" / ".runtime" / "party-mode-v2" / "demo"
            self.assertTrue((base / "board.json").is_file())
            self.assertTrue((base / "agents.json").is_file())
            self.assertTrue((base / "public_round.json").is_file())
            self.assertTrue((base / "actions.json").is_file())
            self.assertTrue((base / "audit.jsonl").is_file())
            self.assertEqual(1, result["board_status"]["round"])
            self.assertEqual("publish", result["board_status"]["phase"])
            rendered = json.dumps(result, ensure_ascii=False)
            for forbidden in self.party_mode_v2.HOST_FORBIDDEN_TERMS:
                self.assertNotIn(forbidden, rendered)
            action_types = {action["type"] for action in result["next_actions"]}
            self.assertEqual({"dispatch_child", "wait_children"}, action_types)

    def test_view_returns_only_current_round(self) -> None:
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
            )
            base = root / ".cowork-flow" / ".runtime" / "party-mode-v2" / "demo"
            board = json.loads((base / "board.json").read_text(encoding="utf-8"))
            board["round"] = {"current": 2, "max": 5, "phase": "respond"}
            board["rounds"] = [
                {
                    "round": 1,
                    "posts": [{"post_id": "r1-old", "claim": "old"}],
                    "responses": [],
                    "moderator_events": [],
                },
                {
                    "round": 2,
                    "posts": [{"post_id": "r2-new", "claim": "new"}],
                    "responses": [],
                    "moderator_events": [],
                },
            ]
            (base / "board.json").write_text(
                json.dumps(board, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            view = self.party_mode_v2.view_discussion(
                root,
                discussion_id="demo",
                agent_id="arch",
            )

            self.assertEqual(2, view["round"])
            self.assertEqual("arch", view["agent_id"])
            self.assertEqual(["r2-new"], [post["post_id"] for post in view["visible_posts"]])
            self.assertNotIn("r1-old", json.dumps(view, ensure_ascii=False))

    def test_rejects_unsafe_discussion_and_agent_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))

            for bad_id in ("../escape", "bad/name", "-bad", "bad space", "bad;cmd"):
                with self.subTest(discussion_id=bad_id):
                    with self.assertRaisesRegex(ValueError, "unsafe_discussion_id"):
                        self.party_mode_v2.init_discussion(
                            root,
                            discussion_id=bad_id,
                            topic="Runtime board",
                            agent_specs=[
                                "arch:architecture",
                                "runtime:runtime-control",
                                "test:testing",
                            ],
                        )

            self.assertFalse((root / ".cowork-flow" / ".runtime" / "escape").exists())

            with self.assertRaisesRegex(ValueError, "unsafe_agent_id"):
                self.party_mode_v2.init_discussion(
                    root,
                    discussion_id="demo",
                    topic="Runtime board",
                    agent_specs=[
                        "arch:architecture",
                        "../runtime:runtime-control",
                        "test:testing",
                    ],
                )

    def test_round_can_be_omitted_when_current_round_mode_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  require_current_round_only: "false"
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
            for agent_id in ("arch", "runtime", "test"):
                payload = self._post_payload(1, f"{agent_id} claim")
                payload.pop("round")
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=payload,
                )
            self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            response_payload = self._maintain_payload("runtime", "r1-arch-p1")
            response_payload.pop("round")

            response = self.party_mode_v2.respond_submission(
                root,
                discussion_id="demo",
                agent_id="runtime",
                payload=response_payload,
            )

            self.assertEqual("r1-arch-p1", response["target_post_id"])

    def test_view_empty_state_and_phase_specific_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)

            view = self.party_mode_v2.view_discussion(root, discussion_id="demo", agent_id="arch")
            self.assertEqual("waiting_for_current_round_posts", view["empty_state"]["visible_posts"])
            self.assertEqual("responses_not_open_yet", view["empty_state"]["visible_responses"])
            self.assertEqual("post", view["expected_next_action"])

            base = self._base_dir(root)
            publish_prompt = (base / "prompts" / "arch-r1-publish.md").read_text(encoding="utf-8")
            self.assertIn("party-v2 post --file", publish_prompt)
            self.assertIn('"claim"', publish_prompt)
            self.assertNotIn("party-v2 respond --file", publish_prompt)

            self._respond_to_phase(root)
            respond_prompt = (base / "prompts" / "arch-r1-respond.md").read_text(encoding="utf-8")
            self.assertIn("party-v2 respond --file", respond_prompt)
            self.assertIn('"target_post_id"', respond_prompt)
            self.assertIn("max_rebuttal_targets_per_agent", respond_prompt)
            self.assertNotEqual(publish_prompt, respond_prompt)

    def test_finalize_requires_closed_discussion_or_manual_termination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)

            with self.assertRaisesRegex(ValueError, "finalize_requires_closed_discussion"):
                self.party_mode_v2.finalize_discussion(root, discussion_id="demo")

            report = self.party_mode_v2.finalize_discussion(
                root,
                discussion_id="demo",
                manual_termination=True,
            )

            self.assertEqual("manual_terminated", report["stop_reason"])
            self.assertEqual("closed", self._read_board(root)["round"]["phase"])
            self.assertEqual([], json.loads((self._base_dir(root) / "actions.json").read_text(encoding="utf-8"))["next_actions"])

    def test_converged_report_separates_historical_disagreements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  max_rounds: 2
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
            for agent_id, target in {
                "arch": "r1-runtime-p2",
                "runtime": "r1-test-p3",
                "test": "r1-arch-p1",
            }.items():
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._maintain_payload(agent_id, target),
                )
            next_round = self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            self.assertFalse(next_round["terminal"])
            self.assertEqual(2, next_round["board_status"]["round"])

            for agent_id in ("arch", "runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(2, f"{agent_id} refined claim"),
                )
            self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            for agent_id, target in {
                "arch": "r2-runtime-p2",
                "runtime": "r2-test-p3",
                "test": "r2-arch-p1",
            }.items():
                payload = self._concede_payload(agent_id, target)
                payload["round"] = 2
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=payload,
                )

            terminal = self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            report = self._read_final_report(root)

            self.assertTrue(terminal["terminal"])
            self.assertEqual("converged", terminal["stop_reason"])
            self.assertEqual("converged", report["stop_reason"])
            self.assertEqual([], report["current_unresolved_disagreements"])
            self.assertEqual([], report["unresolved_disagreements"])
            self.assertGreaterEqual(len(report["historical_disagreements"]), 3)

    def test_fresh_context_next_round_closes_stale_children_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  max_rounds: 2
  fresh_context_per_round: "true"
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
            for agent_id, target in {
                "arch": "r1-runtime-p2",
                "runtime": "r1-test-p3",
                "test": "r1-arch-p1",
            }.items():
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._maintain_payload(agent_id, target),
                )

            next_round = self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            actions = next_round["next_actions"]
            self.assertEqual(["close_child"] * 3, [action["type"] for action in actions[:3]])
            self.assertEqual(
                ["dispatch_child"] * 3 + ["wait_children"],
                [action["type"] for action in actions[3:]],
            )
            self.assertEqual(
                {"fresh_context_per_round"},
                {action["reason"] for action in actions[:3]},
            )
            close_result = self.party_mode_v2.record_action_result(
                root,
                discussion_id="demo",
                payload={
                    "action_id": actions[0]["action_id"],
                    "type": "close_child",
                    "agent_id": actions[0]["agent_id"],
                    "outcome": "success",
                },
            )
            self.assertEqual("close_child", close_result["type"])
            agents = self._read_agents(root)
            closed_agent = next(agent for agent in agents["agents"] if agent["agent_id"] == actions[0]["agent_id"])
            self.assertEqual("closed", closed_agent["status"])
            base = self._base_dir(root)
            self.assertIn("close_child", (base / "action_history.jsonl").read_text(encoding="utf-8"))
            self.assertIn('"event": "close"', (base / "audit.jsonl").read_text(encoding="utf-8"))

    def test_three_agent_simulation_reaches_converged_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root)

            monitor = self.party_mode_v2.monitor_discussion(root, discussion_id="demo")
            self.assertEqual(1, monitor["board_status"]["round"])
            self.assertEqual("publish", monitor["board_status"]["phase"])
            self.assertEqual({"dispatch_child", "wait_children"}, {action["type"] for action in monitor["next_actions"]})

            for agent_id in ("arch", "runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(1, f"{agent_id} claim"),
                )

            view = self.party_mode_v2.view_discussion(
                root,
                discussion_id="demo",
                agent_id="arch",
            )
            self.assertEqual("arch", view["agent_id"])
            self.assertEqual(3, len(view["visible_posts"]))
            self.assertEqual(1, view["round"])

            respond_state = self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            self.assertEqual("respond", respond_state["board_status"]["phase"])
            self.assertIn(
                "send_control_message",
                {action["type"] for action in respond_state["next_actions"]},
            )

            targets = {
                "arch": "r1-runtime-p2",
                "runtime": "r1-test-p3",
                "test": "r1-arch-p1",
            }
            for agent_id, target in targets.items():
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._concede_payload(agent_id, target),
                )

            report = self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            self.assertEqual("converged", report["stop_reason"])
            self.assertEqual(3, len(report["pro"]))
            self.assertEqual(3, len(report["changed_positions"]))
            self.assertEqual([], report["maintained_positions"])
            self.assertEqual([], report["unresolved_disagreements"])

    def test_monitor_output_contains_status_and_actions_not_opinion_synthesis(self) -> None:
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

            monitor = self.party_mode_v2.monitor_discussion(root, discussion_id="demo")
            rendered = json.dumps(monitor, ensure_ascii=False)

            self.assertIn("board_status", monitor)
            self.assertIn("next_actions", monitor)
            self.assertEqual("respond", monitor["board_status"]["phase"])
            self.assertNotIn("arch claim", rendered)
            self.assertNotIn("runtime claim", rendered)
            self.assertNotIn("test claim", rendered)
            self.assertNotIn("evidence for", rendered)
            self.assertNotIn("reasoning", rendered)
            self.assertNotIn("pro", monitor)
            self.assertNotIn("con", monitor)
            for forbidden in self.party_mode_v2.HOST_FORBIDDEN_TERMS:
                self.assertNotIn(forbidden, rendered)

    def test_max_rounds_unconverged_report_lists_positions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            self._init_demo(root, max_rounds=1)
            for agent_id in ("arch", "runtime", "test"):
                self.party_mode_v2.post_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._post_payload(1, f"{agent_id} claim"),
                )
            self.party_mode_v2.advance_discussion(root, discussion_id="demo")
            targets = {
                "arch": "r1-runtime-p2",
                "runtime": "r1-arch-p1",
                "test": "r1-arch-p1",
            }
            for agent_id, target in targets.items():
                self.party_mode_v2.respond_submission(
                    root,
                    discussion_id="demo",
                    agent_id=agent_id,
                    payload=self._maintain_payload(agent_id, target),
                )

            report = self.party_mode_v2.advance_discussion(root, discussion_id="demo")

            self.assertEqual("max_rounds_unconverged", report["stop_reason"])
            self.assertEqual(3, len(report["pro"]))
            self.assertEqual(3, len(report["maintained_positions"]))
            self.assertEqual(3, len(report["unresolved_disagreements"]))
            final_report = (
                root
                / ".cowork-flow"
                / ".runtime"
                / "party-mode-v2"
                / "demo"
                / "reports"
                / "final.json"
            )
            self.assertTrue(final_report.is_file())
