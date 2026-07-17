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

When red/green evidence is useful or required, write one JSON object per line to `<task>/check.jsonl` with `type: "tdd"` and:

- `acceptanceId`, `testFile`, `testName`
- `redCommand`, `redExitCode`, `redOutputExcerpt`, `failureReason`
- `whyThisTestMatters`
- `greenCommand`, `greenExitCode`, `broaderVerification`

Only docs/comment/format-only work may use a documented `exemption`.

## Anti-Rationalization

The following excuses do not exempt meaningful behavior testing or required high-risk TDD evidence:

| Excuse | Why It Fails | Required Alternative |
|---|---|---|
| "This logic is simple, no test needed" | Simple logic still breaks on edge cases and later edits. | Write the smallest behavior test for the acceptance ID. |
| "Other tests already cover this" | Invisible coverage is not red-green evidence. | Point to the exact redCommand and acceptanceId in `check.jsonl`. |
| "I'll add tests after implementation" | Post-implementation tests are not a red-green cycle. | Red first, then green; record both commands. |
| "It looks correct" | Visual inspection misses scenarios that tests can pin down. | Turn the expected behavior and edge case into assertions. |
| "I've written similar tests" | Similar structure is not the same behavior. | Re-run the redCommand for this acceptanceId. |
| "This is internal only" | Internal behavior still affects callers and workflow state. | Test through the public entry point, or directly test the internal contract when that is the narrowest stable surface. |
