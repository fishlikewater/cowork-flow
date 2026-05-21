#!/usr/bin/env python3
"""
cowork-flow configuration reader.

Reads settings from .cowork-flow/config.yaml with sensible defaults.
"""

from __future__ import annotations

from pathlib import Path

from .paths import DIR_WORKFLOW, get_repo_root


# Defaults
DEFAULT_SESSION_COMMIT_MESSAGE = "chore: record journal"
DEFAULT_MAX_JOURNAL_LINES = 2000
DEFAULT_AGENT_TEAM_ENABLED = False

CONFIG_FILE = "config.yaml"


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_simple_yaml(content: str) -> dict:
    result: dict = {}
    current_section: str | None = None
    current_list_key: str | None = None

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        if indent == 0 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = _unquote(value.strip())
            current_section = None
            current_list_key = None

            if value:
                result[key] = value
            else:
                result[key] = {}
                current_section = key
            continue

        if current_section and indent >= 2:
            section = result.setdefault(current_section, {})
            if not isinstance(section, dict):
                continue

            if stripped.startswith("- ") and current_list_key:
                current_list = section.setdefault(current_list_key, [])
                if isinstance(current_list, list):
                    current_list.append(_unquote(stripped[2:].strip()))
                continue

            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = _unquote(value.strip())
                if value:
                    section[key] = value
                    current_list_key = None
                else:
                    section[key] = []
                    current_list_key = key

    return result


def _get_config_path(repo_root: Path | None = None) -> Path:
    """Get path to config.yaml."""
    root = repo_root or get_repo_root()
    return root / DIR_WORKFLOW / CONFIG_FILE


def _load_config(repo_root: Path | None = None) -> dict:
    """Load and parse config.yaml. Returns empty dict on any error."""
    config_file = _get_config_path(repo_root)
    try:
        content = config_file.read_text(encoding="utf-8")
        return _parse_simple_yaml(content)
    except (OSError, IOError):
        return {}


def get_session_commit_message(repo_root: Path | None = None) -> str:
    """Get the commit message for auto-committing session records."""
    config = _load_config(repo_root)
    return config.get("session_commit_message", DEFAULT_SESSION_COMMIT_MESSAGE)


def get_max_journal_lines(repo_root: Path | None = None) -> int:
    """Get the maximum lines per journal file."""
    config = _load_config(repo_root)
    value = config.get("max_journal_lines", DEFAULT_MAX_JOURNAL_LINES)
    try:
        return int(value)
    except (ValueError, TypeError):
        return DEFAULT_MAX_JOURNAL_LINES


def _is_true(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def get_agent_team_enabled(repo_root: Path | None = None) -> bool:
    """Return whether agent-team runtime commands are enabled."""
    config = _load_config(repo_root)
    agent_team = config.get("agent_team")
    if not isinstance(agent_team, dict):
        return DEFAULT_AGENT_TEAM_ENABLED
    return _is_true(agent_team.get("enabled"))


def get_hooks(event: str, repo_root: Path | None = None) -> list[str]:
    """Get hook commands for a lifecycle event.

    Args:
        event: Event name (e.g. "after_create", "after_archive").
        repo_root: Repository root path.

    Returns:
        List of shell commands to execute, empty if none configured.
    """
    config = _load_config(repo_root)
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return []
    commands = hooks.get(event)
    if isinstance(commands, list):
        return [str(c) for c in commands]
    return []
