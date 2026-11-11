#!/usr/bin/env python3
"""Repository-root, developer and task-directory paths."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


# Renaming an on-disk directory starts here.
# Directory names
DIR_WORKFLOW = ".cowork-flow"
DIR_AGENTS = ".agents"
DIR_TASKS = "tasks"
DIR_ARCHIVE = "archive"
DIR_SPEC = "spec"
DIR_SCRIPTS = "scripts"

# File names
FILE_DEVELOPER = ".developer"
FILE_TASK_JSON = "task.json"
RUNTIME_IGNORE_TEXT = "*\n!.gitignore\n"
TASK_DATE_PREFIX_PATTERN = re.compile(r"^\d{2}-\d{2}-")
FULL_DATE_PREFIX_PATTERN = re.compile(r"^\d{4}-(\d{2}-\d{2}-)")


def get_repo_root(start_path: Path | None = None) -> Path:
    """Walk up to the nearest directory holding .cowork-flow/.

    Nested repositories resolve to the inner root; with no marker the
    working directory is returned, not start_path.
    """
    current = (start_path or Path.cwd()).absolute()

    while current != current.parent:
        if (current / DIR_WORKFLOW).is_dir():
            return current
        current = current.parent

    # Fallback to current directory if no .cowork-flow/ found
    return Path.cwd().absolute()


def get_developer(repo_root: Path | None = None) -> str | None:
    """Developer name, or None when unset or still a <placeholder>."""
    if repo_root is None:
        repo_root = get_repo_root()

    dev_file = repo_root / DIR_WORKFLOW / FILE_DEVELOPER

    if not dev_file.is_file():
        return None

    try:
        content = dev_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("name="):
                name = line.split("=", 1)[1].strip()
                if not name or (name.startswith("<") and name.endswith(">")):
                    return None
                return name
    except (OSError, IOError):
        pass

    return None


def check_developer(repo_root: Path | None = None) -> bool:
    """True when a developer name is recorded."""
    return get_developer(repo_root) is not None


def get_tasks_dir(repo_root: Path | None = None) -> Path:
    """Tasks directory under the repo root."""
    if repo_root is None:
        repo_root = get_repo_root()
    return repo_root / DIR_WORKFLOW / DIR_TASKS


def runtime_root_for(path: Path) -> Path | None:
    """The `.cowork-flow/.runtime` root containing path, if any."""
    for parent in Path(path).absolute().parents:
        if parent.name == ".runtime" and parent.parent.name == DIR_WORKFLOW:
            return parent
    return None


def ensure_runtime_gitignore(path: Path) -> None:
    """Create the runtime self-ignore file once; never overwrite it."""
    runtime_root = runtime_root_for(path)
    if runtime_root is None:
        return
    ignore = runtime_root / ".gitignore"
    if ignore.exists():
        return
    try:
        runtime_root.mkdir(parents=True, exist_ok=True)
        with ignore.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(RUNTIME_IGNORE_TEXT)
    except OSError:
        return


def generate_task_date_prefix() -> str:
    """Today's MM-DD task-directory prefix."""
    return datetime.now().strftime("%m-%d")


def ensure_task_date_prefix(slug: str) -> str:
    """Return slug with exactly one MM-DD prefix.

    A full YYYY-MM-DD- prefix is normalized to MM-DD-; a bare slug
    gets today's MM-DD prefix.
    """
    full = FULL_DATE_PREFIX_PATTERN.match(slug)
    if full:
        return full.group(1) + slug[full.end():]
    if TASK_DATE_PREFIX_PATTERN.match(slug):
        return slug
    return f"{generate_task_date_prefix()}-{slug}"


if __name__ == "__main__":
    repo = get_repo_root()
    print(f"Repository root: {repo}")
    print(f"Developer: {get_developer(repo)}")
    print(f"Tasks dir: {get_tasks_dir(repo)}")
