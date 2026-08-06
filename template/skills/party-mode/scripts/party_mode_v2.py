#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Party Mode V2 runtime-board controller.

This script owns advisory discussion state and emits host-neutral next actions.
It does not call Codex, Claude Code, or OpenCode host primitives directly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

def _add_runtime_scripts_path() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".cowork-flow" / "scripts"
        if candidate.is_dir():
            candidate_text = str(candidate)
            if candidate_text not in sys.path:
                sys.path.insert(0, candidate_text)
            return


_add_runtime_scripts_path()
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from party_board_store import (
    append_action_history as _append_action_history,
    append_audit as _append_audit,
    load_board,
    read_json as _read_json,
    save_board,
    state_lock as _state_lock,
    write_json as _write_json,
)
from party_action_contract import validate_actions_document
from party_actions import (
    actions_document as _project_actions_document,
    child_action as _project_child_action,
    close_actions as _project_close_actions,
    empty_actions_document as _project_empty_actions,
    fallback_actions_document as _project_fallback_actions,
)
from party_reports import (
    action_results_summary as _project_action_results_summary,
    build_final_report as _project_final_report,
)
from party_state_machine import (
    advance_board_state as _advance_board_state,
    build_public_round as _project_public_round,
    current_round as _project_current_round,
    ensure_finalizable as _ensure_finalizable_state,
    initial_agents_state as _project_initial_agents_state,
    initial_board as _project_initial_board,
)
from infra.config import get_party_mode_v2_config
from infra.paths import DIR_WORKFLOW, get_repo_root
from adapters.host.host_manifest import load_host_manifest

RUNTIME_DIR = ".runtime"
MODE_DIR = "party-mode-v2"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CONFIDENCE_VALUES = {"low", "medium", "high"}
PARTY_BOARD_ACTION_CAPABILITY = "party_board_action"
SUPPORTED_HOST_CAPABILITY_STATUSES = {"native", "shim", "plugin", "external", "experimental"}
HOST_FORBIDDEN_TERMS = (
    "spawn_agent",
    "wait_agent",
    "followup_task",
    "close_agent",
    "Claude Task",
    "OpenCode task",
)


def _validate_identifier(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"unsafe_{label}")
    return value


def _runtime_base(repo_root: Path) -> Path:
    return (repo_root / DIR_WORKFLOW / RUNTIME_DIR / MODE_DIR).resolve()


def discussion_dir(repo_root: Path, discussion_id: str) -> Path:
    discussion_id = _validate_identifier(discussion_id, label="discussion_id")
    base = _runtime_base(repo_root)
    path = (base / discussion_id).resolve()
    if base != path and base not in path.parents:
        raise ValueError("unsafe_discussion_id")
    return path


def _parse_agent_spec(spec: str) -> dict[str, str]:
    agent_id, separator, lens = spec.partition(":")
    agent_id = agent_id.strip()
    lens = lens.strip()
    if not agent_id or not separator or not lens:
        raise ValueError(f"invalid agent spec: {spec!r}; expected <agent_id>:<lens>")
    _validate_identifier(agent_id, label="agent_id")
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


def _prompt_text(
    discussion_id: str,
    agent: dict[str, str],
    round_number: int,
    phase: str,
) -> str:
    agent_id = agent["agent_id"]
    base = _prompt_header(discussion_id, agent, round_number, phase)
    if phase == "publish":
        return base + _publish_prompt_payload(discussion_id, agent_id, round_number)
    return base + _respond_prompt_payload(discussion_id, agent_id, round_number)


def _prompt_header(
    discussion_id: str,
    agent: dict[str, str],
    round_number: int,
    phase: str,
) -> str:
    agent_id = agent["agent_id"]
    return (
        f"# Party Mode V2 Child: {agent_id}\n\n"
        f"discussion_id: {discussion_id}\n"
        f"agent_id: {agent_id}\n"
        f"lens: {agent['lens']}\n"
        f"round: {round_number}\n"
        f"phase: {phase}\n\n"
        "Use the Party Mode V2 board API. Do not ask the moderator to forward "
        "or summarize opinions.\n\n"
        "First inspect the current-round board:\n\n"
        "```powershell\n"
        f".\\.cowork-flow\\run.cmd party-v2 view --discussion-id {discussion_id} --agent-id {agent_id}\n"
        "```\n"
    )


def _publish_prompt_payload(discussion_id: str, agent_id: str, round_number: int) -> str:
    return (
        "\nSubmit one current-round post with `party-v2 post --file`:\n\n"
        "```powershell\n"
        f".\\.cowork-flow\\run.cmd party-v2 post --discussion-id {discussion_id} --agent-id {agent_id} --file <payload.json>\n"
        "```\n\n"
        "Payload fields:\n\n"
        "```json\n"
        "{\n"
        f"  \"round\": {round_number},\n"
        "  \"claim\": \"...\",\n"
        "  \"evidence\": [\"...\"],\n"
        "  \"risk\": \"...\",\n"
        "  \"tradeoff\": \"...\",\n"
        "  \"acceptance_signal\": \"...\",\n"
        "  \"what_would_change_my_mind\": \"...\"\n"
        "}\n"
        "```\n"
    )


