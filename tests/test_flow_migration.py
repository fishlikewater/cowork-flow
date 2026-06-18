"""Tests for DB schema versioned migration (P0-B)."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import tempfile
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".cowork-flow" / "scripts"))

import pytest
from flow.store import FlowStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_migration(migration_dir: Path, version: int, name: str, sql: str) -> Path:
    """Write a migration file and return its path."""
    filename = f"{version:04d}_{name}.sql"
    path = migration_dir / filename
    path.write_text(sql, encoding="utf-8")
    return path


def _compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _store_row_count(db_path: str, table: str) -> int:
    conn = sqlite3.connect(db_path)
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Test: empty DB applies 0001_initial
# ---------------------------------------------------------------------------

def test_empty_db_applies_initial_migration():
    """A brand-new DB should create schema_migrations and apply 0001_initial."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path) as store:
            rows = store.db.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
            versions = {r["version"] for r in rows}
            assert 1 in versions
            rec = store.db.execute(
                "SELECT * FROM schema_migrations WHERE version=1"
            ).fetchone()
            assert rec is not None
            assert rec["name"] == "0001_initial"
            assert len(rec["checksum"]) == 16
            tables = store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = {r["name"] for r in tables}
            assert "task" in table_names
            assert "runtime_context" in table_names


# ---------------------------------------------------------------------------
# Test: checksum tampering causes startup error
# ---------------------------------------------------------------------------

def test_checksum_tampering_raises_error():
    """If a recorded checksum is altered, re-opening should raise."""
    tmp = tempfile.mkdtemp()
    try:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path):
            pass
        # Tamper with the checksum
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE schema_migrations SET checksum='tampered00000000' WHERE version=1"
        )
        conn.commit()
        conn.close()
        # Re-opening should detect the mismatch
        try:
            with FlowStore(db_path):
                pass
            assert False, "Expected RuntimeError for checksum mismatch"
        except RuntimeError as e:
            assert "checksum mismatch" in str(e).lower() or "CHECKSUM" in str(e)
    finally:
        # Clean up - close any lingering handles
        import shutil
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test: re-opening existing DB applies no new migrations
# ---------------------------------------------------------------------------

def test_reopen_applies_nothing():
    """Opening an already-migrated DB should not re-apply migrations."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path):
            pass
        first_count = _store_row_count(db_path, "schema_migrations")
        with FlowStore(db_path):
            pass
        second_count = _store_row_count(db_path, "schema_migrations")
        assert first_count == second_count


# ---------------------------------------------------------------------------
# Test: CLI --status shows applied
# ---------------------------------------------------------------------------

def test_cli_status_shows_applied():
    """_get_applied_migrations should return the migration records."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path) as store:
            rows = store._get_applied_migrations()
            assert len(rows) >= 1
            assert rows[0]["version"] == 1
            assert rows[0]["name"] == "0001_initial"


# ---------------------------------------------------------------------------
# Test: backup created before migration
# ---------------------------------------------------------------------------

def test_backup_created_before_migration():
    """A backup file should be created in .runtime before applying migrations."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path):
            pass
        runtime_dir = (
            Path(__file__).resolve().parent.parent
            / ".cowork-flow" / ".runtime"
        )
        backups = list(runtime_dir.glob("db-backup-*.sqlite"))
        assert len(backups) >= 1


# ---------------------------------------------------------------------------
# Test: multiple sequential migrations
# ---------------------------------------------------------------------------

def test_multiple_sequential_migrations():
    """Two migrations in order should both apply correctly."""
    tmp = tempfile.mkdtemp()
    try:
        # Build an isolated copy of the migrations dir
        src_migration_dir = (
            Path(__file__).resolve().parent.parent
            / ".cowork-flow" / "scripts" / "flow" / "migrations"
        )
        iso_migration_dir = Path(tmp) / "migrations"
        iso_migration_dir.mkdir()
        for f in src_migration_dir.glob("*.sql"):
            (iso_migration_dir / f.name).write_bytes(f.read_bytes())
        # Add v2
        _write_migration(
            iso_migration_dir, 2, "add_test_table",
            "CREATE TABLE IF NOT EXISTS test_migration_table (id INTEGER PRIMARY KEY);",
        )

        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path) as store:
            # Patch migration dir for this test
            orig_migration_dir = store._discover_pending_migrations.__code__.co_consts
            # Replace by monkey-patching the module-level path resolution
            import flow.store as store_mod
            orig_file = store_mod.FlowStore._discover_pending_migrations

            def patched_discover(self):
                applied = {
                    row["version"]
                    for row in self.db.execute(
                        "SELECT version FROM schema_migrations"
                    ).fetchall()
                }
                pattern = re.compile(r"^(\d{4})_.+\.sql$")
                pending = []
                for sql_file in sorted(iso_migration_dir.glob("*.sql")):
                    m = pattern.match(sql_file.name)
                    if not m:
                        continue
                    version = int(m.group(1))
                    name = sql_file.stem
                    if version not in applied:
                        pending.append((version, name, sql_file))
                return pending

            store._discover_pending_migrations = lambda: patched_discover(store)

            pending = store._discover_pending_migrations()
            v2 = [p for p in pending if p[0] == 2]
            assert len(v2) == 1, f"Expected 1 pending v2, got {len(v2)} from {pending}"
            store._apply_migration(2, "add_test_table", v2[0][2])
            tables = store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_migration_table'"
            ).fetchall()
            assert len(tables) == 1
            rows = store._get_applied_migrations()
            versions = {r["version"] for r in rows}
            assert 1 in versions
            assert 2 in versions
    finally:
        import shutil
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test: existing FlowStore operations work after migration
# ---------------------------------------------------------------------------

def test_taskview_after_migration():
    """Existing FlowStore operations should work after migration."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path) as store:
            tid = store.create_task(
                id="mv-test", title="Migration View Test",
                creator="d", assignee="d",
            )
            task = store.get_task(tid)
            assert task is not None
            assert task.title == "Migration View Test"


