#!/usr/bin/env python3
"""Direct lifecycle fact checks.

These checks intentionally avoid a dynamic gate registry or natural-language
spec validators. The workflow kernel only blocks on facts it can decide from
task metadata and the current git snapshot.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from services.lifecycle_policy import LifecycleExecutionPolicy
from services.task_context import (
    normalize_context_file_scope_entry,
    read_context_jsonl_entries,
)


PROTECTED_WORKFLOW_PATTERNS = (
    r"(^|/)\.cowork-flow/spec/",
    r"(^|/)\.cowork-flow/workflow\.md$",
    r"(^|/)AGENTS\.md$",
    r"(^|/)CLAUDE\.md$",
)


@dataclass(frozen=True)
class LifecycleCheckIssue:
    """Machine-readable lifecycle check issue with stable message compatibility."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class LifecycleCheckResult:
    """Result of direct lifecycle fact checks."""

    stage: str
    blockers: tuple[str, ...] = ()
    issues: tuple[LifecycleCheckIssue, ...] = ()
    spec_check: dict | None = None

    def __post_init__(self) -> None:
        if self.issues and not self.blockers:
            object.__setattr__(
                self,
                "blockers",
                tuple(issue.message for issue in self.issues),
            )

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def exit_code(self) -> int:
        return 1 if self.blocked else 0


