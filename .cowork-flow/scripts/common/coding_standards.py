#!/usr/bin/env python3
"""Coding standards validators for changed files."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, Sequence

from .git_snapshot import ChangedFile

TEXT_IO_SUFFIXES = {".py", ".ps1", ".js", ".mjs", ".cjs", ".ts", ".tsx"}
EXEMPT_PATH_PREFIXES = (
    "tests/fixtures/coding-standards/",
    "test/fixtures/coding-standards/",
)

NODE_TEXT_IO_PATTERN = re.compile(
    r"\b(readFile|readFileSync|writeFile|writeFileSync)\s*\(",
)
POWERSHELL_TEXT_IO_PATTERN = re.compile(
    r"\b(Get-Content|Set-Content|Out-File)\b",
    re.IGNORECASE,
)


def validate_changed_files(
    repo_root: Path,
    changed_files: Sequence[ChangedFile],
) -> list[dict]:
    """Validate coding standards for changed files."""
    violations: list[dict] = []
    for changed_file in changed_files:
        rel_path = changed_file.path
        if _is_exempt_path(rel_path):
            continue

        file_path = Path(repo_root) / rel_path
        if not file_path.is_file() or file_path.suffix.lower() not in TEXT_IO_SUFFIXES:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            violations.append(
                _violation(
                    "CS-UTF8-READ-001",
                    rel_path,
                    "Coding standards: changed text file must be valid UTF-8",
                    "Rewrite the file as UTF-8 without relying on the system default encoding.",
                )
            )
            continue
        except OSError:
            continue

        suffix = file_path.suffix.lower()
        if suffix == ".py":
            violations.extend(_validate_python_text_io(rel_path, content))
        elif suffix == ".ps1":
            violations.extend(_validate_powershell_text_io(rel_path, content))
        elif suffix in {".js", ".mjs", ".cjs", ".ts", ".tsx"}:
            violations.extend(_validate_node_text_io(rel_path, content))

    return violations


def _validate_python_text_io(rel_path: str, content: str) -> list[dict]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function_name = _call_name(node)
        if function_name in {"open", "read_text", "write_text"}:
            if _is_binary_python_call(node, function_name):
                continue
            if not _has_utf8_encoding(node):
                violations.append(
                    _violation(
                        "CS-UTF8-PY-001",
                        rel_path,
                        "Coding standards: Python text IO must pass encoding=\"utf-8\"",
                        "Add encoding=\"utf-8\" to open(), Path.open(), read_text(), or write_text().",
                        line=getattr(node, "lineno", None),
                    )
                )

    return violations


def _validate_node_text_io(rel_path: str, content: str) -> list[dict]:
    violations: list[dict] = []
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if not NODE_TEXT_IO_PATTERN.search(line):
            continue

        segment = "\n".join(lines[index : min(index + 5, len(lines))]).lower()
        if "utf8" in segment or "utf-8" in segment:
            continue

        violations.append(
            _violation(
                "CS-UTF8-NODE-001",
                rel_path,
                "Coding standards: Node file IO must specify utf8 encoding",
                "Pass 'utf8' or { encoding: 'utf8' } to readFile/writeFile calls.",
                line=index + 1,
            )
        )

    return violations


def _validate_powershell_text_io(rel_path: str, content: str) -> list[dict]:
    violations: list[dict] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if POWERSHELL_TEXT_IO_PATTERN.search(line) and "-encoding" not in line.lower():
            violations.append(
                _violation(
                    "CS-UTF8-PS-001",
                    rel_path,
                    "Coding standards: PowerShell text IO must specify -Encoding UTF8",
                    "Add -Encoding UTF8 to Get-Content, Set-Content, or Out-File.",
                    line=line_number,
                )
            )

    return violations


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _is_binary_python_call(node: ast.Call, function_name: str) -> bool:
    mode_values: list[str] = []
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode_values.extend(_literal_strings([keyword.value]))

    positional_mode_index = 1 if function_name == "open" else 0
    if len(node.args) > positional_mode_index:
        mode_values.extend(_literal_strings([node.args[positional_mode_index]]))

    return any("b" in value for value in mode_values)


def _has_utf8_encoding(node: ast.Call) -> bool:
    for keyword in node.keywords:
        if keyword.arg != "encoding":
            continue
        values = _literal_strings([keyword.value])
        return bool(values) and all(_is_utf8(value) for value in values)
    return False


def _literal_strings(nodes: Iterable[ast.AST]) -> list[str]:
    values: list[str] = []
    for node in nodes:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value.lower())
    return values


def _is_utf8(value: str) -> bool:
    return value.replace("_", "-").lower() in {"utf-8", "utf8"}


def _is_exempt_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)


def _violation(
    rule_id: str,
    file_path: str,
    message: str,
    fix_hint: str,
    *,
    line: int | None = None,
) -> dict:
    violation = {
        "rule_id": rule_id,
        "type": "coding_standard",
        "severity": "block",
        "passed": False,
        "message": message,
        "file": file_path,
        "fix_hint": fix_hint,
    }
    if line is not None:
        violation["line"] = line
    return violation
