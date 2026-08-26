---
name: task-planning
description: Use when requirements are clear enough to turn into an executable multi-step cowork-flow implementation plan.
---

# Task Planning

Create a plan that another agent can execute without guessing.

## Inputs

Before writing a plan, confirm the request has an executable scope, acceptance criteria, and intended behavior. If those are missing, ask for clarification.

Read:

- Active task `decision-anchor.md`.
- Relevant decision-anchor, design, guide, or spec files.
- Relevant `.cowork-flow/spec/` indexes and target specs.
- `.cowork-flow/spec/guides/index.md` for non-trivial, ambiguous, cross-layer, or reusable-work planning.
- Files that define the contracts being changed.

## Plan Shape

Save plans to `.cowork-flow/plans/YYYY-MM-DD-<slug>.md` unless the user asks for another path.

### Plan Style: Task Briefs, Not Design Docs

Plans exist to prevent implementation drift. They must guide implementation by pinning task order, file boundaries, key symbols, the core patch shape, test proof, completion conditions, and prohibited drift. They are not architecture essays and must not explain every possible option.

Do not write option-comparison tables unless the user explicitly asks. Do not copy complete implementations into the plan. The plan should expose the core patch shape: where to change, what behavior changes, what key branch or pseudocode should guide the edit, how tests prove it, and which boundaries must not be crossed.

Start with a concise brief:

```markdown
# <Feature> Implementation Plan

> Execution rule: this plan exists to prevent implementation drift. The implementer must work through tasks in order.
> If the plan conflicts with current code facts, a plan-external file becomes necessary, or a test fails for an unplanned reason, stop and report back instead of expanding scope.
>
> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

| Field | Content |
|----|------|
| **Goal** | <One sentence describing the observable behavior change> |
| **Task Type** | Tiny / Normal / High-risk: <reason> |
| **Strategy** | Serial / Parallel: <why> |
| **Success Criteria** | AC-001 / AC-002 / AC-003 |
| **Final Verification** | `<command>` -> exit 0; `<command>` -> exit 0 |
| **Primary Risk** | Low / Medium / High: <one sentence> |

## Goal

<1-3 sentences describing the expected observable behavior.>

## Acceptance Criteria

- AC-001: <observable behavior>
- AC-002: <observable behavior>

## Global Constraints

- <Architecture boundary, compatibility requirement, command, or output field that must be preserved>
- <Explicitly prohibited scope expansion>

## File Boundaries

- `path/a.py`: <responsibility; only change this function or region>
- `tests/test_a.py`: <responsibility; only add or modify these tests>

## Tasks
```

Then list task briefs, followed by integrated verification and completion checks.

## Task Rules

- Classify the plan before writing tasks:
  - **Tiny**: pure docs, names, comments, or no-behavior cleanup. Use file boundaries, completion conditions, and one verification command.
  - **Normal**: ordinary behavior, test, or workflow guidance changes. Use the full task brief below.
  - **High-risk**: workflow, runtime, template, spec, hook, state-machine, migration, or security-sensitive changes. Use the full task brief plus code-fact sources and explicit drift boundaries.
- Each task names exact files to create, modify, or test.
- Each task is small enough to execute and verify independently.
- Every Normal or High-risk task must use this brief format:

  ```markdown
  ### Task N: <small goal>

  **Purpose**
  - <Observable behavior after this task is complete>

  **Code Fact Sources**
  - Read: `path/a.py::function_name`
  - Read: `tests/test_a.py::test_existing_behavior`

  **File Boundaries**
  - Create / Modify / Test: `path/a.py` (only change <function/region>)
  - Test: `tests/test_a.py` (only change <test/region>)

  **Key Symbols**
  - Change: `function_name()`, `ClassName.method()`, `<config-key>`
  - Preserve: `existing_helper()`, output field `<field>`

  **Implementation Notes**
  ```python
  # Core control-flow sketch; adjust names to match existing code.
  # Do not copy a complete implementation into the plan.
  ...
  ```

  **Test Proof**
  - `tests/test_a.py::test_x`: proves <specific behavior>
  - Core assertion: <one sentence describing the assertion, not only the test name>

  **Verification Command**
  ```bash
  <command>
  ```

  **Completion Conditions**
  - <2-4 checkable conditions>

  **Prohibited Drift**
  - <2-5 explicit prohibited changes>

  **Deviation Conditions**
  - If <plan-external file/layer> becomes necessary, must stop and report back because the file boundary is wrong.
  ```

