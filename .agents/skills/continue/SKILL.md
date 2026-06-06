---
name: continue
description: Use when resuming an in-progress cowork-flow task after interruption, context compression, or a new session.
---

# Continue

Use this to recover the next actionable step without rereading the whole repository.

## Steps

1. Run `.cowork-flow/run resume` or `.\.cowork-flow\run.cmd resume` on Windows.
2. Run `.cowork-flow/run task current`.
3. Read the active task `prd.md`.
4. Read the current plan only if the task references one.
5. Read the relevant JSONL index for the current phase: `implement.jsonl`, `check.jsonl`, or `debug.jsonl`.
6. Inspect `git status --short` and any changed files relevant to the task.

## Output

State:

- Active task and phase.
- Completed work.
- Next step.
- Blockers.
- Verification still required.

Avoid broad archive/history scans unless the active task explicitly depends on them.
