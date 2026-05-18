# Template Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将模板应用后的协作资产收敛为根目录 `AGENTS.md`、`.agent/`、`.cowork-flow/`，并用自研 Python 脚本承接 OpenSpec 的核心变更规格能力。

**Architecture:** 保留现有工作流语义，把 Agent 能力放入 `.agent/skills/`，把流程状态、规范、计划、任务、会话和脚本放入 `.cowork-flow/`。通过路径常量、结构测试和全文搜索把旧 `.agents`、`.trellis`、`openspec`、`docs/superpowers` 引用清理为新结构。

**Tech Stack:** Python 3 标准库、`unittest`、现有 Markdown/YAML 文档、现有 cowork-flow 模板脚本。

---

## 文件结构与职责

- Create: `tests/test_template_convergence.py`
  - 验证 `template/` 根目录只暴露 `AGENTS.md`、`.agent/`、`.cowork-flow/` 这组协作入口，并确保不会把 `.DS_Store` 复制到目标项目。
- Create: `tests/test_flow_script_paths.py`
  - 验证脚本路径常量、仓库根目录识别、任务路径解析和 skill 路径生成都使用 `.cowork-flow` / `.agent`。
- Create: `tests/test_change_script.py`
  - 验证 `.cowork-flow/scripts/change.py` 的 `create`、`validate`、`archive`、`list` 成功路径和失败路径。
- Create: `tests/test_no_legacy_template_paths.py`
  - 防止模板文件继续引用旧 `.trellis`、`.agents`、`openspec` 命令或 `docs/superpowers` 路径。
- Create: `template/.cowork-flow/scripts/change.py`
  - 自研变更规格脚本，替代 `openspec new/validate/archive/list` 的模板级能力。
- Modify/Rename: `template/.agents/` -> `template/.agent/`
  - 保留现有 skill，更新路径引用。
- Modify/Rename: `template/.trellis/` -> `template/.cowork-flow/`
  - 保留任务、workspace、spec、scripts、workflow、config。
- Move: `template/docs/superpowers/plans/.gitkeep` -> `template/.cowork-flow/plans/.gitkeep`
  - 模板应用后不再生成根目录 `docs/`。
- Move: `template/openspec/changes/archive/.gitkeep` -> `template/.cowork-flow/changes/archive/.gitkeep`
  - 模板应用后不再生成根目录 `openspec/`。
- Modify: `template/.cowork-flow/scripts/common/paths.py`
  - 将 `DIR_WORKFLOW` 改为 `.cowork-flow`，新增 `DIR_AGENT = ".agent"` 和 `DIR_CHANGES = "changes"`。
- Modify: `template/.cowork-flow/scripts/common/__init__.py`
  - 导出新增目录常量。
- Modify: `template/.cowork-flow/scripts/task.py`
  - 更新任务路径提示、相对路径解析、默认上下文和 skill 路径。
- Modify: `template/.cowork-flow/scripts/add_session.py`
  - 更新自动提交路径和帮助文案。
- Modify: `template/.cowork-flow/scripts/common/developer.py`
  - 更新开发者初始化提示中的目录名称。
- Modify: `template/.cowork-flow/scripts/common/git_context.py`
  - 更新上下文输出中的目录名称。
- Modify: `template/.cowork-flow/scripts/common/config.py`
  - 更新配置说明。
- Modify: `template/.cowork-flow/scripts/common/task_utils.py`
  - 更新示例输出。
- Modify: `template/.cowork-flow/scripts/init_developer.py`
  - 更新 docstring 和提示文案。
- Modify: `template/.cowork-flow/workflow.md`
  - 保留 L0/L1/L2 流程，但替换 OpenSpec CLI 为 `change.py`，并明确 `changes/plans/tasks` 不重复维护 checklist。
- Modify: `template/AGENTS.md`
  - 更新托管说明块，指向 `.cowork-flow/` 和 `.agent/`。
- Modify: `template/.agent/skills/*/SKILL.md`
  - 更新所有旧路径、命令和 OpenSpec 引用。
- Modify: `README.md`
  - 更新仓库结构、快速开始、常用命令和接入原则。

---

### Task 1: 模板根结构收敛

**Files:**
- Create: `tests/test_template_convergence.py`
- Rename: `template/.agents/` -> `template/.agent/`
- Rename: `template/.trellis/` -> `template/.cowork-flow/`
- Move: `template/docs/superpowers/plans/.gitkeep` -> `template/.cowork-flow/plans/.gitkeep`
- Move: `template/openspec/changes/archive/.gitkeep` -> `template/.cowork-flow/changes/archive/.gitkeep`
- Delete: `template/docs/`
- Delete: `template/openspec/`
- Delete: every `template/**/.DS_Store`

