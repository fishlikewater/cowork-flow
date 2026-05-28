# Clean-room Trellis-like Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not use subagent-driven-development for this rewrite, because the work changes subagent behavior itself. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild cowork-flow's default execution model around session-scoped tasks and fixed `cowork-research` / `cowork-implement` / `cowork-check` subagents, removing old agent-team-centered paths.

**Architecture:** Add a focused active-task runtime under `.cowork-flow/.runtime/sessions/`, make task scripts depend on explicit session context, and rewrite workflow/skills around fixed-role subagents that self-load task context from `Active task: <task>`. Remove agent-team state-machine scripts, skills, config, and tests when they no longer serve the new model.

**Tech Stack:** Python 3 scripts under `.cowork-flow/scripts`, Node test runner, Python `unittest`, Markdown skills/templates.

---

## File Structure

- Create: `.cowork-flow/scripts/common/active_task.py`
  - Owns context-key resolution and session pointer read/write/clear.
- Create: `template/.cowork-flow/scripts/common/active_task.py`
  - Template mirror of the runtime helper.
- Modify: `.cowork-flow/scripts/task.py`
  - Use active-task helper for `create/start/current/finish/archive`; remove `.current-task` logic.
- Modify: `template/.cowork-flow/scripts/task.py`
  - Template mirror.
- Modify: `.cowork-flow/scripts/common/paths.py`
  - Remove current-task file helpers and constants.
- Modify: `template/.cowork-flow/scripts/common/paths.py`
  - Template mirror.
- Modify: `.cowork-flow/scripts/common/git_context.py`
  - Render session-scoped current task in resume context.
- Modify: `template/.cowork-flow/scripts/common/git_context.py`
  - Template mirror.
- Modify: `.cowork-flow/scripts/resume.py`
  - Resume from session-scoped active task; remove worker/agent-team warnings if agent-team is deleted.
- Modify: `template/.cowork-flow/scripts/resume.py`
  - Template mirror.
- Create: `.codex/agents/cowork-research.toml`, `.codex/agents/cowork-implement.toml`, `.codex/agents/cowork-check.toml`
  - Project agent definitions when Codex supports them.
- Create: `template/.codex/agents/cowork-research.toml`, `template/.codex/agents/cowork-implement.toml`, `template/.codex/agents/cowork-check.toml`
  - Template mirrors.
- Modify: `.agent/skills/start/SKILL.md`, `.agent/skills/finish-work/SKILL.md`, `.agent/skills/check-cross-layer/SKILL.md`
  - New default route.
- Modify: matching files under `template/.agent/skills/`
  - Template mirrors.
- Modify: `.cowork-flow/workflow.md`, `template/.cowork-flow/workflow.md`
  - New Plan/Implement/Check/Finish flow.
- Delete: `.agent/skills/agent-team-execution/SKILL.md`, `template/.agent/skills/agent-team-execution/SKILL.md`
  - Old default runtime skill.
- Delete: `.cowork-flow/scripts/agent_team.py`, `.cowork-flow/scripts/common/agent_team.py`, `.cowork-flow/agent-team/`
  - Old state machine, if no remaining tests or commands require it.
- Delete: template mirrors of agent-team scripts/config.
- Modify/Delete: tests under `tests/test_agent_team_*`, `tests/test_worker_execution_context.py`, `tests/test_subagent_recovery.py`
  - Replace with new tests or remove obsolete coverage.

---

## Current Execution Status

Not started. Design change exists at `.cowork-flow/changes/05-28-clean-room-trellis-like-rewrite/`.

---

### Task 1: Add Session-scoped Active Task Runtime

**Files:**
- Create: `.cowork-flow/scripts/common/active_task.py`
- Create: `template/.cowork-flow/scripts/common/active_task.py`
- Test: `tests/test_active_task_runtime.py`

- [ ] **Step 1: Write failing tests for context-key behavior**

