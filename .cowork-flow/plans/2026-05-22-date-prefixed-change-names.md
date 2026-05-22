# Date Prefixed Change Names Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make newly created `.cowork-flow/changes/` directories use the same `MM-DD-<slug>` naming style as tasks.

**Architecture:** Reuse the existing date-prefix helper used by task creation. Keep the public input as a bare slug, but create and report the actual date-prefixed directory name. Existing directories remain addressable by their current names.

**Tech Stack:** Python standard library, unittest regression tests.

---

## Current Status

- Change/spec/task context created.
- Implementation complete; final verification in progress.

### Task 1: Add Regression Coverage

**Files:**
- Modify: `tests/test_change_script.py`

- [x] Step 1: Update `test_create_generates_change_scaffold` to expect `MM-DD-replace-auth`.
  Verification: `python -m unittest tests.test_change_script.ChangeScriptTest.test_create_generates_change_scaffold` fails before implementation because the script still creates `replace-auth`.

### Task 2: Implement Date-Prefixed Change Creation

**Files:**
- Modify: `template/.cowork-flow/scripts/change.py`
- Modify: `.cowork-flow/scripts/change.py`

- [x] Step 2: Import and use `generate_task_date_prefix()` in `create_change`.
  Verification: targeted unittest passes.

- [x] Step 3: Keep validation/list/archive behavior unchanged for existing directory names.
  Verification: full `tests.test_change_script` passes.

### Task 3: Final Verification

**Files:**
- Check: `tests/test_change_script.py`
- Check: `template/.cowork-flow/scripts/change.py`
- Check: `.cowork-flow/scripts/change.py`

- [x] Step 4: Run `python -m unittest tests.test_change_script`.
- [x] Step 5: Run broader relevant tests if needed.
- [x] Step 6: Update plan/checklist and change/task metadata before handoff.