- [ ] **Step 1: Write the failing structure test**

```python
# tests/test_template_convergence.py
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class TemplateConvergenceTest(unittest.TestCase):
    def test_template_root_has_only_converged_collaboration_entries(self) -> None:
        entries = {path.name for path in TEMPLATE.iterdir()}

        self.assertIn("AGENTS.md", entries)
        self.assertIn(".agent", entries)
        self.assertIn(".cowork-flow", entries)

        self.assertNotIn(".agents", entries)
        self.assertNotIn(".trellis", entries)
        self.assertNotIn("docs", entries)
        self.assertNotIn("openspec", entries)

    def test_template_does_not_ship_macos_metadata(self) -> None:
        ds_store_files = sorted(
            str(path.relative_to(ROOT))
            for path in TEMPLATE.rglob(".DS_Store")
        )

        self.assertEqual([], ds_store_files)

    def test_required_flow_subdirectories_exist(self) -> None:
        expected = {
            "changes",
            "config.yaml",
            "plans",
            "scripts",
            "spec",
            "tasks",
            "workflow.md",
            "workspace",
        }
        actual = {path.name for path in (TEMPLATE / ".cowork-flow").iterdir()}

        self.assertTrue(expected.issubset(actual))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
rtk python3 -m unittest tests.test_template_convergence -v
```

Expected: FAIL because `template/.agent` and `template/.cowork-flow` do not exist yet, while `.agents`, `.trellis`, `docs`, `openspec`, and `.DS_Store` still exist.

- [ ] **Step 3: Rename directories and move placeholders**

Run:

```bash
rtk git mv template/.agents template/.agent
rtk git mv template/.trellis template/.cowork-flow
rtk mkdir -p template/.cowork-flow/plans template/.cowork-flow/changes/archive
rtk git mv template/docs/superpowers/plans/.gitkeep template/.cowork-flow/plans/.gitkeep
rtk git mv template/openspec/changes/archive/.gitkeep template/.cowork-flow/changes/archive/.gitkeep
rtk git rm -r template/docs template/openspec
rtk find template -name .DS_Store -print
rtk git rm -f template/.DS_Store template/.agent/.DS_Store template/.agent/skills/.DS_Store template/.cowork-flow/.DS_Store
```

If `rtk find template -name .DS_Store -print` returns additional files, remove those exact files with `rtk git rm -f <path>` before continuing.

- [ ] **Step 4: Run the structure test to verify it passes**

Run:

```bash
rtk python3 -m unittest tests.test_template_convergence -v
```

Expected: PASS.

- [ ] **Step 5: Commit the converged root structure**

Run:

```bash
rtk git add tests/test_template_convergence.py template
rtk git commit -m "refactor: converge template root structure"
```

Expected: commit includes the structure test and template directory moves only.

---

### Task 2: 脚本路径常量与任务上下文迁移

**Files:**
- Create: `tests/test_flow_script_paths.py`
- Modify: `template/.cowork-flow/scripts/common/paths.py`
- Modify: `template/.cowork-flow/scripts/common/__init__.py`
- Modify: `template/.cowork-flow/scripts/task.py`
- Modify: `template/.cowork-flow/scripts/add_session.py`
- Modify: `template/.cowork-flow/scripts/common/developer.py`
- Modify: `template/.cowork-flow/scripts/common/git_context.py`
- Modify: `template/.cowork-flow/scripts/common/config.py`
- Modify: `template/.cowork-flow/scripts/common/task_utils.py`
- Modify: `template/.cowork-flow/scripts/init_developer.py`

- [ ] **Step 1: Write the failing path behavior tests**

```python
# tests/test_flow_script_paths.py
from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / ".cowork-flow" / "scripts"


class FlowScriptPathsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(SCRIPTS))
        cls.paths = importlib.import_module("common.paths")
        cls.task = importlib.import_module("task")

    @classmethod
    def tearDownClass(cls) -> None:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))

    def test_workflow_and_agent_directory_constants_are_current(self) -> None:
        self.assertEqual(".cowork-flow", self.paths.DIR_WORKFLOW)
        self.assertEqual(".agent", self.paths.DIR_AGENT)
        self.assertEqual("changes", self.paths.DIR_CHANGES)

    def test_repo_root_detection_uses_cowork_flow_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "src" / "feature"
            nested.mkdir(parents=True)
            (root / ".cowork-flow").mkdir()

            self.assertEqual(root, self.paths.get_repo_root(nested))

    def test_task_relative_paths_accept_cowork_flow_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-18-demo"
            task_dir.mkdir(parents=True)

            resolved = self.task._resolve_task_dir(
                ".cowork-flow/tasks/05-18-demo",
                root,
            )

            self.assertEqual(task_dir, resolved)

    def test_default_context_references_new_skill_directory(self) -> None:
        self.assertEqual(
            ".agent/skills/finish-work/SKILL.md",
            self.task._skill_path("finish-work"),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
rtk python3 -m unittest tests.test_flow_script_paths -v
```

