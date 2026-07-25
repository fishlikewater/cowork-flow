---
name: review
description: Use before completing a cowork-flow task to review code, tests, specs, gate output, and completion readiness.
---

# Review

Use this Skill during the check phase, before `task complete`, or whenever a task needs a focused code review.

## Principles

- Review early enough that fixes are cheap; do not wait until archive/commit to discover blockers.
- Review the current diff and exact task context, not broad conversation memory.
- Separate machine-decidable gates from human judgment: hard gates block; review judgment explains risk and fixes.
- Prefer fresh verification from the current checkout over stale prior output.
- Do not create task-local review artifact files. The review result and command output are the evidence.

## Inputs

Read only what is needed for the current task:

1. `<task>/decision-anchor.md` and acceptance criteria.
2. The linked implementation plan, if present.
3. `<task>/check.jsonl` and each referenced file.
4. Current `git diff` / `git status --short`.
5. Relevant `.cowork-flow/spec/` files and backend/frontend quality rules for changed paths.
6. Gate output from coding standards, implementation scope, runtime rules, machine warnings, and complexity signals.

## Review Checklist

- **Scope**: every changed file is planned or justified; no unrelated cleanup sneaks in.
- **Behavior**: acceptance criteria are satisfied through observable behavior, not implementation-shaped assertions.
- **Tests**: tests fail for meaningful regressions, reject shallow existence/mock/snapshot-only checks, and cover boundary/error paths when relevant.
- **Specs**: specs are updated when behavior/contracts changed, or the review states why no spec update is needed.
- **Code quality**: naming, layering, error handling, state boundaries, security-sensitive paths, and complexity are reviewed against project specs.
- **Machine gates**: blocking gate failures are fixed before acceptance; advisory warnings are fixed or explicitly accepted with rationale.

## Severity

- `critical`: correctness, security, data loss, lifecycle bypass, or completion would be invalid. Blocks completion.
- `important`: maintainability, missing meaningful tests, spec drift, or likely future bug. Fix before completion unless explicitly accepted.
- `minor`: clarity or polish that does not invalidate completion. May be noted without blocking.

## Output

Return a concise review result with:

- `acceptanceId`: covered acceptance criteria or `overall`.
- `status`: `pass`, `needs_fix`, or `blocked`.
- `findings`: severity, file, line/scope, impact, and fix.
- `test_intent_review`: why tests prove the intended behavior or what is missing.
- `machine_gate_review`: commands/gates run, pass/fail/warn status, and warning disposition.
- `verification`: exact commands run from this checkout.
- `specUpdates`: files updated or reason no update was needed.
- `resolution`: what was fixed and what remains.

Do not claim completion from checklist intent alone; completion requires current verification output.
