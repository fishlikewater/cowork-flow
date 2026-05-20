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
4. In Codex, dispatch the ready assignments to the recommended agent types. Tell each worker it is not alone in the codebase, must respect the write boundary, must not revert others' edits, and must list changed files.
5. While workers run, coordinate: answer questions, unblock context gaps, and integrate non-conflicting results.
6. Record outputs with `record-result` and reviews with `record-review`.
7. Use `retry` only after adding missing context, changing agent choice, or splitting an oversized assignment.
8. Run `complete` before claiming the agent team work is done.

## Rules

- The script suggests; the main agent decides.
- Do not parallelize assignments with overlapping write files.
- Do not skip spec review or quality review.
- Do not rely on chat history for state; write results through `agent-team` commands.
