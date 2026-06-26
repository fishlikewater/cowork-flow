# Phase 5 Shallow Test Rejection

## Goal

Reject tests that exist only to satisfy the process and do not prove behavior.

## Files

- `.cowork-flow/scripts/common/test_quality.py`
- `template/.cowork-flow/scripts/common/test_quality.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_test_quality.py`

## Acceptance Criteria

- Scanner checks Python and JavaScript test files changed by the task.
- Scanner rejects clear shallow patterns: `assert True`, `self.assertTrue(True)`, empty snapshots, existence-only tests, and mock-call-only tests without observable behavior assertions.
- Bugfix tasks require regression input or original failure condition in test plan or test naming.
- Scanner stays conservative and does not attempt to prove every good test perfect.
- Positive tests show meaningful behavior assertions pass.

## Verification

Run:

```bash
rtk python -m pytest tests/test_test_quality.py tests/test_quality_gate.py -q
```