Expected: FAIL because `DIR_AGENT` and `DIR_CHANGES` are not defined, `DIR_WORKFLOW` is still `.trellis`, and `_skill_path()` still returns `.agents/...`.

- [ ] **Step 3: Update shared path constants**

Apply these exact changes in `template/.cowork-flow/scripts/common/paths.py`:

```python
# Directory names
DIR_WORKFLOW = ".cowork-flow"
DIR_AGENT = ".agent"
DIR_WORKSPACE = "workspace"
DIR_TASKS = "tasks"
DIR_ARCHIVE = "archive"
DIR_SPEC = "spec"
DIR_CHANGES = "changes"
DIR_SCRIPTS = "scripts"
```

Also update docstrings in the same file so they describe `.cowork-flow/` instead of `.trellis/`.

- [ ] **Step 4: Export new constants**

In `template/.cowork-flow/scripts/common/__init__.py`, extend the `from .paths import (...)` list with:

```python
    DIR_AGENT,
    DIR_CHANGES,
```

- [ ] **Step 5: Update task.py path helpers and hints**

In `template/.cowork-flow/scripts/task.py`, update `_resolve_task_dir()` so the relative-prefix branch accepts the new workflow directory:

```python
    # Relative path (contains path separator or starts with .cowork-flow)
    if "/" in target_dir or target_dir.startswith(DIR_WORKFLOW):
        return repo_root / target_dir
```

Update `_skill_path()` to:

```python
def _skill_path(name: str) -> str:
    return f".agent/skills/{name}/SKILL.md"
```

Update all user-facing examples and hints in `task.py` from `.trellis/...` to `.cowork-flow/...`.

- [ ] **Step 6: Update automatic metadata commit paths**

In `template/.cowork-flow/scripts/add_session.py`, replace the hard-coded git paths:

```python
["git", "add", "-A", ".trellis/workspace", ".trellis/tasks"]
["git", "diff", "--cached", "--quiet", "--", ".trellis/workspace", ".trellis/tasks"]
```

with:

```python
["git", "add", "-A", ".cowork-flow/workspace", ".cowork-flow/tasks"]
["git", "diff", "--cached", "--quiet", "--", ".cowork-flow/workspace", ".cowork-flow/tasks"]
```

Update the nearby docstring and `--no-commit` help text to say `.cowork-flow`.

- [ ] **Step 7: Update remaining script text references**

Run:

```bash
rtk rg -n "\\.trellis|\\.agents" template/.cowork-flow/scripts -S
```

For every remaining match in `developer.py`, `git_context.py`, `config.py`, `task_utils.py`, `init_developer.py`, and `task.py`, replace old path text with `.cowork-flow` or `.agent` as appropriate.

- [ ] **Step 8: Run the path tests to verify they pass**

Run:

```bash
rtk python3 -m unittest tests.test_flow_script_paths -v
```

Expected: PASS.

- [ ] **Step 9: Run the structure test again**

Run:

```bash
rtk python3 -m unittest tests.test_template_convergence tests.test_flow_script_paths -v
```

Expected: PASS.

- [ ] **Step 10: Commit script path migration**

Run:

```bash
rtk git add tests/test_flow_script_paths.py template/.cowork-flow/scripts
rtk git commit -m "refactor: migrate workflow script paths"
```

Expected: commit contains tests and script path updates only.

---

### Task 3: 自研 change.py 替代 OpenSpec 核心命令

**Files:**
- Create: `tests/test_change_script.py`
- Create: `template/.cowork-flow/scripts/change.py`

- [ ] **Step 1: Write the failing change script tests**