def _respond_prompt_payload(discussion_id: str, agent_id: str, round_number: int) -> str:
    return (
        "\nRespond to current-round target posts only. Respect `max_rebuttal_targets_per_agent`.\n\n"
        "Submit with `party-v2 respond --file`:\n\n"
        "```powershell\n"
        f".\\.cowork-flow\\run.cmd party-v2 respond --discussion-id {discussion_id} --agent-id {agent_id} --file <payload.json>\n"
        "```\n\n"
        "Payload fields include `target_post_id` and exactly one decision: `maintain`, `revise`, or `concede`.\n\n"
        "```json\n"
        "{\n"
        f"  \"round\": {round_number},\n"
        "  \"target_post_id\": \"r<round>-<agent>-p<n>\",\n"
        "  \"decision\": \"revise\",\n"
        "  \"my_current_position\": \"...\",\n"
        "  \"opponent_claim\": \"...\",\n"
        "  \"opponent_evidence_i_checked\": [\"...\"],\n"
        "  \"reasoning\": \"...\",\n"
        "  \"accepted_part\": \"...\",\n"
        "  \"rejected_part\": \"...\",\n"
        "  \"updated_position\": \"...\",\n"
        "  \"still_disagree\": true\n"
        "}\n"
        "```\n"
    )


def _round_empty_state(items: list[Any], phase: str, *, item_type: str) -> str | None:
    if items:
        return None
    if item_type == "posts":
        if phase == "publish":
            return "waiting_for_current_round_posts"
        if phase == "closed":
            return "discussion_closed"
        return "no_current_round_posts"
    if phase == "publish":
        return "responses_not_open_yet"
    if phase == "respond":
        return "waiting_for_current_round_responses"
    if phase == "closed":
        return "discussion_closed"
    return "no_current_round_responses"


def _build_public_round(board: dict[str, Any]) -> dict[str, Any]:
    return _project_public_round(board)
def _agent_prompt_file(
    base_dir: Path,
    discussion_id: str,
    agent: dict[str, str],
    *,
    round_number: int,
    phase: str,
) -> tuple[str, str]:
    agent_id = agent["agent_id"]
    prompt_name = f"{agent_id}-r{round_number}-{phase}.md"
    prompt_path = base_dir / "prompts" / prompt_name
    prompt_path.write_text(
        _prompt_text(discussion_id, agent, round_number, phase),
        encoding="utf-8",
    )
    prompt_file = Path(DIR_WORKFLOW) / RUNTIME_DIR / MODE_DIR / discussion_id / "prompts" / prompt_name
    return prompt_name, str(prompt_file)


def _host_manifest_root(repo_root: Path) -> Path:
    repo_manifest = repo_root / DIR_WORKFLOW / "spec" / "runtime" / "host-assets.json"
    if repo_manifest.is_file():
        return repo_root
    for parent in _SCRIPT_DIR.parents:
        if (parent / DIR_WORKFLOW / "spec" / "runtime" / "host-assets.json").is_file():
            return parent
    return repo_root


def _normalize_host_id(host_id: str | None) -> str | None:
    if host_id is None or not str(host_id).strip():
        return None
    return _validate_identifier(str(host_id).strip(), label="host_id")


def _party_board_capability(repo_root: Path, host_id: str | None) -> Any | None:
    if host_id is None:
        return None
    manifest = load_host_manifest(_host_manifest_root(repo_root))
    return manifest.host_capability(host_id, PARTY_BOARD_ACTION_CAPABILITY)


def _party_board_action_is_supported(repo_root: Path, host_id: str | None) -> bool:
    capability = _party_board_capability(repo_root, host_id)
    if capability is None:
        return True
    return capability.status in SUPPORTED_HOST_CAPABILITY_STATUSES


def _party_board_fallback_actions(
    repo_root: Path,
    base_dir: Path,
    discussion_id: str,
    agents: list[dict[str, str]],
    *,
    round_number: int,
    phase: str,
    host_id: str,
) -> dict[str, Any]:
    capability = _party_board_capability(repo_root, host_id)
    fallback = capability.fallback if capability is not None else "inline_or_manual"
    (base_dir / "prompts").mkdir(parents=True, exist_ok=True)
    prompt_files: list[str] = []
    for agent in agents:
        _prompt_name, prompt_file = _agent_prompt_file(
            base_dir,
            discussion_id,
            agent,
            round_number=round_number,
            phase=phase,
        )
        prompt_files.append(prompt_file)
    document = _project_fallback_actions(
        discussion_id,
        round_number=round_number,
        phase=phase,
        host_id=host_id,
        fallback=fallback,
    )
    action = document["next_actions"][0]
    _append_action_history(base_dir, "action-issued", action)
    _append_audit(
        base_dir,
        "fallback",
        {
            "host_id": host_id,
            "capability": PARTY_BOARD_ACTION_CAPABILITY,
            "fallback": fallback,
            "round": round_number,
            "phase": phase,
            "prompt_files": prompt_files,
        },
    )
    return document
