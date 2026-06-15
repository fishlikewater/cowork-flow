# DB Runtime State And Maintenance Spec

## Source Of Truth

- DB is the single source of truth for runtime state.
- Files remain the source for reviewable assets: PRD, plan, change documents, spec documents, and task context JSONL.
- Existing `.cowork-flow/.runtime/*.json` files are compatibility inputs only during migration. New full runtime state must not depend on them after the migration path is in place.

## Runtime Tables

### `runtime_context`

Stores one formal or advisory runtime context.

Required fields:

- `id TEXT PRIMARY KEY`
- `scope TEXT NOT NULL`
- `host TEXT NOT NULL`
- `adapter TEXT NOT NULL`
- `agent_type TEXT NOT NULL`
- `role TEXT NOT NULL`
- `task_id TEXT REFERENCES task(id) ON DELETE SET NULL`
- `task_dir TEXT`
- `parent_context_key TEXT`
- `dispatch_kind TEXT NOT NULL`
- `status TEXT NOT NULL`
- `bound_context_key TEXT`
- `transport_json TEXT NOT NULL DEFAULT '{}'`
- `assignment_json TEXT NOT NULL DEFAULT '{}'`
- `authority_json TEXT NOT NULL DEFAULT '{}'`
- `created_at TEXT NOT NULL`
- `bound_at TEXT`
- `closed_at TEXT`
- `last_seen_at TEXT`

### `runtime_session`

Stores main-session and subagent host-context bindings.

Required fields:

- `context_key TEXT PRIMARY KEY`
- `scope TEXT NOT NULL`
- `runtime_context_id TEXT REFERENCES runtime_context(id) ON DELETE CASCADE`
- `active_task_id TEXT REFERENCES task(id) ON DELETE SET NULL`
- `active_task_path TEXT`
- `platform TEXT NOT NULL`
- `status TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `last_seen_at TEXT NOT NULL`

### `dashboard_process`

Stores current project Dashboard process state.

Required fields:

- `id TEXT PRIMARY KEY`
- `pid INTEGER`
- `host TEXT NOT NULL`
- `port INTEGER NOT NULL`
- `url TEXT NOT NULL`
- `status TEXT NOT NULL`
- `started_at TEXT NOT NULL`
- `last_seen_at TEXT`
- `stdout_log TEXT`
- `stderr_log TEXT`

### `maintenance_event`

Stores DB maintenance executions.

Required fields:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `kind TEXT NOT NULL`
- `dry_run INTEGER NOT NULL`
- `summary_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`

## Compatibility

- Migration imports existing runtime context/session/dashboard JSON files into DB.
- During compatibility window, writes may emit a tiny pointer file only when needed by existing hooks/adapters. The pointer may contain `runtime_context_id`, `context_key`, and `db_path`, but not full state.
- All new read paths must prefer DB.

## Cleanup Policy

- Dry-run is mandatory before destructive cleanup from Dashboard.
- Cleanup may remove:
  - closed runtime contexts older than retention days.
  - runtime sessions with missing runtime context.
  - stale dashboard process rows whose pid is not alive.
  - imported compatibility rows marked stale.
- Cleanup must not remove:
  - active task data.
  - open or bound runtime contexts.
  - audit rows for active or non-archived tasks.
  - task, plan, change, or spec files.
- WAL checkpoint and VACUUM are explicit operations separate from row cleanup.

## Dashboard Contract

- `GET /api/maintenance/db/stats` returns DB size, WAL size, row counts, stale counts, and recommended actions.
- `POST /api/maintenance/db/cleanup?dry_run=true` returns a summary and confirmation token without deleting rows.
- `POST /api/maintenance/db/cleanup` requires the confirmation token from the dry-run response.
- `POST /api/maintenance/db/checkpoint` runs WAL checkpoint.
- `POST /api/maintenance/db/vacuum` runs VACUUM and may briefly lock the DB.

## CLI Contract

- `dashboard db stats`
- `dashboard db cleanup --dry-run --retention-days <n>`
- `dashboard db cleanup --confirm <token> --retention-days <n>`
- `dashboard db checkpoint`
- `dashboard db vacuum`
