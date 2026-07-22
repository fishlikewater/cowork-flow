#!/usr/bin/env python3
"""
cowork-flow configuration reader.

Reads settings from .cowork-flow/config.yaml with sensible defaults.
"""

from __future__ import annotations

from pathlib import Path

from .paths import DIR_WORKFLOW, get_repo_root
from .yaml_utils import parse_quoted_yaml


# Defaults
DEFAULT_SESSION_COMMIT_MESSAGE = "chore: record journal"
DEFAULT_MAX_JOURNAL_LINES = 2000
DEFAULT_CODEX_DISPATCH_MODE = "sub-agent"
DEFAULT_ENTRY_LEGACY_TEXT_FALLBACK = False
DEFAULT_PARTY_MODE_V2_MIN_AGENTS = 3
DEFAULT_PARTY_MODE_V2_MAX_AGENTS = 5
DEFAULT_PARTY_MODE_V2_MAX_ROUNDS = 5
DEFAULT_PARTY_MODE_V2_MAX_REBUTTAL_TARGETS_PER_AGENT = 2
DEFAULT_PARTY_MODE_V2_MAX_DRIFT_WARNINGS = 2
DEFAULT_PARTY_MODE_V2_FRESH_CONTEXT_PER_ROUND = True
DEFAULT_PARTY_MODE_V2_REQUIRE_CURRENT_ROUND_ONLY = True

CONFIG_FILE = "config.yaml"


def _get_config_path(repo_root: Path | None = None) -> Path:
    """Get path to config.yaml."""
    root = repo_root or get_repo_root()
    return root / DIR_WORKFLOW / CONFIG_FILE


def _load_config(repo_root: Path | None = None) -> dict:
    """Load and parse config.yaml. Returns empty dict on any error."""
    config_file = _get_config_path(repo_root)
    try:
        content = config_file.read_text(encoding="utf-8")
        return parse_quoted_yaml(content)
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


def get_codex_dispatch_mode(repo_root: Path | None = None) -> str:
    """Get the Codex dispatch mode used by workflow-state hooks."""
    config = _load_config(repo_root)
    codex = config.get("codex")
    if not isinstance(codex, dict):
        return DEFAULT_CODEX_DISPATCH_MODE
    mode = codex.get("dispatch_mode")
    if mode in {"sub-agent", "inline"}:
        return str(mode)
    return DEFAULT_CODEX_DISPATCH_MODE


def _get_section(config: dict, section_name: str) -> dict:
    section = config.get(section_name)
    if isinstance(section, dict):
        return section
    return {}


def _get_int(
    section: dict, key: str, default: int, *, minimum: int | None = None
) -> int:
    value = section.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _get_bool(section: dict, key: str, default: bool) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def get_entry_legacy_text_fallback_enabled(repo_root: Path | None = None) -> bool:
    """Get whether the legacy text entry fallback is enabled."""
    config = _load_config(repo_root)
    entry = _get_section(config, "entry")
    legacy = entry.get("legacy_text_fallback")
    if not isinstance(legacy, dict):
        return DEFAULT_ENTRY_LEGACY_TEXT_FALLBACK
    return _get_bool(
        legacy,
        "enabled",
        DEFAULT_ENTRY_LEGACY_TEXT_FALLBACK,
    )


def get_party_mode_v2_config(repo_root: Path | None = None) -> dict[str, int | bool]:
    """Get Party Mode V2 runtime-board defaults."""
    config = _load_config(repo_root)
    section = _get_section(config, "party_mode_v2")
    min_agents = _get_int(
        section,
        "min_agents",
        DEFAULT_PARTY_MODE_V2_MIN_AGENTS,
        minimum=3,
    )
    max_agents = _get_int(
        section,
        "max_agents",
        DEFAULT_PARTY_MODE_V2_MAX_AGENTS,
        minimum=min_agents,
    )
    return {
        "min_agents": min_agents,
        "max_agents": max_agents,
        "max_rounds": _get_int(
            section,
            "max_rounds",
            DEFAULT_PARTY_MODE_V2_MAX_ROUNDS,
            minimum=1,
        ),
        "max_rebuttal_targets_per_agent": _get_int(
            section,
            "max_rebuttal_targets_per_agent",
            DEFAULT_PARTY_MODE_V2_MAX_REBUTTAL_TARGETS_PER_AGENT,
            minimum=1,
        ),
        "max_drift_warnings": _get_int(
            section,
            "max_drift_warnings",
            DEFAULT_PARTY_MODE_V2_MAX_DRIFT_WARNINGS,
            minimum=0,
        ),
        "fresh_context_per_round": _get_bool(
            section,
            "fresh_context_per_round",
            DEFAULT_PARTY_MODE_V2_FRESH_CONTEXT_PER_ROUND,
        ),
        "require_current_round_only": _get_bool(
            section,
            "require_current_round_only",
            DEFAULT_PARTY_MODE_V2_REQUIRE_CURRENT_ROUND_ONLY,
        ),
    }


def get_party_mode_v2_min_agents(repo_root: Path | None = None) -> int:
    return int(get_party_mode_v2_config(repo_root)["min_agents"])


def get_party_mode_v2_max_agents(repo_root: Path | None = None) -> int:
    return int(get_party_mode_v2_config(repo_root)["max_agents"])


def get_party_mode_v2_max_rounds(repo_root: Path | None = None) -> int:
    return int(get_party_mode_v2_config(repo_root)["max_rounds"])
