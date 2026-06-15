# Unify Runtime State In DB And Add Maintenance Controls

## Goal

Make SQLite the single source of truth for runtime state and provide safe Dashboard/CLI database maintenance controls.

## Scope

- Add DB tables for runtime contexts, runtime sessions, Dashboard process state, and maintenance events.
- Move active task/session and subagent runtime lifecycle reads/writes to DB.
- Keep PRD, plan, change, spec, and task context files as Git-reviewable files.
- Add compatibility import for existing runtime JSON state.
- Add Dashboard maintenance UI and API with stats, dry-run cleanup, confirmed cleanup, checkpoint, and vacuum.
- Add CLI equivalents for maintenance commands.
- Keep root/template files synchronized.

## Non-Goals

- No full DB migration for PRD/plan/change/spec documents.
- No destructive one-click cleanup.
- No global daemon or cross-project process registry.
- No cleanup of active runtime contexts or active task data.

## Acceptance Criteria

1. DB stores runtime context/session/dashboard process facts.
2. `subagent init/bind/status/update/close` work against DB-backed runtime state.
3. `task start/current/finish` session state works against DB-backed session state.
4. Dashboard details show subagent runtime data from DB runtime source.
5. Existing runtime JSON can be imported without duplicate runtime records.
6. Dashboard has a "数据库维护" entry with stats and dry-run-first cleanup.
7. Cleanup requires confirmation and records a maintenance event.
8. CLI exposes `dashboard db stats/cleanup/checkpoint/vacuum`.
9. Tests cover runtime lifecycle, cleanup safety, and root/template parity.

## Relevant Files

- `.cowork-flow/scripts/flow/schema.sql`
- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/common/active_task.py`
- `.cowork-flow/scripts/common/inject_workflow_state.py`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/dashboard/server.py`
- `.cowork-flow/scripts/dashboard/static/index.html`
- `.cowork-flow/scripts/dashboard/static/app.js`
- `.cowork-flow/scripts/dashboard/static/style.css`
- `template/.cowork-flow/scripts/flow/schema.sql`
- `template/.cowork-flow/scripts/flow/store.py`
- `template/.cowork-flow/scripts/common/active_task.py`
- `template/.cowork-flow/scripts/common/inject_workflow_state.py`
- `template/.cowork-flow/scripts/subagent.py`
- `template/.cowork-flow/scripts/dashboard/server.py`
- `template/.cowork-flow/scripts/dashboard/static/index.html`
- `template/.cowork-flow/scripts/dashboard/static/app.js`
- `template/.cowork-flow/scripts/dashboard/static/style.css`
- `.cowork-flow/spec/subagent-dispatch.md`
- `template/.cowork-flow/spec/subagent-dispatch.md`
- `tests/test_active_task_runtime.py`
- `tests/test_subagent_dispatch.py`
- `tests/test_dashboard.py`

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_active_task_runtime tests.test_subagent_dispatch tests.test_dashboard -v`
- `rtk npm run test:template`
- `rtk git diff --check`
