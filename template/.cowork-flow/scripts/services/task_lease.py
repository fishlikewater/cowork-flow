#!/usr/bin/env python3
"""Branch-anchored task lease facts for the task lifecycle.

The lease answers one question the rest of the state model cannot: on which
branch this task was last started. It is a fact, not a lock: the start
activation point and completion refuse a mismatch, and an explicit takeover
overrides that gate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from infra import git_snapshot


LEASE_KEY = "lease"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(meta: dict, *, repo_root: Path, executor: str) -> None:
    """Write the lease for the branch this checkout is currently on.

    branch stays None without git or on detached HEAD; head stays None only
    when git is unavailable, because a detached HEAD still names a commit.
    branch_conflict treats an unknown branch as no conflict so headless and
    CI starts keep working.
    """
    meta[LEASE_KEY] = {
        "executor": executor,
        "branch": git_snapshot.current_branch(repo_root),
        "head": git_snapshot.current_head(repo_root),
        "at": _now(),
    }


def release(meta: dict) -> bool:
    """Drop the lease; returns True when one was present."""
    return meta.pop(LEASE_KEY, None) is not None


def branch_conflict(task_data: dict, repo_root: Path) -> str | None:
    """Blocker text when the recorded lease branch differs from this checkout.

    Returns None when the task holds no lease, the lease records no branch
    (start ran without git), or the current branch is unknown (detached HEAD).
    """
    meta = task_data.get("meta")
    lease = meta.get(LEASE_KEY) if isinstance(meta, dict) else None
    recorded = lease.get("branch") if isinstance(lease, dict) else None
    if not isinstance(recorded, str) or not recorded:
        return None
    current = git_snapshot.current_branch(repo_root)
    if not current or recorded == current:
        return None
    return (
        f"task lease is held on branch '{recorded}', "
        f"current branch is '{current}'"
    )
