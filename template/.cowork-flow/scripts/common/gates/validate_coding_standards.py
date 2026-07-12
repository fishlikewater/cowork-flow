#!/usr/bin/env python3
"""Coding-standard gates — context-injection model.

Under Approach A, rules authored under ``.cowork-flow/spec/backend/*.md`` and
``spec/frontend/*.md`` are machine-parsed into checklist items, then surfaced to
the LLM via ``get_coding_standards_summary`` (already wired into the check/
review gates). The LLM is trusted to verify its own code against these items.

Only machine-decidable checks run here as hard blocks:

* Phase 1 — UTF-8 / IO-encoding (``validate_changed_files``).
* ``validate_complexity_signals`` — oversize Python functions (warn).

A separate ``collect_machine_checks`` helper is exposed for callers that want
additional regex-style warnings (hardcoded secrets, debug prints, silent
excepts, trailing comments...) WITHOUT hard-blocking the workflow. These are
emitted at severity=advisory so they can be rendered for the LLM without being a
wall the user must satisfy.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Sequence

from common.gates.coding_standards import validate_changed_files
from common.git.git_snapshot import collect_changed_files, collect_changed_paths

# Source files our spec validators inspect.
_EXTENSIONS = {
    ".py", ".pyi",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".rb", ".cs", ".kt", ".php",
    ".yaml", ".yml", ".json", ".toml",
}

_BACKEND_SUFFIXES = re.compile(r"\.(py|java|go|rs|rb|cs|kt|php)$")
_FRONTEND_SUFFIXES = re.compile(r"\.(tsx|jsx|vue|svelte|ts|js|mjs|cjs|css|scss)$")
_SECRET_RE = re.compile(
    r"""(?ix)
    (?:password|passwd|secret|api[_\s]?key|token|access[_\s]?key)
    \s*[:=]\s*["'][^"'}{)($]{3,}["']
    """
)
_SILENT_EXCEPT_RE = re.compile(r"^\s*except\b\s*.*:\s*(#.*)?$")
_BARE_PRINT_RE = re.compile(r"(?<!\w)print\s*\(")
_CONSOLE_RE = re.compile(r"\bconsole\.(log|info|debug)\s*\(")
_JS_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}


def _is_backend_file(rel_path: str) -> bool:
    return bool(_BACKEND_SUFFIXES.search(rel_path))


def _is_frontend_file(rel_path: str) -> bool:
    return bool(_FRONTEND_SUFFIXES.search(rel_path))


# ---------------------------------------------------------------------------
# Spec parser
# ---------------------------------------------------------------------------

_RULE_PATTERNS = [
    re.compile(r"(?i)(?:^|\s)(?:must\s+not|should\s+not|do\s+not|never|avoid)\s+(.+)$"),
    re.compile(r"(?:^|\s)(?:禁止|不得|不能|不应|避免|不要|不可|不许)\s*(.*)$"),
    re.compile(r"(?i)(?:^|\s)(?:must|should|shall|always|应当|应该|需要)\s+(.+)$"),
]


def _rule_text(line: str) -> str | None:
    line = line.strip().lstrip("-* ").strip()
    if not line or line.startswith("#"):
        return None
    for pat in _RULE_PATTERNS:
        m = pat.search(line)
        if m:
            text = m.group(m.lastindex).strip(" .。")
            if len(text) > 3:
                return text
    return None


def load_spec_rules(
    repo_root,
    categories: tuple[str, ...] = ("backend", "frontend"),
) -> list[dict]:
    """Return every natural-language rule declared under ``spec/<category>/``.

    Re-reads markdown on every call, so user edits take effect without restart.
    The returned rule shape is the current runtime checklist contract:
    category, source, line, and text.
    """
    out: list[dict] = []
    repo_root = Path(repo_root)
    for category in categories:
        spec_dir = repo_root / ".cowork-flow" / "spec" / category
        if not spec_dir.is_dir():
            continue
        for md in sorted(spec_dir.glob("*.md")):
            if md.name == "index.md":
                continue
            text = md.read_text(encoding="utf-8")
            for lineno, raw in enumerate(text.splitlines(), start=1):
                rule = _rule_text(raw)
                if rule is None:
                    continue
                out.append({
                    "category": category,
                    "source": f".cowork-flow/spec/{category}/{md.name}",
                    "line": lineno,
                    "text": rule,
                })
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_coding_standards_summary(
    repo_root: Path,
    task_dir: Path,
) -> str:
    """Render the active user-authored rules as a review checklist (read-only).

    Calls whose changed paths cover neither backend nor frontend files return
    an empty string — there is nothing actionable for the LLM to review.
    """
    changed = collect_changed_paths(repo_root)
    if not changed:
        return ""

    backend = [p for p in changed if _is_backend_file(p)]
    frontend = [p for p in changed if _is_frontend_file(p)]
    if not backend and not frontend:
        return ""

    out: list[str] = []
    if backend:
        rules = load_spec_rules(repo_root, ("backend",))
        if rules:
            out.append("=== Backend spec rules — LLM review checklist ===")
            for r in rules:
                out.append(f"- [{r['source']}:{r['line']}] {r['text']}")
    if frontend:
        rules = load_spec_rules(repo_root, ("frontend",))
        if rules:
            out.append("=== Frontend spec rules — LLM review checklist ===")
            for r in rules:
                out.append(f"- [{r['source']}:{r['line']}] {r['text']}")
    return "\n".join(out)


def validate_coding_standards(
    repo_root: Path,
    task_dir: Path | None = None,
) -> list[dict]:
    """Run hard machine-checkable coding-standard gates.

    Approach A keeps only the UTF-8 / IO-encoding check here. All natural
    language rules authored in the spec tree are surfaced to the LLM via the
    checklist in ``get_coding_standards_summary``; they do not block the
    workflow from this function. Optional advisory warnings live in
    ``collect_machine_checks``.
    """
    return list(validate_changed_files(repo_root, collect_changed_files(repo_root)))


def collect_machine_checks(
    repo_root: Path,
    task_dir: Path | None = None,
) -> list[dict]:
    """Emit regex-style advisory signals (severity=advisory).

    The LLM decides how to act on them; the workflow never blocks on a hit.
    Kept separate from ``validate_coding_standards`` so callers can choose
    whether to render them in a gate log, inject them into context, or ignore.
    """
    violations: list[dict] = []
    for changed_file in _changed_machine_check_files(repo_root):
        violations.extend(_machine_check_violations_for_file(repo_root, changed_file))
    return violations


def _changed_machine_check_files(repo_root: Path) -> Sequence[object]:
    try:
        return collect_changed_files(repo_root)
    except Exception:  # noqa: BLE001 — defensively isolate git errors
        return ()


def _machine_check_violations_for_file(repo_root: Path, changed_file: object) -> list[dict]:
    file_path = repo_root / changed_file.path
    if not file_path.is_file():
        return []
    suffix = file_path.suffix.lower()
    if suffix not in _EXTENSIONS:
        return []
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return _machine_check_violations_for_lines(changed_file.path, suffix, content.splitlines())


def _machine_check_violations_for_lines(
    rel_path: str,
    suffix: str,
    lines: list[str],
) -> list[dict]:
    violations: list[dict] = []
    for lineno, raw in enumerate(lines, start=1):
        violations.extend(_machine_check_violations_for_line(rel_path, suffix, lines, lineno, raw))
    return violations


def _machine_check_violations_for_line(
    rel_path: str,
    suffix: str,
    lines: list[str],
    lineno: int,
    raw: str,
) -> list[dict]:
    violations: list[dict] = []
    if _looks_like_hardcoded_secret(raw):
        violations.append(_adv(
            "MACHINE-HARDCODED-SECRET-001",
            "Possible hard-coded secret in source",
            rel_path, lineno,
            "Read the value from configuration or environment variables.",
        ))
    if suffix == ".py" and _BARE_PRINT_RE.search(raw):
        violations.append(_adv(
            "MACHINE-DEBUG-PRINT-001",
            "Debug print on changed line",
            rel_path, lineno,
            "Use a structured logger or remove the print.",
        ))
    if suffix in _JS_SUFFIXES and _CONSOLE_RE.search(raw):
        violations.append(_adv(
            "MACHINE-CONSOLE-LOG-001",
            "console.{log,info,debug} on changed line",
            rel_path, lineno,
            "Use the project logger or remove the call.",
        ))
    if _is_silent_python_except(suffix, lines, lineno, raw):
        violations.append(_adv(
            "MACHINE-SILENT-EXCEPT-001",
            "Empty exception handler silently swallows errors",
            rel_path, lineno,
            "Log or re-raise the exception, or narrow the except types.",
        ))
    return violations


def _looks_like_hardcoded_secret(raw: str) -> bool:
    # Low-signal heuristic: only flag if the line also has an assignment / call.
    return (
        _SECRET_RE.search(raw) is not None
        and "process.env" not in raw
        and "os.environ" not in raw
    )


def _is_silent_python_except(
    suffix: str,
    lines: list[str],
    lineno: int,
    raw: str,
) -> bool:
    return (
        suffix == ".py"
        and _SILENT_EXCEPT_RE.match(raw) is not None
        and lineno < len(lines)
        and lines[lineno].strip() in {"pass", "...", ""}
    )


def _adv(
    rule_id: str,
    message: str,
    file_path: str,
    line: int,
    fix_hint: str,
) -> dict:
    return {
        "rule_id": rule_id,
        "type": "machine_check",
        "severity": "advisory",
        "passed": False,
        "message": message,
        "file": file_path,
        "line": line,
        "fix_hint": fix_hint,
    }


def validate_complexity_signals(repo_root: Path, task_dir: Path | None) -> list[dict]:
    """Detect over-complexity signals in modified files (warn-level)."""
    import ast
    import subprocess
    warnings: list[dict] = []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~"],
            cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", timeout=10,
        )
        changed_files = [f for f in result.stdout.splitlines() if f]
    except (subprocess.SubprocessError, OSError):
        return warnings

    for rel_path in changed_files:
        if not rel_path.endswith(".py"):
            continue
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", None) or node.lineno
                func_lines = end - node.lineno
                if func_lines > 50:
                    warnings.append({
                        "rule_id": "COMPLEX-FUNC-001",
                        "type": "coding_standard",
                        "severity": "warn",
                        "passed": False,
                        "message": (
                            f"{rel_path}:{node.name} function is "
                            f"{func_lines} lines (< 50 recommended)"
                        ),
                        "file": str(rel_path),
                        "fix_hint": (
                            "Split into multiple named functions "
                            "by responsibility."
                        ),
                    })
    return warnings


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Coding-standard gate")
    parser.add_argument("--task-dir", help="Task directory")
    parser.add_argument("--repo-root", default=".", help="Repo root path")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--list", action="store_true", help="List parsed spec rules")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--machine-checks", action="store_true",
                        help="Also emit advisory machine-check warnings")

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_dir = Path(args.task_dir).resolve() if args.task_dir else repo_root

    if args.list:
        for r in load_spec_rules(repo_root):
            print(json.dumps(r, ensure_ascii=False))
        return
    if args.summarize:
        print(get_coding_standards_summary(repo_root, task_dir) or "No spec rules activated.")
        return
    if args.validate:
        v = validate_coding_standards(repo_root, task_dir)
        if args.machine_checks:
            v.extend(collect_machine_checks(repo_root, task_dir))
        for x in v:
            print(json.dumps(x, ensure_ascii=False))
        sys.exit(1 if any(x["severity"] == "block" for x in v) else 0)
    print(get_coding_standards_summary(repo_root, task_dir) or "No spec rules activated.")


if __name__ == "__main__":
    main()
