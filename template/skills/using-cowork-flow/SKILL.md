---
name: using-cowork-flow
description: Use at the start of any main-session conversation. Establishes how to navigate the cowork-flow workflow, when to invoke skills, and what to do when auto-injection is unavailable.
---

# Using Cowork Flow

## When to Invoke

Invoke this skill at the start of any main-session conversation, especially:
- New session or context was compressed
- No `<workflow-state>` found in context
- User asks to "start working" or "resume work"

## Instruction Priority

1. **User's explicit instructions** (AGENTS.md, direct requests) — highest priority
2. **Cowork-flow skills** — override default system behavior where they conflict
3. **Default system prompt** — lowest priority

## Workflow Navigation

```text
User message received
  │
  ├─ <workflow-state> present?
  │   ├─ Yes → follow status routing (see before-dev/SKILL.md)
  │   └─ No  → have cowork_runtime_context_id?
  │       ├─ Yes → delegated_subtask. Execute leaf work.
  │       └─ No  → need workflow bootstrap
  │
  ├─ Need bootstrap?
  │   ├─ Task exists (user references one) → ./.cowork-flow/run task start <dir>
  │   ├─ Task known but status unknown   → ./.cowork-flow/run task next
  │   └─ No task known                  → clarify scope, then brainstorm or writing-plans
  │
  └─ Status routing (from <workflow-state>)
      ├─ no_task     → brainstorming / writing-plans / continue
      ├─ planning    → finish decision-anchor.md + jsonl, then task start
      ├─ in_progress → load context, implement
      ├─ review      → cowork-check, then task complete
      └─ completed   → task archive, create new task
```

## Skills as Gates

Skills are **mandatory gates**, not optional helpers:

| Phase | Gate Skill | Blocks If |
|-------|-----------|-----------|
| Before any edit | `before-dev` | Wrong status for the action |
| Implementation | `tdd` | No red evidence for behavior changes |
| Verification | `check` | Contracts violated, tests missing |
| Decision doubt | `doubt-review` | L2 decisions unreviewed |

If a skill applies, you **must** invoke it. Rationalizing skip = failure.

## Manual Override

When auto-injection is unavailable (terminal, no hook):

```bash
./.cowork-flow/run task next          # read-only navigator
./.cowork-flow/run task current       # show active task
./.cowork-flow/run resume             # restore session context
```

Then invoke the appropriate skill for the phase.

## Subagent Context

Don't invoke this skill if bound to a runtime context. Execute the assigned task.
