# Workflow navigation readiness and project context

## Problem

The project now has a documented brainstorming gate, but the operational path is
still implicit. After an unclear requirement appears, the main session must infer
from multiple files whether to brainstorm, create/change a task, write design,
write a plan, start work, or dispatch fixed agents.

That creates three practical gaps:

- No workflow navigator that answers "what should I do next?" from current task
  and change state.
- No explicit L2 readiness gate before task start or fixed-agent dispatch.
- No maintained project-context artifact, so each main session or subagent must
  repeatedly rediscover project facts from scattered files.

## Proposal

Borrow the lightweight parts of BMAD-style analysis without adopting its full role
system:

1. Add `flow help` / `task next` style navigation so the next action is explicit
   and command-oriented.
2. Add a machine-checkable L2 readiness gate that reports missing goal, non-goals,
   assumptions, scope boundary, acceptance criteria, proposal/spec/design, plan,
   task link, and verification.
3. Add generated/maintained `project-context.md` so project facts have one compact
   context surface while authoritative rules remain in existing files.

## Benefits

- Ambiguous requirements are clarified before vague PRDs or premature dispatch.
- L2 work fails closed before important artifacts are missing.
- Agents spend fewer tokens rediscovering project structure.
- Users get actionable next commands instead of process archaeology.
- Template users inherit a stronger but still lightweight workflow.

## Non-goals

- No `agent-team` revival.
- No mandatory BMAD role/persona stack.
- No hook-owned workflow truth.
- No environment-variable setup for normal use.
