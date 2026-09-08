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
        {
            "id": "FACT_LAYER_ACCESS_V1",
            "path": ".cowork-flow/spec/contracts/fact-layer-access.md",
            "digest": [
                "Task/scope/spec facts are read-only via MCP tools or CLI; writes only flow through CLI lifecycle gates.",
                "Prefer MCP task_state/task_scope/task_specs for fact queries when available; CLI is the fallback.",
            ],
            "readWhen": [
                "when querying task facts or file scope",
                "when registering the fact layer for a new host or external client",
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


# Digest policy line wording is a per-host contract fact (context-injection.md
# transport table): the zcode line says "repeat fingerprint", the opencode
# plugin line says "every plugin transform", and zcode additionally drops the
# registry-warning line.
DIGEST_POLICY_BY_HOST = {
    "zcode": (
        "policy: repeat fingerprint every hook; "
        "read full spec files only before listed actions."
    ),
    "opencode": (
        "policy: repeat this short digest every plugin transform; "
        "read full spec files only before listed actions."
    ),
}
DIGEST_POLICY_DEFAULT = (
    "policy: repeat this short digest every hook; "
    "read full spec files only before listed actions."
)
DIGEST_WARNING_SILENT_HOSTS = frozenset({"zcode"})


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
        task_path, status, source = _get_active_task_with_fallback(
            root, hook_input, host
        )

    if status == "stale" and task_path:
        # Unified missing-task semantics (previously zcode JS-only): a bound
        # task whose directory or task.json vanished renders the no_task
        # family message instead of a generic fallback breadcrumb.
        status = "no_task"
        body = MISSING_TASK_BODY.format(task_path=task_path)
    else:
        body = (
            breadcrumbs.get(status)
            or "Run ./.cowork-flow/run task next --json for the current workflow route."
        )
    if host == "zcode":
        body += _rebind_hints(root)
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
    context = "\n\n".join(blocks)
    if host == "zcode":
        # Port of the zcode essential-files check: appended after the whole
        # context so a broken install is visible without a second hook pass.
        context += _essential_files_warning(root)
    return context


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
        from services.context_paths import load_scope_rules
        from services.fact_view import (
            build_stage_contract,
            file_scope_whitelist,
            parse_decision_anchor,
            spec_digest_items,
            spec_pointer_files,
        )

        task_dir = root / task_path
        whitelist = file_scope_whitelist(root, task_dir)
        spec_files = spec_pointer_files(task_dir)
        digests = spec_digest_items(root, spec_files) if spec_files else {}
        rules = load_scope_rules(root)
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
            rules=rules,
            digests=digests,
        )
    except Exception as error:
        sys.stderr.write(f"stage-contract degraded: {error}\n")
        return None


def spec_edit_warning(root: Path, hook_input: dict[str, Any]) -> str:
    """Editor-phase spec-check single-line warning (PostToolUse short path).

    Silence rules match the zcode JS mirror (editScopeWarning family): only
    an active in_progress/review main-session task gets advisories —
    no_task, planning, completed, and delegated sessions stay silent. Empty
    string means silent. Never raises — the editor path must not break
    edits.
    """
    try:
        task_path, status, _source = _get_active_task(root, hook_input)
    except Exception:
        return ""
    if not task_path or status not in STAGE_CONTRACT_STATES:
        return ""
    if _session_scope(root, hook_input) == "subagent":
        return ""
    tool_input = hook_input.get("tool_input")
    file_path = (
        tool_input.get("file_path") if isinstance(tool_input, dict) else None
    )
    if not isinstance(file_path, str) or not file_path.strip():
        return ""
    try:
        from services.spec_check import run_edit_checks

        return run_edit_checks(root, file_path)
    except Exception:
        return ""


def edit_scope_warning(root: Path, hook_input: dict[str, Any]) -> str:
    """Per-edit out-of-scope warning (zcode-only capability). Port of the
    zcode hook's editScopeWarning: at most one line when the edited file is
    outside the task's file-scope whitelist. Silence rules match the JS
    source, including the newest-session display fallback for sessions with
    no resolvable identity. Never raises."""
    try:
        task_path, status, _source = _get_active_task_with_fallback(
            root, hook_input, "zcode"
        )
    except Exception:
        return ""
    if not task_path or status not in STAGE_CONTRACT_STATES:
        return ""
    if _session_scope(root, hook_input) == "subagent":
        return ""
    tool_input = hook_input.get("tool_input")
    file_path = (
        tool_input.get("file_path") if isinstance(tool_input, dict) else None
    )
    if not isinstance(file_path, str) or not file_path.strip():
        return ""
    try:
        from services.fact_view import file_scope_whitelist, path_in_scope

        whitelist = file_scope_whitelist(root, root / task_path)
        if path_in_scope(whitelist, file_path).get("inScope"):
            return ""
    except Exception:
        return ""
    normalized = file_path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return (
        f"⚠️ {normalized} is outside the task's declared scope. "
        "If intended, add it with `task context add` (agent-mutable) "
        "or revert the edit."
    )


def merged_edit_warning(root: Path, hook_input: dict[str, Any]) -> str:
    """zcode PostToolUse Edit/Write/MultiEdit context: the scope warning and
    the spec-check warning merged into one additionalContext payload, at
    most one line each, joined by a newline (port of the zcode hook's
    mergedEditWarning)."""
    scope_line = edit_scope_warning(root, hook_input)
    spec_line = spec_edit_warning(root, hook_input)
    if scope_line and spec_line:
        return f"{scope_line}\n{spec_line}"
    return scope_line or spec_line


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
        DIGEST_POLICY_BY_HOST.get(host, DIGEST_POLICY_DEFAULT),
    ]
    if warning and host not in DIGEST_WARNING_SILENT_HOSTS:
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


