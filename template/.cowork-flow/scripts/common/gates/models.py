#!/usr/bin/env python3
"""Typed models shared by the cowork-flow gate pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


GATE_SCOPES = frozenset({"task_start", "task_review", "task_complete"})
GATE_SEVERITIES = frozenset({"block", "warn", "advisory"})


@dataclass(frozen=True)
class GateContext:
    """Runtime inputs available to every gate validator."""

    repo_root: Path
    scope: str
    task_dir: Path | None = None
    allow_spec_file_modifications: bool = False

    def __post_init__(self) -> None:
        if self.scope not in GATE_SCOPES:
            raise ValueError(f"unsupported gate scope: {self.scope}")
        object.__setattr__(self, "repo_root", Path(self.repo_root))
        if self.task_dir is not None:
            object.__setattr__(self, "task_dir", Path(self.task_dir))


@dataclass(frozen=True)
class ValidatorBinding:
    """Lazy module/function binding plus its GateContext argument mapping."""

    key: str
    module: str
    function: str
    positional: tuple[str, ...] = ()
    keyword: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GateDefinition:
    """Declarative gate definition registered once and reused by stages."""

    id: str
    validator_key: str
    required: bool
    block_message: str
    warning_message: str | None = None
    log_violations: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("gate id must be non-empty")
        if not self.validator_key.strip():
            raise ValueError(f"gate {self.id} validator_key must be non-empty")
        if self.required and not self.block_message.strip():
            raise ValueError(f"required gate {self.id} needs a block message")


@dataclass(frozen=True)
class Violation:
    """Stable typed representation of a validator failure."""

    rule_id: str
    type: str
    severity: str
    message: str
    file: str
    fix_hint: str
    scope: str
    gate_id: str
    passed: bool = False
    error_code: str | None = None
    extra: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("violation rule_id must be non-empty")
        if self.severity not in GATE_SEVERITIES:
            raise ValueError(f"unsupported violation severity: {self.severity}")
        if self.scope not in GATE_SCOPES:
            raise ValueError(f"unsupported violation scope: {self.scope}")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, object],
        *,
        scope: str,
        gate_id: str,
    ) -> "Violation":
        rule_id = str(raw.get("rule_id") or raw.get("id") or "").strip()
        severity = str(raw.get("severity") or "").strip()
        message = str(raw.get("message") or "").strip()
        if not rule_id or not severity or not message:
            raise ValueError("validator violation must define rule_id, severity, and message")

        known_fields = {
            "rule_id",
            "id",
            "type",
            "severity",
            "message",
            "file",
            "fix_hint",
            "scope",
            "gate_id",
            "passed",
            "error_code",
        }
        extra = {key: value for key, value in raw.items() if key not in known_fields}
        return cls(
            rule_id=rule_id,
            type=str(raw.get("type") or "gate"),
            severity=severity,
            message=message,
            file=str(raw.get("file") or ""),
            fix_hint=str(raw.get("fix_hint") or ""),
            scope=scope,
            gate_id=gate_id,
            passed=bool(raw.get("passed", False)),
            error_code=str(raw.get("error_code") or rule_id),
            extra=extra,
        )

    def to_dict(self) -> dict:
        result = {
            "rule_id": self.rule_id,
            "type": self.type,
            "severity": self.severity,
            "passed": self.passed,
            "message": self.message,
            "file": self.file,
            "fix_hint": self.fix_hint,
            "scope": self.scope,
            "gate_id": self.gate_id,
            "error_code": self.error_code or self.rule_id,
        }
        result.update(self.extra)
        return result


@dataclass
class GateResult:
    """Normalized aggregate or per-gate result."""

    scope: str
    task_dir: Path | None = None
    violations: list[dict] = field(default_factory=list)
    executions: list["GateExecution"] = field(default_factory=list)

    @classmethod
    def from_violations(
        cls,
        scope: str,
        violations: list[dict],
        task_dir: Path | None = None,
    ) -> "GateResult":
        normalized = []
        for violation in violations:
            item = dict(violation)
            item.setdefault("scope", scope)
            item.setdefault("error_code", item.get("rule_id") or item.get("id"))
            normalized.append(item)
        return cls(scope=scope, task_dir=task_dir, violations=normalized)

    @property
    def blockers(self) -> list[dict]:
        return [
            violation
            for violation in self.violations
            if violation.get("severity") == "block"
        ]

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def exit_code(self) -> int:
        return 1 if self.blocked else 0


@dataclass(frozen=True)
class GateExecution:
    """One gate definition evaluated within a pipeline stage."""

    definition: GateDefinition
    result: GateResult

    @property
    def blocked(self) -> bool:
        return self.result.blocked
