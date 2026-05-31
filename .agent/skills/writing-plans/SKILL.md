---
name: writing-plans
description: Use when requirements are clear enough to turn into an executable multi-step cowork-flow implementation plan.
---

# Writing Plans

Create a plan that another agent can execute without guessing.

## Inputs

Before writing a plan, confirm the request has an executable scope, acceptance criteria, and intended behavior. If those are missing, ask for clarification.

Read:

- Active task PRD.
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
- Include a failing test before implementation when behavior can be tested.
- Do not add shallow tests just to satisfy process. Avoid tests that only assert existence, mirror implementation details, count mocks without behavior, or snapshot empty structure.
- For complex problems, test depth first: cover invariants, cross-layer contracts, state transitions, error boundaries, and real regression paths before narrow unit cases.
- Avoid placeholders such as TODO, TBD, "handle edge cases", or "write tests".
- Keep root/template parity explicit when both copies exist.

## Parallel Work

Execution strategy guide:

- Use serial work when slices share files, shared helpers, tests, or one behavior chain.
- Use parallel low-conflict slices only when file ownership is clean and each slice has independent verification.
- Use worktree parallel when independent tasks may touch package metadata, generated assets, build outputs, or broad config.

- Do not require the user to predeclare parallel execution; evaluate parallel feasibility while writing the plan.
- Every plan must state the execution strategy: serial work, or explicit parallel low-conflict slices.
- Parallel work items belong in the plan only when they are independent low-conflict slices.
- Each parallel item must name file ownership, dependencies, expected outputs, and verification commands.
- Use separate sessions, and use a separate `git worktree` when independent tasks may write overlapping project areas.
- After parallel items finish, include one final integrated verification step before Check/Finish.

## Self-Review

Before handoff:

1. Confirm every PRD acceptance criterion maps to a plan step.
2. Search the plan for placeholders.
3. Check names, paths, command syntax, and expected outputs.
4. Record remaining risks or blockers.
