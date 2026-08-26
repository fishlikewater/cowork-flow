#!/usr/bin/env python3
"""Task context repository-relative path policy."""

from __future__ import annotations

import re
from pathlib import Path


CONTEXT_ENTRY_TYPES = frozenset(("file", "directory", "planned-file", "deleted-file"))


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
    _validate_context_path(candidate, normalized, segments, path, entry_type)
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
) -> None:
    if not _is_valid_context_path(normalized, segments, path, entry_type):
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
) -> bool:
    return not (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in ("", ".", "..") for segment in segments)
        or any(character in normalized for character in "*?[]")
        or (entry_type in {"planned-file", "deleted-file"} and str(path).endswith(("/", "\\")))
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
    changed files for lifecycle review.
    """
    entry_type = entry.get("type", "file")
    file_path = entry.get("file")
    if not isinstance(file_path, str) or not file_path:
        return None, "missing file path"
    if entry_type == "directory":
        return _normalize_context_file_scope_path(repo_root, file_path, entry_type)
    if entry_type not in ("file", "planned-file", "deleted-file"):
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
