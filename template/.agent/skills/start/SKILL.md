---
name: start
description: Use when starting or resuming work in a project that uses the cowork-flow template, after context compression, or before any request that may modify repository files. Initialize session context and route work into the L0/L1/L2 workflow.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific assignment, skip this skill.
If the current user message contains `Assignment ID:`, `delegated subtask`, `dispatched worker`, or `You are already the dispatched worker`, skip this skill.
</SUBAGENT-STOP>

# Start Session

## HARD ENTRY GATE

This skill may run only after `.agent/skills/entry-boundary` has allowed `MAIN_SESSION`.

Classify the actual user or delegation task message, not project bootstrap text such as AGENTS.md, environment_context, or injected instruction blocks.

If entry-boundary returned DELEGATED_SUBTASK or UNCERTAIN, stop immediately. Do not run the Start flow, do not run unscoped `./.cowork-flow/run resume`, and do not load main-session context.

If this prompt is a delegated subtask, you are the leaf executor by default. Do not call spawn_agent, wait_agent, close_agent, or list_agents, and do not wait for another subagent, unless the assignment explicitly says coordinator or asks you to manage other agents.

Do not reclassify delegated work as MAIN_SESSION inside this skill. If the prompt contains a bounded assignment (task description with specific files, steps, and a report format), the assignment prompt remains the source of truth and must use scoped recovery instead.

Use this skill as the entrypoint for cowork-flow top-level sessions.

Any request that changes repository files MUST first be classified as `L0`, `L1`, or `L2`, then follow the matching workflow in `.cowork-flow/workflow.md`.
Do not use direct-edit shortcuts unless the user explicitly tells you not to use cowork-flow for this task.

## Start

1. Read `AGENTS.md` and `.cowork-flow/workflow.md`.
2. Run `./.cowork-flow/run resume`.
3. If developer identity is missing, run:

```bash
./.cowork-flow/run get-developer
./.cowork-flow/run init-developer <developer-name>
```

4. Read only the spec index files:

```bash
for f in .cowork-flow/spec/frontend/index.md .cowork-flow/spec/backend/index.md .cowork-flow/spec/guides/index.md; do
  [ -f "$f" ] && cat "$f"
done
```

5. Report current context:
    - current developer
    - current task
    - active tasks
    - worktree state
    - anything that may affect the next step

Command examples use macOS / Linux / Git Bash / WSL syntax. In native Windows cmd or PowerShell, replace `./.cowork-flow/run <command>` with `.\.cowork-flow\run.cmd <command>`.

## Route The Request

After context is loaded, choose exactly one path.

### Question Only

Use this path when the user only wants explanation, analysis, or review, and no repository files need to change.

- Answer directly.
- If the request turns into a file change, stop and reclassify it as `L0`, `L1`, or `L2`.

### Repository Change

Use this path for any repository edit, including small docs, comments, tests, refactors, or behavior changes.

1. Classify the task using `.cowork-flow/workflow.md`:
    - `L0`: no external behavior change
    - `L1`: bounded behavior change
    - `L2`: cross-layer or important behavior change
2. Follow the matching workflow in `.cowork-flow/workflow.md`:
    - `L0`: section 6
    - `L1` / `L2`: section 7
3. Before editing files, ensure task context exists under `.cowork-flow/tasks/<task>/`.
4. Before handoff, follow workflow verification, state sync, and session recording requirements.

Do not maintain a second implementation checklist in this skill.

## Required Routing Rules

- If the task is vague, complex, or has multiple possible interpretations, use the project brainstorming flow before implementation.
- If the task changes behavior, do not skip `change -> spec -> plan`; for `L2`, do not skip `design.md`.
- If an approved plan has independent work and `.cowork-flow/config.yaml` enables agent teams, use `agent-team-execution` and finish that path with `agent-team complete`.
- If context was compressed or the task is being resumed, use the minimal recovery path below instead of bulk-reading the repo.

## Resume / Context Compression

When resuming after a long task, a new session, or context compression:

1. Run `./.cowork-flow/run resume`.
2. Follow `RESUME CHECKLIST` from `resume.py`.
3. Read only the current PRD, current plan status, and the jsonl references needed for the current phase.
4. Do not bulk-read `.cowork-flow/spec/`, all plans, all tasks, or workspace journals.
