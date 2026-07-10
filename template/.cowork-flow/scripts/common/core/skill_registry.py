from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(".cowork-flow/spec/runtime/skill-registry.json")
KINDS = {"phase", "protocol", "domain", "mode", "runtime"}
VISIBILITIES = {"public", "internal"}
ENTRY_STATUSES = {"active", "deprecated", "disabled"}
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
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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
ALLOWED_FIELDS = REQUIRED_FIELDS | {"replacement", "removeAfter"}


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
    replacement: str | None
    remove_after: str | None

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
            "replacement": self.replacement,
            "removeAfter": self.remove_after,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_skill_registry(template_root: Path) -> SkillRegistry:
    path = Path(template_root) / REGISTRY_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillRegistryError(
            f"unable to read Skill Registry {path}: {exc}"
        ) from exc
    return create_skill_registry(raw, template_root)


def create_skill_registry(
    raw: dict[str, Any],
    template_root: Path,
) -> SkillRegistry:
    _validate_root(raw)
    entries = tuple(
        sorted(
            (
                _normalize_entry(entry, Path(template_root))
                for entry in raw["entries"]
            ),
            key=lambda entry: entry.id,
        )
    )
    by_id: dict[str, SkillEntry] = {}
    aliases: dict[str, str] = {}
    tokens: set[str] = set()
    for entry in entries:
        for token in (entry.id, *entry.aliases):
            if token in tokens:
                raise SkillRegistryError(f"duplicate skill id or alias: {token}")
            tokens.add(token)
            if token == entry.id:
                by_id[token] = entry
            else:
                aliases[token] = entry.id

    public_intents: set[str] = set()
    for entry in entries:
        if entry.enforcement == "mandatory" and entry.runtime_gate is None:
            raise SkillRegistryError(
                f"mandatory entry {entry.id} requires runtimeGate"
            )
        if entry.runtime_gate is not None:
            gate = by_id.get(entry.runtime_gate)
            if gate is None or gate.kind != "runtime":
                raise SkillRegistryError(
                    f"runtimeGate {entry.runtime_gate} "
                    "must reference a runtime entry"
                )
        if entry.kind == "runtime":
            if (
                entry.visibility != "internal"
                or entry.enforcement != "runtime"
            ):
                raise SkillRegistryError(
                    f"runtime entry {entry.id} must be internal "
                    "with runtime enforcement"
                )
        elif entry.enforcement == "runtime":
            raise SkillRegistryError(
                f"non-runtime entry {entry.id} cannot use runtime enforcement"
            )
        if entry.status == "deprecated":
            if entry.replacement is None or entry.remove_after is None:
                raise SkillRegistryError(
                    f"deprecated entry {entry.id} "
                    "requires replacement and removeAfter"
                )
            if (
                entry.replacement not in by_id
                or entry.replacement == entry.id
            ):
                raise SkillRegistryError(
                    f"deprecated entry {entry.id} has invalid replacement: "
                    f"{entry.replacement}"
                )
        if entry.visibility == "public" and entry.status == "active":
            for intent in entry.intents:
                if intent in public_intents:
                    raise SkillRegistryError(f"duplicate public intent: {intent}")
                public_intents.add(intent)

    _validate_managed_paths(entries)
    return SkillRegistry(schema_version=1, entries=entries)


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


def _normalize_entry(raw: Any, template_root: Path) -> SkillEntry:
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
    display_name = raw["displayName"]
    if not isinstance(display_name, str) or not display_name.strip():
        raise SkillRegistryError(
            f"displayName for {raw['id']} must be a non-empty string"
        )

    aliases = _string_tuple(raw["aliases"], raw["id"], "aliases")
    for alias in aliases:
        if not ID_PATTERN.fullmatch(alias):
            raise SkillRegistryError(
                f"invalid alias for {raw['id']}: {alias}"
            )
    kind = _enum(raw["kind"], KINDS, raw["id"], "kind")
    visibility = _enum(
        raw["visibility"],
        VISIBILITIES,
        raw["id"],
        "visibility",
    )
    status = _enum(raw["status"], ENTRY_STATUSES, raw["id"], "status")
    statuses = _string_tuple(raw["statuses"], raw["id"], "statuses")
    for workflow_status in statuses:
        if workflow_status not in WORKFLOW_STATUSES:
            raise SkillRegistryError(
                f"invalid workflow status for {raw['id']}: {workflow_status}"
            )
    intents = _string_tuple(raw["intents"], raw["id"], "intents")
    for intent in intents:
        if not INTENT_PATTERN.fullmatch(intent):
            raise SkillRegistryError(
                f"invalid intent for {raw['id']}: {intent}"
            )
    enforcement = _enum(
        raw["enforcement"],
        ENFORCEMENTS,
        raw["id"],
        "enforcement",
    )
    runtime_gate = _nullable_string(
        raw["runtimeGate"],
        raw["id"],
        "runtimeGate",
    )
    if runtime_gate is not None and not ID_PATTERN.fullmatch(runtime_gate):
        raise SkillRegistryError(
            f"invalid runtimeGate for {raw['id']}: {runtime_gate}"
        )
    runtime_command = _nullable_string(
        raw["runtimeCommand"],
        raw["id"],
        "runtimeCommand",
    )
    evidence_artifact = _nullable_string(
        raw["evidenceArtifact"],
        raw["id"],
        "evidenceArtifact",
    )
    source = _relative_path(raw["source"], raw["id"], "source")
    if not (template_root / Path(source)).exists():
        raise SkillRegistryError(
            f"source does not exist for {raw['id']}: {source}"
        )
    managed_paths = tuple(
        sorted(
            set(
                _managed_path(path, raw["id"])
                for path in _string_tuple(
                    raw["managedPaths"],
                    raw["id"],
                    "managedPaths",
                )
            )
        )
    )
    replacement = _nullable_string(
        raw.get("replacement"),
        raw["id"],
        "replacement",
    )
    if replacement is not None and not ID_PATTERN.fullmatch(replacement):
        raise SkillRegistryError(
            f"invalid replacement for {raw['id']}: {replacement}"
        )
    remove_after = _nullable_string(
        raw.get("removeAfter"),
        raw["id"],
        "removeAfter",
    )
    if remove_after is not None and not DATE_PATTERN.fullmatch(remove_after):
        raise SkillRegistryError(
            f"invalid removeAfter for {raw['id']}: {remove_after}"
        )

    return SkillEntry(
        id=raw["id"],
        display_name=display_name.strip(),
        aliases=tuple(sorted(set(aliases))),
        kind=kind,
        visibility=visibility,
        status=status,
        statuses=tuple(sorted(set(statuses))),
        intents=tuple(sorted(set(intents))),
        enforcement=enforcement,
        runtime_gate=runtime_gate,
        runtime_command=runtime_command,
        evidence_artifact=evidence_artifact,
        source=source,
        managed_paths=managed_paths,
        replacement=replacement,
        remove_after=remove_after,
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
