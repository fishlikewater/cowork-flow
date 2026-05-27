# Subagent safe recovery

## Goal

Prevent dispatched subagents from being pulled into main coordinator context, and provide scoped recovery when subagents lose their initial task context after long execution or compaction.

## Scope

- Add explicit runtime authority modes: none, coordinator, worker, subagent.
- Gate agent-team coordinator mutation commands behind coordinator context.
- Add generic subagent context files and resume support.
- Add start-skill preflight guidance that treats uncertain messages as subagent-safe.
- Add doctor checks for subagent safety.
- Sync root and template scripts/skills.

## Acceptance criteria

- Unscoped agent-team coordinator mutation commands fail.
- Worker/subagent contexts cannot mutate coordinator state.
- Worker-report only works in worker context.
- Agent-team prepare emits coordinator context.
- Generic subagent init/status/update/resume work.
- Subagent resume does not print main resume checklist.
- Start skill documents conservative preflight and scoped recovery.
- Tests cover runtime gate, recovery, and docs guidance.
