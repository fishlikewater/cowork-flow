#!/usr/bin/env python3
"""Persistent operation log for recoverable multi-file writes."""

from __future__ import annotations

from pathlib import Path

from infra.storage.state_store import StateStore, StateStoreError


FINAL_PHASES = ("committed", "conflicted")


class OperationLog:
    """Persist and enumerate Unit of Work operation records."""

    def __init__(
        self,
        repo_root: Path,
        *,
        state_store: StateStore | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.state_store = state_store or StateStore()
        self.operations_dir = (
            self.repo_root
            / ".cowork-flow"
            / ".runtime"
            / "operations"
        )

    def path(self, operation_id: str) -> Path:
        return self.operations_dir / f"{operation_id}.json"

    def load(self, operation_id: str) -> dict:
        return self.state_store.load(self.path(operation_id)).data

    def create(self, operation_id: str, data: dict) -> dict:
        path = self.path(operation_id)
        if path.is_file():
            return self.load(operation_id)
        return self.state_store.replace(
            path,
            data,
            expected_revision=0,
            operation_id=f"{operation_id}:log:1",
        ).data

    def save(self, operation_id: str, data: dict) -> dict:
        path = self.path(operation_id)
        current = self.state_store.load(path)
        return self.state_store.replace(
            path,
            data,
            expected_revision=current.revision,
            operation_id=(
                f"{operation_id}:log:{current.revision + 1}"
            ),
        ).data

    def pending(self) -> tuple[dict, ...]:
        if not self.operations_dir.is_dir():
            return ()
        records: list[dict] = []
        for path in sorted(self.operations_dir.glob("*.json")):
            try:
                record = self.state_store.load(path).data
            except StateStoreError:
                raise
            if record.get("phase") not in FINAL_PHASES:
                records.append(record)
        return tuple(records)
    def pending_facts(self) -> tuple[dict, ...]:
        """Return read-only facts about non-final operation records."""
        if not self.operations_dir.is_dir():
            return ()
        facts: list[dict] = []
        for path in sorted(self.operations_dir.glob("*.json")):
            try:
                record = self.state_store.load(path).data
            except StateStoreError as error:
                facts.append(
                    {
                        "path": str(path),
                        "phase": "unreadable",
                        "error": {
                            "code": error.code,
                            "path": str(error.path),
                            "detail": error.detail,
                        },
                    }
                )
                continue
            phase = record.get("phase")
            if phase == "committed":
                continue
            participants = record.get("participants")
            facts.append(
                {
                    "path": str(path),
                    "operation_id": str(record.get("operation_id") or path.stem),
                    "kind": str(record.get("kind") or "unknown"),
                    "phase": str(phase or "unknown"),
                    "participant_count": (
                        len(participants)
                        if isinstance(participants, list)
                        else 0
                    ),
                    "error": record.get("error"),
                }
            )
        return tuple(facts)