Create `tests/test_active_task_runtime.py`:

```python
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers.flow_imports import import_flow_module


class ActiveTaskRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.active_task = import_flow_module("common.active_task")

    def test_context_key_uses_cowork_env_first(self) -> None:
        with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main window"}, clear=True):
            self.assertEqual("main_window", self.active_task.resolve_context_key())

    def test_context_key_uses_codex_session_when_cowork_missing(self) -> None:
        with patch.dict(os.environ, {"CODEX_SESSION_ID": "abc-123"}, clear=True):
            self.assertEqual("codex_abc-123", self.active_task.resolve_context_key())

    def test_context_key_missing_returns_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.active_task.resolve_context_key())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_active_task_runtime -v`

Expected: FAIL or ERROR because `common.active_task` does not exist.

- [ ] **Step 3: Implement context key helper**

Add `.cowork-flow/scripts/common/active_task.py` and mirror it to `template/.cowork-flow/scripts/common/active_task.py`:

```python
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import DIR_WORKFLOW

DIR_RUNTIME = ".runtime"
DIR_SESSIONS = "sessions"


@dataclass(frozen=True)
class ActiveTask:
    task_path: str | None
    context_key: str | None
    source: str


def _sanitize(raw: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip()).strip("._-")
    return safe[:160]


def resolve_context_key() -> str | None:
    explicit = os.environ.get("COWORK_FLOW_CONTEXT_ID")
    if explicit and explicit.strip():
        return _sanitize(explicit)

    codex_session = os.environ.get("CODEX_SESSION_ID")
    if codex_session and codex_session.strip():
        return f"codex_{_sanitize(codex_session)}"

    codex_thread = os.environ.get("CODEX_THREAD_ID")
    if codex_thread and codex_thread.strip():
        return f"codex_{_sanitize(codex_thread)}"

    return None


def sessions_dir(repo_root: Path) -> Path:
    return repo_root / DIR_WORKFLOW / DIR_RUNTIME / DIR_SESSIONS
```

- [ ] **Step 4: Run test to verify context-key tests pass**

Run: `python -m unittest tests.test_active_task_runtime -v`

Expected: PASS for the three context-key tests.

- [ ] **Step 5: Add failing tests for session pointer read/write/clear**

Append to `tests/test_active_task_runtime.py`:

```python
    def test_set_and_get_active_task_require_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {}, clear=True):
                self.assertIsNone(self.active_task.set_active_task(root, ".cowork-flow/tasks/05-28-demo"))
                self.assertEqual(None, self.active_task.get_active_task(root).task_path)

    def test_set_get_and_clear_active_task_for_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".cowork-flow").mkdir()
            task_dir = root / ".cowork-flow" / "tasks" / "05-28-demo"
            task_dir.mkdir(parents=True)

            with patch.dict(os.environ, {"COWORK_FLOW_CONTEXT_ID": "main"}, clear=True):
                active = self.active_task.set_active_task(root, ".cowork-flow/tasks/05-28-demo")
                self.assertEqual(".cowork-flow/tasks/05-28-demo", active.task_path)
                self.assertEqual(".cowork-flow/tasks/05-28-demo", self.active_task.get_active_task(root).task_path)
                self.active_task.clear_active_task(root)
                self.assertEqual(None, self.active_task.get_active_task(root).task_path)
```

- [ ] **Step 6: Run test to verify pointer tests fail**

Run: `python -m unittest tests.test_active_task_runtime -v`

Expected: FAIL because `set_active_task`, `get_active_task`, and `clear_active_task` are missing.

- [ ] **Step 7: Implement session pointer functions**

Add to both active_task files:

