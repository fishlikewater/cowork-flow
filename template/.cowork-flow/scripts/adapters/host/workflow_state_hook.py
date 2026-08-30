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
    session_start: bool | None = None,
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
    if session_start is None:
        # No event signal from the host: treat the first injection as a
        # session start. Session state files appear once a task activation
        # exists (start), so their absence keeps every injection full.
        session_start = not _session_has_started(root, hook_input)
    if session_start:
        digest_block = _build_contract_digest(root, host, adapter)
    else:
        contracts, _warning = _load_contract_registry(root)
        digest_block = (
            f'<contract-fingerprint value="{contract_fingerprint(root, contracts)}"/>'
        )
    anchor_block = _decision_anchor_block(root, task_path, status)
    blocks = [*preamble, digest_block]
    if anchor_block:
        blocks.append(anchor_block)
    contract_block = _stage_contract_block(root, task_path, status)
    if contract_block:
        blocks.append(contract_block)
    blocks.append(
        f"<workflow-state{_workflow_state_attrs(task_path, status, source)}>"
        f"\n{body}\n</workflow-state>"
    )
    return "\n\n".join(blocks)


def _session_has_started(root: Path, hook_input: dict[str, Any]) -> bool:
    """True once the hook session holds a task activation state file.

    Resolving the context key and probing the session directory keeps this
    conservative: any resolution failure falls back to the full digest
    (reported as "not started").
    """
    try:
        from runtime.session_state import resolve_context_key, sessions_dir
    except Exception:
        return False
    try:
        context_key = resolve_context_key(hook_input)
    except Exception:
        return False
    if not context_key:
        return False
    return (sessions_dir(root) / f"{context_key}.json").exists()


def _xml_attr(value: Any) -> str:
    # Delegates to the fact-view implementation: the escaping rules must stay
    # identical across the decision-anchor and stage-contract blocks.
    from services.fact_view import xml_attr

    return xml_attr(value)


def _workflow_state_attrs(
    task_path: str | None, status: str, source: str
) -> str:
    """Structured fact header (context-injection.md, stage 1): the machine
    picks task/status/source off the attributes; humans read the body."""
    attrs = [f'status="{_xml_attr(status)}"', f'source="{_xml_attr(source)}"']
    if task_path:
        attrs.insert(0, f'task="{_xml_attr(task_path)}"')
    return "".join(f" {attr}" for attr in attrs)


DECISION_ANCHOR_STATES = ("planning", "in_progress", "review")
STAGE_CONTRACT_STATES = ("in_progress", "review")


def _effective_task_status(
    root: Path, task_path: str, status: str
) -> str | None:
    """Delegated subtasks read the underlying task's status; every other
    status is already effective."""
    if status != "delegated_subtask":
        return status
    try:
        data = json.loads(
            (root / task_path / "task.json").read_text(encoding="utf-8")
        )
        effective_status = data.get("status")
    except (OSError, json.JSONDecodeError):
        return None
    return effective_status if isinstance(effective_status, str) else None


def _decision_anchor_block(
    root: Path, task_path: str | None, status: str
) -> str | None:
    """Compact decision facts (why this task, what done means, what was
    rejected) for states where they steer execution. Delegated subtasks read
    the underlying task's status. Absent anchor file or terminal states
    inject nothing."""
    if not task_path:
        return None
    effective_status = _effective_task_status(root, task_path, status)
    if effective_status not in DECISION_ANCHOR_STATES:
        return None
    try:
        from services.fact_view import parse_decision_anchor

        text = (root / task_path / "decision-anchor.md").read_text(
            encoding="utf-8"
        )
        parsed = parse_decision_anchor(text)
    except (OSError, UnicodeDecodeError):
        # Absent or undecodable anchors are routine: no block, no noise.
        return None
    except Exception as error:
        # Anything else leaves a trace so silent guard loss stays diagnosable
        # (stdout is the injection channel, stderr is safe).
        sys.stderr.write(f"decision-anchor degraded: {error}\n")
        return None
    if not parsed["goal"] and not parsed["acceptanceCriteria"]:
        return None
    lines = [f'<decision-anchor task="{_xml_attr(task_path)}">']
    if parsed["goal"]:
        lines.append(f"Goal: {parsed['goal'].splitlines()[0][:160]}")
    if parsed["acceptanceCriteria"]:
        items = "; ".join(
            f"{item['id']} {item['text'][:80]}"
            for item in parsed["acceptanceCriteria"][:8]
        )
        lines.append(f"Acceptance: {items}")
    if parsed["rejectedOptions"]:
        lines.append("Rejected: " + "; ".join(parsed["rejectedOptions"][:6]))
    lines.append("</decision-anchor>")
    return "\n".join(lines)


def _stage_contract_block(
    root: Path, task_path: str | None, status: str
) -> str | None:
    """Implementation contract (edit scope, specs to read, gates preview,
    declared verification commands) for states where it steers execution.
    Data comes from the frozen task artifacts via services.fact_view — the
    single source shared with the MCP task_scope tool. Delegated subtasks
    render the parent scope as a read-only reference."""
    if not task_path:
        return None
    effective_status = _effective_task_status(root, task_path, status)
    if effective_status not in STAGE_CONTRACT_STATES:
        return None
    try:
        from services.fact_view import (
            build_stage_contract,
            file_scope_whitelist,
            parse_decision_anchor,
            spec_pointer_files,
        )

        task_dir = root / task_path
        whitelist = file_scope_whitelist(root, task_dir)
        spec_files = spec_pointer_files(task_dir)
        anchor_path = task_dir / "decision-anchor.md"
        try:
            parsed = parse_decision_anchor(
                anchor_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError):
            # Absent or undecodable anchor: scope/gates still render; the
            # verify line is dropped by the empty results.
            parsed = {"validationCommands": []}
        except Exception as error:
            # Never silently kill the guard block: leave a degradation trace
            # on stderr (stdout is the injection channel).
            sys.stderr.write(f"stage-contract degraded: {error}\n")
            return None
        return build_stage_contract(
            task_path,
            whitelist,
            spec_files,
            parsed,
            mutable=status != "delegated_subtask",
        )
    except Exception as error:
        sys.stderr.write(f"stage-contract degraded: {error}\n")
        return None


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


def contract_fingerprint(root: Path, contracts: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            contracts,
            ensure_ascii=False,
            sort_keys=True,
            # Compact separators keep the bytes identical to the JS
            # stableStringify implementations (see context-injection.md).
            separators=(",", ":"),
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
    return digest.hexdigest()[:16]


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
    fingerprint = contract_fingerprint(root, contracts)
    lines = [
        f'<cowork-runtime host="{host}" adapter="{adapter}">',
        f'<contract-digest fingerprint="{fingerprint}">',
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
    # No "Scope: subagent" line here: the stage-contract block owns the scope
    # declaration and renders the parent task's scope as a read-only reference
    # for delegated sessions (build_stage_contract(mutable=False)).
    lines = [
        f"Runtime context: {context.get('runtime_context_id')}",
        f"Agent: {context.get('agent_type') or 'unknown'}",
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
