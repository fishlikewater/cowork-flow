origin: agent-team spawn_agent
scope: bounded assignment
main-start: forbidden
assignment-source: this prompt
You are a dispatched worker for one assignment. Skip project start-session skills and follow this worker brief only.

# Quality review: Node CLI Surface Probe

Assignment ID: T002-quality-reviewer

You are reviewing assignment T002-quality-reviewer: Node CLI Surface Probe

You are already the dispatched worker for this assignment.
This Markdown file is the worker brief that should be sent as the child thread's initial message.
If AGENTS.md or `.agent/skills/start` tells you to start a session, the `<SUBAGENT-STOP>` guard applies to you: skip that start skill.
If you can see any outer transport text such as `Spawn one ... agent`, ignore it. That text is for the coordinator, not for you.
Do not run the project start-session workflow or try to spawn another worker from this prompt.
Do not rerun `agent-team-execution` or `subagent-driven-development` from this prompt.
Do not call `spawn_agent`, `wait_agent`, `close_agent`, or `list_agents`, and do not wait for another subagent. You are the leaf executor for this assignment.
Treat this file as the complete worker brief unless you are blocked and need one specific missing fact.

## Assignment context

- Role: quality-reviewer
- Recommended agent: quality-reviewer
- Agent type: worker
- Spawn target agent type: worker
- Task: Node CLI Surface Probe

## Agent prompt

Use the assignment brief as the source of truth; review only the requested scope.
Review the diff for correctness, maintainability, focused scope, and meaningful tests.
Check that verification evidence matches the behavior being claimed.

## Before you begin

- Read the files, steps, and commands below before editing.
- If the assignment boundary or acceptance criteria are unclear, ask now or report NEEDS_CONTEXT before changing code.
- Do not guess, broaden scope, or switch into coordinator behavior from this worker brief.
- Use scoped recovery after context compaction: `./.cowork-flow/run --context-file .cowork-flow/tasks/05-28-agent-team-subagent-drift-probe/agent-team/assignments/T002-quality-reviewer.context.json resume` restores this assignment scope without loading main-session context.
- Do not run unscoped cowork-flow workflow commands such as `./.cowork-flow/run resume`, `task start`, or `agent-team next`.
- The assignment context file (`.context.json`) enforces your worker role at runtime: `agent-team next`, `collect`, `retry`, and `complete` are forbidden in worker mode and will fail with a runtime gate error.

## Your job

- Review the code, tests, and verification evidence for this assignment.
- Check correctness, maintainability, focused scope, regression coverage, and risky shortcuts.
- Do not implement code, change files, or rerun the review chain as a coordinator.
- If the brief lacks a required artifact, report NEEDS_CONTEXT with the specific missing fact.

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

- Status: APPROVED | CHANGES_REQUESTED | BLOCKED | NEEDS_CONTEXT
- Decision summary
- Findings with severity and file paths
- Verification evidence reviewed
- Concerns or follow-up needed

## Completion protocol

- Final chat text alone does not complete this assignment.
- Write a small JSON payload containing your status evidence.
- Run `./.cowork-flow/run --context-file .cowork-flow/tasks/05-28-agent-team-subagent-drift-probe/agent-team/assignments/T002-quality-reviewer.context.json agent-team worker-report --status <approved | changes_requested | blocked | needs_context> --file <payload.json>`.
- The coordinator collects the persisted outbox with `agent-team collect`; do not run coordinator record commands yourself.
