#!/usr/bin/env python3
"""Task context repository-relative path policy."""

from __future__ import annotations

import json
import re
from pathlib import Path


CONTEXT_ENTRY_TYPES = frozenset(("file", "directory", "planned-file", "deleted-file"))

# Byte-identical with the shipped .cowork-flow/spec/runtime/scope-rules.json;
# loaded from disk at runtime so the rules are a single source across python
# and the zcode/opencode JS mirrors. Keep both sides in sync (locked by
# tests/test_scope_rules.py default-equivalence).
DEFAULT_SCOPE_RULES: dict = {
    "schemaVersion": 1,
    "scopeFilter": {
        "allowedTypes": ["file", "planned-file", "deleted-file"],
        "wildcardChars": ["*", "?", "[", "]"],
        "rejectedSegments": ["", ".", ".."],
        "driveLetterPattern": "^[A-Za-z]:",
        "trailingSlashRejectedTypes": ["planned-file", "deleted-file"],
    },
    "stageContract": {
        "budget": 1200,
        "scopeLimit": 8,
        "specLimit": 4,
        "verifyLimit": 3,
    },
}

_RULES_CACHE: dict[str, dict] = {}


def load_scope_rules(repo_root: Path) -> dict:
    """Read <repo>/.cowork-flow/spec/runtime/scope-rules.json; missing or
    malformed files fall back to DEFAULT_SCOPE_RULES (per-process cache)."""
    root = Path(repo_root).resolve()
    cached = _RULES_CACHE.get(str(root))
    if cached is not None:
        return cached
    rules = DEFAULT_SCOPE_RULES
    path = root / ".cowork-flow" / "spec" / "runtime" / "scope-rules.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and loaded.get("schemaVersion") == 1:
            rules = loaded
    except (OSError, json.JSONDecodeError):
        pass
    _RULES_CACHE[str(root)] = rules
    return rules


