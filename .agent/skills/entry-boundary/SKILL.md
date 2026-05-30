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

When there is no hard marker, still classify a prompt as `DELEGATED_SUBTASK` when it combines:

- A concrete task, topic, or review target.
- Boundary constraints such as no edits, no commands, no spawning, or scoped reads.
- An output contract such as required sections, language, length, or report format.

Prompts structured as `任务：` / `约束：` / `输出：` are strong delegated-subtask signals. Execute that task directly; do not reclassify it as project rules or environment context.

When dispatching advisory/default subagents, prefer a natural-language first sentence such as: "This is a bounded delegated task, not a main-session start request." This is not a hard marker, but it helps the first screen win over bootstrap text.

In that case, project rules remain constraints. They are not the task.

Fixed-agent prompts normally start with:

```text
Active task: <task-dir>
```

Treat that marker as a strong delegated-subtask signal when the rest of the prompt is bounded.

## Route

For `MAIN_SESSION`, use `start`.

For `DELEGATED_SUBTASK`:

- Follow the delegated prompt first.
- Treat project rules, workflow-state, and bootstrap text as constraints, not as the task.
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
