#!/usr/bin/env python3
"""Advisory review fact report for task-review."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _add_runtime_scripts_path() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".cowork-flow" / "scripts"
        if candidate.is_dir():
            value = str(candidate)
            if value not in sys.path:
                sys.path.insert(0, value)
            return


_add_runtime_scripts_path()

from adapters.review.test_intent import classify_test_content
from infra.git_snapshot import collect_changed_paths
from infra.quality_sources import quality_source_entries
from services.lifecycle_checks import LifecycleCheckRunner
from services.task_context import TaskContextService
from runtime.session_state import is_main_session


PROTECTED_PREFIX = "Protected workflow/spec file changed outside main session: "
UNLISTED_PREFIX = "Modified file not listed in implement.jsonl: "
TEST_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
FUNCTION_LINE_SOFT_LIMIT = 60
CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
    ".rb",
    ".php",
}
FRONTEND_SUFFIXES = {".jsx", ".tsx", ".css", ".scss", ".vue", ".svelte"}
BACKEND_SUFFIXES = {".py", ".go", ".rs", ".java", ".kt", ".rb", ".php"}
JS_SHALLOW_PATTERNS = (
    (re.compile(r"\bassert\s*\(\s*true\s*\)"), "assert(true)"),
    (
        re.compile(r"\bexpect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)"),
        "expect(true).toBe(true)",
    ),
    (re.compile(r"\.toMatchSnapshot\s*\("), "snapshot assertion"),
    (re.compile(r"\btoBeTruthy\s*\("), "truthy assertion"),
)


def _repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".cowork-flow").is_dir():
            return candidate
    for parent in Path(__file__).resolve().parents:
        if (parent / ".cowork-flow").is_dir():
            return parent
    return cwd


def _task_dir(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _read_task_json(task_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _infer_dev_type(task_data: dict[str, Any], changed_files: list[str]) -> str:
    raw = task_data.get("dev_type")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    frontend = any(
        Path(path).suffix in FRONTEND_SUFFIXES or path.startswith(("frontend/", "web/", "app/"))
        for path in changed_files
    )
    backend = any(
        Path(path).suffix in BACKEND_SUFFIXES or "/scripts/" in path
        for path in changed_files
    )
    if frontend and backend:
        return "fullstack"
    if frontend:
        return "frontend"
    if backend:
        return "backend"
    return ""


def _normalized_issue(
    *,
    code: str,
    severity: str,
    path: str,
    message: str,
    source: str,
    **extra: str,
) -> dict[str, str]:
    issue = {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "source": source,
    }
    issue.update(extra)
    return issue


def _lifecycle_issue_fact(issue: Any) -> dict[str, str]:
    return _normalized_issue(
        code=str(getattr(issue, "code", "") or "lifecycle_issue"),
        severity="error",
        path=str(getattr(issue, "path", "") or ""),
        message=str(getattr(issue, "message", "") or ""),
        source="lifecycle",
    )


def _fallback_lifecycle_issue(
    *,
    code: str,
    path: str,
    message: str,
) -> dict[str, str]:
    return _normalized_issue(
        code=code,
        severity="error",
        path=path,
        message=message,
        source="lifecycle",
    )


def _scope_facts(
    repo_root: Path,
    task_dir: Path,
    *,
    allow_spec_file_modifications: bool,
) -> dict[str, Any]:
    scope_facts, _ = _scope_facts_with_issues(
        repo_root,
        task_dir,
        allow_spec_file_modifications=allow_spec_file_modifications,
    )
    return scope_facts


def _scope_facts_with_issues(
    repo_root: Path,
    task_dir: Path,
    *,
    allow_spec_file_modifications: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    result = LifecycleCheckRunner(repo_root).review(
        task_dir,
        allow_spec_file_modifications=allow_spec_file_modifications,
    )
    protected: list[str] = []
    unlisted: list[str] = []
    context_issues: list[str] = []
    normalized_issues: list[dict[str, str]] = []
    issues = tuple(getattr(result, "issues", ()) or ())
    if issues:
        for issue in issues:
            code = str(getattr(issue, "code", "") or "")
            path = getattr(issue, "path", None)
            message = str(getattr(issue, "message", "") or "")
            normalized_issues.append(_lifecycle_issue_fact(issue))
            if code == "protected_workflow_file":
                protected.append(str(path or message.removeprefix(PROTECTED_PREFIX)))
            elif code == "unlisted_changed_file":
                normalized = str(path or message.removeprefix(UNLISTED_PREFIX))
                if normalized not in protected:
                    unlisted.append(normalized)
            else:
                context_issues.append(message)
    else:
        for message in result.blockers:
            if message.startswith(PROTECTED_PREFIX):
                path = message.removeprefix(PROTECTED_PREFIX)
                protected.append(path)
                normalized_issues.append(
                    _fallback_lifecycle_issue(
                        code="protected_workflow_file",
                        path=path,
                        message=message,
                    )
                )
            elif message.startswith(UNLISTED_PREFIX):
                path = message.removeprefix(UNLISTED_PREFIX)
                unlisted.append(path)
                normalized_issues.append(
                    _fallback_lifecycle_issue(
                        code="unlisted_changed_file",
                        path=path,
                        message=message,
                    )
                )
            else:
                context_issues.append(message)
                normalized_issues.append(
                    _fallback_lifecycle_issue(
                        code="lifecycle_context_issue",
                        path="",
                        message=message,
                    )
                )
    return (
        {
            "unlistedChangedFiles": unlisted,
            "protectedWorkflowFiles": protected,
            "contextIssues": context_issues,
            "lifecycleMessages": list(result.blockers),
        },
        normalized_issues,
    )


def _check_context_sources(repo_root: Path, task_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for entry in TaskContextService(repo_root).entries(task_dir, "check"):
        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path.strip():
            continue
        normalized = file_path.strip().replace("\\", "/").removeprefix("./")
        entries.append(
            {
                "file": normalized,
                "reason": str(entry.get("reason") or "Review context entry"),
                "kind": "check_context",
                "exists": (repo_root / normalized).is_file(),
            }
        )
    return entries


def _spec_sources(
    repo_root: Path,
    task_dir: Path,
    *,
    dev_type: str,
    changed_files: list[str],
) -> list[dict[str, Any]]:
    sources = _check_context_sources(repo_root, task_dir)
    for entry in quality_source_entries(repo_root, dev_type, paths=tuple(changed_files)):
        file_path = str(entry["file"])
        sources.append(
            {
                "file": file_path,
                "reason": str(entry.get("reason") or "Quality source"),
                "kind": "quality_source",
                "exists": (repo_root / file_path).is_file(),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        file_path = str(source["file"])
        if file_path in seen:
            continue
        seen.add(file_path)
        deduped.append(source)
    return deduped


def _is_test_file(path: str) -> bool:
    file_name = Path(path).name
    suffix = Path(path).suffix
    if suffix not in TEST_SUFFIXES:
        return False
    return (
        file_name.startswith("test_")
        or file_name.endswith("_test.py")
        or ".test." in file_name
        or ".spec." in file_name
        or path.startswith("tests/")
        or "/tests/" in path
    )


def _is_code_file(path: str) -> bool:
    return Path(path).suffix in CODE_SUFFIXES


def _python_function_lengths(content: str) -> dict[str, dict[str, int]]:
    try:
        tree = ast.parse(content.lstrip("\ufeff"))
    except SyntaxError:
        return {}

    functions: dict[str, dict[str, int]] = {}

    def visit_nodes(nodes: list[ast.stmt], prefix: tuple[str, ...]) -> None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit_nodes(node.body, (*prefix, node.name))
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                name = ".".join((*prefix, node.name))
                functions[name] = {
                    "line": node.lineno,
                    "lines": end_lineno - node.lineno + 1,
                }
                visit_nodes(node.body, (*prefix, node.name))

    visit_nodes(tree.body, ())
    return functions


def _git_baseline_text(repo_root: Path, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _complexity_signals(repo_root: Path, changed_files: list[str]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for raw_path in changed_files:
        normalized = raw_path.replace("\\", "/").removeprefix("./")
        if Path(normalized).suffix != ".py":
            continue
        full_path = repo_root / normalized
        if not full_path.is_file():
            continue
        try:
            current_functions = _python_function_lengths(
                full_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError):
            continue
        baseline_text = _git_baseline_text(repo_root, normalized)
        baseline_functions = (
            _python_function_lengths(baseline_text) if baseline_text is not None else {}
        )
        for function_name, current in sorted(current_functions.items()):
            current_lines = current["lines"]
            if current_lines <= FUNCTION_LINE_SOFT_LIMIT:
                continue
            baseline_lines = baseline_functions.get(function_name, {}).get("lines", 0)
            budget_baseline = (
                baseline_lines if baseline_lines > FUNCTION_LINE_SOFT_LIMIT else 0
            )
            if budget_baseline == 0:
                code = "complexity_new_long_function"
                message = (
                    f"Function {function_name} is {current_lines} lines; "
                    f"soft budget is {FUNCTION_LINE_SOFT_LIMIT} lines."
                )
            elif current_lines > baseline_lines:
                code = "complexity_hotspot_grew"
                message = (
                    f"Function {function_name} grew from {baseline_lines} "
                    f"to {current_lines} lines; split responsibilities or record intent."
                )
            else:
                code = "complexity_existing_hotspot"
                message = (
                    f"Existing hotspot {function_name} remains {current_lines} lines; "
                    "warning only for reviewer awareness."
                )
            signals.append(
                {
                    "code": code,
                    "file": normalized,
                    "function": function_name,
                    "line": str(current["line"]),
                    "baselineLines": str(budget_baseline),
                    "currentLines": str(current_lines),
                    "limitLines": str(FUNCTION_LINE_SOFT_LIMIT),
                    "reason": message,
                }
            )
    return signals


def _complexity_issues(signals: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        _normalized_issue(
            code=signal["code"],
            severity="warning",
            path=signal["file"],
            message=signal["reason"],
            source="complexity",
            function=signal["function"],
            line=signal["line"],
            baselineLines=signal["baselineLines"],
            currentLines=signal["currentLines"],
            limitLines=signal["limitLines"],
        )
        for signal in signals
    ]


def _python_test_names(content: str) -> list[str]:
    try:
        tree = ast.parse(content.lstrip("\ufeff"))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            names.append(node.name)
            continue
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                    names.append(f"{node.name}.{child.name}")
    return names


def _python_shallow_signals(path: str, content: str) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for test_name in _python_test_names(content):
        classification = classify_test_content(content, test_name)
        if classification in {"warn", "block"}:
            signals.append(
                {
                    "file": path,
                    "testName": test_name,
                    "signal": classification,
                    "reason": "test intent helper flagged a shallow or ambiguous assertion",
                }
            )
    return signals


def _text_shallow_signals(path: str, content: str) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for pattern, label in JS_SHALLOW_PATTERNS:
        if pattern.search(content):
            signals.append(
                {
                    "file": path,
                    "testName": "",
                    "signal": "warn",
                    "reason": f"possible shallow test pattern: {label}",
                }
            )
    return signals


def _test_intent_signals(repo_root: Path, changed_files: list[str]) -> dict[str, Any]:
    test_files = [path for path in changed_files if _is_test_file(path)]
    shallow_signals: list[dict[str, str]] = []
    unreadable: list[str] = []
    for path in test_files:
        full_path = repo_root / path
        try:
            content = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable.append(path)
            continue
        if Path(path).suffix == ".py":
            shallow_signals.extend(_python_shallow_signals(path, content))
        else:
            shallow_signals.extend(_text_shallow_signals(path, content))
    return {
        "changedTestFiles": test_files,
        "shallowAssertionSignals": shallow_signals,
        "unreadableTestFiles": unreadable,
    }


def _test_intent_issues(test_signals: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for signal in test_signals["shallowAssertionSignals"]:
        issues.append(
            _normalized_issue(
                code="shallow_assertion_signal",
                severity="warning",
                path=str(signal.get("file") or ""),
                message=str(signal.get("reason") or "shallow test intent signal"),
                source="test-intent",
                testName=str(signal.get("testName") or ""),
                signal=str(signal.get("signal") or ""),
            )
        )
    return issues


def _verification_hints(
    changed_files: list[str],
    test_signals: dict[str, Any],
    complexity_signals: list[dict[str, str]],
) -> list[str]:
    hints: list[str] = []
    code_files = [
        path
        for path in changed_files
        if _is_code_file(path) and not _is_test_file(path)
    ]
    if code_files and not test_signals["changedTestFiles"]:
        hints.append(
            "Code files changed without changed test files; "
            "reviewer should confirm behavior coverage."
        )
    if test_signals["shallowAssertionSignals"]:
        hints.append("Review shallowAssertionSignals before accepting test intent.")
    if complexity_signals:
        hints.append("Review complexity soft-budget warnings before accepting large functions.")
    return hints


def build_report(repo_root: Path, task_dir: Path) -> dict[str, Any]:
    task_data = _read_task_json(task_dir)
    changed_files = collect_changed_paths(repo_root)
    dev_type = _infer_dev_type(task_data, changed_files)
    test_signals = _test_intent_signals(repo_root, changed_files)
    complexity_signals = _complexity_signals(repo_root, changed_files)
    scope_facts, scope_issues = _scope_facts_with_issues(
        repo_root,
        task_dir,
        allow_spec_file_modifications=is_main_session(repo_root),
    )
    return {
        "reportVersion": 1,
        "mode": "advisory",
        "task": {
            "dir": _relative(repo_root, task_dir),
            "state": str(task_data.get("status") or ""),
            "devType": dev_type,
        },
        "changedFiles": changed_files,
        "scopeFacts": scope_facts,
        "normalizedIssues": [
            *scope_issues,
            *_test_intent_issues(test_signals),
            *_complexity_issues(complexity_signals),
        ],
        "specSources": _spec_sources(
            repo_root,
            task_dir,
            dev_type=dev_type,
            changed_files=changed_files,
        ),
        "testIntentSignals": test_signals,
        "complexitySignals": complexity_signals,
        "verificationHints": _verification_hints(
            changed_files,
            test_signals,
            complexity_signals,
        ),
        "notes": [
            "This report is advisory and does not mutate task state.",
            "Do not treat natural-language spec review as a runtime lifecycle gate.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print advisory review facts for task-review.",
    )
    parser.add_argument("task_dir", help="Task directory to inspect.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output. The command currently always prints JSON.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    report = build_report(repo_root, _task_dir(repo_root, args.task_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