```python
def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_path(repo_root: Path, context_key: str) -> Path:
    return sessions_dir(repo_root) / f"{context_key}.json"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_active_task(repo_root: Path, task_path: str) -> ActiveTask | None:
    context_key = resolve_context_key()
    if not context_key:
        return None
    target = repo_root / task_path
    if not target.is_dir():
        return None
    _write_json(
        _session_path(repo_root, context_key),
        {
            "current_task": task_path.replace("\\", "/"),
            "platform": "codex" if context_key.startswith("codex_") else "manual",
            "last_seen_at": _now(),
        },
    )
    return ActiveTask(task_path.replace("\\", "/"), context_key, "session")


def get_active_task(repo_root: Path) -> ActiveTask:
    context_key = resolve_context_key()
    if not context_key:
        return ActiveTask(None, None, "missing-context")
    data = _read_json(_session_path(repo_root, context_key))
    task_path = data.get("current_task")
    if isinstance(task_path, str) and task_path.strip():
        return ActiveTask(task_path.strip(), context_key, "session")
    return ActiveTask(None, context_key, "empty-session")


def clear_active_task(repo_root: Path) -> ActiveTask:
    active = get_active_task(repo_root)
    if active.context_key:
        try:
            _session_path(repo_root, active.context_key).unlink()
        except FileNotFoundError:
            pass
    return active


def clear_task_from_sessions(repo_root: Path, task_path: str) -> int:
    cleared = 0
    root = sessions_dir(repo_root)
    if not root.is_dir():
        return 0
    normalized = task_path.replace("\\", "/")
    for path in root.glob("*.json"):
        data = _read_json(path)
        if data.get("current_task") == normalized:
            path.unlink()
            cleared += 1
    return cleared
```

- [ ] **Step 8: Run test to verify runtime passes**

Run: `python -m unittest tests.test_active_task_runtime -v`

Expected: PASS.

---

### Task 2: Replace `.current-task` in Task and Resume Scripts

**Files:**
- Modify: `.cowork-flow/scripts/task.py`
- Modify: `template/.cowork-flow/scripts/task.py`
- Modify: `.cowork-flow/scripts/common/paths.py`
- Modify: `template/.cowork-flow/scripts/common/paths.py`
- Modify: `.cowork-flow/scripts/common/git_context.py`
- Modify: `template/.cowork-flow/scripts/common/git_context.py`
- Modify: `.cowork-flow/scripts/resume.py`
- Modify: `template/.cowork-flow/scripts/resume.py`
- Test: `tests/test_flow_script_paths.py`

- [ ] **Step 1: Write failing test that `task start` requires context key**

Replace `test_cmd_start_sets_current_task_when_ready` in `tests/test_flow_script_paths.py` with:

```python
    def test_cmd_start_requires_session_context_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / ".cowork-flow" / "tasks" / "05-19-demo"
            task_dir.mkdir(parents=True)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            (task_dir / "task.json").write_text("{}", encoding="utf-8")
            (task_dir / "prd.md").write_text("# Demo\n", encoding="utf-8")
            for name in ("implement.jsonl", "check.jsonl", "debug.jsonl"):
                (task_dir / name).write_text('{"file": "AGENTS.md"}\n', encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {}, clear=True):
                    result = self.task.cmd_start(argparse.Namespace(dir=".cowork-flow/tasks/05-19-demo"))
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(1, result)
            self.assertFalse((root / ".cowork-flow" / ".current-task").exists())
```

- [ ] **Step 2: Add import needed by the test**

At top of `tests/test_flow_script_paths.py`, add:

```python
from unittest.mock import patch
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_cmd_start_requires_session_context_key -v`

Expected: FAIL because current code writes `.current-task`.

- [ ] **Step 4: Modify task start/finish to use active_task**

In both task scripts, import:

```python
from common.active_task import (
    clear_active_task,
    clear_task_from_sessions,
    get_active_task,
    set_active_task,
)
```

Remove imports of `FILE_CURRENT_TASK`, `get_current_task`, `set_current_task`, `clear_current_task`.

In `cmd_start`, replace current pointer write with:

