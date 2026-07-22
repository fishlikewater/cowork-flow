#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight YAML read/write utilities for cowork-flow.

Handles the subset of YAML that cowork-flow actually uses:
- Flat ``key: value`` metadata files (change.yaml)
- Section-based config files (config.yaml, adapter.yaml)

Zero external dependencies — uses only stdlib.
"""

from __future__ import annotations

from pathlib import Path


def parse_scalar(value: str) -> object:
    """Coerce a YAML-like scalar string to Python type.

    Handles: null/true/false, integer digits, plain strings.
    """
    if value == "null":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdecimal():
        return int(value)
    return value


def format_scalar(value: object) -> str:
    """Inverse of parse_scalar — format a Python value for a YAML file."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def read_flat_metadata(path: Path) -> dict[str, object]:
    """Read a flat ``key: value`` YAML file (e.g. change.yaml).

    Returns an empty dict on missing file or parse error.
    Lines starting with ``#`` or lacking ``:`` are skipped.
    """
    data: dict[str, object] = {}
    if not path.is_file():
        return data

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return data

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value.strip())
    return data


def write_flat_metadata(path: Path, data: dict[str, object]) -> None:
    """Write a flat ``key: value`` YAML file."""
    lines = [f"{key}: {format_scalar(value)}\n" for key, value in data.items()]
    path.write_text("".join(lines), encoding="utf-8")


def parse_sectioned_yaml(content: str) -> dict[str, object]:
    """Parse a simple YAML document with 2-level sections.

    Top-level keys become sections. Indented keys (2-space) become
    entries of the current section. Supports list values with ``- item`` syntax.
    Handles type coercion via :func:`parse_scalar`.

    Used by ``config.py`` and ``test_host_adapters.py`` for config/adapter files.
    """
    result: dict[str, object] = {}
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
            value = value.strip()
            current_section = None
            current_list_key = None

            if value:
                result[key] = parse_scalar(value)
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
                    current_list.append(stripped[2:].strip())
                continue

            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                if value:
                    section[key] = parse_scalar(value)
                    current_list_key = None
                else:
                    section[key] = []
                    current_list_key = key

    return result


def read_sectioned_yaml(path: Path) -> dict[str, object]:
    """Read a section-based YAML file from disk. Returns {} on error."""
    try:
        return parse_sectioned_yaml(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def parse_quoted_yaml(content: str) -> dict[str, object]:
    """Parse sectioned YAML where values may be quoted (e.g. config.yaml).

    Same structure as :func:`parse_sectioned_yaml` but strips surrounding
    ``"`` / ``'`` quotes and keeps all values as plain strings —
    callers are responsible for their own type coercion.
    """

    def _unquote(value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            return value[1:-1]
        return value

    result: dict[str, object] = {}
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


def read_quoted_yaml(path: Path) -> dict[str, object]:
    """Read a quoted-value YAML file from disk. Returns {} on error."""
    try:
        return parse_quoted_yaml(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
