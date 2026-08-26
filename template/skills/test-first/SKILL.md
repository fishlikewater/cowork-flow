---
name: test-first
description: Use when implementing behavior changes with red-green-refactor discipline. Guides test-first development without creating workflow evidence artifacts or lifecycle gates.
---

# Test First

Use this Skill to practice test-first implementation inside the active cowork-flow task. This Skill does not start, review, complete, archive, dispatch, route tasks, or require JSONL evidence records; use `cowork-flow` for lifecycle state.

## Trigger

Use for behavior, state, protocol, CLI, data-format, permission, or error-handling changes. Behavior changes default to a red test before implementation: first pin the expected behavior with the smallest meaningful failing test, then make the minimum code change needed to turn it green.

For docs/comment/format-only work, skip TDD and run the smallest relevant verification command.

## Red test before implementation

Do not modify production code before the red test for a behavior change unless a documented exception applies. The normal path is:

1. Map the behavior to a `decision-anchor.md` acceptance ID when one exists.
2. Write the smallest meaningful test that fails because the target behavior is missing or wrong.
3. Run the test and confirm the red failure is about target behavior, not setup/import/environment noise.
4. Implement the minimum change.
5. Run the same test to green, then run directly dependent tests.
6. Refactor only after the behavior is pinned green.

Tests added after implementation are regression tests, not evidence that a red-green cycle happened. They may still be useful, but do not describe them as test-first work unless the red failure was observed before the implementation change.

## Exceptions

If red-first is skipped, state the reason before or with the implementation summary and name the substitute verification. Acceptable reasons are limited to:

- docs/comment/format-only changes where no behavior changes.
- an existing precise failing test already reproduces the target behavior.
- the behavior cannot be reproduced locally after a focused attempt; describe the attempted command and observed result.
- no usable test entry point exists; explain the gap and use the narrowest manual or static verification available.

## Output

Do not write TDD evidence objects to `check.jsonl`, do not create `tdd.jsonl`, and do not create TDD exemption records. Report the exact red/green commands in the agent response or task review narrative when useful; the workflow does not validate them as separate evidence artifacts.

## Anti-Rationalization

Do not use these excuses to skip meaningful behavior tests:

| Excuse | Why It Fails | Required Alternative |
|---|---|---|
| "This logic is simple, no test needed" | Simple logic still breaks on edge cases and later edits. | Write the smallest behavior test, or state the concrete non-test verification used. |
| "Other tests already cover this" | Invisible coverage is hard to review. | Name the exact existing test command and behavior it covers. |
| "I'll add tests after implementation" | Post-implementation tests can miss the original failure mode and is not test-first. | Red first, then green; if this already happened, call the new test a regression test. |
| "It looks correct" | Visual inspection misses scenarios that tests can pin down. | Turn expected behavior and edge cases into assertions. |
| "This is internal only" | Internal behavior still affects callers and workflow state. | Test through the public entry point, or directly test the narrow internal contract. |