```python
    active = set_active_task(repo_root, task_dir)
    if active is None:
        print(colored("Error: Missing session context. Set COWORK_FLOW_CONTEXT_ID or run inside Codex session.", Colors.RED))
        return 1
```

In `cmd_finish`, use:

```python
    active = get_active_task(repo_root)
    if not active.task_path:
        print(colored("No current task set for this session", Colors.YELLOW))
        return 0
    clear_active_task(repo_root)
```

In `cmd_archive`, replace current-task cleanup with:

```python
    clear_task_from_sessions(repo_root, f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}")
```

- [ ] **Step 5: Remove `.current-task` helpers from paths**

In both `paths.py`, delete:

- `FILE_CURRENT_TASK`
- `_get_current_task_file`
- `get_current_task`
- `get_current_task_abs`
- `set_current_task`
- `clear_current_task`
- `has_current_task`

Keep unrelated path helpers unchanged.

- [ ] **Step 6: Add a `task current` command**

In both task scripts, add parser:

```python
subparsers.add_parser("current", help="Show current session task")
```

Add command handler:

```python
def cmd_current(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    active = get_active_task(repo_root)
    if not active.context_key:
        print(colored("Error: Missing session context. Set COWORK_FLOW_CONTEXT_ID or run inside Codex session.", Colors.RED), file=sys.stderr)
        return 1
    if not active.task_path:
        print("Current task: (none)")
        return 0
    print(f"Current task: {active.task_path}")
    print(f"Source: {active.source}:{active.context_key}")
    return 0
```

Register `"current": cmd_current`.

- [ ] **Step 7: Run focused task tests**

Run: `python -m unittest tests.test_flow_script_paths -v`

Expected: initial failures only where tests still assert `.current-task`.

- [ ] **Step 8: Update resume/git_context to use active_task**

In both `git_context.py`, replace `get_current_task(repo_root)` with `get_active_task(repo_root).task_path`.

Update no-task notes to say:

```text
No current task for this session. Create a task or run task start with COWORK_FLOW_CONTEXT_ID.
```

- [ ] **Step 9: Update remaining tests that reference `.current-task`**

Search:

Run: `rg -n "\.current-task|get_current_task|set_current_task|clear_current_task|has_current_task" tests .cowork-flow template`

For each remaining test, either delete obsolete assertion or change it to `.runtime/sessions/<key>.json`.

- [ ] **Step 10: Run focused tests**

Run: `python -m unittest tests.test_active_task_runtime tests.test_flow_script_paths -v`

Expected: PASS.

---

### Task 3: Add Fixed Cowork Agent Definitions and Remove Agent-team Skill

**Files:**
- Create: `.codex/agents/cowork-research.toml`
- Create: `.codex/agents/cowork-implement.toml`
- Create: `.codex/agents/cowork-check.toml`
- Create: `template/.codex/agents/cowork-research.toml`
- Create: `template/.codex/agents/cowork-implement.toml`
- Create: `template/.codex/agents/cowork-check.toml`
- Delete: `.agent/skills/agent-team-execution/SKILL.md`
- Delete: `template/.agent/skills/agent-team-execution/SKILL.md`
- Test: `tests/test_cowork_agents.py`
- Modify: `tests/test_agent_team_docs.py` or delete if fully obsolete.

- [ ] **Step 1: Write failing tests for new agent definitions**

Create `tests/test_cowork_agents.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoworkAgentsTest(unittest.TestCase):
    def test_codex_agent_definitions_exist_in_root_and_template(self) -> None:
        for base in (ROOT / ".codex" / "agents", ROOT / "template" / ".codex" / "agents"):
            self.assertTrue((base / "cowork-research.toml").is_file())
            self.assertTrue((base / "cowork-implement.toml").is_file())
            self.assertTrue((base / "cowork-check.toml").is_file())

    def test_agents_require_active_task_and_disable_multi_agent(self) -> None:
        for path in (
            ROOT / ".codex" / "agents" / "cowork-implement.toml",
            ROOT / ".codex" / "agents" / "cowork-check.toml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Active task:", text)
            self.assertIn("MUST NOT spawn", text)
            self.assertIn("multi_agent = false", text)
            self.assertIn("enabled = false", text)

    def test_agent_team_execution_skill_removed(self) -> None:
        self.assertFalse((ROOT / ".agent" / "skills" / "agent-team-execution" / "SKILL.md").exists())
        self.assertFalse((ROOT / "template" / ".agent" / "skills" / "agent-team-execution" / "SKILL.md").exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cowork_agents -v`

