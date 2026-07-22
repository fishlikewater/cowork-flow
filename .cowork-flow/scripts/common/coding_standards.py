#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coding standard scanners for quality gate evidence.

Provides:
    scan_bom          - detect BOM bytes in text files
    scan_encoding     - detect Python text IO missing explicit UTF-8
    scan_whitespace   - run git diff --check
    scan_standards    - batch scan returning evidence dict
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

# -- BOM bytes ----------------------------------------------------------------


BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"


def _has_bom(path: Path) -> bool:
    """Check if file starts with a BOM."""
    try:
        with path.open("rb") as f:
            head = f.read(4)
    except OSError:
        return False
    return head.startswith((BOM_UTF8, BOM_UTF16_LE, BOM_UTF16_BE))


_TEXT_EXTENSIONS = frozenset({
    ".py", ".md", ".yaml", ".yml", ".toml", ".json", ".jsonl",
    ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".svg",
    ".txt", ".sh", ".cmd", ".cfg", ".ini", ".env",
})


def scan_bom(scan_paths: list[Path]) -> dict:
    """Scan text files for BOM bytes.

    Returns {'ok': bool, 'violations': [str]}.
    """
    violations: list[str] = []
    for root in scan_paths:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix in _TEXT_EXTENSIONS and _has_bom(root):
                violations.append(f"{root}: starts with BOM")
        elif root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if "__pycache__" in str(path) or "node_modules" in str(path):
                    continue
                if path.suffix in _TEXT_EXTENSIONS and _has_bom(path):
                    violations.append(f"{path}: starts with BOM")
    return {"ok": len(violations) == 0, "violations": violations}


# -- Python text IO encoding --------------------------------------------------


def scan_encoding(scan_paths: list[Path]) -> dict:
    """Scan Python + JS/TS files for text IO calls missing explicit UTF-8 encoding.

    Returns {'ok': bool, 'violations': [str]}.
    """
    violations: list[str] = []

    # Python scan
    for root in scan_paths:
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".py":
            _check_encoding(root, violations)
        elif root.is_dir():
            for path in root.rglob("*.py"):
                if not path.is_file():
                    continue
                if "__pycache__" in str(path):
                    continue
                _check_encoding(path, violations)

    # JS/TS scan
    js_result = scan_encoding_js(scan_paths)
    violations.extend(js_result.get("violations", []))

    return {"ok": len(violations) == 0, "violations": violations}


def _check_encoding(path: Path, violations: list[str]) -> None:
    """AST-based scan for text I/O missing explicit UTF-8 encoding.

    Falls back to regex for files with syntax errors.
    """
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return _check_encoding_regex(path, violations)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = _call_func_name(node)
        if func_name not in ("open", "read_text", "write_text"):
            continue

        if _has_utf8_encoding(node):
            continue
        if func_name == "open" and _is_binary_mode(node):
            continue

        violations.append(
            f"{path}:{node.lineno}:"
            f" {func_name}() missing explicit encoding='utf-8'"
        )


def _call_func_name(node: ast.Call) -> str | None:
    """Return the function name of a Call node — e.g. 'open', 'read_text'."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _has_utf8_encoding(node: ast.Call) -> bool:
    """Return True if the call already has an explicit encoding='utf-8' kwarg."""
    return any(
        kw.arg == "encoding"
        and isinstance(kw.value, ast.Constant)
        and str(kw.value.value).lower().replace("-", "") == "utf8"
        for kw in node.keywords
    )


def _is_binary_mode(node: ast.Call) -> bool:
    """Return True for open() calls with a binary mode like 'rb' or 'wb'.

    open(path, mode):   mode is positional arg 1 (top-level function).
    thing.open(mode):   mode is positional arg 0 (method call).
    """
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return "b" in str(kw.value.value)

    is_method = isinstance(node.func, ast.Attribute)
    mode_index = 0 if is_method else 1

    if len(node.args) > mode_index and isinstance(node.args[mode_index], ast.Constant):
        return "b" in str(node.args[mode_index].value)
    return False


# -- Regex fallback (for syntax-error files) ----------------------------------


_TEXT_IO_PATTERN = re.compile(r"\b(open|read_text|write_text)\s*\([^)]*\)")
_EXPLICIT_UTF8_RE = re.compile(r"encoding\s*=\s*[\"']utf-?8[\"']", re.IGNORECASE)


def _check_encoding_regex(path: Path, violations: list[str]) -> None:
    """Regex-based fallback for files that can't be AST-parsed.

    Has a known ceiling: cannot handle nested parentheses in arguments
    (e.g. write_text(json.dumps(...), encoding='utf-8')).  The AST path above
    handles those correctly.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return

    for match in _TEXT_IO_PATTERN.finditer(text):
        call = match.group(0)
        func = match.group(1)
        if func in ("read_text", "write_text"):
            if not _EXPLICIT_UTF8_RE.search(call):
                violations.append(
                    f"{path}:{_line_of(text, match.start())}:"
                    f" {func}() missing explicit encoding='utf-8'"
                )
        elif func == "open":
            modes = re.findall(r"[\"']([rwa][+]?[tb]*|[rwa]\+[tb]*)[\"']", call)
            if modes:
                mode = modes[0].lower()
                if "b" in mode:
                    continue
            if not _EXPLICIT_UTF8_RE.search(call):
                violations.append(
                    f"{path}:{_line_of(text, match.start())}:"
                    f" open() missing explicit encoding='utf-8' in text mode"
                )


