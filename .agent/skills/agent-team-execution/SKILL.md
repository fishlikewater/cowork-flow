---
name: agent-team-execution
description: Use when executing an approved implementation plan with independent tasks, multiple agents, or an explicit request to use agent team execution
---

# Agent Team Execution

Use this skill after a task is active and an approved `.cowork-flow/plans/*.md` file is in task context.

## Process

1. Run `./.cowork-flow/run agent-team prepare <task-dir> --plan <plan-file>`.
2. Review `agent-team/dispatch-plan.yaml` for unsafe parallelism, file conflicts, missing context, or weak agent matches.
3. Run `./.cowork-flow/run agent-team next <task-dir>` to get ready assignments.
4. In Codex with `[features] multi_agent = true`, dispatch each ready assignment with `spawn_agent` using the generated `agent-team/assignments/<assignment-id>.md` prompt content. Dispatch multiple ready assignments in parallel only after confirming their write files do not overlap.
5. Collect each spawned worker result with `wait_agent`, then call `close_agent` to free the worker slot. Tell each worker it is not alone in the codebase, must respect the write boundary, must not revert others' edits, and must list changed files.
6. Only fall back to manual prompt execution when the current host does not expose `spawn_agent`, `wait_agent`, or `close_agent`. Do not use manual execution merely because the assignment is stored as Markdown.
7. While workers run, coordinate: answer questions, unblock context gaps, and integrate non-conflicting results.
8. Record outputs with `record-result` and reviews with `record-review`.
9. Use `retry` only after adding missing context, changing agent choice, or splitting an oversized assignment.
10. Run `complete` before claiming the agent team work is done.

## Rules

- The script suggests; the main agent decides.
- Do not parallelize assignments with overlapping write files.
- Do not skip spec review or quality review.
- In Codex, `agent-team` is coordinator-dispatched: the Python script generates assignments, and the main agent performs the real `spawn_agent` / `wait_agent` / `close_agent` calls.
- Do not rely on chat history for state; write results through `agent-team` commands.
