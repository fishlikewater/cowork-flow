# Fix Change Archive After Task Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `change archive` work after the linked task has already been archived.

**Architecture:** Keep validation strict, but normalize task metadata before archive validation when the active task path can be resolved to an existing archived task. Also make repo-relative workflow links resolve to their direct path even when missing so diagnostics do not double-prefix paths.

**Tech Stack:** Python standard library, unittest.

---

## Current Status

- Change/spec/task context created.
- Implementation and verification complete.

### Task 1: Reproduce the Bug

**Files:**
- Modify: `tests/test_change_script.py`

- [x] Step 1: Add a failing test where a change points to `.cowork-flow/tasks/05-18-active`, that active path is absent, an archived task exists under `.cowork-flow/tasks/archive/2026-05/05-18-active`, and `change archive` succeeds while normalizing metadata to `archive/2026-05/05-18-active`.
  Verification: `python3 -m unittest tests.test_change_script.ChangeScriptTest.test_archive_accepts_task_already_moved_to_archive` fails before implementation.

- [x] Step 2: Add a failing test proving missing repo-relative task errors do not double-prefix `.cowork-flow/tasks/`.
  Verification: `python3 -m unittest tests.test_change_script.ChangeScriptTest.test_validate_reports_missing_repo_relative_task_without_double_prefix` fails before implementation.

### Task 2: Implement the Fix

**Files:**
- Modify: `template/.cowork-flow/scripts/change.py`
- Modify: `.cowork-flow/scripts/change.py`

- [x] Step 3: Update link resolution so repo-relative `.cowork-flow/<base>/...` paths return the direct path even when missing.
  Verification: missing-link diagnostic test passes.

- [x] Step 4: Before archive validation, normalize active task links to an archived task when exactly one archived task with the same directory name exists.
  Verification: task-already-archived archive test passes.

### Task 3: Verify and Sync

**Files:**
- Check: `tests/test_change_script.py`
- Check: `.cowork-flow/changes/05-22-fix-change-archive-after-task-archive/spec.md`

- [x] Step 5: Run `python3 -m unittest tests.test_change_script`.
- [x] Step 6: Run `python3 -m unittest tests.test_template_convergence tests.test_flow_script_paths`.
- [x] Step 7: Sync task/change/plan/session status before handoff.
