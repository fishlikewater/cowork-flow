# Agent Team Subagent Recursion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Codex agent-team workers from mistaking themselves for the coordinator and recursively spawning more workers.

**Architecture:** Keep `agent-team` coordinator-dispatched, but separate coordinator dispatch metadata from worker assignment content. `prepare` will emit structured Codex spawn defaults plus assignment `.context.json` worker scope files, while assignment Markdown becomes a pure worker brief with explicit anti-recursion guidance and a scoped recovery path.

**Tech Stack:** Python standard library, unittest, Markdown skill documentation.

---

## Current Execution Status

- `2026-05-26`: User supplied a real failing dispatch prompt showing coordinator text and worker brief were mixed in one natural-language message.
- `2026-05-26`: Root cause confirmed: child threads can inherit or receive the outer `Spawn one worker agent ...` text and recurse.
- `2026-05-26`: Wrote failing tests for Codex adapter payload, assignment brief wording, and skill guidance before changing runtime files.
- `2026-05-26`: Updated root and template runtimes to emit structured Codex spawn metadata and hardened assignment prompts against leaked coordinator transport text.
- `2026-05-26`: Added a formal worker context protocol: `prepare` now writes assignment `.context.json` files, `run.py` accepts `--context-file`, `resume` has a worker-local output path, and worker mode blocks coordinator commands in `task` and `agent-team`.
- `2026-05-26`: Updated root and template `agent-team-execution` skill guidance to require `spawn_agent` / `wait_agent` / `close_agent` with `fork_turns: none` and assignment-body-only worker messages.
- `2026-05-26`: Added explicit `spawnResult` metadata for Codex adapter payloads so coordinators capture `nickname` / `task_name` immediately and prefer host `nickname` for display.
- `2026-05-26`: Verified with `python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_docs tests.test_agent_team_runtime tests.test_agent_team_state_machine tests.test_worker_execution_context tests.test_flow_script_paths tests.test_python_runner -v` (`61 tests`, `OK`), plus real `spawn_agent` probes confirming immediate `nickname` returns for both `worker` and `default`, and assignment-shaped worker prompts staying in worker mode.
- `2026-05-26`: Added readable Codex `suggestedTaskName` metadata plus natural-language assignment headings so hosts that surface raw child `task_name` / prompt-derived names start from a human-readable label instead of `T00x-role`.

### Task 1: Lock The Regression In Tests

**Files:**
- Modify: `tests/test_agent_team_plan_parser.py`
- Modify: `tests/test_agent_team_docs.py`
- Modify: `tests/test_agent_team_runtime.py`
- Modify: `tests/test_worker_execution_context.py`

- [x] **Step 1: Write failing tests for structured Codex spawn metadata**
- [x] **Step 2: Write failing tests for assignment anti-recursion wording**
- [x] **Step 3: Write failing tests for skill guidance to use `spawn_agent` / `wait_agent` / `close_agent` with `fork_turns: none`**
- [x] **Step 4: Run the focused unittest commands and confirm they fail for the expected reason**

### Task 2: Implement Runtime And Skill Fixes

**Files:**
- Modify: `.cowork-flow/scripts/common/agent_team.py`
- Modify: `.cowork-flow/scripts/agent_team.py`
- Modify: `.cowork-flow/scripts/common/execution_context.py`
- Modify: `.cowork-flow/scripts/run.py`
- Modify: `.cowork-flow/scripts/resume.py`
- Modify: `.cowork-flow/scripts/task.py`
- Modify: `.agent/skills/agent-team-execution/SKILL.md`
- Modify: `template/.cowork-flow/scripts/common/agent_team.py`
- Modify: `template/.cowork-flow/scripts/common/execution_context.py`
- Modify: `template/.cowork-flow/scripts/run.py`
- Modify: `template/.cowork-flow/scripts/resume.py`
- Modify: `template/.cowork-flow/scripts/task.py`
- Modify: `template/.cowork-flow/scripts/agent_team.py`
- Modify: `template/.agent/skills/agent-team-execution/SKILL.md`

- [x] **Step 1: Emit structured Codex adapter metadata from `prepare`**
- [x] **Step 2: Harden assignment prompts against leaked coordinator transport text**
- [x] **Step 3: Update skill docs to require structured spawn usage and forbid mixed dispatch prompts**
- [x] **Step 4: Re-run focused tests until green**

### Task 3: Verify And Sync Workflow State

**Files:**
- Modify: `.cowork-flow/changes/05-26-agent-team-subagent-recursion/change.yaml`

- [x] **Step 1: Run the full relevant unittest set**
- [x] **Step 2: Update plan status and bind plan/task into `change.yaml`**
- [x] **Step 3: Confirm task context and verification evidence are consistent before closeout**
