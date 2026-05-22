# Resumable Archive Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make task/change archive commands resumable after partial copy/move failures.

**Architecture:** Add one small shared directory archive helper in `.cowork-flow/scripts/common/archive_utils.py`, then replace direct `shutil.move` archive operations in task and change scripts. Keep command interfaces unchanged and make retry behavior automatic.

**Tech Stack:** Python standard library, `unittest`, existing cowork-flow scripts.

---

## Current Execution Status
Implemented and verified. RED failures were observed for resumable archive and archived task-link normalization; prefixed task-link validation already passed with existing `_resolve_link()` behavior, so no production change was needed there. `npm run test:template` passed with 72 tests and 7 skipped. `git diff --check` passed. Local cleanup of `.tmp-tests/` is blocked by Windows permission errors and remains outside tracked files.

## Task 1: Add Failing Regression Tests

**Files:**
- Modify: `tests/test_change_script.py`
- Modify: `tests/test_flow_script_paths.py`

- [x] Step 1: Add change archive tests for `.cowork-flow/tasks/<task>` link validation, matching source/destination resume, and archived task normalization.
  Verification: `python -m unittest tests.test_change_script.ChangeScriptTest.test_validate_accepts_prefixed_task_link tests.test_change_script.ChangeScriptTest.test_archive_resumes_when_source_and_destination_match tests.test_change_script.ChangeScriptTest.test_archive_normalizes_archived_task_link`
  Expected before implementation: at least one failure mentioning duplicate/missing path or destination already exists.

- [x] Step 2: Add task archive test for matching source/destination resume.
  Verification: `python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_task_archive_resumes_when_source_and_destination_match`
  Expected before implementation: failure because archive target already exists.

## Task 2: Implement Shared Archive Helper

**Files:**
- Create: `.cowork-flow/scripts/common/archive_utils.py`

- [x] Step 1: Implement directory comparison by relative file paths and file bytes.
  Verification: targeted tests from Task 1 still fail only because callers do not use the helper.

- [x] Step 2: Implement `archive_directory_resumable(source, destination)` returning a small result object with `status`, `destination`, and optional `message`.
  Verification: helper handles destination missing, matching duplicate, differing duplicate, and delete failure paths.

## Task 3: Wire Task Archive

**Files:**
- Modify: `.cowork-flow/scripts/common/task_utils.py`
- Modify: `.cowork-flow/scripts/task.py` only if needed for partial status messaging.

- [x] Step 1: Replace `shutil.move` in `archive_task_dir()` with the shared helper.
  Verification: task archive resume test passes.

- [x] Step 2: Preserve existing return shape for successful archive and report partial/conflict failures to stderr.
  Verification: existing task tests continue to pass.

## Task 4: Wire Change Archive and Link Normalization

**Files:**
- Modify: `.cowork-flow/scripts/change.py`

- [x] Step 1: Confirm `_resolve_link()` so repo-relative paths such as `.cowork-flow/tasks/<task>` are accepted without double-prefixing.
  Verification: prefixed task link validation test passes.

- [x] Step 2: Replace `shutil.move` in `archive_change()` with the shared helper and finalize metadata after verified archive.
  Verification: change archive resume test passes.

- [x] Step 3: Normalize archived task links to `archive/YYYY-MM/<task>` when metadata points at `.cowork-flow/tasks/archive/YYYY-MM/<task>`.
  Verification: archived task normalization test passes.

## Task 5: Verify and Sync State

**Files:**
- Modify: `.cowork-flow/changes/resumable-archive-operations/change.yaml`
- Modify: `.cowork-flow/tasks/05-22-resumable-archive-operations/task.json`
- Modify: `.cowork-flow/plans/2026-05-22-resumable-archive-operations.md`

- [x] Step 1: Run targeted tests.
  Command: `python -m unittest tests.test_change_script tests.test_flow_script_paths`
  Expected: pass.

- [x] Step 2: Run template suite.
  Command: `npm run test:template`
  Expected: pass.

- [x] Step 3: Update plan checkboxes and change/task metadata to match actual completion state.
  Verification: `git status --short` shows only relevant files.
