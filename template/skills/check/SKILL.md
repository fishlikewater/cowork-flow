---
name: check
description: Use after code or workflow changes to verify quality, spec compliance, tests, cross-layer contracts, and template/root consistency before finish-work.
---

# Check

Use this after implementation and before `finish-work`.

Apply ERROR_OUTPUT_AS_DATA contract. If tempted to skip steps, re-execute with verifiable evidence.

## Steps

1. Read active task decision-anchor.md, plan, and `check.jsonl`.
2. Review `git diff --name-only` and `git diff`.
3. Check contracts across caller/callee, command output, persisted state, templates, and docs.
4. Verify spec compliance:
   - Read each spec file listed in `check.jsonl`.
   - For each guideline in the spec, check the diff for violations (naming, structure, encoding, error handling, quality gates).
   - Spec files not listed in `check.jsonl` do not apply to this check.
5. Verify all new/modified code against project coding standards:
   - For every source file added or changed in the diff, determine whether it is backend or frontend.
   - Read the matching index (`.cowork-flow/spec/backend/index.md` or `.cowork-flow/spec/frontend/index.md`) to discover which guideline files apply.
   - Read each applicable guideline file and cross-check the changed code for violations (UTF-8 enforcement, directory structure, error handling, layering, component patterns, etc.).
   - Report each violation with: file path, violated rule, and a one-line fix suggestion.
6. Confirm `.cowork-flow/spec/` is updated or explicitly unchanged.
7. Review test intent: reject shallow tests that do not fail for meaningful behavior breaks.
8. Run focused tests that would fail if the changed behavior broke.
9. Run broader validation when the change touches shared runtime, templates, packaging, or public workflow.
10. Report `test_intent_review` with the key tests that defend decision-anchor.md acceptance behavior.
11. Report spec compliance: for each spec/ file checked, state pass/fail with evidence from the diff.

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

## Simplification Review

See [simplification-guide.md](./simplification-guide.md) when refactoring > 50 lines.
