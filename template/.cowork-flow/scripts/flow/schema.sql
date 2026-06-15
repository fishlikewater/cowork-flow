PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS task (
    id            TEXT PRIMARY KEY,
    artifact_dir  TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'planning',
    pattern       TEXT NOT NULL DEFAULT 'generic',
    priority      TEXT NOT NULL DEFAULT 'P2',
    creator       TEXT NOT NULL,
    assignee      TEXT NOT NULL,
    level         TEXT NOT NULL DEFAULT 'L1',
    parent_id     TEXT REFERENCES task(id) ON DELETE SET NULL,
    commit_sha    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    completed_at  TEXT,
    meta          TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);
CREATE INDEX IF NOT EXISTS idx_task_parent ON task(parent_id);
CREATE INDEX IF NOT EXISTS idx_task_pattern ON task(pattern);

CREATE TABLE IF NOT EXISTS task_child (
    parent_id   TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    child_id    TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (parent_id, child_id)
);

CREATE INDEX IF NOT EXISTS idx_task_child_child ON task_child(child_id);

CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT REFERENCES task(id) ON DELETE SET NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    operator    TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_task ON audit(task_id);

CREATE TABLE IF NOT EXISTS block (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    reason      TEXT NOT NULL,
    decision    TEXT,
    decided_by  TEXT,
    blocked_at  TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_block_task ON block(task_id);

CREATE TABLE IF NOT EXISTS agent_run (
    id              TEXT PRIMARY KEY,
    task_id     TEXT REFERENCES task(id) ON DELETE SET NULL,
    agent_type      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    host_context_key TEXT,
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    closed_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_run_task ON agent_run(task_id);

CREATE TABLE IF NOT EXISTS runtime_context (
    id                TEXT PRIMARY KEY,
    scope             TEXT NOT NULL,
    host              TEXT NOT NULL,
    adapter           TEXT NOT NULL,
    agent_type        TEXT NOT NULL,
    role              TEXT NOT NULL,
    task_id           TEXT REFERENCES task(id) ON DELETE SET NULL,
    task_dir          TEXT,
    parent_context_key TEXT,
    dispatch_kind     TEXT NOT NULL,
    status            TEXT NOT NULL,
    bound_context_key TEXT,
    transport_json    TEXT NOT NULL DEFAULT '{}',
    assignment_json   TEXT NOT NULL DEFAULT '{}',
    authority_json    TEXT NOT NULL DEFAULT '{}',
    payload_json      TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    bound_at          TEXT,
    closed_at         TEXT,
    last_seen_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_runtime_context_task ON runtime_context(task_id);
CREATE INDEX IF NOT EXISTS idx_runtime_context_status ON runtime_context(status);
CREATE INDEX IF NOT EXISTS idx_runtime_context_bound_key ON runtime_context(bound_context_key);

CREATE TABLE IF NOT EXISTS runtime_session (
    context_key        TEXT PRIMARY KEY,
    scope              TEXT NOT NULL,
    runtime_context_id TEXT REFERENCES runtime_context(id) ON DELETE CASCADE,
    active_task_id     TEXT REFERENCES task(id) ON DELETE SET NULL,
    active_task_path   TEXT,
    platform           TEXT NOT NULL,
    status             TEXT NOT NULL,
    payload_json       TEXT NOT NULL DEFAULT '{}',
    created_at         TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runtime_session_task ON runtime_session(active_task_id);
CREATE INDEX IF NOT EXISTS idx_runtime_session_runtime ON runtime_session(runtime_context_id);

CREATE TABLE IF NOT EXISTS dashboard_process (
    id          TEXT PRIMARY KEY,
    pid         INTEGER,
    host        TEXT NOT NULL,
    port        INTEGER NOT NULL,
    url         TEXT NOT NULL,
    status      TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    started_at  TEXT NOT NULL,
    last_seen_at TEXT,
    stdout_log  TEXT,
    stderr_log  TEXT
);

CREATE INDEX IF NOT EXISTS idx_dashboard_process_status ON dashboard_process(status);

CREATE TABLE IF NOT EXISTS maintenance_event (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,
    dry_run      INTEGER NOT NULL,
    summary_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
