#!/usr/bin/env python3
"""Typed, fail-closed gate pipeline for lifecycle commands."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .models import (
    GateContext,
    GateDefinition,
    GateExecution,
    GateResult,
    ValidatorBinding,
    Violation,
)
from .registry import GateLoadError, GateRegistry


REVIEW_GATE_SEQUENCE = (
    "implementation",
    "runtime_rules",
    "coding_standards",
    "quality_machine_checks",
    "complexity",
)

STAGE_GATES = {
    "task_start": ("runtime_rules",),
    "task_review": REVIEW_GATE_SEQUENCE,
    "task_complete": REVIEW_GATE_SEQUENCE,
}


def _core_validator_bindings() -> tuple[ValidatorBinding, ...]:
    return (
        ValidatorBinding(
            key="runtime_rules",
            module="validate_rules",
            function="validate_rules",
            positional=("repo_root", "scope", "task_dir"),
        ),
        ValidatorBinding(
            key="implementation",
            module="validate_implementation",
            function="validate_implementation",
            positional=("repo_root", "task_dir"),
            keyword={
                "allow_spec_file_modifications": "allow_spec_file_modifications",
            },
        ),
        ValidatorBinding(
            key="coding_standards",
            module="validate_coding_standards",
            function="validate_coding_standards",
            positional=("repo_root", "task_dir"),
        ),
    )


def _quality_validator_bindings() -> tuple[ValidatorBinding, ...]:
    return (
        ValidatorBinding(
            key="quality_machine_checks",
            module="validate_coding_standards",
            function="validate_machine_checks",
            positional=("repo_root", "task_dir"),
        ),
    )


def _validator_bindings() -> tuple[ValidatorBinding, ...]:
    return (
        *_core_validator_bindings(),
        *_quality_validator_bindings(),
        ValidatorBinding(
            key="complexity",
            module="validate_coding_standards",
            function="validate_complexity_signals",
            positional=("repo_root", "task_dir"),
        ),
    )


def _core_gate_definitions() -> tuple[GateDefinition, ...]:
    return (
        GateDefinition(
            id="runtime_rules",
            validator_key="runtime_rules",
            required=True,
            block_message="Spec enforcement blocked lifecycle transition",
            log_violations=True,
        ),
        GateDefinition(
            id="implementation",
            validator_key="implementation",
            required=True,
            block_message="Implementation gate blocked lifecycle transition",
            warning_message="Implementation violations detected",
        ),
        GateDefinition(
            id="coding_standards",
            validator_key="coding_standards",
            required=True,
            block_message="Coding standards gate blocked lifecycle transition",
        ),
    )


def _quality_gate_definitions() -> tuple[GateDefinition, ...]:
    return (
        GateDefinition(
            id="quality_machine_checks",
            validator_key="quality_machine_checks",
            required=False,
            block_message="",
            warning_message="Quality machine-check warnings",
        ),
    )


def _gate_definitions() -> tuple[GateDefinition, ...]:
    return (
        *_core_gate_definitions(),
        *_quality_gate_definitions(),
        GateDefinition(
            id="complexity",
            validator_key="complexity",
            required=False,
            block_message="",
            warning_message="Complexity review warnings",
        ),
    )


def build_default_registry() -> GateRegistry:
    registry = GateRegistry()
    for binding in _validator_bindings():
        registry.register_validator(binding)
    for definition in _gate_definitions():
        registry.register_gate(definition)
    return registry


def _pipeline_violation(
    *,
    rule_id: str,
    context: GateContext,
    definition: GateDefinition,
    message: str,
    fix_hint: str,
) -> dict:
    severity = "block" if definition.required else "warn"
    return Violation(
        rule_id=rule_id,
        type="gate_pipeline",
        severity=severity,
        message=message,
        file=definition.validator_key,
        fix_hint=fix_hint,
        scope=context.scope,
        gate_id=definition.id,
        error_code=rule_id,
    ).to_dict()


def _normalize_violation(
    raw_violation: object,
    context: GateContext,
    definition: GateDefinition,
) -> dict:
    if not isinstance(raw_violation, Mapping):
        return _pipeline_violation(
            rule_id="GATE-PROTOCOL-001",
            context=context,
            definition=definition,
            message=f"Gate {definition.id} returned a non-object violation",
            fix_hint="Return violation dictionaries with stable metadata.",
        )
    try:
        return Violation.from_mapping(
            raw_violation,
            scope=context.scope,
            gate_id=definition.id,
        ).to_dict()
    except ValueError as error:
        return _pipeline_violation(
            rule_id="GATE-PROTOCOL-001",
            context=context,
            definition=definition,
            message=f"Gate {definition.id} returned invalid metadata: {error}",
            fix_hint="Return violations with rule_id, severity, and message.",
        )


def _normalize_violations(
    raw_result: object,
    context: GateContext,
    definition: GateDefinition,
) -> list[dict]:
    if isinstance(raw_result, list):
        return [
            _normalize_violation(item, context, definition)
            for item in raw_result
        ]
    return [
        _pipeline_violation(
            rule_id="GATE-PROTOCOL-001",
            context=context,
            definition=definition,
            message=(
                f"Gate {definition.id} returned "
                f"{type(raw_result).__name__}; expected a list of violations"
            ),
            fix_hint="Return list[dict] from the registered gate validator.",
        )
    ]


class GatePipeline:
    """Execute the configured stage gates with fail-closed semantics."""

    def __init__(self, registry: GateRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    def _execute_gate(
        self,
        context: GateContext,
        gate_id: str,
    ) -> GateExecution:
        definition = self.registry.gate(gate_id)
        try:
            raw_result = self.registry.invoke(definition, context)
        except GateLoadError as error:
            violations = [
                _pipeline_violation(
                    rule_id="GATE-LOAD-001",
                    context=context,
                    definition=definition,
                    message=f"Gate {definition.id} could not load: {error}",
                    fix_hint="Restore the required validator module and function.",
                )
            ]
        except Exception as error:
            violations = [
                _pipeline_violation(
                    rule_id="GATE-EXEC-001",
                    context=context,
                    definition=definition,
                    message=f"Gate {definition.id} failed during execution: {error}",
                    fix_hint="Fix the validator exception; lifecycle gates fail closed.",
                )
            ]
        else:
            violations = _normalize_violations(raw_result, context, definition)
        return GateExecution(
            definition=definition,
            result=GateResult.from_violations(
                context.scope,
                violations,
                context.task_dir,
            ),
        )

    def run(self, context: GateContext) -> GateResult:
        executions = [
            self._execute_gate(context, gate_id)
            for gate_id in STAGE_GATES[context.scope]
        ]
        violations = [
            violation
            for execution in executions
            for violation in execution.result.violations
        ]
        priority_violations = [
            violation
            for violation in violations
            if str(violation.get("rule_id", "")).startswith("GATE-")
        ]
        ordinary_violations = [
            violation
            for violation in violations
            if not str(violation.get("rule_id", "")).startswith("GATE-")
        ]

        return GateResult(
            scope=context.scope,
            task_dir=context.task_dir,
            violations=[*priority_violations, *ordinary_violations],
            executions=executions,
        )


class GateRunner:
    """Compatibility facade used by lifecycle commands and tests."""

    def __init__(
        self,
        repo_root: Path,
        registry: GateRegistry | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.pipeline = GatePipeline(registry)

    def run(
        self,
        scope: str,
        task_dir: Path | None = None,
        *,
        allow_spec_file_modifications: bool = False,
    ) -> GateResult:
        return self.pipeline.run(
            GateContext(
                repo_root=self.repo_root,
                scope=scope,
                task_dir=task_dir,
                allow_spec_file_modifications=allow_spec_file_modifications,
            )
        )

    def coding_standards_summary(self, task_dir: Path | None = None) -> str:
        module = __import__(
            "validate_coding_standards",
            globals(),
            locals(),
            ["get_coding_standards_summary"],
            1,
        )
        return module.get_coding_standards_summary(self.repo_root, task_dir)

    def log(self, result: GateResult) -> None:
        try:
            module = __import__(
                "validate_rules",
                globals(),
                locals(),
                ["log_violations"],
                1,
            )
        except ImportError:
            return
        module.log_violations(
            result.violations,
            result.scope,
            result.task_dir,
            self.repo_root,
        )


__all__ = [
    "GateContext",
    "GateDefinition",
    "GateExecution",
    "GatePipeline",
    "GateRegistry",
    "GateResult",
    "GateRunner",
    "Violation",
    "build_default_registry",
]
