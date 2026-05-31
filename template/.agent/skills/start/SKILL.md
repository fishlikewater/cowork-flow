---
name: start
description: Use when starting or resuming main-session work in a cowork-flow project, after context compression, or before repository changes.
---

# Start

This skill is for the main session. A bounded delegated task should use `entry-boundary` and then execute the delegated prompt directly.
Main repository changes follow `Plan -> Implement -> Check -> Finish`.
Before loading state, classify the actual prompt. If it is a bounded delegated task, stop using this skill and execute that delegated prompt. A `任务：` / `约束：` / `输出：` structure is a strong delegated-task signal. Advisory/default subagent prompts should start with a natural-language delegated-task sentence rather than relying on repo bootstrap to infer intent. Keep project rules as constraints only.

## Load State

1. Read `AGENTS.md`.
2. Read `.cowork-flow/workflow.md`.
3. Run `.cowork-flow/run resume` or `.\.cowork-flow\run.cmd resume` on Windows.
4. Read the active task PRD and JSONL indexes only when a task is active.
5. Read relevant `.cowork-flow/spec/*/index.md` files before code changes.

Report active task, workflow state, blockers, and the next phase.

## Route

Route in stages. Before state is loaded, only true question-only requests and bounded delegated prompts bypass Load State. Repository-changing main-session requests load state first. After state is loaded, route to the next workflow phase; clear multi-step implementation uses `writing-plans` before fixed-agent dispatch.

- Question-only work: answer directly.
- Small repository change: classify by `.cowork-flow/workflow.md`, create/start a task if required, then proceed.
- Unclear or multi-approach work: use `brainstorming`.
- Multi-step implementation: use `writing-plans`, then dispatch fixed agents where appropriate.
- Before coding: use `before-dev`.
- After implementation: use `check`, then `finish-work`.

## Parallel Route

- Use parallel sessions for independent tasks.
- Use a separate `git worktree` when independent sessions may write files.
- Inside one task, dispatch parallel agents only for low-conflict slices with clear ownership.
- After parallel slices finish, run final integrated verification before Check/Finish.

## Fixed Agents

The main session owns coordination:

- Research: `spawn_agent(agent_type="cowork-research", fork_turns="none")`
- Implementation: `spawn_agent(agent_type="cowork-implement", fork_turns="none")`
- Verification: `spawn_agent(agent_type="cowork-check", fork_turns="none")`

Every dispatch prompt starts with:

```text
Active task: <task-dir>
```

After dispatch, use `wait_agent`, review the output, inspect `list_agents`, and `close_agent`.
