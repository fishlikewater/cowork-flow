#!/usr/bin/env python3
"""Read .cowork-flow/config.yaml; a missing file yields defaults."""

from __future__ import annotations

import re
from pathlib import Path

from infra.paths import DIR_WORKFLOW, get_repo_root


# Defaults
DEFAULT_CODEX_DISPATCH_MODE = "sub-agent"
DEFAULT_PARTY_MODE_V2_MIN_AGENTS = 3
DEFAULT_PARTY_MODE_V2_MAX_AGENTS = 5
DEFAULT_PARTY_MODE_V2_MAX_ROUNDS = 5
DEFAULT_PARTY_MODE_V2_MAX_REBUTTAL_TARGETS_PER_AGENT = 2
DEFAULT_PARTY_MODE_V2_MAX_DRIFT_WARNINGS = 2
DEFAULT_PARTY_MODE_V2_FRESH_CONTEXT_PER_ROUND = True
DEFAULT_PARTY_MODE_V2_REQUIRE_CURRENT_ROUND_ONLY = True

DEFAULT_LANGUAGE = "zh-CN"
SUPPORTED_LANGUAGES = ("zh-CN", "en-US")
LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_cn": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
    "en_us": "en-US",
}

CONFIG_FILE = "config.yaml"


class UnsupportedLanguageError(ValueError):
    """The config declares a language the runtime does not support."""


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _strip_comment(value: str) -> str:
    """Cuts an inline comment; `#` inside quotes or glued to a word stays.

    Only a quote at the start of the scalar opens a quoted region, so a bare
    apostrophe in `Sam's project  # note` does not swallow the comment.
    """
    quote = ""
    escaped = False
    for idx, char in enumerate(value):
        if escaped:
            escaped = False
        elif quote == '"' and char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = ""
        elif idx == 0 and char in ("'", '"'):
            quote = char
        elif char == "#" and (idx == 0 or value[idx - 1] in " \t"):
            return value[:idx].rstrip()
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
            value = _unquote(_strip_comment(value.strip()))
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
                    item = _strip_comment(stripped[2:].strip())
                    current_list.append(_unquote(item))
                continue

            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = _unquote(_strip_comment(value.strip()))
                if value:
                    section[key] = value
                    current_list_key = None
                else:
                    section[key] = []
                    current_list_key = key

    return result


def _get_config_path(repo_root: Path | None = None) -> Path:
    root = repo_root or get_repo_root()
    return root / DIR_WORKFLOW / CONFIG_FILE


def _load_config(repo_root: Path | None = None) -> dict:
    """Any read or parse error yields an empty config."""
    config_file = _get_config_path(repo_root)
    try:
        content = config_file.read_text(encoding="utf-8")
        return _parse_simple_yaml(content)
    except (OSError, IOError):
        return {}


def normalize_language(value: object) -> str | None:
    """Canonical language for a supported value, otherwise None."""
    if not isinstance(value, str):
        return None
    return LANGUAGE_ALIASES.get(value.strip().lower())


_LANGUAGE_KEY_RE = re.compile(r"^language\s*:\s*(.*)$")


def _read_language_setting(
    repo_root: Path | None = None,
) -> tuple[str | None, bool, bool]:
    """The explicit top-level language scalar.

    Returns `(raw, present, duplicate)`. Only top-level `language:` lines count.
    Two keys, an empty value, a glued comment, or trailing junk are left for
    `normalize_language` to reject, matching the Node reader.
    """
    config_file = _get_config_path(repo_root)
    try:
        content = config_file.read_text(encoding="utf-8")
    except (OSError, IOError):
        return None, False, False

    entries: list[str] = []
    for raw_line in content.splitlines():
        if raw_line.startswith((" ", "\t")):
            continue
        match = _LANGUAGE_KEY_RE.match(raw_line)
        if match:
            entries.append(match.group(1))
    if not entries:
        return None, False, False
    if len(entries) > 1:
        return None, True, True
    raw = _unquote(_strip_comment(entries[0].strip())).strip()
    return raw, True, False


def get_language(
    repo_root: Path | None = None,
    *,
    strict: bool = False,
) -> str:
    """Task/plan artifact language from the project config.

    A missing file or key yields the default. An explicit unsupported value or
    duplicate `language` keys raises when strict is set; runtime generation uses
    the non-strict form so a config typo cannot block task creation.
    """
    raw, present, duplicate = _read_language_setting(repo_root)
    if not present:
        return DEFAULT_LANGUAGE
    canonical = None if duplicate else normalize_language(raw)
    if canonical is not None:
        return canonical
    if strict:
        detail = (
            "duplicate language keys"
            if duplicate
            else f"unsupported language {raw!r}"
        )
        raise UnsupportedLanguageError(
            detail + "; expected one of: " + ", ".join(SUPPORTED_LANGUAGES)
        )
    return DEFAULT_LANGUAGE



def get_hooks(event: str, repo_root: Path | None = None) -> list[str]:
    """Hook commands declared for one lifecycle event; empty when none."""
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

def _get_int(section: dict, key: str, default: int, *, minimum: int | None = None) -> int:
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
