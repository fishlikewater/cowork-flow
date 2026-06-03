---
name: check
description: Use after code or workflow changes to verify quality, spec compliance, tests, cross-layer contracts, and template/root consistency before finish-work.
---

# Check

Use this after implementation and before `finish-work`.

## Steps

1. Read active task PRD, plan, and `check.jsonl`.
2. Review `git diff --name-only` and `git diff`.
3. Check contracts across caller/callee, command output, persisted state, templates, and docs.
4. Confirm `.cowork-flow/spec/` is updated or explicitly unchanged.
5. Review test intent: reject shallow tests that do not fail for meaningful behavior breaks.
6. Run focused tests that would fail if the changed behavior broke.
7. Run broader validation when the change touches shared runtime, templates, packaging, or public workflow.

## Report

Return:

- Issues found and fixes made.
- Files reviewed.
- Commands run and results.
- Remaining risks.

Do not claim success from intent. Use command output and reviewed diffs as evidence.
