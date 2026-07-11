"""Schema migration repository for the Flow SQLite store."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from common.time_utils import now_utc_iso as _now


class MigrationStore:
    """Schema migration boundary for FlowStore's SQLite database."""

    def __init__(
        self,
        *,
        db: sqlite3.Connection,
        db_path: str,
        transaction: Callable,
        migration_dir: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        self.db = db
        self.db_path = db_path
        self._transaction = transaction
        self.migration_dir = migration_dir or Path(__file__).resolve().parent / "migrations"
        self.backup_dir = backup_dir or Path(__file__).resolve().parent.parent.parent / ".runtime"

    def validate_applied_checksums(self) -> None:
        """Verify that all applied migrations' checksums match their current file content."""
        if not self.migration_dir.is_dir():
            return
        rows = self.db.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        for row in rows:
            expected = row["checksum"]
            sql_file = self.migration_dir / f"{row['name']}.sql"
            if not sql_file.is_file():
                raise RuntimeError(
                    f"migration v{row['version']} ({row['name']}): file not found at {sql_file}"
                )
            content = sql_file.read_text(encoding="utf-8")
            actual = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            if actual != expected:
                raise RuntimeError(
                    f"migration v{row['version']} ({row['name']}): "
                    f"checksum mismatch (expected={expected}, actual={actual})"
                )

    def ensure_schema_migrations_table(self) -> None:
        """Create schema_migrations table if it does not exist."""
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version     INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                applied_at  TEXT NOT NULL,
                checksum    TEXT NOT NULL
            )"""
        )
        self.db.commit()

    def discover_pending(self) -> list[tuple[int, str, Path]]:
        """Return list of (version, name, path) for migrations not yet applied."""
        applied = {
            row["version"]
            for row in self.db.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        if not self.migration_dir.is_dir():
            return []
        pattern = re.compile(r"^(\d{4})_.+\.sql$")
        pending: list[tuple[int, str, Path]] = []
        for sql_file in sorted(self.migration_dir.glob("*.sql")):
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

    def apply(self, version: int, name: str, path: Path) -> None:
        """Apply a single migration file and record version/checksum after success."""
        content = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        now = _now()

        self.db.executescript(content)

        def _do_record():
            self.db.execute(
                "INSERT INTO schema_migrations (version, name, applied_at, checksum) VALUES (?,?,?,?)",
                (version, name, now, checksum),
            )
            return None

        self._transaction(_do_record)

    def backup_before_migration(self) -> None:
        """Copy the DB file to a backup location before applying migrations."""
        db_path = Path(self.db_path)
        if not db_path.exists():
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self.backup_dir / f"db-backup-v{timestamp}.sqlite"
        import shutil

        shutil.copy2(str(db_path), str(backup_path))

    def get_applied(self) -> list[dict]:
        """Return list of applied migration records ordered by version."""
        rows = self.db.execute(
            "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        return [dict(r) for r in rows]
