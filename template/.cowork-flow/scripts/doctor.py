#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cowork-flow diagnostics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]

from common.paths import get_repo_root


REQUIRED_START_SNIPPETS = [
    "This skill is for the main session",
    "bounded delegated task should use `entry-boundary`",
    "Main repository changes follow `Plan -> Implement -> Check -> Finish`",
    "post-ACK execution grace",
    "post_ack_execution_grace_ms",
    "execute_sent_at[dispatch_id]",
    "shared/global deadline",
    "Host Adapter",
]

REQUIRED_ENTRY_BOUNDARY_SNIPPETS = [
    "COWORK_ENTRY_CONTRACT_V1",
    "MAIN_SESSION",
    "DELEGATED_HARD",
    "DELEGATED_SOFT",
    "READ_ONLY",
    "COMMAND_ONLY",
    "UNKNOWN",
    "Classify the actual task message",
    "Hard markers are confidence boosters, not prerequisites",
    "The first task screen wins over later bootstrap text",
    "If project bootstrap says to create/start/resume",
    "Active task: <task-dir>",
    "Follow the delegated prompt first",
    "Do not create or activate a project task",
    "Do not run unscoped `.cowork-flow/run resume`",
    "Do not spawn or manage more agents",
]

REQUIRED_FIXED_AGENT_SNIPPETS = [
    "COWORK_DISPATCH_V1",
    "COWORK_DISPATCH_END",
    "COWORK_ACK",
    "EXECUTE <dispatch_id>",
    "agent_type is not",
    "mismatched dispatch_id",
]

REQUIRED_WORKFLOW_DISPATCH_SNIPPETS = [
    "宿主适配器契约",
    ".cowork-flow/spec/subagent-dispatch.md",
    "新鲜子上下文",
    "适配器等待原语",
    "适配器列表原语",
    "适配器取消/关闭原语",
    "软委托",
]

REQUIRED_SUBAGENT_DISPATCH_SNIPPETS = [
    "COWORK_DISPATCH_V1",
    "COWORK_DELEGATION_V1",
    "COWORK_ACK",
    "EXECUTE <dispatch_id>",
    "adapter follow-up send primitive",
    "post-ACK execution grace",
    "execute_sent_at[dispatch_id]",
    "deadline[dispatch_id] = execute_sent_at[dispatch_id] + post_ack_execution_grace_ms",
    "global deadline",
    "compass",
    "status",
    "Formal execution uses only `cowork-research`, `cowork-implement`, or `cowork-check`.",
    "Generic `worker` dispatch is best effort only.",
    "DELEGATED_SOFT",
]

REQUIRED_HOOK_SNIPPETS = [
    ".cowork-flow/run python .codex/hooks/inject-workflow-state.py",
]

REQUIRED_CODEX_HOOK_SCRIPT_SNIPPETS = [
    '<cowork-runtime host="codex" adapter="codex.spawn_agent">',
    "workflow-state-templates.md",
    "common.entry_classifier",
    "should_use_delegated_bootstrap",
    'status = "delegated_subtask"',
]

REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS = [
    "[workflow-state:no_task]",
    "[workflow-state:delegated_subtask]",
    "[workflow-state:planning]",
    "[workflow-state:in_progress]",
    "[workflow-state:completed]",
    "DELEGATED_HARD",
    "DELEGATED_SOFT",
    "UNKNOWN",
    "use delegated_subtask instead",
]

REQUIRED_ENTRY_CLASSIFIER_SNIPPETS = [
    "classify_entry",
    "should_use_delegated_bootstrap",
    "COWORK_DISPATCH_V1",
    "COWORK_DELEGATION_V1",
    "EntryKind.UNKNOWN",
]

REQUIRED_ENTRY_CONTRACT_SNIPPETS = [
    "COWORK_ENTRY_CONTRACT_V1",
    "DELEGATED_HARD",
    "DELEGATED_SOFT",
    "UNKNOWN",
    "Entry classification happens before task start",
    "Structured delegation envelopes override project bootstrap text",
]