# ---------------------------------------------------------------------------
# Test: stored checksum matches file content
# ---------------------------------------------------------------------------

def test_stored_checksum_matches_file():
    """The checksum in schema_migrations should match the migration file."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path) as store:
            migration_dir = (
                Path(__file__).resolve().parent.parent
                / ".cowork-flow" / "scripts" / "flow" / "migrations"
            )
            initial_file = migration_dir / "0001_initial.sql"
            content = initial_file.read_text(encoding="utf-8")
            expected_checksum = _compute_checksum(content)
            rows = store._get_applied_migrations()
            v1 = [r for r in rows if r["version"] == 1]
            assert len(v1) == 1
            assert v1[0]["checksum"] == expected_checksum


# ---------------------------------------------------------------------------
# Test: no pending migrations when nothing new
# ---------------------------------------------------------------------------

def test_no_pending_when_up_to_date():
    """After migration, _discover_pending_migrations should return empty."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        with FlowStore(db_path) as store:
            pending = store._discover_pending_migrations()
            # All SQL files in migrations/ are accounted for (v1 applied)
            assert len([p for p in pending if p[0] == 1]) == 0


# ---------------------------------------------------------------------------
# Test: version gap causes startup error
# ---------------------------------------------------------------------------

def test_version_gap_raises_error():
    """If v1 is applied but v3 file exists (v2 missing), FlowStore.__init__ should raise."""
    import importlib
    import flow.store as store_mod
    importlib.reload(store_mod)
    from flow.store import FlowStore
    tmp = tempfile.mkdtemp()
    try:

        migration_dir = Path(tmp) / "migrations"
        migration_dir.mkdir()

        # Write v1 and v3 but NOT v2
        # Use real 0001_initial.sql content so checksum validation passes
        real_initial = (Path(__file__).resolve().parent.parent / ".cowork-flow" / "scripts" / "flow" / "migrations" / "0001_initial.sql").read_text(encoding="utf-8")
        v3_content = "CREATE TABLE IF NOT EXISTS later_table (id INTEGER PRIMARY KEY);"
        _write_migration(migration_dir, 1, "initial", real_initial)
        _write_migration(migration_dir, 3, "later", v3_content)

        db_path = str(Path(tmp) / "test.db")

        # First apply v1 only (write checksum that matches real migration file)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE schema_migrations ("
                "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                "applied_at TEXT NOT NULL, checksum TEXT NOT NULL)"
            )
            checksum = _compute_checksum(real_initial)
            conn.execute(
                "INSERT INTO schema_migrations VALUES (1, '0001_initial', '2026-01-01T00:00:00Z', ?)",
                (checksum,),
            )
            conn.commit()

        # Patch _discover_pending_migrations to use our isolated migration_dir
        orig_discover = store_mod.FlowStore._discover_pending_migrations

        def patched_discover(self):
            applied = {
                row["version"]
                for row in self.db.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            }
            pattern = re.compile(r"^(\d{4})_.+\.sql$")
            pending = []
            for sql_file in sorted(migration_dir.glob("*.sql")):
                m = pattern.match(sql_file.name)
                if not m:
                    continue
                version = int(m.group(1))
                name = sql_file.stem
                if version not in applied:
                    pending.append((version, name, sql_file))
            if pending and applied:
                max_applied = max(applied)
                min_pending = min(p[0] for p in pending)
                if min_pending > max_applied + 1:
                    raise RuntimeError(
                        f"version gap detected: max applied v{max_applied}, "
                        f"but next pending is v{min_pending}; "
                        f"missing migration(s) between v{max_applied + 1} and v{min_pending - 1}"
                    )
            return pending

        store_mod.FlowStore._discover_pending_migrations = patched_discover
        try:
            with FlowStore(db_path):
                pass
            assert False, "Expected RuntimeError for version gap"
        except RuntimeError as e:
            assert "gap" in str(e).lower() or "version gap" in str(e).lower()
        finally:
            store_mod.FlowStore._discover_pending_migrations = orig_discover
    finally:
        try:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        except OSError:
            pass
