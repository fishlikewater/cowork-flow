# Task 1.1: Create flow module skeleton

**Goal:** Create .cowork-flow/scripts/flow/ directory with schema.sql, add get_db_path() to paths.py, register flow command in run.py.

**Scope:**
- Create .cowork-flow/scripts/flow/__init__.py
- Create .cowork-flow/scripts/flow/schema.sql (5 tables: task, task_child, audit, block, agent_run)
- Add get_db_path() + FILE_FLOW_DB to .cowork-flow/scripts/common/paths.py
- Register "flow": "flow/store.py" in run.py COMMAND_SCRIPTS

**Files:**
- Create: .cowork-flow/scripts/flow/__init__.py
- Create: .cowork-flow/scripts/flow/schema.sql
- Modify: .cowork-flow/scripts/common/paths.py
- Modify: .cowork-flow/scripts/run.py

**Acceptance:**
- ./cowork-flow/run flow --help succeeds (no "unknown command")
- get_db_path() returns .cowork-flow/cowork-flow.db relative to repo root
- schema.sql DDL is syntactically valid SQLite

**Reference:** .cowork-flow/plans/2026-06-11-flow-pattern-engine.md Task 1.1