# Post-closeout Workflow Hardening Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Harden the closeout path so archive state, archived contexts, Windows npm commands, and legacy completed tasks stay intentional after final scans.

**Architecture:** Keep changes surgical. `task.py` / `change.py` remain the lifecycle write path, with root/template parity for runtime scripts. Node package command execution stays in `src/lib/package-info.js`, with tests updated around the public helper contract.

**Execution Strategy:** Serial. The first two tasks share archive lifecycle files, the npm warning task is independent but should wait until archive behavior is stable, and the completed-task audit should run last after archive mechanics are hardened.

**Verification:** Focused Python lifecycle tests, Node package/update tests, `npm run pack:check`, archived task validation checks, and `git diff --check`.

## Task 1: Linked Change Final Archive Gate

- **Task:** `.cowork-flow/tasks/07-16-archive-linked-change-final-gate`
- **Goal:** Prevent `task archive` from prematurely archiving a multi-task linked change while keeping single-task auto archive behavior.
- **Files:** `.cowork-flow/scripts/task.py`, `template/.cowork-flow/scripts/task.py`, `.cowork-flow/scripts/change.py`, `template/.cowork-flow/scripts/change.py`, `tests/test_flow_script_paths.py`, `tests/test_change_script.py`.
- **Steps:**
  1. Add a failing test for a multi-task change where archiving the first completed task must not archive the change.
  2. Implement a narrow finalization/readiness helper for linked active changes.
  3. Preserve and rerun the existing single-task auto-archive test.
- **Verification:** `..\.cowork-flowun.cmd python -m unittest tests.test_flow_script_paths tests.test_change_script -v`; `git diff --check`.

## Task 2: Archive Context Reference Rewrite

- **Task:** `.cowork-flow/tasks/07-16-archive-context-reference-rewrite`
- **Goal:** Make archived task context JSONL files validate immediately after task/change archive moves source artifacts.
- **Files:** `.cowork-flow/scripts/task.py`, `template/.cowork-flow/scripts/task.py`, `.cowork-flow/scripts/change.py`, `template/.cowork-flow/scripts/change.py`, `tests/test_flow_script_paths.py`, `tests/test_change_script.py`.
- **Steps:**
  1. Add failing tests for archived task `implement.jsonl` / `check.jsonl` / `debug.jsonl` references to moved task/change paths.
  2. Rewrite only JSONL `file` fields for artifacts moved by the current archive operation.
  3. Validate archived task contexts in tests after archive.
- **Verification:** `..\.cowork-flowun.cmd python -m unittest tests.test_flow_script_paths tests.test_change_script -v`; `git diff --check`.

## Task 3: Shellless Windows NPM Commands

- **Task:** `.cowork-flow/tasks/07-16-npm-command-shellless-windows`
- **Goal:** Remove Node `DEP0190` warning from package/update npm invocations on Windows.
- **Files:** `src/lib/package-info.js`, `test/update.test.js`, `test/package.test.js`, `scripts/pack-check.js` if needed.
- **Steps:**
  1. Update tests to expect an explicit Windows npm command strategy rather than `{ shell: true }`.
  2. Implement command/options helpers for `execFile` and `spawn`.
  3. Verify `pack:check` output no longer includes cowork-flow-caused `DEP0190` warnings.
- **Verification:** `npm test -- test/update.test.js test/package.test.js`; `npm run pack:check`; `git diff --check`.

## Task 4: Legacy Completed Task Audit

- **Task:** `.cowork-flow/tasks/07-16-completed-task-audit`
- **Goal:** Make the remaining 06-25 completed task state intentional.
- **Files:** `.cowork-flow/tasks/06-25-*`, `.cowork-flow/tasks/archive/`, `.cowork-flow/workspace/codex/`.
- **Steps:**
  1. List all completed 06-25 tasks and validate each candidate.
  2. Archive tasks that are safe and have no active change dependency.
  3. Record a written reason for any task intentionally left completed.
- **Verification:** `..\.cowork-flowun.cmd task list`; `..\.cowork-flowun.cmd task current`; `git diff --check`.

## Final Check

- Validate all new archived tasks if executed.
- Run focused tests from changed subsystems.
- Run `npm run pack:check` and `git diff --check`.
- Archive this change after all tasks complete and record the session.
