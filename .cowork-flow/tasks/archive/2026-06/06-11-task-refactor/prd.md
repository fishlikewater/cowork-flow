# Task 1.4: Refactor task.py to use FlowStore

**Goal:** Replace all task.json file reads/writes in task.py with FlowStore SQLite operations.

**Scope:**
- cmd_create: write to FlowStore, create artifact dir, support --pattern and --meta
- cmd_start, cmd_review, cmd_complete, cmd_archive: call FlowStore.update_status()
- cmd_current, cmd_finish, cmd_list: read from FlowStore
- list-context, add-context, validate: resolve artifact_dir from FlowStore
- cmd_archive: move artifact dir to tasks/archive/<dir>/, set commit_sha
- Hook env vars: pass COWORK_TASK_ID, COWORK_TASK_DIR, COWORK_DB_PATH
- Write tests: .cowork-flow/tests/test_task_flow.py

**Files:**
- Modify: .cowork-flow/scripts/task.py
- Create: .cowork-flow/tests/test_task_flow.py

**Acceptance:**
- pytest .cowork-flow/tests/test_task_flow.py -v -- PASS
- task create "test" --pattern generic creates task in SQLite
- task list shows SQLite-stored tasks
- task archive <id> moves artifact dir and updates status
- task.json files no longer created by any task command

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.4