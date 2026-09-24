#!/usr/bin/env python3
"""Structured cowork-flow distribution and runtime health checks."""

from __future__ import annotations

import argparse
import json
import os
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
    tasks_dir = repo_root / ".cowork-flow" / "tasks"
    if not tasks_dir.is_dir():
        return []
    bound_tasks = _session_task_paths(repo_root)
    issues: list[dict[str, str]] = []
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir() or task_dir.name == "archive":
            continue
        task = _task_path(repo_root, task_dir)
        data = _task_metadata(task_dir / "task.json")
        status = str(data.get("status") or "unknown")
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


def check_spec_checks(repo_root: Path) -> list[dict[str, str]]:
    """Spec-check declaration health: parse errors and command entry
    existence. Execution belongs to `run spec-check`; doctor only proves
    the declarations can run, before a completion gate finds out they
    cannot."""
    issues: list[dict[str, str]] = []
    import shutil

    try:
        from services.spec_check import collect_spec_declarations
    except Exception as error:
        return [
            {
                "kind": "spec-checks",
                "spec": "",
                "message": f"spec-check service unavailable: {error}",
            }
        ]
    for spec_decls in collect_spec_declarations(repo_root):
        for message in spec_decls.errors:
            issues.append(
                {"kind": "spec-checks", "spec": spec_decls.spec, "message": message}
            )
        for decl in spec_decls.decls:
            entry = (decl.cmd_win if sys.platform == "win32" else decl.cmd) or decl.cmd
            first_token = entry.split()[0] if entry.split() else ""
            if not first_token:
                issues.append(
                    {
                        "kind": "spec-checks",
                        "spec": spec_decls.spec,
                        "message": f"empty command declaration: {decl.cmd!r}",
                    }
                )
                continue
            if shutil.which(first_token) is None:
                issues.append(
                    {
                        "kind": "spec-checks",
                        "spec": spec_decls.spec,
                        "message": f"command entry not found: {first_token}",
                    }
                )
    return issues


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


def _dsh_preset_dir() -> Path:
    base = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    return Path(base) / ".agent-presets" / "cowork-flow"


def check_dsh_preset(repo_root: Path) -> list[dict[str, str]]:
    """DSH preset freshness. Advisory only, and silent when the preset is
    absent: it is a machine-level asset installed once, so it does not
    update with npm or sync. Report an unknown or stale installed version
    instead of assuming the injection logic matches this project."""
    preset_dir = _dsh_preset_dir()
    if not preset_dir.is_dir():
        return []
    marker = preset_dir / ".cowork-flow-preset.json"
    if not marker.is_file():
        return [
            _issue(
                code="PRESET-UNKNOWN-VERSION",
                severity="warning",
                path=str(marker),
                message=(
                    "DSH preset is installed without a version marker; its "
                    "injection logic may predate the current release"
                ),
                command_hint="cwf host add dsh --component preset --force",
                contract="runtime-health:dsh-preset",
            )
        ]
    recorded: object = None
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError, ValueError, AttributeError):
        recorded = None
    if not isinstance(recorded, str) or not recorded:
        return [
            _issue(
                code="PRESET-UNKNOWN-VERSION",
                severity="warning",
                path=str(marker),
                message=(
                    "DSH preset version marker is unreadable; its injection "
                    "logic may predate the current release"
                ),
                command_hint="cwf host add dsh --component preset --force",
                contract="runtime-health:dsh-preset",
            )
        ]
    try:
        project_version = (
            repo_root / DIR_WORKFLOW / ".version"
        ).read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not project_version or recorded == project_version:
        return []
    return [
        _issue(
            code="PRESET-STALE",
            severity="warning",
            path=str(marker),
            message=(
                f"DSH preset was installed from {recorded} but this project "
                f"runs {project_version}; the preset does not update with "
                "sync or npm, so injection may lag the project runtime"
            ),
            command_hint="cwf host add dsh --component preset --force",
            contract="runtime-health:dsh-preset",
        )
    ]


def _project_version(repo_root: Path) -> str:
    try:
        return (
            repo_root / DIR_WORKFLOW / ".version"
        ).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


_HOOK_START_MARK = "# cowork-flow: kimi hook start."
_KIMI_HOOK_MARKER = ".cowork-flow-kimi-hook.json"
_KIMI_HOOK_CONTRACT = "runtime-health:kimi-hook"


def _kimi_home() -> Path:
    return Path(os.environ.get("KIMI_CODE_HOME") or (Path.home() / ".kimi-code"))


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


def _marker_version(marker: Path) -> str | None:
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError, ValueError, AttributeError):
        return None
    return recorded if isinstance(recorded, str) and recorded else None


