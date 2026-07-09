---
name: tdd
description: Use when implementing behavior changes, bug fixes, state transitions, protocols, CLI/runtime contracts, data format changes, or error handling that can be tested before implementation.
---

# TDD

Use this before editing behavior-changing code.

## Red-Green-Refactor

1. Map the task decision-anchor.md acceptance criteria to stable IDs such as `AC-001`.
2. Write the smallest meaningful failing test first.
3. Run the red command and confirm it fails because the target behavior is missing or wrong.
4. Implement the smallest change that makes the behavior pass.
5. Run the green command and relevant broader verification.
6. Refactor only after the behavior is green.

Do not count shallow tests as TDD evidence. Tests that only import code, assert a function exists, assert `True`, count mocks without behavior, or mirror implementation details do not satisfy red-green-refactor.

## Evidence

Record TDD proof in `<task>/tdd.jsonl`. Each evidence line is one JSON object:

```json
{
  "acceptanceId": "AC-001",
  "testFile": "tests/test_example.py",
  "testName": "test_behavior",
  "redCommand": "python -m unittest tests.test_example.TestCase.test_behavior -v",
  "redExitCode": 1,
  "redOutputExcerpt": "expected failure excerpt",
  "failureReason": "target behavior was not implemented",
  "whyThisTestMatters": "explains which user-visible behavior would regress",
  "greenCommand": "python -m unittest tests.test_example.TestCase.test_behavior -v",
  "greenExitCode": 0,
  "broaderVerification": "python -m unittest tests.test_example -v"
}
```

Every evidence record must map to a decision-anchor.md `acceptanceId`. The red failure must be about the target behavior, not syntax, import, environment, fixture, or setup failure.

`testName` must resolve to the exact behavior test in `testFile`. Use one of:
`test_method`, `ClassName.test_method`, or `module.ClassName.test_method`.
Do not point evidence at a class, module, or a name that only exists in a command string.

## Exemption

Pure documentation, comment-only, or formatting-only tasks may use an exemption record instead of red/green evidence:

```json
{
  "type": "exemption",
  "acceptanceId": "AC-001",
  "exemptionType": "docs-only",
  "reason": "Only documentation wording changed; runtime behavior is untouched.",
  "verificationCommand": "git diff --check"
}
```

Do not use an exemption for runtime, CLI, protocol, state, data format, permission, or error-handling changes.

## Anti-Rationalization

> The following excuses do not exempt the TDD evidence requirement. Each has an actionable alternative.

| Agent psychology | Rebuttal | Alternative |
|---|---|---|
| "This logic is simple, no test needed" | Simple logic also breaks on edge cases and later modifications. Simplicity is not grounds to skip evidence. | Write a coverage test asserting core behavior — takes < 2 minutes |
| "Other tests already cover this" | "Already covered" cannot be verified from tdd.jsonl evidence. Invisible evidence = non-existent. | Locate the corresponding acceptanceId and redCommand directly in tdd.jsonl |
| "I'll add tests after implementation" | Post-implementation tests are not a red-green cycle — they verify implementation, not behavior. | Red first, then green; evidence stays in tdd.jsonl |
| "It looks correct to the naked eye" | Errors visible to the naked eye don't become bugs. Bugs arise from scenarios that "look correct." | Turn "looks correct" inputs into assertions; turn "unexpected inputs" into edge-case tests |
| "I've written similar tests, same pattern" | Same pattern does not mean same behavior. Each acceptanceId requires independent evidence. | Re-run redCommand for the current acceptanceId and record the output |
| "This is an internal function, not externally visible" | Internal functions are relied upon by other internal callers. Behavior changes propagate through the call chain. | Test through the public entry point that calls it, or test the internal function directly |
