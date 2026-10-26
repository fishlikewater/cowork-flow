#!/usr/bin/env python3
"""Structured cowork-flow distribution and runtime health checks."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _add_runtime_scripts_path() -> None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".cowork-flow" / "scripts"
        if candidate.is_dir():
            value = str(candidate)
            if value not in sys.path:
                sys.path.insert(0, value)
            return


_add_runtime_scripts_path()

from adapters.host.host_manifest import (
    HostManifestError,
    HostPlatform,
    detect_installed_platforms,
    load_host_manifest,
    validate_host_assets,
)
from infra.paths import DIR_WORKFLOW, get_repo_root
from infra.config import UnsupportedLanguageError, get_language
from infra.skill_manifest import SkillManifestError, action_owners, load_skill_manifests
from infra.storage.operation_log import OperationLog
from infra.storage.state_store import DEFAULT_STALE_LOCK_SECONDS, StateStore


def _issue(
    *,
    code: str,
    severity: str,
    path: str,
    message: str,
    command_hint: str = "",
    contract: str,
    **extra: str,
) -> dict[str, str]:
    issue = {
        "code": code,
        "severity": severity,
        "path": path,
        "message": message,
        "commandHint": command_hint,
        "contract": contract,
    }
    issue.update(extra)
    return issue


def _compare_file(
    left: Path,
    right: Path,
    errors: list[str],
    *,
    missing_left: str = "missing template asset",
    missing_right: str = "missing installed asset",
    drift: str = "distribution drift",
) -> None:
    if not left.is_file():
        errors.append(f"{missing_left}: {left}")
        return
    if not right.is_file():
        errors.append(f"{missing_right}: {right}")
        return
    if left.read_bytes() != right.read_bytes():
        errors.append(f"{drift}: {left} != {right}")


def _same_file(left: Path, right: Path, errors: list[str]) -> None:
    _compare_file(left, right, errors)


def _distribution_root(repo_root: Path) -> Path:
    template = repo_root / "template"
    if (
        (template / ".cowork-flow/spec/runtime/host-assets.json").is_file()
        and (template / ".cowork-flow/scripts/kernel/workflow_route.py").is_file()
        and (template / "skills").is_dir()
    ):
        return template
    return repo_root


def _host_errors(repo_root: Path) -> list[str]:
    distribution_root = _distribution_root(repo_root)
    if distribution_root != repo_root:
        return validate_host_assets(distribution_root)
    try:
        platform_ids = detect_installed_platforms(distribution_root)
    except HostManifestError as error:
        return [str(error)]
    if not platform_ids:
        return ["no installed host platform detected"]
    return validate_host_assets(distribution_root, platform_ids=platform_ids)


def _host_issue(error: str) -> dict[str, str]:
    path = ""
    if ":" in error:
        path = error.rsplit(":", 1)[-1].strip()
    lowered = error.lower()
    if "missing command target" in lowered:
        code = "HOST-ASSET-MISSING-COMMAND-TARGET"
    elif "missing command config" in lowered:
        code = "HOST-ASSET-MISSING-COMMAND-CONFIG"
    elif "invalid command config" in lowered:
        code = "HOST-ASSET-INVALID-COMMAND-CONFIG"
    elif "illegal capability" in lowered:
        code = "HOST-ASSET-ILLEGAL-CAPABILITY"
    elif "capability mismatch" in lowered:
        code = "HOST-ASSET-CAPABILITY-MISMATCH"
    elif "adapter host mismatch" in lowered:
        code = "HOST-ASSET-HOST-MISMATCH"
    elif "invalid adapter yaml" in lowered:
        code = "HOST-ASSET-INVALID-ADAPTER"
    else:
        code = "HOST-ASSET-VALIDATION-ERROR"
    return _issue(
        code=code,
        severity="error",
        path=path,
        message=error,
        contract="runtime-health:host-adapters",
    )


def _host_issues(repo_root: Path) -> list[dict[str, str]]:
    return [_host_issue(error) for error in _host_errors(repo_root)]


def _distribution_files(root: Path) -> tuple[Path, ...]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]
    return tuple(sorted(files))


def _source_checkout_protected_path(relative: Path) -> bool:
    value = relative.as_posix()
    if value in {".cowork-flow/config.yaml", ".cowork-flow/.developer"}:
        return True
    return value.startswith(".cowork-flow/tasks/") or value.startswith(
        ".cowork-flow/plans/"
    ) or value.startswith(".cowork-flow/.runtime/")


def _source_checkout_live_files(template: Path) -> tuple[Path, ...]:
    runtime_root = template / ".cowork-flow"
    return tuple(
        source
        for source in _distribution_files(runtime_root)
        if not _source_checkout_protected_path(source.relative_to(template))
    )


def check_distribution(repo_root: Path) -> list[str]:
    errors: list[str] = []
    template = repo_root / "template"
    if _distribution_root(repo_root) == repo_root:
        return errors
    for source in _source_checkout_live_files(template):
        relative = source.relative_to(template)
        target = repo_root / relative
        if target.is_file():
            _compare_file(
                source,
                target,
                errors,
                drift="local live runtime drift",
            )
    try:
        host_manifest = load_host_manifest(template)
    except HostManifestError as error:
        errors.append(str(error))
        return errors
    try:
        installed_platforms = detect_installed_platforms(repo_root)
    except HostManifestError:
        installed_platforms = ()
    skill_roots = {
        host_manifest.platform(platform_id).skill_read_root
        for platform_id in installed_platforms
        if host_manifest.platform(platform_id).skill_read_root
    }
    skill_root = template / "skills"
    for source in _distribution_files(skill_root):
        relative = source.relative_to(skill_root)
        for skill_root_target in sorted(skill_roots):
            _same_file(source, repo_root / skill_root_target / relative, errors)
    return errors


_ANCHOR_LANGUAGE_CHECKS = {
    "zh-CN": ("## 目标", "## 验收标准", "## 被拒方案", "## 验证命令"),
    "en-US": ("## Goal", "## Acceptance Criteria", "## Rejected Options", "## Verification Commands"),
}
_PLAN_LANGUAGE_CHECKS = {
    "zh-CN": re.compile(r"(?m)^\*\*目标(?::\*\*|\*\*:)"),
    "en-US": re.compile(r"(?m)^\*\*Goal(?::\*\*|\*\*:)"),
}


def _contract_block(text: str) -> str:
    """The schema example is the machine-readable heading source."""
    match = re.search(r"```markdown\n(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text


def _asset_language(path: Path, kind: str) -> str | None:
    """Detected output language, `mixed`, or None when the asset is absent."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if kind == "anchor":
        block = _contract_block(text)
        present = {
            language
            for language, markers in _ANCHOR_LANGUAGE_CHECKS.items()
            if all(marker in block for marker in markers)
        }
    else:
        present = {
            language
            for language, pattern in _PLAN_LANGUAGE_CHECKS.items()
            if pattern.search(text)
        }
    if len(present) > 1:
        return "mixed"
    return next(iter(present), None)


