# Phase 1 Shared Quality Gate Kernel

## Goal

Create the shared quality gate kernel used by lifecycle commands, doctor checks, and tests.

## Files

- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_quality_gate.py`
- `.cowork-flow/plans/2026-06-23-lifecycle-tdd-quality-gates.md`

## Acceptance Criteria

- `GateResult` records `ok`, `errors`, and `warnings`.
- `load_quality_evidence(task_dir)` reads `quality.json` with explicit UTF-8.
- `validate_tdd_evidence(task_dir)` validates `testPlan`, `red`, and `green`.
- `validate_completion_evidence(task_dir)` validates final check evidence.
- Tests fail when `behavior_change` lacks red evidence, red evidence exits `0`, or green evidence does not match the red command family.

## Verification

Run:

```bash
rtk python -m pytest tests/test_quality_gate.py -q
```
