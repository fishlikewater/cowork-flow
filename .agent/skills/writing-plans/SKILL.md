---
name: writing-plans
description: Use when requirements are clear enough to turn into an executable multi-step cowork-flow implementation plan.
---

# Writing Plans

Create a plan that another agent can execute without guessing.

## Inputs

Read:

- Current task PRD.
- Relevant change spec/design files.
- Relevant `.cowork-flow/spec/` indexes and target specs.
- Files that define the contracts being changed.

## Plan Shape

Save plans to `.cowork-flow/plans/YYYY-MM-DD-<slug>.md` unless the user asks for another path.

Start with:

```markdown
# <Feature> Implementation Plan

> For agentic workers: use `spawn_agent(agent_type="cowork-implement", fork_turns="none")` for implementation and `spawn_agent(agent_type="cowork-check", fork_turns="none")` for verification. Every dispatch prompt starts with `Active task: <task-dir>`.

**Goal:** <one sentence>
**Architecture:** <2-3 sentences>
**Verification:** <commands or checks>
```

## Task Rules

- Each task names exact files to create, modify, or test.
- Each step is small enough to execute and verify independently.
- Include commands and expected results.
- Include tests before implementation when behavior can be tested.
- Avoid placeholders such as TODO, TBD, "handle edge cases", or "write tests".
- Keep root/template parity explicit when both copies exist.

## Self-Review

Before handoff:

1. Confirm every PRD acceptance criterion maps to a plan step.
2. Search the plan for placeholders.
3. Check names, paths, command syntax, and expected outputs.
4. Record remaining risks or blockers.
