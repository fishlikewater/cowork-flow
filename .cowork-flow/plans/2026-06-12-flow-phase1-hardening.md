# Flow Phase 1 Hardening Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Make Phase 1 Flow SQLite/task lifecycle implementation reliable and align `FLOW-UPGRADE-DESIGN.md` with current implementation decisions.
**Architecture:** Keep `flow.store.FlowStore` as the single SQLite access layer, with explicit transaction boundaries and read-only queries that do not acquire writer locks. Keep task artifacts on disk, but lifecycle status/query truth comes from FlowStore; filesystem movement and DB state updates must not silently diverge.
**Verification:** `python -m pytest tests/test_flow_store.py tests/test_flow_migrate.py tests/test_flow_script_paths.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q`, `npm run test:all`, `git diff --check`.

**Execution strategy:** Serial work. The fixes share `FlowStore`, task CLI, hook state injection, root/template runtime files, and shared tests; parallel writes would raise merge risk.

## Task 1: Add Regression Tests For Real Phase 1 Failures

Files:
- `tests/test_flow_store.py`
- `tests/test_flow_migrate.py`
- `tests/test_flow_script_paths.py`
- `tests/test_codex_hooks.py`
- `tests/test_claude_hooks.py`

Steps:
1. Add FlowStore tests that prove transactions rollback after `IntegrityError`, `unblock_task` rejects missing active blocks, and `board_view` remains read-only.
2. Add migration tests for child-before-parent ordering, failed migration rollback, and valid parent/children link restoration.
3. Add task CLI tests for `task create --parent` and missing-DB-row status update failures.
4. Add hook tests proving Flow-only active tasks report the SQLite status instead of `stale`.

Expected initial result: tests fail on current implementation.

## Task 2: Fix FlowStore Transaction And State Semantics

Files:
- `.cowork-flow/scripts/flow/store.py`
- `template/.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/flow/schema.sql`
- `template/.cowork-flow/scripts/flow/schema.sql`

Steps:
1. Ensure `_transaction()` rolls back on every exception, retries only lock failures, and leaves the connection usable.
2. Add a read helper or direct read path for `board_view()` so dashboard reads do not take `BEGIN IMMEDIATE`.
3. Make `block_task()` and `unblock_task()` validate task existence and current state before writing block/audit rows.
4. Keep schema FK behavior aligned with archive/query needs and document that audit/agent rows may preserve deleted-task history.

Verification:
- `python -m pytest tests/test_flow_store.py -q`

## Task 3: Fix Migration Atomicity And Relationship Import

Files:
- `.cowork-flow/scripts/flow/migrate.py`
- `template/.cowork-flow/scripts/flow/migrate.py`
- `tests/test_flow_migrate.py`

Steps:
1. Parse all `task.json` files first and build `dir_to_id`.
2. Insert tasks without parent links during pass 1.
3. Link parent/child relationships in pass 2, supporting both child `parent` and parent `children[]` without duplicate links.
4. Wrap the whole migration in one transaction; any validation or write failure rolls back all imported rows and returns/raises a clear failure.
5. Keep orphan child directory references as warnings only when the child directory truly does not exist.

Verification:
- `python -m pytest tests/test_flow_migrate.py -q`

## Task 4: Fix Task CLI And Hook Query Reliability

Files:
- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/inject_workflow_state.py`
- `template/.cowork-flow/scripts/common/inject_workflow_state.py`
- `tests/test_flow_script_paths.py`
- `tests/test_codex_hooks.py`
- `tests/test_claude_hooks.py`

Steps:
1. Remove duplicate parent linking in `cmd_create`.
2. Make `review`, `complete`, `block`, `unblock`, and archive DB updates fail loudly when FlowStore cannot update the intended row.
3. Make workflow-state injection read active task status from FlowStore by artifact directory before falling back to legacy `task.json`.
4. Keep hook environment variables aligned with FlowStore (`COWORK_TASK_ID`, `COWORK_TASK_DIR`, `COWORK_DB_PATH`) while retaining legacy hook compatibility only where explicitly documented.

Verification:
- `python -m pytest tests/test_flow_script_paths.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q`

## Task 5: Align Design Document And Template

Files:
- `FLOW-UPGRADE-DESIGN.md`
- root/template copies of touched runtime files

Steps:
1. Update path and command casing from `Flow` to `flow`.
2. Clarify transaction model, read/write lock model, migration atomicity, hook transition behavior, and DB/filesystem consistency contract.
3. Mark Phase 1 reliability gates as required before Phase 2.
4. Confirm root/template runtime files remain byte-identical where expected.

Verification:
- root/template SHA comparison for touched files
- `git diff --check`

## Final Verification

Run:

```powershell
python -m pytest tests/test_flow_store.py tests/test_flow_migrate.py tests/test_flow_script_paths.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q
npm run test:all
git diff --check
```

Expected result:
- Targeted Python tests pass.
- Full Node/template/package gate passes.
- No whitespace errors.
