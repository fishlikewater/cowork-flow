"""Distributed Skill manifest discovery and validation.

Each Skill owns only its own actions, commands, and context rules.  The
loader combines those declarations at the boundary and fails closed when an
action has no unique owner or when replicas disagree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Any


class SkillManifestError(RuntimeError):
    """Raised when distributed Skill metadata cannot be trusted."""


@dataclass(frozen=True)
class SkillAction:
    skill: str
    action_id: str
    label: str
    lifecycle_check: str | None
    mutates_state: bool
    command: str | None
    diagnostics_command: str | None


@dataclass(frozen=True)
class SkillContextRule:
    skill: str
    contexts: tuple[str, ...]
    dev_types: tuple[str, ...]
    path_patterns: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SkillCommand:
    skill: str
    name: str
    aliases: tuple[str, ...]
    script: str
    script_path: Path
    script_digest: str


@dataclass(frozen=True)
class SkillManifest:
    skill: str
    path: Path
    actions: tuple[SkillAction, ...]
    context_rules: tuple[SkillContextRule, ...]
    commands: tuple[SkillCommand, ...]


def _reject_unknown_fields(
    value: dict[str, Any],
    *,
    allowed: frozenset[str],
    scope: str,
    path: Path,
) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise SkillManifestError(
            f"unexpected {scope} field(s): {', '.join(unexpected)}: {path}"
        )


def skill_roots(repo_root: Path) -> tuple[Path, ...]:
    root = Path(repo_root)
    roots = [
        root / ".agents" / "skills",
        root / ".claude" / "skills",
        root / "skills",
        root / "template" / "skills",
    ]
    source_template = Path(__file__).resolve().parents[3] / "skills"
    if source_template not in roots:
        roots.append(source_template)
    return tuple(roots)


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _strings(
    value: object,
    *,
    field: str,
    path: Path,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SkillManifestError(f"manifest context {field} must be a list: {path}")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SkillManifestError(
                f"manifest context {field} must contain non-empty strings: {path}"
            )
        items.append(item.strip())
    return tuple(items)


def _parse_manifest(path: Path, raw: dict[str, Any]) -> SkillManifest:
    _reject_unknown_fields(
        raw,
        allowed=frozenset({"schemaVersion", "skill", "actions", "context", "commands"}),
        scope="Skill manifest",
        path=path,
    )
    schema_version = raw.get("schemaVersion")
    if type(schema_version) is not int or schema_version != 1:
        raise SkillManifestError(
            f"unsupported Skill manifest schemaVersion: {schema_version}: {path}"
        )
    skill = raw.get("skill")
    if not isinstance(skill, str) or not skill.strip():
        raise SkillManifestError(f"manifest missing skill: {path}")
    skill = skill.strip()
    if skill != path.parent.name:
        raise SkillManifestError(
            f"manifest skill does not match directory: {skill} != {path.parent.name}: {path}"
        )

    actions: list[SkillAction] = []
    raw_actions = raw.get("actions", [])
    if not isinstance(raw_actions, list):
        raise SkillManifestError(f"manifest actions must be a list: {path}")
    for item in raw_actions:
        if not isinstance(item, dict):
            raise SkillManifestError(f"manifest action must be an object: {path}")
        _reject_unknown_fields(
            item,
            allowed=frozenset(
                {
                    "id",
                    "label",
                    "lifecycleCheck",
                    "mutatesState",
                    "command",
                    "diagnosticsCommand",
                }
            ),
            scope="manifest action",
            path=path,
        )
        action_id = item.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            raise SkillManifestError(f"manifest action id is missing: {path}")
        label = item.get("label", action_id)
        if not isinstance(label, str) or not label.strip():
            raise SkillManifestError(f"manifest action label is invalid: {path}")
        lifecycle_check = item.get("lifecycleCheck")
        if lifecycle_check is not None and not isinstance(lifecycle_check, str):
            raise SkillManifestError(f"manifest lifecycleCheck is invalid: {path}")
        mutates_state = item.get("mutatesState", False)
        if not isinstance(mutates_state, bool):
            raise SkillManifestError(f"manifest mutatesState is invalid: {path}")
        command = item.get("command")
        if command is not None and not isinstance(command, str):
            raise SkillManifestError(f"manifest command is invalid: {path}")
        diagnostics_command = item.get("diagnosticsCommand")
        if diagnostics_command is not None and not isinstance(diagnostics_command, str):
            raise SkillManifestError(f"manifest diagnosticsCommand is invalid: {path}")
        actions.append(
            SkillAction(
                skill=skill,
                action_id=action_id.strip(),
                label=label.strip(),
                lifecycle_check=lifecycle_check.strip() if isinstance(lifecycle_check, str) else None,
                mutates_state=mutates_state,
                command=command.strip() if isinstance(command, str) else None,
                diagnostics_command=(
                    diagnostics_command.strip()
                    if isinstance(diagnostics_command, str)
                    else None
                ),
            )
        )

    context_rules: list[SkillContextRule] = []
    raw_context = raw.get("context", [])
    if not isinstance(raw_context, list):
        raise SkillManifestError(f"manifest context must be a list: {path}")
    for item in raw_context:
        if not isinstance(item, dict):
            raise SkillManifestError(f"manifest context rule must be an object: {path}")
        _reject_unknown_fields(
            item,
            allowed=frozenset(
                {"contexts", "devTypes", "pathPatterns", "reason"}
            ),
            scope="manifest context",
            path=path,
        )
        contexts = _strings(
            item.get("contexts", ["implement"]),
            field="contexts",
            path=path,
        )
        patterns = _strings(
            item.get("pathPatterns", []),
            field="pathPatterns",
            path=path,
        )
        dev_types = _strings(
            item.get("devTypes", []),
            field="devTypes",
            path=path,
        )
        reason = item.get("reason", f"Auto-routed {skill} Skill")
        if not isinstance(reason, str) or not reason.strip():
            raise SkillManifestError(f"manifest context reason is invalid: {path}")
        if not contexts:
            raise SkillManifestError(f"manifest context rule is empty: {path}")
        context_rules.append(
            SkillContextRule(
                skill=skill,
                contexts=contexts,
                dev_types=dev_types,
                path_patterns=patterns,
                reason=reason.strip(),
            )
        )

    commands: list[SkillCommand] = []
    raw_commands = raw.get("commands", [])
    if not isinstance(raw_commands, list):
        raise SkillManifestError(f"manifest commands must be a list: {path}")
    for item in raw_commands:
        if not isinstance(item, dict):
            raise SkillManifestError(f"manifest command must be an object: {path}")
        _reject_unknown_fields(
            item,
            allowed=frozenset({"name", "aliases", "script"}),
            scope="manifest command",
            path=path,
        )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SkillManifestError(f"manifest command name is missing: {path}")
        name = name.strip()

        raw_aliases = item.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise SkillManifestError(f"manifest command aliases must be a list: {path}")
        aliases: list[str] = []
        for alias in raw_aliases:
            if not isinstance(alias, str) or not alias.strip():
                raise SkillManifestError(f"manifest command alias is invalid: {path}")
            aliases.append(alias.strip())
        command_names = (name, *aliases)
        if len(set(command_names)) != len(command_names):
            raise SkillManifestError(f"manifest command alias is duplicated: {path}")

        script = item.get("script")
        if not isinstance(script, str) or not script.strip():
            raise SkillManifestError(f"manifest command script is missing: {path}")
        script = script.strip()
        script_reference = Path(script)
        if script_reference.is_absolute() or PureWindowsPath(script).is_absolute():
            raise SkillManifestError(f"manifest command script escapes Skill: {path}")
        skill_dir = path.parent.resolve()
        script_path = (skill_dir / script_reference).resolve()
        try:
            script_path.relative_to(skill_dir)
        except ValueError as error:
            raise SkillManifestError(
                f"manifest command script escapes Skill: {path}"
            ) from error
        if not script_path.is_file():
            raise SkillManifestError(
                f"manifest command script is missing: {script_path}"
            )
        try:
            script_digest = sha256(script_path.read_bytes()).hexdigest()
        except OSError as error:
            raise SkillManifestError(
                f"manifest command script is unreadable: {script_path}"
            ) from error
        commands.append(
            SkillCommand(
                skill=skill,
                name=name,
                aliases=tuple(aliases),
                script=script,
                script_path=script_path,
                script_digest=script_digest,
            )
        )
    if not actions and not context_rules and not commands:
        raise SkillManifestError(
            f"Skill manifest must declare at least one action, context rule, or command: {path}"
        )
    return SkillManifest(
        skill,
        path,
        tuple(actions),
        tuple(context_rules),
        tuple(commands),
    )


def _replica_precedence(repo_root: Path, manifest: SkillManifest) -> tuple[int, str]:
    root = Path(repo_root).resolve()
    source_template = Path(__file__).resolve().parents[3] / "skills"
    ordered_roots = (
        root / "template" / "skills",
        source_template,
        root / "skills",
        root / ".agents" / "skills",
        root / ".claude" / "skills",
    )
    manifest_path = manifest.path.resolve()
    for index, candidate in enumerate(ordered_roots):
        try:
            manifest_path.relative_to(candidate.resolve())
        except ValueError:
            continue
        return (index, str(manifest_path))
    return (len(ordered_roots), str(manifest_path))


def load_skill_manifests(repo_root: Path) -> tuple[SkillManifest, ...]:
    """Load valid Skill metadata and prefer tracked source replicas."""
    manifests: dict[str, list[SkillManifest]] = {}
    for root in skill_roots(repo_root):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/manifest.json")):
            raw = _read_manifest(path)
            if raw is None:
                raise SkillManifestError(f"invalid Skill manifest: {path}")
            manifest = _parse_manifest(path, raw)
            manifests.setdefault(manifest.skill, []).append(manifest)

    result: list[SkillManifest] = []
    for skill, replicas in sorted(manifests.items()):
        canonical = _manifest_signature(replicas[0])
        if any(_manifest_signature(replica) != canonical for replica in replicas[1:]):
            paths = ", ".join(str(replica.path) for replica in replicas)
            raise SkillManifestError(f"conflicting Skill manifest replicas: {skill}: {paths}")
        result.append(sorted(replicas, key=lambda replica: _replica_precedence(repo_root, replica))[0])
    command_owners: dict[str, str] = {}
    for manifest in result:
        for command in manifest.commands:
            for command_name in (command.name, *command.aliases):
                previous = command_owners.get(command_name)
                if previous is not None:
                    raise SkillManifestError(
                        f"Skill command has multiple owners: {command_name} "
                        f"({previous}, {command.skill})"
                    )
                command_owners[command_name] = command.skill
    return tuple(result)


def _manifest_signature(manifest: SkillManifest) -> tuple[object, ...]:
    return (
        tuple(
            (
                item.action_id,
                item.label,
                item.lifecycle_check,
                item.mutates_state,
                item.command,
                item.diagnostics_command,
            )
            for item in manifest.actions
        ),
        tuple(
            (item.contexts, item.dev_types, item.path_patterns, item.reason)
            for item in manifest.context_rules
        ),
        tuple(
            (item.name, item.aliases, item.script)
            for item in manifest.commands
        ),
    )


def action_owners(repo_root: Path) -> dict[str, SkillAction]:
    owners: dict[str, SkillAction] = {}
    for manifest in load_skill_manifests(repo_root):
        for action in manifest.actions:
            if action.action_id in owners:
                previous = owners[action.action_id]
                raise SkillManifestError(
                    f"workflow action has multiple owners: {action.action_id} "
                    f"({previous.skill}, {action.skill})"
                )
            owners[action.action_id] = action
    return owners


def context_entries(
    repo_root: Path,
    *,
    context: str,
    dev_type: str | None = None,
    paths: tuple[str, ...] = (),
    include_wildcard: bool = True,
) -> list[dict[str, str]]:
    normalized_dev_type = (dev_type or "").strip()
    normalized_paths = tuple(
        str(path).replace("\\", "/").removeprefix("./") for path in paths
    )
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for manifest in load_skill_manifests(repo_root):
        for rule in manifest.context_rules:
            if context not in rule.contexts:
                continue
            if (
                (not include_wildcard or "*" not in rule.dev_types)
                and normalized_dev_type not in rule.dev_types
                and not any(
                fnmatchcase(path, pattern)
                for path in normalized_paths
                for pattern in rule.path_patterns
                )
            ):
                continue
            skill_file = _skill_path(repo_root, manifest.skill)
            if skill_file in seen:
                continue
            seen.add(skill_file)
            entries.append({"file": skill_file, "reason": rule.reason})
    return entries


def skill_command_scripts(
    repo_root: Path,
    *,
    reserved_names: tuple[str, ...] = (),
) -> dict[str, Path]:
    commands: dict[str, Path] = {}
    reserved = set(reserved_names)
    for manifest in load_skill_manifests(repo_root):
        for command in manifest.commands:
            for command_name in (command.name, *command.aliases):
                if command_name in reserved:
                    raise SkillManifestError(
                        f"Skill command conflicts with reserved runtime command: "
                        f"{command_name} ({command.skill})"
                    )
                commands[command_name] = command.script_path
    return commands


def _skill_path(repo_root: Path, skill: str) -> str:
    root = Path(repo_root)
    if (root / ".claude").is_dir() and not (root / ".agents").is_dir():
        return f".claude/skills/{skill}/SKILL.md"
    return f".agents/skills/{skill}/SKILL.md"


def action_metadata(repo_root: Path, action_id: str) -> SkillAction | None:
    return action_owners(repo_root).get(action_id)
