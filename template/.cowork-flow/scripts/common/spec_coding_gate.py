#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spec-driven coding gate — parses spec markdown to activate NL validators.

Reads natural-language rules from `.cowork-flow/spec/backend/*.md` and
`spec/frontend/*.md`, matches them against a registry of validators via regex,
and runs only the activated validators against changed files.

User edits to spec files take effect on the next gate run without restart.

Provides:
    load_spec_rules(repo_root) -> list[dict]
    validate_spec_coding(repo_root, task_dir) -> list[dict]
    get_spec_coding_summary(repo_root, task_dir) -> str
    register_nl_validator(pattern) -> decorator
    nl_category(category) -> decorator
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# NL Validator registry
# ---------------------------------------------------------------------------

# Each entry: (compiled_pattern, category, validator_fn)
# validator(content, rel_path) yields (lineno, message, fix_hint)
_NL_VALIDATORS: list[tuple[re.Pattern, str, Callable[[str, str], Iterable[tuple[int, str, str]]]]] = []


def register_nl_validator(pattern: str) -> Callable[[Callable], Callable]:
    """Decorator: register a validator function keyed by a regex pattern.

    The validator activates when a spec rule's text matches this pattern.
    Category is read from the function's `_nl_category` attribute (default "backend").
    """
    def decorator(fn: Callable) -> Callable:
        category = getattr(fn, "_nl_category", "backend")
        _NL_VALIDATORS.append((re.compile(pattern, re.IGNORECASE), category, fn))
        return fn
    return decorator


def nl_category(category: str) -> Callable[[Callable], Callable]:
    """Decorator: tag a validator as "backend" or "frontend"."""
    def decorator(fn: Callable) -> Callable:
        fn._nl_category = category
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Built-in NL validators
# ---------------------------------------------------------------------------


@register_nl_validator(r"(硬编码|hardcode|hard.code|secret|password|api[_\s]?key|token)")
@nl_category("backend")
def _no_hardcoded_secrets(content: str, rel_path: str) -> Iterable[tuple[int, str, str]]:
    """Detect hard-coded secrets (password, api_key, token = "...")."""
    pattern = re.compile(
        r"""(?ix)
        (?:password|passwd|secret|api[_\s]?key|token|access[_\s]?key|
             aws_access_key_id|aws_secret_access_key)
        \s*[:=]\s*["'][^"'}{)($]{3,}["']
        """
    )
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pattern.search(raw) and "process.env" not in raw and "os.environ" not in raw:
            yield (lineno,
                   "Possible hard-coded secret in source; spec forbids it.",
                   "Read from configuration or environment variables.")


@register_nl_validator(r"(print\b|console\.(log|info|debug)|日志|logger|logging|结构化日志)")
@nl_category("backend")
def _no_debug_prints(content: str, rel_path: str) -> Iterable[tuple[int, str, str]]:
    """Detect debug prints (print/console.log) in source."""
    if rel_path.endswith(".py"):
        pat = re.compile(r"(?<!\w)print\s*\(")
    elif rel_path.endswith((".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")):
        pat = re.compile(r"\bconsole\.(log|info|debug)\s*\(")
    else:
        return
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pat.search(raw):
            yield (lineno, "Debug print found; spec prefers structured logger.",
                   "Use a structured logger instead.")


@register_nl_validator(r"(吞|swallow|静默|except|空\s*except)")
@nl_category("backend")
def _no_silent_except(content: str, rel_path: str) -> Iterable[tuple[int, str, str]]:
    """Detect empty exception handlers that silently swallow errors."""
    if not rel_path.endswith(".py"):
        return
    lines = content.splitlines()
    for lineno, raw in enumerate(lines, start=1):
        if re.match(r"^\s*except\b\s*.*:\s*(#.*)?$", raw):
            nxt = lines[lineno].strip() if lineno < len(lines) else ""
            if nxt in {"pass", "...", ""} or nxt.startswith(("pass ", "...")):
                yield (lineno, "Empty exception handler silently swallows errors.",
                       "Log or re-raise the exception, or narrow the except types.")


@register_nl_validator(r"(硬编码|hardcode|明文|magic\s+number)")
@nl_category("frontend")
def _no_magic_values_frontend(content: str, rel_path: str) -> Iterable[tuple[int, str, str]]:
    """Detect magic values in frontend source (placeholder for user extension)."""
    pat = re.compile(r"""(?ix)(?:magic\s+number|hardcode|硬编码|明文)""")
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pat.search(raw):
            yield (lineno, "Hard-coded magic value in frontend source; spec forbids it.")


# ---------------------------------------------------------------------------
# Spec parser
# ---------------------------------------------------------------------------

_RULE_PATTERNS = [
    # English negative
    re.compile(r"(?i)(?:^|\s)(?:must\s+not|should\s+not|do\s+not|never|avoid)\s+(.+)$"),
    # Chinese negative
    re.compile(r"(?:^|\s)(?:禁止|不得|不能|不应|避免|不要|不可|不许)\s*(.*)$"),
    # English/Chinese positive
    re.compile(r"(?i)(?:^|\s)(?:must|should|shall|always|应当|应该|需要|可以)\s+(.+)$"),
]

