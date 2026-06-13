# Dashboard Runtime Control Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Make Dashboard runtime state and archived browsing reliable, then add current-project Dashboard CLI lifecycle commands.
**Architecture:** Persist formal direct subagent runs in the existing `agent_run` table. Keep Dashboard read-only, but improve static filtering/layout. Add stdlib-only process control under `.cowork-flow/.runtime/dashboard.json`.
**Verification:** `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_subagent_dispatch.SubagentDispatchTest tests.test_dashboard.DashboardTest -v`; `rtk npm run test:template`; `rtk git diff --check`; Browser smoke at `http://127.0.0.1:8080/`.

Execution strategy: serial. The subagent runtime, dashboard CLI, static UI, and tests share root/template files and should be integrated in one line of work.

## Steps

1. Add failing coverage for direct formal subagent runtime recording.
   - Files: `tests/test_subagent_dispatch.py`.
   - Verify: direct `subagent init --execution-task-dir` creates `agent_run`, then bind/close update statuses.

2. Add failing coverage for Dashboard CLI and UI state contracts.
   - Files: `tests/test_dashboard.py`.
   - Verify: CLI start/status/stop uses a repo-local runtime file; static UI does not mutate `showArchived` from status tabs; archived layout helpers/classes exist in root and template.

3. Implement runtime recording.
   - Files: `.cowork-flow/scripts/subagent.py`, `template/.cowork-flow/scripts/subagent.py`, `.cowork-flow/spec/subagent-dispatch.md`.
   - Verify: focused subagent dispatch unittest passes.

4. Implement Dashboard CLI lifecycle.
   - Files: `.cowork-flow/scripts/dashboard/server.py`, `template/.cowork-flow/scripts/dashboard/server.py`.
   - Verify: Dashboard CLI lifecycle unittest passes.

5. Redesign archived Dashboard layout and filter behavior.
   - Files: `.cowork-flow/scripts/dashboard/static/app.js`, `.cowork-flow/scripts/dashboard/static/style.css`, template static mirrors.
   - Verify: static contract tests and template parity pass.

6. Final integrated check.
   - Commands:
     - `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_subagent_dispatch.SubagentDispatchTest tests.test_dashboard.DashboardTest -v`
     - `rtk npm run test:template`
     - `rtk git diff --check`
   - Expected: all pass; diff contains only task/change/plan/spec/runtime/dashboard/test updates and excludes `.codegraph/`.
