---
name: finish-work
description: Use when implementation and verification are complete and cowork-flow work needs final scope review, commit/archive/session recording, or handoff.
---

# Finish Work

Use this in the main session after implementation and `check` are complete.

## Gate

Before claiming completion, verify:

- Active task exists, or the work was explicitly read-only/no-task.
- `check` or equivalent final review ran.
- `git diff` was reviewed for scope.
- Relevant tests, build, lint, or focused validation ran.
- `.cowork-flow/spec/` was updated when the change created durable knowledge.
- Plan checkboxes and task status match reality.
- No unrelated dirty files are staged.

## Sequence

1. Run `git status --short`.
2. Run `git diff --check`.
3. Run focused tests and then broader project verification when appropriate.
4. Update the plan/task status.
5. If commit policy allows, stage only expected files and commit.
6. Archive completed task/change artifacts when requested or required by workflow.
7. Record the session with `.cowork-flow/run add-session` after code policy is satisfied.

If the user asks not to commit, stop before staging and report the verified state.
