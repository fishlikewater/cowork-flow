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
ROOT_SCRIPTS = ROOT / ".cowork-flow" / "scripts"
TEMPLATE_SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class TestPartyModeV2Runtime(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT_SCRIPTS))
        self.addCleanup(self._cleanup_imports)
        self.config = importlib.import_module("common.config")
        self.party_mode_v2 = importlib.import_module("party_mode_v2")

    def _cleanup_imports(self) -> None:
        if str(ROOT_SCRIPTS) in sys.path:
            sys.path.remove(str(ROOT_SCRIPTS))
        for module_name in (
            "party_mode_v2",
            "common.config",
            "common.paths",
            "common",
        ):
            sys.modules.pop(module_name, None)

    def _repo(self, temp_dir: Path, config_text: str | None = None) -> Path:
        repo = temp_dir / "repo"
        workflow = repo / ".cowork-flow"
        workflow.mkdir(parents=True)
        (workflow / "config.yaml").write_text(config_text or "", encoding="utf-8")
        return repo

    def test_party_mode_v2_config_defaults_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  min_agents: 4
  max_agents: 6
  max_rounds: 7
  max_rebuttal_targets_per_agent: 3
  max_drift_warnings: 1
  fresh_context_per_round: "false"
  require_current_round_only: "true"
""",
            )

            config = self.config.get_party_mode_v2_config(root)

            self.assertEqual(4, config["min_agents"])
            self.assertEqual(6, config["max_agents"])
            self.assertEqual(7, config["max_rounds"])
            self.assertEqual(3, config["max_rebuttal_targets_per_agent"])
            self.assertEqual(1, config["max_drift_warnings"])
            self.assertIs(config["fresh_context_per_round"], False)
            self.assertIs(config["require_current_round_only"], True)

    def test_party_mode_v2_config_falls_back_for_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(
                Path(temp_name),
                """
party_mode_v2:
  min_agents: 2
  max_agents: nope
  max_rounds: 0
  fresh_context_per_round: maybe
""",
            )

            config = self.config.get_party_mode_v2_config(root)

            self.assertEqual(3, config["min_agents"])
            self.assertEqual(5, config["max_agents"])
            self.assertEqual(5, config["max_rounds"])
            self.assertIs(config["fresh_context_per_round"], True)

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
            lock_path = base / ".state.lock"
            handle = lock_path.open("a+b")
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
            self.party_mode_v2._lock_file(handle)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT_SCRIPTS / "party_mode_v2.py"),
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
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.wait(timeout=1)
            finally:
                self.party_mode_v2._unlock_file(handle)
                handle.close()

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
            self.assertEqual([], json.loads((base / "actions.json").read_text(encoding="utf-8"))["next_actions"])
            self.assertIn("action-issued", (base / "action_history.jsonl").read_text(encoding="utf-8"))

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

    def test_root_and_template_runtime_assets_stay_in_sync(self) -> None:
        pairs = (
            (
                ROOT / ".cowork-flow" / "scripts" / "party_mode_v2.py",
                TEMPLATE_SCRIPTS / "party_mode_v2.py",
            ),
            (
                ROOT / ".cowork-flow" / "scripts" / "run.py",
                TEMPLATE_SCRIPTS / "run.py",
            ),
            (
                ROOT / ".cowork-flow" / "scripts" / "common" / "config.py",
                TEMPLATE_SCRIPTS / "common" / "config.py",
            ),
        )
        for root_path, template_path in pairs:
            self.assertEqual(
                root_path.read_text(encoding="utf-8"),
                template_path.read_text(encoding="utf-8"),
                f"{root_path} differs from {template_path}",
            )

    def test_party_v2_command_is_registered(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "scripts" / "run.py",
            TEMPLATE_SCRIPTS / "run.py",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn('"party-v2": "party_mode_v2.py"', text)
            self.assertIn('"party_v2": "party_mode_v2.py"', text)

    def test_runner_dispatches_party_v2_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = self._repo(Path(temp_name))
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / ".cowork-flow" / "scripts" / "run.py"),
                    "party-v2",
                    "--repo-root",
                    str(root),
                    "init",
                    "--discussion-id",
                    "demo",
                    "--topic",
                    "Runtime board",
                    "--agent",
                    "arch:architecture",
                    "--agent",
                    "runtime:runtime-control",
                    "--agent",
                    "test:testing",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual("demo", output["discussion_id"])
            self.assertTrue(
                (
                    root
                    / ".cowork-flow"
                    / ".runtime"
                    / "party-mode-v2"
                    / "demo"
                    / "board.json"
                ).is_file()
            )

    def test_config_templates_document_party_mode_v2(self) -> None:
        for path in (
            ROOT / ".cowork-flow" / "config.yaml",
            ROOT / "template" / ".cowork-flow" / "config.yaml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("party_mode_v2:", text)
            self.assertIn("min_agents: 3", text)
            self.assertIn("max_rounds: 5", text)


if __name__ == "__main__":
    unittest.main()
