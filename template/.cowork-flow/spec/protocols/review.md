# Review Protocol

> Internal protocol loaded by `cowork-check`; it is not a public Skill.

## Contract

1. Read the task decision anchor, plan, `check.jsonl`, registered context, and current diff.
2. Review behavior, caller/callee contracts, persisted state, templates, specs, and scope.
3. Review test intent, reject shallow tests, run focused tests that fail for meaningful behavior breaks, then broader validation for shared runtime changes.
4. Verify `quality-review.jsonl` covers quality checklist, machine warning, and Definition of Done evidence.
5. Reject shallow tests and unresolved blockers; fix only in-scope issues.

## Output

Report the same core fields on every Host:

- `acceptanceId`
- `status`
- `findings`
- `test_intent_review`
- `verification`
- `quality_review`
- `resolution`

Do not claim completion from intent or unexecuted commands.

## Quality Evidence

`quality-review.jsonl` is the task-local audit trail for quality review. Each
record must include `id`, `source`, `type`, `status`, `files`, `evidence`, and
`verification`.

- `source`: a spec/checklist path or machine warning rule ID.
- `type`: `checklist`, `machine_warning`, or `dod`.
- `status`: `pass`, `fail`, `not_applicable`, or `acknowledged_warning`.
- `evidence`: concrete file/rule reasoning, not generic "checked" claims.
- `verification`: exact commands run or an explicit reason a command was not applicable.

Backend/frontend natural-language markdown supplies review checklist context,
not dynamic hard validators. Deterministic hard gates cover machine-decidable
checks; machine warning output must be fixed or acknowledged in
`quality-review.jsonl` before completion.

## Simplification Review

When a change exceeds 50 lines or readability is a finding:

- understand the code responsibility, callers, callees, and protected behavior before editing;
- prefer guard clauses and responsibility-based helpers for deep nesting or long functions;
- remove unused code only after confirming it has no side effects;
- keep project naming conventions and explanatory `why` comments;
- use a mechanical transform for changes above 500 lines;
- reject any simplification that changes behavior or removes error handling.