Expected: FAIL because files still missing and old skill exists.

- [ ] **Step 3: Add `cowork-implement` agent definition**

Create root and template `cowork-implement.toml`:

```toml
name = "cowork-implement"
description = "Cowork-flow implementer that self-loads task context from Active task."
sandbox_mode = "workspace-write"

developer_instructions = """
You are the `cowork-implement` subagent.

The dispatch message MUST start with:
Active task: .cowork-flow/tasks/<task>

If the message does not contain that line, stop and ask for the active task path.

Load context before editing:
1. Read `<task>/prd.md`.
2. Read `<task>/info.md` if present.
3. Read `<task>/implement.jsonl`.
4. Read each JSONL `file` entry.

Rules:
- MUST NOT spawn, wait for, list, or close other agents.
- MUST NOT run task start, task finish, task archive, or unscoped resume.
- MUST NOT commit or push.
- Keep edits inside requested scope.
- Report changed files and exact verification commands.
"""

[features]
multi_agent = false

[features.multi_agent_v2]
enabled = false
```

- [ ] **Step 4: Add `cowork-check` and `cowork-research` definitions**

Use the same root/template mirror pattern.

`cowork-check` must include:

```text
Read `<task>/prd.md`, `<task>/check.jsonl`, and `git diff`.
Fix issues directly when in scope.
MUST NOT commit, archive, or spawn agents.
```

`cowork-research` must include:

```text
Write only under `<task>/research/`.
Do not modify code, specs, task state, or git.
Persist findings to Markdown files.
```

- [ ] **Step 5: Delete old agent-team skill files**

Delete:

```text
.agent/skills/agent-team-execution/SKILL.md
template/.agent/skills/agent-team-execution/SKILL.md
```

If directories become empty, delete the directories too.

- [ ] **Step 6: Run new agent tests**

Run: `python -m unittest tests.test_cowork_agents -v`

Expected: PASS.

---

### Task 4: Rewrite Workflow and Skills to New Mainline

**Files:**
- Modify: `.cowork-flow/workflow.md`
- Modify: `template/.cowork-flow/workflow.md`
- Modify: `.agent/skills/start/SKILL.md`
- Modify: `template/.agent/skills/start/SKILL.md`
- Modify: `.agent/skills/finish-work/SKILL.md`
- Modify: `template/.agent/skills/finish-work/SKILL.md`
- Modify: `.agent/skills/check-cross-layer/SKILL.md`
- Modify: `template/.agent/skills/check-cross-layer/SKILL.md`
- Test: `tests/test_workflow_trellis_like.py`

- [ ] **Step 1: Write failing workflow tests**

Create `tests/test_workflow_trellis_like.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTrellisLikeTest(unittest.TestCase):
    def test_workflow_uses_fixed_agent_mainline(self) -> None:
        text = (ROOT / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-research", text)
        self.assertIn("cowork-implement", text)
        self.assertIn("cowork-check", text)
        self.assertNotIn("agent-team prepare", text)
        self.assertNotIn("agent-team next", text)

    def test_start_skill_routes_to_fixed_agents(self) -> None:
        text = (ROOT / ".agent" / "skills" / "start" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Plan -> Implement -> Check -> Finish", text)
        self.assertIn("Active task:", text)
        self.assertNotIn("agent-team-execution", text)

    def test_template_workflow_matches_new_terms(self) -> None:
        text = (ROOT / "template" / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("cowork-implement", text)
        self.assertNotIn("agent-team prepare", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_workflow_trellis_like -v`

