---
name: agent-team-execution
description: Use when executing an approved implementation plan with independent tasks, multiple agents, or an explicit request to use agent team execution
---

# Agent Team Execution

Use this skill after a task is active and an approved `.cowork-flow/plans/*.md` file is in task context.

## Process

1. Run `./.cowork-flow/run agent-team prepare <task-dir> --plan <plan-file>`.
2. Review `agent-team/dispatch-plan.yaml` for unsafe parallelism, file conflicts, missing context, or weak agent matches. If the graph is unsafe, fix the plan dependencies or split assignments, then rerun `prepare`.
3. Run `./.cowork-flow/run agent-team next <task-dir>` to get ready assignments.
4. Dispatch ready assignments using the Dispatch Protocol below.
5. While workers run, coordinate: answer questions, unblock context gaps, and integrate non-conflicting results.
6. Record implementer outputs with `record-result` and reviewer outputs with `record-review`.
7. Use `retry` only after adding missing context, changing agent choice, or splitting an oversized assignment.
8. Repeat `next -> dispatch -> record` until no assignments remain.
9. Run `./.cowork-flow/run agent-team complete <task-dir>` before claiming the agent team work is done.

## Dispatch Protocol

Do not invoke `superpowers:subagent-driven-development` from this skill. Agent-team has its own persisted state machine; use Codex subagent orchestration directly and keep `agent-team` as the source of truth for ready assignments, results, reviews, retries, and completion.

### Codex Tool Dispatch

- In Codex hosts that expose real multi-agent tools, dispatch workers with `spawn_agent`, wait for all requested results with `wait_agent`, and close completed child threads with `close_agent`.
- For each ready assignment, read `agent-team/assignments/<assignment-id>.md` and use that file's body as the child `message`.
- When `agent-team/adapters/codex.json` provides `suggestedTaskName`, pass that value as the child `task_name` so the Codex App can start from a readable label instead of a raw assignment id.
- After each `spawn_agent` call returns, immediately capture the host-provided `nickname` and canonical `task_name`, then persist them with `./.cowork-flow/run agent-team record-spawn <task-dir> --assignment <id> --task-name <returned-task-name> [--nickname <returned-nickname>]`.
- `prepare` also emits `agent-team/assignments/<assignment-id>.context.json`. If a worker needs cowork-flow recovery, route it through `./.cowork-flow/run --context-file <that-file> resume` instead of plain `resume`.
- Set `agent_type` from the assignment and pass `fork_turns: none` so the worker starts as a fresh child thread instead of inheriting coordinator history.
- The child `message` must be the assignment prompt body only. Do not prepend coordinator dispatch wording such as `Spawn one ... agent`, because that wording can leak into the child thread and make it think it is the coordinator.
- Treat `recommended_agent` as the registry match and prompt source, not as the Codex spawn target unless it also names a real Codex custom agent.
- Prefer the host `nickname` for human-facing display once it is available. Do not invent your own alias when the host already returned one.
- After dispatching a ready batch, wait for all requested results, summarize each result by assignment id, then record outcomes through `agent-team`.
- Use `/agent` in interactive CLI sessions when you need to inspect, steer, stop, or close active agent threads.
- Only fall back to manual or another host-level dispatch path if the current Codex host does not expose real subagent tools.

### Subagent Evidence Gate

- Do not treat wording in the final answer as evidence that a subagent actually ran. Phrases like "worker reported" or "explorer agent result" can be produced by the parent agent without a real child thread.
- Before recording any assignment result, confirm real subagent evidence from the Codex host: visible subagent activity in the app or CLI, `/agent` showing the child thread, JSON event output whose item type shows an agent thread or agent job, or a successful `spawn_agents_on_csv` output written by child workers.
- If no subagent evidence appears, stop before `record-result` or `record-review`. Report that the Codex runtime did not expose or start subagents for this batch, include the exact dispatch prompt or command used, and keep the assignment ready for retry in a working runtime.
- In `codex exec --json` experiments, inspect the event stream. A run that only shows the parent thread plus ordinary `command_execution` items is not a successful subagent dispatch, even if the final answer claims an agent result.

### Fresh Worker Per Assignment

- Spawn one agent per ready assignment. Use the assignment's `agent_type` as the Codex spawn target; built-in Codex agent types include `default`, `worker`, and `explorer`, and project or personal custom agents may add more.
- Keep `fork_turns: none`; do not request a full-history fork for these worker dispatches.
- Spawn a fresh worker for each ready assignment. Do not reuse the main agent context as the worker context.
- Put the assignment Markdown, write boundary, and any needed task facts directly in the worker prompt body.
- Add this scene-setting to every worker prompt: it is not alone in the codebase, it must respect the listed write boundary, it must not revert other agents' edits, and it must report changed files plus exact verification commands.
- Dispatch multiple ready assignments in parallel only after confirming their write files do not overlap. If they overlap, dispatch them sequentially or repair the dependency graph.

### Worker Result Handling

- Wait for the consolidated Codex response for the requested batch before recording results.
- Treat worker statuses as follows:
  - `DONE`: inspect changed files and verification evidence, then record `done` with `record-result`.
  - `DONE_WITH_CONCERNS`: inspect the concerns before recording; retry if they affect correctness or scope.
  - `NEEDS_CONTEXT`: add the missing context to the assignment or task context, then use `retry`.
  - `BLOCKED`: decide whether to add context, choose a stronger agent, split the assignment, or stop for coordinator decision.

### Review Chain

- After an implementer is recorded, let `agent-team next` unlock that task's spec reviewer. Dispatch the reviewer as a fresh worker using its generated assignment prompt.
- If the spec reviewer rejects or flags gaps, record the review result, retry the implementer with the specific gaps, then rerun the review.
- Only after spec review is approved should the quality reviewer run. If quality review rejects, retry the implementer with the specific issues and rerun the review chain.
- Do not let implementer self-review replace `record-review` for spec or quality assignments.

## Rules

- The script suggests; the main agent decides.
- Do not parallelize assignments with overlapping write files.
- Do not skip spec review or quality review.
- In Codex, `agent-team` is coordinator-dispatched: the Python script generates assignments, and the main agent performs the real subagent dispatch calls while preserving `agent-team` state.
- Do not rely on chat history for state; write results through `agent-team` commands.
