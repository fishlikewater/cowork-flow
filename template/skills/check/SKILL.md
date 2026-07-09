---
name: check
description: Use after code or workflow changes to verify quality, spec compliance, tests, cross-layer contracts, and template/root consistency before finish-work.
---

# Check

Use this after implementation and before `finish-work`.

## Step 0: Anti-Rationalization Gate

Before starting the formal check, self-examine with the following questions:

- "Am I skipping a step because it feels simple?" → Simple still requires evidence
- "Am I lowering the bar because of time pressure?" → Time pressure is a red flag, not an excuse
- "Am I using 'looks right' instead of 'verifiably correct'?" → Command output is the evidence
- "Am I batch-skipping steps because 'they're all the same'?" → Each step has an independent purpose

If any answer is "yes," return to the start of the current step and re-execute in a verifiable manner.

## Steps

1. Read active task decision-anchor.md, plan, and `check.jsonl`.
2. Review `git diff --name-only` and `git diff`.
3. Check contracts across caller/callee, command output, persisted state, templates, and docs.
4. Verify spec compliance:
   - Read each spec file listed in `check.jsonl`.
   - For each guideline in the spec, check the diff for violations (naming, structure, encoding, error handling, quality gates).
   - Spec files not listed in `check.jsonl` do not apply to this check.
5. Confirm `.cowork-flow/spec/` is updated or explicitly unchanged.
6. Review test intent: reject shallow tests that do not fail for meaningful behavior breaks.
7. Run focused tests that would fail if the changed behavior broke.
8. Run broader validation when the change touches shared runtime, templates, packaging, or public workflow.
9. Report `test_intent_review` with the key tests that defend decision-anchor.md acceptance behavior.
10. Report spec compliance: for each spec/ file checked, state pass/fail with evidence from the diff.

## Report

Return:

- Issues found and fixes made.
- Files reviewed.
- Commands run and results.
- Remaining risks.

Do not claim success from intent. Use command output and reviewed diffs as evidence.

## Debug Quality Check

- Root cause fix has a corresponding regression test (not a symptom fix)
- Not a symptom fix (fixed UI-level duplication instead of API-level duplication)
- Evidence recorded in `<task>/debug.jsonl` (if applicable)
- If a repeatedly triggered bug, break-loop record is in `<task>/break-loop.md`

## Simplification Review (run when code changes exceed 50 lines or review finds readability issues)

### Pre-Simplification Self-Check (Chesterton's Fence)

For each simplification, answer:
- What is this code's responsibility? Who calls it? What does it call?
- Will existing tests' defined behavior be broken?
- Why did the original author write it this way? (check git blame)
If you cannot answer, stop — you do not understand this code.

### Simplification Signals

| Signal | Action |
|---|---|
| Nesting depth >= 3 levels | Extract guard clause or helper |
| Function > 50 lines | Split by responsibility into multiple named functions |
| Nested ternary `a ? b : c ? d : e` | Replace with if/else / switch / lookup |
| Boolean flag arguments `doThing(true, false, true)` | Replace with options object or split into two functions |
| Same condition checked >= 3 times | Extract as a named predicate function |
| Redundant wrapper `async () => await foo()` | Export foo directly |
| Unused import / variable | Remove (after confirming no side effects) |
| Missing type hint (when project convention requires it) | Add it |

### Naming Readability Signals

| Signal | Action |
|---|---|
| `data`, `result`, `temp`, `val` | Rename to describe content: `userProfile`, `errors` |
| Abbreviations `usr`, `cfg`, `btn`, `evt` | Use full words (`id`, `url`, `api` are exceptions) |
| Name contradicts behavior (`get` but mutates) | Rename to reflect actual behavior |
| "What" comment (`// increment counter` on `count++`) | Remove comment |
| "Why" comment (`// Retry because API is flaky`) | Keep |

### Rule of 500

If a refactoring would modify > 500 lines, use automated tools (sed/codemod/AST transform) rather than manual editing — manual large-scale changes are error-prone and cause review fatigue.

### Red Flags

- Simplification causes test failures (behavior was changed — violates "preserve behavior" principle)
- "Simplification" results in longer and harder-to-read code
- Renaming based on personal preference rather than project convention
- Removing error handling "to make the code cleaner"
- Batching multiple simplifications into one non-rollbackable large commit
