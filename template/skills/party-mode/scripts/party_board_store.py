#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Storage helpers for Party Mode V2 runtime-board state."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCKS_GUARD = threading.Lock()
_STATE_LOCKS: dict[str, dict[str, Any]] = {}

__all__ = [
    "append_action_history",
    "append_audit",
    "load_board",
    "read_json",
    "save_board",
    "state_lock",
    "write_json",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock_file(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle: Any) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class _StateLock:
    def __init__(self, base_dir: Path, state: dict[str, Any]) -> None:
        self.base_dir = base_dir
        self.state = state

    def __enter__(self) -> "_StateLock":
        thread_lock = self.state["thread_lock"]
        thread_lock.acquire()
        current_thread = threading.get_ident()
        if self.state.get("owner_thread") == current_thread:
            self.state["depth"] += 1
            return self

        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.base_dir / ".state.lock"
        handle = lock_path.open("a+b")
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        _lock_file(handle)
        self.state["owner_thread"] = current_thread
        self.state["depth"] = 1
        self.state["handle"] = handle
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        thread_lock = self.state["thread_lock"]
        try:
            current_thread = threading.get_ident()
            if self.state.get("owner_thread") == current_thread:
                self.state["depth"] -= 1
                if self.state["depth"] == 0:
                    handle = self.state.pop("handle", None)
                    self.state["owner_thread"] = None
                    if handle is not None:
                        try:
                            _unlock_file(handle)
                        finally:
                            handle.close()
        finally:
            thread_lock.release()


def state_lock(base_dir: Path) -> _StateLock:
    key = str(base_dir.resolve())
    with _LOCKS_GUARD:
        state = _STATE_LOCKS.get(key)
        if state is None:
            state = {
                "thread_lock": threading.RLock(),
                "owner_thread": None,
                "depth": 0,
            }
            _STATE_LOCKS[key] = state
        return _StateLock(base_dir, state)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_board(base_dir: Path) -> dict[str, Any]:
    return read_json(base_dir / "board.json")


def save_board(base_dir: Path, board: dict[str, Any]) -> None:
    write_json(base_dir / "board.json", board)


def append_audit(base_dir: Path, event: str, payload: dict[str, Any]) -> None:
    audit_path = base_dir / "audit.jsonl"
    entry = {"timestamp": _now(), "event": event, "payload": payload}
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_action_history(base_dir: Path, event: str, payload: dict[str, Any]) -> None:
    history_path = base_dir / "action_history.jsonl"
    entry = {"timestamp": _now(), "event": event, "payload": payload}
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
