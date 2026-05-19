#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add a new session to journal file and update index.md.

Usage:
    python3 add_session.py --title "Title" --commit "hash" --summary "Summary"
    echo "content" | python3 add_session.py --title "Title" --commit "hash"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from common.paths import (
    FILE_JOURNAL_PREFIX,
    count_lines,
    get_repo_root,
    get_developer,
    get_workspace_dir,
)
from common.developer import ensure_developer
from common.config import get_session_commit_message, get_max_journal_lines

MARKER_CURRENT_STATUS_START = "@@@auto:current-status"
MARKER_CURRENT_STATUS_END = "@@@/auto:current-status"
MARKER_ACTIVE_DOCUMENTS_START = "@@@auto:active-documents"
MARKER_ACTIVE_DOCUMENTS_END = "@@@/auto:active-documents"
MARKER_SESSION_HISTORY_START = "@@@auto:session-history"
MARKER_SESSION_HISTORY_END = "@@@/auto:session-history"


# =============================================================================
# Helper Functions
# =============================================================================

def get_latest_journal_info(dev_dir: Path) -> tuple[Path | None, int, int]:
    """Get latest journal file info.

    Returns:
        Tuple of (file_path, file_number, line_count).
    """
    latest_file: Path | None = None
    latest_num = -1

    for f in dev_dir.glob(f"{FILE_JOURNAL_PREFIX}*.md"):
        if not f.is_file():
            continue

        match = re.search(r"(\d+)$", f.stem)
        if match:
            num = int(match.group(1))
            if num > latest_num:
                latest_num = num
                latest_file = f

    if latest_file:
        lines = count_lines(latest_file)
        return latest_file, latest_num, lines

    return None, 0, 0


def get_current_session(index_file: Path) -> int:
    """Get current session number from index.md."""
    if not index_file.is_file():
        return 0

    content = index_file.read_text(encoding="utf-8")
    for line in content.splitlines():
        if "Total Sessions" in line or "\u603b\u4f1a\u8bdd\u6570" in line:
            match = re.search(r"[:\uFF1A]\s*(\d+)", line)
            if match:
                return int(match.group(1))
    return 0


def _extract_journal_num(filename: str) -> int:
    """Extract journal number from filename for sorting."""
    match = re.search(r"(\d+)", filename)
    return int(match.group(1)) if match else 0


def _format_commit_display(commit: str) -> str:
    """Format commit hashes for display in index.md."""
    if not commit or commit == "-":
        return "-"
    return re.sub(r"([a-f0-9]{7,})", r"`\1`", commit.replace(",", ", "))


def _format_commit_table(commit: str) -> str:
    """Format commit hashes for a session entry."""
    if not commit or commit == "-":
        return "(no code commit; planning or sync session)"

    commit_table = """| Hash | Note |
|------|------|"""
    for c in commit.split(","):
        c = c.strip()
        commit_table += f"\n| `{c}` | See git log |"
    return commit_table


def count_journal_files(dev_dir: Path, active_num: int) -> str:
    """Count journal files and return table rows."""
    active_file = f"{FILE_JOURNAL_PREFIX}{active_num}.md"
    result_lines = []

    files = sorted(
        [f for f in dev_dir.glob(f"{FILE_JOURNAL_PREFIX}*.md") if f.is_file()],
        key=lambda f: _extract_journal_num(f.stem),
        reverse=True
    )

    for f in files:
        filename = f.name
        lines = count_lines(f)
        status = "Current" if filename == active_file else "Archived"
        result_lines.append(f"| `{filename}` | ~{lines} | {status} |")

    return "\n".join(result_lines)


def create_new_journal_file(
    dev_dir: Path, num: int, developer: str, today: str, max_lines: int = 2000,
) -> Path:
    """Create a new journal file."""
    prev_num = num - 1
    new_file = dev_dir / f"{FILE_JOURNAL_PREFIX}{num}.md"

    content = f"""# Development Journal - {developer} (Part {num})

> Continued from `{FILE_JOURNAL_PREFIX}{prev_num}.md` (archived after about {max_lines} lines)
> Start date: {today}

---

"""
    new_file.write_text(content, encoding="utf-8")
    return new_file