Expected: FAIL because old workflow still references agent-team.

- [ ] **Step 3: Rewrite workflow mainline**

In both workflow files, replace L1/L2 execution routing with:

```text
Default execution flow:
1. Plan: create task, write prd.md, collect research, curate implement.jsonl/check.jsonl.
2. Implement: main session dispatches cowork-implement with first line `Active task: <task-dir>`.
3. Check: main session dispatches cowork-check with first line `Active task: <task-dir>`.
4. Finish: main session verifies, updates specs if needed, commits, archives, records session.
```

Remove default recommendations to use `agent-team`.

- [ ] **Step 4: Update start skill**

In both start skills:

- Keep main-session entry gate.
- Remove `agent-team-execution`.
- Add rule:

```text
For implementation, dispatch cowork-implement unless user explicitly asks for inline work.
For verification, dispatch cowork-check unless user explicitly asks for inline review.
Every dispatch prompt must start with `Active task: <task-dir>`.
```

- [ ] **Step 5: Update finish/check skills**

Remove agent-team status/complete requirements.

Finish skill must check:

```text
- current session task exists
- cowork-check or equivalent final verification ran
- specs updated or explicitly judged unchanged
- work committed before archive/session
```

- [ ] **Step 6: Run workflow tests**

Run: `python -m unittest tests.test_workflow_trellis_like -v`

Expected: PASS.

---

### Task 5: Remove Agent-team Runtime and Obsolete Tests

**Files:**
- Delete: `.cowork-flow/scripts/agent_team.py`
- Delete: `.cowork-flow/scripts/common/agent_team.py`
- Delete: `.cowork-flow/agent-team/`
- Delete: `template/.cowork-flow/scripts/agent_team.py`
- Delete: `template/.cowork-flow/scripts/common/agent_team.py`
- Delete: `template/.cowork-flow/agent-team/`
- Modify: `.cowork-flow/scripts/run.py`
- Modify: `template/.cowork-flow/scripts/run.py`
- Delete/Replace: `tests/test_agent_team_docs.py`
- Delete/Replace: `tests/test_agent_team_plan_parser.py`
- Delete/Replace: `tests/test_agent_team_runtime.py`
- Delete/Replace: `tests/test_agent_team_state_machine.py`
- Modify/Delete: `tests/test_worker_execution_context.py`
- Modify/Delete: `tests/test_subagent_recovery.py`
- Modify: `tests/test_no_legacy_template_paths.py`

- [ ] **Step 1: Write failing test that CLI no longer exposes agent-team**

Add to `tests/test_no_legacy_template_paths.py`:

```python
def test_agent_team_runtime_removed() -> None:
    root = Path(__file__).resolve().parents[1]
    removed = [
        root / ".cowork-flow" / "scripts" / "agent_team.py",
        root / ".cowork-flow" / "scripts" / "common" / "agent_team.py",
        root / "template" / ".cowork-flow" / "scripts" / "agent_team.py",
        root / "template" / ".cowork-flow" / "scripts" / "common" / "agent_team.py",
    ]
    for path in removed:
        assert not path.exists(), str(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_no_legacy_template_paths -v`

Expected: FAIL because agent-team scripts still exist.

- [ ] **Step 3: Remove agent-team scripts/config**

Delete root and template paths listed above.

Remove `agent-team` command routing from both `run.py` files.

- [ ] **Step 4: Remove obsolete tests**

Delete tests that only verify old assignment/outbox/review-chain behavior:

```text
tests/test_agent_team_docs.py
tests/test_agent_team_plan_parser.py
tests/test_agent_team_runtime.py
tests/test_agent_team_state_machine.py
```

If any assertion still matters for new fixed agents, move it into `tests/test_cowork_agents.py` or `tests/test_workflow_trellis_like.py`.