def _line_of(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


# -- Whitespace / git diff --check -------------------------------------------


def scan_whitespace(repo_root: Path) -> dict:
    """Run git diff --check and return result.

    Returns {'ok': bool, 'violations': [str]}.
    """
    # Skip if not in a git repository
    if not (repo_root / ".git").exists():
        return {"ok": True, "violations": []}

    try:
        result = subprocess.run(
            ["git", "diff", "--check"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "violations": ["git diff --check failed to run"]}

    violations: list[str] = []
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            if line.strip():
                violations.append(line.strip())
        for line in result.stdout.splitlines():
            if line.strip():
                violations.append(line.strip())
    return {"ok": len(violations) == 0, "violations": violations}


# -- JavaScript / TypeScript text IO encoding ---------------------------------


_JS_NO_ENCODING_RE = re.compile(
    r"\b(readFile(?:Sync)?|writeFile(?:Sync)?)\s*\(([^)]*)\)",
)
_JS_UTF8_ARG_RE = re.compile(
    # encoding as: readFile(path, 'utf8', cb) OR {encoding: 'utf8'} OR {encoding: "utf-8"}
    r"""(?:encoding\s*:\s*[\"']utf-?8[\"']  # {encoding: 'utf8'}
         |,\s*[\"']utf-?8[\"']\s*[,)]        # readFile(path, 'utf8', cb)
        )""",
    re.IGNORECASE | re.VERBOSE,
)


def scan_encoding_js(scan_paths: list[Path]) -> dict:
    """Scan JS/TS files for fs.readFile / fs.writeFile calls missing explicit
    UTF-8 encoding.

    Returns {'ok': bool, 'violations': [str]}.
    """
    violations: list[str] = []
    for root in scan_paths:
        if not root.exists():
            continue
        if root.is_file() and root.suffix in (".js", ".mjs", ".cjs", ".ts", ".tsx"):
            _check_encoding_js(root, violations)
        elif root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if "node_modules" in str(path) or "__pycache__" in str(path):
                    continue
                if path.suffix in (".js", ".mjs", ".cjs", ".ts", ".tsx"):
                    _check_encoding_js(path, violations)
    return {"ok": len(violations) == 0, "violations": violations}


def _check_encoding_js(path: Path, violations: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return

    for match in _JS_NO_ENCODING_RE.finditer(text):
        func = match.group(1)
        args = match.group(2)
        # Skip if encoding is present:
        #   - as options object key: {encoding: 'utf8'}
        #   - as inline string: readFile(path, 'utf8', cb)
        if _JS_UTF8_ARG_RE.search("," + args + ")"):
            continue
        violations.append(
            f"{path}:{_line_of(text, match.start())}:"
            f" {func}() missing explicit encoding='utf-8'"
        )


# -- Batch scan ---------------------------------------------------------------


def scan_standards(task_dir: Path, repo_root: Path | None = None) -> dict:
    """Run all standard scans and return evidence dict.

    Returns a dict suitable for quality.json 'standards' field.
    """
    root = repo_root or Path.cwd()

    # Scan the task directory and repo workflow scripts
    scan_paths = [task_dir]
    workflow_scripts = task_dir.parent.parent / "scripts"  # .cowork-flow/scripts/
    if workflow_scripts.exists():
        scan_paths.append(workflow_scripts)

    # Shallow test scan
    from .test_quality import scan_test_files

    return {
        "encodingScan": scan_encoding(scan_paths),
        "bomScan": scan_bom(scan_paths),
        "whitespaceCheck": scan_whitespace(root),
        "shallowTestScan": scan_test_files(task_dir),
    }
