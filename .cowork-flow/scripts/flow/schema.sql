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
    task_id     TEXT NOT NULL REFERENCES task(id) ON DELETE CASCADE,
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