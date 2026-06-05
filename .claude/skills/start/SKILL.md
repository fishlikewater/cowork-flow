---
name: start
description: Use when starting or resuming main-session work in a cowork-flow project, after context compression, or before repository changes.
---

# Start

This skill is for the main session only. Formal subagents are accepted only after runtime context binding is recorded and must not load this startup flow.
Main repository changes follow `Plan -> Implement -> Check -> Finish`.
Before loading state, classify only whether the current request is a
main-session request, read-only question, command-only wrapper, or unclear
input. Do not infer subagent identity from prompt shape. If a child has
`cowork_runtime_context_id`, hook/plugin binding may run early; otherwise the
child must run the explicit shim bind before formal work.

## Load State

1. Read `AGENTS.md`.
2. Read `.cowork-flow/workflow.md`.
3. Read `.cowork-flow/config.yaml` for Codex dispatch hints and lifecycle hooks.
4. Run `.cowork-flow/run resume` or `.\.cowork-flow\run.cmd resume` on Windows.
5. Read the active task PRD and JSONL indexes only when a task is active.
6. Read relevant `.cowork-flow/spec/*/index.md` files before code changes.

Report active task, workflow state, blockers, and the next phase.

## Route

Route in stages. Before state is loaded, true question-only requests may bypass
Load State. Repository-changing main-session requests load state first. After
state is loaded, apply the requirement clarification gate from
`.cowork-flow/workflow.md`, then route to the next workflow phase; clear
multi-step implementation uses `writing-plans` before fixed-agent dispatch.

New requirements that are unclear, boundary-unclear, multi-approach, behavior-changing, or missing acceptance criteria use `brainstorming` before PRD, planning, or fixed-agent dispatch. Small repository changes proceed directly only when the goal, scope boundary, and acceptance criteria are already clear.

- Question-only work: answer directly.
- Small repository change with clear goal/scope/acceptance: classify by `.cowork-flow/workflow.md`, create/start a task if required, then proceed.
- Unclear, boundary-unclear, behavior-changing, or multi-approach work: use `brainstorming`.
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

- Research: dispatch `cowork-research` through the active Host Adapter.
- Implementation: dispatch `cowork-implement` through the active Host Adapter.
- Verification: dispatch `cowork-check` through the active Host Adapter.

Every formal dispatch uses runtime-context dispatch:

```text
cowork_runtime_context_id: <runtime_context_id>
cowork_host_context_key: <host_context_key>
```

Before spawning a formal child, create a runtime context with
`.cowork-flow/run subagent init` and pass the returned prompt transport through
the active Host Adapter. The child's first step is
`.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>`; if a
hook/plugin already bound the same key, this command is idempotent. The parent
must verify `status=bound` and `bound_context_key=<host_context_key>` before
accepting output. If binding is missing, closed, invalid, or mismatched, the
child fails closed and must not run start/resume/task activation/archive/commit
or coordinate other agents.

After dispatch, use adapter wait/list/cancel primitives, review the output,
verify deliverables, and close the runtime context with
`.cowork-flow/run subagent close <runtime_context_id>`.
