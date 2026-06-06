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


ENTRY_BOUNDARY_DIR = "entry" + "-boundary"

REQUIRED_START_SNIPPETS = [
    "This skill is for the main session",
    "accepted only after runtime context binding is recorded",
    "Main repository changes follow `Plan -> Implement -> Check -> Finish`",
    "Host Adapter",
    ".cowork-flow/run subagent init",
    "cowork_runtime_context_id",
    "cowork_host_context_key",
    ".cowork-flow/run subagent bind <runtime_context_id> <host_context_key>",
    ".cowork-flow/run subagent close",
]

REQUIRED_FIXED_AGENT_SNIPPETS = [
    "cowork_runtime_context_id: <runtime_context_id>",
    "bound runtime context",
    "report needs_context",
    "MUST NOT spawn",
    "multi_agent = false",
    "enabled = false",
]

REQUIRED_FIXED_AGENT_DESCRIPTION_SNIPPET = "runtime-context"

FORBIDDEN_FIXED_AGENT_DESCRIPTION_SNIPPETS = [
    "Active task",
    "active task",
    "self-loads task context",
    "self-loads",
]

FORBIDDEN_README_DISPATCH_SNIPPETS = [
    'message="Active task: <task-dir>\\n\\n<assignment>"',
    "提示词首行使用 `Active task: <task-dir>`",
]

REQUIRED_WORKFLOW_DISPATCH_SNIPPETS = [
    "宿主适配器契约",
    ".cowork-flow/spec/subagent-dispatch.md",
    "新鲜子上下文",
    "runtime context",
    "适配器等待原语",
    "适配器列表原语",
    "适配器取消/关闭原语",
    "advisory work",
]

REQUIRED_SUBAGENT_DISPATCH_SNIPPETS = [
    "Runtime-context subagent dispatch",
    "cowork_runtime_context_id",
    "cowork_host_context_key",
    ".cowork-flow/.runtime/subagents/<runtime_context_id>.json",
    ".cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json",
    "Verified binding is the formal dispatch acceptance event",
    "subagent bind <runtime_context_id> <host_context_key>",
    'bound_context_key: "<host_context_key>"',
    "fail-closed subagent state",
    "Generic `worker`, `default`, or `explorer` dispatch is advisory only",
]

REQUIRED_HOOK_SNIPPETS = [
    ".cowork-flow/run python .codex/hooks/inject-workflow-state.py",
]

REQUIRED_RUNTIME_HOOK_SNIPPETS = [
    "resolve_runtime_context_id",
    "bind_runtime_context",
    "runtime-context-invalid",
    'status = "delegated_subtask"',
    "workflow-state-templates.md",
]

REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS = [
    "[workflow-state:no_task]",
    "[workflow-state:delegated_subtask]",
    "[workflow-state:planning]",
    "[workflow-state:in_progress]",
    "[workflow-state:review]",
    "[workflow-state:checking]",
    "[workflow-state:completed]",
    "runtime context",
    "UNKNOWN is not a delegated",
]

REQUIRED_ENTRY_CLASSIFIER_SNIPPETS = [
    "classify_entry",
    "EntryKind.MAIN_SESSION",
    "EntryKind.READ_ONLY",
    "EntryKind.COMMAND_ONLY",
    "EntryKind.UNKNOWN",
]

REQUIRED_ENTRY_CONTRACT_SNIPPETS = [
    "COWORK_ENTRY_CONTRACT_V1",
    "main-session prompts",
    "resolved by runtime context binding",
    "`UNKNOWN` is not subagent evidence",
    "Runtime context binding overrides project bootstrap text",
]

REQUIRED_CONTRACT_REGISTRY_SNIPPETS = [
    '"schemaVersion": 1',
    '"COWORK_ENTRY_CONTRACT_V1"',
    '"RUNTIME_CONTEXT_DISPATCH_V2"',
    '"HOST_ADAPTER_CAPABILITIES_V1"',
    '"HOST_ADAPTER_SCHEMA_V1"',
    '"readWhen"',
    '".cowork-flow/spec/entry-contract.md"',
    '".cowork-flow/spec/subagent-dispatch.md"',
    '".cowork-flow/spec/capabilities.md"',
    '".cowork-flow/spec/adapter.schema.json"',
]