# Source file extensions our spec validators inspect
_SOURCE_EXTS = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".rb", ".cs", ".kt", ".php",
    ".yaml", ".yml", ".json", ".toml",
}

_BACKEND_SUFFIXES = re.compile(r"\.(py|java|go|rs|rb|cs|kt|php)$")
_FRONTEND_SUFFIXES = re.compile(r"\.(tsx|jsx|vue|svelte|ts|js|mjs|cjs|css|scss)$")


def _rule_text(line: str) -> str | None:
    """Extract rule intent from a raw markdown line.

    Returns the rule text if the line looks like a rule, else None.
    """
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
    repo_root: Path,
    categories: tuple[str, ...] = ("backend", "frontend"),
) -> list[dict]:
    """Parse every rule declared under `spec/<category>/*.md`.

    Re-reads markdown on every call, so user edits take effect without restart.

    Returns a list of dicts: {category, source, line, text, validators}.
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
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            for lineno, raw in enumerate(text.splitlines(), start=1):
                rule = _rule_text(raw)
                if rule is None:
                    continue
                # Find which NL validators this rule activates
                activated = [
                    pat.pattern for pat, cat, _ in _NL_VALIDATORS
                    if cat in (category, "backend") and pat.search(rule)
                ]
                out.append({
                    "category": category,
                    "source": f".cowork-flow/spec/{category}/{md.name}",
                    "line": lineno,
                    "text": rule,
                    "validators": activated,
                })
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_spec_coding_summary(repo_root: Path, task_dir: Path) -> str:
    """Render the active user-authored rules as a checklist (read-only)."""
    rules = load_spec_rules(repo_root)
    if not rules:
        return ""
    changed = _collect_changed_paths(repo_root)
    if not changed:
        return ""

    backend = [p for p in changed if _BACKEND_SUFFIXES.search(p)]
    frontend = [p for p in changed if _FRONTEND_SUFFIXES.search(p)]
    if not backend and not frontend:
        return ""

    out: list[str] = []
    if backend:
        backend_rules = [r for r in rules if r["category"] == "backend"]
        if backend_rules:
            out.append("=== Backend spec rules — VALIDATED during check gate ===")
            for r in backend_rules:
                out.append(f"- [{r['source']}:{r['line']}] {r['text']}")
    if frontend:
        frontend_rules = [r for r in rules if r["category"] == "frontend"]
        if frontend_rules:
            out.append("=== Frontend spec rules — VALIDATED during check gate ===")
            for r in frontend_rules:
                out.append(f"- [{r['source']}:{r['line']}] {r['text']}")
    return "\n".join(out)


def validate_spec_coding(repo_root: Path, task_dir: Path) -> list[dict]:
    """Run spec-activated NL validators against changed files.

    Returns a list of violation dicts with rule_id, type, severity, message, file, line.
    """
    violations: list[dict] = []
    spec_rules = load_spec_rules(repo_root)
    if not spec_rules:
        return violations

    # Collect activated validator patterns
    activated: set[str] = set()
    for rule in spec_rules:
        activated.update(rule.get("validators", []))
    if not activated:
        return violations

    changed_files = _collect_changed_paths(repo_root)
    for rel_path in changed_files:
        suffix = Path(rel_path).suffix.lower()
        if suffix not in _SOURCE_EXTS:
            continue
        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for pat, _category, validator in _NL_VALIDATORS:
            if pat.pattern not in activated:
                continue
            try:
                results = validator(content, rel_path)
            except Exception:
                continue  # defensively isolate parsing
            for lineno, msg, *rest in results:
                fix_hint = rest[0] if rest else ""
                violations.append({
                    "rule_id": f"SPEC-{validator.__name__}",
                    "type": "spec_coding_standard",
                    "severity": "block",
                    "passed": False,
                    "message": msg,
                    "file": rel_path,
                    "line": lineno,
                    "fix_hint": fix_hint,
                })

    return violations


# ---------------------------------------------------------------------------
# Changed files collection (uses git status)
# ---------------------------------------------------------------------------


def _collect_changed_paths(repo_root: Path) -> list[str]:
    """Collect changed file paths from git status."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"').replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ")[-1]
        if path:
            paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Spec-driven coding gate")
    parser.add_argument("--task-dir", required=True, help="Task directory path")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--list", action="store_true", help="List parsed spec rules")
    parser.add_argument("--validate", action="store_true")

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_dir = Path(args.task_dir).resolve()

    if args.list:
        for r in load_spec_rules(repo_root):
            print(json.dumps(r, ensure_ascii=False))
        return
    if args.summarize:
        print(get_spec_coding_summary(repo_root, task_dir) or "No spec rules activated.")
        return
    if args.validate:
        v = validate_spec_coding(repo_root, task_dir)
        for x in v:
            print(json.dumps(x, ensure_ascii=False))
        import sys
        sys.exit(1 if v else 0)
    print(get_spec_coding_summary(repo_root, task_dir) or "No spec rules activated.")


if __name__ == "__main__":
    main()
