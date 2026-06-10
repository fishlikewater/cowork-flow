#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Party Mode V2 runtime-board controller.

This script owns advisory discussion state and emits host-neutral next actions.
It does not call Codex, Claude Code, or OpenCode host primitives directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.config import get_party_mode_v2_config
from common.paths import DIR_WORKFLOW, get_repo_root

RUNTIME_DIR = ".runtime"
MODE_DIR = "party-mode-v2"
HOST_FORBIDDEN_TERMS = (
    "spawn_agent",
    "wait_agent",
    "followup_task",
    "close_agent",
    "Claude Task",
    "OpenCode task",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discussion_dir(repo_root: Path, discussion_id: str) -> Path:
    return repo_root / DIR_WORKFLOW / RUNTIME_DIR / MODE_DIR / discussion_id


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_audit(base_dir: Path, event: str, payload: dict[str, Any]) -> None:
    audit_path = base_dir / "audit.jsonl"
    entry = {"timestamp": _now(), "event": event, "payload": payload}
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _parse_agent_spec(spec: str) -> dict[str, str]:
    agent_id, separator, lens = spec.partition(":")
    agent_id = agent_id.strip()
    lens = lens.strip()
    if not agent_id or not separator or not lens:
        raise ValueError(f"invalid agent spec: {spec!r}; expected <agent_id>:<lens>")
    return {"agent_id": agent_id, "lens": lens}


def _validate_agents(agents: list[dict[str, str]], config: dict[str, int | bool]) -> None:
    min_agents = int(config["min_agents"])
    max_agents = int(config["max_agents"])
    if len(agents) < min_agents:
        raise ValueError(f"party_mode_v2 requires at least {min_agents} agents")
    if len(agents) > max_agents:
        raise ValueError(f"party_mode_v2 allows at most {max_agents} agents")
    seen: set[str] = set()
    for agent in agents:
        agent_id = agent["agent_id"]
        if agent_id in seen:
            raise ValueError(f"duplicate agent_id: {agent_id}")
        seen.add(agent_id)


def _prompt_text(discussion_id: str, agent: dict[str, str], round_number: int) -> str:
    agent_id = agent["agent_id"]
    return (
        f"# Party Mode V2 Child: {agent_id}\n\n"
        f"discussion_id: {discussion_id}\n"
        f"agent_id: {agent_id}\n"
        f"lens: {agent['lens']}\n"
        f"round: {round_number}\n\n"
        "Use the Party Mode V2 board API. Do not ask the moderator to forward "
        "or summarize opinions.\n\n"
        "Commands:\n\n"
        "```powershell\n"
        f".\\.cowork-flow\\run.cmd party-v2 view --discussion-id {discussion_id} --agent-id {agent_id}\n"
        "```\n"
    )


def _build_public_round(board: dict[str, Any]) -> dict[str, Any]:
    current_round = int(board["round"]["current"])
    current = next(
        (
            item
            for item in board.get("rounds", [])
            if int(item.get("round", -1)) == current_round
        ),
        {"round": current_round, "posts": [], "responses": [], "moderator_events": []},
    )
    return {
        "schema_version": 1,
        "discussion_id": board["discussion_id"],
        "round": current_round,
        "phase": board["round"]["phase"],
        "topic": board["topic"],
        "visible_posts": list(current.get("posts", [])),
        "visible_responses": list(current.get("responses", [])),
        "moderator_events": list(current.get("moderator_events", [])),
    }


def _build_actions(
    base_dir: Path,
    discussion_id: str,
    agents: list[dict[str, str]],
    *,
    round_number: int,
    phase: str,
) -> dict[str, Any]:
    actions = []
    prompts_dir = base_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for agent in agents:
        agent_id = agent["agent_id"]
        prompt_name = f"{agent_id}-r{round_number}-{phase}.md"
        prompt_path = prompts_dir / prompt_name
        prompt_path.write_text(_prompt_text(discussion_id, agent, round_number), encoding="utf-8")
        actions.append(
            {
                "type": "dispatch_child" if phase == "publish" else "send_control_message",
                "agent_id": agent_id,
                "agent_kind": "advisory",
                "lens": agent["lens"],
                "message_kind": f"board_{phase}",
                "prompt_file": str(
                    Path(DIR_WORKFLOW) / RUNTIME_DIR / MODE_DIR / discussion_id / "prompts" / prompt_name
                ),
            }
        )
    actions.append(
        {
            "type": "wait_children",
            "agent_ids": [agent["agent_id"] for agent in agents],
        }
    )
    return {"schema_version": 1, "discussion_id": discussion_id, "next_actions": actions}


def init_discussion(
    repo_root: Path,
    *,
    discussion_id: str,
    topic: str,
    agent_specs: list[str],
) -> dict[str, Any]:
    config = get_party_mode_v2_config(repo_root)
    agents = [_parse_agent_spec(spec) for spec in agent_specs]
    _validate_agents(agents, config)
    base_dir = discussion_dir(repo_root, discussion_id)
    max_rounds = int(config["max_rounds"])
    board = {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "topic": topic,
        "round": {"current": 1, "max": max_rounds, "phase": "publish"},
        "rounds": [
            {
                "round": 1,
                "posts": [],
                "responses": [],
                "moderator_events": [],
            }
        ],
        "termination": {"reason": None},
    }
    agents_state = {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "agents": [
            {
                "agent_id": agent["agent_id"],
                "lens": agent["lens"],
                "status": "pending",
                "drift_warnings": 0,
                "host_child_id": None,
            }
            for agent in agents
        ],
    }
    actions = _build_actions(base_dir, discussion_id, agents, round_number=1, phase="publish")
    public_round = _build_public_round(board)
    _write_json(base_dir / "board.json", board)
    _write_json(base_dir / "agents.json", agents_state)
    _write_json(base_dir / "actions.json", actions)
    _write_json(base_dir / "public_round.json", public_round)
    _append_audit(
        base_dir,
        "init",
        {
            "discussion_id": discussion_id,
            "agent_count": len(agents),
            "max_rounds": max_rounds,
        },
    )
    return monitor_discussion(repo_root, discussion_id=discussion_id)


def view_discussion(
    repo_root: Path,
    *,
    discussion_id: str,
    agent_id: str | None = None,
) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = _read_json(base_dir / "board.json")
    public_round = _build_public_round(board)
    if agent_id:
        public_round["agent_id"] = agent_id
    _write_json(base_dir / "public_round.json", public_round)
    return public_round


def monitor_discussion(repo_root: Path, *, discussion_id: str) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = _read_json(base_dir / "board.json")
    agents = _read_json(base_dir / "agents.json")
    actions = _read_json(base_dir / "actions.json")
    active_agents = [
        agent
        for agent in agents.get("agents", [])
        if str(agent.get("status", "")).startswith(("pending", "active"))
    ]
    return {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "board_status": {
            "round": board["round"]["current"],
            "phase": board["round"]["phase"],
            "max_rounds": board["round"]["max"],
            "active_agents": len(active_agents),
            "termination_reason": board.get("termination", {}).get("reason"),
        },
        "next_actions": actions.get("next_actions", []),
    }


def _current_round(board: dict[str, Any]) -> dict[str, Any]:
    current_round = int(board["round"]["current"])
    for item in board.get("rounds", []):
        if int(item.get("round", -1)) == current_round:
            return item
    item = {"round": current_round, "posts": [], "responses": [], "moderator_events": []}
    board.setdefault("rounds", []).append(item)
    return item


def _active_agent_ids(base_dir: Path) -> list[str]:
    agents = _read_json(base_dir / "agents.json")
    return [
        str(agent["agent_id"])
        for agent in agents.get("agents", [])
        if str(agent.get("status", "")).startswith(("pending", "active"))
    ]


def _agent_lenses(base_dir: Path) -> list[dict[str, str]]:
    agents = _read_json(base_dir / "agents.json")
    return [
        {"agent_id": str(agent["agent_id"]), "lens": str(agent["lens"])}
        for agent in agents.get("agents", [])
        if str(agent.get("status", "")).startswith(("pending", "active"))
    ]


def _require_non_empty_text(payload: dict[str, Any], key: str, error: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error)
    return value.strip()


def _require_non_empty_list(payload: dict[str, Any], key: str, error: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(error)
    return value


def _write_runtime_state(base_dir: Path, board: dict[str, Any]) -> None:
    _write_json(base_dir / "board.json", board)
    _write_json(base_dir / "public_round.json", _build_public_round(board))


def post_submission(
    repo_root: Path,
    *,
    discussion_id: str,
    agent_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = _read_json(base_dir / "board.json")
    if board["round"]["phase"] != "publish":
        raise ValueError("phase_not_publish")
    if agent_id not in _active_agent_ids(base_dir):
        raise ValueError("agent_not_active")
    current_round = int(board["round"]["current"])
    if int(payload.get("round", current_round)) != current_round:
        raise ValueError("round_mismatch")
    claim = _require_non_empty_text(payload, "claim", "missing_claim")
    evidence = _require_non_empty_list(payload, "evidence", "missing_evidence")
    risk = _require_non_empty_text(payload, "risk", "missing_risk")
    tradeoff = _require_non_empty_text(payload, "tradeoff", "missing_tradeoff")
    acceptance_signal = _require_non_empty_text(
        payload,
        "acceptance_signal",
        "missing_acceptance_signal",
    )
    what_would_change_my_mind = _require_non_empty_text(
        payload,
        "what_would_change_my_mind",
        "missing_what_would_change_my_mind",
    )
    current = _current_round(board)
    posts = current.setdefault("posts", [])
    if any(post.get("agent_id") == agent_id for post in posts):
        raise ValueError("duplicate_post")
    post = {
        "post_id": f"r{current_round}-{agent_id}-p{len(posts) + 1}",
        "agent_id": agent_id,
        "claim": claim,
        "evidence": evidence,
        "risk": risk,
        "tradeoff": tradeoff,
        "acceptance_signal": acceptance_signal,
        "what_would_change_my_mind": what_would_change_my_mind,
    }
    posts.append(post)
    _write_runtime_state(base_dir, board)
    _append_audit(base_dir, "post", {"agent_id": agent_id, "post_id": post["post_id"]})
    return post


def _current_post_ids(board: dict[str, Any]) -> set[str]:
    return {str(post["post_id"]) for post in _current_round(board).get("posts", [])}


def respond_submission(
    repo_root: Path,
    *,
    discussion_id: str,
    agent_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = _read_json(base_dir / "board.json")
    if board["round"]["phase"] != "respond":
        raise ValueError("phase_not_respond")
    if agent_id not in _active_agent_ids(base_dir):
        raise ValueError("agent_not_active")
    current_round = int(board["round"]["current"])
    if int(payload.get("round", current_round)) != current_round:
        raise ValueError("round_mismatch")
    target_post_id = _require_non_empty_text(payload, "target_post_id", "missing_target_post_id")
    if target_post_id not in _current_post_ids(board):
        raise ValueError("target_not_in_current_round")
    decision = _require_non_empty_text(payload, "decision", "missing_decision")
    if decision not in {"maintain", "revise", "concede"}:
        raise ValueError("invalid_decision")
    _require_non_empty_text(payload, "my_current_position", "missing_current_position")
    _require_non_empty_text(payload, "opponent_claim", "missing_opponent_claim")
    _require_non_empty_list(
        payload,
        "opponent_evidence_i_checked",
        "missing_checked_evidence",
    )
    reasoning = _require_non_empty_text(payload, "reasoning", "missing_reasoning")

    if decision == "concede":
        _require_non_empty_text(payload, "why_opponent_is_right", "shallow_concession")
        _require_non_empty_list(payload, "accepted_evidence", "shallow_concession")
        _require_non_empty_text(payload, "why_my_previous_position_failed", "shallow_concession")
        position_delta = "changed"
        still_disagree = False
    elif decision == "revise":
        _require_non_empty_text(payload, "accepted_part", "vague_revision")
        _require_non_empty_text(payload, "rejected_part", "vague_revision")
        _require_non_empty_text(payload, "updated_position", "vague_revision")
        position_delta = str(payload.get("position_delta") or "narrowed")
        still_disagree = bool(payload.get("still_disagree", True))
    else:
        _require_non_empty_text(payload, "why_opponent_is_wrong", "unsupported_rebuttal")
        counter_evidence = payload.get("counter_evidence")
        counter_reasoning = payload.get("counter_reasoning")
        if not counter_evidence and not counter_reasoning:
            raise ValueError("unsupported_rebuttal")
        position_delta = "unchanged"
        still_disagree = True

    current = _current_round(board)
    responses = current.setdefault("responses", [])
    response = {
        "response_id": f"r{current_round}-{agent_id}-resp{len(responses) + 1}",
        "agent_id": agent_id,
        "target_post_id": target_post_id,
        "decision": decision,
        "reasoning": reasoning,
        "position_delta": position_delta,
        "still_disagree": still_disagree,
        "confidence_after_review": str(payload.get("confidence_after_review", "medium")),
    }
    responses.append(response)
    _write_runtime_state(base_dir, board)
    _append_audit(
        base_dir,
        "respond",
        {"agent_id": agent_id, "response_id": response["response_id"]},
    )
    return response


def _write_actions_for_phase(base_dir: Path, discussion_id: str, round_number: int, phase: str) -> None:
    actions = _build_actions(
        base_dir,
        discussion_id,
        _agent_lenses(base_dir),
        round_number=round_number,
        phase=phase,
    )
    _write_json(base_dir / "actions.json", actions)


def advance_discussion(repo_root: Path, *, discussion_id: str) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = _read_json(base_dir / "board.json")
    current = _current_round(board)
    active_agents = _active_agent_ids(base_dir)
    current_round = int(board["round"]["current"])
    if board["round"]["phase"] == "publish":
        posted_agents = {str(post["agent_id"]) for post in current.get("posts", [])}
        missing = sorted(set(active_agents) - posted_agents)
        if missing:
            raise ValueError(f"publish_incomplete:{','.join(missing)}")
        board["round"]["phase"] = "respond"
        _write_runtime_state(base_dir, board)
        _write_actions_for_phase(base_dir, discussion_id, current_round, "respond")
        return monitor_discussion(repo_root, discussion_id=discussion_id)

    if board["round"]["phase"] != "respond":
        raise ValueError("phase_not_advanceable")

    responded_agents = {str(response["agent_id"]) for response in current.get("responses", [])}
    missing = sorted(set(active_agents) - responded_agents)
    if missing:
        raise ValueError(f"respond_incomplete:{','.join(missing)}")

    if not any(bool(response.get("still_disagree")) for response in current.get("responses", [])):
        board["round"]["phase"] = "closed"
        board["termination"] = {"reason": "converged"}
        _write_runtime_state(base_dir, board)
        _write_json(base_dir / "actions.json", {"schema_version": 1, "discussion_id": discussion_id, "next_actions": []})
        return finalize_discussion(repo_root, discussion_id=discussion_id)

    if current_round >= int(board["round"]["max"]):
        board["round"]["phase"] = "closed"
        board["termination"] = {"reason": "max_rounds_unconverged"}
        _write_runtime_state(base_dir, board)
        _write_json(base_dir / "actions.json", {"schema_version": 1, "discussion_id": discussion_id, "next_actions": []})
        return finalize_discussion(repo_root, discussion_id=discussion_id)

    next_round = current_round + 1
    board["round"] = {"current": next_round, "max": board["round"]["max"], "phase": "publish"}
    board.setdefault("rounds", []).append(
        {"round": next_round, "posts": [], "responses": [], "moderator_events": []}
    )
    _write_runtime_state(base_dir, board)
    _write_actions_for_phase(base_dir, discussion_id, next_round, "publish")
    return monitor_discussion(repo_root, discussion_id=discussion_id)


def finalize_discussion(repo_root: Path, *, discussion_id: str) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = _read_json(base_dir / "board.json")
    posts = [post for item in board.get("rounds", []) for post in item.get("posts", [])]
    responses = [
        response
        for item in board.get("rounds", [])
        for response in item.get("responses", [])
    ]
    report = {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "stop_reason": board.get("termination", {}).get("reason") or "manual_finalize",
        "pro": [
            {"agent_id": post["agent_id"], "claim": post["claim"], "evidence": post["evidence"]}
            for post in posts
        ],
        "con": [
            {
                "agent_id": response["agent_id"],
                "target_post_id": response["target_post_id"],
                "reasoning": response["reasoning"],
            }
            for response in responses
            if response.get("decision") == "maintain"
        ],
        "changed_positions": [
            response for response in responses if response.get("position_delta") == "changed"
        ],
        "maintained_positions": [
            response for response in responses if response.get("position_delta") == "unchanged"
        ],
        "unresolved_disagreements": [
            response for response in responses if response.get("still_disagree")
        ],
    }
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    _write_json(reports_dir / "final.json", report)
    return report


def _print_json(data: dict[str, Any]) -> None:
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if any(term in rendered for term in HOST_FORBIDDEN_TERMS):
        print("Error: host-specific primitive leaked into output", file=sys.stderr)
        raise SystemExit(2)
    print(rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Party Mode V2 runtime-board controller")
    parser.add_argument("--repo-root", type=Path, default=None)
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init")
    init_parser.add_argument("--discussion-id", required=True)
    init_parser.add_argument("--topic", required=True)
    init_parser.add_argument("--agent", action="append", required=True)

    view_parser = subcommands.add_parser("view")
    view_parser.add_argument("--discussion-id", required=True)
    view_parser.add_argument("--agent-id", default=None)

    monitor_parser = subcommands.add_parser("monitor")
    monitor_parser.add_argument("--discussion-id", required=True)

    post_parser = subcommands.add_parser("post")
    post_parser.add_argument("--discussion-id", required=True)
    post_parser.add_argument("--agent-id", required=True)
    post_parser.add_argument("--file", type=Path, required=True)

    respond_parser = subcommands.add_parser("respond")
    respond_parser.add_argument("--discussion-id", required=True)
    respond_parser.add_argument("--agent-id", required=True)
    respond_parser.add_argument("--file", type=Path, required=True)

    advance_parser = subcommands.add_parser("advance")
    advance_parser.add_argument("--discussion-id", required=True)

    finalize_parser = subcommands.add_parser("finalize")
    finalize_parser.add_argument("--discussion-id", required=True)

    return parser


def _read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload_must_be_object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root or get_repo_root()
    try:
        if args.command == "init":
            _print_json(
                init_discussion(
                    repo_root,
                    discussion_id=args.discussion_id,
                    topic=args.topic,
                    agent_specs=args.agent,
                )
            )
            return 0
        if args.command == "view":
            _print_json(
                view_discussion(
                    repo_root,
                    discussion_id=args.discussion_id,
                    agent_id=args.agent_id,
                )
            )
            return 0
        if args.command == "monitor":
            _print_json(monitor_discussion(repo_root, discussion_id=args.discussion_id))
            return 0
        if args.command == "post":
            _print_json(
                post_submission(
                    repo_root,
                    discussion_id=args.discussion_id,
                    agent_id=args.agent_id,
                    payload=_read_payload(args.file),
                )
            )
            return 0
        if args.command == "respond":
            _print_json(
                respond_submission(
                    repo_root,
                    discussion_id=args.discussion_id,
                    agent_id=args.agent_id,
                    payload=_read_payload(args.file),
                )
            )
            return 0
        if args.command == "advance":
            _print_json(advance_discussion(repo_root, discussion_id=args.discussion_id))
            return 0
        if args.command == "finalize":
            _print_json(finalize_discussion(repo_root, discussion_id=args.discussion_id))
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    parser.print_usage()
    return 2


if __name__ == "__main__":
    sys.exit(main())
