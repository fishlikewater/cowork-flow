#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cowork-flow diagnostics."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
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
    ".cowork-flow/spec/core/dispatch.md",
    "subagent dispatch",
    "subagent check",
    "runtime context",
    "advisory work",
]

REQUIRED_SUBAGENT_DISPATCH_SNIPPETS = [
    "Runtime-context subagent dispatch",
    "cowork_runtime_context_id",
    "cowork_host_context_key",
    "`runtime_context`: one row keyed by `<runtime_context_id>`",
    "`runtime_session`: one logical row keyed by `subagent_<runtime_context_id>`",
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
    "resolve_runtime_context",
    "runtime-context-invalid",
    'status = "delegated_subtask"',
    "from common.inject_workflow_state import",
]

REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS = [
    "[workflow-state:no_task]",
    "[workflow-state:delegated_subtask]",
    "[workflow-state:planning]",
    "[workflow-state:in_progress]",
    "[workflow-state:review]",
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
    "COWORK_ENTRY_CONTRACT_V2",
    "main-session prompts",
    "resolved by runtime context binding",
    "`UNKNOWN` is not subagent evidence",
    "Runtime context binding overrides project bootstrap text",
    "dual-channel classification",
]

REQUIRED_CONTRACT_REGISTRY_SNIPPETS = [
    '"schemaVersion": 1',
    '"COWORK_ENTRY_CONTRACT_V2"',
    '"RUNTIME_CONTEXT_DISPATCH_V2"',
    '"HOST_ADAPTER_CAPABILITIES_V1"',
    '"HOST_ADAPTER_SCHEMA_V1"',
    '"readWhen"',
    '".cowork-flow/spec/core/entry.md"',
    '".cowork-flow/spec/core/dispatch.md"',
    '".cowork-flow/spec/reference/adapters/capabilities.md"',
    '".cowork-flow/spec/reference/adapters/adapter.schema.json"',
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
    "DB `runtime_context` row",
    "bound runtime context",
    "leaf executor",
]

REQUIRED_CLAUDE_AGENT_SNIPPETS = [
    "name:",
    "cowork_runtime_context_id: <runtime_context_id>",
    "DB `runtime_context` row",
    "bound runtime context",
    "leaf executor",
    "Do not use the Task tool or invoke subagents",
]

FORBIDDEN_RUNTIME_FILE_SNIPPETS = [
    ".runtime/subagents",
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
    "${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run python",
    "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/inject-workflow-state.py",
    "UserPromptSubmit",
    "SessionStart",
]


@dataclass(frozen=True)
class ReleaseHealthResult:
    name: str
    status: str
    current: str
    blocker: str = ""
    next_command: str = ""
    files: tuple[str, ...] = ()


def _compact_lines(text: str, limit: int = 3) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    excerpt = "; ".join(lines[:limit])
    if len(lines) > limit:
        excerpt += f"; +{len(lines) - limit} more line(s)"
    return excerpt


def _compact_errors(errors: list[str], limit: int = 3) -> str:
    excerpt = "; ".join(errors[:limit])
    if len(errors) > limit:
        excerpt += f"; +{len(errors) - limit} more issue(s)"
    return excerpt


def _result_from_errors(
    name: str,
    errors: list[str],
    *,
    ok_current: str,
    next_command: str,
    files: tuple[str, ...],
) -> ReleaseHealthResult:
    if errors:
        return ReleaseHealthResult(
            name=name,
            status="FAIL",
            current=f"{len(errors)} issue(s) detected",
            blocker=_compact_errors(errors),
            next_command=next_command,
            files=files,
        )
    return ReleaseHealthResult(name=name, status="OK", current=ok_current, files=files)


def _result_from_subprocess(
    name: str,
    result: subprocess.CompletedProcess[str],
    *,
    next_command: str,
    files: tuple[str, ...],
) -> ReleaseHealthResult:
    output = _compact_lines(result.stdout) or _compact_lines(result.stderr)
    if result.returncode == 0:
        return ReleaseHealthResult(
            name=name,
            status="OK",
            current=output or "command completed successfully",
            next_command=next_command,
            files=files,
        )
    return ReleaseHealthResult(
        name=name,
        status="FAIL",
        current=f"command exited with {result.returncode}",
        blocker=_compact_lines(result.stderr) or output or "command failed",
        next_command=next_command,
        files=files,
    )