def check_kimi_hook(repo_root: Path) -> list[dict[str, str]]:
    """Kimi Code hook health. Advisory only, and silent while Kimi Code is
    not configured at all: the hook is a machine-level asset installed once
    into the user-level config.toml, so it does not update with npm or sync.
    Report an unknown or stale installed version instead of assuming the
    injection logic matches this project."""
    home = _kimi_home()
    config = home / "config.toml"
    try:
        config_text = config.read_text(encoding="utf-8")
    except OSError:
        return []
    if _HOOK_START_MARK not in config_text:
        return _kimi_hook_warning(
            "HOOK-NOT-INSTALLED",
            config,
            "Kimi Code is configured but no cowork-flow hook is registered; "
            "sessions inject no workflow context",
            "cwf host add kimi-code",
        )
    shim = home / "hooks" / "cowork-flow-inject.mjs"
    if not shim.is_file():
        return _kimi_hook_warning(
            "HOOK-SHIM-MISSING",
            shim,
            "config.toml registers the cowork-flow hook but its shim is "
            "missing; the host runs a command that cannot start",
            "cwf host add kimi-code",
        )
    marker = home / "hooks" / _KIMI_HOOK_MARKER
    if not marker.is_file():
        return _kimi_hook_warning(
            "HOOK-UNKNOWN-VERSION",
            marker,
            "Kimi Code hook is installed without a version marker; its "
            "injection logic may predate the current release",
            "cwf host add kimi-code",
        )
    recorded = _marker_version(marker)
    if recorded is None:
        return _kimi_hook_warning(
            "HOOK-UNKNOWN-VERSION",
            marker,
            "Kimi Code hook version marker is unreadable; its injection logic "
            "may predate the current release",
            "cwf host add kimi-code",
        )
    project_version = _project_version(repo_root)
    if not project_version or recorded == project_version:
        return []
    return _kimi_hook_warning(
        "HOOK-STALE",
        marker,
        f"Kimi Code hook was installed from {recorded} but this project runs "
        f"{project_version}; the hook does not update with sync or npm, so "
        "injection may lag the project runtime",
        "cwf host add kimi-code",
    )


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


def _qoder_home() -> Path:
    configured = (os.environ.get("QODER_CONFIG_DIR") or "").strip()
    return Path(configured) if configured else Path.home() / ".qoder"


def _qoder_registry_entry(registry_path: Path) -> dict[str, object] | None:
    """The first registry entry cowork-flow owns, or None.

    Qoder documents this file's shape nowhere, so an unreadable or unexpected
    file is reported as "not installed" rather than trusted.
    """
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    plugins = registry.get("plugins") if isinstance(registry, dict) else None
    entries = plugins.get(QODER_PLUGIN_KEY) if isinstance(plugins, dict) else None
    if isinstance(entries, list) and entries and isinstance(entries[0], dict):
        return entries[0]
    return None


def _payload_manifest(platform_id: str, repo_root: Path) -> str | None:
    """Plugin manifest path inside a host's payload, taken from the host asset
    manifest declaration. Returns None when the declaration cannot be read, so a
    caller falls back to its own literal instead of skipping the check."""
    try:
        manifest = load_host_manifest(_distribution_root(repo_root))
        platform = manifest.platform(platform_id)
    except HostManifestError:
        return None
    return platform.payload.manifest if platform.payload else None


