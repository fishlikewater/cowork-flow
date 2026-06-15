# DB Runtime State And Maintenance Design

## Brainstorming Summary

Goal: move runtime state into DB while keeping Git-reviewable documents as files.

Non-goals:

- Do not store PRD/plan/change/spec documents in DB.
- Do not make Dashboard a general mutation console.
- Do not delete historical task/audit data by default.

Recommended direction: DB is runtime state source; files remain document source. Dashboard adds a dedicated maintenance area with dry-run-first destructive actions.

Rejected alternatives:

- Full DB-only for everything: rejected because docs become harder to diff, merge, review, and archive.
- Keep runtime json as source and reconcile DB: rejected because it preserves the current split-brain risk.
- One-click cleanup: rejected because it can destroy useful history without preview.

## Architecture

```text
Host prompt/env
  -> runtime id/context key
  -> active_task.py
  -> FlowStore runtime tables
  -> subagent.py / task.py / dashboard.py
```

`runtime_context` owns subagent runtime identity and lifecycle. `runtime_session` owns main/subagent host context bindings. `dashboard_process` owns project-local Dashboard server status. `maintenance_event` records dry-run and cleanup executions.

`agent_run` should no longer be an independent state source. Implementation should either:

1. Read Dashboard agent runs from `runtime_context`, or
2. Keep `agent_run` as a compatibility projection updated from `runtime_context` in the same transaction.

Preferred: first move reads to `runtime_context`; keep `agent_run` only for compatibility until tests and template consumers stop depending on it.

## Migration Strategy

1. Extend schema with runtime tables.
2. Add FlowStore APIs for runtime context/session/process/maintenance operations.
3. Import existing runtime JSON files on first access or via an explicit migration command.
4. Switch runtime reads to DB.
5. Switch runtime writes to DB.
6. Emit minimal pointer files only for compatibility if required.
7. Update specs/tests; keep root/template parity.

## Dashboard Maintenance UX

Add a "数据库维护" entry in Dashboard.

View sections:

- 数据库概览：DB/WAL size, table row counts.
- 垃圾扫描：closed runtime, orphan session, stale process.
- 清理预览：dry-run summary and confirmation token.
- 执行清理：requires confirmation token.
- 压缩操作：checkpoint and vacuum as separate actions.

Safety behavior:

- destructive controls disabled until dry-run completes.
- confirmation token expires quickly or binds to dry-run summary.
- UI text warns that VACUUM can briefly lock DB.

## CLI Maintenance UX

CLI mirrors Dashboard for scriptable recovery:

```powershell
.\.cowork-flow\run.cmd dashboard db stats
.\.cowork-flow\run.cmd dashboard db cleanup --dry-run --retention-days 30
.\.cowork-flow\run.cmd dashboard db cleanup --confirm <token> --retention-days 30
.\.cowork-flow\run.cmd dashboard db checkpoint
.\.cowork-flow\run.cmd dashboard db vacuum
```

## Risks

- Hook/bootstrap path may run before DB is initialized. Mitigation: ensure schema initialization is cheap and deterministic; keep pointer-file fallback during transition.
- SQLite lock contention during VACUUM. Mitigation: separate operation, clear warning, tests for command behavior.
- Existing tests expect runtime JSON. Mitigation: update tests to assert DB state; keep compatibility import tests.
- Root/template divergence. Mitigation: parity tests and `npm run test:template`.
