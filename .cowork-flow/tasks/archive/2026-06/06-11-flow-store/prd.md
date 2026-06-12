# Task 1.2: Implement FlowStore CRUD with SQLite

**Goal:** Implement FlowStore class with full CRUD for tasks, children, blocks, agent_runs, and audit.

**Scope:**
- Create .cowork-flow/scripts/flow/store.py with FlowStore class
- Implement: create_task, get_task, update_status, update_meta, list_tasks, list_children
- Implement: link_child, unlink_child, all_children_done
- Implement: block_task, unblock_task, get_active_block
- Implement: create_agent_run, update_agent_run_status, get_active_agent_run, list_agent_runs_for_parent
- Implement: get_audit_trail, board_view
- update_meta uses BEGIN IMMEDIATE with 3 retries for concurrency safety
- Write tests: .cowork-flow/tests/test_flow_store.py

**Files:**
- Create: .cowork-flow/scripts/flow/store.py
- Create: .cowork-flow/tests/test_flow_store.py

**Acceptance:**
- pytest .cowork-flow/tests/test_flow_store.py -v -- all tests PASS
- CRUD operations work on :memory: database
- Foreign key constraints enforced
- Audit trail records every status change

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.2