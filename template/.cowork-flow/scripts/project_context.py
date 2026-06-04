#!/usr/bin/env python3
"""Generate and refresh .cowork-flow/project-context.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common.paths import DIR_WORKFLOW, get_repo_root

PROJECT_CONTEXT_FILE = "project-context.md"
GENERATED_START = "<!-- COWORK-FLOW:PROJECT-CONTEXT:START -->"
GENERATED_END = "<!-- COWORK-FLOW:PROJECT-CONTEXT:END -->"
MANUAL_HEADING = "## Manual Notes"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _display(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _status_line(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    return f"- `{rel_path}`: {'present' if path.exists() else 'missing'}"


def _extract_backtick_value(text: str, label: str) -> str | None:
    pattern = re.compile(rf"-\s*{re.escape(label)}\s*[：:]\s*`([^`]+)`")
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return None


def _project_identity(repo_root: Path) -> list[str]:
    agents = _read_text(repo_root / "AGENTS.md")
    package = _read_json(repo_root / "package.json")
    name = _extract_backtick_value(agents, "项目名称") or str(package.get("name") or "unknown")
    stack = _extract_backtick_value(agents, "主要技术栈") or "unspecified"
    commit_policy = _extract_backtick_value(agents, "提交策略") or "unspecified"
    doc_language = _extract_backtick_value(agents, "文档语言") or "unspecified"
    return [
        "## Project Identity",
        "",
        f"- Name: `{name}`",
        f"- Stack: {stack}",
        f"- Commit policy: {commit_policy}",
        f"- Documentation language: {doc_language}",
        "",
    ]


def _package_scripts(repo_root: Path) -> list[str]:
    package_path = repo_root / "package.json"
    package = _read_json(package_path)
    lines = ["## Package Scripts", ""]
    if not package_path.is_file():
        lines.extend(["- package.json: missing", ""])
        return lines

    scripts = package.get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        lines.extend(["- No package scripts declared.", ""])
        return lines

    for name in sorted(str(key) for key in scripts.keys()):
        value = scripts.get(name)
        if isinstance(value, str):
            lines.append(f"- `npm run {name}`: `{value}`")
    lines.append("")
    return lines


def _workflow_commands() -> list[str]:
    return [
        "## Workflow Commands",
        "",
        "- `./.cowork-flow/run task next`: show next safe workflow action.",
        "- `./.cowork-flow/run task start <task-dir>`: activate task and run readiness gates.",
        "- `./.cowork-flow/run task review [task-dir]`: move task to check stage.",
        "- `./.cowork-flow/run task complete [task-dir]`: mark task completed.",
        "- `./.cowork-flow/run change validate <slug>`: validate change metadata and required docs.",
        "- `./.cowork-flow/run project-context refresh`: refresh this file.",
        "",
    ]


def _host_adapters(repo_root: Path) -> list[str]:
    lines = ["## Host Adapters", ""]
    for rel_path in (
        ".codex",
        ".opencode",
        ".claude",
        ".cowork-flow/adapters/codex/adapter.yaml",
        ".cowork-flow/adapters/opencode/adapter.yaml",
        ".cowork-flow/adapters/claude-code/adapter.yaml",
    ):
        lines.append(_status_line(repo_root, rel_path))
    lines.append("")
    return lines


def _important_specs(repo_root: Path) -> list[str]:
    lines = ["## Important Specs", ""]
    spec_dir = repo_root / DIR_WORKFLOW / "spec"
    if not spec_dir.is_dir():
        lines.extend(["- `.cowork-flow/spec`: missing", ""])
        return lines

    for path in sorted(spec_dir.rglob("*.md")):
        lines.append(f"- `{_display(path, repo_root)}`")
    lines.append("")
    return lines


def _local_constraints(repo_root: Path) -> list[str]:
    lines = ["## Local Constraints", ""]
    for rel_path in (
        "AGENTS.md",
        ".cowork-flow/workflow.md",
        ".cowork-flow/config.yaml",
        ".cowork-flow/.version",
    ):
        lines.append(_status_line(repo_root, rel_path))
    lines.extend(
        [
            "- Generated context is an index. Authoritative rules stay in `AGENTS.md`, `.cowork-flow/workflow.md`, and `.cowork-flow/spec/`.",
            "- Do not hand-edit generated sections; add durable project notes under Manual Notes.",
            "",
        ]
    )
    return lines


def _render_generated(repo_root: Path) -> str:
    lines: list[str] = [
        GENERATED_START,
        "## Generated Context",
        "",
        "Generated deterministically from local project files.",
        "",
    ]
    for section in (
        _project_identity(repo_root),
        _package_scripts(repo_root),
        _workflow_commands(),
        _host_adapters(repo_root),
        _important_specs(repo_root),
        _local_constraints(repo_root),
    ):
        lines.extend(section)
    lines.append(GENERATED_END)
    return "\n".join(lines).rstrip() + "\n"


def _extract_manual_notes(existing: str) -> str:
    marker = f"\n{MANUAL_HEADING}"
    index = existing.find(marker)
    if index >= 0:
        manual = existing[index + 1 :].rstrip()
        if manual:
            return manual + "\n"
    if existing.startswith(MANUAL_HEADING):
        return existing.rstrip() + "\n"
    return f"{MANUAL_HEADING}\n\n- Add project-specific notes here.\n"


def render_project_context(repo_root: Path, existing: str = "") -> str:
    manual_notes = _extract_manual_notes(existing)
    return (
        "# Project Context\n\n"
        f"{_render_generated(repo_root)}\n"
        f"{manual_notes}"
    )


def refresh_project_context(repo_root: Path) -> Path:
    path = repo_root / DIR_WORKFLOW / PROJECT_CONTEXT_FILE
    existing = _read_text(path)
    path.write_text(render_project_context(repo_root, existing), encoding="utf-8")
    return path


def cmd_refresh(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    path = refresh_project_context(repo_root)
    print(f"refreshed {_display(path, repo_root)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate cowork-flow project context")
    subparsers = parser.add_subparsers(dest="command")

    refresh = subparsers.add_parser("refresh", help="Refresh .cowork-flow/project-context.md")
    refresh.set_defaults(func=cmd_refresh)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args(["refresh"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