```python
# tests/test_change_script.py
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"


class ChangeScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        shutil.copytree(TEMPLATE, self.repo)
        self.script = self.repo / ".cowork-flow" / "scripts" / "change.py"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_change(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_create_generates_change_scaffold(self) -> None:
        result = self.run_change("create", "replace-auth")

        self.assertEqual(0, result.returncode, result.stderr)
        change_dir = self.repo / ".cowork-flow" / "changes" / "replace-auth"
        self.assertTrue((change_dir / "change.yaml").is_file())
        self.assertTrue((change_dir / "proposal.md").is_file())
        self.assertTrue((change_dir / "design.md").is_file())
        self.assertTrue((change_dir / "specs" / ".gitkeep").is_file())
        self.assertIn("slug: replace-auth", (change_dir / "change.yaml").read_text())

    def test_validate_requires_non_empty_behavior_spec_unless_documentation_only(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)

        failed = self.run_change("validate", "replace-auth")
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("specs", failed.stderr)

        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "specs" / "backend" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        passed = self.run_change("validate", "replace-auth")
        self.assertEqual(0, passed.returncode, passed.stderr)
        self.assertIn("valid", passed.stdout)

    def test_validate_requires_design_for_l2_change(self) -> None:
        self.assertEqual(0, self.run_change("create", "cross-layer-auth", "--level", "L2").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "cross-layer-auth" / "specs" / "backend" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Cross-layer behavior\n\n- Frontend and backend share the same contract.\n", encoding="utf-8")

        failed = self.run_change("validate", "cross-layer-auth")
        self.assertNotEqual(0, failed.returncode)
        self.assertIn("design.md", failed.stderr)

        design = self.repo / ".cowork-flow" / "changes" / "cross-layer-auth" / "design.md"
        design.write_text("# Design\n\nUse one explicit API contract.\n", encoding="utf-8")

        passed = self.run_change("validate", "cross-layer-auth")
        self.assertEqual(0, passed.returncode, passed.stderr)

    def test_archive_requires_valid_change_and_moves_to_month_archive(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)
        spec = self.repo / ".cowork-flow" / "changes" / "replace-auth" / "specs" / "backend" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("# Backend behavior\n\n- The API returns 200.\n", encoding="utf-8")

        archived = self.run_change("archive", "replace-auth")

        self.assertEqual(0, archived.returncode, archived.stderr)
        self.assertFalse((self.repo / ".cowork-flow" / "changes" / "replace-auth").exists())
        archive_root = self.repo / ".cowork-flow" / "changes" / "archive"
        matches = list(archive_root.glob("*/replace-auth/change.yaml"))
        self.assertEqual(1, len(matches))

    def test_list_prints_active_changes(self) -> None:
        self.assertEqual(0, self.run_change("create", "replace-auth").returncode)

        listed = self.run_change("list")

        self.assertEqual(0, listed.returncode, listed.stderr)
        self.assertIn("replace-auth", listed.stdout)
        self.assertIn("draft", listed.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
rtk python3 -m unittest tests.test_change_script -v
```

Expected: FAIL because `template/.cowork-flow/scripts/change.py` does not exist.

- [ ] **Step 3: Create change.py with minimal standard-library implementation**