def check_qoder_plugin(repo_root: Path) -> list[dict[str, str]]:
    """Qoder plugin health. Advisory, and silent while the project never
    selected the Qoder host: the plugin is a machine-level asset installed once
    into `~/.qoder/plugins`, so it never updates through sync or npm."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "qoder" / "adapter.yaml"
    if not adapter.is_file():
        return []

    home = _qoder_home()
    registry_path = home / "plugins" / "installed_plugins_v2.json"
    entry = _qoder_registry_entry(registry_path)
    if entry is None:
        return _qoder_warning(
            "PLUGIN-NOT-INSTALLED",
            registry_path,
            "this project declares the Qoder host, but cowork-flow is not "
            "registered in the Qoder plugin cache, so Qoder sessions inject no "
            "workflow context; loading also needs a Qoder restart and a "
            "trusted workspace",
            "cwf host add qoder",
        )

    install_path = Path(str(entry.get("installPath") or ""))
    manifest_relative = _payload_manifest("qoder", repo_root) or ".qoder-plugin/plugin.json"
    if not (install_path / manifest_relative).is_file():
        return _qoder_warning(
            "PLUGIN-PAYLOAD-MISSING",
            install_path / manifest_relative,
            f"the Qoder plugin registry points at {install_path}, but no "
            "manifest is on disk there; the host cannot load a missing payload",
            "cwf host add qoder --force",
        )
    for relative in ("hooks/hooks.json", "hooks/inject-context.py"):
        if not (install_path / relative).is_file():
            return _qoder_warning(
                "PLUGIN-PAYLOAD-INCOMPLETE",
                install_path / relative,
                "the installed Qoder plugin has no hook payload, so every hook "
                "command it declares fails to start",
                "cwf host add qoder --force",
            )

    settings_path = home / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        settings = {}
    enabled = settings.get("enabledPlugins") if isinstance(settings, dict) else None
    if not isinstance(enabled, dict) or enabled.get(QODER_PLUGIN_KEY) is not True:
        return _qoder_warning(
            "PLUGIN-DISABLED",
            settings_path,
            'the Qoder plugin is installed but not enabled '
            f'(`enabledPlugins["{QODER_PLUGIN_KEY}"]`); no hook fires',
            "cwf host add qoder --force",
        )

    recorded = str(entry.get("version") or "")
    project_version = _project_version(repo_root)
    if project_version and recorded != project_version:
        return _qoder_warning(
            "PLUGIN-STALE",
            registry_path,
            f"the Qoder plugin was installed from {recorded or 'an unknown version'} "
            f"but this project runs {project_version}; the plugin does not update "
            "with sync or npm, so injection may lag the project runtime",
            "cwf host add qoder --force",
        )
    return []


_CLAUDE_CODE_PLUGIN_CONTRACT = "runtime-health:claude-code-plugin"
_CLAUDE_CODE_PLUGIN_NAME = "cowork-flow"
_CLAUDE_CODE_SKILL = "skills/cowork-flow-bootstrap/SKILL.md"


def _claude_home() -> Path:
    configured = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
    return Path(configured) if configured else Path.home() / ".claude"


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

    install_path = _claude_home() / "skills" / _CLAUDE_CODE_PLUGIN_NAME
    manifest_relative = _payload_manifest(
        "claude-code", repo_root
    ) or ".claude-plugin/plugin.json"
    manifest_path = install_path / manifest_relative
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        manifest = None
    if not isinstance(manifest, dict):
        return _claude_code_warning(
            "PLUGIN-NOT-INSTALLED",
            install_path,
            "this project declares the Claude Code host, but no cowork-flow "
            "skills-directory plugin is installed, so Claude Code sessions see "
            "no cowork-flow plugin Skill",
            "cwf host add claude-code",
        )
    if manifest.get("name") != _CLAUDE_CODE_PLUGIN_NAME:
        # A hand-made folder at the same path is not cowork-flow's to report on.
        return []

    if not (install_path / _CLAUDE_CODE_SKILL).is_file():
        return _claude_code_warning(
            "PLUGIN-PAYLOAD-INCOMPLETE",
            install_path / _CLAUDE_CODE_SKILL,
            "the installed Claude Code plugin carries no bootstrap Skill, so it "
            "contributes nothing in a repository without a runtime",
            "cwf host add claude-code --force",
        )

    recorded = str(manifest.get("version") or "")
    project_version = _project_version(repo_root)
    if project_version and recorded != project_version:
        return _claude_code_warning(
            "PLUGIN-STALE",
            manifest_path,
            f"the Claude Code plugin was installed from {recorded or 'an unknown version'} "
            f"but this project runs {project_version}; the plugin does not update "
            "with sync or npm",
            "cwf host add claude-code --force",
        )
    return []


_OPENCODE_PLUGIN_CONTRACT = "runtime-health:opencode-plugin"
_OPENCODE_PLUGIN_FILE = "plugins/cowork-flow.js"
_OPENCODE_PLUGIN_MARKER = "CoworkFlowPlugin"
_OPENCODE_CORE = "cowork-flow/plugin-core.js"
_OPENCODE_SKILL = "cowork-flow/skills/cowork-flow-bootstrap/SKILL.md"


def _opencode_home() -> Path:
    configured = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
    base = Path(configured) if configured else Path.home() / ".config"
    return base / "opencode"


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
    """OpenCode plugin health. Advisory, and silent while the project never
    selected the OpenCode host: the plugin is a machine-level asset installed
    once into the user's config directory, so it never updates through sync or
    npm.

    OpenCode's plugin format carries no manifest, so there is no version to
    compare. Staleness is judged against the project's own copy of the same two
    files instead: they are the same source delivered twice, so a difference
    means one of them was updated and the other was not."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "opencode" / "adapter.yaml"
    if not adapter.is_file():
        return []

    home = _opencode_home()
    plugin = home / _OPENCODE_PLUGIN_FILE
    try:
        installed = plugin.read_text(encoding="utf-8")
    except OSError:
        return _opencode_warning(
            "PLUGIN-NOT-INSTALLED",
            plugin,
            "this project declares the OpenCode host, but no cowork-flow plugin "
            "is installed in the OpenCode config directory, so OpenCode sessions "
            "see no cowork-flow plugin Skill",
            "cwf host add opencode",
        )
    if _OPENCODE_PLUGIN_MARKER not in installed:
        # A same-named file a user put there is not cowork-flow's to report on.
        return []

    for relative in (_OPENCODE_CORE, _OPENCODE_SKILL):
        if not (home / relative).is_file():
            return _opencode_warning(
                "PLUGIN-PAYLOAD-INCOMPLETE",
                home / relative,
                f"the installed OpenCode plugin is missing {relative}, so it "
                "registers a skills directory that is not there",
                "cwf host add opencode --force",
            )

    for relative in (_OPENCODE_PLUGIN_FILE, _OPENCODE_CORE):
        project_copy = repo_root / ".opencode" / relative
        if not project_copy.is_file():
            # The project has not been initialized with its own copy yet.
            continue
        try:
            project_text = project_copy.read_text(encoding="utf-8")
        except OSError:
            continue
        installed_text = (
            installed
            if relative == _OPENCODE_PLUGIN_FILE
            else (home / relative).read_text(encoding="utf-8")
        )
        if project_text != installed_text:
            return _opencode_warning(
                "PLUGIN-STALE",
                home / relative,
                f"the installed OpenCode {relative} differs from this project's "
                "copy of the same file; one of them was updated and the other "
                "was not, and the plugin does not update with sync or npm",
                "cwf host add opencode --force",
            )
    return []


