# Phase 3 TDD Review Enforcement

## Goal

Make `task review` block behavior-changing work until valid red-phase TDD evidence exists.

## Files

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_flow_script_paths.py`

## Acceptance Criteria

- `cmd_review` calls `validate_tdd_evidence` before updating status to `review`.
- `behavior_change` and `bugfix` tasks fail review without `testPlan` and failing red evidence.
- `refactor_no_behavior_change` requires existing or characterization test evidence.
- `docs_chore` can bypass red-first TDD but still needs validation evidence.
- Failure output names the missing evidence field and next action.

## Verification

Run:

```bash
rtk python -m pytest tests/test_flow_script_paths.py tests/test_quality_gate.py -q
```
