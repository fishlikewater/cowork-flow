# Task 1.3: Implement task.json migration script

**Goal:** Create .cowork-flow/scripts/flow/migrate.py that reads old tasks/*/task.json files and imports into cowork-flow.db.

**Scope:**
- Create .cowork-flow/scripts/flow/migrate.py with run_migration(tasks_dir, db_path)
- Field mapping: id/name->id, title, description, status, priority, creator, assignee, completedAt, commit, parent, children
- Legacy fields (dev_type, scope, relatedFiles, notes) go to meta JSON
- Children resolved via task_child table; orphan references warn and skip
- Transaction-wrapped: validate -> commit or rollback
- On success: rename tasks/ -> tasks.backup/, add to .gitignore
- Write tests: .cowork-flow/tests/test_flow_migrate.py

**Files:**
- Create: .cowork-flow/scripts/flow/migrate.py
- Create: .cowork-flow/tests/test_flow_migrate.py

**Acceptance:**
- pytest .cowork-flow/tests/test_flow_migrate.py -v -- all tests PASS
- Migration with valid data succeeds
- Migration with orphan children warns but completes
- Empty tasks dir does not crash

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.3