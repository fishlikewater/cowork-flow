# Task 1.6: Clean up task_utils.py legacy code

**Goal:** Remove FILE_TASK_JSON constant, delete legacy archive functions from task_utils.py, confirm no dead code references.

**Scope:**
- Remove FILE_TASK_JSON = "task.json" from .cowork-flow/scripts/common/paths.py
- Remove archive_task_dir() and archive_task_complete() from .cowork-flow/scripts/common/task_utils.py
- Verify no remaining references to FILE_TASK_JSON or task.json outside migrate.py/comments

**Files:**
- Modify: .cowork-flow/scripts/common/paths.py
- Modify: .cowork-flow/scripts/common/task_utils.py

**Acceptance:**
- grep FILE_TASK_JSON returns no results in scripts/
- No dead imports in any Python file
- All existing tests still pass after removal

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.6