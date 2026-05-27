# Subagent Safe Recovery Implementation Plan

> **For agentic workers:** This plan must be executed inline in the current session. Do not dispatch subagents for this task because the task fixes subagent dispatch/recovery behavior. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conservative subagent-safe start behavior, explicit runtime authority gates, and scoped subagent recovery.

**Architecture:** Keep cowork-flow as Python scripts plus Markdown skills. Add explicit execution modes in `common/execution_context.py`, gate agent-team mutations in `agent_team.py`, add a small `subagent.py` runtime for generic subagent ledgers, extend `resume.py`, and verify with focused unittest coverage.

**Tech Stack:** Python standard library, unittest, Markdown skill docs, existing Node release test wrapper.

---

## Current Execution Status

- Status: complete on 2026-05-27. Implemented explicit authority modes, agent-team coordinator context gates, generic subagent scoped recovery, start preflight guidance, and doctor checks.
- Constraint: do not use subagents for this task.
- Existing worktree already contains related uncommitted agent-team review-contract changes; preserve them and build on top.

### Task 1: Runtime authority tests

**Files:**
- Modify: `tests/test_worker_execution_context.py`
- Modify: `tests/test_agent_team_state_machine.py`

- [x] Add tests that no-context agent-team coordinator mutations fail.
- [x] Add tests that worker context cannot run coordinator mutations.
- [x] Add tests that coordinator context cannot run worker-report.
- [x] Run focused tests and confirm RED.

### Task 2: Execution context and agent-team gate

**Files:**
- Modify: `.cowork-flow/scripts/common/execution_context.py`
- Modify: `.cowork-flow/scripts/agent_team.py`
- Modify: `.cowork-flow/scripts/common/agent_team.py`
- Mirror: `template/.cowork-flow/scripts/...`

- [x] Add `none`, `coordinator`, `worker`, and `subagent` modes.
- [x] Make default context `none`.
- [x] Emit `agent-team/coordinator.context.json` from prepare.
- [x] Require coordinator context for coordinator-only commands.
- [x] Run focused tests and confirm GREEN.

### Task 3: Generic subagent recovery

**Files:**
- Create: `.cowork-flow/scripts/subagent.py`
- Modify: `.cowork-flow/scripts/run.py`
- Modify: `.cowork-flow/scripts/resume.py`
- Add tests in `tests/test_subagent_recovery.py`
- Mirror: `template/.cowork-flow/scripts/...`

- [x] Add RED tests for subagent init/status/update/resume.
- [x] Implement generic subagent ledger files.
- [x] Extend resume for `mode=subagent`.
- [x] Run focused tests and confirm GREEN.

### Task 4: Start guidance and doctor

**Files:**
- Modify: `.agent/skills/start/SKILL.md`
- Modify: `template/.agent/skills/start/SKILL.md`
- Create or modify: `.cowork-flow/scripts/doctor.py`
- Modify: `.cowork-flow/scripts/run.py`
- Add tests for docs/doctor.

- [x] Add start preflight and subagent-safe recovery guidance.
- [x] Add `doctor --subagent-safety` checks.
- [x] Run docs/doctor tests.

### Task 5: Full verification and state sync

- [x] Run focused Python unittest suite.
- [x] Run `npm run test:all` if feasible.
- [x] Run `change validate 05-27-subagent-safe-recovery`.
- [x] Update plan status and session journal.
