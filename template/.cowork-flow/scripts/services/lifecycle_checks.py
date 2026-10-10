#!/usr/bin/env python3
"""Direct lifecycle fact checks.

These checks intentionally avoid a dynamic gate registry or natural-language
spec validators. The workflow kernel only blocks on facts it can decide from
task metadata and the current git snapshot.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from infra.git_snapshot import collect_changed_paths_since
from services.fact_view import (
    parse_decision_anchor,
    spec_pointer_files,
    task_baseline,
    task_data,
)
from services.lifecycle_policy import LifecycleExecutionPolicy
from services.review_receipt import (
    REVIEW_FILE,
    read_review_receipts,
    receipt_binding_issue,
)
from services.task_context import (
    normalize_context_file_scope_entry,
    read_context_jsonl_entries,
)
from services.task_gate_profiles import GATE_PROFILE_STRICT, resolve_gate_profile


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
    evidence_exemption: dict | None = None
    spec_exemption: dict | None = None

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
        allow_unchecked_specs: bool | None = None,
        allow_missing_evidence: bool | None = None,
        execution_policy: LifecycleExecutionPolicy | None = None,
    ) -> LifecycleCheckResult:
        spec_report = _spec_check_report(self.repo_root)
        allow_unchecked = (
            bool(allow_unchecked_specs)
            if allow_unchecked_specs is not None
            else _policy_allows_unchecked(execution_policy)
        )
        spec_issues = _spec_check_completion_issues(
            spec_report,
            allow_unchecked_specs=allow_unchecked,
        )
        ac_issues, evidence_exemption = _ac_evidence_completion_facts(
            task_dir,
            allow_missing_evidence=(
                bool(allow_missing_evidence)
                if allow_missing_evidence is not None
                else _policy_allows_missing_evidence(execution_policy)
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
                + list(_review_receipt_completion_issues(
                    self.repo_root,
                    task_dir,
                ))
                + list(spec_issues)
                + list(ac_issues)
            ),
            spec_check=spec_report,
            evidence_exemption=evidence_exemption,
            spec_exemption=_spec_check_exemption(
                spec_report,
                allow_unchecked_specs=allow_unchecked,
            ),
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


def _policy_allows_missing_evidence(
    execution_policy: LifecycleExecutionPolicy | None,
) -> bool:
    return bool(
        execution_policy is not None
        and execution_policy.allow_missing_evidence
    )


def _ac_evidence_completion_facts(
    task_dir: Path,
    *,
    allow_missing_evidence: bool,
) -> tuple[list[LifecycleCheckIssue], dict | None]:
    """Completion gate over acceptance-criteria evidence.

    The gate only decides existence facts: which AC ids the decision anchor
    declares, which are checked, and which carry at least one evidence
    record. Tasks without AC rows are exempt (compatibility path); an
    unreadable evidence module degrades the same way instead of blocking
    every legacy task. Returns the issues plus the recorded exemption
    (missing ids) when --allow-missing-evidence absorbed the gap."""
    try:
        from services.ac_evidence import (
            evidence_coverage,
            load_acceptance_criteria,
            read_evidence,
        )
    except Exception:  # pragma: no cover - broken runtime copy degrades
        return [], None
    acceptance = load_acceptance_criteria(task_dir)
    if not acceptance:
        return [], None
    coverage = evidence_coverage(acceptance, read_evidence(task_dir))
    unchecked = [item["id"] for item in acceptance if not item["checked"]]
    unproven = [
        ac_id for ac_id in coverage["missing"] if ac_id not in unchecked
    ]
    issues: list[LifecycleCheckIssue] = []
    if unchecked:
        issues.append(
            LifecycleCheckIssue(
                code="LIFECYCLE-AC-001",
                message=(
                    f"decision-anchor has {len(unchecked)} unchecked "
                    "acceptance criterion(ies): "
                    f"{', '.join(unchecked[:5])}; finish them and tick the "
                    "checkbox, or record evidence in evidence.jsonl"
                ),
            )
        )
    exemption: dict | None = None
    if unproven:
        if allow_missing_evidence:
            exemption = {"missing": unproven}
        else:
            issues.append(
                LifecycleCheckIssue(
                    code="LIFECYCLE-AC-002",
                    message=(
                        f"{len(unproven)} acceptance criterion(ies) lack "
                        "evidence records: "
                        f"{', '.join(unproven[:5])}; append "
                        "{ac, kind: test|command|manual, ref, note?, "
                        "recordedAt, by} records to evidence.jsonl, or pass "
                        "--allow-missing-evidence to record the exemption"
                    ),
                )
            )
    return issues, exemption


def _spec_check_report(repo_root: Path) -> dict | None:
    """Run the lifecycle-phase spec checks. A structural failure degrades to
    an unchecked report — never to a silently passing gate."""
    try:
        from services.spec_check import run_checks
    except Exception:  # pragma: no cover - import surface must stay lazy
        return {"schemaVersion": 1, "phase": "lifecycle", "results": [],
                "parseErrors": [], "summary": {"pass": 0, "violation": 0,
                "unchecked": 1, "executorError": 1,
                "classification": "executor-failure"}}
    try:
        return run_checks(repo_root, phase="lifecycle")
    except Exception as error:  # fail closed: unchecked, not pass
        return {"schemaVersion": 1, "phase": "lifecycle", "results": [],
                "parseErrors": [], "summary": {"pass": 0, "violation": 0,
                "unchecked": 1, "executorError": 1, "error": str(error),
                "classification": "executor-failure"}}


def _spec_check_exemption(
    spec_report: dict | None,
    *,
    allow_unchecked_specs: bool,
) -> dict | None:
    """The exemption this completion applied, or None.

    Single source for both the persisted telemetry and the delivery output:
    a waived gate that is recorded but never shown reads as a clean pass.
    An executor failure is never exemptible, so it never yields one.
    """
    if not spec_report or not allow_unchecked_specs:
        return None
    summary = spec_report.get("summary") or {}
    if int(summary.get("executorError") or 0):
        return None
    unchecked = int(summary.get("unchecked") or 0)
    return {"unchecked": unchecked} if unchecked else None


def _spec_check_parse_error_issue(parse_errors: list) -> LifecycleCheckIssue | None:
    """The blocking fact for declarations the parser could not read."""
    if not parse_errors:
        return None
    details = []
    for item in parse_errors:
        if isinstance(item, dict):
            spec = item.get("spec") or "?"
            error = item.get("error") or "unknown parse error"
            details.append(f"{spec}: {error}")
    suffix = "; ".join(details[:3])
    return LifecycleCheckIssue(
        code="SPEC-CHECK-PARSE-ERROR",
        message=(
            f"spec checks report {len(parse_errors)} parse error(s)"
            + (f": {suffix}" if suffix else "")
        ),
    )


def _spec_check_executor_issue(summary: dict) -> LifecycleCheckIssue | None:
    """The blocking fact for a spec-check executor that never ran.

    Not waivable: --allow-unchecked exempts a command that could not run, not
    an executor that is broken. The `unchecked: 1` in a degraded report is a
    placeholder for "no verdict", so it never becomes a finding of its own.
    """
    if not int(summary.get("executorError") or 0):
        return None
    return LifecycleCheckIssue(
        code="SPEC-CHECK-EXECUTOR-ERROR",
        message=(
            "spec-check executor failed; the declared checks did not run, so "
            "this is not an exemption-eligible unchecked result — fix the "
            "spec-check executor and rerun"
        ),
    )


def _spec_check_completion_issues(
    spec_report: dict | None,
    *,
    allow_unchecked_specs: bool,
) -> list[LifecycleCheckIssue]:
    if not spec_report:
        return []
    summary = spec_report.get("summary") or {}
    issues: list[LifecycleCheckIssue] = []
    parse_error_issue = _spec_check_parse_error_issue(
        spec_report.get("parseErrors") or []
    )
    if parse_error_issue is not None:
        issues.append(parse_error_issue)
    executor_issue = _spec_check_executor_issue(summary)
    if executor_issue is not None:
        issues.append(executor_issue)
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
    if unchecked and executor_issue is None and not allow_unchecked_specs:
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



def task_changed_paths(repo_root: Path, task_dir: Path) -> tuple[list[str], bool]:
    """Review change set for one task: baseline..HEAD merged with the
    working tree, plus whether the snapshot degraded to status-only."""
    return collect_changed_paths_since(repo_root, task_baseline(task_dir))


def compute_change_fingerprint(repo_root: Path, task_dir: Path) -> str:
    """Hash of everything a review result is a judgment about.

    Covers the changed files' content, the anchor's goal and AC text, the
    bound plan's content, the dev type, and the applicable spec pointers, so
    a change to code, scope, specs, plan, goal, or AC wording invalidates an
    older receipt. Runtime metadata is excluded for the same reason the
    scope gate excludes it: dispatching the reviewer writes context files
    under `.cowork-flow/.runtime/`, and counting those would make every
    receipt stale the moment it is recorded.
    """
    repo_root = Path(repo_root).resolve()
    task_dir = Path(task_dir).resolve()
    changed, _degraded = task_changed_paths(repo_root, task_dir)
    paths = {
        path: _content_digest(repo_root, path)
        for path in sorted(
            {
                normalized
                for normalized in (_normalize_git_path(item) for item in changed)
                if normalized and not _is_runtime_metadata_path(normalized)
            }
        )
    }

    anchor_text = ""
    try:
        anchor_text = (task_dir / "decision-anchor.md").read_text(encoding="utf-8")
    except OSError:
        anchor_text = ""
    anchor = parse_decision_anchor(anchor_text) if anchor_text else {}
    acceptance = anchor.get("acceptanceCriteria") or []
    anchor_facts = {
        "goal": anchor.get("goal") or "",
        "acceptance": [
            item.get("text") or "" for item in acceptance if isinstance(item, dict)
        ],
    }

    task = task_data(task_dir)
    meta = task.get("meta")
    plan_file = meta.get("planFile") if isinstance(meta, dict) else None
    plan_digest = ""
    if isinstance(plan_file, str) and plan_file.strip():
        try:
            plan_digest = hashlib.sha256(
                (repo_root / plan_file.strip()).read_bytes()
            ).hexdigest()[:16]
        except OSError:
            plan_digest = "missing"

    payload = json.dumps(
        {
            "paths": paths,
            "anchor": anchor_facts,
            "plan": plan_digest,
            # The dev type selects the applicable spec and skill reading
            # list, so switching it changes what the review was a judgment
            # about even when the repo ships no spec files for it.
            "devType": task.get("dev_type"),
            "specs": sorted(spec_pointer_files(task_dir)),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _content_digest(repo_root: Path, relative: str) -> str:
    """Content digest of one changed path.

    Hashing content, not just the path set, is what makes a receipt stale
    when an already-changed file is edited again — a path-only fingerprint
    would keep passing while the reviewed code kept moving."""
    try:
        return hashlib.sha256((repo_root / relative).read_bytes()).hexdigest()[:16]
    except OSError:
        return "absent"


def _review_receipt_completion_issues(
    repo_root: Path,
    task_dir: Path,
) -> list[LifecycleCheckIssue]:
    """A strict task cannot complete without a passing review of the
    current change set.

    Legacy tasks keep the historical path, where review receipts are
    advisory. The latest receipt decides: a later `fail` is not masked by
    an earlier `pass`, while a retry that passes supersedes an older fail.
    """
    if resolve_gate_profile(task_data(task_dir)) != GATE_PROFILE_STRICT:
        return []
    receipts = read_review_receipts(task_dir)
    if not receipts:
        return [
            LifecycleCheckIssue(
                code="LIFECYCLE-REVIEW-001",
                message=(
                    "task has no independent review receipt; dispatch a "
                    "cowork-check agent and record one with "
                    "`subagent check-review` before completing"
                ),
            )
        ]
    latest = receipts[-1]
    if latest.get("result") != "pass":
        return [
            LifecycleCheckIssue(
                code="LIFECYCLE-REVIEW-002",
                message=(
                    f"the latest of {len(receipts)} review receipt(s) did not "
                    "pass; re-run the review and record a passing receipt"
                ),
            )
        ]
    current = compute_change_fingerprint(repo_root, task_dir)
    if latest.get("changedFingerprint") != current:
        return [
            LifecycleCheckIssue(
                code="LIFECYCLE-REVIEW-003",
                message=(
                    "review receipt is stale: the change set, plan, goal, "
                    "acceptance text, or applicable specs changed after it "
                    "was recorded; re-run cowork-check"
                ),
            )
        ]
    binding_reason = receipt_binding_issue(repo_root, task_dir, latest)
    if binding_reason:
        return [
            LifecycleCheckIssue(
                code="LIFECYCLE-REVIEW-004",
                message=(
                    "the latest review receipt is not backed by a runtime "
                    f"binding: {binding_reason}; dispatch a cowork-check agent "
                    "and record the receipt with `subagent check-review`"
                ),
            )
        ]
    return []


def _review_completion_issues(
    repo_root: Path,
    task_dir: Path,
    *,
    allow_spec_file_modifications: bool,
) -> list[LifecycleCheckIssue]:
    changed_files, degraded = task_changed_paths(repo_root, task_dir)
    issues: list[LifecycleCheckIssue] = []
    if degraded and task_baseline(task_dir):
        issues.append(
            LifecycleCheckIssue(
                code="GIT-SNAPSHOT-DEGRADED",
                message=(
                    "Git snapshot degraded; cannot verify the complete file "
                    "scope because the baseline diff is unavailable"
                ),
            )
        )
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
