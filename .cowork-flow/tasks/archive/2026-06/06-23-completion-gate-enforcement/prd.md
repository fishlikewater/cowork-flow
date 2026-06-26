# Phase 4 Completion Gate Enforcement

## Goal

Make `task complete` require green TDD evidence, coding-standard evidence, and check evidence before marking a task completed.

## Files

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_flow_script_paths.py`
- `tests/test_quality_gate.py`

## Acceptance Criteria

- `cmd_complete` calls `validate_completion_evidence` before updating status to `completed`.
- Green evidence must match the red command family.
- Completion fails when green evidence, standards evidence, or check evidence is missing.
- Pattern transition validation remains but is not the only completion gate.
- Failure output is actionable and names the missing or failed evidence.

## Verification

Run:

```bash
rtk python -m pytest tests/test_flow_script_paths.py tests/test_quality_gate.py -q
```
