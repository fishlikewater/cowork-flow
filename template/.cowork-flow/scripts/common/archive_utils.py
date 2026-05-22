#!/usr/bin/env python3
"""Small resumable directory archive helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import filecmp
import shutil


@dataclass(frozen=True)
class ArchiveResult:
    status: str
    destination: Path
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "archived"

    @property
    def partial(self) -> bool:
        return self.status == "partial"


def directories_match(left: Path, right: Path) -> bool:
    """Return True when two directory trees contain the same files and bytes."""
    if not left.is_dir() or not right.is_dir():
        return False

    left_files = sorted(path.relative_to(left) for path in left.rglob("*") if path.is_file())
    right_files = sorted(path.relative_to(right) for path in right.rglob("*") if path.is_file())
    if left_files != right_files:
        return False

    return all(filecmp.cmp(left / rel, right / rel, shallow=False) for rel in left_files)


def archive_directory_resumable(source: Path, destination: Path) -> ArchiveResult:
    """Copy, verify, then delete a directory, resuming matching duplicate state."""
    if not source.is_dir():
        return ArchiveResult("failed", destination, f"source directory not found: {source}")

    if destination.exists():
        if not destination.is_dir():
            return ArchiveResult("failed", destination, f"archive destination is not a directory: {destination}")
        if not directories_match(source, destination):
            return ArchiveResult(
                "failed",
                destination,
                f"archive source and destination differ: {source} | {destination}",
            )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(source, destination)
        except (OSError, IOError, shutil.Error) as exc:
            return ArchiveResult("failed", destination, f"failed to copy directory to archive: {exc}")
        if not directories_match(source, destination):
            return ArchiveResult("failed", destination, f"archive verification failed: {source} | {destination}")

    try:
        shutil.rmtree(source)
    except (OSError, IOError) as exc:
        return ArchiveResult(
            "partial",
            destination,
            f"archive verified but source remains: {source}; delete failed: {exc}",
        )

    return ArchiveResult("archived", destination)