def _child_action(
    base_dir: Path,
    discussion_id: str,
    agent: dict[str, str],
    *,
    round_number: int,
    phase: str,
) -> dict[str, Any]:
    _prompt_name, prompt_file = _agent_prompt_file(
        base_dir,
        discussion_id,
        agent,
        round_number=round_number,
        phase=phase,
    )
    return _project_child_action(
        agent=agent,
        round_number=round_number,
        phase=phase,
        prompt_file=prompt_file,
    )
def _build_actions(
    repo_root: Path,
    base_dir: Path,
    discussion_id: str,
    agents: list[dict[str, str]],
    *,
    round_number: int,
    phase: str,
    host_id: str | None = None,
) -> dict[str, Any]:
    host_id = _normalize_host_id(host_id)
    if host_id is not None and not _party_board_action_is_supported(repo_root, host_id):
        return _party_board_fallback_actions(
            repo_root,
            base_dir,
            discussion_id,
            agents,
            round_number=round_number,
            phase=phase,
            host_id=host_id,
        )
    prompts_dir = base_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    child_actions = [
        _child_action(
            base_dir,
            discussion_id,
            agent,
            round_number=round_number,
            phase=phase,
        )
        for agent in agents
    ]
    document = _project_actions_document(
        discussion_id,
        child_actions=child_actions,
        agent_ids=[agent["agent_id"] for agent in agents],
        round_number=round_number,
        phase=phase,
    )
    for action in document["next_actions"]:
        _append_action_history(base_dir, "action-issued", action)
    return document
def _build_close_actions(
    base_dir: Path,
    agents: list[dict[str, str]],
    *,
    round_number: int,
    reason: str,
) -> list[dict[str, Any]]:
    actions = _project_close_actions(
        agents,
        round_number=round_number,
        reason=reason,
    )
    for action in actions:
        _append_action_history(base_dir, "action-issued", action)
        _append_audit(
            base_dir,
            "close",
            {
                "agent_id": action["agent_id"],
                "round": round_number,
                "reason": reason,
            },
        )
    return actions
def _empty_actions(discussion_id: str) -> dict[str, Any]:
    return _project_empty_actions(discussion_id)
def _write_actions_json(base_dir: Path, actions: dict[str, Any]) -> None:
    _write_json(base_dir / "actions.json", validate_actions_document(actions))


def _with_terminal_state(data: dict[str, Any], terminal: bool) -> dict[str, Any]:
    data["terminal"] = terminal
    return data


def _initial_board(
    discussion_id: str,
    topic: str,
    max_rounds: int,
    *,
    host_id: str | None = None,
) -> dict[str, Any]:
    return _project_initial_board(
        discussion_id,
        topic,
        max_rounds,
        host_id=host_id,
    )
def _initial_agents_state(discussion_id: str, agents: list[dict[str, str]]) -> dict[str, Any]:
    return _project_initial_agents_state(discussion_id, agents)
def init_discussion(
    repo_root: Path,
    *,
    discussion_id: str,
    topic: str,
    agent_specs: list[str],
    host_id: str | None = None,
) -> dict[str, Any]:
    _validate_identifier(discussion_id, label="discussion_id")
    config = get_party_mode_v2_config(repo_root)
    agents = [_parse_agent_spec(spec) for spec in agent_specs]
    _validate_agents(agents, config)
    host_id = _normalize_host_id(host_id)
    base_dir = discussion_dir(repo_root, discussion_id)
    with _state_lock(base_dir):
        max_rounds = int(config["max_rounds"])
        board = _initial_board(discussion_id, topic, max_rounds, host_id=host_id)
        agents_state = _initial_agents_state(discussion_id, agents)
        actions = _build_actions(
            repo_root,
            base_dir,
            discussion_id,
            agents,
            round_number=1,
            phase="publish",
            host_id=host_id,
        )
        public_round = _build_public_round(board)
        save_board(base_dir, board)
        _write_json(base_dir / "agents.json", agents_state)
        _write_actions_json(base_dir, actions)
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
    if agent_id:
        _validate_identifier(agent_id, label="agent_id")
    with _state_lock(base_dir):
        board = load_board(base_dir)
        public_round = _build_public_round(board)
        if agent_id:
            public_round["agent_id"] = agent_id
        _write_json(base_dir / "public_round.json", public_round)
        _append_audit(
            base_dir,
            "view",
            {"agent_id": agent_id, "round": public_round["round"], "phase": public_round["phase"]},
        )
    return public_round