- [ ] **Step 5: Search for stale references**

Run: `rg -n "agent-team|agent_team|worker-report|record-spawn|record-review|collect|retry" .cowork-flow template .agent tests src test`

Expected: only archived historical records under `.cowork-flow/tasks/archive` or `.cowork-flow/changes/archive` may remain. No active scripts, skills, templates, or tests should reference old runtime.

- [ ] **Step 6: Run focused removal tests**

Run: `python -m unittest tests.test_no_legacy_template_paths tests.test_cowork_agents tests.test_workflow_trellis_like -v`

Expected: PASS.

---

### Task 6: Sync Package Template and Installer Tests

**Files:**
- Modify: `src/lib/copy-template.js` if template filtering references removed paths
- Modify: `test/template-paths.test.js`
- Modify: `tests/test_flow_script_paths.py`
- Modify: `scripts/run-template-tests.js` if it enumerates removed tests
- Test: Node and Python template tests

- [ ] **Step 1: Run template path tests to find stale expectations**

Run: `npm test -- test/template-paths.test.js`

Expected: FAIL if tests still expect agent-team files or `.current-task`.

- [ ] **Step 2: Update Node template tests**

Adjust assertions to expect:

```js
assert.equal(isInternalTemplateFile('.cowork-flow\\scripts\\change.py'), false);
assert.equal(isInternalTemplateFile('.codex\\agents\\cowork-implement.toml'), false);
```

Remove assertions for deleted agent-team assets.

- [ ] **Step 3: Run Python template tests**

Run: `npm run test:template`

Expected: identify stale references.

- [ ] **Step 4: Fix stale template references**

For each failure:

- replace `.current-task` with `.runtime/sessions/<context>.json`
- replace agent-team execution text with cowork fixed-agent flow
- remove tests for deleted scripts

- [ ] **Step 5: Run focused template verification**

Run: `npm run test:template`

Expected: PASS.

---

### Task 7: Full Verification and Change Metadata

**Files:**
- Modify: `.cowork-flow/changes/05-28-clean-room-trellis-like-rewrite/change.yaml`
- Modify: `.cowork-flow/plans/2026-05-28-clean-room-trellis-like-rewrite.md`

- [ ] **Step 1: Update plan execution status**

Change `Current Execution Status` to:

```text
Implementation complete pending full verification.
```

- [ ] **Step 2: Link plan in change metadata**

Set in `change.yaml`:

```yaml
plan: .cowork-flow/plans/2026-05-28-clean-room-trellis-like-rewrite.md
```

- [ ] **Step 3: Validate change**

Run: `.\.cowork-flow\run.cmd change validate 05-28-clean-room-trellis-like-rewrite`

Expected: `05-28-clean-room-trellis-like-rewrite valid`

- [ ] **Step 4: Run full verification**

Run: `npm run test:all`

Expected: PASS.

- [ ] **Step 5: Search for forbidden stale paths**

Run: `rg -n "\.current-task|agent-team prepare|agent-team next|worker-report|record-spawn" .cowork-flow template .agent tests src test`

Expected: no active-path matches. Archived historical task/change records are acceptable only under archive directories.

- [ ] **Step 6: Commit**

Commit after user-approved implementation:

```bash
git add .cowork-flow template .agent .codex tests test src scripts package.json package-lock.json
git commit -m "feat: rewrite workflow around fixed cowork agents"
```

---

## Self-review

- Spec coverage: plan covers clean-room constraint, session active task, fixed agents, task file contract, agent-team removal, workflow/skills, tests, and full verification.
- Placeholder scan: no placeholder-marker language.
- Scope check: this is a breaking L2 rewrite; tasks are ordered so session runtime lands before workflow and deletion.
- Execution recommendation: run inline with `superpowers:executing-plans`, not subagent-driven, because this rewrite changes subagent dispatch behavior.
