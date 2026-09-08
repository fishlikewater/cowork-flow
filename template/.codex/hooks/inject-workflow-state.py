#!/usr/bin/env python3
"""Codex hook: thin delegate to the host-neutral injection entry.

All workflow facts and host shaping (dispatch-mode preamble, envelope,
session-probe digest semantics) live in adapters/host/inject.py — this file
only locates the project runtime next to itself (.codex/hooks/ → project
root) and forwards with --host codex.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    scripts_dir = project_root / ".cowork-flow" / "scripts"
    if not scripts_dir.is_dir():
        # Outside any cowork-flow project: stay silent like the entry does.
        return 0
    sys.path.insert(0, str(scripts_dir))
    from adapters.host.inject import main as inject_main

    return inject_main(["--host", "codex"])


if __name__ == "__main__":
    raise SystemExit(main())