Create `template/.cowork-flow/scripts/change.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manage cowork-flow behavior changes without the external OpenSpec CLI."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from common.paths import DIR_ARCHIVE, DIR_CHANGES, DIR_WORKFLOW, get_repo_root


VALID_LEVELS = {"L1", "L2"}
VALID_STATUSES = {"draft", "active", "archived"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _changes_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / DIR_CHANGES


def _change_dir(repo_root: Path, slug: str) -> Path:
    return _changes_dir(repo_root) / slug


def _metadata_path(change_dir: Path) -> Path:
    return change_dir / "change.yaml"


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "1"}


def _read_simple_yaml(path: Path) -> dict[str, str | None]:
    data: dict[str, str | None] = {}
    if not path.is_file():
        return data

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        data[key.strip()] = None if value == "null" else value
    return data


def _write_metadata(path: Path, data: dict[str, str | None]) -> None:
    lines = []
    for key, value in data.items():
        rendered = "null" if value is None else value
        lines.append(f"{key}: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def _spec_files(change_dir: Path) -> list[Path]:
    specs_dir = change_dir / "specs"
    if not specs_dir.is_dir():
        return []
    return sorted(path for path in specs_dir.glob("**/spec.md") if path.is_file())


def _validate_slug(slug: str) -> list[str]:
    if SLUG_RE.match(slug):
        return []
    return [f"invalid slug: {slug}. Use lowercase words separated by hyphens."]


def _validate_change(repo_root: Path, slug: str) -> list[str]:
    errors = _validate_slug(slug)
    change_dir = _change_dir(repo_root, slug)
    metadata = _read_simple_yaml(_metadata_path(change_dir))

    if not change_dir.is_dir():
        return [f"change not found: {DIR_WORKFLOW}/{DIR_CHANGES}/{slug}"]

    if not metadata:
        errors.append("change.yaml is missing or empty")

    if metadata.get("slug") != slug:
        errors.append("change.yaml slug must match the change directory name")

    level = metadata.get("level") or "L1"
    if level not in VALID_LEVELS:
        errors.append("change.yaml level must be L1 or L2")

    status = metadata.get("status") or "draft"
    if status not in VALID_STATUSES:
        errors.append("change.yaml status must be draft, active, or archived")

    if not _non_empty_file(change_dir / "proposal.md"):
        errors.append("proposal.md is missing or empty")

    documentation_only = _is_true(metadata.get("documentation_only"))
    if not documentation_only and not _spec_files(change_dir):
        errors.append("specs must contain at least one specs/<area>/spec.md file")

    if level == "L2" and not _non_empty_file(change_dir / "design.md"):
        errors.append("design.md is required and must be non-empty for L2 changes")

    plan = metadata.get("plan")
    if plan and not (repo_root / plan).exists():
        errors.append(f"linked plan does not exist: {plan}")

    task = metadata.get("task")
    if task and not (repo_root / task).exists():
        errors.append(f"linked task does not exist: {task}")

    return errors


def cmd_create(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors = _validate_slug(args.slug)
    if errors:
        print(errors[0], file=sys.stderr)
        return 1

    if args.level not in VALID_LEVELS:
        print("level must be L1 or L2", file=sys.stderr)
        return 1

    change_dir = _change_dir(repo_root, args.slug)
    if change_dir.exists():
        print(f"change already exists: {change_dir}", file=sys.stderr)
        return 1

    (change_dir / "specs").mkdir(parents=True)
    (change_dir / "specs" / ".gitkeep").write_text("", encoding="utf-8")
    (change_dir / "proposal.md").write_text(
        f"# Proposal: {args.slug}\n\n## Why\n\n## What Changes\n\n## Acceptance Criteria\n",
        encoding="utf-8",
    )
    (change_dir / "design.md").write_text("", encoding="utf-8")
    _write_metadata(
        _metadata_path(change_dir),
        {
            "slug": args.slug,
            "status": "draft",
            "level": args.level,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "documentation_only": "false",
            "plan": None,
            "task": None,
        },
    )

    print(f"created {DIR_WORKFLOW}/{DIR_CHANGES}/{args.slug}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors = _validate_change(repo_root, args.slug)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"valid {DIR_WORKFLOW}/{DIR_CHANGES}/{args.slug}")
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    errors = _validate_change(repo_root, args.slug)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    source = _change_dir(repo_root, args.slug)
    archive_month = datetime.now().strftime("%Y-%m")
    target = _changes_dir(repo_root) / DIR_ARCHIVE / archive_month / args.slug
    if target.exists():
        print(f"archive target already exists: {target}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    metadata_path = _metadata_path(target)
    metadata = _read_simple_yaml(metadata_path)
    metadata["status"] = "archived"
    metadata["archived_at"] = datetime.now(timezone.utc).isoformat()
    _write_metadata(metadata_path, metadata)

    print(f"archived {DIR_WORKFLOW}/{DIR_CHANGES}/{DIR_ARCHIVE}/{archive_month}/{args.slug}")
    return 0


def _iter_active_changes(repo_root: Path) -> list[Path]:
    changes_dir = _changes_dir(repo_root)
    if not changes_dir.is_dir():
        return []
    return sorted(
        path
        for path in changes_dir.iterdir()
        if path.is_dir() and path.name != DIR_ARCHIVE
    )


def _iter_archived_changes(repo_root: Path) -> list[Path]:
    archive_dir = _changes_dir(repo_root) / DIR_ARCHIVE
    if not archive_dir.is_dir():
        return []
    return sorted(path for path in archive_dir.glob("*/*") if path.is_dir())


def _print_change(path: Path, archived: bool) -> None:
    metadata = _read_simple_yaml(_metadata_path(path))
    status = metadata.get("status") or ("archived" if archived else "draft")
    level = metadata.get("level") or "L1"
    plan = metadata.get("plan") or "-"
    task = metadata.get("task") or "-"
    label = "archived" if archived else "active"
    print(f"{label}\t{path.name}\t{level}\t{status}\tplan={plan}\ttask={task}")


def cmd_list(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    active = _iter_active_changes(repo_root)
    archived = _iter_archived_changes(repo_root)

    if not active and not archived:
        print("No changes.")
        return 0

    for path in active:
        _print_change(path, archived=False)
    for path in archived:
        _print_change(path, archived=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage cowork-flow behavior changes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a behavior change")
    create.add_argument("slug", help="lowercase hyphenated change slug")
    create.add_argument("--level", choices=sorted(VALID_LEVELS), default="L1")
    create.set_defaults(func=cmd_create)

    validate = subparsers.add_parser("validate", help="Validate a behavior change")
    validate.add_argument("slug")
    validate.set_defaults(func=cmd_validate)

    archive = subparsers.add_parser("archive", help="Archive a validated behavior change")
    archive.add_argument("slug")
    archive.set_defaults(func=cmd_archive)

    list_changes = subparsers.add_parser("list", help="List active and archived changes")
    list_changes.set_defaults(func=cmd_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run change script tests**

Run:

```bash
rtk python3 -m unittest tests.test_change_script -v
```

Expected: PASS.

- [ ] **Step 5: Run all current tests**

Run:

```bash
rtk python3 -m unittest tests.test_template_convergence tests.test_flow_script_paths tests.test_change_script -v
```

Expected: PASS.

- [ ] **Step 6: Commit change script**

Run:

```bash
rtk git add tests/test_change_script.py template/.cowork-flow/scripts/change.py
rtk git commit -m "feat: add cowork-flow change script"
```

Expected: commit contains `change.py` and tests.

---

### Task 4: 工作流文档、AGENTS 与 skills 路径更新

**Files:**
- Create: `tests/test_no_legacy_template_paths.py`
- Modify: `template/AGENTS.md`
- Modify: `template/.cowork-flow/workflow.md`
- Modify: `template/.agent/skills/break-loop/SKILL.md`
- Modify: `template/.agent/skills/check-cross-layer/SKILL.md`
- Modify: `template/.agent/skills/finish-work/SKILL.md`
- Modify: `template/.agent/skills/record-session/SKILL.md`
- Modify: `template/.agent/skills/start/SKILL.md`
- Modify: `template/.agent/skills/update-spec/SKILL.md`
- Modify: `template/.cowork-flow/config.yaml`
- Modify: `template/.cowork-flow/workspace/index.md`

- [ ] **Step 1: Write the failing legacy-path scan test**

```python
# tests/test_no_legacy_template_paths.py
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
FORBIDDEN_PATTERNS = (
    ".trellis",
    ".agents",
    "docs/superpowers",
    "openspec new",
    "openspec validate",
    "openspec archive",
    "openspec/changes",
    "openspec/config.yaml",
)