def check_language(repo_root: Path) -> list[dict[str, str]]:
    """Report an invalid `language` value and localized-asset drift.

    A missing config key or a missing asset means the project predates the
    language option: it is not drift, so it stays silent until the first sync.
    """
    config_file = repo_root / DIR_WORKFLOW / "config.yaml"
    try:
        config_text = config_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if not re.search(r"(?m)^language\s*:", config_text):
        return []

    try:
        language = get_language(repo_root, strict=True)
    except UnsupportedLanguageError as error:
        return [
            _issue(
                code="CONFIG-LANGUAGE-001",
                severity="error",
                path=config_file.relative_to(repo_root).as_posix(),
                message=str(error),
                command_hint="Edit .cowork-flow/config.yaml, then run cwf project sync",
                contract="runtime-health:language",
            )
        ]

    issues: list[dict[str, str]] = []
    assets = (
        (".cowork-flow/spec/contracts/decision-anchor.md", "anchor"),
        (".cowork-flow/templates/plan-template.md", "plan"),
    )
    for relative, kind in assets:
        path = repo_root / relative
        detected = _asset_language(path, kind)
        if detected is None:
            continue
        if detected != language:
            issues.append(
                _issue(
                    code="LANGUAGE-DRIFT-001",
                    severity="warning",
                    path=relative,
                    message=(
                        f"installed asset language is {detected}, but "
                        f".cowork-flow/config.yaml selects {language}"
                    ),
                    command_hint="cwf project sync",
                    contract="runtime-health:language",
                )
            )
    return issues


def _task_path(repo_root: Path, task_dir: Path) -> str:
    try:
        return task_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(task_dir)