def _run_doctor_subcheck(
    repo_root: Path,
    name: str,
    args: list[str],
    *,
    next_command: str,
    files: tuple[str, ...],
) -> ReleaseHealthResult:
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), *args],
            cwd=repo_root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ReleaseHealthResult(
            name=name,
            status="FAIL",
            current="subcheck could not run",
            blocker=str(exc),
            next_command=next_command,
            files=files,
        )
    return _result_from_subprocess(
        name, result, next_command=next_command, files=files
    )


def _check_release_encoding(repo_root: Path) -> ReleaseHealthResult:
    try:
        from common import coding_standards
    except Exception as exc:
        return ReleaseHealthResult(
            name="UTF-8/BOM",
            status="FAIL",
            current="coding standard scanner could not load",
            blocker=str(exc),
            next_command=".\\.cowork-flow\\run.cmd python -m pytest tests/test_coding_standards.py -q",
            files=(".cowork-flow/scripts/common/coding_standards.py",),
        )

    scan_paths = [
        repo_root / ".cowork-flow" / "scripts",
        repo_root / "template" / ".cowork-flow" / "scripts",
    ]
    bom = coding_standards.scan_bom(scan_paths)
    encoding = coding_standards.scan_encoding(scan_paths)
    errors = [
        *bom.get("violations", []),
        *encoding.get("violations", []),
    ]
    return _result_from_errors(
        "UTF-8/BOM",
        errors,
        ok_current="BOM and explicit UTF-8 scans passed",
        next_command=".\\.cowork-flow\\run.cmd python -m pytest tests/test_coding_standards.py -q",
        files=(
            ".cowork-flow/scripts/common/coding_standards.py",
            "template/.cowork-flow/scripts/common/coding_standards.py",
        ),
    )


def _check_release_template_sync(repo_root: Path) -> ReleaseHealthResult:
    checked = (
        ".cowork-flow/scripts/doctor.py",
        ".cowork-flow/scripts/common/coding_standards.py",
        ".cowork-flow/scripts/flow/store.py",
    )
    errors: list[str] = []
    for rel in checked:
        root_file = repo_root / rel
        template_file = repo_root / "template" / rel
        if not root_file.is_file():
            errors.append(f"missing root file: {rel}")
            continue
        if not template_file.is_file():
            errors.append(f"missing template file: template/{rel}")
            continue
        if root_file.read_bytes() != template_file.read_bytes():
            errors.append(f"template drift: {rel}")
    return _result_from_errors(
        "root/template sync",
        errors,
        ok_current=f"{len(checked)} mirrored files match",
        next_command="npm test -- test/sync.test.js",
        files=tuple(checked),
    )


def _check_release_migrations(repo_root: Path) -> ReleaseHealthResult:
    try:
        from flow.store import FlowStore

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "release-health.sqlite")
            with FlowStore(db_path) as store:
                applied = store._get_applied_migrations()
                pending = store._discover_pending_migrations()
        errors = [f"pending migration v{version}: {name}" for version, name, _ in pending]
        return _result_from_errors(
            "DB migration",
            errors,
            ok_current=f"{len(applied)} migration(s) apply cleanly to a fresh DB",
            next_command=".\\.cowork-flow\\run.cmd flow migrate --status",
            files=(
                ".cowork-flow/scripts/flow/store.py",
                ".cowork-flow/scripts/flow/migrations",
            ),
        )
    except Exception as exc:
        return ReleaseHealthResult(
            name="DB migration",
            status="FAIL",
            current="fresh DB migration check failed",
            blocker=str(exc),
            next_command=".\\.cowork-flow\\run.cmd python -m pytest tests/test_flow_migration.py -q",
            files=(
                ".cowork-flow/scripts/flow/store.py",
                ".cowork-flow/scripts/flow/migrations",
            ),
        )


