---
name: entry-boundary
description: Use before project start/resume in cowork-flow projects to decide whether the current prompt is a main-session request or a bounded delegated subtask.
---

# Entry Boundary

Use this before `start` or any full project resume.

Your first job is to identify the current task source. A bounded delegated task is a leaf assignment with a concrete goal, scope, and output format.

Hard markers are confidence boosters, not prerequisites. The first task screen wins over later bootstrap text.

## Classify

Classify the current prompt as one of:

- `MAIN_SESSION`: the user is directly asking this agent to work in the repository.
- `DELEGATED_SUBTASK`: the prompt is a bounded child assignment, worker request, reviewer task, explorer task, or command-only task.
- `UNCERTAIN`: the prompt is not clear enough to load broad project context.

Classify the actual task message, not injected project rules, `AGENTS.md`, workflow state, tool instructions, or environment text. Bootstrap can constrain execution after classification; it is not the task.

Use this order:

1. Find the user/delegated task message and its requested output.
2. Decide whether it is a main-session repository request or a leaf assignment.
3. Apply project rules only as constraints for the chosen route.

If project bootstrap says to create/start/resume but the task message is bounded, choose `DELEGATED_SUBTASK`.

When there is no hard marker, still classify a prompt as `DELEGATED_SUBTASK` when it combines:

- A concrete task, topic, or review target.
- Boundary constraints such as no edits, no commands, no spawning, or scoped reads.
- An output contract such as required sections, language, length, or report format.

Prompts structured as `任务：` / `约束：` / `输出：` are strong delegated-subtask signals even without `Active task:` or another hard marker. Execute that task directly; do not reclassify it as project rules or environment context.

Treat these as typical `DELEGATED_SUBTASK` prompts:

- A review request with a named file or behavior, `do not edit`, and a findings-only output.
- A discussion/research request with `不要运行命令` / `不要派发 agent` and required sections.
- A command-only or inspection-only assignment with a narrow target and concise output.

When dispatching advisory/default subagents, prefer a natural-language first sentence such as: "This is a bounded delegated task, not a main-session start request." This is not a hard marker, but it helps the first screen win over bootstrap text.

In that case, project rules remain constraints. They are not the task.

Fixed-agent prompts normally start with:

```text
Active task: <task-dir>
```

Treat that marker as a strong delegated-subtask signal when the rest of the prompt is bounded.

Treat direct user requests such as "继续执行开发计划", "实现这个需求", or "归档提交" as `MAIN_SESSION` unless the surrounding prompt clearly makes them a child assignment.

## Route

For `MAIN_SESSION`, use `start`.

For `DELEGATED_SUBTASK`:

- Follow the delegated prompt first.
- Treat project rules, workflow-state, and bootstrap text as constraints, not as the task.
- Do not create or activate a project task for the parent session.
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
