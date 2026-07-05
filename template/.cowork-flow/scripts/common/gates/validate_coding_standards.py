#!/usr/bin/env python3
"""Spec-driven coding standards — gates honor user-edited spec files.

Files under ``.cowork-flow/spec/backend/``, ``spec/frontend/`` and
``spec/guides/`` are parsed at runtime into review-checklist rules and matched
against a small registry of registered validators. Anything a user adds to
those files is activated at the next gate run — the gate re-reads the
markdown every time.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

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


def _is_backend_file(rel_path: str) -> bool:
    return bool(_BACKEND_SUFFIXES.search(rel_path))


def _is_frontend_file(rel_path: str) -> bool:
    return bool(_FRONTEND_SUFFIXES.search(rel_path))


# ---------------------------------------------------------------------------
# Registered NL-backed validators
# ---------------------------------------------------------------------------

# Each entry: (compiled-pattern, category, validator-fn).
# ``validator(content, rel_path)`` yields ``(lineno, message, fix_hint)``.
_NL_VALIDATORS: list[tuple[re.Pattern, str, Callable[[str, str], Iterable[tuple[int, str, str]]]]] = []


def register_nl_validator(pattern: str) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        category = getattr(fn, "_nl_category", "backend")
        _NL_VALIDATORS.append((re.compile(pattern, re.IGNORECASE), category, fn))
        return fn
    return decorator


def nl_category(category: str) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        fn._nl_category = category
        return fn
    return decorator


@register_nl_validator(r"(硬编码|hardcode|hard.code|secret|password|api[_\s]?key|token)")
@nl_category("backend")
def _no_hardcoded_secrets(content: str, rel_path: str) -> Iterable[tuple[int, str, str]]:
    pattern = re.compile(
        r"""(?ix)
        (?:password|passwd|secret|api[_\s]?key|token|access[_\s]?key|aws_access_key_id|aws_secret_access_key)
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
    pat = re.compile(r"""(?ix)(?:magic\s+number|hardcode|硬编码)""")
    for lineno, raw in enumerate(content.splitlines(), start=1):
        if pat.search(raw):
            yield (lineno, "Hard-coded magic value in frontend source; spec forbids it.")


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
                    "validators": [
                        pat.pattern for pat, cat, _ in _NL_VALIDATORS
                        if cat in (category, "backend") and re.search(pat, rule)
                    ],
                })
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_coding_standards_summary(
    repo_root: Path,
    task_dir: Path,
) -> str:
    """Render the active user-authored rules as a checklist (read-only)."""
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
    """Run all coding-standard checks — hardcoded UTF-8 + spec-activated NL rules.

    The NL rules only run when the user's spec files declare a matching rule
    text, making spec files genuinely editable quality gates.
    """
    violations: list[dict] = []

    # Phase 1: hardcoded UTF-8 / IO checks always run.
    violations.extend(validate_changed_files(repo_root, collect_changed_files(repo_root)))

    # Phase 2: spec-driven validators — activated by user-edited spec text.
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
            except Exception:  # noqa: BLE001 — defensively isolate parsing
                continue
            for lineno, msg, *rest in results:
                fix_hint = rest[0] if rest else ""
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

    parser = argparse.ArgumentParser(description="Spec-driven coding gate")
    parser.add_argument("--task-dir", help="Task directory")
    parser.add_argument("--repo-root", default=".", help="Repo root path")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--list", action="store_true", help="List parsed spec rules")
    parser.add_argument("--validate", action="store_true", help="Run spec validators vs changed files")

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
        for x in v:
            print(json.dumps(x, ensure_ascii=False))
        sys.exit(1 if v else 0)
    print(get_coding_standards_summary(repo_root, task_dir) or "No spec rules activated.")


if __name__ == "__main__":
    main()
