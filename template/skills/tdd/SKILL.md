---
name: tdd
description: Use when implementing behavior changes with red-green-refactor discipline. Guides test-first development without creating workflow evidence artifacts or lifecycle gates.
---

# TDD

Use this Skill to practice test-first implementation inside the active cowork-flow task. This Skill does not start, review, complete, archive, dispatch, route tasks, or require JSONL evidence records; use `cowork-flow` for lifecycle state.

## Trigger

Use for behavior, state, protocol, CLI, data-format, permission, or error-handling changes when a failing test is the clearest way to pin expected behavior. For docs/comment/format-only work, skip TDD and run the smallest relevant verification command.

## Red-Green-Refactor

1. Map the behavior to a `decision-anchor.md` acceptance ID when one exists.
2. Write the smallest meaningful test that fails because the target behavior is missing or wrong.
3. Run the test and confirm the red failure is about target behavior, not setup/import/environment noise.
4. Implement the minimum change.
5. Run the same test to green, then run directly dependent tests.
6. Refactor only after the behavior is pinned green.

## Output

Do not write TDD evidence objects to `check.jsonl`, do not create `tdd.jsonl`, and do not create TDD exemption records. Report the exact red/green commands in the agent response or task review narrative when useful; the workflow does not validate them as separate evidence artifacts.

## Anti-Rationalization

Do not use these excuses to skip meaningful behavior tests:

| Excuse | Why It Fails | Required Alternative |
|---|---|---|
| "This logic is simple, no test needed" | Simple logic still breaks on edge cases and later edits. | Write the smallest behavior test, or state the concrete non-test verification used. |
| "Other tests already cover this" | Invisible coverage is hard to review. | Name the exact existing test command and behavior it covers. |
| "I'll add tests after implementation" | Post-implementation tests can miss the original failure mode. | Prefer red first, then green when behavior is new or risky. |
| "It looks correct" | Visual inspection misses scenarios that tests can pin down. | Turn expected behavior and edge cases into assertions. |
| "This is internal only" | Internal behavior still affects callers and workflow state. | Test through the public entry point, or directly test the narrow internal contract. |