class NoLegacyTemplatePathsTest(unittest.TestCase):
    def test_template_text_files_do_not_reference_legacy_paths(self) -> None:
        offenders: list[str] = []
        text_files = [
            path
            for path in TEMPLATE.rglob("*")
            if path.is_file() and path.suffix in {".md", ".py", ".yaml", ".gitignore"}
        ]

        for path in text_files:
            content = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in content:
                    offenders.append(f"{path.relative_to(ROOT)} contains {pattern}")

        self.assertEqual([], offenders)

    def test_change_directories_do_not_define_tasks_md(self) -> None:
        tasks_files = sorted(
            str(path.relative_to(ROOT))
            for path in (TEMPLATE / ".cowork-flow" / "changes").rglob("tasks.md")
        )

        self.assertEqual([], tasks_files)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the scan test to verify it fails**

Run:

```bash
rtk python3 -m unittest tests.test_no_legacy_template_paths -v
```

Expected: FAIL because workflow, skills, README-adjacent template docs, and scripts still mention old paths.

- [ ] **Step 3: Update template/AGENTS.md**

Replace the managed Trellis block with this wording:

```markdown
<!-- COWORK-FLOW:START -->
# cowork-flow Instructions

These instructions are for AI assistants working in this project.

Use the `.agent/skills/start` skill when starting a new session to:
- Initialize your developer identity
- Understand current project context
- Read relevant guidelines

Use `@/.cowork-flow/` to learn:
- Development workflow (`workflow.md`)
- Project structure guidelines (`spec/`)
- Developer workspace (`workspace/`)

Use `@/.agent/skills/` for reusable local skills.

Keep this managed block so cowork-flow updates can refresh the instructions.

<!-- COWORK-FLOW:END -->
```

- [ ] **Step 4: Update workflow.md L1/L2 sections**

In `template/.cowork-flow/workflow.md`, replace OpenSpec-specific commands with:

```bash
python3 ./.cowork-flow/scripts/change.py create <slug>
python3 ./.cowork-flow/scripts/change.py validate <slug>
python3 ./.cowork-flow/scripts/change.py archive <slug>
```

Update the L1/L2 persistence rules:

```markdown
`.cowork-flow/changes/<slug>/` 只保存 proposal、design、behavior specs 和 change.yaml。
实现 checklist 只保存在 `.cowork-flow/plans/*.md`。
任务运行状态只保存在 `.cowork-flow/tasks/`。
```

- [ ] **Step 5: Update skill command references**

Run:

```bash
rtk perl -0pi -e 's#\\.trellis#\\.cowork-flow#g; s#\\.agents#\\.agent#g; s#docs/superpowers/plans#\\.cowork-flow/plans#g; s#openspec/changes#\\.cowork-flow/changes#g' template/.agent/skills/*/SKILL.md template/.cowork-flow/workflow.md template/.cowork-flow/workspace/index.md template/.cowork-flow/config.yaml
```

Then manually replace command text in `template/.agent/skills/start/SKILL.md`:

```text
openspec new change <slug>
openspec validate --strict --type change <slug>
openspec archive <slug>
```

with:

```text
python3 ./.cowork-flow/scripts/change.py create <slug>
python3 ./.cowork-flow/scripts/change.py validate <slug>
python3 ./.cowork-flow/scripts/change.py archive <slug>
```

Remove any instruction that asks maintainers to update `.cowork-flow/changes/<slug>/tasks.md`; plan checkboxes live in `.cowork-flow/plans/`.

- [ ] **Step 6: Run legacy scan test**

Run:

```bash
rtk python3 -m unittest tests.test_no_legacy_template_paths -v
```

Expected: PASS.

- [ ] **Step 7: Run all tests**

Run:

```bash
rtk python3 -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 8: Commit docs and skills migration**

Run:

```bash
rtk git add tests/test_no_legacy_template_paths.py template/AGENTS.md template/.agent template/.cowork-flow
rtk git commit -m "docs: update workflow paths for cowork-flow"
```

Expected: commit contains template docs, skills, workflow, and scan test.

---

### Task 5: README 与模板接入说明更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing README assertions inside the existing scan test**

Append this test to `tests/test_no_legacy_template_paths.py`:

```python
    def test_readme_documents_converged_template_structure(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", readme)
        self.assertIn(".agent/", readme)
        self.assertIn(".cowork-flow/", readme)
        self.assertIn("python3 ./.cowork-flow/scripts/change.py create <slug>", readme)

        self.assertNotIn(".trellis/", readme)
        self.assertNotIn(".agents/", readme)
        self.assertNotIn("docs/superpowers/", readme)
        self.assertNotIn("openspec/", readme)
        self.assertNotIn("openspec new", readme)
```

- [ ] **Step 2: Run README test to verify it fails**

Run:

```bash
rtk python3 -m unittest tests.test_no_legacy_template_paths.NoLegacyTemplatePathsTest.test_readme_documents_converged_template_structure -v
```

Expected: FAIL because README still documents old directories and commands.

- [ ] **Step 3: Rewrite README structure section**

Update the README structure block to:

```markdown
## 仓库结构

```text
.
├── README.md
└── template/
    ├── AGENTS.md
    ├── .agent/
    │   └── skills/
    └── .cowork-flow/
        ├── config.yaml
        ├── workflow.md
        ├── scripts/
        ├── spec/
        ├── changes/
        ├── plans/
        ├── tasks/
        └── workspace/
```
```

- [ ] **Step 4: Rewrite README template content descriptions**

Use this content as the canonical wording:

```markdown
`template/AGENTS.md`
项目级协作约定入口，包含编码前思考、简单优先、外科手术式改动、验证优先等基础原则。接入项目后，应把项目名称、技术栈、运行命令、测试命令和提交策略补齐。

`template/.agent/skills/`
本地技能入口，覆盖开始工作、收尾验证、记录 session、更新规范、跨层检查等常见协作动作。这里的 skill 应保持通用，不承载某个业务项目的一次性细节。

`template/.cowork-flow/`
cowork-flow 工作流目录，包含流程说明、任务状态、开发者工作区、项目规范、行为变更规格、实现计划和辅助脚本。

`template/.cowork-flow/changes/`
行为变更规格目录，用自研 `change.py` 管理 proposal、design、behavior specs 和归档。不维护实现 checklist。

`template/.cowork-flow/plans/`
实现计划目录，保存可执行步骤、验证方式和执行状态。
```

- [ ] **Step 5: Rewrite README command examples**

Use `.cowork-flow` commands:

```markdown
初始化或查看开发者身份：

```bash
python3 ./.cowork-flow/scripts/get_developer.py
python3 ./.cowork-flow/scripts/init_developer.py <developer-name>
```

查看当前上下文：

```bash
python3 ./.cowork-flow/scripts/get_context.py
python3 ./.cowork-flow/scripts/task.py list
```

创建行为变更：

```bash
python3 ./.cowork-flow/scripts/change.py create <slug>
python3 ./.cowork-flow/scripts/change.py validate <slug>
```

创建并启动任务：

```bash
python3 ./.cowork-flow/scripts/task.py create "<title>" --slug <task-name>
python3 ./.cowork-flow/scripts/task.py start <task-dir>
```

记录 session：

```bash
python3 ./.cowork-flow/scripts/get_context.py --mode record
python3 ./.cowork-flow/scripts/add_session.py \
  --title "<session-title>" \
  --commit "<commit-or-handoff-ref>" \
  --summary "<summary>"
