---
name: before-dev
description: Use before writing code in a cowork-flow project to load project-specific guidelines, active task context, and verification expectations.
---

# Before Dev

Use this immediately before code edits.

## Read

1. `AGENTS.md`
2. `.cowork-flow/workflow.md`
3. Active task `prd.md`
4. Active task `implement.jsonl`
5. Relevant `.cowork-flow/spec/*/index.md`
6. Any exact files named by the task, plan, or user

Do not bulk-load unrelated tasks, archived sessions, or every spec file.

## Confirm

State briefly:

- Assumptions.
- Success criteria.
- Files or modules likely to change.
- Verification command you expect to run.
- Whether fixed agents or inline work are appropriate.

If the task is a bounded subagent prompt, do not convert it into main-session planning.
