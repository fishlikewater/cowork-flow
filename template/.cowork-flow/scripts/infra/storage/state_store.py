#!/usr/bin/env python3
"""Revision-aware UTF-8 JSON state persistence."""

from __future__ import annotations

import errno
import json
import math
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


STATE_METADATA_KEY = "_state"
LOCK_METADATA_SCHEMA_VERSION = 1
DEFAULT_STALE_LOCK_SECONDS = 30 * 60
ATOMIC_REPLACE_ATTEMPTS = 5
ATOMIC_REPLACE_RETRY_SECONDS = 0.01


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


@dataclass(frozen=True)
class LockInfo:
    """Read-only facts about a StateStore lock file."""

    lock_path: Path
    target: Path
    exists: bool
    pid: int | None
    created_at: str | None
    age_seconds: float | None
    owner_availability: str
    status: str
    detail: str

    @property
    def owner_available(self) -> bool | None:
        if self.owner_availability == "available":
            return True
        if self.owner_availability == "missing":
            return False
        return None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "lockPath": str(self.lock_path),
            "target": str(self.target),
            "exists": self.exists,
            "ownerAvailability": self.owner_availability,
            "status": self.status,
            "detail": self.detail,
        }
        if self.pid is not None:
            data["pid"] = self.pid
        if self.created_at is not None:
            data["createdAt"] = self.created_at
        if self.age_seconds is not None:
            data["ageSeconds"] = self.age_seconds
        return data


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

    def inspect_lock(
        self,
        path: str | Path,
        *,
        stale_after_seconds: float = DEFAULT_STALE_LOCK_SECONDS,
    ) -> LockInfo:
        target = Path(path)
        return self.inspect_lock_path(
            self.lock_path_for(target),
            target=target,
            stale_after_seconds=stale_after_seconds,
        )

    def inspect_lock_path(
        self,
        lock_path: str | Path,
        *,
        target: str | Path | None = None,
        stale_after_seconds: float = DEFAULT_STALE_LOCK_SECONDS,
    ) -> LockInfo:
        stale_after_seconds = self._validated_stale_threshold(
            stale_after_seconds
        )
        lock = Path(lock_path)
        target_path = (
            Path(target)
            if target is not None
            else self.target_from_lock_path(lock)
        )
        try:
            raw_text = lock.read_text(encoding="utf-8")
        except FileNotFoundError:
            return LockInfo(
                lock_path=lock,
                target=target_path,
                exists=False,
                pid=None,
                created_at=None,
                age_seconds=None,
                owner_availability="unknown",
                status="absent",
                detail="state lock is absent",
            )
        except (OSError, UnicodeDecodeError) as error:
            return LockInfo(
                lock_path=lock,
                target=target_path,
                exists=True,
                pid=None,
                created_at=None,
                age_seconds=None,
                owner_availability="unknown",
                status="unknown",
                detail=f"state lock metadata could not be read: {error}",
            )
        return self._lock_info_from_text(
            lock,
            target_path,
            raw_text,
            stale_after_seconds=stale_after_seconds,
        )

    def remove_stale_lock(
        self,
        path: str | Path,
        *,
        stale_after_seconds: float = DEFAULT_STALE_LOCK_SECONDS,
    ) -> bool:
        stale_after_seconds = self._validated_stale_threshold(
            stale_after_seconds
        )
        target = Path(path)
        lock_path = self.lock_path_for(target)
        try:
            original = lock_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        except (OSError, UnicodeDecodeError):
            return False
        info = self._lock_info_from_text(
            lock_path,
            target,
            original,
            stale_after_seconds=stale_after_seconds,
        )
        if info.status != "recoverable":
            return False
        try:
            current = lock_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        except (OSError, UnicodeDecodeError):
            return False
        if current != original:
            return False
        try:
            lock_path.unlink()
        except FileNotFoundError:
            return False
        except OSError as error:
            raise StateStoreError(
                "STATE-LOCK-002",
                target,
                "stale state lock could not be removed",
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
            StateStore._replace_with_retry(temp_path, path)
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

    @staticmethod
    def _replace_with_retry(source: Path, target: Path) -> None:
        for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
            try:
                os.replace(source, target)
                return
            except PermissionError:
                if attempt == ATOMIC_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(
                    ATOMIC_REPLACE_RETRY_SECONDS * (2 ** attempt)
                )

    @contextmanager
    def _lock(self, path: Path) -> Iterator[None]:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.lock_path_for(path)
        deadline = time.monotonic() + self.lock_timeout_seconds
        lock_handle = None
        while lock_handle is None:
            try:
                lock_handle = lock_path.open("x", encoding="utf-8")
                self._write_lock_payload(lock_handle, path)
            except FileExistsError as error:
                if time.monotonic() >= deadline:
                    raise StateStoreError(
                        "STATE-LOCK-001",
                        path,
                        "timed out waiting for state lock",
                    ) from error
                time.sleep(self.lock_poll_seconds)
            except OSError as error:
                if lock_handle is not None:
                    try:
                        lock_handle.close()
                    except OSError:
                        pass
                    try:
                        lock_path.unlink(missing_ok=True)
                    except OSError:
                        pass
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

    @staticmethod
    def lock_path_for(path: str | Path) -> Path:
        target = Path(path)
        return target.with_name(f"{target.name}.lock")

    @staticmethod
    def target_from_lock_path(lock_path: str | Path) -> Path:
        lock = Path(lock_path)
        if lock.name.endswith(".lock"):
            return lock.with_name(lock.name[:-5])
        return lock

    @staticmethod
    def _write_lock_file(
        lock_path: Path,
        target: Path,
        *,
        pid: int | None = None,
        created_at: str | None = None,
    ) -> None:
        payload = StateStore._lock_payload(
            target,
            pid=pid,
            created_at=created_at,
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_lock_payload(stream: object, target: Path) -> None:
        payload = StateStore._lock_payload(target)
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        stream.flush()

    @staticmethod
    def _lock_payload(
        target: Path,
        *,
        pid: int | None = None,
        created_at: str | None = None,
    ) -> dict[str, object]:
        return {
            "schemaVersion": LOCK_METADATA_SCHEMA_VERSION,
            "pid": os.getpid() if pid is None else pid,
            "createdAt": created_at or StateStore._now_iso(),
            "target": str(target),
        }

    @staticmethod
    def _validated_stale_threshold(value: float) -> float:
        threshold = float(value)
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("stale_after_seconds must be a non-negative finite number")
        return threshold

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")

    @staticmethod
    def _parse_created_at(value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _pid_exists(pid: int) -> bool | None:
        if pid <= 0:
            return False
        if pid == os.getpid():
            return True
        if os.name == "nt":
            return StateStore._windows_pid_exists(pid)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as error:
            if getattr(error, "errno", None) == errno.ESRCH:
                return False
            if getattr(error, "errno", None) == errno.EPERM:
                return True
            return None
        return True

    @staticmethod
    def _windows_pid_exists(pid: int) -> bool | None:
        try:
            import ctypes
        except ImportError:
            return None
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        error = ctypes.windll.kernel32.GetLastError()
        if error == 87:  # ERROR_INVALID_PARAMETER: PID does not exist.
            return False
        if error == 5:  # ERROR_ACCESS_DENIED: process exists but is protected.
            return True
        return None

    def _lock_info_from_text(
        self,
        lock_path: Path,
        target: Path,
        raw_text: str,
        *,
        stale_after_seconds: float,
    ) -> LockInfo:
        try:
            raw = json.loads(raw_text) if raw_text.strip() else {}
        except json.JSONDecodeError:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        pid = raw.get("pid")
        pid_value = pid if isinstance(pid, int) and not isinstance(pid, bool) else None
        created_at = raw.get("createdAt")
        created_at_value = created_at if isinstance(created_at, str) else None
        created = self._parse_created_at(created_at_value)
        age_seconds = None
        if created is not None:
            age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - created).total_seconds(),
            )
        else:
            try:
                age_seconds = max(0.0, time.time() - lock_path.stat().st_mtime)
            except OSError:
                age_seconds = None
        target_value = raw.get("target")
        if isinstance(target_value, str) and target_value.strip():
            target = Path(target_value)

        if pid_value is None:
            availability = "unknown"
            status = "unknown"
            detail = "state lock owner pid is unknown"
        else:
            exists = self._pid_exists(pid_value)
            if exists is True:
                availability = "available"
                status = "active"
                detail = "state lock owner process is still available"
            elif exists is False:
                availability = "missing"
                if age_seconds is not None and age_seconds >= stale_after_seconds:
                    status = "recoverable"
                    detail = "state lock owner process is missing and lock is stale"
                else:
                    status = "stale-but-unsafe"
                    detail = (
                        "state lock owner process is missing but lock age "
                        "does not satisfy the stale threshold"
                    )
            else:
                availability = "unknown"
                status = "unknown"
                detail = "state lock owner process availability is unknown"
        return LockInfo(
            lock_path=lock_path,
            target=target,
            exists=True,
            pid=pid_value,
            created_at=created_at_value,
            age_seconds=age_seconds,
            owner_availability=availability,
            status=status,
            detail=detail,
        )