```
```

- [ ] **Step 6: Run README test**

Run:

```bash
rtk python3 -m unittest tests.test_no_legacy_template_paths.NoLegacyTemplatePathsTest.test_readme_documents_converged_template_structure -v
```

Expected: PASS.

- [ ] **Step 7: Run all tests**

Run:

```bash
rtk python3 -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 8: Commit README update**

Run:

```bash
rtk git add README.md tests/test_no_legacy_template_paths.py
rtk git commit -m "docs: document cowork-flow template structure"
```

Expected: commit contains README and README scan test.

---

### Task 6: 端到端验证与最终清理

**Files:**
- Modify only if verification reveals missed references:
  - `README.md`
  - `template/AGENTS.md`
  - `template/.agent/skills/*/SKILL.md`
  - `template/.cowork-flow/**/*`
  - `tests/*`

- [ ] **Step 1: Run the complete unittest suite**

Run:

```bash
rtk python3 -m unittest discover -s tests -v
```

Expected: PASS for all tests.

- [ ] **Step 2: Verify no forbidden root-level template directories remain**

Run:

```bash
rtk test -d template/.agent
rtk test -d template/.cowork-flow
rtk test ! -e template/.agents
rtk test ! -e template/.trellis
rtk test ! -e template/docs
rtk test ! -e template/openspec
```

Expected: all commands exit 0.

- [ ] **Step 3: Verify legacy references are gone from template and README**

Run:

```bash
rtk rg -n "\\.trellis|\\.agents|docs/superpowers|openspec new|openspec validate|openspec archive|openspec/changes|openspec/config.yaml" README.md template tests
```

Expected: no matches.

- [ ] **Step 4: Verify change.py manually in a copied template**

Run:

```bash
rtk mktemp -d
```

If the command prints a temp directory path, use it as `<tmp>`, then run:

```bash
rtk mkdir -p <tmp>/cowork-flow-smoke
rtk rsync -a template/ <tmp>/cowork-flow-smoke/
rtk python3 <tmp>/cowork-flow-smoke/.cowork-flow/scripts/change.py create smoke-change
rtk mkdir -p <tmp>/cowork-flow-smoke/.cowork-flow/changes/smoke-change/specs/general
rtk python3 -c "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('# Smoke\n\n- Works.\n', encoding='utf-8')" <tmp>/cowork-flow-smoke/.cowork-flow/changes/smoke-change/specs/general/spec.md
rtk python3 <tmp>/cowork-flow-smoke/.cowork-flow/scripts/change.py validate smoke-change
rtk python3 <tmp>/cowork-flow-smoke/.cowork-flow/scripts/change.py archive smoke-change
```

Expected: create, validate, and archive all exit 0.

- [ ] **Step 5: Inspect git status for unrelated pre-existing files**

Run:

```bash
rtk git status --short
```

Expected: only intended changes for this migration are present. If unrelated `.idea/` or user-created files remain, leave them untracked and mention them in the final handoff.

- [ ] **Step 6: Commit final cleanup if needed**

Run only if Task 6 required edits:

```bash
rtk git add README.md template tests
rtk git commit -m "chore: verify cowork-flow template convergence"
```

Expected: commit contains only final cleanup or verification fixes.

---

## 自审记录

- **Spec coverage:** 计划覆盖根目录收敛、`.agent` skills、`.cowork-flow` workflow/scripts/spec/tasks/workspace/plans/changes、自研 `change.py`、OpenSpec 移除、三类状态不重复、README/AGENTS/workflow/skills/scripts 路径统一。
- **Placeholder scan:** 未使用占位词或“类似前面”式说明；每个代码步骤给出具体文件内容或具体替换内容。
- **Type consistency:** 统一使用 `.cowork-flow`、`.agent`、`DIR_WORKFLOW`、`DIR_AGENT`、`DIR_CHANGES`、`change.yaml`、`documentation_only`。
- **风险提示:** 当前工作区已有已暂存 `.DS_Store` 和未跟踪 `.idea/`；执行 Task 1 时应把 `template/**/.DS_Store` 作为模板清理项处理，但不要处理根目录 `.idea/`，除非用户另行要求。
