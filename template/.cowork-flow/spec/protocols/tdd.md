# TDD Protocol

> Internal protocol loaded by `cowork-implement`; it is not a public Skill.

## Trigger

Use for behavior, state, protocol, CLI, data-format, permission, or error-handling changes.

## Red-Green-Refactor

This section is the authoritative red-green-refactor contract.

1. Map each behavior test to a `decision-anchor.md` acceptance ID.
2. Run the smallest meaningful test before implementation and confirm the failure is caused by missing behavior.
3. Implement the minimum change, rerun the same test, then run directly dependent tests.
4. Reject shallow tests that only prove imports, symbols, mocks, snapshots, or implementation details.

`testName` must identify the exact behavior test as `test_method`,
`ClassName.test_method`, or `module.ClassName.test_method`.

## Output

Write one JSON object per line to `<task>/tdd.jsonl` with:

- `acceptanceId`, `testFile`, `testName`
- `redCommand`, `redExitCode`, `redOutputExcerpt`, `failureReason`
- `whyThisTestMatters`
- `greenCommand`, `greenExitCode`, `broaderVerification`

Only docs/comment/format-only work may use a documented `exemption`.
