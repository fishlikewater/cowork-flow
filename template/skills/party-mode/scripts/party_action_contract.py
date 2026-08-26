#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Host-neutral action contract checks for Party Mode V2."""

from __future__ import annotations

from typing import Any

ACTION_TYPES = {
    "dispatch_child",
    "send_control_message",
    "wait_children",
    "list_children",
    "close_child",
    "report_to_user",
}

DOCUMENT_FIELDS = {"schema_version", "discussion_id", "next_actions"}
ACTION_FIELDS = {
    "action_id",
    "type",
    "agent_id",
    "agent_ids",
    "agent_kind",
    "lens",
    "message_kind",
    "prompt_file",
    "reason",
}
REQUIRED_FIELDS_BY_TYPE = {
    "dispatch_child": {
        "action_id",
        "type",
        "agent_id",
        "agent_kind",
        "lens",
        "message_kind",
        "prompt_file",
    },
    "send_control_message": {
        "action_id",
        "type",
        "agent_id",
        "agent_kind",
        "lens",
        "message_kind",
        "prompt_file",
    },
    "wait_children": {"action_id", "type", "agent_ids"},
    "list_children": {"action_id", "type"},
    "close_child": {"action_id", "type", "agent_id", "reason"},
    "report_to_user": {"action_id", "type", "reason"},
}


class PartyActionContractError(ValueError):
    """Raised when a Party Mode action document violates the schema contract."""


def _require_non_empty_string(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PartyActionContractError(error)
    return value


def _validate_agent_ids(value: Any, index: int) -> None:
    if not isinstance(value, list):
        raise PartyActionContractError(f"invalid_action_field:{index}:agent_ids")
    for agent_index, agent_id in enumerate(value):
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise PartyActionContractError(
                f"invalid_action_field:{index}:agent_ids[{agent_index}]"
            )


def _validate_action(action: Any, index: int) -> None:
    if not isinstance(action, dict):
        raise PartyActionContractError(f"invalid_action:{index}")
    unknown = sorted(set(action) - ACTION_FIELDS)
    if unknown:
        raise PartyActionContractError(f"unexpected_action_field:{index}:{unknown[0]}")

    action_type = _require_non_empty_string(action.get("type"), f"invalid_action_type:{index}")
    if action_type not in ACTION_TYPES:
        raise PartyActionContractError(f"invalid_action_type:{index}:{action_type}")

    missing = sorted(REQUIRED_FIELDS_BY_TYPE[action_type] - set(action))
    if missing:
        raise PartyActionContractError(f"missing_action_field:{index}:{missing[0]}")

    _require_non_empty_string(action.get("action_id"), f"invalid_action_field:{index}:action_id")
    for key in ("agent_id", "agent_kind", "lens", "message_kind", "prompt_file", "reason"):
        if key in action:
            _require_non_empty_string(action.get(key), f"invalid_action_field:{index}:{key}")
    if "agent_ids" in action:
        _validate_agent_ids(action["agent_ids"], index)


def validate_actions_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise PartyActionContractError("invalid_actions_document")
    unknown = sorted(set(document) - DOCUMENT_FIELDS)
    if unknown:
        raise PartyActionContractError(f"unexpected_actions_field:{unknown[0]}")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise PartyActionContractError("invalid_actions_schema_version")
    _require_non_empty_string(document.get("discussion_id"), "invalid_actions_discussion_id")
    actions = document.get("next_actions")
    if not isinstance(actions, list):
        raise PartyActionContractError("invalid_actions_next_actions")
    for index, action in enumerate(actions):
        _validate_action(action, index)
    return document