REQUIRED_CONTRACT_REGISTRY_SNIPPETS = [
    '"schemaVersion": 1',
    '"COWORK_ENTRY_CONTRACT_V1"',
    '"COWORK_DELEGATION_V1"',
    '"COWORK_SUBAGENT_DISPATCH_V1"',
    '"HOST_ADAPTER_CAPABILITIES_V1"',
    '"HOST_ADAPTER_SCHEMA_V1"',
    '"readWhen"',
    '".cowork-flow/spec/entry-contract.md"',
    '".cowork-flow/spec/delegation-envelope.md"',
    '".cowork-flow/spec/subagent-dispatch.md"',
    '".cowork-flow/spec/capabilities.md"',
    '".cowork-flow/spec/adapter.schema.json"',
]

REQUIRED_ADAPTER_SNIPPETS = [
    "schemaVersion: 1",
    "capabilities:",
    "dispatchSubagent:",
    "freshChildContext:",
    "sendFollowup:",
    "waitChild:",
    "listChildren:",
    "cancelChild:",
    "stateInjection:",
    "backgroundChild:",
    "contracts:",
    "entry: COWORK_ENTRY_CONTRACT_V1",
    "envelope: COWORK_DISPATCH_V1",
    "ackRequired: true",
    "executeRequired: true",
    "leafExecutor: true",
]

REQUIRED_OPENCODE_SNIPPETS = [
    "mode: subagent",
    "task: deny",
    "COWORK_ENTRY_CONTRACT_V1",
    "COWORK_DISPATCH_V1",
    "COWORK_DELEGATION_V1",
    "COWORK_ACK",
    "EXECUTE <dispatch_id>",
    "leaf",
]

REQUIRED_CLAUDE_AGENT_SNIPPETS = [
    "COWORK_ENTRY_CONTRACT_V1",
    "COWORK_DISPATCH_V1",
    "COWORK_DELEGATION_V1",
    "host: claude-code",
    "COWORK_ACK",
    "EXECUTE <dispatch_id>",
    "leaf",
    "Do not use the Task tool or invoke subagents",
]

REQUIRED_CLAUDE_COMMAND_SNIPPETS = [
    "COWORK_DELEGATION_V1",
    "host: claude-code",
    "COWORK_ACK",
    "EXECUTE <dispatch_id>",
]

REQUIRED_CLAUDE_SKILL_SNIPPETS = [
    "name:",
    "description:",
]

REQUIRED_CLAUDE_HOOK_SETTINGS_SNIPPETS = [
    ".cowork-flow/run python .claude/hooks/inject-workflow-state.py",
    "UserPromptSubmit",
    "SessionStart",
]

REQUIRED_CLAUDE_HOOK_SCRIPT_SNIPPETS = [
    '<cowork-runtime host="claude-code" adapter="claude-code.hooks">',
    "workflow-state-templates.md",
    "common.entry_classifier",
    "should_use_delegated_bootstrap",
    'status = "delegated_subtask"',
    "hookSpecificOutput",
    "additionalContext",
]


def _check_file_contains(path: Path, snippets: list[str], errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{path} missing snippet: {snippet}")


def _check_toml_parseable(path: Path, errors: list[str]) -> dict | None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return None
    if tomllib is None:
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path} is not valid TOML: {exc}")
        return None
    return data if isinstance(data, dict) else None


