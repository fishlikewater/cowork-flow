#!/usr/bin/env python3
"""Emit cowork-flow workflow context for Codex UserPromptSubmit hooks."""

from __future__ import annotations

import json
import hashlib
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
                "Classify main-session requests before task start, resume, archive, or commit.",
                "Runtime context, not prompt labels, identifies formal subagent sessions.",
            ],
            "readWhen": ["before task start/resume/archive", "when prompt and bootstrap text conflict"],
        },
        {
            "id": "RUNTIME_CONTEXT_DISPATCH_V2",
            "path": ".cowork-flow/spec/subagent-dispatch.md",
            "digest": [
                "Formal subagent work is keyed by cowork_runtime_context_id.",
                "Explicit shim bind records bound_context_key before formal output is accepted.",
            ],
            "readWhen": ["before formal subagent dispatch", "when checking subagent health"],
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
        '<cowork-runtime host="codex" adapter="codex.spawn_agent">',
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


def _get_dispatch_mode(root: Path) -> str:
    _load_common(root)
    try:
        from common.config import get_codex_dispatch_mode  # type: ignore[import-not-found]
    except Exception:
        return "sub-agent"
    try:
        return get_codex_dispatch_mode(root)
    except Exception:
        return "sub-agent"


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


def _resolve_runtime_context(root: Path, hook_input: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    _load_common(root)
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
    if not context or context.get("scope") != "subagent" or context.get("status") == "closed":
        return None, runtime_context_id

    bound = bind_runtime_context(root, runtime_context_id, values=hook_input)
    return bound or context, runtime_context_id


def _subagent_runtime_lines(context: dict[str, Any]) -> list[str]:
    assignment = context.get("assignment") if isinstance(context.get("assignment"), dict) else {}
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


def _build_context(
    root: Path,
    task_path: str | None,
    status: str,
    source: str,
    breadcrumbs: dict[str, str],
    dispatch_mode: str,
    extra_lines: list[str] | None = None,
) -> str:
    body = breadcrumbs.get(status) or "Refer to .cowork-flow/workflow.md for the current step."
    if extra_lines:
        body = "\n".join([body, *extra_lines])
    if task_path is None:
        header = f"Status: {status}\nSource: {source}"
    else:
        header = f"Task: {task_path}\nStatus: {status}\nSource: {source}"

    return "\n\n".join(
        [
            f"<codex-dispatch-mode>{dispatch_mode}</codex-dispatch-mode>",
            (
                "<codex-runtime>\n"
                "dispatch_mode_meaning: workflow dispatch hint, not current thread role\n"
                "runtime_context_identity: formal subagent sessions bind before workflow-state injection\n"
                "</codex-runtime>"
            ),
            (
                _build_contract_digest(root)
            ),
            f"<workflow-state>\n{header}\n{body}\n</workflow-state>",
        ]
    )


def main() -> int:
    if os.environ.get("COWORK_FLOW_HOOKS") == "0" or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1":
        return 0

    hook_input = _read_hook_input()
    cwd_value = hook_input.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value.strip() else Path.cwd()
    root = _find_repo_root(cwd)
    if root is None:
        return 0

    breadcrumbs = _load_breadcrumbs(root)
    dispatch_mode = _get_dispatch_mode(root)
    runtime_context, runtime_context_id = _resolve_runtime_context(root, hook_input)
    extra_lines: list[str] | None = None
    if runtime_context is not None:
        task_dir = runtime_context.get("task_dir")
        task_path = task_dir.strip() if isinstance(task_dir, str) and task_dir.strip() else None
        status = "delegated_subtask"
        source = f"runtime-context:{runtime_context.get('runtime_context_id')}"
        extra_lines = _subagent_runtime_lines(runtime_context)
    elif runtime_context_id:
        task_path = None
        status = "delegated_subtask"
        source = f"runtime-context-invalid:{runtime_context_id}"
        extra_lines = [
            f"Runtime context: {runtime_context_id}",
            "Scope: subagent",
            "Runtime context is missing, closed, or invalid. Do not run start/resume/task start/archive/commit/spawn.",
        ]
    else:
        task_path, status, source = _get_active_task(root, hook_input)
    additional_context = _build_context(
        root,
        task_path,
        status,
        source,
        breadcrumbs,
        dispatch_mode,
        extra_lines,
    )

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": additional_context,
                }
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
