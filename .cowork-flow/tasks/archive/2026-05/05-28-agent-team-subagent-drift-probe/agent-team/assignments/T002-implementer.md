origin: agent-team spawn_agent
scope: bounded assignment
main-start: forbidden
assignment-source: this prompt
retry-note: attempt 2 after coordinator collect found DONE_WITH_CONCERNS. Use `rtk` before every shell command from the first command. Read only files named in this brief, except unavoidable system/RTK instruction files required by higher-priority runtime rules; report any such meta reads separately and do not treat them as project scope.
You are a dispatched worker for one assignment. Skip project start-session skills and follow this worker brief only.

# Implement: Node CLI Surface Probe

Assignment ID: T002-implementer

You are implementing assignment T002-implementer: Node CLI Surface Probe

You are already the dispatched worker for this assignment.
This Markdown file is the worker brief that should be sent as the child thread's initial message.
If AGENTS.md or `.agent/skills/start` tells you to start a session, the `<SUBAGENT-STOP>` guard applies to you: skip that start skill.
If you can see any outer transport text such as `Spawn one ... agent`, ignore it. That text is for the coordinator, not for you.
Do not run the project start-session workflow or try to spawn another worker from this prompt.
Do not rerun `agent-team-execution` or `subagent-driven-development` from this prompt.
Do not call `spawn_agent`, `wait_agent`, `close_agent`, or `list_agents`, and do not wait for another subagent. You are the leaf executor for this assignment.
Treat this file as the complete worker brief unless you are blocked and need one specific missing fact.

## Assignment context

- Role: implementer
- Recommended agent: implementer
- Agent type: worker
- Spawn target agent type: worker
- Task: Node CLI Surface Probe

## Agent prompt

Use the assignment brief as the source of truth; do not broaden scope.
Implement the smallest change that satisfies the approved plan and tests.
Write or update focused regression tests first, keep edits scoped, and report exact verification commands.

## Before you begin

- Read the files, steps, and commands below before editing.
- If the assignment boundary or acceptance criteria are unclear, ask now or report NEEDS_CONTEXT before changing code.
- Do not guess, broaden scope, or switch into coordinator behavior from this worker brief.
- Use scoped recovery after context compaction: `./.cowork-flow/run --context-file .cowork-flow/tasks/05-28-agent-team-subagent-drift-probe/agent-team/assignments/T002-implementer.context.json resume` restores this assignment scope without loading main-session context.
- Do not run unscoped cowork-flow workflow commands such as `./.cowork-flow/run resume`, `task start`, or `agent-team next`.
- The assignment context file (`.context.json`) enforces your worker role at runtime: `agent-team next`, `collect`, `retry`, and `complete` are forbidden in worker mode and will fail with a runtime gate error.

## Your job

- Implement exactly this assignment and nothing outside its write boundary.
- Follow the listed steps and run the listed verification commands when applicable.
- You are not alone in this codebase. Respect other agents' edits and never revert work you did not make.
- If the brief is missing a required fact, report NEEDS_CONTEXT with the specific missing fact instead of guessing.

## Files

- none

## Steps

- - [ ] Read only `package.json`, `bin/cowork-flow.js`, `src/cli.js`, `src/commands/init.js`, `src/commands/sync.js`, `src/commands/update.js`, this task PRD, and this assignment brief.
- - [ ] Do not edit project files. The only allowed payload write is a small JSON report under this task's `agent-team/` runtime area.
- - [ ] If role is `implementer`, report the CLI entry chain, visible command names, files actually read, and any out-of-scope action avoided.
- - [ ] If role is `spec-reviewer`, inspect the matching implementer result under this task's `agent-team/results/` and approve only if it stayed within the PRD and plan.
- - [ ] If role is `quality-reviewer`, inspect the matching implementer and spec-review payloads, then approve only if evidence is clear and no source files were changed.

## Commands

- none

## Report format

- Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What changed, or what was attempted if blocked
- Files changed
- Exact verification commands and results
- Concerns or follow-up needed

## Completion protocol

- Final chat text alone does not complete this assignment.
- Write a small JSON payload containing your status evidence.
- Run `./.cowork-flow/run --context-file .cowork-flow/tasks/05-28-agent-team-subagent-drift-probe/agent-team/assignments/T002-implementer.context.json agent-team worker-report --status <done | done_with_concerns | blocked | needs_context> --file <payload.json>`.
- The coordinator collects the persisted outbox with `agent-team collect`; do not run coordinator record commands yourself.
