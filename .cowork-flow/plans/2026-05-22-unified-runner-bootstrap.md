# Unified Runner Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move cowork-flow command dispatch into one Python runner while keeping small platform launchers for Python selection.

**Architecture:** Add `template/.cowork-flow/scripts/run.py` as the single command dispatcher, copy it into `.cowork-flow/scripts/run.py`, and shrink `run`/`run.cmd` to Python selection plus forwarding. Update tests to assert dispatch lives in Python instead of batch/sh.

**Tech Stack:** Python standard library, POSIX sh, Windows batch, unittest, Node test runner.

---

### Task 1: Shared Runner Dispatch

**Files:**
- Create: `template/.cowork-flow/scripts/run.py`
- Create: `.cowork-flow/scripts/run.py`
- Modify: `template/.cowork-flow/run`
- Modify: `.cowork-flow/run`
- Modify: `template/.cowork-flow/run.cmd`
- Modify: `.cowork-flow/run.cmd`
- Modify: `tests/test_python_runner.py`
- Modify: `test/package.test.js`
- Modify: `test/init.test.js`

- [x] Step 1: Write failing tests for shared Python dispatch and thin Windows launcher.
- [x] Step 2: Run targeted tests and confirm failure.
- [x] Step 3: Add shared Python runner and thin bootstrap launchers.
- [x] Step 4: Run targeted tests and confirm pass.
- [x] Step 5: Run template/package verification tests.
