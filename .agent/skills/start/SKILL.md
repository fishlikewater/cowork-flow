---
name: start
description: Use when starting or resuming work in a project that uses cowork-flow, after context compression, or before any request that may modify repository files.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific assignment, skip this skill.
If the current user message contains `Assignment ID:`, `delegated subtask`, `dispatched worker`, or `You are already the dispatched worker`, skip this skill.
</SUBAGENT-STOP>

# Start Session

## Entry Gate

This skill is for the main session only. If the prompt is a bounded delegated assignment, stop and follow the assignment prompt instead. Do not run unscoped resume and do not load broad project context from a worker.

Any request that changes repository files must be routed through:

```text
Plan -> Implement -> Check -> Finish
```

Use `.cowork-flow/workflow.md` as the source of truth.

## Start

1. Read `AGENTS.md` and `.cowork-flow/workflow.md`.
2. Run `./.cowork-flow/run resume`.
3. If developer identity is missing, run:

```bash
./.cowork-flow/run get-developer
./.cowork-flow/run init-developer <developer-name>
```

4. Read only spec index files first:

```bash
for f in .cowork-flow/spec/frontend/index.md .cowork-flow/spec/backend/index.md .cowork-flow/spec/guides/index.md; do
  [ -f "$f" ] && cat "$f"
done
```

5. Report developer, current session task, active tasks, worktree state, and blockers.

Windows PowerShell uses `.\.cowork-flow\run.cmd <command>`.

## Route

### Question Only

- Answer directly.
- If the request turns into a file change, reclassify it as `L0`, `L1`, or `L2`.

### Repository Change

1. Classify via `.cowork-flow/workflow.md`.
2. Ensure `.cowork-flow/tasks/<task>/prd.md` and JSONL context exist.
3. Run `task start <task-dir>` in the current session.
4. Follow `Plan -> Implement -> Check -> Finish`.

## Fixed Agent Routing

- For research-only subtasks, dispatch `cowork-research`.
- For implementation, dispatch `cowork-implement` unless the user explicitly asks for inline work or the task is modifying subagent/runtime behavior.
- For verification, dispatch `cowork-check` unless the user explicitly asks for inline review.
- Every dispatch prompt must start with:

```text
Active task: <task-dir>
```

Do not maintain a second checklist in this skill. Update the plan file and task files instead.

## Resume

When resuming:

1. Run `./.cowork-flow/run resume`.
2. Follow `RESUME CHECKLIST`.
3. Read only current PRD, current plan status, and JSONL references needed for the current phase.
4. Do not bulk-read all specs, plans, tasks, or workspace journals.