- For Tiny tasks, keep the brief short but still name exact file boundaries, completion conditions, and verification commands.
- For behavior changes, include a failing test before implementation when behavior can be tested.
- Do not add shallow tests just to satisfy process. Avoid tests that only assert existence, mirror implementation details, count mock calls without behavior, or snapshot empty structure.
- For complex problems, test depth first: business invariants, cross-layer contracts, state transitions, error boundaries, and real regression paths before narrow unit cases.
- Map behavior-changing tests to stable `decision-anchor.md` acceptance IDs when useful; do not create `tdd.jsonl` or write TDD evidence records into `check.jsonl`.
- Avoid placeholders such as `TODO`, `TBD`, "handle edge cases", or "write tests".
- Keep root/template parity explicit when both copies exist.
- When guide material changes the intended approach, capture the selected conclusion in `decision-anchor.md`, the task brief, or explicit prohibited drift; do not leave it as unstated background knowledge.
- If a task needs more than about 15 lines of implementation pseudocode, split it or narrow the scope. Plans should guide the edit, not replace the implementation.

### Anti-Rationalization - Planning Phase

| Agent Rationalization | Rebuttal | Alternative |
|---|---|---|
| "This task is too small, let's merge it." | Task granularity is determined by acceptance criteria, not line count. Merge only when AC cannot be split. | Split until each step has a distinct AC; keep steps independent even when short. |
| "Write a rough plan first, refine during implementation." | Rough plans do not constrain implementation. Unconstrained implementation invites scope creep and rework. | Use `decision-anchor.md` to derive acceptance criteria, then write task briefs with file boundaries, key symbols, implementation notes, test proof, completion conditions, and prohibited drift. |
| "Skip the plan since we already have decision-anchor." | `decision-anchor.md` defines what to do; the plan defines how to do it and in what order. Without a plan, dependency mistakes surface mid-implementation and increase rework. | Derive ACs from `decision-anchor.md`, then map each AC to concrete files and verification commands. |
| "This task does not need a verification command." | No verification means no completion signal. Every task needs an executable verification command. | Add at least one automated check, such as typecheck, test, lint, or build. |
| "The plan should explore every alternative." | Heavy option analysis slows routine implementation and hides the path to execute. | State the chosen path and drift boundaries. Add option analysis only when the user asks or the decision is genuinely architectural. |

## Plan Approval Gate

A plan can be marked approved only when all conditions hold:

- Every task in `implement.jsonl` has clear acceptance criteria.
- Every task has implementation steps and verification commands.
- Task dependencies are explicit, including whether work is serial or parallelizable.

## Post-Approval Options

- **Step-by-task progression** (default path): the user runs `task next <task-dir> --run` for the current safe action, completes the task, then runs `task next <next-task-dir> --run` for the next task.
- **Batch mode**: triggered only when the user explicitly says "auto" or "batch"; see `skills/batch-execution/SKILL.md`. Each task still must be verified independently.

> **Default is step-by-task progression.** Do not enter batch mode unless the user explicitly says "auto".

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

1. Confirm every `decision-anchor.md` acceptance criterion maps to a task.
2. Search the plan for placeholders.
3. Confirm every Normal or High-risk task has file boundaries, key symbols, implementation notes, test proof, completion conditions, and prohibited drift.
4. Check names, paths, command syntax, and expected outputs.
5. Confirm the plan says to stop and report back when code facts conflict with the plan, a plan-external file becomes necessary, or a test fails for an unplanned reason.
