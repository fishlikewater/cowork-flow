#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host-neutral Party Mode V2 action document builders."""

from __future__ import annotations

from typing import Any

from party_action_contract import validate_actions_document

PARTY_BOARD_ACTION_CAPABILITY = "party_board_action"


def child_action(
    *,
    agent: dict[str, str],
    round_number: int,
    phase: str,
    prompt_file: str,
) -> dict[str, Any]:
    agent_id = agent["agent_id"]
    return {
        "action_id": f"r{round_number}-{phase}-{agent_id}",
        "type": "dispatch_child" if phase == "publish" else "send_control_message",
        "agent_id": agent_id,
        "agent_kind": "advisory",
        "lens": agent["lens"],
        "message_kind": f"board_{phase}",
        "prompt_file": prompt_file,
    }


def actions_document(
    discussion_id: str,
    *,
    child_actions: list[dict[str, Any]],
    agent_ids: list[str],
    round_number: int,
    phase: str,
) -> dict[str, Any]:
    actions = list(child_actions)
    actions.append(
        {
            "action_id": f"r{round_number}-{phase}-wait",
            "type": "wait_children",
            "agent_ids": list(agent_ids),
        }
    )
    return validate_actions_document(
        {"schema_version": 1, "discussion_id": discussion_id, "next_actions": actions}
    )


def fallback_actions_document(
    discussion_id: str,
    *,
    round_number: int,
    phase: str,
    host_id: str,
    fallback: str,
) -> dict[str, Any]:
    action = {
        "action_id": f"r{round_number}-{phase}-fallback",
        "type": "report_to_user",
        "reason": (
            f"{PARTY_BOARD_ACTION_CAPABILITY} unsupported for host {host_id}; "
            f"fallback={fallback}; manually deliver prompt files or record unable_to_dispatch"
        ),
    }
    return validate_actions_document(
        {"schema_version": 1, "discussion_id": discussion_id, "next_actions": [action]}
    )


def close_actions(
    agents: list[dict[str, str]],
    *,
    round_number: int,
    reason: str,
) -> list[dict[str, Any]]:
    return [
        {
            "action_id": f"r{round_number}-close-{agent['agent_id']}",
            "type": "close_child",
            "agent_id": agent["agent_id"],
            "reason": reason,
        }
        for agent in agents
    ]


def empty_actions_document(discussion_id: str) -> dict[str, Any]:
    return validate_actions_document(
        {"schema_version": 1, "discussion_id": discussion_id, "next_actions": []}
    )