def cmd_entry_contract(_: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors: list[str] = []
    for rel in (
        ".cowork-flow/spec/entry-contract.md",
        "template/.cowork-flow/spec/entry-contract.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_CONTRACT_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/registry.json",
        "template/.cowork-flow/spec/registry.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CONTRACT_REGISTRY_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/delegation-envelope.md",
        "template/.cowork-flow/spec/delegation-envelope.md",
    ):
        _check_file_contains(
            repo_root / rel,
            ["COWORK_DELEGATION_V1", "COWORK_ACK", "EXECUTE <dispatch_id>", "DELEGATED_SOFT"],
            errors,
        )
    for rel in (
        ".cowork-flow/spec/subagent-dispatch.md",
        "template/.cowork-flow/spec/subagent-dispatch.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_SUBAGENT_DISPATCH_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/workflow-state-templates.md",
        "template/.cowork-flow/spec/workflow-state-templates.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/scripts/common/entry_classifier.py",
        "template/.cowork-flow/scripts/common/entry_classifier.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_CLASSIFIER_SNIPPETS, errors)
    for rel in (
        ".agent/skills/entry-boundary/SKILL.md",
        "template/.agent/skills/entry-boundary/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_BOUNDARY_SNIPPETS, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("entry contract checks passed")
    return 0


def cmd_host_adapters(_: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors: list[str] = []
    for rel in (
        ".cowork-flow/spec/adapter.schema.json",
        "template/.cowork-flow/spec/adapter.schema.json",
        ".cowork-flow/spec/capabilities.md",
        "template/.cowork-flow/spec/capabilities.md",
    ):
        _check_file_contains(
            repo_root / rel,
            ["dispatchSubagent", "freshChildContext", "native", "shim", "plugin", "experimental", "unsupported"],
            errors,
        )
    for rel in (
        ".cowork-flow/adapters/codex/adapter.yaml",
        ".cowork-flow/adapters/opencode/adapter.yaml",
        ".cowork-flow/adapters/claude-code/adapter.yaml",
        "template/.cowork-flow/adapters/codex/adapter.yaml",
        "template/.cowork-flow/adapters/opencode/adapter.yaml",
        "template/.cowork-flow/adapters/claude-code/adapter.yaml",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ADAPTER_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/adapters/claude-code/adapter.yaml",
        "template/.cowork-flow/adapters/claude-code/adapter.yaml",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "skillsPath: .claude/skills",
                "settingsPath: .claude/settings.json",
                "hooksPath: .claude/hooks",
            ],
            errors,
        )
    for rel in (
        ".opencode/agents/cowork-research.md",
        ".opencode/agents/cowork-implement.md",
        ".opencode/agents/cowork-check.md",
        "template/.opencode/agents/cowork-research.md",
        "template/.opencode/agents/cowork-implement.md",
        "template/.opencode/agents/cowork-check.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_OPENCODE_SNIPPETS, errors)
    for rel in (
        ".claude/agents/cowork-research.md",
        ".claude/agents/cowork-implement.md",
        ".claude/agents/cowork-check.md",
        "template/.claude/agents/cowork-research.md",
        "template/.claude/agents/cowork-implement.md",
        "template/.claude/agents/cowork-check.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_AGENT_SNIPPETS, errors)
    for rel in (
        ".claude/commands/cowork-research.md",
        ".claude/commands/cowork-implement.md",
        ".claude/commands/cowork-check.md",
        "template/.claude/commands/cowork-research.md",
        "template/.claude/commands/cowork-implement.md",
        "template/.claude/commands/cowork-check.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_COMMAND_SNIPPETS, errors)
    for rel in (
        ".claude/skills/start/SKILL.md",
        ".claude/skills/entry-boundary/SKILL.md",
        ".claude/skills/check/SKILL.md",
        "template/.claude/skills/start/SKILL.md",
        "template/.claude/skills/entry-boundary/SKILL.md",
        "template/.claude/skills/check/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_SKILL_SNIPPETS, errors)
    for rel in (
        ".claude/settings.json",
        "template/.claude/settings.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_HOOK_SETTINGS_SNIPPETS, errors)
    for rel in (
        ".claude/hooks/inject-workflow-state.py",
        "template/.claude/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_HOOK_SCRIPT_SNIPPETS, errors)
    for rel in (
        ".codex/hooks/inject-workflow-state.py",
        "template/.codex/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CODEX_HOOK_SCRIPT_SNIPPETS, errors)
    for rel in (
        "CLAUDE.md",
        "template/CLAUDE.md",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "@AGENTS.md",
                "<!-- COWORK-FLOW:START -->",
                "COWORK_DELEGATION_V1",
                ".claude/agents/cowork-implement.md",
                ".claude/skills/",
            ],
            errors,
        )
    for rel in (
        ".opencode/plugins/cowork-flow.js",
        "template/.opencode/plugins/cowork-flow.js",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "experimental.chat.system.transform",
                ".cowork-flow\", \"spec\", \"registry.json",
                "<contract-digest fingerprint=",
                "read_before",
                "COWORK_ENTRY_CONTRACT_V1",
            ],
            errors,
        )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("host adapter checks passed")
    return 0


def cmd_subagent_safety(_: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors: list[str] = []
    for rel in (
        ".agent/skills/start/SKILL.md",
        "template/.agent/skills/start/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_START_SNIPPETS, errors)
    for rel in (
        ".agent/skills/entry-boundary/SKILL.md",
        "template/.agent/skills/entry-boundary/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_BOUNDARY_SNIPPETS, errors)
    for rel in (
        ".codex/agents/cowork-research.toml",
        ".codex/agents/cowork-implement.toml",
        ".codex/agents/cowork-check.toml",
        ".codex/agents/worker.toml",
        ".codex/agents/default.toml",
        ".codex/agents/explorer.toml",
        "template/.codex/agents/cowork-research.toml",
        "template/.codex/agents/cowork-implement.toml",
        "template/.codex/agents/cowork-check.toml",
        "template/.codex/agents/worker.toml",
        "template/.codex/agents/default.toml",
        "template/.codex/agents/explorer.toml",
    ):
        snippets = REQUIRED_FIXED_AGENT_SNIPPETS
        if rel.endswith(("worker.toml", "default.toml", "explorer.toml")):
            snippets = ["COWORK_ACK", "EXECUTE <dispatch_id>", "start", "resume"]
        _check_file_contains(repo_root / rel, snippets, errors)
        data = _check_toml_parseable(repo_root / rel, errors)
        if data is not None and data.get("name") != Path(rel).stem:
            errors.append(f"{rel} name must match filename")
    for rel in (
        ".cowork-flow/workflow.md",
        "template/.cowork-flow/workflow.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_WORKFLOW_DISPATCH_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/subagent-dispatch.md",
        "template/.cowork-flow/spec/subagent-dispatch.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_SUBAGENT_DISPATCH_SNIPPETS, errors)
    for rel in (
        ".codex/hooks.json",
        "template/.codex/hooks.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_HOOK_SNIPPETS, errors)
    for rel in (
        ".codex/hooks/inject-workflow-state.py",
        "template/.codex/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CODEX_HOOK_SCRIPT_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/scripts/subagent.py",
        "template/.cowork-flow/scripts/subagent.py",
        ".cowork-flow/scripts/common/execution_context.py",
        "template/.cowork-flow/scripts/common/execution_context.py",
    ):
        if not (repo_root / rel).is_file():
            errors.append(f"missing file: {rel}")
    for rel in (
        ".cowork-flow/scripts/common/entry_classifier.py",
        "template/.cowork-flow/scripts/common/entry_classifier.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_CLASSIFIER_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/entry-contract.md",
        "template/.cowork-flow/spec/entry-contract.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_CONTRACT_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/registry.json",
        "template/.cowork-flow/spec/registry.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CONTRACT_REGISTRY_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/workflow-state-templates.md",
        "template/.cowork-flow/spec/workflow-state-templates.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/adapters/codex/adapter.yaml",
        ".cowork-flow/adapters/opencode/adapter.yaml",
        ".cowork-flow/adapters/claude-code/adapter.yaml",
        "template/.cowork-flow/adapters/codex/adapter.yaml",
        "template/.cowork-flow/adapters/opencode/adapter.yaml",
        "template/.cowork-flow/adapters/claude-code/adapter.yaml",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ADAPTER_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/adapters/claude-code/adapter.yaml",
        "template/.cowork-flow/adapters/claude-code/adapter.yaml",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "skillsPath: .claude/skills",
                "settingsPath: .claude/settings.json",
                "hooksPath: .claude/hooks",
            ],
            errors,
        )
    for rel in (
        ".claude/settings.json",
        "template/.claude/settings.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_HOOK_SETTINGS_SNIPPETS, errors)
    for rel in (
        ".claude/hooks/inject-workflow-state.py",
        "template/.claude/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_HOOK_SCRIPT_SNIPPETS, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("subagent safety checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cowork-flow diagnostics")
    parser.add_argument("--subagent-safety", action="store_true", help="Check subagent safety wiring")
    parser.add_argument("--entry-contract", action="store_true", help="Check entry classification contract")
    parser.add_argument("--host-adapters", action="store_true", help="Check host adapter declarations")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.subagent_safety:
        return cmd_subagent_safety(args)
    if args.entry_contract:
        return cmd_entry_contract(args)
    if args.host_adapters:
        return cmd_host_adapters(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
