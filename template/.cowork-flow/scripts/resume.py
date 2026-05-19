#!/usr/bin/env python3
"""恢复 cowork-flow 会话的最小入口。"""

from __future__ import annotations

from common.git_context import get_context_text


def main() -> int:
    print("========================================")
    print("COWORK-FLOW RESUME")
    print("========================================")
    print("Use this after new sessions, long-task resumes, or context compression.")
    print("Read RESUME CHECKLIST first; load details on demand.")
    print("")
    print(get_context_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