def generate_session_content(
    session_num: int,
    title: str,
    commit: str,
    summary: str,
    extra_content: str,
    today: str
) -> str:
    """Generate session content."""
    commit_table = _format_commit_table(commit)

    return f"""

## Session {session_num}: {title}

**Date**: {today}
**Task**: {title}

### Summary

{summary}

### Main Changes

{extra_content}

### Git Commit

{commit_table}

### Verification

- [OK] (add verification results)

### Status

[OK] **Completed**

### Follow-up Actions

- None, current task is complete
"""


def update_index(
    index_file: Path,
    dev_dir: Path,
    title: str,
    commit: str,
    new_session: int,
    active_file: str,
    today: str
) -> bool:
    """Update index.md with new session info."""
    commit_display = _format_commit_display(commit)

    # Get file number from active_file name
    match = re.search(r"(\d+)", active_file)
    active_num = int(match.group(1)) if match else 0
    files_table = count_journal_files(dev_dir, active_num)

    print(f"Updating index.md (session {new_session})...", file=sys.stderr)
    print(f"  Title: {title}", file=sys.stderr)
    print(f"  Commit: {commit_display}", file=sys.stderr)
    print(f"  Current file: {active_file}", file=sys.stderr)
    print("", file=sys.stderr)

    content = index_file.read_text(encoding="utf-8")

    if MARKER_CURRENT_STATUS_START not in content:
        print("Error: index.md is missing auto-update markers. Please restore the template first.", file=sys.stderr)
        return False

    # Process sections
    lines = content.splitlines()
    new_lines = []

    in_current_status = False
    in_active_documents = False
    in_session_history = False
    header_written = False

    for line in lines:
        if MARKER_CURRENT_STATUS_START in line:
            new_lines.append(line)
            in_current_status = True
            new_lines.append(f"- **Current file**: `{active_file}`")
            new_lines.append(f"- **Total Sessions**: {new_session}")
            new_lines.append(f"- **Last Active**: {today}")
            continue

        if MARKER_CURRENT_STATUS_END in line:
            in_current_status = False
            new_lines.append(line)
            continue

        if MARKER_ACTIVE_DOCUMENTS_START in line:
            new_lines.append(line)
            in_active_documents = True
            new_lines.append("| File | Lines | Status |")
            new_lines.append("|------|------|------|")
            new_lines.append(files_table)
            continue

        if MARKER_ACTIVE_DOCUMENTS_END in line:
            in_active_documents = False
            new_lines.append(line)
            continue

        if MARKER_SESSION_HISTORY_START in line:
            new_lines.append(line)
            in_session_history = True
            header_written = False
            continue

        if MARKER_SESSION_HISTORY_END in line:
            in_session_history = False
            new_lines.append(line)
            continue

        if in_current_status:
            continue

        if in_active_documents:
            continue

        if in_session_history:
            new_lines.append(line)
            if re.match(r"^\|\s*-", line) and not header_written:
                new_lines.append(f"| {new_session} | {today} | {title} | {commit_display} |")
                header_written = True
            continue

        new_lines.append(line)

    index_file.write_text("\n".join(new_lines), encoding="utf-8")
    print("[OK] index.md updated.", file=sys.stderr)
    return True


# =============================================================================
# Main Function
# =============================================================================

def _auto_commit_workspace(repo_root: Path) -> None:
    """Stage .cowork-flow/workspace and .cowork-flow/tasks, then commit with a configured message."""
    commit_msg = get_session_commit_message(repo_root)
    subprocess.run(
        ["git", "add", "-A", ".cowork-flow/workspace", ".cowork-flow/tasks"],
        cwd=repo_root,
        capture_output=True,
    )
    # Check if there are staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", ".cowork-flow/workspace", ".cowork-flow/tasks"],
        cwd=repo_root,
    )
    if result.returncode == 0:
        print("[OK] No workspace metadata changes to commit.", file=sys.stderr)
        return
    commit_result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if commit_result.returncode == 0:
        print(f"[OK] Metadata auto-committed: {commit_msg}", file=sys.stderr)
    else:
        print(f"[WARN] Metadata auto-commit failed: {commit_result.stderr.strip()}", file=sys.stderr)


