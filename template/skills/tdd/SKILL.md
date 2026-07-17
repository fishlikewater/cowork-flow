---
name: tdd
description: Use when implementing behavior changes with red-green-refactor discipline. Guides test-first development and records optional or high-risk red/green evidence in check.jsonl without replacing cowork-flow routing.
---

# TDD

Use this Skill to practice test-first implementation inside the active cowork-flow task. This Skill does not start, review, complete, archive, dispatch, or route tasks; use `cowork-flow` for lifecycle state.

## Trigger

Use for behavior, state, protocol, CLI, data-format, permission, or error-handling changes. For docs/comment/format-only work, skip TDD and record the verification method in `check.jsonl`.

## Red-Green-Refactor

1. Map the behavior to a `decision-anchor.md` acceptance ID.
2. Write the smallest meaningful test that fails because the target behavior is missing or wrong.
3. Run the test and confirm the red failure is about target behavior, not setup/import/environment noise.
4. Implement the minimum change.
5. Run the same test to green, then run directly dependent tests.
6. Refactor only after the behavior is pinned green.

## Evidence

For ordinary behavior changes, recording red/green evidence is recommended when it helps review but is not a separate artifact requirement. For high-risk changes such as protocol, state-machine, permission, security, migration, public-contract, or file-format changes, record a `type: "tdd"` object in `<task>/check.jsonl` with:

- `acceptanceId`, `testFile`, `testName`
- `redCommand`, `redExitCode`, `redOutputExcerpt`, `failureReason`
- `whyThisTestMatters`
- `greenCommand`, `greenExitCode`, `broaderVerification`

Only docs/comment/format-only work may use a documented `type: "tdd_exemption"` record in `check.jsonl`.

## Anti-Rationalization

Do not use these excuses to skip meaningful behavior tests:

| Excuse | Why It Fails | Required Alternative |
|---|---|---|
| "This logic is simple, no test needed" | Simple logic still breaks on edge cases and later edits. | Write the smallest behavior test for the acceptance ID. |
| "Other tests already cover this" | Invisible coverage is not red-green evidence. | Point to the exact test command and acceptance ID in `check.jsonl`. |
| "I'll add tests after implementation" | Post-implementation tests are not a red-green cycle. | Red first, then green; record both commands when evidence is required. |
| "It looks correct" | Visual inspection misses scenarios that tests can pin down. | Turn expected behavior and edge cases into assertions. |
| "This is internal only" | Internal behavior still affects callers and workflow state. | Test through the public entry point, or directly test the narrow internal contract. |
