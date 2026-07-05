#!/usr/bin/env python3
"""Coding standards gate — dynamically loaded from user-editable spec files.

The markdown files under ``.cowork-flow/spec/backend/``, ``spec/frontend/`` and
``spec/guides/`` are **not** dead documentation. They are parsed into
human-readable rules, surfaced as a task checklist, and **enforced** during
review/complete gates. Anything a user adds to those files is honored at the
next gate run — the gate re-reads the markdown every time.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from common.git.git_snapshot import collect_changed_files, collect_changed_paths

from common.gates.coding_standards import validate_changed_files

# Source files our spec validators inspect. Broader than the hardcoded
# TEXT_IO_SUFFIXES set so Python/YAML/TS/JS are all visible to user rules.
_EXTENSIONS = {
    ".py", ".pyi",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".rb", ".cs", ".kt", ".php",
    ".yaml", ".yml", ".json", ".toml",
}


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------

_BACKEND_SUFFIXES = re.compile(r"\.(py|java|go|rs|rb|cs|kt|php)$")
_FRONTEND_SUFFIXES = re.compile(r"\.(tsx|jsx|vue|svelte|ts|js|mjs|cjs|css|scss)$")


def _is_backend_file(rel_path: str) -> bool:
    return bool(_BACKEND_SUFFIXES.search(rel_path))


def _is_frontend_file(rel_path: str) -> bool:
    return bool(_FRONTEND_SUFFIXES.search(rel_path))


# ---------------------------------------------------------------------------
# Spec-driven natural-language rules
# ---------------------------------------------------------------------------

# Pattern → (category, validator) where validator(content, rel_path) -> list[(line, message, fix_hint)].
# Rules live in code because they back natural-language spec text; users do not
# edit Python. To add a new rule, add a bullet to spec/backend or spec/frontend
# matching the pattern AND add an entry here.
_NL_VALIDATORS: list[tuple[str, str, callable]] = []


def register_nl_validator(pattern: str):
    """Decorate a validator that activates when the spec line matches ``pattern``."""

    def decorator(fn) -> callable:
        category = getattr(fn, "_nl_category", "backend")
        _NL_VALIDATORS.append((re.compile(pattern, re.IGNORECASE), category, fn))
        return fn

    return decorator


def nl_category(category: str):
    """Set the spec category (backend / frontend) for a validator."""

    def decorator(fn) -> callable:
        fn._nl_category = category
        return fn

    return decorator


# Built-in validators ----------------------------------------------------------


@register_nl_validator(r"(硬编码|hardcode|hard.code|secret|password|api[_\s]?key|token)")
@nl_category("backend")
def _no_hardcoded_secrets(content: str, rel_path: str) -> list[tuple[int, str, str]]:
    """User rule: '不允许硬编码 secret / 不允许明文 password'."""
    hits: list[tuple[int, str, str]] = []
    pattern = re.compile(
        r"""(?ix)
        (?:password|passwd|secret|api[_\s]?key|token|access[_\s]?key|aws_access_key_id|aws_secret_access_key)
        \s*[:=]\s*["'][^"'"\s$(){}]{3,}["']
        """
    )
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pattern.search(raw) and "process.env" not in raw and "os.environ" not in raw:
            hits.append((
                lineno,
                "Possible hard-coded secret in source; spec forbids it.",
                "Read from configuration or environment variables.",
            ))
    return hits


@register_nl_validator(r"(硬编码|hardcode|明文|magic\s+number)")
@nl_category("frontend")
def _no_magic_values_frontend(content: str, rel_path: str) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    pattern = re.compile(r"""(?ix)(?:magic\s+number|hardcode|硬编码)""")
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pattern.search(raw):
            hits.append((lineno, "Hard-coded magic value in frontend source; spec forbids it."))
    return hits


@register_nl_validator(r"(print\b|console\.(log|info|debug)|日志|logger|logging)")
@nl_category("backend")
def _no_debug_prints(content: str, rel_path: str) -> list[tuple[int, str, str]]:
    """User rule: '不允许 print / 不允许 console.log'."""
    hits: list[tuple[int, str, str]] = []
    if rel_path.endswith(".py"):
        pat = re.compile(r"""(?<!#)\bprint\s*\(""")
    else:
        pat = re.compile(r"""\bconsole\.(log|info|debug)\s*\(""")
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pat.search(raw):
            hits.append((lineno, "Debug print found; spec prefers structured logger."))
    return hits


@register_nl_validator(r"(吞|swallow|静默|except|空\s*except)")
@nl_category("backend")
def _no_silent_except(content: str, rel_path: str) -> list[tuple[int, str, str]]:
    """User rule: '不允许空 except / 不允许吞异常'."""
    if not rel_path.endswith(".py"):
        return []
    hits: list[tuple[int, str, str]] = []
    lines = content.splitlines()
    for lineno, raw in enumerate(lines, start=1):
        if re.match(r"^\s*except\b\s*.*:\s*(#.*)?$", raw):
            nxt = lines[lineno].strip() if lineno < len(lines) else ""
            if nxt in {"pass", "...", ""} or nxt.startswith(("pass ", "...")):
                hits.append((lineno, "Empty exception handler silently swallows errors."))
    return hits


# ---------------------------------------------------------------------------
# Spec parser
# ---------------------------------------------------------------------------

# Supported rule patterns (must match the start of a markdown bullet or line).
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

    The returned dicts are plain JSON so they can be rendered straight onto a
    review checklist diff. Each rule carries its source file and line so the
    reviewer can trace it back.
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
                out.append(
                    {
                        "category": category,
                        "source": f".cowork-flow/spec/{category}/{md.name}",
                        "line": lineno,
                        "text": rule,
                        "validators": [
                            pat.pattern for pat, cat, _ in _NL_VALIDATORS
                            if cat in (category, "backend") and re.search(pat, rule)
                        ],
                    }
                )
    return out


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def get_coding_standards_summary(
    repo_root: Path,
    task_dir: Path,
) -> str:
    """Surface the user-authored rules for the reviewer.

    This is generated content — it NEVER asserts. The actual enforcement
    happens in :func:`validate_coding_standards`.
    """
    paths = collect_changed_paths(repo_root)
    if not paths:
        return ""

    backend = [p for p in paths if _is_backend_file(p)]
    frontend = [p for p in paths if _is_frontend_file(p)]
    if not backend and not frontend:
        return ""

    out: list[str] = []
    if backend:
        rules = load_spec_rules(repo_root, ("backend",))
        if rules:
            out.append("=== Backend spec rules — VALIDATED during check gate ===")
            for r in rules:
                out.append(f"- [{r['source']}:{r['line']}] {r['text']}")
    if frontend:
        rules = load_spec_rules(repo_root, ("frontend",))
        if rules:
            out.append("=== Frontend spec rules — VALIDATED during check gate ===")
            for r in rules:
                out.append(f"- [{r['source']}:{r['line']}] {r['text']}")
    return "\n".join(out)


def validate_coding_standards(
    repo_root: Path,
    task_dir: Path | None = None,
) -> list[dict]:
    """Run all coding-standard checks — both hardcoded and user-authored.

    Hardcoded checks (UTF-8 IO, etc.) always run. Built-in NL validators run
    only when the user has declared a matching rule in their spec files — this
    is what makes spec rules "actually work" once a user edits them.
    """
    violations: list[dict] = []

    # Phase 1: hardcoded validators (UTF-8 IO, etc.)
    violations.extend(validate_changed_files(repo_root, collect_changed_files(repo_root)))

    # Phase 2: spec-backed validators (activated by matching user-declared rules)
    spec_rules = load_spec_rules(repo_root)
    if not spec_rules:
        return violations

    activated: set[str] = set()
    for rule in spec_rules:
        activated.update(rule.get("validators", []))
    if not activated:
        return violations

    for changed_file in collect_changed_files(repo_root):
        file_path = repo_root / changed_file.path
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix not in _EXTENSIONS:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pat, _category, validator in _NL_VALIDATORS:
            if pat.pattern not in activated:
                continue
            try:
                results = validator(content, changed_file.path)
            except Exception:  # noqa: BLE001 — defensively isolate user-file parsing
                continue
            for entry in results:
                lineno, msg = entry[0], entry[1]
                fix_hint = entry[2] if len(entry) > 2 else ""
                violations.append({
                    "rule_id": f"SPEC-{validator.__name__}",
                    "type": "spec_coding_standard",
                    "severity": "block",
                    "passed": False,
                    "message": msg,
                    "file": changed_file.path,
                    "line": lineno,
                    "fix_hint": fix_hint,
                })

    return violations



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Dynamic spec-driven coding gate")
    parser.add_argument("--task-dir", help="Task directory path (optional)")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--summarize", action="store_true", help="Print spec checklist summary")
    parser.add_argument("--list", action="store_true", help="List parsed spec rules for the repo")
    parser.add_argument("--validate", action="store_true", help="Run spec validators against changed files")

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_dir = Path(args.task_dir).resolve() if args.task_dir else None

    if args.list:
        for r in load_spec_rules(repo_root):
            print(json.dumps(r, ensure_ascii=False))
        return

    if args.summarize:
        out = get_coding_standards_summary(repo_root, task_dir or repo_root)
        print(out or "No spec rules activated for current changes.")
        return

    if args.validate:
        violations = validate_coding_standards(repo_root, task_dir)
        for v in violations:
            print(json.dumps(v, ensure_ascii=False))
        sys.exit(1 if violations else 0)

    # default: summary
    out = get_coding_standards_summary(repo_root, task_dir or repo_root)
    print(out or "No spec rules activated for current changes.")


if __name__ == "__main__":
    main()