MISSING_TASK_BODY = (
    "Session 指向的任务目录不存在（{task_path}）。\n"
    "当前项目无有效任务。请运行 ./.cowork-flow/run task next --run "
    '--title "<title>" --slug <task-name> --assignee <name> 创建新任务。'
)

# Port of the zcode hook's essential-files check (inject-context.js
# checkEssentialFiles): appended to the zcode context when any guard file of
# the workflow install is missing.
ESSENTIAL_FILES = (
    "AGENTS.md",
    ".cowork-flow/config.yaml",
    ".cowork-flow/run",
    ".cowork-flow/spec/runtime/contract-registry.json",
    ".cowork-flow/spec/contracts/workflow-state-templates.md",
)


def _get_active_task_with_fallback(
    root: Path,
    hook_input: dict[str, Any],
    host: str,
) -> tuple[str | None, str, str]:
    """zcode parity: when no session identity resolves at all, the zcode hook
    displayed the newest valid main session's binding. Display-only — the CLI
    lifecycle commands keep their strict identity semantics."""
    task_path, status, source = _get_active_task(root, hook_input)
    if host != "zcode" or task_path or source != "missing-context":
        return task_path, status, source
    fallback = _newest_session_task(root)
    if fallback is None:
        return task_path, status, source
    task_json = root / fallback / "task.json"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback, "stale", "session-fallback"
    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        status = "unknown"
    return fallback, status.strip(), "session-fallback"


def _newest_session_task(root: Path) -> str | None:
    try:
        from runtime.session_state import sessions_dir
    except Exception:
        return None
    sessions = sessions_dir(root)
    if not sessions.is_dir():
        return None
    entries: list[tuple[str, str]] = []
    try:
        paths = sorted(sessions.glob("*.json"))
    except OSError:
        return None
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        task_path = data.get("active_task_path")
        if not isinstance(task_path, str) or not task_path.strip():
            continue
        if data.get("scope") == "subagent":
            continue
        entries.append(
            (str(data.get("last_seen_at") or ""), task_path.strip())
        )
    entries.sort(reverse=True)
    for _seen_at, task_path in entries:
        task_dir = root / task_path
        if task_dir.is_dir() and (task_dir / "task.json").is_file():
            return task_path
    return None


def _rebind_hints(root: Path) -> str:
    """Port of the zcode hook's formatRebindHints: one-level task scan for
    bindable (non-completed) tasks, appended to no_task/missing bodies."""
    tasks_dir = root / ".cowork-flow" / "tasks"
    try:
        children = sorted(tasks_dir.iterdir())
    except OSError:
        return ""
    entries: list[str] = []
    for child in children:
        if not child.is_dir():
            continue
        relative = f".cowork-flow/tasks/{child.name}"
        task_json = child / "task.json"
        if not task_json.is_file():
            continue
        try:
            data = json.loads(task_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            status = "unknown"
        else:
            status = str(data.get("status") or "unknown").strip() or "unknown"
        if status == "completed":
            continue
        entries.append(f"- {relative} ({status})")
    if not entries:
        return ""
    return (
        "\n活动任务（可用 ./.cowork-flow/run task next <dir> 改绑）：\n"
        + "\n".join(entries)
    )


def _essential_files_warning(root: Path) -> str:
    missing = [rel for rel in ESSENTIAL_FILES if not (root / rel).exists()]
    if not missing:
        return ""
    return (
        "\n\n⚠️ 缺少必要文件："
        + ", ".join(missing)
        + "。\n请立即创建这些文件以保障工作流正常运行。"
    )


def _session_scope(root: Path, hook_input: dict[str, Any]) -> str:
    try:
        from runtime.session_state import resolve_context_key, sessions_dir
    except Exception:
        return ""
    context_key = resolve_context_key(hook_input)
    if not context_key:
        return ""
    try:
        data = json.loads(
            (sessions_dir(root) / f"{context_key}.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError, ValueError):
        return ""
    scope = data.get("scope")
    return scope if isinstance(scope, str) else ""


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
    result = bound or context
    if not result.get("runtime_context_id"):
        # Legacy context files predate the id field; the detected id is the
        # identity that opened this context, so display it.
        result = {**result, "runtime_context_id": runtime_context_id}
    return result, runtime_context_id


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
