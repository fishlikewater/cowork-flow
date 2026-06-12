# Task 1.5: Refactor git_context and active_task to FlowStore

**Goal:** Replace file-system task.json reading in git_context.py and active_task.py with FlowStore queries.

**Scope:**
- git_context.py: replace _load_task_json_by_dir() -> FlowStore.list_tasks()
- git_context.py: replace _active_task_json() -> FlowStore.get_task()
- active_task.py: replace task.json reads -> FlowStore.get_task()
- Verify resume and get-context output unchanged

**Files:**
- Modify: .cowork-flow/scripts/common/git_context.py
- Modify: .cowork-flow/scripts/common/active_task.py

**Acceptance:**
- ./cowork-flow/run resume output matches pre-refactor output
- ./cowork-flow/run get-context output matches
- No task.json file reads in git_context or active_task code paths

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.5