def _check_release_pack_boundary(repo_root: Path) -> ReleaseHealthResult:
    try:
        result = subprocess.run(
            ["node", "scripts/pack-check.js"],
            cwd=repo_root,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ReleaseHealthResult(
            name="pack boundary",
            status="FAIL",
            current="pack-check could not run",
            blocker=str(exc),
            next_command="npm run pack:check",
            files=("scripts/pack-check.js", "package.json"),
        )
    if result.returncode == 0:
        ok_line = next(
            (
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip().startswith("pack-check ok:")
            ),
            "package boundary check passed",
        )
        return ReleaseHealthResult(
            name="pack boundary",
            status="OK",
            current=ok_line,
            next_command="npm run pack:check",
            files=("scripts/pack-check.js", "package.json"),
        )
    return _result_from_subprocess(
        "pack boundary",
        result,
        next_command="npm run pack:check",
        files=("scripts/pack-check.js", "package.json"),
    )


def build_release_health_results(repo_root: Path) -> list[ReleaseHealthResult]:
    return [
        _check_release_encoding(repo_root),
        _check_release_template_sync(repo_root),
        _check_release_migrations(repo_root),
        _run_doctor_subcheck(
            repo_root,
            "host adapter",
            ["--host-adapters"],
            next_command=".\\.cowork-flow\\run.cmd doctor --host-adapters",
            files=(
                ".cowork-flow/adapters",
                "template/.cowork-flow/adapters",
                ".cowork-flow/spec/reference/adapters/adapter.schema.json",
            ),
        ),
        _run_doctor_subcheck(
            repo_root,
            "subagent safety",
            ["--subagent-safety"],
            next_command=".\\.cowork-flow\\run.cmd doctor --subagent-safety",
            files=(
                ".codex/agents",
                ".claude/agents",
                ".cowork-flow/spec/core/dispatch.md",
            ),
        ),
        _check_release_pack_boundary(repo_root),
    ]


def format_release_health_results(results: list[ReleaseHealthResult]) -> str:
    lines = ["Release health:"]
    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        lines.append(f"[{result.status}] {result.name}")
        lines.append(f"  current: {result.current}")
        if result.blocker:
            lines.append(f"  blocker: {result.blocker}")
        if result.next_command:
            lines.append(f"  next: {result.next_command}")
        if result.files:
            lines.append("  files:")
            for file in result.files:
                lines.append(f"    - {file}")
    lines.append(
        f"Summary: OK={counts.get('OK', 0)} WARN={counts.get('WARN', 0)} FAIL={counts.get('FAIL', 0)}"
    )
    return "\n".join(lines) + "\n"


def cmd_release_health(_: argparse.Namespace) -> int:
    results = build_release_health_results(get_repo_root())
    print(format_release_health_results(results), end="")
    return 1 if any(result.status == "FAIL" for result in results) else 0


def _check_claude_skill_commands_anchored(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if ".cowork-flow/run" not in line:
            continue
        if ".\\.cowork-flow\\run.cmd" in line:
            continue
        if "${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run" not in line:
            errors.append(f"{path}:{line_number} has unanchored Claude Code command")


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
        ".cowork-flow/spec/core/entry.md",
        "template/.cowork-flow/spec/core/entry.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_ENTRY_CONTRACT_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/spec/registry.json",
        "template/.cowork-flow/spec/registry.json",
    ):
        _check_file_contains(
            repo_root / rel, REQUIRED_CONTRACT_REGISTRY_SNIPPETS, errors
        )
    for rel in (
        ".cowork-flow/spec/core/dispatch.md",
        "template/.cowork-flow/spec/core/dispatch.md",
    ):
        _check_file_contains(
            repo_root / rel, REQUIRED_SUBAGENT_DISPATCH_SNIPPETS, errors
        )
    for rel in (
        ".cowork-flow/spec/core/state-templates.md",
        "template/.cowork-flow/spec/core/state-templates.md",
    ):
        _check_file_contains(
            repo_root / rel, REQUIRED_WORKFLOW_STATE_TEMPLATE_SNIPPETS, errors
        )
    for rel in (
        ".cowork-flow/scripts/common/entry_classifier.py",
        "template/.cowork-flow/scripts/common/entry_classifier.py",
    ):
        _check_file_contains(
            repo_root / rel, REQUIRED_ENTRY_CLASSIFIER_SNIPPETS, errors
        )


def _check_host_adapters(repo_root: Path, errors: list[str]) -> None:
    for rel in (
        ".cowork-flow/spec/reference/adapters/adapter.schema.json",
        "template/.cowork-flow/spec/reference/adapters/adapter.schema.json",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "dispatchSubagent",
                "freshChildContext",
                "runtimeContextDispatch",
                "unsupported",
            ],
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
        _check_file_omits(repo_root / rel, FORBIDDEN_RUNTIME_FILE_SNIPPETS, errors)
    for rel in (
        ".claude/agents/cowork-research.md",
        ".claude/agents/cowork-implement.md",
        ".claude/agents/cowork-check.md",
        "template/.claude/agents/cowork-research.md",
        "template/.claude/agents/cowork-implement.md",
        "template/.claude/agents/cowork-check.md",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_CLAUDE_AGENT_SNIPPETS, errors)
        _check_file_omits(repo_root / rel, FORBIDDEN_RUNTIME_FILE_SNIPPETS, errors)
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
    for skill_root in (
        repo_root / ".claude" / "skills",
        repo_root / "template" / ".claude" / "skills",
    ):
        for skill in skill_root.glob("*/SKILL.md"):
            _check_claude_skill_commands_anchored(skill, errors)
    for rel in (
        ".claude/settings.json",
        "template/.claude/settings.json",
    ):
        _check_file_contains(
            repo_root / rel, REQUIRED_CLAUDE_HOOK_SETTINGS_SNIPPETS, errors
        )
    for rel in (
        ".claude/hooks/inject-workflow-state.py",
        "template/.claude/hooks/inject-workflow-state.py",
        ".codex/hooks/inject-workflow-state.py",
        "template/.codex/hooks/inject-workflow-state.py",
    ):
        _check_file_contains(repo_root / rel, REQUIRED_RUNTIME_HOOK_SNIPPETS, errors)
    for rel in (
        ".cowork-flow/scripts/common/inject_workflow_state.py",
        "template/.cowork-flow/scripts/common/inject_workflow_state.py",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "resolve_runtime_context_id",
                "bind_runtime_context",
                "state-templates.md",
            ],
            errors,
        )
    for rel in (
        "CLAUDE.md",
        "template/CLAUDE.md",
    ):
        _check_file_contains(
            repo_root / rel,
            [
                "@AGENTS.md",
                "<!-- COWORK-FLOW:START -->",
            ],
            errors,
        )
        _check_file_omits(
            repo_root / rel,
            [
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
                '.cowork-flow", "spec", "registry.json',
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
                    errors.append(
                        f"{rel} description contains stale dispatch marker: {snippet}"
                    )
        elif data is not None:
            errors.append(f"{rel} missing description")
    if (repo_root / "README.md").is_file():
        _check_file_omits(
            repo_root / "README.md", FORBIDDEN_README_DISPATCH_SNIPPETS, errors
        )
    for rel in (
        ".codex/agents/worker.toml",
        ".codex/agents/default.toml",
        ".codex/agents/explorer.toml",
        "template/.codex/agents/worker.toml",
        "template/.codex/agents/default.toml",
        "template/.codex/agents/explorer.toml",
    ):
        _check_file_contains(
            repo_root / rel, ["bootstrap", "start", "resume", "advisory"], errors
        )
        data = _check_toml_parseable(repo_root / rel, errors)
        if data is not None and data.get("name") != Path(rel).stem:
            errors.append(f"{rel} name must match filename")
    for rel in (
        ".cowork-flow/workflow.md",
        "template/.cowork-flow/workflow.md",
    ):
        _check_file_contains(
            repo_root / rel, REQUIRED_WORKFLOW_DISPATCH_SNIPPETS, errors
        )
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
    parser.add_argument(
        "--release-health",
        action="store_true",
        help="Run aggregate release health diagnostics",
    )
    parser.add_argument(
        "--subagent-safety", action="store_true", help="Check subagent safety wiring"
    )
    parser.add_argument(
        "--entry-contract",
        action="store_true",
        help="Check entry classification contract",
    )
    parser.add_argument(
        "--host-adapters", action="store_true", help="Check host adapter declarations"
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.release_health:
        return cmd_release_health(args)
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
