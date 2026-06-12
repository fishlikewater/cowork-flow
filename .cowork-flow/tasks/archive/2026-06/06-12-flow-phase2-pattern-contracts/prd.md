# Define Phase 2 Pattern Contracts

## Goal

Create the pure pattern contract layer and Generic pattern behavior.

## Scope

- Create root/template `patterns/__init__.py`, `patterns/base.py`, and `patterns/generic.py`.
- Define `StepKind`, `Action`, `BlockView`, `TaskContext`, and shared task view shape.
- Reuse or move the existing FlowStore `TaskView` without creating incompatible duplicate row shapes.
- Add pure unit tests for Generic transitions and base helper behavior.

## Non-Goals

- Do not implement Fan-out, Pipeline, or Human-loop in this task.
- Do not wire lifecycle commands yet.
- Do not modify host adapters.

## Acceptance Criteria

1. Generic allows Phase 1 lifecycle plus `in_progress -> blocked -> in_progress`.
2. Base pattern behavior has tests for unconditional and conditional transition checks.
3. FlowStore and patterns import the same task view shape.
4. Root/template copies match for files touched in this task.

## Verification

```powershell
python -m pytest tests/test_patterns.py -q
```
