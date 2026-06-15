#!/usr/bin/env python3
"""Flow persistent store layer — SQLite-backed task management."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.time_utils import now_utc_iso as _now
from patterns.base import TaskView


class FlowStore:
    """SQLite persistence layer for the Flow system — single write-entry point."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self) -> None:
        try:
            self.db.close()
        except sqlite3.Error:
            pass

    def _ensure_schema(self) -> None:
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        if schema_path.is_file():
            self.db.executescript(schema_path.read_text(encoding="utf-8"))
        else:
            print(f"[WARN] schema.sql not found at {schema_path}", file=sys.stderr)

    def _transaction(self, fn):
        """Execute fn() inside a BEGIN IMMEDIATE transaction with retry."""
        for attempt in range(3):
            try:
                self.db.execute("BEGIN IMMEDIATE")
                result = fn()
                self.db.commit()
                return result
            except sqlite3.OperationalError as e:
                self.db.rollback()
                if "locked" in str(e) and attempt < 2:
                    time.sleep(0.1)
                else:
                    raise
            except Exception:
                self.db.rollback()
                raise
        raise RuntimeError("unreachable: _transaction exhausted retries without raising")

    # --- Task CRUD ---

    def create_task(self, *,
        id: str, title: str,
        description: str = "", status: str = "planning",
        pattern: str = "generic", priority: str = "P2",
        creator: str, assignee: str, level: str = "L1",
        parent_id: str | None = None,
        artifact_dir: str | None = None,
        commit_sha: str | None = None,
        meta: dict | None = None,
    ) -> str:
        now = _now()
        artifact_dir = artifact_dir or f"{datetime.now(timezone.utc).strftime('%m-%d')}-{id}"
        meta_json = json.dumps(meta or {}, ensure_ascii=False)

        def _do_insert():
            self.db.execute(
                """INSERT INTO task (id, artifact_dir, title, description, status,
                   pattern, priority, creator, assignee, level, parent_id,
                   commit_sha, created_at, updated_at, meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (id, artifact_dir, title, description, status,
                 pattern, priority, creator, assignee, level, parent_id,
                 commit_sha, now, now, meta_json),
            )
            self.db.execute(
                "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
                (id, None, status, creator, "", now),
            )
            if parent_id:
                self.db.execute(
                    "INSERT INTO task_child (parent_id, child_id) VALUES (?,?)",
                    (parent_id, id),
                )
            return id

        try:
            return self._transaction(_do_insert)
        except sqlite3.IntegrityError as e:
            msg = str(e)
            if "UNIQUE constraint failed: task.id" in msg or "PRIMARY KEY" in msg:
                print(f"[WARN] Duplicate task ID: {id}", file=sys.stderr)
            elif "task_child" in msg or "parent_id" in msg:
                print(f"[WARN] Cannot link child {id} to parent {parent_id}: {e}", file=sys.stderr)
            else:
                print(f"[WARN] Integrity error creating task {id}: {e}", file=sys.stderr)
            raise

    def get_task(self, task_id: str) -> TaskView | None:
        row = self.db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        children = [r["child_id"] for r in self.db.execute(
            "SELECT child_id FROM task_child WHERE parent_id = ? ORDER BY sort_order", (task_id,)
        ).fetchall()]
        return _row_to_taskview(row, children=children)

    def get_task_by_artifact_dir(self, artifact_dir: str) -> TaskView | None:
        row = self.db.execute(
            "SELECT * FROM task WHERE artifact_dir = ?", (artifact_dir,)
        ).fetchone()
        if row is None:
            return None
        children = [r["child_id"] for r in self.db.execute(
            "SELECT child_id FROM task_child WHERE parent_id = ? ORDER BY sort_order", (row["id"],)
        ).fetchall()]
        return _row_to_taskview(row, children=children)

    def update_status(self, task_id: str, new_status: str,
                      operator: str, reason: str = "") -> bool:
        def _do_update():
            now = _now()
            old = self.db.execute("SELECT status FROM task WHERE id = ?", (task_id,)).fetchone()
            if old is None:
                return False
            old_status = old["status"]
            self.db.execute(
                "UPDATE task SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, task_id),
            )
            self.db.execute(
                "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
                (task_id, old_status, new_status, operator, reason, now),
            )
            if new_status == "completed":
                self.db.execute("UPDATE task SET completed_at = ? WHERE id = ?", (now, task_id))
            return True

        return self._transaction(_do_update) or False

    def update_meta(self, task_id: str, meta: dict) -> bool:
        def _do_update_meta():
            meta_json = json.dumps(meta, ensure_ascii=False)
            now = _now()
            self.db.execute(
                "UPDATE task SET meta = ?, updated_at = ? WHERE id = ?",
                (meta_json, now, task_id),
            )
            return True

        return self._transaction(_do_update_meta) or False

    def list_tasks(self, status: str | None = None) -> list[TaskView]:
        if status:
            rows = self.db.execute(
                "SELECT * FROM task WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM task ORDER BY created_at DESC").fetchall()
        parent_map: dict[str, list[str]] = {}
        for cr in self.db.execute("SELECT parent_id, child_id FROM task_child ORDER BY parent_id, sort_order").fetchall():
            parent_map.setdefault(cr["parent_id"], []).append(cr["child_id"])
        return [_row_to_taskview(r, children=parent_map.get(r["id"], [])) for r in rows]

    def list_children(self, parent_id: str) -> list[TaskView]:
        rows = self.db.execute(
            """SELECT t.* FROM task t
               JOIN task_child tc ON t.id = tc.child_id
               WHERE tc.parent_id = ? ORDER BY tc.sort_order""",
            (parent_id,),
        ).fetchall()
        parent_map: dict[str, list[str]] = {}
        for cr in self.db.execute("SELECT parent_id, child_id FROM task_child ORDER BY parent_id, sort_order").fetchall():
            parent_map.setdefault(cr["parent_id"], []).append(cr["child_id"])
        return [_row_to_taskview(r, children=parent_map.get(r["id"], [])) for r in rows]

    def link_child(self, parent_id: str, child_id: str, sort_order: int = 0) -> bool:
        def _do_link():
            self.db.execute(
                "INSERT INTO task_child (parent_id, child_id, sort_order) VALUES (?,?,?)",
                (parent_id, child_id, sort_order),
            )
            self.db.execute(
                "UPDATE task SET parent_id = ?, updated_at = ? WHERE id = ?",
                (parent_id, _now(), child_id),
            )
            return True

        return self._transaction(_do_link) or False

    def unlink_child(self, parent_id: str, child_id: str) -> bool:
        def _do_unlink():
            self.db.execute(
                "DELETE FROM task_child WHERE parent_id = ? AND child_id = ?",
                (parent_id, child_id),
            )
            self.db.execute(
                "UPDATE task SET parent_id = NULL, updated_at = ? WHERE id = ?",
                (_now(), child_id),
            )
            return True

        return self._transaction(_do_unlink) or False

    def all_children_done(self, parent_id: str) -> bool:
        count = self.db.execute(
            """SELECT COUNT(*) FROM task t
               JOIN task_child tc ON t.id = tc.child_id
               WHERE tc.parent_id = ? AND t.status NOT IN ('completed','archived')""",
            (parent_id,),
        ).fetchone()[0]
        return count == 0

    # --- Block ---

    def block_task(self, task_id: str, reason: str) -> bool:
        def _do_block():
            task = self.db.execute(
                "SELECT status FROM task WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return False
            existing = self.db.execute(
                "SELECT id FROM block WHERE task_id = ? AND resolved_at IS NULL LIMIT 1",
                (task_id,),
            ).fetchone()
            if existing:
                return False
            now = _now()
            self.db.execute(
                "INSERT INTO block (task_id, reason, blocked_at) VALUES (?,?,?)",
                (task_id, reason, now),
            )
            self.db.execute(
                "UPDATE task SET status = ?, updated_at = ? WHERE id = ?",
                ("blocked", now, task_id),
            )
            self.db.execute(
                "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
                (task_id, task["status"], "blocked", "system", reason, now),
            )
            return True

        return self._transaction(_do_block) or False

    def unblock_task(self, task_id: str, decision: str = "", decided_by: str = "") -> bool:
        def _do_unblock():
            task = self.db.execute(
                "SELECT status FROM task WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return False
            block = self.db.execute(
                "SELECT id FROM block WHERE task_id = ? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if block is None:
                return False
            now = _now()
            self.db.execute(
                "UPDATE block SET decision = ?, decided_by = ?, resolved_at = ? WHERE id = ?",
                (decision, decided_by, now, block["id"]),
            )
            self.db.execute(
                "UPDATE task SET status = ?, updated_at = ? WHERE id = ?",
                ("in_progress", now, task_id),
            )
            self.db.execute(
                "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
                (task_id, task["status"], "in_progress", decided_by or "system", decision, now),
            )
            return True

        return self._transaction(_do_unblock) or False

    def get_active_block(self, task_id: str):
        row = self.db.execute(
            "SELECT * FROM block WHERE task_id = ? AND resolved_at IS NULL ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None

    # --- Runtime state ---

    def _resolve_task_id_from_path(self, task_path: str | None) -> str | None:
        if not task_path:
            return None
        artifact_dir = Path(task_path).name
        task = self.get_task_by_artifact_dir(artifact_dir)
        if task:
            return task.id
        stripped = artifact_dir
        from common.paths import TASK_DATE_PREFIX_PATTERN

        if TASK_DATE_PREFIX_PATTERN.match(stripped):
            stripped = TASK_DATE_PREFIX_PATTERN.sub("", stripped)
        task = self.get_task(stripped)
        return task.id if task else None

    def upsert_runtime_context(self, payload: dict) -> str:
        runtime_id = str(payload.get("runtime_context_id") or payload.get("id") or "").strip()
        if not runtime_id:
            raise ValueError("runtime_context_id is required")
        now = _now()
        stored = dict(payload)
        stored["runtime_context_id"] = runtime_id
        task_dir = stored.get("task_dir") if isinstance(stored.get("task_dir"), str) else None
        task_id = stored.get("task_id") if isinstance(stored.get("task_id"), str) else None
        if task_id is None:
            task_id = self._resolve_task_id_from_path(task_dir)
            if task_id:
                stored["task_id"] = task_id
        created_at = str(stored.get("created_at") or now)
        last_seen_at = str(stored.get("last_seen_at") or stored.get("updated_at") or now)
        transport = stored.get("transport") if isinstance(stored.get("transport"), dict) else {}
        assignment = stored.get("assignment") if isinstance(stored.get("assignment"), dict) else {}
        authority = stored.get("authority") if isinstance(stored.get("authority"), dict) else {}

        values = (
            runtime_id,
            str(stored.get("scope") or "subagent"),
            str(stored.get("host") or "unknown"),
            str(stored.get("adapter") or "unknown"),
            str(stored.get("agent_type") or "unknown"),
            str(stored.get("role") or stored.get("agent_type") or "unknown"),
            task_id,
            task_dir,
            stored.get("parent_context_key") if isinstance(stored.get("parent_context_key"), str) else None,
            str(stored.get("dispatch_kind") or "advisory"),
            str(stored.get("status") or "pending"),
            stored.get("bound_context_key") if isinstance(stored.get("bound_context_key"), str) else None,
            json.dumps(transport, ensure_ascii=False, sort_keys=True),
            json.dumps(assignment, ensure_ascii=False, sort_keys=True),
            json.dumps(authority, ensure_ascii=False, sort_keys=True),
            json.dumps(stored, ensure_ascii=False, sort_keys=True),
            created_at,
            stored.get("bound_at") if isinstance(stored.get("bound_at"), str) else None,
            stored.get("closed_at") if isinstance(stored.get("closed_at"), str) else None,
            last_seen_at,
        )

        def _do_upsert():
            self.db.execute(
                """INSERT INTO runtime_context (
                   id, scope, host, adapter, agent_type, role, task_id, task_dir,
                   parent_context_key, dispatch_kind, status, bound_context_key,
                   transport_json, assignment_json, authority_json, payload_json,
                   created_at, bound_at, closed_at, last_seen_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     scope=excluded.scope,
                     host=excluded.host,
                     adapter=excluded.adapter,
                     agent_type=excluded.agent_type,
                     role=excluded.role,
                     task_id=excluded.task_id,
                     task_dir=excluded.task_dir,
                     parent_context_key=excluded.parent_context_key,
                     dispatch_kind=excluded.dispatch_kind,
                     status=excluded.status,
                     bound_context_key=excluded.bound_context_key,
                     transport_json=excluded.transport_json,
                     assignment_json=excluded.assignment_json,
                     authority_json=excluded.authority_json,
                     payload_json=excluded.payload_json,
                     bound_at=excluded.bound_at,
                     closed_at=excluded.closed_at,
                     last_seen_at=excluded.last_seen_at""",
                values,
            )
            return runtime_id

        return self._transaction(_do_upsert) or runtime_id

    def _runtime_context_from_row(self, row) -> dict:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        for json_field, payload_key in (
            ("transport_json", "transport"),
            ("assignment_json", "assignment"),
            ("authority_json", "authority"),
        ):
            if not isinstance(payload.get(payload_key), dict):
                try:
                    payload[payload_key] = json.loads(row[json_field])
                except (TypeError, json.JSONDecodeError):
                    payload[payload_key] = {}
        payload.update(
            {
                "runtime_context_id": row["id"],
                "scope": row["scope"],
                "host": row["host"],
                "adapter": row["adapter"],
                "agent_type": row["agent_type"],
                "role": row["role"],
                "task_id": row["task_id"],
                "task_dir": row["task_dir"],
                "parent_context_key": row["parent_context_key"],
                "dispatch_kind": row["dispatch_kind"],
                "status": row["status"],
                "bound_context_key": row["bound_context_key"],
                "created_at": row["created_at"],
                "bound_at": row["bound_at"],
                "closed_at": row["closed_at"],
                "last_seen_at": row["last_seen_at"],
            }
        )
        return payload

    def get_runtime_context(self, runtime_context_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM runtime_context WHERE id = ?",
            (runtime_context_id,),
        ).fetchone()
        return self._runtime_context_from_row(row) if row else None

    def list_runtime_contexts_for_task(self, task_id: str) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM runtime_context WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        return [self._runtime_context_from_row(row) for row in rows]

    def upsert_runtime_session(self, context_key: str, payload: dict) -> str:
        if not context_key.strip():
            raise ValueError("context_key is required")
        now = _now()
        stored = dict(payload)
        stored["context_key"] = context_key
        task_path = stored.get("active_task_path") if isinstance(stored.get("active_task_path"), str) else None
        task_id = stored.get("active_task_id") if isinstance(stored.get("active_task_id"), str) else None
        if task_id is None:
            task_id = self._resolve_task_id_from_path(task_path)
            if task_id:
                stored["active_task_id"] = task_id
        runtime_context_id = stored.get("runtime_context_id") if isinstance(stored.get("runtime_context_id"), str) else None
        created_at = str(stored.get("created_at") or now)
        last_seen_at = str(stored.get("last_seen_at") or now)
        values = (
            context_key,
            str(stored.get("scope") or "main"),
            runtime_context_id,
            task_id,
            task_path,
            str(stored.get("platform") or "manual"),
            str(stored.get("status") or "active"),
            json.dumps(stored, ensure_ascii=False, sort_keys=True),
            created_at,
            last_seen_at,
        )

        def _do_upsert():
            self.db.execute(
                """INSERT INTO runtime_session (
                   context_key, scope, runtime_context_id, active_task_id,
                   active_task_path, platform, status, payload_json, created_at, last_seen_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(context_key) DO UPDATE SET
                     scope=excluded.scope,
                     runtime_context_id=excluded.runtime_context_id,
                     active_task_id=excluded.active_task_id,
                     active_task_path=excluded.active_task_path,
                     platform=excluded.platform,
                     status=excluded.status,
                     payload_json=excluded.payload_json,
                     last_seen_at=excluded.last_seen_at""",
                values,
            )
            return context_key

        return self._transaction(_do_upsert) or context_key

    def _runtime_session_from_row(self, row) -> dict:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(
            {
                "context_key": row["context_key"],
                "scope": row["scope"],
                "runtime_context_id": row["runtime_context_id"],
                "active_task_id": row["active_task_id"],
                "active_task_path": row["active_task_path"],
                "platform": row["platform"],
                "status": row["status"],
                "created_at": row["created_at"],
                "last_seen_at": row["last_seen_at"],
            }
        )
        return payload

    def get_runtime_session(self, context_key: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM runtime_session WHERE context_key = ?",
            (context_key,),
        ).fetchone()
        return self._runtime_session_from_row(row) if row else None

    def delete_runtime_session(self, context_key: str) -> bool:
        def _do_delete():
            cursor = self.db.execute(
                "DELETE FROM runtime_session WHERE context_key = ?",
                (context_key,),
            )
            return cursor.rowcount > 0

        return self._transaction(_do_delete) or False

    def delete_runtime_sessions_for_task(self, task_path: str) -> int:
        normalized = task_path.replace("\\", "/")

        def _do_delete():
            cursor = self.db.execute(
                "DELETE FROM runtime_session WHERE active_task_path = ?",
                (normalized,),
            )
            return cursor.rowcount

        return self._transaction(_do_delete) or 0

    # --- Agent Run ---

    def create_agent_run(self, *,
        id: str, task_id: str, agent_type: str,
        status: str = "pending",
        host_context_key: str | None = None,
        created_at: str,
    ) -> str:
        def _do_create_ar():
            self.db.execute(
                "INSERT INTO agent_run (id, task_id, agent_type, status, host_context_key, created_at) VALUES (?,?,?,?,?,?)",
                (id, task_id, agent_type, status, host_context_key, created_at),
            )
            return id

        return self._transaction(_do_create_ar) or id

    def update_agent_run_status(self, run_id: str, status: str) -> bool:
        def _do_update_ar():
            closed_at = _now() if status == "closed" else None
            if closed_at:
                cursor = self.db.execute(
                    "UPDATE agent_run SET status = ?, closed_at = ? WHERE id = ?",
                    (status, closed_at, run_id),
                )
            else:
                cursor = self.db.execute(
                    "UPDATE agent_run SET status = ? WHERE id = ?",
                    (status, run_id),
                )
            return cursor.rowcount > 0

        return self._transaction(_do_update_ar) or False

    def get_active_agent_run(self, task_id: str, agent_type: str | None = None):
        if agent_type:
            row = self.db.execute(
                """SELECT * FROM agent_run
                   WHERE task_id = ? AND agent_type = ? AND status != 'closed'
                   ORDER BY created_at DESC LIMIT 1""",
                (task_id, agent_type),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM agent_run WHERE task_id = ? AND status != 'closed' ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_agent_runs_for_parent(self, parent_id: str) -> list[dict]:
        runtime_rows = self.db.execute(
            """SELECT rc.* FROM runtime_context rc
               JOIN task_child tc ON rc.task_id = tc.child_id
               WHERE tc.parent_id = ? ORDER BY rc.created_at""",
            (parent_id,),
        ).fetchall()
        runs = [self._runtime_context_to_agent_run(self._runtime_context_from_row(r)) for r in runtime_rows]
        runtime_ids = {run["id"] for run in runs}
        rows = self.db.execute(
            """SELECT ar.* FROM agent_run ar
               JOIN task_child tc ON ar.task_id = tc.child_id
               WHERE tc.parent_id = ? ORDER BY ar.created_at""",
            (parent_id,),
        ).fetchall()
        runs.extend(dict(r) for r in rows if r["id"] not in runtime_ids)
        return runs

    def list_agent_runs_for_task(self, task_id: str) -> list[dict]:
        runtime_rows = self.db.execute(
            "SELECT * FROM runtime_context WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        runs = [self._runtime_context_to_agent_run(self._runtime_context_from_row(r)) for r in runtime_rows]
        runtime_ids = {run["id"] for run in runs}
        rows = self.db.execute(
            "SELECT * FROM agent_run WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        runs.extend(dict(r) for r in rows if r["id"] not in runtime_ids)
        return runs

    def _runtime_context_to_agent_run(self, context: dict) -> dict:
        return {
            "id": context.get("runtime_context_id"),
            "runtime_context_id": context.get("runtime_context_id"),
            "task_id": context.get("task_id"),
            "agent_type": context.get("agent_type"),
            "status": context.get("status"),
            "host_context_key": context.get("bound_context_key"),
            "error_message": context.get("error_message"),
            "retry_count": 0,
            "created_at": context.get("created_at"),
            "closed_at": context.get("closed_at"),
            "dispatch_kind": context.get("dispatch_kind"),
        }

    # --- Audit ---

    def get_audit_trail(self, task_id: str):
        rows = self.db.execute(
            "SELECT * FROM audit WHERE task_id = ? ORDER BY created_at", (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def archive_task(self, task_id: str, operator: str, reason: str = "") -> bool:
        def _do_archive():
            now = _now()
            task = self.db.execute(
                "SELECT status, parent_id FROM task WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                return False
            child_rows = self.db.execute(
                "SELECT child_id FROM task_child WHERE parent_id = ?",
                (task_id,),
            ).fetchall()
            self.db.execute(
                "UPDATE task SET status = ?, parent_id = NULL, updated_at = ? WHERE id = ?",
                ("archived", now, task_id),
            )
            self.db.execute(
                "UPDATE task SET parent_id = NULL, updated_at = ? WHERE parent_id = ?",
                (now, task_id),
            )
            if task["parent_id"]:
                self.db.execute(
                    "DELETE FROM task_child WHERE parent_id = ? AND child_id = ?",
                    (task["parent_id"], task_id),
                )
            for child in child_rows:
                self.db.execute(
                    "DELETE FROM task_child WHERE parent_id = ? AND child_id = ?",
                    (task_id, child["child_id"]),
                )
            self.db.execute(
                "INSERT INTO audit (task_id, from_status, to_status, operator, reason, created_at) VALUES (?,?,?,?,?,?)",
                (task_id, task["status"], "archived", operator, reason, now),
            )
            return True

        return self._transaction(_do_archive) or False

    # --- Dashboard ---

    def board_view(self) -> dict:
        statuses = ["planning", "in_progress", "review", "blocked", "completed", "archived"]

        columns = []
        for st in statuses:
            rows = self.db.execute(
                """SELECT t.id, t.title, t.status, t.pattern, t.priority, t.assignee,
                   COALESCE((SELECT COUNT(*) FROM task_child WHERE parent_id = t.id), 0) AS child_total,
                   COALESCE((SELECT COUNT(*) FROM task_child tc JOIN task ct ON tc.child_id = ct.id
                     WHERE tc.parent_id = t.id AND ct.status IN ('completed','archived')), 0) AS child_done
                   FROM task t WHERE t.status = ? ORDER BY t.priority, t.created_at""",
                (st,),
            ).fetchall()
            columns.append({"status": st, "tasks": [dict(r) for r in rows]})
        return {"columns": columns}


    def upsert_dashboard_process(self, process_id: str, state: dict) -> str:
        if not process_id.strip():
            raise ValueError("dashboard process id is required")
        now = _now()
        stored = dict(state)
        stored["id"] = process_id
        values = (
            process_id,
            int(stored["pid"]) if stored.get("pid") is not None else None,
            str(stored.get("host") or "127.0.0.1"),
            int(stored.get("port") or 0),
            str(stored.get("url") or ""),
            str(stored.get("status") or "running"),
            json.dumps(stored, ensure_ascii=False, sort_keys=True),
            str(stored.get("started_at") or now),
            str(stored.get("last_seen_at") or now),
            stored.get("stdout_log") if isinstance(stored.get("stdout_log"), str) else None,
            stored.get("stderr_log") if isinstance(stored.get("stderr_log"), str) else None,
        )

        def _do_upsert():
            self.db.execute(
                """INSERT INTO dashboard_process (
                   id, pid, host, port, url, status, payload_json, started_at,
                   last_seen_at, stdout_log, stderr_log)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     pid=excluded.pid,
                     host=excluded.host,
                     port=excluded.port,
                     url=excluded.url,
                     status=excluded.status,
                     payload_json=excluded.payload_json,
                     last_seen_at=excluded.last_seen_at,
                     stdout_log=excluded.stdout_log,
                     stderr_log=excluded.stderr_log""",
                values,
            )
            return process_id

        return self._transaction(_do_upsert) or process_id

    def get_dashboard_process(self, process_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM dashboard_process WHERE id = ?",
            (process_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(
            {
                "id": row["id"],
                "pid": row["pid"],
                "host": row["host"],
                "port": row["port"],
                "url": row["url"],
                "status": row["status"],
                "started_at": row["started_at"],
                "last_seen_at": row["last_seen_at"],
                "stdout_log": row["stdout_log"],
                "stderr_log": row["stderr_log"],
            }
        )
        return payload

    def delete_dashboard_process(self, process_id: str) -> bool:
        def _do_delete():
            cursor = self.db.execute(
                "DELETE FROM dashboard_process WHERE id = ?",
                (process_id,),
            )
            return cursor.rowcount > 0

        return self._transaction(_do_delete) or False

    # --- DB maintenance ---

    def _table_count(self, table: str) -> int:
        return int(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def _maintenance_cutoff(self, retention_days: int) -> str:
        days = max(0, int(retention_days))
        return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def maintenance_plan(
        self,
        *,
        retention_days: int = 30,
        stale_dashboard_ids: list[str] | None = None,
    ) -> dict:
        cutoff = self._maintenance_cutoff(retention_days)
        closed_runtime_rows = self.db.execute(
            """SELECT id FROM runtime_context
               WHERE status = 'closed' AND COALESCE(closed_at, last_seen_at, created_at) <= ?
               ORDER BY id""",
            (cutoff,),
        ).fetchall()
        orphan_session_rows = self.db.execute(
            """SELECT rs.context_key FROM runtime_session rs
               LEFT JOIN runtime_context rc ON rs.runtime_context_id = rc.id
               WHERE rs.scope = 'subagent'
                 AND rs.runtime_context_id IS NOT NULL
                 AND rc.id IS NULL
               ORDER BY rs.context_key"""
        ).fetchall()
        stale_dashboard_ids = sorted(set(stale_dashboard_ids or []))
        return {
            "retention_days": int(retention_days),
            "cutoff": cutoff,
            "closed_runtime_context_ids": [row["id"] for row in closed_runtime_rows],
            "orphan_runtime_session_keys": [row["context_key"] for row in orphan_session_rows],
            "stale_dashboard_process_ids": stale_dashboard_ids,
        }

    def cleanup_token(self, summary: dict) -> str:
        token_summary = dict(summary)
        token_summary.pop("cutoff", None)
        digest = hashlib.sha256(
            json.dumps(token_summary, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest[:16]

    def maintenance_stats(
        self,
        *,
        retention_days: int = 30,
        stale_dashboard_ids: list[str] | None = None,
    ) -> dict:
        db_path = Path(self.db_path)
        wal_path = db_path.with_name(db_path.name + "-wal")
        plan = self.maintenance_plan(
            retention_days=retention_days,
            stale_dashboard_ids=stale_dashboard_ids,
        )
        tables = [
            "task",
            "audit",
            "block",
            "agent_run",
            "runtime_context",
            "runtime_session",
            "dashboard_process",
            "maintenance_event",
        ]
        cleanup_total = (
            len(plan["closed_runtime_context_ids"])
            + len(plan["orphan_runtime_session_keys"])
            + len(plan["stale_dashboard_process_ids"])
        )
        wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
        return {
            "db_path": str(db_path),
            "db_bytes": db_path.stat().st_size if db_path.exists() else 0,
            "wal_bytes": wal_bytes,
            "row_counts": {table: self._table_count(table) for table in tables},
            "cleanup_candidates": {
                "closed_runtime_contexts": len(plan["closed_runtime_context_ids"]),
                "orphan_runtime_sessions": len(plan["orphan_runtime_session_keys"]),
                "stale_dashboard_processes": len(plan["stale_dashboard_process_ids"]),
            },
            "retention_days": int(retention_days),
            "recommended_actions": [
                action
                for action, count in (("cleanup", cleanup_total), ("checkpoint", wal_bytes))
                if count
            ],
        }

    def cleanup_database(
        self,
        *,
        retention_days: int = 30,
        dry_run: bool,
        confirm: str | None = None,
        stale_dashboard_ids: list[str] | None = None,
    ) -> dict:
        plan = self.maintenance_plan(
            retention_days=retention_days,
            stale_dashboard_ids=stale_dashboard_ids,
        )
        token = self.cleanup_token(plan)
        summary = {
            **plan,
            "confirmation_token": token,
            "deleted": {
                "closed_runtime_contexts": 0,
                "orphan_runtime_sessions": 0,
                "stale_dashboard_processes": 0,
            },
            "dry_run": bool(dry_run),
        }
        if dry_run:
            return summary
        if confirm != token:
            raise ValueError("cleanup confirmation token mismatch")

        def _delete_many(table: str, column: str, values: list[str]) -> int:
            if not values:
                return 0
            placeholders = ",".join("?" for _ in values)
            cursor = self.db.execute(
                f"DELETE FROM {table} WHERE {column} IN ({placeholders})",
                values,
            )
            return cursor.rowcount

        def _do_cleanup():
            summary["deleted"] = {
                "closed_runtime_contexts": _delete_many(
                    "runtime_context",
                    "id",
                    plan["closed_runtime_context_ids"],
                ),
                "orphan_runtime_sessions": _delete_many(
                    "runtime_session",
                    "context_key",
                    plan["orphan_runtime_session_keys"],
                ),
                "stale_dashboard_processes": _delete_many(
                    "dashboard_process",
                    "id",
                    plan["stale_dashboard_process_ids"],
                ),
            }
            summary["dry_run"] = False
            self.db.execute(
                "INSERT INTO maintenance_event (kind, dry_run, summary_json, created_at) VALUES (?,?,?,?)",
                ("cleanup", 0, json.dumps(summary, ensure_ascii=False, sort_keys=True), _now()),
            )
            return summary

        return self._transaction(_do_cleanup)

    def record_maintenance_event(self, kind: str, summary: dict, *, dry_run: bool = False) -> None:
        def _do_insert():
            self.db.execute(
                "INSERT INTO maintenance_event (kind, dry_run, summary_json, created_at) VALUES (?,?,?,?)",
                (kind, 1 if dry_run else 0, json.dumps(summary, ensure_ascii=False, sort_keys=True), _now()),
            )
            return None

        self._transaction(_do_insert)

    def checkpoint(self) -> dict:
        rows = self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        summary = {"result": [tuple(row) for row in rows]}
        self.record_maintenance_event("checkpoint", summary)
        return summary

    def vacuum(self) -> dict:
        self.db.execute("VACUUM")
        summary = {"vacuumed": True}
        self.record_maintenance_event("vacuum", summary)
        return summary

def _row_to_taskview(row, children: list[str] | None = None):
    meta = json.loads(row["meta"])
    return TaskView(
        id=row["id"],
        artifact_dir=row["artifact_dir"],
        title=row["title"],
        status=row["status"],
        pattern=row["pattern"],
        priority=row["priority"] if "priority" in row.keys() else "P2",
        creator=row["creator"] if "creator" in row.keys() else "",
        assignee=row["assignee"] if "assignee" in row.keys() else "",
        parent_id=row["parent_id"],
        children=children if children is not None else [],
        meta=meta,
        block_reason=None,
    )


# --- CLI entrypoint ---

def cmd_init_db(args: argparse.Namespace) -> int:
    from common.paths import get_db_path
    db_path = get_db_path()
    if Path(db_path).exists():
        print(f"Database already exists: {db_path}", file=sys.stderr)
        return 1
    FlowStore(str(db_path))  # __init__ triggers _ensure_schema
    print(f"Database created: {db_path}")
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    from flow.migrate import main as migrate_main
    return migrate_main()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flow store operations")
    sub = parser.add_subparsers(dest="flow_command")
    init_cmd = sub.add_parser("init-db", help="Initialize SQLite database")
    init_cmd.set_defaults(func=cmd_init_db)
    migrate_cmd = sub.add_parser("migrate", help="Migrate legacy task.json tasks to SQLite")
    migrate_cmd.set_defaults(func=cmd_migrate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
