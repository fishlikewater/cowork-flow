from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(".cowork-flow/spec/runtime/skill-registry.json")
KINDS = {"phase", "protocol", "domain", "mode", "runtime"}
VISIBILITIES = {"public", "internal"}
ENTRY_STATUSES = {"active", "disabled"}
WORKFLOW_STATUSES = {
    "no_task",
    "planning",
    "in_progress",
    "review",
    "completed",
    "delegated_subtask",
}
ENFORCEMENTS = {"advisory", "mandatory", "runtime"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
INTENT_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
REQUIRED_FIELDS = {
    "id",
    "displayName",
    "aliases",
    "kind",
    "visibility",
    "status",
    "statuses",
    "intents",
    "enforcement",
    "runtimeGate",
    "runtimeCommand",
    "evidenceArtifact",
    "source",
    "managedPaths",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {"readWhen"}


class SkillRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class SkillEntry:
    id: str
    display_name: str
    aliases: tuple[str, ...]
    kind: str
    visibility: str
    status: str
    statuses: tuple[str, ...]
    intents: tuple[str, ...]
    enforcement: str
    runtime_gate: str | None
    runtime_command: str | None
    evidence_artifact: str | None
    source: str
    managed_paths: tuple[str, ...]
    read_when_dev_types: tuple[str, ...]
    read_when_path_patterns: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "displayName": self.display_name,
            "aliases": list(self.aliases),
            "kind": self.kind,
            "visibility": self.visibility,
            "status": self.status,
            "statuses": list(self.statuses),
            "intents": list(self.intents),
            "enforcement": self.enforcement,
            "runtimeGate": self.runtime_gate,
            "runtimeCommand": self.runtime_command,
            "evidenceArtifact": self.evidence_artifact,
            "source": self.source,
            "managedPaths": list(self.managed_paths),
            "readWhen": {
                "devTypes": list(self.read_when_dev_types),
                "pathPatterns": list(self.read_when_path_patterns),
            },
        }


@dataclass(frozen=True)
class SkillRegistry:
    schema_version: int
    entries: tuple[SkillEntry, ...]
    _by_id: dict[str, SkillEntry] = field(init=False, repr=False)
    _aliases: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_id", {entry.id: entry for entry in self.entries})
        object.__setattr__(
            self,
            "_aliases",
            {
                alias: entry.id
                for entry in self.entries
                for alias in entry.aliases
            },
        )

    @property
    def public_entries(self) -> tuple[SkillEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.visibility == "public" and entry.status == "active"
        )

    @property
    def public_skill_ids(self) -> tuple[str, ...]:
        return tuple(entry.id for entry in self.public_entries)

    def entry(self, id_or_alias: str) -> SkillEntry:
        entry_id = (
            id_or_alias
            if id_or_alias in self._by_id
            else self._aliases.get(id_or_alias)
        )
        if entry_id is None:
            raise SkillRegistryError(f"unknown Skill Registry entry: {id_or_alias}")
        return self._by_id[entry_id]

    def domain_entries_for(
        self,
        *,
        dev_type: str | None,
        paths: tuple[str, ...] | list[str],
    ) -> tuple[SkillEntry, ...]:
        normalized_dev_type = (dev_type or "").strip()
        normalized_paths = tuple(
            str(path).replace("\\", "/").removeprefix("./")
            for path in paths
        )
        return tuple(
            entry
            for entry in self.entries
            if entry.kind == "domain"
            and entry.status == "active"
            and (
                normalized_dev_type in entry.read_when_dev_types
                or any(
                    fnmatchcase(path, pattern)
                    for path in normalized_paths
                    for pattern in entry.read_when_path_patterns
                )
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_skill_registry(
    template_root: Path,
    *,
    validate_sources: bool = True,
) -> SkillRegistry:
    path = Path(template_root) / REGISTRY_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillRegistryError(
            f"unable to read Skill Registry {path}: {exc}"
        ) from exc
    return create_skill_registry(
        raw,
        template_root,
        validate_sources=validate_sources,
    )


def create_skill_registry(
    raw: dict[str, Any],
    template_root: Path,
    *,
    validate_sources: bool = True,
) -> SkillRegistry:
    _validate_root(raw)
    entries = _normalize_entries(raw["entries"], Path(template_root), validate_sources)
    by_id = _validate_unique_tokens(entries)
    _validate_entry_semantics(entries, by_id)
    _validate_managed_paths(entries)
    return SkillRegistry(schema_version=1, entries=entries)


def _normalize_entries(
    raw_entries: list[Any],
    template_root: Path,
    validate_sources: bool,
) -> tuple[SkillEntry, ...]:
    return tuple(
        sorted(
            (
                _normalize_entry(
                    entry,
                    template_root,
                    validate_sources=validate_sources,
                )
                for entry in raw_entries
            ),
            key=lambda entry: entry.id,
        )
    )


def _validate_unique_tokens(entries: tuple[SkillEntry, ...]) -> dict[str, SkillEntry]:
    by_id: dict[str, SkillEntry] = {}
    tokens: set[str] = set()
    for entry in entries:
        for token in (entry.id, *entry.aliases):
            if token in tokens:
                raise SkillRegistryError(f"duplicate skill id or alias: {token}")
            tokens.add(token)
            if token == entry.id:
                by_id[token] = entry
    return by_id


def _validate_entry_semantics(
    entries: tuple[SkillEntry, ...],
    by_id: dict[str, SkillEntry],
) -> None:
    public_intents: set[str] = set()
    for entry in entries:
        _validate_runtime_gate(entry, by_id)
        _validate_runtime_enforcement(entry)
        _validate_public_intents(entry, public_intents)


def _validate_runtime_gate(
    entry: SkillEntry,
    by_id: dict[str, SkillEntry],
) -> None:
    if entry.enforcement == "mandatory" and entry.runtime_gate is None:
        raise SkillRegistryError(f"mandatory entry {entry.id} requires runtimeGate")
    if entry.runtime_gate is None:
        return
    gate = by_id.get(entry.runtime_gate)
    if gate is None or gate.kind != "runtime":
        raise SkillRegistryError(
            f"runtimeGate {entry.runtime_gate} must reference a runtime entry"
        )


def _validate_runtime_enforcement(entry: SkillEntry) -> None:
    if entry.kind == "runtime":
        if entry.visibility != "internal" or entry.enforcement != "runtime":
            raise SkillRegistryError(
                f"runtime entry {entry.id} must be internal with runtime enforcement"
            )
    elif entry.enforcement == "runtime":
        raise SkillRegistryError(
            f"non-runtime entry {entry.id} cannot use runtime enforcement"
        )


def _validate_public_intents(
    entry: SkillEntry,
    public_intents: set[str],
) -> None:
    if entry.visibility != "public" or entry.status != "active":
        return
    for intent in entry.intents:
        if intent in public_intents:
            raise SkillRegistryError(f"duplicate public intent: {intent}")
        public_intents.add(intent)


def _validate_root(raw: Any) -> None:
    if not isinstance(raw, dict):
        raise SkillRegistryError("Skill Registry must be an object")
    for key in raw:
        if key not in {"schemaVersion", "entries"}:
            raise SkillRegistryError(f"unexpected Skill Registry field: {key}")
    if raw.get("schemaVersion") != 1:
        raise SkillRegistryError(
            "unsupported Skill Registry schemaVersion: "
            f"{raw.get('schemaVersion')}"
        )
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SkillRegistryError(
            "Skill Registry entries must be a non-empty array"
        )


def _normalize_entry(
    raw: Any,
    template_root: Path,
    *,
    validate_sources: bool,
) -> SkillEntry:
    entry_id = _validate_entry_shape(raw)
    display_name = _display_name(raw["displayName"], entry_id)
    kind = _enum(raw["kind"], KINDS, entry_id, "kind")
    runtime_fields = _normalize_runtime_fields(raw, entry_id)
    source = _normalize_source(
        raw["source"],
        entry_id,
        template_root,
        validate_sources=validate_sources,
    )
    read_when_dev_types, read_when_path_patterns = _normalize_read_when(
        raw.get("readWhen"),
        entry_id,
        kind,
    )
    return SkillEntry(
        id=entry_id,
        display_name=display_name,
        aliases=_aliases(raw["aliases"], entry_id),
        kind=kind,
        visibility=_enum(raw["visibility"], VISIBILITIES, entry_id, "visibility"),
        status=_enum(raw["status"], ENTRY_STATUSES, entry_id, "status"),
        statuses=_workflow_statuses(raw["statuses"], entry_id),
        intents=_intents(raw["intents"], entry_id),
        enforcement=runtime_fields["enforcement"],
        runtime_gate=runtime_fields["runtime_gate"],
        runtime_command=runtime_fields["runtime_command"],
        evidence_artifact=runtime_fields["evidence_artifact"],
        source=source,
        managed_paths=_managed_paths(raw["managedPaths"], entry_id),
        read_when_dev_types=read_when_dev_types,
        read_when_path_patterns=read_when_path_patterns,
    )


def _validate_entry_shape(raw: Any) -> str:
    if not isinstance(raw, dict):
        raise SkillRegistryError("Skill Registry entry must be an object")
    entry_id = raw.get("id") if isinstance(raw.get("id"), str) else "<unknown>"
    for name in REQUIRED_FIELDS:
        if name not in raw:
            raise SkillRegistryError(
                f"entry {entry_id} missing required field: {name}"
            )
    for name in raw:
        if name not in ALLOWED_FIELDS:
            raise SkillRegistryError(f"unexpected field for {entry_id}: {name}")
    if not isinstance(raw["id"], str) or not ID_PATTERN.fullmatch(raw["id"]):
        raise SkillRegistryError(f"invalid id: {raw['id']}")
    return raw["id"]


def _display_name(value: Any, entry_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SkillRegistryError(
            f"displayName for {entry_id} must be a non-empty string"
        )
    return value.strip()


def _aliases(value: Any, entry_id: str) -> tuple[str, ...]:
    aliases = _string_tuple(value, entry_id, "aliases")
    for alias in aliases:
        if not ID_PATTERN.fullmatch(alias):
            raise SkillRegistryError(
                f"invalid alias for {entry_id}: {alias}"
            )
    return tuple(sorted(set(aliases)))


def _workflow_statuses(value: Any, entry_id: str) -> tuple[str, ...]:
    statuses = _string_tuple(value, entry_id, "statuses")
    for workflow_status in statuses:
        if workflow_status not in WORKFLOW_STATUSES:
            raise SkillRegistryError(
                f"invalid workflow status for {entry_id}: {workflow_status}"
            )
    return tuple(sorted(set(statuses)))


def _intents(value: Any, entry_id: str) -> tuple[str, ...]:
    intents = _string_tuple(value, entry_id, "intents")
    for intent in intents:
        if not INTENT_PATTERN.fullmatch(intent):
            raise SkillRegistryError(
                f"invalid intent for {entry_id}: {intent}"
            )
    return tuple(sorted(set(intents)))


def _normalize_runtime_fields(raw: dict[str, Any], entry_id: str) -> dict[str, str | None]:
    enforcement = _enum(raw["enforcement"], ENFORCEMENTS, entry_id, "enforcement")
    runtime_gate = _nullable_string(
        raw["runtimeGate"],
        entry_id,
        "runtimeGate",
    )
    if runtime_gate is not None and not ID_PATTERN.fullmatch(runtime_gate):
        raise SkillRegistryError(
            f"invalid runtimeGate for {entry_id}: {runtime_gate}"
        )
    runtime_command = _nullable_string(
        raw["runtimeCommand"],
        entry_id,
        "runtimeCommand",
    )
    evidence_artifact = _nullable_string(
        raw["evidenceArtifact"],
        entry_id,
        "evidenceArtifact",
    )
    return {
        "enforcement": enforcement,
        "runtime_gate": runtime_gate,
        "runtime_command": runtime_command,
        "evidence_artifact": evidence_artifact,
    }


def _normalize_source(
    value: Any,
    entry_id: str,
    template_root: Path,
    *,
    validate_sources: bool,
) -> str:
    source = _relative_path(value, entry_id, "source")
    if validate_sources and not (template_root / Path(source)).exists():
        raise SkillRegistryError(
            f"source does not exist for {entry_id}: {source}"
        )
    return source


def _managed_paths(value: Any, entry_id: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(
                _managed_path(path, entry_id)
                for path in _string_tuple(value, entry_id, "managedPaths")
            )
        )
    )


def _enum(value: Any, allowed: set[str], entry_id: str, field_name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SkillRegistryError(
            f"invalid {field_name} for {entry_id}: {value}"
        )
    return value


def _string_tuple(value: Any, entry_id: str, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SkillRegistryError(f"{field_name} for {entry_id} must be an array")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SkillRegistryError(
                f"{field_name} for {entry_id} "
                "must contain non-empty strings"
            )
        normalized.append(item.strip())
    return tuple(normalized)


def _nullable_string(value: Any, entry_id: str, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SkillRegistryError(
            f"{field_name} for {entry_id} "
            "must be null or a non-empty string"
        )
    return value.strip()


def _normalize_read_when(
    value: Any,
    entry_id: str,
    kind: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if value is None:
        return (), ()
    if kind != "domain" or not isinstance(value, dict):
        raise SkillRegistryError(
            f"readWhen for {entry_id} is only valid for domain entries"
        )
    unexpected = set(value) - {"devTypes", "pathPatterns"}
    if unexpected:
        raise SkillRegistryError(
            f"unexpected readWhen field for {entry_id}: {sorted(unexpected)[0]}"
        )
    dev_types = tuple(sorted(set(_string_tuple(
        value.get("devTypes", []),
        entry_id,
        "readWhen.devTypes",
    ))))
    patterns = tuple(sorted(set(_string_tuple(
        value.get("pathPatterns", []),
        entry_id,
        "readWhen.pathPatterns",
    ))))
    if not dev_types and not patterns:
        raise SkillRegistryError(
            f"readWhen for {entry_id} requires devTypes or pathPatterns"
        )
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        if normalized.startswith(("/", "../")) or "/../" in normalized:
            raise SkillRegistryError(
                f"invalid readWhen.pathPatterns for {entry_id}: {pattern}"
            )
    return dev_types, patterns


def _relative_path(value: Any, entry_id: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SkillRegistryError(
            f"{field_name} for {entry_id} must be a non-empty relative path"
        )
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    parts = normalized.split("/")
    if (
        normalized.startswith("/")
        or normalized.startswith("//")
        or re.match(r"^[A-Za-z]:", normalized)
        or ".." in parts
        or any(character in normalized for character in "*?[]")
    ):
        raise SkillRegistryError(
            f"invalid {field_name} for {entry_id}: {value}"
        )
    return normalized


def _managed_path(value: str, entry_id: str) -> str:
    normalized = _relative_path(value, entry_id, "managedPaths")
    if not normalized.endswith("/"):
        raise SkillRegistryError(
            f"managedPaths for {entry_id} must end with /: {value}"
        )
    return normalized


def _validate_managed_paths(entries: tuple[SkillEntry, ...]) -> None:
    owners: list[tuple[str, str]] = []
    for entry in entries:
        for path in entry.managed_paths:
            for existing_entry, existing_path in owners:
                if (
                    path == existing_path
                    or path.startswith(existing_path)
                    or existing_path.startswith(path)
                ):
                    raise SkillRegistryError(
                        "managed path overlap: "
                        f"{existing_entry}:{existing_path} and "
                        f"{entry.id}:{path}"
                    )
            owners.append((entry.id, path))
