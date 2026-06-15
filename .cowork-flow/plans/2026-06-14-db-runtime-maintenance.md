# DB Runtime State And Maintenance Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Move runtime state into DB and add safe DB maintenance controls.
**Architecture:** Add runtime tables and FlowStore APIs, migrate runtime context/session/dashboard process reads and writes to DB, then expose stats/dry-run/cleanup/checkpoint/vacuum through Dashboard and CLI. Keep PRD/plan/change/spec/task context files on disk.
**Verification:** targeted Python tests for runtime DB lifecycle and maintenance, Dashboard tests, template tests, `git diff --check`.
**Status:** implemented and verified in the root/template runtime.

Execution strategy: serial. Runtime identity, session binding, Dashboard API, and cleanup policy share state contracts and must be integrated carefully.

## Steps

1. [done] Add schema and store APIs.
   - Files: `.cowork-flow/scripts/flow/schema.sql`, `.cowork-flow/scripts/flow/store.py`, template mirrors.
   - Add `runtime_context`, `runtime_session`, `dashboard_process`, `maintenance_event`.
   - Verify: FlowStore tests create/update/read/cleanup rows transactionally.

2. [done] Move active session and runtime context helpers to DB.
   - Files: `.cowork-flow/scripts/common/active_task.py`, `.cowork-flow/scripts/common/inject_workflow_state.py`, template mirrors.
   - Preserve function names where possible: `read_runtime_context`, `write_runtime_context`, `bind_runtime_context`, `close_runtime_context`, `set_active_task`, `get_active_task`, `clear_active_task`.
   - Verify: active-task runtime tests pass with DB-backed state.

3. [done] Move subagent lifecycle to DB source.
   - Files: `.cowork-flow/scripts/subagent.py`, template mirror.
   - `subagent init/bind/status/update/close/spawn-family/check-family` read/write DB runtime state.
   - Replace independent `agent_run` source with DB runtime source or compatibility projection updated in one transaction.
   - Verify: direct formal init, bind, close, family idempotency tests.

4. [done] Move Dashboard process state into DB.
   - Files: `.cowork-flow/scripts/dashboard/server.py`, template mirror.
   - `dashboard start/status/stop` uses `dashboard_process` instead of `.runtime/dashboard.json`.
   - Verify: CLI lifecycle test asserts DB state and project-local behavior.

5. [done] Add DB maintenance backend.
   - Files: `.cowork-flow/scripts/dashboard/server.py`, `.cowork-flow/scripts/flow/store.py`, template mirrors.
   - Add stats, dry-run cleanup, confirmed cleanup, checkpoint, vacuum.
   - Verify: cleanup never touches active/unclosed runtime rows; dry-run has no mutation; confirmed cleanup records `maintenance_event`.

6. [done] Add Dashboard maintenance UI.
   - Files: `.cowork-flow/scripts/dashboard/static/index.html`, `app.js`, `style.css`, template mirrors.
   - Add "数据库维护" view with stats, dry-run, cleanup confirmation, checkpoint/vacuum controls.
   - Verify: static contract tests and browser smoke.

7. [done] Update specs and compatibility docs.
   - Files: `.cowork-flow/spec/subagent-dispatch.md`, relevant template spec mirrors, this change docs.
   - Document DB as runtime source and file docs as review assets.
   - Verify: docs tests and grep for old full-runtime-json source claims.

8. [done] Integrated verification.
   - Commands:
     - `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_active_task_runtime tests.test_subagent_dispatch tests.test_dashboard -v`
     - `rtk npm run test:template`
     - `rtk git diff --check`
   - Expected: all pass; no `.codegraph/` or `.runtime/` staged.
