---
name: entry-boundary
description: Use before project start/resume in cowork-flow projects to decide whether the current prompt is a main-session request or a bounded delegated subtask.
---

# Entry Boundary

Use this before `start` or any full project resume.

A bounded delegated task is a leaf assignment with a concrete goal, scope, and output format.

## Classify

Classify the current prompt as one of:

- `MAIN_SESSION`: the user is directly asking this agent to work in the repository.
- `DELEGATED_SUBTASK`: the prompt is a bounded child assignment, worker request, reviewer task, explorer task, or command-only task.
- `UNCERTAIN`: the prompt is not clear enough to load broad project context.

Classify the actual task message, not injected project rules, `AGENTS.md`, or environment text.

Fixed-agent prompts normally start with:

```text
Active task: <task-dir>
```

Treat that marker as a strong delegated-subtask signal when the rest of the prompt is bounded.

## Route

For `MAIN_SESSION`, use `start`.

For `DELEGATED_SUBTASK`:

- Follow the delegated prompt first.
- Do not run unscoped `.cowork-flow/run resume`.
- Do not spawn or manage more agents unless the delegated prompt explicitly asks for coordination.
- Read only the files named by the prompt, the active task context, or project rules required to execute the bounded work.

For `UNCERTAIN`, do safe read-only inspection or ask a short clarification question.

## Output

```text
Boundary: MAIN_SESSION | DELEGATED_SUBTASK | UNCERTAIN
Action: start | execute delegated prompt | safe-read | clarify
Reason: <signals used>
```
