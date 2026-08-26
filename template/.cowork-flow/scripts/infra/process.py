#!/usr/bin/env python3
"""Shared subprocess bootstrap for runtime-owned Python child processes."""

from __future__ import annotations

import os
from pathlib import Path

RUNTIME_SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def runtime_pythonpath_env(
    scripts_dir: Path = RUNTIME_SCRIPTS_DIR,
    *,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return a copy of os.environ with `scripts_dir` first on PYTHONPATH.

    The runtime scripts directory is prepended so a child Python process can
    import `services.*` / `infra.*` from the same runtime this code came from,
    while any caller-provided PYTHONPATH entries are preserved after it.
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(scripts_dir)
        if not existing
        else f"{scripts_dir}{os.pathsep}{existing}"
    )
    if extra:
        env.update(extra)
    return env
