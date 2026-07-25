# Review Protocol

> Internal protocol loaded by `cowork-check`; public guidance is mirrored in the `review` Skill.

## Contract

1. Read the task decision anchor, plan, `check.jsonl`, registered context, and current diff.
2. Review behavior, caller/callee contracts, persisted state, templates, specs, and scope.
3. Review test intent: reject shallow tests, prefer checks that fail for meaningful behavior breaks, then run focused and broader validation as risk requires.
4. Run or inspect deterministic gates for machine-decidable checks; treat blocking gate failures as unresolved findings.
5. Review machine warning output as advisory signal: fix real issues or explicitly report an accepted warning with rationale in the review result.
6. Reject unresolved blockers; fix only in-scope issues.

## Output

Report the same core fields on every Host:

- `acceptanceId`
- `status`
- `findings`
- `test_intent_review`
- `verification`
- `machine_gate_review`
- `resolution`

Do not claim completion from intent, memory, or unexecuted commands. Completion requires fresh verification output from the current diff.

## Review Evidence

Review evidence lives in the checker response and command output, not in a task-local evidence file. Keep it concrete:

- cite exact changed files, affected contracts, and acceptance criteria;
- include exact commands run and whether they passed, failed, or were not applicable with reason;
- classify findings as `critical`, `important`, or `minor`;
- distinguish blocking failures from advisory machine warnings;
- state whether specs were updated or explicitly not needed.

Backend/frontend natural-language markdown supplies review checklist context, not dynamic hard validators. Deterministic hard gates cover machine-decidable checks.

## Simplification Review

When a change exceeds 50 lines or readability is a finding:

- understand the code responsibility, callers, callees, and protected behavior before editing;
- prefer guard clauses and responsibility-based helpers for deep nesting or long functions;
- remove unused code only after confirming it has no side effects;
- keep project naming conventions and explanatory `why` comments;
- use a mechanical transform for changes above 500 lines;
- reject any simplification that changes behavior or removes error handling.
