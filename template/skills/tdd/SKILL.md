---
name: tdd
description: Use for TDD-required tasks (behavior_change, bugfix) to produce valid quality.json evidence before implementation. Guidance only — task review and task complete are the hard gates.
---

# TDD

Use this skill for tasks with `workType: behavior_change` or `workType: bugfix`. It guides evidence production — lifecycle state transitions (`task review`, `task complete`) enforce compliance, not this skill.

## Workflow

1. **Read the task** — PRD acceptance criteria define what the tests must prove.
2. **Write testPlan** — one entry per acceptance point in `quality.json`:
   ```json
   {
     "workType": "behavior_change",
     "testPlan": [
       {
         "acceptancePoint": "task creation returns valid ID",
         "testCommand": "pytest tests/test_task.py::test_creates_valid_id -q",
         "breaksWhen": "function returns None or empty string instead of a UUID"
       }
     ]
   }
   ```
3. **Record red evidence** — run the tests BEFORE implementing. Record the failing output:
   ```json
   "red": {
     "command": "pytest tests/test_task.py::test_creates_valid_id -q",
     "exitCode": 1,
     "failingTests": ["test_creates_valid_id"],
     "outputExcerpt": "FAILED test_creates_valid_id - AssertionError: expected UUID, got None"
   }
   ```
   red `exitCode` **MUST NOT** be 0. No passing red phase is valid evidence.
4. **Implement** — write the minimum code to make the test pass.
5. **Record green evidence** — run the same command family again:
   ```json
   "green": {
     "command": "pytest tests/test_task.py::test_creates_valid_id -q",
     "exitCode": 0,
     "passingTests": ["test_creates_valid_id"],
     "outputExcerpt": "1 passed in 0.05s"
   }
   ```

## Shallow Tests Rejected

These tests do not prove behavior and will be blocked by lifecycle gates:

- `assert True` / `self.assertTrue(True)` / `expect(true).toBe(true)`
- Empty snapshots or snapshots with no assertions.
- Existence-only tests: `def test_exists(): pass`
- Mock-call-only tests that assert a mock was called without asserting observable behavior.
- Implementation-mirroring assertions that copy the production code verbatim.

Write tests that fail when the **business behavior** breaks — not tests that re-state the implementation.

## Constraints

- This skill is **guidance only**. `task review` and `task complete` enforce evidence requirements.
- Evidence must be recorded as **command output**, not free-text claims.
- For `refactor_no_behavior_change`: record the existing tests that verify current behavior in `testPlan`. Red-first is not required.
- For `docs_chore`: TDD evidence is not required. `standards` and `check` evidence are still required at completion.