def _task_metadata(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _session_task_paths(repo_root: Path) -> set[str]:
    sessions = repo_root / ".cowork-flow" / ".runtime" / "sessions"
    active: set[str] = set()
    if not sessions.is_dir():
        return active
    for path in sorted(sessions.glob("*.json")):
        data = _task_metadata(path)
        task_path = data.get("active_task_path")
        if isinstance(task_path, str) and task_path.strip():
            active.add(task_path.replace("\\", "/"))
    return active


def _normalized_task_path(value: str, repo_root: Path) -> str:
    """One task, one key: recorded task dirs may be absolute.

    Absoluteness is decided on the raw value before any slash stripping, so
    a slash-rooted POSIX path is not mistaken for a relative one.
    """
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/") or Path(raw).is_absolute():
        try:
            return (
                Path(raw).resolve().relative_to(repo_root.resolve()).as_posix()
            )
        except ValueError:
            pass
    normalized = raw
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _open_subagent_contexts_by_task(repo_root: Path) -> dict[str, list[str]]:
    """Open subagent runtime contexts, keyed by their task directory."""
    directory = repo_root / ".cowork-flow" / ".runtime" / "subagents"
    open_by_task: dict[str, list[str]] = {}
    if not directory.is_dir():
        return open_by_task
    for path in sorted(directory.glob("*.json")):
        data = _task_metadata(path)
        if data.get("status") == "closed":
            continue
        task_path = data.get("task_dir")
        if not isinstance(task_path, str) or not task_path.strip():
            continue
        context_id = str(data.get("runtime_context_id") or path.stem)
        open_by_task.setdefault(
            _normalized_task_path(task_path, repo_root), []
        ).append(context_id)
    return open_by_task


def _task_hygiene_issue(
    *,
    kind: str,
    task: str,
    status: str,
    message: str,
    hint: str,
) -> dict[str, str]:
    code = f"TASK-HYGIENE-{kind.replace('_', '-').upper()}"
    return _issue(
        code=code,
        severity="warning",
        path=task,
        message=message,
        command_hint=hint,
        contract="runtime-health:task-hygiene",
        kind=kind,
        task=task,
        status=status,
        hint=hint,
    )


def _missing_context_files(task_dir: Path) -> tuple[str, ...]:
    required = ("decision-anchor.md", "implement.jsonl", "check.jsonl", "debug.jsonl")
    return tuple(name for name in required if not (task_dir / name).is_file())


def check_task_hygiene(repo_root: Path) -> list[dict[str, str]]:
    from services.task_gate_profiles import is_light_task

    tasks_dir = repo_root / ".cowork-flow" / "tasks"
    if not tasks_dir.is_dir():
        return []
    bound_tasks = _session_task_paths(repo_root)
    open_subagents = _open_subagent_contexts_by_task(repo_root)
    issues: list[dict[str, str]] = []
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir() or task_dir.name == "archive":
            continue
        task = _task_path(repo_root, task_dir)
        data = _task_metadata(task_dir / "task.json")
        status = str(data.get("status") or "unknown")
        if is_light_task(data):
            # A warning, not an error: the profile is legitimate, and the
            # point is that a reduced gate set is never silent.
            issues.append(
                _task_hygiene_issue(
                    kind="light_profile",
                    task=task,
                    status=status,
                    message=(
                        "task runs under the light profile: the review "
                        "receipt, acceptance-evidence and dev_type gates are "
                        "waived"
                    ),
                    hint=f"./.cowork-flow/run task next {task}",
                )
            )
        if status == "completed":
            issues.append(
                _task_hygiene_issue(
                    kind="completed_unarchived",
                    task=task,
                    status=status,
                    message="completed task remains in the active task tree",
                    hint=f"./.cowork-flow/run task next {task} --run --intent archive",
                )
            )
            open_ids = open_subagents.get(
                _normalized_task_path(task, repo_root)
            )
            if open_ids:
                issues.append(
                    _task_hygiene_issue(
                        kind="completed_with_open_subagents",
                        task=task,
                        status=status,
                        message=(
                            "completed task still has open subagent context(s): "
                            + ", ".join(open_ids)
                        ),
                        hint=f"./.cowork-flow/run subagent list --task {task}",
                    )
                )
        if status in {"in_progress", "review"} and task not in bound_tasks:
            issues.append(
                _task_hygiene_issue(
                    kind="in_progress_unbound",
                    task=task,
                    status=status,
                    message="active task state is not bound to any runtime session",
                    hint=f"./.cowork-flow/run task next {task} --run",
                )
            )
        missing = _missing_context_files(task_dir)
        if missing:
            issues.append(
                _task_hygiene_issue(
                    kind="missing_task_context",
                    task=task,
                    status=status,
                    message=f"missing task context file(s): {', '.join(missing)}",
                    hint=f"./.cowork-flow/run task next {task} --validate",
                )
            )
    return issues


def _print_task_hygiene_issues(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        print(
            "WARNING: "
            f"{issue['kind']}: {issue['task']} ({issue['status']}): "
            f"{issue['message']}",
            file=sys.stderr,
        )
        print(f"Hint: {issue['hint']}", file=sys.stderr)


SESSION_STALE_MAX_AGE_DAYS = 30


def _session_hygiene_issue(
    *,
    kind: str,
    path: str,
    message: str,
    hint: str,
) -> dict[str, str]:
    code = f"SESSION-HYGIENE-{kind.replace('_', '-').upper()}"
    return _issue(
        code=code,
        severity="warning",
        path=path,
        message=message,
        command_hint=hint,
        contract="runtime-health:session-hygiene",
        kind=kind,
        hint=hint,
    )


def _parse_session_timestamp(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def check_session_hygiene(repo_root: Path) -> list[dict[str, str]]:
    """Report stale runtime session files without failing health."""
    sessions_dir = repo_root / ".cowork-flow" / ".runtime" / "sessions"
    if not sessions_dir.is_dir():
        return []
    now = datetime.now(timezone.utc)
    issues: list[dict[str, str]] = []
    for path in sorted(sessions_dir.glob("*.json")):
        diagnostic = _diagnostic_path(repo_root, path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if not isinstance(data, dict):
            issues.append(
                _session_hygiene_issue(
                    kind="unreadable_session",
                    path=diagnostic,
                    message="session file is unreadable or not a JSON object",
                    hint=f"review and delete {diagnostic}",
                )
            )
            continue
        reasons: list[str] = []
        task_path = str(data.get("active_task_path") or "")
        dead_task = bool(task_path) and not (
            repo_root / task_path / "task.json"
        ).is_file()
        raw_seen_at = str(data.get("last_seen_at") or "")
        seen_at = _parse_session_timestamp(raw_seen_at) if raw_seen_at else None
        aged = False
        if seen_at is None and raw_seen_at:
            reasons.append(f"unparsable last_seen_at: {raw_seen_at}")
            aged = True
        elif seen_at is not None and seen_at.tzinfo is None:
            # Naive timestamps cannot be compared against aware now().
            reasons.append(f"last_seen_at without timezone: {raw_seen_at}")
            aged = True
        elif seen_at is not None:
            age_days = (now - seen_at).days
            if age_days > SESSION_STALE_MAX_AGE_DAYS:
                reasons.append(f"not seen for {age_days} days")
                aged = True
        if dead_task:
            issues.append(
                _session_hygiene_issue(
                    kind="dead_task",
                    path=diagnostic,
                    message=(
                        f"session bound to missing task directory: {task_path}"
                    ),
                    hint=f"delete {diagnostic} or rebind via ./.cowork-flow/run task next",
                )
            )
        if aged:
            issues.append(
                _session_hygiene_issue(
                    kind="aged",
                    path=diagnostic,
                    message=f"stale session file: {'; '.join(reasons)}",
                    hint=f"delete {diagnostic}",
                )
            )
    return issues


def _print_session_hygiene_issues(issues: list[dict[str, str]]) -> None:
    for issue in issues:
        print(
            f"WARNING: {issue['kind']}: {issue['path']}: {issue['message']}",
            file=sys.stderr,
        )
        print(f"Hint: {issue['hint']}", file=sys.stderr)


def _diagnostic_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _state_lock_code(status: str) -> str:
    return f"STATE-RECOVERY-LOCK-{status.upper().replace('_', '-')}"


def _state_lock_command_hint(info) -> str:
    if info.status != "recoverable":
        return "Inspect the lock owner facts; do not delete unless the owner PID is missing and the lock is older than the stale threshold."
    return (
        "Use an explicit recovery action only after verification, for example "
        "StateStore().remove_stale_lock(Path(<target>), stale_after_seconds="
        f"{DEFAULT_STALE_LOCK_SECONDS})"
    )


def _state_lock_issue(repo_root: Path, info) -> dict[str, object]:
    fields = info.to_dict()
    fields.update(
        {
            "kind": "state_lock",
            "lockPath": _diagnostic_path(repo_root, info.lock_path),
            "target": str(info.target),
        }
    )
    if info.age_seconds is not None:
        fields["ageSeconds"] = round(info.age_seconds, 3)
    return _issue(
        code=_state_lock_code(info.status),
        severity="warning",
        path=_diagnostic_path(repo_root, info.lock_path),
        message=info.detail,
        command_hint=_state_lock_command_hint(info),
        contract="runtime-health:state-recovery",
        **fields,
    )


def _operation_command_hint() -> str:
    return (
        "Inspect the pending operation record; a trusted recovery command may "
        "call UnitOfWork.recover_all(repo_root) without interpreting error "
        "output as instructions."
    )


def _pending_operation_issue(repo_root: Path, fact: dict) -> dict[str, object]:
    error = fact.get("error")
    if fact.get("phase") == "unreadable" and isinstance(error, dict):
        return _issue(
            code="STATE-RECOVERY-OPERATION-UNREADABLE",
            severity="warning",
            path=_diagnostic_path(repo_root, Path(str(fact.get("path") or ""))),
            message=str(error.get("detail") or "operation record is unreadable"),
            command_hint="Inspect the operation record manually; Doctor does not mutate recovery state.",
            contract="runtime-health:state-recovery",
            kind="pending_operation",
            operationId=str(fact.get("operation_id") or ""),
            phase=str(fact.get("phase") or "unreadable"),
            errorCode=str(error.get("code") or ""),
        )
    operation_id = str(fact.get("operation_id") or "")
    phase = str(fact.get("phase") or "unknown")
    record_error = fact.get("error")
    if phase == "conflicted":
        error_detail = ""
        error_code = ""
        if isinstance(record_error, dict):
            error_code = str(record_error.get("code") or "")
            error_detail = str(record_error.get("detail") or "")
        suffix = ": ".join(value for value in (error_code, error_detail) if value)
        message = (
            f"conflicted UnitOfWork operation {operation_id}"
            + (f": {suffix}" if suffix else "")
        )
        return _issue(
            code="STATE-RECOVERY-CONFLICTED-OPERATION",
            severity="warning",
            path=_diagnostic_path(repo_root, Path(str(fact.get("path") or ""))),
            message=message,
            command_hint=(
                "Resolve the recorded conflict manually; Doctor does not retry "
                "or mutate conflicted operation state."
            ),
            contract="runtime-health:state-recovery",
            kind="pending_operation",
            operationId=operation_id,
            operationKind=str(fact.get("kind") or "unknown"),
            phase=phase,
            participantCount=fact.get("participant_count", 0),
        )
    return _issue(
        code="STATE-RECOVERY-PENDING-OPERATION",
        severity="warning",
        path=_diagnostic_path(repo_root, Path(str(fact.get("path") or ""))),
        message=f"pending UnitOfWork operation {operation_id} is in phase {phase}",
        command_hint=_operation_command_hint(),
        contract="runtime-health:state-recovery",
        kind="pending_operation",
        operationId=operation_id,
        operationKind=str(fact.get("kind") or "unknown"),
        phase=phase,
        participantCount=fact.get("participant_count", 0),
    )


def check_state_recovery(repo_root: Path) -> list[dict[str, object]]:
    workflow = repo_root / ".cowork-flow"
    if not workflow.is_dir():
        return []
    store = StateStore()
    issues: list[dict[str, object]] = []
    for lock_path in sorted(workflow.rglob("*.lock")):
        if not lock_path.is_file():
            continue
        info = store.inspect_lock_path(
            lock_path,
            stale_after_seconds=DEFAULT_STALE_LOCK_SECONDS,
        )
        if info.status != "absent":
            issues.append(_state_lock_issue(repo_root, info))
    operation_log = OperationLog(repo_root, state_store=store)
    for fact in operation_log.pending_facts():
        issues.append(_pending_operation_issue(repo_root, fact))
    return issues


def _print_state_recovery_issues(issues: list[dict[str, object]]) -> None:
    for issue in issues:
        print(
            "WARNING: "
            f"{issue['kind']}: {issue['path']}: "
            f"{issue['message']}",
            file=sys.stderr,
        )
        hint = issue.get("commandHint")
        if hint:
            print(f"Hint: {hint}", file=sys.stderr)


def check_runtime(repo_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        load_skill_manifests(repo_root)
        action_owners(repo_root)
    except SkillManifestError as error:
        errors.append(f"Skill manifest error: {error}")

    distribution_root = _distribution_root(repo_root)
    kernel_path = distribution_root / ".cowork-flow/scripts/kernel/workflow_route.py"
    if not kernel_path.is_file():
        errors.append(f"missing kernel route: {kernel_path}")
    else:
        source = kernel_path.read_text(encoding="utf-8")
        for forbidden in ("activatedSkill", "recommendedSkill", "./.cowork-flow/run", "label"):
            if forbidden in source:
                errors.append(f"kernel contains delivery concern: {forbidden}")

    workflow_template = distribution_root / ".cowork-flow/spec/contracts/workflow-state-templates.md"
    if not workflow_template.is_file():
        errors.append(f"missing workflow-state contract: {workflow_template}")
    else:
        text = workflow_template.read_text(encoding="utf-8")
        for status in ("no_task", "delegated_subtask", "planning", "in_progress", "review", "completed"):
            if f"[workflow-state:{status}]" not in text:
                errors.append(f"workflow-state contract missing status: {status}")
    return errors


def _global_mcp_registered() -> bool:
    """Tolerant probe of user-level host configs for a cowork-flow MCP
    entry. Read-only; missing files simply mean "not registered"."""
    import os

    home = Path(os.path.expanduser("~"))
    candidates = (
        home / ".zcode" / "cli" / "config.json",
        home / ".claude.json",
        home / ".codex" / "config.toml",
    )
    for path in candidates:
        try:
            if path.is_file() and "cowork-flow" in path.read_text(
                encoding="utf-8", errors="replace"
            ):
                return True
        except OSError:
            continue
    return False


def check_mcp_registration(repo_root: Path) -> list[dict[str, str]]:
    """MCP fact-layer registration health. Advisory only (never fatal):
    global registration is a supported default, so absence is a hint, not
    an error. Reports project-level .mcp.json presence and the duplicate
    global+project combination."""
    issues: list[dict[str, str]] = []
    project_registered = False
    project_mcp = repo_root / ".mcp.json"
    if project_mcp.is_file():
        try:
            data = json.loads(project_mcp.read_text(encoding="utf-8"))
            servers = (
                data.get("mcpServers") if isinstance(data, dict) else None
            )
            project_registered = isinstance(servers, dict) and any(
                "cowork" in str(name).lower() for name in servers
            )
            issues.append(
                {
                    "kind": "mcp",
                    "status": "project",
                    "message": (
                        "project .mcp.json registers the fact layer"
                        if project_registered
                        else "project .mcp.json present but no cowork-flow server entry"
                    ),
                }
            )
        except (OSError, json.JSONDecodeError, ValueError):
            issues.append(
                {
                    "kind": "mcp",
                    "status": "project",
                    "message": "project .mcp.json is not valid JSON",
                }
            )
    global_registered = _global_mcp_registered()
    if project_registered and global_registered:
        issues.append(
            {
                "kind": "mcp",
                "status": "duplicate",
                "message": (
                    "cowork-flow is registered both globally and at project "
                    "level; hosts deduplicate by server name, but removing "
                    "one keeps the tool list clean"
                ),
            }
        )
    if not project_registered and not global_registered:
        issues.append(
            {
                "kind": "mcp",
                "status": "absent",
                "message": (
                    "fact layer not registered: register globally with "
                    "`cwf mcp serve`, or add a project .mcp.json "
                    "(see spec/contracts/fact-layer-access.md)"
                ),
            }
        )
    return issues


def check_dsh_preset(repo_root: Path) -> list[dict[str, str]]:
    """DSH preset freshness from the CLI-owned install-state read model.

    Advisory only, and silent while the project never selected DSH or when the
    preset is absent: it is a machine-level asset installed once, so it does
    not update with npm or sync. Report an unknown or stale installed version
    instead of assuming the injection logic matches this project."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "dsh" / "adapter.yaml"
    if not adapter.is_file():
        return []
    row, unavailable = _inspect_component_row(
        repo_root, "dsh", "preset", "the dsh preset"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    path = _inspect_path(row, "dsh")
    reason = str(row.get("reason") or "")

    if status == "missing":
        return []
    if status == "broken":
        return [
            _issue(
                code="PRESET-UNKNOWN-VERSION",
                severity="warning",
                path=str(path),
                message=(
                    f"DSH preset is installed without a readable version marker "
                    f"({reason}); its injection logic may predate the current "
                    "release"
                ),
                command_hint="cwf host add dsh --component preset --force",
                contract="runtime-health:dsh-preset",
            )
        ]
    if status in ("installed", "stale"):
        project_version = _project_stale_version(row, repo_root)
        if project_version is not None:
            recorded = row.get("version") or "an unknown version"
            return [
                _issue(
                    code="PRESET-STALE",
                    severity="warning",
                    path=str(path),
                    message=_project_stale_message(
                        "DSH preset",
                        recorded,
                        project_version,
                        "the preset does not update with sync or npm, so "
                        "injection may lag the project runtime",
                    ),
                    command_hint="cwf host add dsh --component preset --force",
                    contract="runtime-health:dsh-preset",
                )
            ]
        return []
    return _unexpected_inspect_status("dsh", status)


def _project_version(repo_root: Path) -> str:
    try:
        return (
            repo_root / DIR_WORKFLOW / ".version"
        ).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _project_stale_version(row: dict[str, object], repo_root: Path) -> str | None:
    """The project runtime version when the installed payload does not match it.

    Inspect's own `stale` compares the payload with the running CLI. Doctor
    answers for this project, so it compares with the project's `.version`
    instead; a payload with no recorded version is unknown, not fresh."""
    project_version = _project_version(repo_root)
    if project_version and row.get("version") != project_version:
        return project_version
    return None


_KIMI_HOOK_CONTRACT = "runtime-health:kimi-hook"


def _kimi_hook_warning(
    code: str, path: Path, message: str, hint: str
) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_KIMI_HOOK_CONTRACT,
        )
    ]


def check_kimi_hook(repo_root: Path) -> list[dict[str, str]]:
    """Kimi Code hook health from the CLI-owned install-state read model.

    Silent while unselected or unconfigured; report unknown or stale versions
    instead of assuming the machine-level hook matches this project."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "kimi-code" / "adapter.yaml"
    if not adapter.is_file():
        return []
    row, unavailable = _inspect_component_row(
        repo_root, "kimi-code", "hook", "the kimi-code hook"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    path = _inspect_path(row, "kimi-code")
    reason = str(row.get("reason") or "")

    if status == "missing":
        if reason == "config file is absent":
            return []
        return _kimi_hook_warning(
            "HOOK-NOT-INSTALLED",
            path,
            "Kimi Code is configured but no cowork-flow hook is registered; "
            "sessions inject no workflow context",
            "cwf host add kimi-code --component hook",
        )
    if status == "broken":
        if reason == "shim is missing":
            return _kimi_hook_warning(
                "HOOK-SHIM-MISSING",
                path,
                "config.toml registers the cowork-flow hook but its shim is "
                "missing; the host runs a command that cannot start",
                "cwf host add kimi-code --component hook",
            )
        if reason.startswith("version marker"):
            return _kimi_hook_warning(
                "HOOK-UNKNOWN-VERSION",
                path,
                f"Kimi Code hook {reason}; its injection logic may predate the "
                "current release",
                "cwf host add kimi-code --component hook",
            )
        return _host_inspect_unavailable_issue(
            "kimi-code", {"reason": f"host inspect reported {reason!r}"}
        )
    if status in ("installed", "stale"):
        project_version = _project_stale_version(row, repo_root)
        if project_version is not None:
            recorded = row.get("version") or "an unknown version"
            return _kimi_hook_warning(
                "HOOK-STALE",
                path,
                _project_stale_message(
                    "Kimi Code hook",
                    recorded,
                    project_version,
                    "the hook does not update with sync or npm, so injection "
                    "may lag the project runtime",
                ),
                "cwf host add kimi-code --component hook",
            )
        return []
    return _unexpected_inspect_status("kimi-code", status)


_QODER_PLUGIN_CONTRACT = "runtime-health:qoder-plugin"
QODER_PLUGIN_KEY = "cowork-flow@cowork-flow-local"


def _qoder_warning(code: str, path: Path, message: str, hint: str) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_QODER_PLUGIN_CONTRACT,
        )
    ]


_ZCODE_PLUGIN_CONTRACT = "runtime-health:zcode-plugin"


def _zcode_warning(code: str, path: Path, message: str, hint: str) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_ZCODE_PLUGIN_CONTRACT,
        )
    ]


_HOST_INSPECT_CONTRACT = "runtime-health:host-inspect"
HOST_INSPECT_TIMEOUT_SECONDS = 5
_HOST_INSPECT_CACHE: dict[str, dict[str, object]] = {}


def _host_inspect_command() -> list[str] | None:
    """The CLI invocation that owns machine install-state facts.

    A configured JavaScript entry runs through Node, so a checkout can be
    inspected without installing it globally.
    """
    configured = (os.environ.get("COWORK_FLOW_CLI") or "").strip()
    if configured:
        if configured.lower().endswith((".js", ".mjs", ".cjs")):
            node = shutil.which("node")
            return [node, configured] if node else None
        return [configured]
    for name in ("cwf", "cowork-flow"):
        found = shutil.which(name)
        if found:
            return [found]
    return None


def _host_inspect_unavailable(reason: str) -> dict[str, object]:
    return {"available": False, "reason": reason, "hosts": {}}


def _run_host_inspect() -> dict[str, object]:
    command = _host_inspect_command()
    if command is None:
        return _host_inspect_unavailable(
            "the cowork-flow CLI is not on PATH; set COWORK_FLOW_CLI or install it"
        )
    try:
        completed = subprocess.run(
            [*command, "host", "inspect", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=HOST_INSPECT_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as error:
        return _host_inspect_unavailable(f"host inspect could not run: {error}")
    if completed.returncode != 0:
        return _host_inspect_unavailable(
            f"host inspect exited with {completed.returncode}"
        )
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, ValueError):
        return _host_inspect_unavailable("host inspect returned invalid JSON")
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        return _host_inspect_unavailable(
            "host inspect does not support schemaVersion 1; upgrade cowork-flow"
        )
    rows = payload.get("hosts")
    if not isinstance(rows, list):
        return _host_inspect_unavailable("host inspect returned no hosts list")
    hosts: dict[str, dict[str, object]] = {}
    components: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        host_id = row["id"]
        component = str(row.get("component") or "")
        components[f"{host_id}:{component}"] = row
        hosts.setdefault(host_id, row)
    return {
        "available": True,
        "reason": "",
        "hosts": hosts,
        "components": components,
    }


def _inspect_row(
    facts: dict[str, object], host_id: str, component: str
) -> dict[str, object] | None:
    row = facts.get("components", {}).get(f"{host_id}:{component}")
    return row if isinstance(row, dict) else None


def _host_inspect_facts(repo_root: Path) -> dict[str, object]:
    """One inspect call per doctor run; the facts are read-only."""
    key = str(repo_root)
    cached = _HOST_INSPECT_CACHE.get(key)
    if cached is None:
        cached = _run_host_inspect()
        _HOST_INSPECT_CACHE[key] = cached
    return cached


def _inspect_component_row(
    repo_root: Path, host_id: str, component: str, label: str
) -> tuple[dict[str, object] | None, list[dict[str, str]] | None]:
    """The inspect row for one component, or the shared unavailable warning."""
    facts = _host_inspect_facts(repo_root)
    if not facts["available"]:
        return None, _host_inspect_unavailable_issue(host_id, facts)
    row = _inspect_row(facts, host_id, component)
    if row is None:
        return None, _host_inspect_unavailable_issue(
            host_id, {"reason": f"host inspect omitted {label}"}
        )
    return row, None


def _unexpected_inspect_status(
    host_id: str, status: object
) -> list[dict[str, str]]:
    return _host_inspect_unavailable_issue(
        host_id, {"reason": f"host inspect reported status {status!r}"}
    )


def _inspect_path(row: dict[str, object], fallback: str = "cowork-flow") -> Path:
    """The most specific path for a warning.

    The read model owns host layout, so the doctor never derives the path from
    the human-readable reason: detail path, payload root, then registration."""
    return Path(
        str(
            row.get("detailPath")
            or row.get("payloadPath")
            or row.get("registeredSource")
            or fallback
        )
    )


def _project_stale_message(
    subject: str, recorded: object, project_version: str, consequence: str
) -> str:
    return (
        f"{subject} was installed from {recorded or 'an unknown version'} but "
        f"this project runs {project_version}; {consequence}"
    )


def _host_inspect_unavailable_issue(
    platform_id: str, facts: dict[str, object]
) -> list[dict[str, str]]:
    command = _host_inspect_command()
    label = " ".join(command) if command else "cwf"
    return [
        _issue(
            code="HOST-INSPECT-UNAVAILABLE",
            severity="warning",
            path=label,
            message=(
                f"cannot verify the {platform_id} plugin install state: "
                f"{facts.get('reason') or 'host inspect is unavailable'}; the "
                "installed cowork-flow CLI may be missing or older than this project"
            ),
            command_hint="npm install -g cowork-flow@latest",
            contract=_HOST_INSPECT_CONTRACT,
        )
    ]


def check_qoder_plugin(repo_root: Path) -> list[dict[str, str]]:
    """Qoder plugin health from the CLI-owned install-state read model.

    Advisory, and silent while the project never selected the Qoder host: the
    plugin is a machine-level asset installed once into `~/.qoder/plugins`, so
    it never updates through sync or npm."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "qoder" / "adapter.yaml"
    if not adapter.is_file():
        return []

    row, unavailable = _inspect_component_row(
        repo_root, "qoder", "plugin", "qoder"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    payload = Path(str(row.get("payloadPath") or row.get("registeredSource") or "qoder"))
    path = _inspect_path(row, "qoder")
    reason = str(row.get("reason") or "")

    if status == "missing":
        return _qoder_warning(
            "PLUGIN-NOT-INSTALLED",
            path,
            "this project declares the Qoder host, but cowork-flow is not "
            "registered in the Qoder plugin cache, so Qoder sessions inject no "
            "workflow context; loading also needs a Qoder restart and a "
            "trusted workspace",
            "cwf host add qoder",
        )
    if status == "broken":
        code = (
            "PLUGIN-PAYLOAD-MISSING"
            if "manifest" in reason or "installPath" in reason
            else "PLUGIN-PAYLOAD-INCOMPLETE"
        )
        return _qoder_warning(
            code,
            path,
            f"the Qoder plugin at {payload} is incomplete ({reason}); the host "
            "cannot load it",
            "cwf host add qoder --force",
        )
    if status in ("installed", "stale"):
        if row.get("enabled") is False:
            return _qoder_warning(
                "PLUGIN-DISABLED",
                path,
                'the Qoder plugin is installed but not enabled '
                f'(`enabledPlugins["{QODER_PLUGIN_KEY}"]`); no hook fires',
                "cwf host add qoder --force",
            )
        project_version = _project_stale_version(row, repo_root)
        if project_version is not None:
            recorded = row.get("version") or "an unknown version"
            return _qoder_warning(
                "PLUGIN-STALE",
                path,
                _project_stale_message(
                    "the Qoder plugin",
                    recorded,
                    project_version,
                    "the plugin does not update with sync or npm, so injection "
                    "may lag the project runtime",
                ),
                "cwf host add qoder --force",
            )
        return []
    return _unexpected_inspect_status("qoder", status)


def check_zcode_plugin(repo_root: Path) -> list[dict[str, str]]:
    """ZCode plugin health from the CLI-owned install-state read model.

    Advisory, and silent while the project never selected the ZCode host: the
    plugin is a machine-level asset installed once into the ZCode config
    directory, so it never updates through sync or npm."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "zcode" / "adapter.yaml"
    if not adapter.is_file():
        return []

    row, unavailable = _inspect_component_row(
        repo_root, "zcode", "plugin", "zcode"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    payload = Path(str(row.get("payloadPath") or row.get("registeredSource") or "zcode"))
    path = _inspect_path(row, "zcode")

    if status == "missing":
        return _zcode_warning(
            "PLUGIN-NOT-INSTALLED",
            path,
            "this project declares the ZCode host, but no cowork-flow plugin is "
            "installed in the ZCode config directory, so ZCode sessions inject no "
            "workflow context",
            "cwf host add zcode",
        )
    if status == "broken":
        reason = str(row.get("reason") or "")
        code = (
            "PLUGIN-UNKNOWN-VERSION"
            if "manifest" in reason or "no version" in reason
            else "PLUGIN-PAYLOAD-MISSING"
        )
        return _zcode_warning(
            code,
            path,
            f"the ZCode plugin at {payload} is incomplete ({reason}); the host "
            "cannot load it",
            "cwf host add zcode --force",
        )
    if status in ("installed", "stale"):
        project_version = _project_stale_version(row, repo_root)
        if project_version is not None:
            recorded = row.get("version") or "an unknown version"
            return _zcode_warning(
                "PLUGIN-STALE",
                path,
                _project_stale_message(
                    "the ZCode plugin",
                    recorded,
                    project_version,
                    "the plugin does not update with sync or npm, so injection "
                    "may lag the project runtime",
                ),
                "cwf host add zcode --force",
            )
        return []
    return _unexpected_inspect_status("zcode", status)


_CLAUDE_CODE_PLUGIN_CONTRACT = "runtime-health:claude-code-plugin"


def _claude_code_warning(
    code: str, path: Path, message: str, hint: str
) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_CLAUDE_CODE_PLUGIN_CONTRACT,
        )
    ]


def check_claude_code_plugin(repo_root: Path) -> list[dict[str, str]]:
    """Claude Code plugin health. Advisory, and silent while the project never
    selected the Claude Code host: the plugin is a machine-level asset installed
    once into the user's skills directory, so it never updates through sync or
    npm.

    Claude Code loads `<skills-dir>/<name>/` as `<name>@skills-dir` when that
    folder carries a plugin manifest, so the payload is readable straight from
    disk: there is no registry entry and no enable flag to consult."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "claude-code" / "adapter.yaml"
    if not adapter.is_file():
        return []

    row, unavailable = _inspect_component_row(
        repo_root, "claude-code", "plugin", "claude-code"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    path = _inspect_path(row, "claude")
    reason = str(row.get("reason") or "")

    if status == "missing":
        if reason == "a different plugin owns this directory":
            return []
        return _claude_code_warning(
            "PLUGIN-NOT-INSTALLED",
            path,
            "this project declares the Claude Code host, but no cowork-flow "
            "skills-directory plugin is installed, so Claude Code sessions see "
            "no cowork-flow plugin Skill",
            "cwf host add claude-code",
        )
    if status == "broken":
        return _claude_code_warning(
            "PLUGIN-PAYLOAD-INCOMPLETE",
            path,
            "the installed Claude Code plugin carries no bootstrap Skill, so it "
            "contributes nothing in a repository without a runtime",
            "cwf host add claude-code --force",
        )
    if status in ("installed", "stale"):
        project_version = _project_stale_version(row, repo_root)
        if project_version is not None:
            recorded = row.get("version") or "an unknown version"
            return _claude_code_warning(
                "PLUGIN-STALE",
                path,
                _project_stale_message(
                    "the Claude Code plugin",
                    recorded,
                    project_version,
                    "the plugin does not update with sync or npm",
                ),
                "cwf host add claude-code --force",
            )
        return []
    return _unexpected_inspect_status("claude-code", status)


_OPENCODE_PLUGIN_CONTRACT = "runtime-health:opencode-plugin"
_OPENCODE_PROJECT_PLUGIN = ".opencode/plugins/cowork-flow.js"
_OPENCODE_PROJECT_CORE = ".opencode/cowork-flow/plugin-core.js"


def _opencode_warning(
    code: str, path: Path, message: str, hint: str
) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_OPENCODE_PLUGIN_CONTRACT,
        )
    ]


def check_opencode_plugin(repo_root: Path) -> list[dict[str, str]]:
    """OpenCode plugin health from the CLI-owned install-state read model.

    Advisory, and silent while the project never selected the OpenCode host: the
    plugin is a machine-level asset installed once into the user's config
    directory, so it never updates through sync or npm.

    OpenCode's plugin format carries no manifest, so there is no version to
    compare. Staleness is judged against the project's own copy of the same two
    files instead: they are the same source delivered twice, so a difference
    means one of them was updated and the other was not."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "opencode" / "adapter.yaml"
    if not adapter.is_file():
        return []

    row, unavailable = _inspect_component_row(
        repo_root, "opencode", "plugin", "opencode"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    registered = Path(str(row.get("registeredSource") or "opencode"))
    payload = Path(str(row["payloadPath"])) if row.get("payloadPath") else registered
    path = _inspect_path(row, "opencode")
    reason = str(row.get("reason") or "")

    if status == "missing":
        # A same-named file a user put there is not cowork-flow's to report on.
        if reason == "a different plugin owns this file":
            return []
        return _opencode_warning(
            "PLUGIN-NOT-INSTALLED",
            path,
            "this project declares the OpenCode host, but no cowork-flow plugin "
            "is installed in the OpenCode config directory, so OpenCode sessions "
            "see no cowork-flow plugin Skill",
            "cwf host add opencode",
        )
    if status == "broken":
        return _opencode_warning(
            "PLUGIN-PAYLOAD-INCOMPLETE",
            path,
            f"the installed OpenCode plugin is incomplete ({reason}), so it "
            "registers a skills directory that is not there",
            "cwf host add opencode --force",
        )
    if status not in ("installed", "stale"):
        return _unexpected_inspect_status("opencode", status)

    for installed_path, project_relative in (
        (registered, _OPENCODE_PROJECT_PLUGIN),
        (payload / "plugin-core.js", _OPENCODE_PROJECT_CORE),
    ):
        # A project mid-init has no copy yet; an unreadable one is not ours to
        # judge. Either way there is nothing to compare, so the loop moves on.
        try:
            project_text = (repo_root / project_relative).read_text(encoding="utf-8")
            installed_text = installed_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if project_text != installed_text:
            return _opencode_warning(
                "PLUGIN-STALE",
                installed_path,
                f"the installed OpenCode {project_relative} differs from this "
                "project's copy of the same file; one of them was updated and "
                "the other was not, and the plugin does not update with sync or "
                "npm",
                "cwf host add opencode --force",
            )
    return []


_KIMI_PLUGIN_CONTRACT = "runtime-health:kimi-code-plugin"


def _kimi_plugin_warning(
    code: str, path: Path, message: str, hint: str
) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_KIMI_PLUGIN_CONTRACT,
        )
    ]


def check_kimi_code_plugin(repo_root: Path) -> list[dict[str, str]]:
    """Kimi Code plugin health from the CLI-owned install-state read model.

    Advisory, and silent while the project never selected the Kimi Code host.

    The plugin is a machine-level asset: `cwf host add kimi-code` installs the
    managed copy and writes the registry record itself (no TUI handoff), so a
    record that is missing, disabled, half-materialized or stale is exactly
    what this check names."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "kimi-code" / "adapter.yaml"
    if not adapter.is_file():
        return []

    row, unavailable = _inspect_component_row(
        repo_root, "kimi-code", "plugin", "kimi-code"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    path = _inspect_path(row, "kimi-code")
    reason = str(row.get("reason") or "")

    if status == "missing":
        return _kimi_plugin_warning(
            "PLUGIN-NOT-INSTALLED",
            path,
            "this project declares the Kimi Code host, but cowork-flow is not "
            "registered as a Kimi Code plugin, so sessions load no cowork-flow "
            "plugin Skill",
            "cwf host add kimi-code",
        )
    if row.get("enabled") is False:
        return _kimi_plugin_warning(
            "PLUGIN-DISABLED",
            path,
            "the cowork-flow Kimi Code plugin is installed but disabled, so its "
            "bootstrap Skill never loads",
            "/plugins enable cowork-flow",
        )
    if status == "broken":
        return _kimi_plugin_warning(
            "PLUGIN-PAYLOAD-INCOMPLETE",
            path,
            f"the installed Kimi Code plugin is incomplete ({reason}), so it "
            "cannot load the bootstrap Skill",
            "cwf host add kimi-code --force",
        )
    if status not in ("installed", "stale"):
        return _unexpected_inspect_status("kimi-code", status)
    project_version = _project_stale_version(row, repo_root)
    if project_version is not None:
        recorded = row.get("version") or "an unknown version"
        return _kimi_plugin_warning(
            "PLUGIN-STALE",
            path,
            _project_stale_message(
                "the Kimi Code plugin",
                recorded,
                project_version,
                "the plugin does not update with sync or npm",
            ),
            "cwf host add kimi-code --force",
        )
    if reason == "stable reinstall source directory is missing":
        return _kimi_plugin_warning(
            "PLUGIN-SOURCES-MISSING",
            path,
            "the cowork-flow Kimi Code plugin is registered but its stable "
            "reinstall source directory is gone",
            "cwf host add kimi-code",
        )
    return []


_CODEX_PLUGIN_CONTRACT = "runtime-health:codex-plugin"
CODEX_PLUGIN_KEY = "cowork-flow@cowork-flow-local"


def _codex_warning(code: str, path: Path, message: str, hint: str) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_CODEX_PLUGIN_CONTRACT,
        )
    ]


def check_codex_plugin(repo_root: Path) -> list[dict[str, str]]:
    """Codex plugin health from the CLI-owned install-state read model.

    Advisory, and silent while the project never selected the Codex host: the
    plugin is a machine-level asset registered in `~/.codex/config.toml`, so it
    never updates through sync or npm."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "codex" / "adapter.yaml"
    if not adapter.is_file():
        return []

    row, unavailable = _inspect_component_row(
        repo_root, "codex", "plugin", "codex"
    )
    if unavailable is not None:
        return unavailable
    status = row.get("status")
    path = _inspect_path(row, "codex")
    reason = str(row.get("reason") or "")

    if status == "missing":
        return _codex_warning(
            "PLUGIN-NOT-INSTALLED",
            path,
            "this project declares the Codex host, but cowork-flow's marketplace "
            "is not registered in the Codex config, so Codex sessions see no "
            "cowork-flow plugin Skills",
            "cwf host add codex",
        )
    if status == "broken":
        return _codex_warning(
            "PLUGIN-PAYLOAD-MISSING",
            path,
            f"the Codex marketplace is registered but its payload is incomplete "
            f"({reason}); the host cannot load a missing payload",
            "cwf host add codex --force",
        )
    if status not in ("installed", "stale"):
        return _unexpected_inspect_status("codex", status)
    if row.get("enabled") is not True:
        return _codex_warning(
            "PLUGIN-DISABLED",
            path,
            "the Codex plugin is registered but not enabled "
            f'(`[plugins."{CODEX_PLUGIN_KEY}"] enabled = true`), so its Skills '
            "stay invisible to sessions",
            "cwf host add codex --force",
        )
    project_version = _project_stale_version(row, repo_root)
    if project_version is not None:
        recorded = row.get("version") or "an unknown version"
        return _codex_warning(
            "PLUGIN-STALE",
            path,
            _project_stale_message(
                "the Codex plugin",
                recorded,
                project_version,
                "the plugin does not update with sync or npm",
            ),
            "cwf host add codex --force",
        )
    return []


_SKILL_DELIVERY_CONTRACT = "runtime-health:skill-delivery"


def _skill_delivery_warning(
    code: str, path: str | Path, message: str, hint: str = ""
) -> list[dict[str, str]]:
    return [
        _issue(
            code=code,
            severity="warning",
            path=str(path),
            message=message,
            command_hint=hint,
            contract=_SKILL_DELIVERY_CONTRACT,
        )
    ]


def _legacy_machine_skills_issues(
    platform_id: str,
    project_skills: Path | None,
    facts: dict[str, object],
) -> list[dict[str, str]]:
    """Warnings for a host whose machine-level plugin still carries a copy of a
    Skill this project also ships. The payload is bootstrap-only, so a
    same-named copy is a leftover that may come from another release; a payload
    Skill the project does not ship (the bootstrap guide) is expected and stays
    silent."""
    row = _inspect_row(facts, platform_id, "plugin")
    if row is None or not row.get("payloadPath"):
        return []
    payload = Path(str(row["payloadPath"]))
    skills = payload / "skills"
    if not skills.is_dir():
        return []
    names: set[str] = set()
    if project_skills is not None:
        try:
            names = {
                entry.name
                for entry in project_skills.iterdir()
                if (entry / "SKILL.md").is_file()
            }
        except OSError:
            names = set()
    replicas = sorted(
        entry.name
        for entry in skills.iterdir()
        if (entry / "SKILL.md").is_file() and entry.name in names
    )
    if not replicas:
        return []
    return _skill_delivery_warning(
        "PLUGIN-SKILLS-LEGACY",
        skills,
        f"the {platform_id} plugin payload still carries project Skill copies "
        f"({', '.join(replicas)}) from {payload.name}; project Skills ship with "
        "the project only, so the payload copy is redundant and may come from "
        "another release",
        f"cwf host add {platform_id} --force",
    )


def check_skill_delivery(repo_root: Path) -> list[dict[str, str]]:
    """Skill delivery diagnostics for the hosts this project selected: whether
    each declared read root is on disk, whether a machine-level plugin payload
    still carries a copy of a Skill this project ships, and whether a
    declared discovery channel sits behind host-side gates. Advisory only:
    doctor cannot read host trust state, and a leftover copy is not a broken
    project."""
    root = _distribution_root(repo_root)
    try:
        manifest = load_host_manifest(root)
    except HostManifestError:
        return []  # host adapter checks already report an unreadable manifest
    try:
        platforms = detect_installed_platforms(repo_root)
    except HostManifestError:
        return []
    if not platforms:
        return []
    issues: list[dict[str, str]] = []
    facts = _host_inspect_facts(repo_root)
    for platform_id in platforms:
        platform = manifest.platform(platform_id)
        read_root = repo_root / platform.skill_read_root
        delivered = read_root.is_dir()
        if not delivered:
            issues.extend(
                _skill_delivery_warning(
                    "SKILL-READROOT-MISSING",
                    platform.skill_read_root,
                    f"{platform_id} reads skills from {platform.skill_read_root}, "
                    "but this project has no such directory, so sessions see no "
                    "cowork-flow skills",
                    "cwf project sync",
                )
            )
        for entry in platform.skill_discovery:
            # A reminder, not a verdict: host trust state is unreadable from
            # here, and a missing read root is already reported above.
            if entry.scope == "project" and entry.gates and delivered:
                issues.extend(
                    _skill_delivery_warning(
                        "SKILL-DISCOVERY-GATED",
                        platform.skill_read_root,
                        f"{platform_id} discovers {entry.path} only behind "
                        f"{' + '.join(entry.gates)}; until then the skills on "
                        "disk stay invisible to the host",
                    )
                )
        issues.extend(
            _legacy_machine_skills_issues(
                platform_id, read_root if delivered else None, facts
            )
        )
    return issues


def _all_check_result(repo_root: Path) -> dict[str, object]:
    host_issues = _host_issues(repo_root)
    runtime_errors = check_runtime(repo_root)
    distribution_errors = check_distribution(repo_root)
    language_issues = check_language(repo_root)
    task_hygiene_issues = check_task_hygiene(repo_root)
    state_recovery_issues = check_state_recovery(repo_root)
    session_hygiene_issues = check_session_hygiene(repo_root)
    mcp_issues = check_mcp_registration(repo_root)
    dsh_preset_issues = check_dsh_preset(repo_root)
    kimi_hook_issues = check_kimi_hook(repo_root)
    qoder_plugin_issues = check_qoder_plugin(repo_root)
    codex_plugin_issues = check_codex_plugin(repo_root)
    claude_code_plugin_issues = check_claude_code_plugin(repo_root)
    opencode_plugin_issues = check_opencode_plugin(repo_root)
    zcode_plugin_issues = check_zcode_plugin(repo_root)
    kimi_code_plugin_issues = check_kimi_code_plugin(repo_root)
    skill_delivery_issues = check_skill_delivery(repo_root)
    errors: list[dict[str, object]] = []
    for issue in host_issues:
        errors.append({"kind": "host_adapter", **issue})
    errors.extend(
        {"kind": "runtime", "message": error}
        for error in runtime_errors
    )
    errors.extend(
        {"kind": "distribution", "message": error}
        for error in distribution_errors
    )
    errors.extend(
        {"kind": "language", **issue}
        for issue in language_issues
        if issue["severity"] == "error"
    )
    return {
        "ok": not errors,
        "errors": errors,
        "issues": {
            "hostAdapters": host_issues,
            "language": language_issues,
            "taskHygiene": task_hygiene_issues,
            "stateRecovery": state_recovery_issues,
            "sessionHygiene": session_hygiene_issues,
            "mcpRegistration": mcp_issues,
            "dshPreset": dsh_preset_issues,
            "kimiHook": kimi_hook_issues,
            "qoderPlugin": qoder_plugin_issues,
            "codexPlugin": codex_plugin_issues,
            "claudeCodePlugin": claude_code_plugin_issues,
            "opencodePlugin": opencode_plugin_issues,
            "zcodePlugin": zcode_plugin_issues,
            "kimiCodePlugin": kimi_code_plugin_issues,
            "skillDelivery": skill_delivery_issues,
        },
    }


def _run_checks(repo_root: Path, *, structured: bool = False) -> int:
    result = _all_check_result(repo_root)
    errors = result["errors"]
    if structured:
        print(json.dumps(result, ensure_ascii=False))
        return 1 if errors else 0
    for issue in result["issues"]["language"]:
        if issue["severity"] == "error":
            continue
        print(f"Language ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    _print_task_hygiene_issues(result["issues"]["taskHygiene"])
    _print_state_recovery_issues(result["issues"]["stateRecovery"])
    _print_session_hygiene_issues(result["issues"]["sessionHygiene"])
    for issue in result["issues"]["mcpRegistration"]:
        print(f"MCP ({issue['status']}): {issue['message']}")
    for issue in result["issues"]["dshPreset"]:
        print(f"DSH preset ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["kimiHook"]:
        print(f"Kimi hook ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["qoderPlugin"]:
        print(f"Qoder plugin ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["codexPlugin"]:
        print(f"Codex plugin ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["claudeCodePlugin"]:
        print(f"Claude Code plugin ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["opencodePlugin"]:
        print(f"OpenCode plugin ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["zcodePlugin"]:
        print(f"ZCode plugin ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["kimiCodePlugin"]:
        print(f"Kimi Code plugin ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    for issue in result["issues"]["skillDelivery"]:
        print(f"Skill delivery ({issue['code']}): {issue['message']}")
        if issue.get("commandHint"):
            print(f"  fix: {issue['commandHint']}")
    if errors:
        for error in errors:
            print(f"ERROR: {error['message']}", file=sys.stderr)
        return 1
    print("runtime health checks passed")
    return 0


def _run_host_checks(repo_root: Path, *, structured: bool = False) -> int:
    issues = _host_issues(repo_root)
    if structured:
        print(json.dumps({"issues": issues}, ensure_ascii=False))
        return 1 if issues else 0
    errors = [issue["message"] for issue in issues]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("host adapter checks passed")
    return 0


def _run_runtime_checks(repo_root: Path) -> int:
    errors = check_runtime(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("runtime safety checks passed")
    return 0


def _run_task_hygiene_checks(repo_root: Path, *, structured: bool = False) -> int:
    issues = check_task_hygiene(repo_root)
    if structured:
        print(json.dumps({"issues": issues}, ensure_ascii=False))
        return 0
    if issues:
        _print_task_hygiene_issues(issues)
    else:
        print("task hygiene checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="cowork-flow diagnostics")
    parser.add_argument("--all", action="store_true", help="Run all structured health checks")
    parser.add_argument("--subagent-safety", action="store_true", help="Run runtime safety checks")
    parser.add_argument("--host-adapters", action="store_true", help="Run host asset checks")
    parser.add_argument("--task-hygiene", action="store_true", help="Report stale task hygiene issues")
    parser.add_argument("--json", action="store_true", help="Render machine-readable diagnostics where supported")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = get_repo_root()
    if args.all:
        return _run_checks(repo_root, structured=bool(args.json))
    if args.host_adapters:
        return _run_host_checks(repo_root, structured=bool(args.json))
    if args.subagent_safety:
        return _run_runtime_checks(repo_root)
    if args.task_hygiene:
        return _run_task_hygiene_checks(repo_root, structured=bool(args.json))
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
