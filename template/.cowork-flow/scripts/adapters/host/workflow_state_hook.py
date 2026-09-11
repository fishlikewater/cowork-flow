#!/usr/bin/env python3
"""Shared workflow-state protocol used by host hook adapters.

This module is host-neutral: it renders the workflow facts and consumes a
HostPolicy object for the per-host deltas (digest wording, preamble,
edit warnings, unbound-session fallback). Host behaviors live in the
per-host policy modules beside this file (zcode_policy.py,
claude_code_policy.py, codex_policy.py); hosts without a module (dsh) run
on default_policy().
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


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


# Digest policy wording is a per-host contract fact (context-injection.md
# transport table); hosts carry their line in their policy module, unknown
# hosts fall back to the default line below.
DEFAULT_DIGEST_POLICY = (
    "policy: repeat this short digest every hook; "
    "read full spec files only before listed actions."
)


class HostPolicy:
    """Per-host deltas consumed by the neutral renderer.

    Fields left at their defaults mean "no such behavior for this host" —
    the renderer checks callables instead of branching on host names.
    Plain class on purpose: this file is also loaded standalone by tests
    under ad-hoc module names, where @dataclass processing crashes on the
    unregistered module lookup.
    """

    __slots__ = (
        "host",
        "digest_policy",
        "digest_warning_silent",
        "session_start_event",
        "session_alias",
        "preamble",
        "rebind_hints",
        "essential_files_warning",
        "fallback_for_unbound",
        "post_tool_use",
        "emit_indent",
        "emit_not_initialized",
    )

    def __init__(
        self,
        host: str,
        digest_policy: str = DEFAULT_DIGEST_POLICY,
        digest_warning_silent: bool = False,
        session_start_event: str | None = "SessionStart",
        session_alias: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        preamble: Callable[[Path], tuple[str, ...]] | None = None,
        rebind_hints: Callable[[Path], str] | None = None,
        essential_files_warning: Callable[[Path], str] | None = None,
        fallback_for_unbound: bool = False,
        post_tool_use: Callable[[Path, dict[str, Any]], tuple[str, int]] | None = None,
        emit_indent: bool = False,
        emit_not_initialized: bool = False,
    ) -> None:
        self.host = host
        self.digest_policy = digest_policy
        self.digest_warning_silent = digest_warning_silent
        self.session_start_event = session_start_event
        self.session_alias = session_alias
        self.preamble = preamble
        self.rebind_hints = rebind_hints
        self.essential_files_warning = essential_files_warning
        self.fallback_for_unbound = fallback_for_unbound
        self.post_tool_use = post_tool_use
        self.emit_indent = emit_indent
        self.emit_not_initialized = emit_not_initialized


def default_policy(host: str = "generic") -> HostPolicy:
    return HostPolicy(host=host)


# Host → policy module dispatch. Data-driven: adding a host is one row plus
# its policy module; the neutral renderer never branches on host names.
_HOST_POLICY_MODULES = {
    "zcode": "adapters.host.zcode_policy",
    "claude-code": "adapters.host.claude_code_policy",
    "codex": "adapters.host.codex_policy",
}


def resolve_policy(host: str, policy: HostPolicy | None = None) -> HostPolicy:
    if policy is not None:
        return policy
    module_name = _HOST_POLICY_MODULES.get(host)
    if not module_name:
        return default_policy(host)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        # A broken host policy module degrades to the neutral default
        # instead of killing the injection.
        return default_policy(host)
    policy = module.POLICY
    return policy if isinstance(policy, HostPolicy) else default_policy(host)


def build_hook_context(
    root: Path,
    hook_input: dict[str, Any],
    *,
    host: str,
    adapter: str,
    preamble: tuple[str, ...],
    session_start: bool | None = None,
    policy: HostPolicy | None = None,
) -> str:
    policy = resolve_policy(host, policy)
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
            root,
            hook_input,
            policy.fallback_for_unbound,
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
    if policy.rebind_hints is not None:
        body += policy.rebind_hints(root)
    if extra_lines:
        body = "\n".join([body, *extra_lines])
    if session_start is None:
        # No event signal from the host: treat the first injection as a
        # session start. Session state files appear once a task activation
        # exists (start), so their absence keeps every injection full.
        session_start = not _session_has_started(root, hook_input)
    if session_start:
        digest_block = _build_contract_digest(root, policy, adapter)
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
        f"<workflow-state{_workflow_state_attrs(task_path, status, source, session=_resolve_session_identity(root, hook_input))}>"
        f"\n{body}\n</workflow-state>"
    )
    context = "\n\n".join(blocks)
    if policy.essential_files_warning is not None:
        # Appended after the whole context so a broken install is visible
        # without a second hook pass (host policy decides whether the check
        # exists at all).
        context += policy.essential_files_warning(root)
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


def _resolve_session_identity(
    root: Path, hook_input: dict[str, Any]
) -> str | None:
    """The caller's resolved context key for the session attribute
    (context-injection.md, stage 1). None when no identity is resolvable —
    the attribute is omitted rather than guessed."""
    _load_common(root)
    try:
        from runtime.session_state import resolve_context_key
    except Exception:
        return None
    try:
        return resolve_context_key(hook_input)
    except Exception:
        return None


def _workflow_state_attrs(
    task_path: str | None,
    status: str,
    source: str,
    session: str | None = None,
) -> str:
    """Structured fact header (context-injection.md, stage 1): the machine
    picks task/status/source/session off the attributes; humans read the
    body. session is appended last and only when a session identity was
    resolvable from the hook input or environment."""
    attrs = [f'status="{_xml_attr(status)}"', f'source="{_xml_attr(source)}"']
    if task_path:
        attrs.insert(0, f'task="{_xml_attr(task_path)}"')
    if session:
        attrs.append(f'session="{_xml_attr(session)}"')
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


def spec_edit_warning(
    root: Path,
    hook_input: dict[str, Any],
    policy: HostPolicy,
) -> str:
    """Editor-phase spec-check single-line warning (PostToolUse short path).

    Delegated subagents are the primary coders, so spec violations must
    reach them too: only an active in_progress/review task is required —
    session scope is not consulted here (scope warnings stay main-only in
    the zcode policy's edit_scope_warning). Hosts with
    fallback_for_unbound (zcode) follow another main session's binding for
    their never-bound hook sessions only while exactly one main-session
    binding exists (see _get_active_task_with_fallback); strict-identity
    hosts (claude-code/codex) require the calling session's own binding.
    no_task, planning, and completed stay silent. Empty string means
    silent. Never raises — the editor path must not break edits.
    """
    try:
        task_path, status, _source = _get_active_task_with_fallback(
            root, hook_input, policy.fallback_for_unbound
        )
    except Exception:
        return ""
    if not task_path or status not in STAGE_CONTRACT_STATES:
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


def spec_only_post_tool_use(
    root: Path,
    hook_input: dict[str, Any],
    policy: HostPolicy,
) -> tuple[str, int]:
    """claude-code / codex PostToolUse transport: spec-check advisory on
    stderr only (exit 2 surfaces it to the model); the edit itself has
    already happened. No additionalContext payload."""
    warning = spec_edit_warning(root, hook_input, policy)
    if warning:
        print(warning, file=sys.stderr)
        return "", 2
    return "", 0


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
    policy: HostPolicy,
    adapter: str,
) -> str:
    contracts, warning = _load_contract_registry(root)
    fingerprint = contract_fingerprint(root, contracts)
    lines = [
        f'<cowork-runtime host="{policy.host}" adapter="{adapter}">',
        f'<contract-digest fingerprint="{fingerprint}">',
        policy.digest_policy,
    ]
    if warning and not policy.digest_warning_silent:
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


def _get_active_task_with_fallback(
    root: Path,
    hook_input: dict[str, Any],
    fallback_for_unbound: bool,
) -> tuple[str | None, str, str]:
    """zcode parity: a hook session that carries no binding follows another
    main session's binding — but only when exactly one main-session binding
    exists. Two sources qualify for the fallback: no session identity at all
    (missing-context), and a session id that resolves but was never bound
    (empty-session) — the zcode hook always carries the conversation's own
    session id, while task activation happens in the Bash CLI under a
    separate explicit identity, so the hook session file may not exist yet.
    Gated by the host policy's fallback_for_unbound flag; display/warning-only
    — the CLI lifecycle commands keep their strict identity semantics. With
    two or more main-session bindings the newest one belongs to some other
    window, so the fallback refuses and the caller renders no_task plus the
    rebind hints instead."""
    task_path, status, source = _get_active_task(root, hook_input)
    if (
        not fallback_for_unbound
        or task_path
        or source not in {"missing-context", "empty-session"}
    ):
        return task_path, status, source
    candidates = _main_session_task_candidates(root)
    if len(candidates) != 1:
        return task_path, status, source
    fallback = candidates[0]
    task_json = root / fallback / "task.json"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback, "stale", "session-fallback"
    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        status = "unknown"
    return fallback, status.strip(), "session-fallback"


def _main_session_task_candidates(root: Path) -> list[str]:
    """All main-scope session bindings whose task directory is still valid,
    newest first. Subagent scopes never qualify: delegated sessions follow
    their runtime context, not another session's file."""
    try:
        from runtime.session_state import sessions_dir
    except Exception:
        return []
    sessions = sessions_dir(root)
    if not sessions.is_dir():
        return []
    entries: list[tuple[str, str]] = []
    try:
        paths = sorted(sessions.glob("*.json"))
    except OSError:
        return []
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
    candidates: list[str] = []
    for _seen_at, task_path in entries:
        task_dir = root / task_path
        if task_dir.is_dir() and (task_dir / "task.json").is_file():
            candidates.append(task_path)
    return candidates


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
