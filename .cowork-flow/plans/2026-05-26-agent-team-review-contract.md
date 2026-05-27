# Agent-team Review Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agent-team reviewer subagents produce role-specific review outputs and prevent empty or invalid review completion from advancing the state machine.

**Architecture:** Keep the existing Python runtime and JSON status files. Add role-specific prompt rendering helpers, command-specific status validation, approved review payload validation, an `in_progress` state on spawn, worker host identity for built-in assignments, and a worker outbox / coordinator collect boundary.

**Tech Stack:** Python standard library, unittest, Node package test wrapper.

---

## Current Execution Status

- Baseline: `npm run test:all` passed before implementation on 2026-05-26.
- Status: complete on 2026-05-27. Added assignment-scoped `allowedContext`, worker resume context display, pending-assignment `worker-report` rejection, Windows-safe workflow/release tests, and repo-relative missing-link validation. Completed five review/refactor iterations and full verification.
- Parallelism: not using agent-team for this change because parser/runtime/prompt/tests are tightly coupled and require a short TDD loop in the same files.

---

### Task 1: Lock prompt and state-machine regressions

**Files:**
- Modify: `tests/test_agent_team_plan_parser.py`
- Modify: `tests/test_agent_team_state_machine.py`
- Modify: `tests/test_agent_team_docs.py`

- [x] **Step 1: Add failing prompt assertions**

Add assertions that spec-reviewer and quality-reviewer assignment prompts are review-only, use role-specific status labels, and do not contain implementer-only report fields.

- [x] **Step 2: Add failing state-machine assertions**

Add tests for `record-spawn` changing ready to `in_progress`, `next` hiding in-progress assignments, `record-review --status approved` requiring an approved JSON payload, and invalid result/review statuses being rejected.

- [x] **Step 3: Run tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_state_machine tests.test_agent_team_docs -v
```

Expected: fails on the new prompt and state-machine expectations.

---

### Task 2: Implement role-specific prompt rendering

**Files:**
- Modify: `.cowork-flow/scripts/common/agent_team.py`
- Modify: `template/.cowork-flow/scripts/common/agent_team.py`

- [x] **Step 1: Split role-specific prompt sections**

Added the explicit `.agent/skills/start` / `<SUBAGENT-STOP>` skip line after an ad hoc review subagent entered start-session recovery instead of returning a review.

After user review, strengthened this from a plain-language hint into a top-of-message `<COWORK-FLOW-WORKER>` marker plus start-skill recognition.

Add helpers that render `## Your job` and `## Report format` differently for implementer, spec-reviewer, and quality-reviewer. Keep existing common worker guardrails unchanged.

- [x] **Step 2: Verify prompt tests GREEN**

Run:

```bash
python3 -m unittest tests.test_agent_team_plan_parser -v
```

Expected: prompt assertions pass.

---

### Task 3: Implement record-spawn and record-result/review gates

**Files:**
- Modify: `.cowork-flow/scripts/agent_team.py`
- Modify: `template/.cowork-flow/scripts/agent_team.py`

- [x] **Step 1: Add status allowlists**

`record-result` accepts `done`, `done_with_concerns`, `blocked`, `needs_context`. `record-review` accepts `approved`, `changes_requested`, `blocked`, `needs_context`.

- [x] **Step 2: Validate approved review payloads**

Before mutating status, require `--file` for `record-review --status approved`, parse it as JSON, and require `decision` or `status` to equal `approved`.

- [x] **Step 3: Mark spawned assignments in progress**

When `record-spawn` succeeds for a ready assignment, set `status` to `in_progress` while preserving existing spawn label fields.

- [x] **Step 4: Verify state-machine tests GREEN**

Run:

```bash
python3 -m unittest tests.test_agent_team_state_machine -v
```

Expected: state-machine assertions pass.

---

### Task 4: Update execution skill docs

**Files:**
- Modify: `.agent/skills/agent-team-execution/SKILL.md`
- Modify: `template/.agent/skills/agent-team-execution/SKILL.md`
- Modify: `tests/test_agent_team_docs.py`

- [x] **Step 1: Document invalid worker reports**

Also documented that the coordinator must not wait indefinitely; if a child starts the project start/resume flow or remains stalled, close the child thread and retry with `--reason adapter_failed`.

State that wait completion without a role-specific valid report must be treated as `adapter_failed` retry, not success or indefinite waiting.

- [x] **Step 2: Verify docs tests GREEN**

Run:

```bash
python3 -m unittest tests.test_agent_team_docs -v
```

Expected: docs assertions pass.

---

### Task 5: Full verification and state sync

**Files:**
- Modify: `.cowork-flow/changes/05-26-agent-team-review-contract/change.yaml`
- Modify: `.cowork-flow/tasks/05-26-agent-team-review-contract/task.json`
- Modify: `.cowork-flow/workspace/codex/journal-1.md`

- [x] **Step 1: Run focused agent-team tests**

Run:

```bash
python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_state_machine tests.test_agent_team_docs tests.test_agent_team_runtime tests.test_worker_execution_context -v
```

Expected: all tests pass.

- [x] **Step 2: Run full test suite**

Run:

```bash
npm run test:all
```

Expected: all tests pass.

- [x] **Step 3: Validate change**

Run:

```bash
./.cowork-flow/run change validate 05-26-agent-team-review-contract
```

Expected: valid.

- [x] **Step 4: Record session**

Run:

```bash
./.cowork-flow/run add-session --title "Harden agent-team review contract" --commit "uncommitted" --summary "Added role-specific reviewer prompts and stricter agent-team result/review state gates."
```

Expected: session entry is recorded.

---

### Task 6: Add worker outbox and collect protocol

**Files:**
- Modify: `tests/test_agent_team_plan_parser.py`
- Modify: `tests/test_agent_team_state_machine.py`
- Modify: `tests/test_worker_execution_context.py`
- Modify: `tests/test_agent_team_docs.py`
- Modify: `.cowork-flow/scripts/common/agent_team.py`
- Modify: `template/.cowork-flow/scripts/common/agent_team.py`
- Modify: `.cowork-flow/scripts/agent_team.py`
- Modify: `template/.cowork-flow/scripts/agent_team.py`
- Modify: `.agent/skills/agent-team-execution/SKILL.md`
- Modify: `template/.agent/skills/agent-team-execution/SKILL.md`

- [x] **Step 1: Add failing host type and outbox tests**

Added RED assertions that built-in implementer/spec-reviewer/quality-reviewer assignments use `agent_type: worker`, registry `agent_type` cannot override them, `worker-report` writes only outbox, worker context cannot mutate coordinator state directly, and `collect` requires persisted outbox.

Run:

```bash
python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_state_machine tests.test_worker_execution_context tests.test_agent_team_docs -v
```

Observed before implementation: failed on reviewer host types and missing `worker-report` / `collect`.

- [x] **Step 2: Implement worker host identity and persisted outbox**

Implemented worker host identity for built-in assignment roles, added `agent-team worker-report` for worker-scoped outbox writes, added `agent-team collect` for coordinator validation and state advancement, and updated assignment completion protocol text.

- [x] **Step 3: Verify focused tests GREEN**

Run:

```bash
python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_state_machine tests.test_worker_execution_context tests.test_agent_team_docs -v
```

Observed after implementation: 41 tests passed.

- [x] **Step 4: Run full verification and record session**

Ran focused full agent-team suite, `npm run test:all`, and `change validate 05-26-agent-team-review-contract` on 2026-05-27. Observed: focused tests passed, `npm run test:all` passed with Windows shell-only release tests skipped, and change validation passed.