_CODEX_PLUGIN_CONTRACT = "runtime-health:codex-plugin"
CODEX_PLUGIN_KEY = "cowork-flow@cowork-flow-local"
_CODEX_MARKETPLACE = "cowork-flow-local"


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


def _codex_home() -> Path:
    configured = (os.environ.get("CODEX_HOME") or "").strip()
    return Path(configured) if configured else Path.home() / ".codex"


def _codex_config_sections(config_path: Path) -> dict[str, dict[str, str]]:
    """Flat key/value pairs for the two sections cowork-flow owns.

    The CI floor is Python 3.10, which has no tomllib, and a TOML dependency is
    not worth two flat sections: every other line and section stays unread.
    """
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    wanted = {
        f"marketplaces.{_CODEX_MARKETPLACE}",
        f"plugins.{CODEX_PLUGIN_KEY}",
    }
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip().replace('"', "")
            current = sections.setdefault(name, {}) if name in wanted else None
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.partition("=")
        current[key.strip().strip('"').strip("'")] = value.strip().strip('"').strip("'")
    return sections


def _codex_marketplace_source() -> str:
    """Marketplace source path registered in the Codex config, or ""."""
    sections = _codex_config_sections(_codex_home() / "config.toml")
    return sections.get(f"marketplaces.{_CODEX_MARKETPLACE}", {}).get("source", "")


