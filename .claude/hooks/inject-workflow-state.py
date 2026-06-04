#!/usr/bin/env python3
"""Emit cowork-flow workflow context for Claude Code hooks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

TAG_RE = re.compile(
    r"\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*\[/workflow-state:\1\]",
    re.DOTALL,
)
DEFAULT_CONTRACT_REGISTRY = {
    "contracts": [
        {
            "id": "COWORK_ENTRY_CONTRACT_V1",
            "path": ".cowork-flow/spec/entry-contract.md",
            "digest": [
                "Classify COWORK_DELEGATION_V1 and COWORK_DISPATCH_V1 before workflow recovery.",
                "UNKNOWN entries must not start, resume, archive, commit, or dispatch subagents.",
            ],
            "readWhen": ["before task start/resume/archive", "before subagent dispatch"],
        },
        {
            "id": "COWORK_DELEGATION_V1",
            "path": ".cowork-flow/spec/delegation-envelope.md",
            "digest": [
                "ACK must match dispatch_id and ack_token before EXECUTE.",
                "DELEGATED_SOFT entries are advisory and cannot complete Implement or Check.",
            ],
            "readWhen": ["before formal subagent dispatch", "when using a generic worker"],
        },
    ]
}


def _find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".cowork-flow").is_dir():
            return current
        if current == current.parent:
            return None
        current = current.parent


def _read_hook_input() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _hook_event_name(hook_input: dict[str, Any]) -> str:
    value = hook_input.get("hook_event_name") or hook_input.get("hookEventName")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "UserPromptSubmit"


def _normalize_hook_input(hook_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(hook_input)
    if "claude_session_id" not in normalized:
        session_id = normalized.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            normalized["claude_session_id"] = session_id
    return normalized


def _load_breadcrumbs(root: Path) -> dict[str, str]:
    workflow = root / ".cowork-flow" / "spec" / "workflow-state-templates.md"
    try:
        text = workflow.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {match.group(1): match.group(2).strip() for match in TAG_RE.finditer(text)}


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _load_contract_registry(root: Path) -> list[dict[str, Any]]:
    registry_file = root / ".cowork-flow" / "spec" / "registry.json"
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = DEFAULT_CONTRACT_REGISTRY
    contracts = data.get("contracts") if isinstance(data, dict) else None
    if not isinstance(contracts, list):
        contracts = DEFAULT_CONTRACT_REGISTRY["contracts"]
    return [contract for contract in contracts if isinstance(contract, dict)]


def _contract_fingerprint(root: Path, contracts: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(contracts, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for contract in contracts:
        path = contract.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        try:
            digest.update((root / path).read_bytes())
        except OSError:
            digest.update(f"missing:{path}".encode("utf-8"))
    return digest.hexdigest()[:16]


def _build_contract_digest(root: Path) -> str:
    contracts = _load_contract_registry(root)
    fingerprint = _contract_fingerprint(root, contracts)
    lines = [
        '<cowork-runtime host="claude-code" adapter="claude-code.hooks">',
        f'<contract-digest fingerprint="{fingerprint}">',
        "policy: repeat this short digest every hook; read full spec files only before listed actions.",
    ]
    for contract in contracts:
        contract_id = contract.get("id")
        path = contract.get("path")
        if not isinstance(contract_id, str) or not contract_id.strip():
            continue
        path_text = path if isinstance(path, str) and path.strip() else "<missing-path>"
        lines.append(f"- {contract_id}: {path_text}")
        for item in _as_string_list(contract.get("digest"))[:2]:
            lines.append(f"  digest: {item}")
        read_when = _as_string_list(contract.get("readWhen"))
        if read_when:
            lines.append(f"  read_before: {'; '.join(read_when)}")
    lines.extend(["</contract-digest>", "</cowork-runtime>"])
    return "\n".join(lines)


def _load_common(root: Path) -> None:
    scripts_dir = root / ".cowork-flow" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _get_active_task(root: Path, hook_input: dict[str, Any]) -> tuple[str | None, str, str]:
    _load_common(root)
    try:
        from common.active_task import get_active_task  # type: ignore[import-not-found]
    except Exception:
        return None, "no_task", "unavailable"

    active = get_active_task(root, hook_input)
    if not active.task_path:
        return None, "no_task", active.source

    task_dir = root / active.task_path
    task_json = task_dir / "task.json"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return active.task_path, "stale", active.source

    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        status = "unknown"
    return active.task_path, status.strip(), active.source


def _build_context(
    root: Path,
    task_path: str | None,
    status: str,
    source: str,
    breadcrumbs: dict[str, str],
) -> str:
    body = breadcrumbs.get(status) or "Refer to .cowork-flow/workflow.md for the current step."
    if task_path is None:
        header = f"Status: {status}\nSource: {source}"
    else:
        header = f"Task: {task_path}\nStatus: {status}\nSource: {source}"

    return "\n\n".join(
        [
            "<claude-code-runtime>\nhooks: UserPromptSubmit, SessionStart\n</claude-code-runtime>",
            _build_contract_digest(root),
            f"<workflow-state>\n{header}\n{body}\n</workflow-state>",
        ]
    )


def main() -> int:
    if os.environ.get("COWORK_FLOW_HOOKS") == "0" or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1":
        return 0

    hook_input = _normalize_hook_input(_read_hook_input())
    cwd_value = hook_input.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value.strip() else Path.cwd()
    root = _find_repo_root(cwd)
    if root is None:
        return 0

    event_name = _hook_event_name(hook_input)
    breadcrumbs = _load_breadcrumbs(root)
    _load_common(root)
    try:
        from common.entry_classifier import (  # type: ignore[import-not-found]
            classify_entry,
            should_use_delegated_bootstrap,
        )

        classification = classify_entry(hook_input)
    except Exception:
        classification = None

    if (
        event_name == "UserPromptSubmit"
        and classification is not None
        and should_use_delegated_bootstrap(classification.entry_kind)
        and classification.source != "empty_prompt"
    ):
        task_path = None
        status = "delegated_subtask"
        source = classification.source
    else:
        task_path, status, source = _get_active_task(root, hook_input)
    additional_context = _build_context(root, task_path, status, source, breadcrumbs)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": additional_context,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
