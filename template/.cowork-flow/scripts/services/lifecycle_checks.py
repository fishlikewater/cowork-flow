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
from services.decision_anchor_schema import parse_decision_anchor
from services.fact_view import (
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
from services.task_gate_profiles import (
    GATE_PROFILE_STRICT,
    is_light_task,
    resolve_gate_profile,
)


PROTECTED_WORKFLOW_PATTERNS = (
    r"(^|/)\.cowork-flow/spec/",
    r"(^|/)\.cowork-flow/workflow\.md$",
    r"(^|/)AGENTS\.md$",
    r"(^|/)CLAUDE\.md$",
)

# A recorded exemption names what it waived: the flag that allowed it, the
# actor who applied it, and the concrete items.
EVIDENCE_EXEMPTION_FLAG = "--allow-missing-evidence"


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
    evidence_exemption: dict | None = None

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
        allow_missing_evidence: bool | None = None,
        execution_policy: LifecycleExecutionPolicy | None = None,
    ) -> LifecycleCheckResult:
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
                + list(ac_issues)
            ),
            evidence_exemption=evidence_exemption,
        )


def _policy_allows_spec_changes(
    execution_policy: LifecycleExecutionPolicy | None,
    allow_spec_file_modifications: bool | None,
) -> bool:
    if execution_policy is not None:
        return execution_policy.allow_spec_file_modifications
    return bool(allow_spec_file_modifications)


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
    record. A legacy task without AC rows is exempt (compatibility path), and
    an unreadable evidence module degrades the same way for it. A strict task
    gets neither exemption: it was required to declare AC rows at start, so an
    empty section at completion means the anchor was rewritten or cannot be
    read, and a broken runtime copy is a fact to fix rather than to skip. A
    light task keeps the AC-row requirement and the module check for the same
    reason — it only waives the evidence side. Returns the issues plus the
    recorded exemption (missing ids) when --allow-missing-evidence absorbed
    the gap."""
    task = task_data(task_dir)
    strict = resolve_gate_profile(task) == GATE_PROFILE_STRICT
    light = is_light_task(task)
    try:
        from services.ac_evidence import (
            evidence_coverage,
            load_acceptance_criteria,
            read_evidence,
        )
    except Exception as error:  # a broken runtime copy must not pass a gate
        if not strict:
            return [], None
        return [
            LifecycleCheckIssue(
                code="LIFECYCLE-AC-004",
                message=(
                    "the acceptance-evidence module is unavailable, so the "
                    f"strict acceptance gate cannot run: {error}; fix the "
                    "runtime install and rerun"
                ),
            )
        ], None
    acceptance = load_acceptance_criteria(task_dir)
    if not acceptance:
        if not strict:
            return [], None
        return [
            LifecycleCheckIssue(
                code="LIFECYCLE-AC-003",
                message=(
                    "strict task declares no acceptance criterion at "
                    "completion; the anchor was required to carry at least one "
                    "`- [ ] AC-xxx: ...` row at start, so either the anchor "
                    "was rewritten, the task was created without one, or the "
                    "anchor is unreadable (check its encoding)"
                ),
            )
        ], None
    if light:
        # The light profile waives the evidence side, not the acceptance-row
        # requirement checked above.
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
            exemption = {
                "missing": unproven,
                "flag": EVIDENCE_EXEMPTION_FLAG,
            }
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


def _actor_text(actor: object) -> str:
    """The recorded actor, or `null` — never a stand-in identity."""
    return "null" if actor is None else str(actor)


def exemption_report_lines(meta: dict | None) -> list[str]:
    """The recorded exemptions rendered once, for every surface that shows them.

    Completion and archive output both print this, so a waived gate cannot be
    described one way when it is recorded and another way when it is read back.
    Each line is plain text; the caller adds colour and picks the stream.
    """
    meta = meta if isinstance(meta, dict) else {}
    lines: list[str] = []
    evidence_exempt = meta.get("evidenceExempt")
    if isinstance(evidence_exempt, dict):
        missing = evidence_exempt.get("missing") or []
        lines.append(
            f"Exempted: {len(missing)} acceptance criterion(ies) without "
            f"evidence via {evidence_exempt.get('flag')} "
            "(recorded in task.json meta.evidenceExempt, "
            f"by {_actor_text(evidence_exempt.get('by'))})"
        )
        for ac_id in missing:
            lines.append(f"  - {ac_id}")
    return lines


def exemption_meta_payloads(
    check_result: object,
    *,
    executor: str | None,
) -> dict[str, dict]:
    """The task.json meta payloads for the exemptions one completion applied.

    Each gate states what it waived — its own flag and its own items — and this
    adds the one fact the gates cannot know: who applied it. Both the persisted
    record and the printed lines come from this single payload, so "recorded"
    and "shown" cannot drift apart. The actor is whatever the caller resolved;
    when it resolved nothing the actor is None rather than a stand-in identity
    such as the creator or assignee.
    """
    payloads: dict[str, dict] = {}
    evidence_exemption = getattr(check_result, "evidence_exemption", None)
    if evidence_exemption:
        payloads["evidenceExempt"] = {"by": executor, **evidence_exemption}
    return payloads


def task_changed_paths(repo_root: Path, task_dir: Path) -> tuple[list[str], bool]:
    """Review change set for one task: baseline..HEAD merged with the
    working tree, plus whether the snapshot degraded to status-only."""
    return collect_changed_paths_since(repo_root, task_baseline(task_dir))


def compute_change_fingerprint(repo_root: Path, task_dir: Path) -> str:
    """Hash of everything a review result is a judgment about.

    Covers the changed files' content, the anchor's goal and AC text, the
    bound plan's content, the dev type, the referenced spec files' content,
    and the declared scope index, so a change to code, scope, specs, plan,
    goal, or AC wording invalidates an older receipt. Runtime metadata is
    excluded for the same reason the scope gate excludes it: dispatching the
    reviewer writes context files under `.cowork-flow/.runtime/`, and counting
    those would make every receipt stale the moment it is recorded.

    Spec bodies and the scope index are digested explicitly rather than left
    to the change set: `.cowork-flow/**` is gitignored, so a rewritten
    requirement or a widened scope would otherwise be invisible.
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
            # Names alone would miss a rewritten requirement; a pointer whose
            # file is gone still counts as a changed reading list.
            "specs": {
                pointer: _content_digest(repo_root, pointer)
                for pointer in sorted(spec_pointer_files(task_dir))
            },
            # implement.jsonl lives under .cowork-flow/tasks/**, which the
            # change set excludes, so the declared scope needs its own entry.
            "scope": _file_digest(task_dir / "implement.jsonl"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _file_digest(path: Path) -> str:
    """Content digest of one file, or "absent" when it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except OSError:
        return "absent"


def _content_digest(repo_root: Path, relative: str) -> str:
    """Content digest of one changed path.

    Hashing content, not just the path set, is what makes a receipt stale
    when an already-changed file is edited again — a path-only fingerprint
    would keep passing while the reviewed code kept moving."""
    return _file_digest(Path(repo_root) / relative)


def _review_receipt_completion_issues(
    repo_root: Path,
    task_dir: Path,
) -> list[LifecycleCheckIssue]:
    """A strict task cannot complete without a passing review of the
    current change set.

    Legacy tasks keep the historical path, where review receipts are
    advisory, and so do light tasks, which opted out at creation. The latest
    receipt decides: a later `fail` is not masked by an earlier `pass`, while
    a retry that passes supersedes an older fail.
    """
    task = task_data(task_dir)
    if resolve_gate_profile(task) != GATE_PROFILE_STRICT or is_light_task(task):
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
