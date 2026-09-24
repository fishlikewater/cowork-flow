#!/usr/bin/env python3
"""Recoverable Unit of Work for local JSON state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from infra.storage.operation_log import OperationLog
from infra.storage.state_store import StateStore, StateStoreError


class UnitOfWorkError(RuntimeError):
    """Raised when a multi-file state operation cannot converge."""

    def __init__(
        self,
        operation_id: str,
        detail: str,
        *,
        code: str = "UOW-001",
    ) -> None:
        self.operation_id = operation_id
        self.detail = detail
        self.code = code
        super().__init__(f"{operation_id}: {detail}")


@dataclass(frozen=True)
class StateMutation:
    path: Path
    action: str
    expected_revision: int
    before: dict
    after: dict | None


FaultInjector = Callable[[int, StateMutation], None]


class UnitOfWork:
    """Stage state mutations and recover interrupted commits."""

    def __init__(
        self,
        repo_root: Path,
        *,
        operation_id: str,
        kind: str,
        state_store: StateStore | None = None,
        operation_log: OperationLog | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.operation_id = operation_id
        self.kind = kind
        self.state_store = state_store or StateStore()
        self.operation_log = operation_log or OperationLog(
            self.repo_root,
            state_store=self.state_store,
        )
        self.fault_injector = fault_injector
        self.mutations: list[StateMutation] = []

    def replace(
        self,
        path: str | Path,
        data: dict,
        *,
        expected_revision: int | None = None,
    ) -> None:
        target = Path(path)
        snapshot = self.state_store.load(target, missing_ok=True)
        self.mutations.append(
            StateMutation(
                path=target,
                action="replace",
                expected_revision=(
                    snapshot.revision
                    if expected_revision is None
                    else expected_revision
                ),
                before=snapshot.data,
                after=dict(data),
            )
        )

    def delete(
        self,
        path: str | Path,
        *,
        expected_revision: int | None = None,
    ) -> None:
        target = Path(path)
        snapshot = self.state_store.load(target, missing_ok=True)
        self.mutations.append(
            StateMutation(
                path=target,
                action="delete",
                expected_revision=(
                    snapshot.revision
                    if expected_revision is None
                    else expected_revision
                ),
                before=snapshot.data,
                after=None,
            )
        )

    def commit(self) -> dict:
        path = self.operation_log.path(self.operation_id)
        candidate = self._record()
        if path.is_file():
            record = self.operation_log.load(self.operation_id)
        else:
            record = self.operation_log.create(
                self.operation_id,
                candidate,
            )
        if not self._request_matches(record, candidate):
            raise UnitOfWorkError(
                self.operation_id,
                "operation id was already used with a different request",
                code="UOW-OPERATION-REUSE-001",
            )
        return self._apply(record)

    @classmethod
    def recover_all(
        cls,
        repo_root: Path,
        *,
        state_store: StateStore | None = None,
    ) -> tuple[str, ...]:
        root = Path(repo_root)
        store = state_store or StateStore()
        operation_log = OperationLog(root, state_store=store)
        recovered: list[str] = []
        for record in operation_log.pending():
            operation_id = str(record["operation_id"])
            unit = cls(
                root,
                operation_id=operation_id,
                kind=str(record.get("kind") or "recovery"),
                state_store=store,
                operation_log=operation_log,
            )
            unit._apply(record)
            recovered.append(operation_id)
        return tuple(recovered)

    def _record(self) -> dict:
        participants = [
            {
                "path": str(mutation.path),
                "action": mutation.action,
                "expected_revision": mutation.expected_revision,
                "before": mutation.before,
                "after": mutation.after,
            }
            for mutation in self.mutations
        ]
        return {
            "schema_version": 1,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "request_fingerprint": self._participants_fingerprint(participants),
            "phase": "prepared",
            "applied": [],
            "participants": participants,
        }

    def _request_matches(self, record: dict, candidate: dict) -> bool:
        recorded_fingerprint = record.get("request_fingerprint")
        candidate_fingerprint = candidate.get("request_fingerprint")
        if isinstance(recorded_fingerprint, str) and recorded_fingerprint:
            return recorded_fingerprint == candidate_fingerprint
        recorded = record.get("participants")
        if not isinstance(recorded, list):
            return False
        return self._participants_fingerprint(recorded) == candidate_fingerprint

    @staticmethod
    def _participants_fingerprint(participants: list[dict]) -> str:
        normalized = [
            {
                "path": str(participant.get("path") or ""),
                "action": str(participant.get("action") or ""),
                "expected_revision": int(
                    participant.get("expected_revision") or 0
                ),
                "after": participant.get("after"),
            }
            for participant in participants
        ]
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _apply(self, record: dict) -> dict:
        phase = record.get("phase")
        if phase == "committed":
            return record
        if phase == "conflicted":
            error = record.get("error")
            detail = "operation is already conflicted"
            if isinstance(error, dict) and error.get("detail"):
                detail = f"{detail}: {error['detail']}"
            raise UnitOfWorkError(
                self.operation_id,
                detail,
                code="UOW-CONFLICT-001",
            )

        record["phase"] = "applying"
        self.operation_log.save(self.operation_id, record)
        applied = {
            int(index)
            for index in record.get("applied", [])
        }
        participants = list(record.get("participants") or [])
        for index, participant in enumerate(participants):
            if index in applied:
                continue
            mutation = self._mutation(participant)
            try:
                self._apply_mutation(mutation)
            except StateStoreError as error:
                rollback_error = self._rollback_applied(
                    applied,
                    participants,
                )
                record["phase"] = "conflicted"
                record["error"] = {
                    "code": error.code,
                    "path": str(error.path),
                    "detail": error.detail,
                }
                record["rolled_back"] = not bool(rollback_error)
                if rollback_error:
                    record["rollback_error"] = rollback_error
                self.operation_log.save(self.operation_id, record)
                raise UnitOfWorkError(
                    self.operation_id,
                    error.detail,
                    code="UOW-CONFLICT-001",
                ) from error

            if self.fault_injector is not None:
                self.fault_injector(index, mutation)

            applied.add(index)
            record["applied"] = sorted(applied)
            self.operation_log.save(self.operation_id, record)

        record["phase"] = "committed"
        record.pop("error", None)
        self.operation_log.save(self.operation_id, record)
        return record

    def _rollback_applied(
        self,
        applied: set[int],
        participants: list[dict],
    ) -> list[dict] | None:
        """Best-effort compensation without overwriting newer writers."""
        errors: list[dict] = []
        for index in sorted(applied, reverse=True):
            if index < 0 or index >= len(participants):
                continue
            mutation = self._mutation(participants[index])
            try:
                current = self.state_store.load(mutation.path, missing_ok=True)
                if mutation.action == "replace":
                    if (
                        not current.exists
                        or current.operation_id != self.operation_id
                        or current.data != (mutation.after or {})
                    ):
                        continue
                    self.state_store.replace(
                        mutation.path,
                        mutation.before,
                        expected_revision=current.revision,
                        operation_id=f"{self.operation_id}:rollback:{index}",
                    )
                elif mutation.action == "delete":
                    if mutation.before:
                        if current.exists:
                            continue
                        self.state_store.replace(
                            mutation.path,
                            mutation.before,
                            expected_revision=0,
                            operation_id=f"{self.operation_id}:rollback:{index}",
                        )
            except StateStoreError as error:
                errors.append(
                    {
                        "index": index,
                        "code": error.code,
                        "path": str(error.path),
                        "detail": error.detail,
                    }
                )
        return errors or None

    def _apply_mutation(self, mutation: StateMutation) -> None:
        if mutation.action == "delete":
            self.state_store.delete(
                mutation.path,
                expected_revision=mutation.expected_revision,
                operation_id=self.operation_id,
            )
            return
        self.state_store.replace(
            mutation.path,
            mutation.after or {},
            expected_revision=mutation.expected_revision,
            operation_id=self.operation_id,
        )

    @staticmethod
    def _mutation(participant: dict) -> StateMutation:
        return StateMutation(
            path=Path(str(participant["path"])),
            action=str(participant["action"]),
            expected_revision=int(participant["expected_revision"]),
            before=dict(participant.get("before") or {}),
            after=(
                dict(participant["after"])
                if isinstance(participant.get("after"), dict)
                else None
            ),
        )