class TaskContextError(RuntimeError):
    """Raised when a context mutation cannot be performed."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


def normalize_context_path(
    repo_root: Path,
    path: str,
    entry_type: str,
) -> tuple[str, Path]:
    """Return a canonical repo-relative context path and its absolute target."""
    candidate = Path(repo_root) / str(path)
    _validate_context_entry_type(candidate, entry_type)
    normalized = _normalized_context_path(path, entry_type)
    segments = normalized.split("/")
    rules = load_scope_rules(repo_root)
    _validate_context_path(
        candidate, normalized, segments, path, entry_type, rules=rules
    )
    repo_root, full_path = _resolved_context_target(repo_root, segments)
    return _typed_context_path(normalized, full_path, repo_root, entry_type)


def _validate_context_entry_type(candidate: Path, entry_type: str) -> None:
    if entry_type not in CONTEXT_ENTRY_TYPES:
        raise TaskContextError(
            "TASK-CONTEXT-TYPE-001",
            candidate,
            f"unsupported context entry type: {entry_type}",
        )


def _normalized_context_path(path: str, entry_type: str) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if entry_type == "directory" and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _validate_context_path(
    candidate: Path,
    normalized: str,
    segments: list[str],
    path: str,
    entry_type: str,
    rules: dict | None = None,
) -> None:
    if not _is_valid_context_path(normalized, segments, path, entry_type, rules):
        raise TaskContextError(
            "TASK-CONTEXT-PATH-002",
            candidate,
            "context path must be a canonical repository-relative path",
        )


def _is_valid_context_path(
    normalized: str,
    segments: list[str],
    path: str,
    entry_type: str,
    rules: dict | None = None,
) -> bool:
    """Rules come from scope-rules.json (loaded by the caller); None falls
    back to the default constants, keeping direct callers byte-compatible.
    Type allow-listing happens at the file-scope layer
    (normalize_context_file_scope_entry), not here: directory entries are
    valid context paths through this function."""
    scope_filter = (rules or {}).get("scopeFilter") or {}
    wildcard_chars = scope_filter.get("wildcardChars")
    if wildcard_chars is None:
        wildcard_chars = ("*", "?", "[", "]")
    drive_letter = scope_filter.get("driveLetterPattern")
    if drive_letter is None:
        drive_letter = r"^[A-Za-z]:"
    rejected_segments = scope_filter.get("rejectedSegments")
    if rejected_segments is None:
        rejected_segments = ("", ".", "..")
    trailing_types = scope_filter.get("trailingSlashRejectedTypes")
    if trailing_types is None:
        trailing_types = ("planned-file", "deleted-file")
    return not (
        not normalized
        or normalized.startswith("/")
        or re.match(drive_letter, normalized) is not None
        or any(segment in rejected_segments for segment in segments)
        or any(character in normalized for character in wildcard_chars)
        or (entry_type in trailing_types and str(path).endswith(("/", "\\")))
    )


def _resolved_context_target(
    repo_root: Path,
    segments: list[str],
) -> tuple[Path, Path]:
    resolved_root = Path(repo_root).resolve()
    return resolved_root, resolved_root.joinpath(*segments).resolve(strict=False)


def _typed_context_path(
    normalized: str,
    full_path: Path,
    repo_root: Path,
    entry_type: str,
) -> tuple[str, Path]:
    try:
        full_path.relative_to(repo_root)
    except ValueError as error:
        raise TaskContextError(
            "TASK-CONTEXT-PATH-002",
            full_path,
            "context path resolves outside the repository",
        ) from error

    if entry_type == "directory":
        normalized = f"{normalized}/"
    return normalized, full_path


def prepare_context_entry(
    repo_root: Path,
    path: str,
    reason: str,
    requested_type: str | None,
) -> tuple[str, str, dict]:
    """Build one validated context entry without writing it."""
    entry_type = requested_type
    if entry_type is None:
        candidate = Path(repo_root) / path
        entry_type = "directory" if candidate.is_dir() else "file"

    normalized_path, full_path = normalize_context_path(
        repo_root,
        path,
        entry_type,
    )
    valid_target = {
        "directory": full_path.is_dir(),
        "planned-file": not full_path.is_dir(),
        "deleted-file": not full_path.is_dir(),
        "file": full_path.is_file(),
    }[entry_type]
    if not valid_target:
        raise TaskContextError(
            "TASK-CONTEXT-PATH-001",
            full_path,
            f"context {entry_type} path does not exist or has the wrong type",
        )

    entry = {"file": normalized_path, "reason": reason}
    if entry_type != "file":
        entry["type"] = entry_type
    return entry_type, normalized_path, entry


def normalize_context_file_scope_entry(
    repo_root: Path,
    entry: dict,
) -> tuple[str | None, str | None]:
    """Return the file-scope path allowed by one context entry.

    Directory entries are valid context, but they do not authorize arbitrary
    changed files for lifecycle review. The allowed type set comes from
    scope-rules.json (single source shared with the JS mirrors)."""
    entry_type = entry.get("type", "file")
    file_path = entry.get("file")
    if not isinstance(file_path, str) or not file_path:
        return None, "missing file path"
    if entry_type == "directory":
        return _normalize_context_file_scope_path(repo_root, file_path, entry_type)
    rules = load_scope_rules(repo_root)
    allowed_types = (rules.get("scopeFilter") or {}).get("allowedTypes")
    if allowed_types is None:
        allowed_types = ("file", "planned-file", "deleted-file")
    if entry_type not in allowed_types:
        return None, f"unsupported type {entry_type!r}"
    return _normalize_context_file_scope_path(repo_root, file_path, entry_type)


def _normalize_context_file_scope_path(
    repo_root: Path,
    file_path: str,
    entry_type: str,
) -> tuple[str | None, str | None]:
    try:
        normalized, _full_path = normalize_context_path(
            repo_root,
            file_path,
            entry_type,
        )
    except TaskContextError:
        return None, f"non-canonical path {file_path!r}"
    if entry_type == "directory":
        return None, None
    return normalized, None