class LifecycleCheckRunner:
    """Run direct lifecycle fact checks for one repository."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def review(
        self,
        task_dir: Path,
        *,
        allow_spec_file_modifications: bool | None = None,
        execution_policy: LifecycleExecutionPolicy | None = None,
    ) -> LifecycleCheckResult:
        return LifecycleCheckResult(
            stage="review",
            issues=tuple(
                _review_completion_issues(
                    self.repo_root,
                    task_dir,
                    allow_spec_file_modifications=_policy_allows_spec_changes(
                        execution_policy,
                        allow_spec_file_modifications,
                    ),
                ),
            ),
        )

    def complete(
        self,
        task_dir: Path,
        *,
        allow_spec_file_modifications: bool | None = None,
        execution_policy: LifecycleExecutionPolicy | None = None,
    ) -> LifecycleCheckResult:
        spec_report = _spec_check_report(self.repo_root)
        spec_issues = _spec_check_completion_issues(
            spec_report,
            allow_unchecked_specs=_policy_allows_unchecked(
                execution_policy,
            ),
        )
        return LifecycleCheckResult(
            stage="complete",
            issues=tuple(
                list(_review_completion_issues(
                    self.repo_root,
                    task_dir,
                    allow_spec_file_modifications=_policy_allows_spec_changes(
                        execution_policy,
                        allow_spec_file_modifications,
                    ),
                ))
                + list(spec_issues)
            ),
            spec_check=spec_report,
        )


def _policy_allows_spec_changes(
    execution_policy: LifecycleExecutionPolicy | None,
    allow_spec_file_modifications: bool | None,
) -> bool:
    if execution_policy is not None:
        return execution_policy.allow_spec_file_modifications
    return bool(allow_spec_file_modifications)


def _policy_allows_unchecked(
    execution_policy: LifecycleExecutionPolicy | None,
) -> bool:
    return bool(execution_policy is not None and execution_policy.allow_unchecked_specs)


def _spec_check_report(repo_root: Path) -> dict | None:
    """Run the lifecycle-phase spec checks. A structural failure degrades to
    an unchecked report — never to a silently passing gate."""
    try:
        from services.spec_check import run_checks
    except Exception:  # pragma: no cover - import surface must stay lazy
        return {"schemaVersion": 1, "phase": "lifecycle", "results": [],
                "parseErrors": [], "summary": {"pass": 0, "violation": 0,
                "unchecked": 1, "executorError": 1}}
    try:
        return run_checks(repo_root, phase="lifecycle")
    except Exception as error:  # fail closed: unchecked, not pass
        return {"schemaVersion": 1, "phase": "lifecycle", "results": [],
                "parseErrors": [], "summary": {"pass": 0, "violation": 0,
                "unchecked": 1, "executorError": 1, "error": str(error)}}


def _spec_check_completion_issues(
    spec_report: dict | None,
    *,
    allow_unchecked_specs: bool,
) -> list[LifecycleCheckIssue]:
    if not spec_report:
        return []
    summary = spec_report.get("summary") or {}
    issues: list[LifecycleCheckIssue] = []
    violation = int(summary.get("violation") or 0)
    unchecked = int(summary.get("unchecked") or 0)
    if violation:
        first_lines = []
        for item in spec_report.get("results") or []:
            if item.get("status") == "violation":
                detail = item.get("firstViolationLine") or item.get("reason") or ""
                first_lines.append(f"{item.get('spec')}: {detail}")
        issues.append(
            LifecycleCheckIssue(
                code="SPEC-CHECK-VIOLATION",
                message=(
                    "spec checks report "
                    f"{violation} violation(s): {'; '.join(first_lines[:3])}"
                ),
            )
        )
    if unchecked and not allow_unchecked_specs:
        issues.append(
            LifecycleCheckIssue(
                code="SPEC-CHECK-UNCHECKED",
                message=(
                    f"spec checks report {unchecked} unchecked command(s) "
                    "(missing/timeout); rerun spec-check, or pass "
                    "--allow-unchecked to complete with the exemption recorded"
                ),
            )
        )
    return issues



def _baseline_changed_paths(
    repo_root: Path, task_dir: Path
) -> tuple[list[str], bool]:
    """Review change set: baseline..HEAD diff merged with the working-tree
    status (task start records meta.baselineCommit once). A missing baseline
    or failed diff degrades to status-only — the pre-baseline behavior."""
    baseline = None
    try:
        task_data = json.loads(
            (task_dir / "task.json").read_text(encoding="utf-8")
        )
        meta = task_data.get("meta") or {}
        value = meta.get("baselineCommit")
        baseline = value if isinstance(value, str) and value else None
    except (OSError, json.JSONDecodeError):
        pass
    from infra.git_snapshot import collect_changed_paths_since

    return collect_changed_paths_since(repo_root, baseline)


def _review_completion_issues(
    repo_root: Path,
    task_dir: Path,
    *,
    allow_spec_file_modifications: bool,
) -> list[LifecycleCheckIssue]:
    changed_files, _degraded = _baseline_changed_paths(repo_root, task_dir)
    issues: list[LifecycleCheckIssue] = []
    if not allow_spec_file_modifications:
        issues.extend(_protected_workflow_file_issues(changed_files))
    issues.extend(
        _allowed_file_scope_issues(
            task_dir,
            changed_files,
            repo_root=repo_root,
        )
    )
    return issues


def _protected_workflow_file_issues(changed_files: list[str]) -> list[LifecycleCheckIssue]:
    issues: list[LifecycleCheckIssue] = []
    for file_path in changed_files:
        normalized = _normalize_git_path(file_path)
        if any(re.search(pattern, normalized) for pattern in PROTECTED_WORKFLOW_PATTERNS):
            issues.append(
                LifecycleCheckIssue(
                    code="protected_workflow_file",
                    path=normalized,
                    message=(
                        "Protected workflow/spec file changed outside main session: "
                        f"{normalized}"
                    ),
                )
            )
    return issues


def _allowed_file_scope_issues(
    task_dir: Path,
    changed_files: list[str],
    *,
    repo_root: Path | None = None,
) -> list[LifecycleCheckIssue]:
    implement_jsonl = task_dir / "implement.jsonl"
    if not implement_jsonl.exists():
        return [
            LifecycleCheckIssue(
                code="missing_implement_jsonl_file_scope",
                path="implement.jsonl",
                message=(
                    "implement.jsonl is missing; file-scope review cannot "
                    "run (remove it and every unlisted edit becomes a free "
                    "pass at review)"
                ),
            )
        ]

    allowed_files, scope_issues = _load_allowed_context_files(
        implement_jsonl,
        repo_root=repo_root,
    )
    if scope_issues:
        return scope_issues

    issues: list[LifecycleCheckIssue] = []
    for file_path in changed_files:
        normalized = _normalize_git_path(file_path)
        if _is_runtime_metadata_path(normalized):
            continue
        if normalized not in allowed_files:
            issues.append(
                LifecycleCheckIssue(
                    code="unlisted_changed_file",
                    path=normalized,
                    message=f"Modified file not listed in implement.jsonl: {normalized}",
                )
            )
    return issues


def _allowed_file_scope_blockers(task_dir: Path, changed_files: list[str]) -> list[str]:
    return [issue.message for issue in _allowed_file_scope_issues(task_dir, changed_files)]


def _is_runtime_metadata_path(file_path: str) -> bool:
    return file_path.startswith(
        (
            ".cowork-flow/.runtime/",
            ".cowork-flow/logs/",
            ".cowork-flow/tasks/",
        )
    )


def _context_issue(code: str, message: str) -> LifecycleCheckIssue:
    return LifecycleCheckIssue(code=code, message=message)


def _load_allowed_context_files(
    implement_jsonl: Path,
    *,
    repo_root: Path | None = None,
) -> tuple[set[str], list[LifecycleCheckIssue]]:
    allowed_files: set[str] = set()
    issues: list[LifecycleCheckIssue] = []
    repo_root = Path(repo_root) if repo_root is not None else _repo_root_from_task_dir(
        implement_jsonl.parent
    )
    parsed = read_context_jsonl_entries(implement_jsonl)
    for issue in parsed.issues:
        if issue.code == "read_error":
            issues.append(
                _context_issue(
                    "implement_jsonl_read_error",
                    issue.message,
                )
            )
            continue
        if issue.code == "invalid_json":
            issues.append(
                _context_issue(
                    "invalid_implement_jsonl_json",
                    f"Invalid implement.jsonl JSON at line {issue.line}",
                )
            )
            continue
        issues.append(_context_issue(issue.code, issue.message))

    for context_entry in parsed.entries:
        entry = context_entry.data
        if not isinstance(entry, dict):
            issues.append(
                _context_issue(
                    "invalid_implement_jsonl_entry",
                    (
                        "Invalid implement.jsonl entry at line "
                        f"{context_entry.line}: expected object"
                    ),
                )
            )
            continue
        normalized, error = normalize_context_file_scope_entry(repo_root, entry)
        if error is not None:
            issues.append(
                _context_issue(
                    "invalid_implement_jsonl_file_scope",
                    (
                        "Invalid implement.jsonl file scope at line "
                        f"{context_entry.line}: {error}"
                    ),
                )
            )
            continue
        if normalized is not None:
            allowed_files.add(normalized)
    if not allowed_files:
        issues.append(
            _context_issue(
                "empty_implement_jsonl_file_scope",
                "implement.jsonl contains no valid file-scope entries",
            )
        )
    return allowed_files, issues


def _repo_root_from_task_dir(task_dir: Path) -> Path:
    task_dir = Path(task_dir)
    if task_dir.parent.name == "tasks" and task_dir.parent.parent.name == ".cowork-flow":
        return task_dir.parent.parent.parent
    return task_dir.parent


def _normalize_git_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized
