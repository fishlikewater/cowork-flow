#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure Party Mode V2 board state transitions and projections."""

from __future__ import annotations

from typing import Any

CONFIDENCE_VALUES = {"low", "medium", "high"}


def round_empty_state(items: list[Any], phase: str, *, item_type: str) -> str | None:
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


def build_public_round(board: dict[str, Any]) -> dict[str, Any]:
    """Project the public current-round board without file IO."""

    current_round_number = int(board["round"]["current"])
    current = next(
        (
            item
            for item in board.get("rounds", [])
            if int(item.get("round", -1)) == current_round_number
        ),
        {"round": current_round_number, "posts": [], "responses": [], "moderator_events": []},
    )
    posts = list(current.get("posts", []))
    responses = list(current.get("responses", []))
    phase = board["round"]["phase"]
    expected_next_action = {
        "publish": "post",
        "respond": "respond",
        "closed": "finalized",
    }.get(str(phase), "monitor")
    return {
        "schema_version": 1,
        "discussion_id": board["discussion_id"],
        "round": current_round_number,
        "phase": phase,
        "topic": board["topic"],
        "visible_posts": posts,
        "visible_responses": responses,
        "moderator_events": list(current.get("moderator_events", [])),
        "empty_state": {
            "visible_posts": round_empty_state(posts, phase, item_type="posts"),
            "visible_responses": round_empty_state(responses, phase, item_type="responses"),
        },
        "expected_next_action": expected_next_action,
    }


def initial_board(
    discussion_id: str,
    topic: str,
    max_rounds: int,
    *,
    host_id: str | None = None,
) -> dict[str, Any]:
    board: dict[str, Any] = {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "topic": topic,
        "round": {"current": 1, "max": max_rounds, "phase": "publish"},
        "rounds": [{"round": 1, "posts": [], "responses": [], "moderator_events": []}],
        "termination": {"reason": None},
    }
    if host_id is not None:
        board["host_id"] = host_id
    return board


def initial_agents_state(discussion_id: str, agents: list[dict[str, str]]) -> dict[str, Any]:
    return {
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


def current_round(board: dict[str, Any]) -> dict[str, Any]:
    current_round_number = int(board["round"]["current"])
    for item in board.get("rounds", []):
        if int(item.get("round", -1)) == current_round_number:
            return item
    item = {"round": current_round_number, "posts": [], "responses": [], "moderator_events": []}
    board.setdefault("rounds", []).append(item)
    return item


def advance_board_state(
    board: dict[str, Any],
    *,
    active_agent_ids: list[str],
    fresh_context_per_round: bool,
) -> dict[str, Any]:
    """Advance the Party board in memory and return action/report facts."""

    current = current_round(board)
    current_round_number = int(board["round"]["current"])
    phase = board["round"]["phase"]
    if phase == "publish":
        posted_agents = {str(post["agent_id"]) for post in current.get("posts", [])}
        missing = sorted(set(active_agent_ids) - posted_agents)
        if missing:
            raise ValueError(f"publish_incomplete:{','.join(missing)}")
        board["round"]["phase"] = "respond"
        return {
            "round": current_round_number,
            "from": "publish",
            "to": "respond",
            "next_actions": {"round": current_round_number, "phase": "respond"},
        }

    if phase != "respond":
        raise ValueError("phase_not_advanceable")

    responded_agents = {str(response["agent_id"]) for response in current.get("responses", [])}
    missing = sorted(set(active_agent_ids) - responded_agents)
    if missing:
        raise ValueError(f"respond_incomplete:{','.join(missing)}")
    if not any(bool(response.get("still_disagree")) for response in current.get("responses", [])):
        board["round"]["phase"] = "closed"
        board["termination"] = {"reason": "converged"}
        return {"round": current_round_number, "from": "respond", "to": "closed", "reason": "converged"}
    if current_round_number >= int(board["round"]["max"]):
        board["round"]["phase"] = "closed"
        board["termination"] = {"reason": "max_rounds_unconverged"}
        return {
            "round": current_round_number,
            "from": "respond",
            "to": "closed",
            "reason": "max_rounds_unconverged",
        }

    next_round_number = current_round_number + 1
    board["round"] = {
        "current": next_round_number,
        "max": board["round"]["max"],
        "phase": "publish",
    }
    board.setdefault("rounds", []).append(
        {"round": next_round_number, "posts": [], "responses": [], "moderator_events": []}
    )
    transition: dict[str, Any] = {
        "round": current_round_number,
        "from": "respond",
        "to": "publish",
        "next_round": next_round_number,
        "next_actions": {"round": next_round_number, "phase": "publish"},
    }
    if fresh_context_per_round:
        transition["close_children_reason"] = "fresh_context_per_round"
    return transition


def ensure_finalizable(board: dict[str, Any], *, manual_termination: bool) -> bool:
    """Close a board in memory for manual finalization when allowed."""

    if board["round"]["phase"] == "closed":
        return False
    if not manual_termination:
        raise ValueError("finalize_requires_closed_discussion")
    board["round"]["phase"] = "closed"
    board["termination"] = {"reason": "manual_terminated"}
    return True
