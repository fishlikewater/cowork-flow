#!/usr/bin/env python3
"""
Developer management utilities.

Provides:
    init_developer     - Initialize developer
    ensure_developer   - Ensure developer is initialized (exit if not)
    show_developer_info - Show developer information
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from .paths import (
    DIR_WORKFLOW,
    DIR_WORKSPACE,
    DIR_TASKS,
    FILE_DEVELOPER,
    FILE_JOURNAL_PREFIX,
    get_repo_root,
    get_developer,
    check_developer,
)


# =============================================================================
# Developer Initialization
# =============================================================================

def init_developer(name: str, repo_root: Path | None = None) -> bool:
    """Initialize developer.

    Creates:
        - .trellis/.developer file with developer info
        - .trellis/workspace/<name>/ directory structure
        - Initial journal file and index.md

    Args:
        name: Developer name.
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        True on success, False on error.
    """
    if not name:
        print("错误：开发者名称不能为空。", file=sys.stderr)
        return False

    if repo_root is None:
        repo_root = get_repo_root()

    dev_file = repo_root / DIR_WORKFLOW / FILE_DEVELOPER
    workspace_dir = repo_root / DIR_WORKFLOW / DIR_WORKSPACE / name

    # Create .developer file
    initialized_at = datetime.now().isoformat()
    try:
        dev_file.write_text(
            f"name={name}\ninitialized_at={initialized_at}\n",
            encoding="utf-8"
        )
    except (OSError, IOError) as e:
        print(f"错误：创建 .developer 文件失败：{e}", file=sys.stderr)
        return False

    # Create workspace directory structure
    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, IOError) as e:
        print(f"错误：创建工作区目录失败：{e}", file=sys.stderr)
        return False

    # Create initial journal file
    journal_file = workspace_dir / f"{FILE_JOURNAL_PREFIX}1.md"
    if not journal_file.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        journal_content = f"""# 开发日志 - {name}（第 1 部分）

> AI 开发会话日志
> 开始时间：{today}

---

"""
        try:
            journal_file.write_text(journal_content, encoding="utf-8")
        except (OSError, IOError) as e:
            print(f"错误：创建日志文件失败：{e}", file=sys.stderr)
            return False

    # Create index.md with markers for auto-update
    index_file = workspace_dir / "index.md"
    if not index_file.exists():
        index_content = f"""# 工作区索引 - {name}

> 用于跟踪 AI 开发会话记录。

---

## 当前状态

<!-- @@@auto:current-status -->
- **当前文件**：`journal-1.md`
- **总会话数**：0
- **最近活跃**：-
<!-- @@@/auto:current-status -->

---

## 活跃文档

<!-- @@@auto:active-documents -->
| 文件 | 行数 | 状态 |
|------|------|------|
| `journal-1.md` | ~0 | 当前 |
<!-- @@@/auto:active-documents -->

---

## 会话历史

<!-- @@@auto:session-history -->
| # | 日期 | 标题 | 提交 |
|---|------|------|------|
<!-- @@@/auto:session-history -->

---

## 说明

- 会话会追加到 journal 文件
- 当前文件超过 2000 行时会自动新建下一份 journal
- 使用 `add_session.py` 记录会话
- 新增记录统一使用中文，历史英文记录可保留
"""
        try:
            index_file.write_text(index_content, encoding="utf-8")
        except (OSError, IOError) as e:
            print(f"错误：创建 index.md 失败：{e}", file=sys.stderr)
            return False

    print(f"开发者已初始化：{name}")
    print(f"  .developer 文件：{dev_file}")
    print(f"  工作区目录：{workspace_dir}")

    return True


def ensure_developer(repo_root: Path | None = None) -> None:
    """Ensure developer is initialized, exit if not.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    if not check_developer(repo_root):
        print("错误：开发者身份尚未初始化。", file=sys.stderr)
        print(f"请执行：python3 ./{DIR_WORKFLOW}/scripts/init_developer.py <your-name>", file=sys.stderr)
        sys.exit(1)


def show_developer_info(repo_root: Path | None = None) -> None:
    """Show developer information.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    developer = get_developer(repo_root)

    if not developer:
        print("开发者：未初始化")
    else:
        print(f"开发者：{developer}")
        print(f"工作区：{DIR_WORKFLOW}/{DIR_WORKSPACE}/{developer}/")
        print(f"任务目录：{DIR_WORKFLOW}/{DIR_TASKS}/")


# =============================================================================
# Main Entry (for testing)
# =============================================================================

if __name__ == "__main__":
    show_developer_info()
