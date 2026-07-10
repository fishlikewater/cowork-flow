#!/usr/bin/env python3
"""Gate definition and validator registry."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from .models import GateContext, GateDefinition, ValidatorBinding


class GateRegistryError(ValueError):
    """Raised when registry declarations are internally inconsistent."""


class GateLoadError(RuntimeError):
    """Raised when a registered validator cannot be loaded."""


class GateRegistry:
    """Register gate definitions and lazily resolve validator functions."""

    def __init__(self) -> None:
        self._bindings: OrderedDict[str, ValidatorBinding] = OrderedDict()
        self._definitions: OrderedDict[str, GateDefinition] = OrderedDict()

    def register_validator(self, binding: ValidatorBinding) -> None:
        if not binding.key.strip():
            raise GateRegistryError("validator key must be non-empty")
        if binding.key in self._bindings:
            raise GateRegistryError(f"duplicate validator key: {binding.key}")
        self._bindings[binding.key] = binding

    def register_gate(self, definition: GateDefinition) -> None:
        if definition.id in self._definitions:
            raise GateRegistryError(f"duplicate gate id: {definition.id}")
        if definition.validator_key not in self._bindings:
            raise GateRegistryError(
                f"gate {definition.id} references unknown validator: "
                f"{definition.validator_key}"
            )
        self._definitions[definition.id] = definition

    def gate(self, gate_id: str) -> GateDefinition:
        try:
            return self._definitions[gate_id]
        except KeyError as error:
            raise GateRegistryError(f"unknown gate id: {gate_id}") from error

    def invoke(self, definition: GateDefinition, context: GateContext) -> object:
        binding = self._bindings[definition.validator_key]
        validator = self._load(binding)
        args = [getattr(context, name) for name in binding.positional]
        kwargs = {
            argument: getattr(context, context_field)
            for argument, context_field in binding.keyword.items()
        }
        return validator(*args, **kwargs)

    @staticmethod
    def _load(binding: ValidatorBinding) -> Callable:
        try:
            module = __import__(
                binding.module,
                globals(),
                locals(),
                [binding.function],
                1,
            )
            validator = getattr(module, binding.function)
        except (ImportError, AttributeError) as error:
            raise GateLoadError(
                f"{binding.module}.{binding.function}: {error}"
            ) from error
        if not callable(validator):
            raise GateLoadError(
                f"{binding.module}.{binding.function} is not callable"
            )
        return validator