def monitor_discussion(repo_root: Path, *, discussion_id: str) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    board = load_board(base_dir)
    agents = _read_json(base_dir / "agents.json")
    actions = validate_actions_document(_read_json(base_dir / "actions.json"))
    active_agents = [
        agent
        for agent in agents.get("agents", [])
        if str(agent.get("status", "")).startswith(("pending", "active"))
    ]
    return {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "terminal": board["round"]["phase"] == "closed",
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
    return _project_current_round(board)
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


def _build_post_payload(
    *,
    current_round: int,
    agent_id: str,
    payload: dict[str, Any],
    post_number: int,
) -> dict[str, Any]:
    return {
        "post_id": f"r{current_round}-{agent_id}-p{post_number}",
        "agent_id": agent_id,
        "claim": _require_non_empty_text(payload, "claim", "missing_claim"),
        "evidence": _require_non_empty_list(payload, "evidence", "missing_evidence"),
        "risk": _require_non_empty_text(payload, "risk", "missing_risk"),
        "tradeoff": _require_non_empty_text(payload, "tradeoff", "missing_tradeoff"),
        "acceptance_signal": _require_non_empty_text(
            payload,
            "acceptance_signal",
            "missing_acceptance_signal",
        ),
        "what_would_change_my_mind": _require_non_empty_text(
            payload,
            "what_would_change_my_mind",
            "missing_what_would_change_my_mind",
        ),
    }


def _write_runtime_state(base_dir: Path, board: dict[str, Any]) -> None:
    save_board(base_dir, board)
    _write_json(base_dir / "public_round.json", _build_public_round(board))


def post_submission(
    repo_root: Path,
    *,
    discussion_id: str,
    agent_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _validate_identifier(agent_id, label="agent_id")
    base_dir = discussion_dir(repo_root, discussion_id)
    config = get_party_mode_v2_config(repo_root)
    with _state_lock(base_dir):
        board = load_board(base_dir)
        if board["round"]["phase"] != "publish":
            raise ValueError("phase_not_publish")
        if agent_id not in _active_agent_ids(base_dir):
            raise ValueError("agent_not_active")
        current_round = int(board["round"]["current"])
        _payload_round(payload, current_round, config)
        current = _current_round(board)
        posts = current.setdefault("posts", [])
        if any(post.get("agent_id") == agent_id for post in posts):
            raise ValueError("duplicate_post")
        post = _build_post_payload(
            current_round=current_round,
            agent_id=agent_id,
            payload=payload,
            post_number=len(posts) + 1,
        )
        posts.append(post)
        _write_runtime_state(base_dir, board)
        _append_audit(base_dir, "post", {"agent_id": agent_id, "post_id": post["post_id"]})
        return post


def _current_post_ids(board: dict[str, Any]) -> set[str]:
    return {str(post["post_id"]) for post in _current_round(board).get("posts", [])}


def _current_post_agent_map(board: dict[str, Any]) -> dict[str, str]:
    return {
        str(post["post_id"]): str(post["agent_id"])
        for post in _current_round(board).get("posts", [])
    }


def _payload_round(payload: dict[str, Any], current_round: int, config: dict[str, int | bool]) -> int:
    if "round" not in payload:
        if bool(config.get("require_current_round_only", True)):
            raise ValueError("missing_round")
        return current_round
    try:
        round_number = int(payload.get("round"))
    except (TypeError, ValueError):
        raise ValueError("missing_round") from None
    if round_number != current_round:
        raise ValueError("round_mismatch")
    return round_number


def _require_bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"invalid_{key}")
    return value


def _confidence(payload: dict[str, Any]) -> str:
    value = str(payload.get("confidence_after_review", "medium"))
    if value not in CONFIDENCE_VALUES:
        raise ValueError("invalid_confidence_after_review")
    return value


def _response_target_and_decision(
    board: dict[str, Any],
    agent_id: str,
    payload: dict[str, Any],
) -> tuple[str, str]:
    target_post_id = _require_non_empty_text(payload, "target_post_id", "missing_target_post_id")
    post_agent_map = _current_post_agent_map(board)
    if target_post_id not in post_agent_map:
        raise ValueError("target_not_in_current_round")
    if post_agent_map[target_post_id] == agent_id:
        raise ValueError("self_target_response")
    decision = _require_non_empty_text(payload, "decision", "missing_decision")
    if decision not in {"maintain", "revise", "concede"}:
        raise ValueError("invalid_decision")
    return target_post_id, decision


def _validate_response_target_limit(
    responses: list[Any],
    *,
    agent_id: str,
    target_post_id: str,
    max_targets: int,
) -> None:
    agent_targets = {
        str(response["target_post_id"])
        for response in responses
        if str(response.get("agent_id")) == agent_id
    }
    if target_post_id in agent_targets:
        raise ValueError("duplicate_target_response")
    if len(agent_targets) >= max_targets:
        raise ValueError("too_many_rebuttal_targets")


def _build_response_base(
    *,
    current_round: int,
    agent_id: str,
    target_post_id: str,
    decision: str,
    payload: dict[str, Any],
    response_number: int,
) -> dict[str, Any]:
    return {
        "response_id": f"r{current_round}-{agent_id}-resp{response_number}",
        "agent_id": agent_id,
        "target_post_id": target_post_id,
        "decision": decision,
        "my_current_position": _require_non_empty_text(
            payload,
            "my_current_position",
            "missing_current_position",
        ),
        "opponent_claim": _require_non_empty_text(
            payload,
            "opponent_claim",
            "missing_opponent_claim",
        ),
        "opponent_evidence_i_checked": _require_non_empty_list(
            payload,
            "opponent_evidence_i_checked",
            "missing_checked_evidence",
        ),
        "reasoning": _require_non_empty_text(payload, "reasoning", "missing_reasoning"),
        "confidence_after_review": _confidence(payload),
    }


def _apply_concede_response(response: dict[str, Any], payload: dict[str, Any]) -> None:
    response["why_opponent_is_right"] = _require_non_empty_text(
        payload,
        "why_opponent_is_right",
        "shallow_concession",
    )
    response["accepted_evidence"] = _require_non_empty_list(
        payload,
        "accepted_evidence",
        "shallow_concession",
    )
    response["why_my_previous_position_failed"] = _require_non_empty_text(
        payload,
        "why_my_previous_position_failed",
        "shallow_concession",
    )
    response["position_delta"] = "changed"
    response["still_disagree"] = False


def _apply_revise_response(response: dict[str, Any], payload: dict[str, Any]) -> None:
    response["accepted_part"] = _require_non_empty_text(
        payload,
        "accepted_part",
        "vague_revision",
    )
    response["rejected_part"] = _require_non_empty_text(
        payload,
        "rejected_part",
        "vague_revision",
    )
    response["updated_position"] = _require_non_empty_text(
        payload,
        "updated_position",
        "vague_revision",
    )
    response["position_delta"] = str(payload.get("position_delta") or "narrowed")
    response["still_disagree"] = _require_bool(payload, "still_disagree", True)


def _apply_maintain_response(response: dict[str, Any], payload: dict[str, Any]) -> None:
    response["why_opponent_is_wrong"] = _require_non_empty_text(
        payload,
        "why_opponent_is_wrong",
        "unsupported_rebuttal",
    )
    counter_evidence = payload.get("counter_evidence")
    counter_reasoning = payload.get("counter_reasoning")
    if not counter_evidence and not counter_reasoning:
        raise ValueError("unsupported_rebuttal")
    if counter_evidence is not None:
        if not isinstance(counter_evidence, list) or not counter_evidence:
            raise ValueError("unsupported_rebuttal")
        response["counter_evidence"] = counter_evidence
    if counter_reasoning is not None:
        response["counter_reasoning"] = str(counter_reasoning)
    response["position_delta"] = "unchanged"
    response["still_disagree"] = True


def _apply_decision_response(
    response: dict[str, Any],
    *,
    decision: str,
    payload: dict[str, Any],
) -> None:
    if decision == "concede":
        _apply_concede_response(response, payload)
    elif decision == "revise":
        _apply_revise_response(response, payload)
    else:
        _apply_maintain_response(response, payload)


def respond_submission(
    repo_root: Path,
    *,
    discussion_id: str,
    agent_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _validate_identifier(agent_id, label="agent_id")
    base_dir = discussion_dir(repo_root, discussion_id)
    config = get_party_mode_v2_config(repo_root)
    with _state_lock(base_dir):
        board = load_board(base_dir)
        if board["round"]["phase"] != "respond":
            raise ValueError("phase_not_respond")
        if agent_id not in _active_agent_ids(base_dir):
            raise ValueError("agent_not_active")
        current_round = int(board["round"]["current"])
        _payload_round(payload, current_round, config)
        target_post_id, decision = _response_target_and_decision(board, agent_id, payload)
        current = _current_round(board)
        responses = current.setdefault("responses", [])
        _validate_response_target_limit(
            responses,
            agent_id=agent_id,
            target_post_id=target_post_id,
            max_targets=int(config["max_rebuttal_targets_per_agent"]),
        )
        response = _build_response_base(
            current_round=current_round,
            agent_id=agent_id,
            target_post_id=target_post_id,
            decision=decision,
            payload=payload,
            response_number=len(responses) + 1,
        )
        _apply_decision_response(response, decision=decision, payload=payload)
        responses.append(response)
        _write_runtime_state(base_dir, board)
        _append_audit(
            base_dir,
            "respond",
            {"agent_id": agent_id, "response_id": response["response_id"]},
        )
        return response


def _write_actions_for_phase(
    repo_root: Path,
    base_dir: Path,
    discussion_id: str,
    round_number: int,
    phase: str,
    *,
    host_id: str | None = None,
    leading_actions: list[dict[str, Any]] | None = None,
) -> None:
    actions = _build_actions(
        repo_root,
        base_dir,
        discussion_id,
        _agent_lenses(base_dir),
        round_number=round_number,
        phase=phase,
        host_id=host_id,
    )
    if leading_actions:
        actions["next_actions"] = leading_actions + actions["next_actions"]
    _write_actions_json(base_dir, actions)


def _advance_publish_phase(
    repo_root: Path,
    *,
    base_dir: Path,
    discussion_id: str,
    board: dict[str, Any],
    current: dict[str, Any],
    active_agents: list[str],
    current_round: int,
) -> dict[str, Any]:
    transition = _advance_board_state(
        board,
        active_agent_ids=active_agents,
        fresh_context_per_round=True,
    )
    _write_runtime_state(base_dir, board)
    _write_actions_for_phase(
        repo_root,
        base_dir,
        discussion_id,
        transition["next_actions"]["round"],
        transition["next_actions"]["phase"],
        host_id=board.get("host_id"),
    )
    _append_audit(
        base_dir,
        "advance",
        {"round": current_round, "from": transition["from"], "to": transition["to"]},
    )
    return monitor_discussion(repo_root, discussion_id=discussion_id)
def _close_discussion(
    repo_root: Path,
    *,
    base_dir: Path,
    discussion_id: str,
    board: dict[str, Any],
    current_round: int,
    reason: str,
) -> dict[str, Any]:
    board["round"]["phase"] = "closed"
    board["termination"] = {"reason": reason}
    _write_runtime_state(base_dir, board)
    _write_actions_json(base_dir, _empty_actions(discussion_id))
    _append_audit(
        base_dir,
        "advance",
        {"round": current_round, "from": "respond", "to": "closed", "reason": reason},
    )
    return finalize_discussion(repo_root, discussion_id=discussion_id)


def _advance_next_round(
    repo_root: Path,
    *,
    base_dir: Path,
    discussion_id: str,
    board: dict[str, Any],
    current_round: int,
) -> dict[str, Any]:
    next_round = current_round + 1
    config = get_party_mode_v2_config(repo_root)
    close_actions = []
    if bool(config.get("fresh_context_per_round", True)):
        close_actions = _build_close_actions(
            base_dir,
            _agent_lenses(base_dir),
            round_number=current_round,
            reason="fresh_context_per_round",
        )
    board["round"] = {"current": next_round, "max": board["round"]["max"], "phase": "publish"}
    board.setdefault("rounds", []).append(
        {"round": next_round, "posts": [], "responses": [], "moderator_events": []}
    )
    _write_runtime_state(base_dir, board)
    _write_actions_for_phase(
        repo_root,
        base_dir,
        discussion_id,
        next_round,
        "publish",
        host_id=board.get("host_id"),
        leading_actions=close_actions,
    )
    _append_audit(
        base_dir,
        "advance",
        {"round": current_round, "from": "respond", "to": "publish", "next_round": next_round},
    )
    return monitor_discussion(repo_root, discussion_id=discussion_id)


def _advance_respond_phase(
    repo_root: Path,
    *,
    base_dir: Path,
    discussion_id: str,
    board: dict[str, Any],
    current: dict[str, Any],
    active_agents: list[str],
    current_round: int,
) -> dict[str, Any]:
    config = get_party_mode_v2_config(repo_root)
    transition = _advance_board_state(
        board,
        active_agent_ids=active_agents,
        fresh_context_per_round=bool(config.get("fresh_context_per_round", True)),
    )
    if transition["to"] == "closed":
        _write_runtime_state(base_dir, board)
        _write_actions_json(base_dir, _empty_actions(discussion_id))
        _append_audit(
            base_dir,
            "advance",
            {
                "round": current_round,
                "from": transition["from"],
                "to": transition["to"],
                "reason": transition["reason"],
            },
        )
        return finalize_discussion(repo_root, discussion_id=discussion_id)

    if transition["to"] != "publish":
        raise ValueError("phase_not_advanceable")
    close_actions = []
    close_reason = transition.get("close_children_reason")
    if close_reason:
        close_actions = _build_close_actions(
            base_dir,
            _agent_lenses(base_dir),
            round_number=current_round,
            reason=str(close_reason),
        )
    _write_runtime_state(base_dir, board)
    _write_actions_for_phase(
        repo_root,
        base_dir,
        discussion_id,
        transition["next_actions"]["round"],
        transition["next_actions"]["phase"],
        host_id=board.get("host_id"),
        leading_actions=close_actions,
    )
    _append_audit(
        base_dir,
        "advance",
        {
            "round": current_round,
            "from": transition["from"],
            "to": transition["to"],
            "next_round": transition["next_round"],
        },
    )
    return monitor_discussion(repo_root, discussion_id=discussion_id)
def advance_discussion(repo_root: Path, *, discussion_id: str) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    with _state_lock(base_dir):
        board = load_board(base_dir)
        current = _current_round(board)
        active_agents = _active_agent_ids(base_dir)
        current_round = int(board["round"]["current"])
        if board["round"]["phase"] == "publish":
            return _advance_publish_phase(
                repo_root,
                base_dir=base_dir,
                discussion_id=discussion_id,
                board=board,
                current=current,
                active_agents=active_agents,
                current_round=current_round,
            )

        if board["round"]["phase"] != "respond":
            raise ValueError("phase_not_advanceable")

        return _advance_respond_phase(
            repo_root,
            base_dir=base_dir,
            discussion_id=discussion_id,
            board=board,
            current=current,
            active_agents=active_agents,
            current_round=current_round,
        )


def _set_all_agents_status(base_dir: Path, status: str) -> None:
    agents = _read_json(base_dir / "agents.json")
    for agent in agents.get("agents", []):
        agent["status"] = status
    _write_json(base_dir / "agents.json", agents)


def _default_agent_status(action_type: str, outcome: str) -> str:
    if outcome != "success":
        return "failed"
    if action_type == "close_child":
        return "closed"
    return "active"


def _ensure_finalizable(
    base_dir: Path,
    discussion_id: str,
    board: dict[str, Any],
    *,
    manual_termination: bool,
) -> None:
    changed = _ensure_finalizable_state(
        board,
        manual_termination=manual_termination,
    )
    if changed:
        _write_runtime_state(base_dir, board)
        _write_actions_json(base_dir, _empty_actions(discussion_id))
def _discussion_posts(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [post for item in board.get("rounds", []) for post in item.get("posts", [])]


def _discussion_responses(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        response
        for item in board.get("rounds", [])
        for response in item.get("responses", [])
    ]


def _round_responses(board: dict[str, Any], round_number: int) -> list[dict[str, Any]]:
    return [
        response
        for item in board.get("rounds", [])
        if int(item.get("round", -1)) == round_number
        for response in item.get("responses", [])
    ]


def _historical_disagreements(
    board: dict[str, Any],
    current_round: int,
) -> list[dict[str, Any]]:
    return [
        response
        for item in board.get("rounds", [])
        if int(item.get("round", -1)) < current_round
        for response in item.get("responses", [])
        if response.get("still_disagree")
    ]


def _round_summary_phase(board: dict[str, Any], round_number: int) -> str:
    if round_number == int(board["round"]["current"]):
        return str(board["round"]["phase"])
    return "completed"


def _rounds_summary(board: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in board.get("rounds", []):
        round_number = int(item.get("round", 0))
        posts = item.get("posts", [])
        responses = item.get("responses", [])
        unresolved = [r for r in responses if r.get("still_disagree")]
        summaries.append(
            {
                "round": round_number,
                "phase": _round_summary_phase(board, round_number),
                "post_count": len(posts),
                "response_count": len(responses),
                "unresolved_count": len(unresolved),
            }
        )
    return summaries


def _action_results_summary(base_dir: Path) -> list[dict[str, Any]]:
    history_path = base_dir / "action_history.jsonl"
    if not history_path.is_file():
        return []
    results: list[dict[str, Any]] = []
    with history_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("event") != "action-result":
                continue
            payload = entry.get("payload", {})
            summary: dict[str, Any] = {
                "action_id": payload.get("action_id"),
                "type": payload.get("type"),
                "outcome": payload.get("outcome"),
            }
            if payload.get("agent_id"):
                summary["agent_id"] = payload["agent_id"]
            results.append(summary)
    return results


def _accepted_evidence_summary(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for response in responses:
        if response.get("decision") != "concede":
            continue
        evidence = response.get("accepted_evidence", [])
        if not evidence:
            continue
        summaries.append(
            {
                "agent_id": response.get("agent_id"),
                "target_post_id": response.get("target_post_id"),
                "accepted_evidence": evidence,
            }
        )
    return summaries

def _build_final_report(
    *,
    base_dir: Path,
    discussion_id: str,
    board: dict[str, Any],
    posts: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    current_responses: list[dict[str, Any]],
    historical_disagreements: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    return _project_final_report(
        discussion_id=discussion_id,
        board=board,
        action_results=_project_action_results_summary(base_dir),
        stop_reason=stop_reason,
    )
def _report_pro_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"agent_id": post["agent_id"], "claim": post["claim"], "evidence": post["evidence"]}
        for post in posts
    ]


def _report_con_responses(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": response["agent_id"],
            "target_post_id": response["target_post_id"],
            "reasoning": response["reasoning"],
        }
        for response in responses
        if response.get("decision") == "maintain"
    ]


def _responses_with_delta(
    responses: list[dict[str, Any]],
    position_delta: str,
) -> list[dict[str, Any]]:
    return [
        response for response in responses if response.get("position_delta") == position_delta
    ]


def _responses_with_decision(
    responses: list[dict[str, Any]],
    decision: str,
) -> list[dict[str, Any]]:
    return [
        response for response in responses if response.get("decision") == decision
    ]


def finalize_discussion(
    repo_root: Path,
    *,
    discussion_id: str,
    manual_termination: bool = False,
) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    with _state_lock(base_dir):
        board = load_board(base_dir)
        _ensure_finalizable(
            base_dir,
            discussion_id,
            board,
            manual_termination=manual_termination,
        )
        _set_all_agents_status(base_dir, "closed")
        current_round = int(board["round"]["current"])
        stop_reason = board.get("termination", {}).get("reason") or "manual_finalize"
        report = _build_final_report(
            base_dir=base_dir,
            discussion_id=discussion_id,
            board=board,
            posts=_discussion_posts(board),
            responses=_discussion_responses(board),
            current_responses=_round_responses(board, current_round),
            historical_disagreements=_historical_disagreements(board, current_round),
            stop_reason=stop_reason,
        )
        reports_dir = base_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        _write_json(reports_dir / "final.json", report)
        _append_audit(base_dir, "finalize", {"stop_reason": stop_reason})
        return report


def record_action_result(
    repo_root: Path,
    *,
    discussion_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    base_dir = discussion_dir(repo_root, discussion_id)
    with _state_lock(base_dir):
        action_id = _require_non_empty_text(payload, "action_id", "missing_action_id")
        action_type = _require_non_empty_text(payload, "type", "missing_action_type")
        outcome = _require_non_empty_text(payload, "outcome", "missing_outcome")
        result = {
            "action_id": action_id,
            "type": action_type,
            "outcome": outcome,
        }
        agent_id = payload.get("agent_id")
        if agent_id:
            agent_id = _validate_identifier(str(agent_id), label="agent_id")
            result["agent_id"] = agent_id
        host_child_id = payload.get("host_child_id")
        if host_child_id:
            result["host_child_id"] = str(host_child_id)
        agent_status = str(payload.get("agent_status", _default_agent_status(action_type, outcome)))
        if agent_id:
            agents = _read_json(base_dir / "agents.json")
            for agent in agents.get("agents", []):
                if str(agent.get("agent_id")) == agent_id:
                    agent["status"] = agent_status
                    if host_child_id:
                        agent["host_child_id"] = str(host_child_id)
                    break
            _write_json(base_dir / "agents.json", agents)
        _append_action_history(base_dir, "action-result", result)
        _append_audit(base_dir, "action-result", result)
        return result


def _print_json(data: dict[str, Any]) -> None:
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    control_surface = json.dumps(data.get("next_actions", []), ensure_ascii=False)
    if any(term in control_surface for term in HOST_FORBIDDEN_TERMS):
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
    init_parser.add_argument("--host-id", default=None)

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
    finalize_parser.add_argument("--manual-termination", action="store_true")

    action_result_parser = subcommands.add_parser("record-action-result")
    action_result_parser.add_argument("--discussion-id", required=True)
    action_result_parser.add_argument("--file", type=Path, required=True)

    return parser


def _read_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload_must_be_object")
    return payload


def _command_result(repo_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "init":
        return init_discussion(
            repo_root,
            discussion_id=args.discussion_id,
            topic=args.topic,
            agent_specs=args.agent,
            host_id=args.host_id,
        )
    if args.command == "view":
        return view_discussion(
            repo_root,
            discussion_id=args.discussion_id,
            agent_id=args.agent_id,
        )
    if args.command == "monitor":
        return monitor_discussion(repo_root, discussion_id=args.discussion_id)
    if args.command == "post":
        return _payload_submission_result(repo_root, args, responder=False)
    if args.command == "respond":
        return _payload_submission_result(repo_root, args, responder=True)
    if args.command == "advance":
        return advance_discussion(repo_root, discussion_id=args.discussion_id)
    if args.command == "finalize":
        return finalize_discussion(
            repo_root,
            discussion_id=args.discussion_id,
            manual_termination=args.manual_termination,
        )
    if args.command == "record-action-result":
        return record_action_result(
            repo_root,
            discussion_id=args.discussion_id,
            payload=_read_payload(args.file),
        )
    raise ValueError(f"unknown command: {args.command}")


def _payload_submission_result(
    repo_root: Path,
    args: argparse.Namespace,
    *,
    responder: bool,
) -> dict[str, Any]:
    submit = respond_submission if responder else post_submission
    return submit(
        repo_root,
        discussion_id=args.discussion_id,
        agent_id=args.agent_id,
        payload=_read_payload(args.file),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root or get_repo_root()
    try:
        _print_json(_command_result(repo_root, args))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