def check_codex_plugin(repo_root: Path) -> list[dict[str, str]]:
    """Codex plugin health. Advisory, and silent while the project never
    selected the Codex host: the plugin is a machine-level asset registered in
    `~/.codex/config.toml`, so it never updates through sync or npm."""
    adapter = repo_root / DIR_WORKFLOW / "adapters" / "codex" / "adapter.yaml"
    if not adapter.is_file():
        return []

    config_path = _codex_home() / "config.toml"
    sections = _codex_config_sections(config_path)
    marketplace = sections.get(f"marketplaces.{_CODEX_MARKETPLACE}")
    if not marketplace:
        return _codex_warning(
            "PLUGIN-NOT-INSTALLED",
            config_path,
            "this project declares the Codex host, but cowork-flow's marketplace "
            "is not registered in the Codex config, so Codex sessions see no "
            "cowork-flow plugin Skills",
            "cwf host add codex",
        )

    source = marketplace.get("source", "")
    payload = (Path(source) / "plugins" / "cowork-flow") if source else None
    manifest_relative = _payload_manifest("codex", repo_root) or ".codex-plugin/plugin.json"
    if payload is None or not (payload / manifest_relative).is_file():
        return _codex_warning(
            "PLUGIN-PAYLOAD-MISSING",
            payload if payload is not None else config_path,
            f"the Codex marketplace is registered from {source or 'an unknown path'}, "
            "but no plugin manifest is on disk there; the host cannot load a "
            "missing payload",
            "cwf host add codex --force",
        )

    plugin = sections.get(f"plugins.{CODEX_PLUGIN_KEY}")
    if not plugin or plugin.get("enabled") != "true":
        return _codex_warning(
            "PLUGIN-DISABLED",
            config_path,
            "the Codex plugin is registered but not enabled "
            f'(`[plugins."{CODEX_PLUGIN_KEY}"] enabled = true`), so its Skills '
            "stay invisible to sessions",
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


def _machine_plugin_payload(platform_id: str) -> Path | None:
    """Payload root of a host's machine-level plugin, or None when that host
    keeps no readable install. Mirrors where the install commands write."""
    if platform_id == "qoder":
        entry = _qoder_registry_entry(
            _qoder_home() / "plugins" / "installed_plugins_v2.json"
        )
        payload = Path(str(entry.get("installPath") or "")) if entry else None
        return payload if payload is not None and payload.is_dir() else None
    if platform_id == "zcode":
        home = Path(os.environ.get("ZCODE_HOME") or (Path.home() / ".zcode"))
        marketplace = (
            home
            / "cli"
            / "plugins"
            / "marketplaces"
            / "cowork-flow-local"
            / "marketplace.json"
        )
        try:
            data = json.loads(marketplace.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        plugins = data.get("plugins") if isinstance(data, dict) else None
        for plugin in plugins if isinstance(plugins, list) else ():
            source = plugin.get("source") if isinstance(plugin, dict) else None
            path = source.get("path") if isinstance(source, dict) else None
            payload = Path(str(path)) if path else None
            if payload is not None and payload.is_dir():
                return payload
        return None
    if platform_id == "codex":
        source = _codex_marketplace_source()
        if not source:
            return None
        payload = Path(source) / "plugins" / "cowork-flow"
        return payload if payload.is_dir() else None
    return None


def _legacy_machine_skills_issues(
    platform_id: str, project_skills: Path | None
) -> list[dict[str, str]]:
    """Warnings for a host whose machine-level plugin still carries a copy of a
    Skill this project also ships. The payload is bootstrap-only, so a
    same-named copy is a leftover that may come from another release; a payload
    Skill the project does not ship (the bootstrap guide) is expected and stays
    silent."""
    payload = _machine_plugin_payload(platform_id)
    if payload is None:
        return []
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
    issues: list[dict[str, str]] = []
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
            _legacy_machine_skills_issues(platform_id, read_root if delivered else None)
        )
    return issues


def _all_check_result(repo_root: Path) -> dict[str, object]:
    host_issues = _host_issues(repo_root)
    runtime_errors = check_runtime(repo_root)
    distribution_errors = check_distribution(repo_root)
    task_hygiene_issues = check_task_hygiene(repo_root)
    state_recovery_issues = check_state_recovery(repo_root)
    session_hygiene_issues = check_session_hygiene(repo_root)
    spec_check_issues = check_spec_checks(repo_root)
    mcp_issues = check_mcp_registration(repo_root)
    dsh_preset_issues = check_dsh_preset(repo_root)
    kimi_hook_issues = check_kimi_hook(repo_root)
    qoder_plugin_issues = check_qoder_plugin(repo_root)
    codex_plugin_issues = check_codex_plugin(repo_root)
    claude_code_plugin_issues = check_claude_code_plugin(repo_root)
    opencode_plugin_issues = check_opencode_plugin(repo_root)
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
    errors.extend({"kind": "spec-checks", **issue} for issue in spec_check_issues)
    return {
        "ok": not errors,
        "errors": errors,
        "issues": {
            "hostAdapters": host_issues,
            "taskHygiene": task_hygiene_issues,
            "stateRecovery": state_recovery_issues,
            "sessionHygiene": session_hygiene_issues,
            "specChecks": spec_check_issues,
            "mcpRegistration": mcp_issues,
            "dshPreset": dsh_preset_issues,
            "kimiHook": kimi_hook_issues,
            "qoderPlugin": qoder_plugin_issues,
            "codexPlugin": codex_plugin_issues,
            "claudeCodePlugin": claude_code_plugin_issues,
            "opencodePlugin": opencode_plugin_issues,
            "skillDelivery": skill_delivery_issues,
        },
    }


def _run_checks(repo_root: Path, *, structured: bool = False) -> int:
    result = _all_check_result(repo_root)
    errors = result["errors"]
    if structured:
        print(json.dumps(result, ensure_ascii=False))
        return 1 if errors else 0
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
