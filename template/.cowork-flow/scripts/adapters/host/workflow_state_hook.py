#!/usr/bin/env python3
"""Shared workflow-state protocol used by host hook adapters."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


TAG_RE = re.compile(
    r"\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*"
    r"\[/workflow-state:\1\]",
    re.DOTALL,
)
DEFAULT_CONTRACT_REGISTRY = {
    "contracts": [
        {
            "id": "RUNTIME_CONTEXT_DISPATCH_V2",
            "path": ".cowork-flow/spec/contracts/subagent-dispatch.md",
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


def codex_dispatch_mode(root: Path) -> str:
    _load_common(root)
    try:
        from infra.config import get_codex_dispatch_mode
    except Exception:
        return "sub-agent"
    try:
        return get_codex_dispatch_mode(root)
    except Exception:
        return "sub-agent"


def build_hook_context(
    root: Path,
    hook_input: dict[str, Any],
    *,
    host: str,
    adapter: str,
    preamble: tuple[str, ...],
) -> str:
    breadcrumbs = _load_breadcrumbs(root)
    runtime_context, runtime_context_id = _resolve_runtime_context(
        root,
        hook_input,
    )
    extra_lines: list[str] | None = None
    if runtime_context is not None:
        task_dir = runtime_context.get("task_dir")
        task_path = (
            task_dir.strip()
            if isinstance(task_dir, str) and task_dir.strip()
            else None
        )
        status = "delegated_subtask"
        source = (
            f"runtime-context:{runtime_context.get('runtime_context_id')}"
        )
        extra_lines = _subagent_runtime_lines(runtime_context)
    elif runtime_context_id:
        task_path = None
        status = "delegated_subtask"
        source = f"runtime-context-invalid:{runtime_context_id}"
        extra_lines = [
            f"Runtime context: {runtime_context_id}",
            "Scope: subagent",
            (
                "Runtime context is missing, closed, or invalid. "
                "Do not run standalone lifecycle commands, resume, archive, commit, or spawn."
            ),
        ]
    else:
        task_path, status, source = _get_active_task(root, hook_input)

    body = (
        breadcrumbs.get(status)
        or "Run ./.cowork-flow/run task next --json for the current workflow route."
    )
    if extra_lines:
        body = "\n".join([body, *extra_lines])
    if task_path is None:
        header = f"Status: {status}\nSource: {source}"
    else:
        header = f"Task: {task_path}\nStatus: {status}\nSource: {source}"
    return "\n\n".join(
        [
            *preamble,
            _build_contract_digest(root, host, adapter),
            f"<workflow-state>\n{header}\n{body}\n</workflow-state>",
        ]
    )


def _load_breadcrumbs(root: Path) -> dict[str, str]:
    path = (
        root
        / ".cowork-flow"
        / "spec"
        / "contracts"
        / "workflow-state-templates.md"
    )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {
        match.group(1): match.group(2).strip()
        for match in TAG_RE.finditer(text)
    }


def _load_contract_registry(
    root: Path,
) -> tuple[list[dict[str, Any]], str | None]:
    path = (
        root
        / ".cowork-flow"
        / "spec"
        / "runtime"
        / "contract-registry.json"
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        data = DEFAULT_CONTRACT_REGISTRY
        warning = f"contract registry unavailable at {path}; using fallback digest"
    except json.JSONDecodeError:
        data = DEFAULT_CONTRACT_REGISTRY
        warning = f"contract registry invalid at {path}; using fallback digest"
    else:
        warning = None
    contracts = data.get("contracts") if isinstance(data, dict) else None
    if not isinstance(contracts, list):
        contracts = DEFAULT_CONTRACT_REGISTRY["contracts"]
        warning = warning or (
            f"contract registry has no contracts array at {path}; "
            "using fallback digest"
        )
    return [
        contract for contract in contracts if isinstance(contract, dict)
    ], warning


def _build_contract_digest(
    root: Path,
    host: str,
    adapter: str,
) -> str:
    contracts, warning = _load_contract_registry(root)
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            contracts,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    )
    for contract in contracts:
        path = contract.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        try:
            digest.update((root / path).read_bytes())
        except OSError:
            digest.update(f"missing:{path}".encode("utf-8"))
    lines = [
        f'<cowork-runtime host="{host}" adapter="{adapter}">',
        f'<contract-digest fingerprint="{digest.hexdigest()[:16]}">',
        (
            "policy: repeat this short digest every hook; "
            "read full spec files only before listed actions."
        ),
    ]
    if warning:
        lines.append(f"warning: {warning}")
    for contract in contracts:
        contract_id = contract.get("id")
        path = contract.get("path")
        if not isinstance(contract_id, str) or not contract_id.strip():
            continue
        path_text = (
            path if isinstance(path, str) and path.strip() else "<missing-path>"
        )
        lines.append(f"- {contract_id}: {path_text}")
        for item in _string_list(contract.get("digest"))[:2]:
            lines.append(f"  digest: {item}")
        read_when = _string_list(contract.get("readWhen"))
        if read_when:
            lines.append(f"  read_before: {'; '.join(read_when)}")
    lines.extend(["</contract-digest>", "</cowork-runtime>"])
    return "\n".join(lines)


def _get_active_task(
    root: Path,
    hook_input: dict[str, Any],
) -> tuple[str | None, str, str]:
    _load_common(root)
    try:
        from runtime.session_state import get_active_task
    except Exception:
        return None, "no_task", "unavailable"
    active = get_active_task(root, hook_input)
    if not active.task_path:
        return None, "no_task", active.source
    task_json = root / active.task_path / "task.json"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return active.task_path, "stale", active.source
    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        status = "unknown"
    return active.task_path, status.strip(), active.source


def _resolve_runtime_context(
    root: Path,
    hook_input: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    _load_common(root)
    try:
        from runtime.session_state import resolve_runtime_context_id
        from services.workflow_runtime import (
            bind_runtime_context,
            read_runtime_context,
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
    bound = bind_runtime_context(
        root,
        runtime_context_id,
        values=hook_input,
    )
    return bound or context, runtime_context_id


def _subagent_runtime_lines(context: dict[str, Any]) -> list[str]:
    assignment = (
        context.get("assignment")
        if isinstance(context.get("assignment"), dict)
        else {}
    )
    lines = [
        f"Runtime context: {context.get('runtime_context_id')}",
        f"Agent: {context.get('agent_type') or 'unknown'}",
        "Scope: subagent",
        "Do not run standalone lifecycle commands, resume, archive, commit, or spawn.",
    ]
    goal = assignment.get("goal")
    if isinstance(goal, str) and goal.strip():
        lines.append(f"Goal: {goal.strip()}")
    return lines


def _load_common(root: Path) -> None:
    scripts_dir = root / ".cowork-flow" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item for item in value
        if isinstance(item, str) and item.strip()
    ]
