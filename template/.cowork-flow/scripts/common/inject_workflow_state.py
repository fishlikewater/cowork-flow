#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared hook logic for injecting cowork-flow workflow state.

Used by host-specific hooks (.claude/hooks/, .codex/hooks/) that only differ in
their host-specific preamble blocks and host adapter identifiers.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

TAG_RE = re.compile(
    r"\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*\[/workflow-state:\1\]",
    re.DOTALL,
)
TASK_DATE_PREFIX_RE = re.compile(r"^\d{2}-\d{2}-")

DEFAULT_CONTRACT_REGISTRY: dict[str, Any] = {
    "contracts": [
        {
            "id": "COWORK_ENTRY_CONTRACT_V2",
            "path": ".cowork-flow/spec/entry-contract.md",
            "digest": [
                "Dual-channel classification: structured signals from adapter.yaml entrySignals priority, legacy text fallback during transition, fail-closed when both absent.",
                "Runtime context, not prompt labels, identifies formal subagent sessions.",
            ],
            "readWhen": [
                "before task start/resume/archive",
                "when prompt and bootstrap text conflict",
            ],
        },
        {
            "id": "RUNTIME_CONTEXT_DISPATCH_V2",
            "path": ".cowork-flow/spec/subagent-dispatch.md",
            "digest": [
                "Formal subagent work is keyed by cowork_runtime_context_id.",
                "Explicit shim bind records bound_context_key before formal output is accepted.",
            ],
            "readWhen": [
                "before formal subagent dispatch",
                "when checking subagent health",
            ],
        },
    ]
}


def find_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".cowork-flow").is_dir():
            return current
        if current == current.parent:
            return None
        current = current.parent


def read_hook_input() -> dict[str, Any]:
    try:
        raw = sys.stdin.buffer.read()
    except AttributeError:
        text = sys.stdin.read()
    else:
        if not raw.strip():
            return {}
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            encoding = getattr(sys.stdin, "encoding", None) or "utf-8"
            text = raw.decode(encoding, errors="replace")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_breadcrumbs(root: Path) -> dict[str, str]:
    workflow = root / ".cowork-flow" / "spec" / "workflow-state-templates.md"
    try:
        text = workflow.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {match.group(1): match.group(2).strip() for match in TAG_RE.finditer(text)}


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def load_contract_registry(root: Path) -> list[dict[str, Any]]:
    registry_file = root / ".cowork-flow" / "spec" / "registry.json"
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = DEFAULT_CONTRACT_REGISTRY
    contracts = data.get("contracts") if isinstance(data, dict) else None
    if not isinstance(contracts, list):
        contracts = DEFAULT_CONTRACT_REGISTRY["contracts"]
    return [contract for contract in contracts if isinstance(contract, dict)]


def contract_fingerprint(root: Path, contracts: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps(contracts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    for contract in contracts:
        path = contract.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        try:
            digest.update((root / path).read_bytes())
        except OSError:
            digest.update(f"missing:{path}".encode("utf-8"))
    return digest.hexdigest()[:16]


def build_contract_digest(root: Path, host: str, adapter: str) -> str:
    contracts = load_contract_registry(root)
    fingerprint = contract_fingerprint(root, contracts)
    lines = [
        f'<cowork-runtime host="{host}" adapter="{adapter}">',
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
        for item in as_string_list(contract.get("digest"))[:2]:
            lines.append(f"  digest: {item}")
        read_when = as_string_list(contract.get("readWhen"))
        if read_when:
            lines.append(f"  read_before: {'; '.join(read_when)}")
    lines.extend(["</contract-digest>", "</cowork-runtime>"])
    return "\n".join(lines)


def load_common(root: Path) -> None:
    scripts_dir = root / ".cowork-flow" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _flow_task_status(root: Path, task_path: str) -> str | None:
    load_common(root)
    try:
        from common.paths import get_db_path  # type: ignore[import-not-found]
        from flow.store import FlowStore  # type: ignore[import-not-found]
    except Exception:
        return None

    db_path = get_db_path(root)
    if not db_path.exists():
        return None

    artifact_dir = Path(task_path).name
    task_id = TASK_DATE_PREFIX_RE.sub("", artifact_dir)
    try:
        with FlowStore(str(db_path)) as store:
            task = store.get_task_by_artifact_dir(artifact_dir)
            if task is None and task_id:
                task = store.get_task(task_id)
            if task is None:
                return None
            return task.status
    except Exception:
        return None


def get_active_task(
    root: Path, hook_input: dict[str, Any]
) -> tuple[str | None, str, str]:
    load_common(root)
    try:
        from common.active_task import get_active_task as _get_active_task  # type: ignore[import-not-found]
    except Exception:
        return None, "no_task", "unavailable"

    active = _get_active_task(root, hook_input)
    if not active.task_path:
        return None, "no_task", active.source

    flow_status = _flow_task_status(root, active.task_path)
    if flow_status:
        return active.task_path, flow_status, active.source

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


def resolve_runtime_context(
    root: Path, hook_input: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    load_common(root)
    try:
        from common.active_task import (  # type: ignore[import-not-found]
            bind_runtime_context,
            read_runtime_context,
            resolve_runtime_context_id,
        )
    except Exception:
        return None, None

    runtime_context_id = resolve_runtime_context_id(hook_input)
    if not runtime_context_id:
        return None, None

    context = read_runtime_context(root, runtime_context_id)
    if (
        not context
        or context.get("scope") != "subagent"
        or context.get("status") == "closed"
    ):
        return None, runtime_context_id

    bound = bind_runtime_context(root, runtime_context_id, values=hook_input)
    return bound or context, runtime_context_id


def subagent_runtime_lines(context: dict[str, Any]) -> list[str]:
    assignment = (
        context.get("assignment") if isinstance(context.get("assignment"), dict) else {}
    )
    lines = [
        f"Runtime context: {context.get('runtime_context_id')}",
        f"Agent: {context.get('agent_type') or 'unknown'}",
        "Scope: subagent",
        "Do not run start/resume/task start/archive/commit/spawn.",
    ]
    goal = assignment.get("goal") if isinstance(assignment, dict) else None
    if isinstance(goal, str) and goal.strip():
        lines.append(f"Goal: {goal.strip()}")
    return lines


def build_context(
    root: Path,
    task_path: str | None,
    status: str,
    source: str,
    breadcrumbs: dict[str, str],
    build_host_block: Callable[[], str],
    extra_lines: list[str] | None = None,
) -> str:
    body = (
        breadcrumbs.get(status)
        or "Refer to .cowork-flow/workflow.md for the current step."
    )
    if extra_lines:
        body = "\n".join([body, *extra_lines])
    if task_path is None:
        header = f"Status: {status}\nSource: {source}"
    else:
        header = f"Task: {task_path}\nStatus: {status}\nSource: {source}"

    return "\n\n".join(
        [
            build_host_block(),
            f"<workflow-state>\n{header}\n{body}\n</workflow-state>",
        ]
    )


def should_skip() -> bool:
    return (
        os.environ.get("COWORK_FLOW_HOOKS") == "0"
        or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1"
    )


def emit_hook_output(event_name: str, additional_context: str) -> int:
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
