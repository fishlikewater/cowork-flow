#!/usr/bin/env python3
"""Host Asset Manifest loading and semantic validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]


MANIFEST_PATH = Path(".cowork-flow/spec/runtime/host-assets.json")
SCHEMA_PATH = Path(".cowork-flow/spec/schemas/host-assets.schema.json")


class HostManifestError(RuntimeError):
    """Raised when the Host Asset Manifest is unavailable or invalid."""


@dataclass(frozen=True)
class CommandTarget:
    config: str
    format: str
    target: str


@dataclass(frozen=True)
class HostPlatform:
    id: str
    display_name: str
    aliases: tuple[str, ...]
    detect_any: tuple[str, ...]
    asset_prefixes: tuple[str, ...]
    asset_files: tuple[str, ...]
    skill_target: str | None
    adapter_path: str
    capabilities: dict[str, str]
    command_targets: tuple[CommandTarget, ...]


@dataclass(frozen=True)
class SyncPolicy:
    protected_files: tuple[str, ...]
    protected_prefixes: tuple[str, ...]
    safe_files: tuple[str, ...]
    safe_prefixes: tuple[str, ...]
    managed_block_files: tuple[str, ...]
    obsolete_files: tuple[str, ...]


@dataclass(frozen=True)
class HostManifest:
    schema_version: int
    capability_values: tuple[str, ...]
    platforms: tuple[HostPlatform, ...]
    excluded_prefixes: tuple[str, ...]
    sync_policy: SyncPolicy

    @property
    def platform_ids(self) -> tuple[str, ...]:
        return tuple(platform.id for platform in self.platforms)

    def platform(self, platform_id: str) -> HostPlatform:
        for platform in self.platforms:
            if platform.id == platform_id:
                return platform
        raise HostManifestError(f"unknown host platform: {platform_id}")

    def resolve_alias(self, alias: str) -> str:
        normalized = alias.strip().lower()
        if normalized == "all":
            raise HostManifestError("all resolves to multiple host platforms")
        for platform in self.platforms:
            if normalized in platform.aliases:
                return platform.id
        raise HostManifestError(f"unknown host platform alias: {alias}")


def load_host_manifest(template_root: Path) -> HostManifest:
    path = Path(template_root) / MANIFEST_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HostManifestError(f"missing host asset manifest: {path}") from error
    except json.JSONDecodeError as error:
        raise HostManifestError(f"invalid host asset manifest JSON: {path}") from error
    if not isinstance(raw, dict):
        raise HostManifestError("host asset manifest must be a JSON object")
    return _build_manifest(raw)


def validate_host_assets(template_root: Path) -> list[str]:
    root = Path(template_root)
    errors: list[str] = []
    try:
        manifest = load_host_manifest(root)
    except HostManifestError as error:
        return [str(error)]

    if not (root / SCHEMA_PATH).is_file():
        errors.append(f"missing host asset schema: {root / SCHEMA_PATH}")

    allowed = set(manifest.capability_values)
    aliases: dict[str, str] = {}
    for platform in manifest.platforms:
        for alias in platform.aliases:
            owner = aliases.get(alias)
            if owner is not None and owner != platform.id:
                errors.append(
                    f"duplicate platform alias {alias}: {owner}, {platform.id}"
                )
            aliases[alias] = platform.id
        _validate_platform(root, platform, allowed, errors)
    return errors


def _validate_platform(
    root: Path,
    platform: HostPlatform,
    allowed: set[str],
    errors: list[str],
) -> None:
    adapter_path = root / platform.adapter_path
    if not adapter_path.is_file():
        errors.append(f"missing adapter: {platform.adapter_path}")
        return
    try:
        adapter = _parse_simple_yaml(adapter_path)
    except (OSError, ValueError) as error:
        errors.append(f"invalid adapter YAML {platform.adapter_path}: {error}")
        return

    if adapter.get("host") != platform.id:
        errors.append(
            f"adapter host mismatch {platform.adapter_path}: "
            f"{adapter.get('host')} != {platform.id}"
        )
    capabilities = adapter.get("capabilities")
    if not isinstance(capabilities, dict):
        errors.append(f"adapter missing capabilities: {platform.adapter_path}")
    else:
        for name, value in capabilities.items():
            if value not in allowed:
                errors.append(
                    f"illegal capability {platform.id}:{name}={value}"
                )
        if capabilities != platform.capabilities:
            errors.append(
                f"capability mismatch between manifest and adapter: {platform.id}"
            )

    for target in platform.command_targets:
        _validate_command_target(root, platform.id, target, errors)


def _validate_command_target(
    root: Path,
    platform_id: str,
    command_target: CommandTarget,
    errors: list[str],
) -> None:
    config_path = root / command_target.config
    target_path = root / command_target.target
    if not config_path.is_file():
        errors.append(
            f"missing command config {platform_id}: {command_target.config}"
        )
        return
    if not target_path.is_file():
        errors.append(
            f"missing command target {platform_id}: {command_target.target}"
        )
        return
    try:
        config = _load_structured(config_path, command_target.format)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(
            f"invalid command config {platform_id}: "
            f"{command_target.config}: {error}"
        )
        return
    strings = tuple(_walk_strings(config))
    if not any(command_target.target in value for value in strings):
        errors.append(
            f"command config {command_target.config} does not reference "
            f"{command_target.target}"
        )


def _load_structured(path: Path, format_name: str) -> object:
    text = path.read_text(encoding="utf-8")
    if format_name == "json":
        return json.loads(text)
    if format_name == "toml":
        if tomllib is None:
            raise ValueError("TOML parser unavailable")
        return tomllib.loads(text)
    if format_name == "yaml":
        return _parse_simple_yaml(path)
    raise ValueError(f"unsupported config format: {format_name}")


def _walk_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _parse_simple_yaml(path: Path) -> dict[str, object]:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = raw_line.strip()
        key, separator, raw_value = stripped.partition(":")
        if not separator or not key.strip():
            raise ValueError(f"invalid mapping at line {line_number}")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        value = raw_value.strip()
        if value:
            parent[key.strip()] = _parse_scalar(value)
        else:
            child: dict[str, object] = {}
            parent[key.strip()] = child
            stack.append((indent, child))
    return root


def _parse_scalar(value: str) -> object:
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdecimal():
        return int(value)
    return value


def _build_manifest(raw: dict[str, Any]) -> HostManifest:
    schema_version = raw.get("schemaVersion")
    if schema_version != 1:
        raise HostManifestError(
            f"unsupported host asset schemaVersion: {schema_version}"
        )
    capability_values = _string_tuple(
        raw.get("capabilityValues"),
        "capabilityValues",
    )
    platforms_raw = raw.get("platforms")
    if not isinstance(platforms_raw, list) or not platforms_raw:
        raise HostManifestError("platforms must be a non-empty array")
    platforms = tuple(
        _build_platform(item)
        for item in platforms_raw
        if isinstance(item, dict)
    )
    if len(platforms) != len(platforms_raw):
        raise HostManifestError("every platform must be an object")
    sync_raw = raw.get("syncPolicy")
    if not isinstance(sync_raw, dict):
        raise HostManifestError("syncPolicy must be an object")
    return HostManifest(
        schema_version=schema_version,
        capability_values=capability_values,
        platforms=platforms,
        excluded_prefixes=_string_tuple(
            raw.get("excludedPrefixes"),
            "excludedPrefixes",
        ),
        sync_policy=SyncPolicy(
            protected_files=_string_tuple(
                sync_raw.get("protectedFiles"),
                "syncPolicy.protectedFiles",
            ),
            protected_prefixes=_string_tuple(
                sync_raw.get("protectedPrefixes"),
                "syncPolicy.protectedPrefixes",
            ),
            safe_files=_string_tuple(
                sync_raw.get("safeFiles"),
                "syncPolicy.safeFiles",
            ),
            safe_prefixes=_string_tuple(
                sync_raw.get("safePrefixes"),
                "syncPolicy.safePrefixes",
            ),
            managed_block_files=_string_tuple(
                sync_raw.get("managedBlockFiles"),
                "syncPolicy.managedBlockFiles",
            ),
            obsolete_files=_string_tuple(
                sync_raw.get("obsoleteFiles"),
                "syncPolicy.obsoleteFiles",
            ),
        ),
    )


def _build_platform(raw: dict[str, Any]) -> HostPlatform:
    platform_id = _required_string(raw, "id")
    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise HostManifestError(
            f"platform {platform_id} capabilities must be an object"
        )
    normalized_capabilities: dict[str, str] = {}
    for name, value in capabilities.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise HostManifestError(
                f"platform {platform_id} capabilities must be strings"
            )
        normalized_capabilities[name] = value
    command_targets_raw = raw.get("commandTargets")
    if not isinstance(command_targets_raw, list):
        raise HostManifestError(
            f"platform {platform_id} commandTargets must be an array"
        )
    command_targets = tuple(
        CommandTarget(
            config=_required_string(item, "config"),
            format=_required_string(item, "format"),
            target=_required_string(item, "target"),
        )
        for item in command_targets_raw
        if isinstance(item, dict)
    )
    if len(command_targets) != len(command_targets_raw):
        raise HostManifestError(
            f"platform {platform_id} commandTargets must be objects"
        )
    skill_target = raw.get("skillTarget")
    if skill_target is not None and not isinstance(skill_target, str):
        raise HostManifestError(
            f"platform {platform_id} skillTarget must be a string or null"
        )
    return HostPlatform(
        id=platform_id,
        display_name=_required_string(raw, "displayName"),
        aliases=_string_tuple(raw.get("aliases"), f"{platform_id}.aliases"),
        detect_any=_string_tuple(
            raw.get("detectAny"),
            f"{platform_id}.detectAny",
        ),
        asset_prefixes=_string_tuple(
            raw.get("assetPrefixes"),
            f"{platform_id}.assetPrefixes",
        ),
        asset_files=_string_tuple(
            raw.get("assetFiles"),
            f"{platform_id}.assetFiles",
        ),
        skill_target=skill_target,
        adapter_path=_required_string(raw, "adapterPath"),
        capabilities=normalized_capabilities,
        command_targets=command_targets,
    )


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HostManifestError(f"{key} must be a non-empty string")
    return value.strip()


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise HostManifestError(f"{label} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise HostManifestError(
                f"{label} entries must be non-empty strings"
            )
        result.append(item.strip())
    return tuple(result)