def add_session(
    title: str,
    commit: str = "-",
    summary: str = "(add summary)",
    extra_content: str = "(add details)",
    auto_commit: bool = True,
) -> int:
    """Add a new session."""
    repo_root = get_repo_root()
    ensure_developer(repo_root)

    developer = get_developer(repo_root)
    if not developer:
        print("Error: developer identity has not been initialized.", file=sys.stderr)
        return 1

    dev_dir = get_workspace_dir(repo_root)
    if not dev_dir:
        print("Error: workspace directory not found.", file=sys.stderr)
        return 1

    max_lines = get_max_journal_lines(repo_root)

    index_file = dev_dir / "index.md"
    today = datetime.now().strftime("%Y-%m-%d")

    journal_file, current_num, current_lines = get_latest_journal_info(dev_dir)
    current_session = get_current_session(index_file)
    new_session = current_session + 1

    session_content = generate_session_content(
        new_session, title, commit, summary, extra_content, today
    )
    content_lines = len(session_content.splitlines())

    print("========================================", file=sys.stderr)
    print("Add Session Record", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"Session: {new_session}", file=sys.stderr)
    print(f"Title: {title}", file=sys.stderr)
    print(f"Commit: {commit}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"Current journal file: {FILE_JOURNAL_PREFIX}{current_num}.md", file=sys.stderr)
    print(f"Current lines: {current_lines}", file=sys.stderr)
    print(f"New content lines: {content_lines}", file=sys.stderr)
    print(f"Total lines after append: {current_lines + content_lines}", file=sys.stderr)
    print("", file=sys.stderr)

    target_file = journal_file
    target_num = current_num

    if current_lines + content_lines > max_lines:
        target_num = current_num + 1
        print(f"[!] Over {max_lines} lines, creating {FILE_JOURNAL_PREFIX}{target_num}.md", file=sys.stderr)
        target_file = create_new_journal_file(dev_dir, target_num, developer, today, max_lines)
        print(f"Created: {target_file}", file=sys.stderr)

    # Append session content
    if target_file:
        with target_file.open("a", encoding="utf-8") as f:
            f.write(session_content)
        print(f"[OK] Appended session to {target_file.name}", file=sys.stderr)

    print("", file=sys.stderr)

    # Update index.md
    active_file = f"{FILE_JOURNAL_PREFIX}{target_num}.md"
    if not update_index(index_file, dev_dir, title, commit, new_session, active_file, today):
        return 1

    print("", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print(f"[OK] Session {new_session} recorded successfully.", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print("", file=sys.stderr)
    print("Updated files:", file=sys.stderr)
    print(f"  - {target_file.name if target_file else 'journal'}", file=sys.stderr)
    print("  - index.md", file=sys.stderr)

    # Auto-commit workspace changes
    if auto_commit:
        print("", file=sys.stderr)
        _auto_commit_workspace(repo_root)

    return 0


# =============================================================================
# Main Entry
# =============================================================================

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Append a session record to the journal and update index.md"
    )
    parser.add_argument("--title", required=True, help="Session title")
    parser.add_argument("--commit", default="-", help="Comma-separated commit hashes")
    parser.add_argument("--summary", default="(add summary)", help="Brief summary")
    parser.add_argument("--content-file", help="Path to a file containing detailed content")
    parser.add_argument("--no-commit", action="store_true",
                        help="Skip automatic .cowork-flow metadata commit")

    args = parser.parse_args()

    extra_content = "(add details)"
    if args.content_file:
        content_path = Path(args.content_file)
        if content_path.is_file():
            extra_content = content_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        extra_content = sys.stdin.read()

    return add_session(
        args.title, args.commit, args.summary, extra_content,
        auto_commit=not args.no_commit,
    )


if __name__ == "__main__":
    sys.exit(main())