REQUIRED_ADAPTER_SNIPPETS = [
    "schemaVersion: 1",
    "capabilities:",
    "dispatchSubagent:",
    "freshChildContext:",
    "waitChild:",
    "listChildren:",
    "cancelChild:",
    "runtimeContextDispatch:",
    "runtimeContextBinding:",
    "runtimeContextCleanup:",
    "runtimeContext:",
    "promptKey: cowork_runtime_context_id",
    "envKey: COWORK_FLOW_RUNTIME_CONTEXT_ID",
    "metadataKey: cowork_runtime_context_id",
    "dispatch: RUNTIME_CONTEXT_DISPATCH_V2",
    "leafExecutor: true",
    "whenRuntimeContextMissing: fail_closed",
]

REQUIRED_OPENCODE_AGENT_SNIPPETS = [
    "mode: subagent",
    "task: deny",
    "cowork_runtime_context_id: <runtime_context_id>",
    "bound runtime context",
    "leaf executor",
]

REQUIRED_CLAUDE_AGENT_SNIPPETS = [
    "name:",
    "cowork_runtime_context_id: <runtime_context_id>",
    "bound runtime context",
    "leaf executor",
    "Do not use the Task tool or invoke subagents",
]

REQUIRED_RUNTIME_COMMAND_SNIPPETS = [
    ".cowork-flow/run subagent init",
    "cowork_runtime_context_id: <runtime_context_id>",
    "needs_context",
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


def _check_file_contains(path: Path, snippets: list[str], errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{path} missing snippet: {snippet}")


def _check_file_omits(path: Path, snippets: list[str], errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet in text:
            errors.append(f"{path} contains forbidden snippet: {snippet}")


def _check_file_absent(path: Path, errors: list[str]) -> None:
    if path.exists():
        errors.append(f"unexpected file: {path}")


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


def _check_common_contracts(repo_root: Path, errors: list[str]) -> None:
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


def _check_host_adapters(repo_root: Path, errors: list[str]) -> None:
    for rel in (
        ".cowork-flow/spec/adapter.schema.json",
        "template/.cowork-flow/spec/adapter.schema.json",
        ".cowork-flow/spec/capabilities.md",
        "template/.cowork-flow/spec/capabilities.md",
    ):
        _check_file_contains(
            repo_root / rel,
            ["dispatchSubagent", "freshChildContext", "runtimeContextDispatch", "unsupported"],
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


def cmd_entry_contract(_: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors: list[str] = []
    _check_common_contracts(repo_root, errors)
    for rel in (
        f".agents/skills/{ENTRY_BOUNDARY_DIR}/SKILL.md",
        f"template/.agents/skills/{ENTRY_BOUNDARY_DIR}/SKILL.md",
    ):
        _check_file_absent(repo_root / rel, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("entry contract checks passed")
    return 0


def cmd_host_adapters(_: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors: list[str] = []
    _check_host_adapters(repo_root, errors)
    for rel in (
        ".opencode/agents/cowork-research.md",
        ".opencode/agents/cowork-implement.md",
        ".opencode/agents/cowork-check.md",
        "template/.opencode/agents/cowork-research.md",
        "template/.opencode/agents/cowork-implement.md",
        "template/.opencode/agents/cowork-check.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_OPENCODE_AGENT_SNIPPETS, errors)
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
        ".opencode/commands/cowork-research.md",
        ".opencode/commands/cowork-implement.md",
        ".opencode/commands/cowork-check.md",
        "template/.claude/commands/cowork-research.md",
        "template/.claude/commands/cowork-implement.md",
        "template/.claude/commands/cowork-check.md",
        "template/.opencode/commands/cowork-research.md",
        "template/.opencode/commands/cowork-implement.md",
        "template/.opencode/commands/cowork-check.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_RUNTIME_COMMAND_SNIPPETS, errors)
    for rel in (
        ".claude/skills/start/SKILL.md",
        ".claude/skills/check/SKILL.md",
        "template/.claude/skills/start/SKILL.md",
        "template/.claude/skills/check/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_SKILL_SNIPPETS, errors)
    for rel in (
        f".claude/skills/{ENTRY_BOUNDARY_DIR}/SKILL.md",
        f"template/.claude/skills/{ENTRY_BOUNDARY_DIR}/SKILL.md",
    ):
        _check_file_absent(repo_root / rel, errors)
    for rel in (
        ".claude/settings.json",
        "template/.claude/settings.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_HOOK_SETTINGS_SNIPPETS, errors)
    for rel in (
        ".claude/hooks/inject-workflow-state.py",
        "template/.claude/hooks/inject-workflow-state.py",
        ".codex/hooks/inject-workflow-state.py",
        "template/.codex/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_RUNTIME_HOOK_SNIPPETS, errors)
    for rel in (
        "CLAUDE.md",
        "template/CLAUDE.md",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "@AGENTS.md",
                "<!-- COWORK-FLOW:START -->",
                ".cowork-flow/run subagent init",
                "cowork_runtime_context_id: <runtime_context_id>",
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
                "RUNTIME_CONTEXT_DISPATCH_V2",
                "resolveRuntimeContextId",
                "bindRuntimeContext",
                "runtime-context-invalid",
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
        ".agents/skills/start/SKILL.md",
        "template/.agents/skills/start/SKILL.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_START_SNIPPETS, errors)
    for rel in (
        f".agents/skills/{ENTRY_BOUNDARY_DIR}/SKILL.md",
        f"template/.agents/skills/{ENTRY_BOUNDARY_DIR}/SKILL.md",
    ):
        _check_file_absent(repo_root / rel, errors)
    for rel in (
        ".codex/agents/cowork-research.toml",
        ".codex/agents/cowork-implement.toml",
        ".codex/agents/cowork-check.toml",
        "template/.codex/agents/cowork-research.toml",
        "template/.codex/agents/cowork-implement.toml",
        "template/.codex/agents/cowork-check.toml",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_FIXED_AGENT_SNIPPETS, errors)
        data = _check_toml_parseable(repo_root / rel, errors)
        if data is not None and data.get("name") != Path(rel).stem:
            errors.append(f"{rel} name must match filename")
        description = data.get("description") if data is not None else None
        if isinstance(description, str):
            if REQUIRED_FIXED_AGENT_DESCRIPTION_SNIPPET not in description:
                errors.append(
                    f"{rel} description must mention {REQUIRED_FIXED_AGENT_DESCRIPTION_SNIPPET}"
                )
            for snippet in FORBIDDEN_FIXED_AGENT_DESCRIPTION_SNIPPETS:
                if snippet in description:
                    errors.append(f"{rel} description contains stale dispatch marker: {snippet}")
        elif data is not None:
            errors.append(f"{rel} missing description")
    if (repo_root / "README.md").is_file():
        _check_file_omits(repo_root / "README.md", FORBIDDEN_README_DISPATCH_SNIPPETS, errors)
    for rel in (
        ".codex/agents/worker.toml",
        ".codex/agents/default.toml",
        ".codex/agents/explorer.toml",
        "template/.codex/agents/worker.toml",
        "template/.codex/agents/default.toml",
        "template/.codex/agents/explorer.toml",
    ):
        _check_file_contains(repo_root / rel, ["bootstrap", "start", "resume", "advisory"], errors)
        data = _check_toml_parseable(repo_root / rel, errors)
        if data is not None and data.get("name") != Path(rel).stem:
            errors.append(f"{rel} name must match filename")
    for rel in (
        ".cowork-flow/workflow.md",
        "template/.cowork-flow/workflow.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_WORKFLOW_DISPATCH_SNIPPETS, errors)
    _check_common_contracts(repo_root, errors)
    _check_host_adapters(repo_root, errors)
    for rel in (
        ".codex/hooks.json",
        "template/.codex/hooks.json",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_HOOK_SNIPPETS, errors)
    for rel in (
        ".codex/hooks/inject-workflow-state.py",
        "template/.codex/hooks/inject-workflow-state.py",
        ".claude/hooks/inject-workflow-state.py",
        "template/.claude/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_RUNTIME_HOOK_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/scripts/subagent.py",
        "template/.cowork-flow/scripts/subagent.py",
        ".cowork-flow/scripts/common/execution_context.py",
        "template/.cowork-flow/scripts/common/execution_context.py",
        ".cowork-flow/scripts/common/active_task.py",
        "template/.cowork-flow/scripts/common/active_task.py",
    ):
        if not (repo_root / rel).is_file():
            errors.append(f"missing file: {rel}")
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
