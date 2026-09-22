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
    cache_bytecode: bool = True,
) -> dict[str, str]:
    """Return a copy of os.environ with `scripts_dir` first on PYTHONPATH.

    The runtime scripts directory is prepended so a child Python process can
    import `services.*` / `infra.*` from the same runtime this code came from,
    while any caller-provided PYTHONPATH entries are preserved after it.

    `cache_bytecode=False` is the skill-script rule: those children run rarely,
    the cache buys them nothing measurable, and the `__pycache__` trees they
    leave behind land next to whatever runtime they resolved to — in a source
    checkout that is the shipped `template/` tree. High-frequency commands keep
    the default so they keep their cache.
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(scripts_dir)
        if not existing
        else f"{scripts_dir}{os.pathsep}{existing}"
    )
    if not cache_bytecode:
        env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env
