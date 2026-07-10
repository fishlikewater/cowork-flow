#!/usr/bin/env python3
"""Revision-aware UTF-8 JSON state persistence."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


STATE_METADATA_KEY = "_state"


class StateStoreError(RuntimeError):
    """Raised when versioned state cannot be read or persisted."""

    def __init__(self, code: str, path: Path, detail: str) -> None:
        self.code = code
        self.path = path
        self.detail = detail
        super().__init__(f"{code}: {detail}: {path}")


@dataclass(frozen=True)
class StateSnapshot:
    path: Path
    data: dict
    revision: int
    operation_id: str | None
    exists: bool


class StateStore:
    """Read and compare-and-swap JSON state documents."""

    def __init__(
        self,
        *,
        lock_timeout_seconds: float = 5.0,
        lock_poll_seconds: float = 0.01,
    ) -> None:
        self.lock_timeout_seconds = lock_timeout_seconds
        self.lock_poll_seconds = lock_poll_seconds

    def load(
        self,
        path: str | Path,
        *,
        missing_ok: bool = False,
    ) -> StateSnapshot:
        return self._load_unlocked(Path(path), missing_ok=missing_ok)

    def replace(
        self,
        path: str | Path,
        data: dict,
        *,
        expected_revision: int | None,
        operation_id: str,
    ) -> StateSnapshot:
        target = Path(path)
        with self._lock(target):
            current = self._load_unlocked(target, missing_ok=True)
            if current.operation_id == operation_id:
                if current.data == data:
                    return current
                raise StateStoreError(
                    "STATE-IDEMPOTENCY-001",
                    target,
                    "operation id was already used with different state",
                )
            self._check_revision(target, current, expected_revision)

            next_revision = current.revision + 1
            persisted = dict(data)
            persisted[STATE_METADATA_KEY] = {
                "schema_version": 1,
                "revision": next_revision,
                "operation_id": operation_id,
            }
            self._atomic_write(target, persisted)
            return StateSnapshot(
                path=target,
                data=dict(data),
                revision=next_revision,
                operation_id=operation_id,
                exists=True,
            )

    def delete(
        self,
        path: str | Path,
        *,
        expected_revision: int | None,
        operation_id: str,
    ) -> bool:
        del operation_id
        target = Path(path)
        with self._lock(target):
            current = self._load_unlocked(target, missing_ok=True)
            if not current.exists:
                return False
            self._check_revision(target, current, expected_revision)
            try:
                target.unlink()
            except OSError as error:
                raise StateStoreError(
                    "STATE-SAVE-001",
                    target,
                    "state file could not be deleted",
                ) from error
            return True

    def _load_unlocked(
        self,
        path: Path,
        *,
        missing_ok: bool,
    ) -> StateSnapshot:
        try:
            raw_text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            if missing_ok:
                return StateSnapshot(path, {}, 0, None, False)
            raise StateStoreError(
                "STATE-LOAD-001",
                path,
                "state file is missing",
            ) from error
        except UnicodeDecodeError as error:
            raise StateStoreError(
                "STATE-LOAD-003",
                path,
                "state file is not valid UTF-8",
            ) from error
        except OSError as error:
            raise StateStoreError(
                "STATE-LOAD-004",
                path,
                "state file could not be read",
            ) from error

        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise StateStoreError(
                "STATE-LOAD-002",
                path,
                "state file is not valid JSON",
            ) from error
        if not isinstance(raw, dict):
            raise StateStoreError(
                "STATE-LOAD-002",
                path,
                "state file must contain a JSON object",
            )

        persisted = dict(raw)
        metadata = persisted.pop(STATE_METADATA_KEY, {})
        if not isinstance(metadata, dict):
            raise StateStoreError(
                "STATE-LOAD-005",
                path,
                "state metadata must be a JSON object",
            )
        revision = metadata.get("revision", 0)
        if not isinstance(revision, int) or revision < 0:
            raise StateStoreError(
                "STATE-LOAD-005",
                path,
                "state revision must be a non-negative integer",
            )
        operation_id = metadata.get("operation_id")
        if operation_id is not None and not isinstance(operation_id, str):
            raise StateStoreError(
                "STATE-LOAD-005",
                path,
                "state operation id must be a string",
            )
        return StateSnapshot(
            path=path,
            data=persisted,
            revision=revision,
            operation_id=operation_id,
            exists=True,
        )

    @staticmethod
    def _check_revision(
        path: Path,
        current: StateSnapshot,
        expected_revision: int | None,
    ) -> None:
        if (
            expected_revision is not None
            and current.revision != expected_revision
        ):
            raise StateStoreError(
                "STATE-CONFLICT-001",
                path,
                "expected revision "
                f"{expected_revision}, found {current.revision}",
            )

    @staticmethod
    def _atomic_write(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(
            f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        )
        json_text = json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ) + "\n"
        try:
            temp_path.write_text(json_text, encoding="utf-8")
            os.replace(temp_path, path)
        except OSError as error:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise StateStoreError(
                "STATE-SAVE-001",
                path,
                "state file could not be written atomically",
            ) from error

    @contextmanager
    def _lock(self, path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_name(f"{path.name}.lock")
        deadline = time.monotonic() + self.lock_timeout_seconds
        lock_handle = None
        while lock_handle is None:
            try:
                lock_handle = lock_path.open("x", encoding="utf-8")
            except FileExistsError as error:
                if time.monotonic() >= deadline:
                    raise StateStoreError(
                        "STATE-LOCK-001",
                        path,
                        "timed out waiting for state lock",
                    ) from error
                time.sleep(self.lock_poll_seconds)
            except OSError as error:
                raise StateStoreError(
                    "STATE-LOCK-001",
                    path,
                    "state lock could not be created",
                ) from error
        try:
            yield
        finally:
            lock_handle.close()
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
