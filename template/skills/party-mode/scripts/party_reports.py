#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure Party Mode V2 final report projection helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def discussion_posts(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [post for item in board.get("rounds", []) for post in item.get("posts", [])]


def discussion_responses(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        response
        for item in board.get("rounds", [])
        for response in item.get("responses", [])
    ]


def round_responses(board: dict[str, Any], round_number: int) -> list[dict[str, Any]]:
    return [
        response
        for item in board.get("rounds", [])
        if int(item.get("round", -1)) == round_number
        for response in item.get("responses", [])
    ]


def historical_disagreements(board: dict[str, Any], current_round: int) -> list[dict[str, Any]]:
    return [
        response
        for item in board.get("rounds", [])
        if int(item.get("round", -1)) < current_round
        for response in item.get("responses", [])
        if response.get("still_disagree")
    ]


def round_summary_phase(board: dict[str, Any], round_number: int) -> str:
    if round_number == int(board["round"]["current"]):
        return str(board["round"]["phase"])
    return "completed"


def rounds_summary(board: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in board.get("rounds", []):
        round_number = int(item.get("round", 0))
        posts = item.get("posts", [])
        responses = item.get("responses", [])
        unresolved = [response for response in responses if response.get("still_disagree")]
        summaries.append(
            {
                "round": round_number,
                "phase": round_summary_phase(board, round_number),
                "post_count": len(posts),
                "response_count": len(responses),
                "unresolved_count": len(unresolved),
            }
        )
    return summaries


def action_results_summary(base_dir: Path) -> list[dict[str, Any]]:
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


def accepted_evidence_summary(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def report_pro_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"agent_id": post["agent_id"], "claim": post["claim"], "evidence": post["evidence"]}
        for post in posts
    ]


def report_con_responses(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": response["agent_id"],
            "target_post_id": response["target_post_id"],
            "reasoning": response["reasoning"],
        }
        for response in responses
        if response.get("decision") == "maintain"
    ]


def responses_with_delta(responses: list[dict[str, Any]], position_delta: str) -> list[dict[str, Any]]:
    return [response for response in responses if response.get("position_delta") == position_delta]


def responses_with_decision(responses: list[dict[str, Any]], decision: str) -> list[dict[str, Any]]:
    return [response for response in responses if response.get("decision") == decision]


def build_final_report(
    *,
    discussion_id: str,
    board: dict[str, Any],
    action_results: list[dict[str, Any]],
    stop_reason: str,
) -> dict[str, Any]:
    """Build a final advisory report from board facts without file writes."""

    current_round = int(board["round"]["current"])
    posts = discussion_posts(board)
    responses = discussion_responses(board)
    current_responses = round_responses(board, current_round)
    current_unresolved = [
        response for response in current_responses if response.get("still_disagree")
    ]
    board_status = {
        "round": current_round,
        "phase": board["round"]["phase"],
        "max_rounds": board["round"]["max"],
        "termination_reason": stop_reason,
    }
    return {
        "schema_version": 1,
        "discussion_id": discussion_id,
        "terminal": True,
        "stop_reason": stop_reason,
        "board_status": board_status,
        "rounds_summary": rounds_summary(board),
        "action_results": list(action_results),
        "accepted_evidence": accepted_evidence_summary(responses),
        "next_actions": [],
        "pro": report_pro_posts(posts),
        "con": report_con_responses(responses),
        "changed_positions": responses_with_delta(responses, "changed"),
        "maintained_positions": responses_with_delta(responses, "unchanged"),
        "revised_positions": responses_with_decision(responses, "revise"),
        "current_unresolved_disagreements": current_unresolved,
        "historical_disagreements": historical_disagreements(board, current_round),
        "unresolved_disagreements": current_unresolved,
    }
