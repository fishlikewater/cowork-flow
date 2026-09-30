#!/usr/bin/env python3
"""Qoder plugin hook entry: locate the project runtime and forward the payload.

Installed into the Qoder plugin cache, so this file is never next to the
project it serves. The project is therefore resolved from the hook payload
(`cwd`) rather than from a module-relative path, and the renderers stay in the
project's own `.cowork-flow/scripts` — one copy of the injection logic per
repository, never a stale second copy in the plugin cache.

Fail-open by design: outside a cowork-flow project, or when the project's own
runtime fails, this exits 0 with no injection. The hook is machine-level, so it
meets project runtimes older than itself; Qoder refuses the prompt on a
non-zero hook exit, and a stale project copy must never do that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOST = "qoder"
WORKFLOW_DIR = ".cowork-flow"
INJECT_RELPATH = ("scripts", "adapters", "host", "inject.py")


def _payload_cwd(raw: bytes) -> str | None:
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None
    if isinstance(payload, dict):
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return cwd
    return None


def find_workflow_root(start: str | None) -> Path | None:
    if not start:
        return None
    try:
        current = Path(start).resolve()
    except OSError:
        return None
    while True:
        if (current / WORKFLOW_DIR).is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def resolve_root(raw: bytes) -> Path | None:
    candidates = [
        _payload_cwd(raw),
        os.environ.get("QODER_PROJECT_DIR"),
        os.environ.get("QODER_WORKING_DIR"),
        os.getcwd(),
    ]
    for candidate in candidates:
        root = find_workflow_root(candidate)
        if root is not None:
            return root
    return None


def resolve_inject(root: Path) -> Path | None:
    inject = root.joinpath(WORKFLOW_DIR, *INJECT_RELPATH)
    return inject if inject.is_file() else None


def main() -> int:
    if (
        os.environ.get("COWORK_FLOW_HOOKS") == "0"
        or os.environ.get("COWORK_FLOW_DISABLE_HOOKS") == "1"
    ):
        return 0

    raw = sys.stdin.buffer.read()
    root = resolve_root(raw)
    if root is None:
        return 0
    inject = resolve_inject(root)
    if inject is None:
        return 0

    # The hook is already running under a Python 3 interpreter, so the only
    # reason to override it is an explicit COWORK_FLOW_PYTHON; sys.executable
    # keeps the hook working where `python` is not on PATH at all.
    interpreter = (os.environ.get("COWORK_FLOW_PYTHON") or "").strip() or sys.executable
    try:
        completed = subprocess.run(
            [interpreter, str(inject), "--host", HOST],
            input=raw,
            cwd=str(root),
            timeout=25,
        )
    except OSError as error:
        print(f"cowork-flow qoder hook: {error}", file=sys.stderr)
        return 0
    except subprocess.TimeoutExpired:
        print("cowork-flow qoder hook: inject timed out", file=sys.stderr)
        return 0
    if completed.returncode != 0:
        # Never propagate: Qoder counts a non-zero exit on SessionStart and
        # UserPromptSubmit as a blocking hook failure. Keep the reason in the
        # run log and leave the event alone.
        print(
            f"cowork-flow qoder hook: inject.py exited {completed.returncode}; skipping injection",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
