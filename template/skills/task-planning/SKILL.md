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
- The installed `.cowork-flow/templates/plan-template.md`.
- Relevant decision-anchor, design, guide, or spec files.
- Relevant `.cowork-flow/spec/` indexes and target specs.
- `.cowork-flow/spec/guides/index.md` for non-trivial, ambiguous, cross-layer, or reusable-work planning.
- Files that define the contracts being changed.

## Plan Shape

Save plans to `.cowork-flow/plans/YYYY-MM-DD-<slug>.md` unless the user asks for another path.

Use the installed `.cowork-flow/templates/plan-template.md` as the plan skeleton. It carries the execution rule, header table, goal and acceptance sections, global constraints, file boundaries, the per-task brief fields, and the final verification section, so this Skill does not restate them.

If the installed template is missing, stop and report it (run `cwf project sync .` to install it); do not invent a replacement shape.

The template is distributed at install time for the project language configured in `.cowork-flow/config.yaml` (`zh-CN` by default, or `en-US`). Write the plan in that language. Keep the template's machine-readable goal line and `AC-NNN` identifiers unchanged so task creation and workflow gates can parse them. Do not translate paths, commands, code identifiers, or spec file names.

### Plan Style: Task Briefs, Not Design Docs

Plans exist to prevent implementation drift. They must guide implementation by pinning task order, file boundaries, key symbols, the core patch shape, test proof, completion conditions, and prohibited drift. They are not architecture essays and must not explain every possible option.

Do not write option-comparison tables unless the user explicitly asks. Do not copy complete implementations into the plan. The plan should expose the core patch shape: where to change, what behavior changes, what key branch or pseudocode should guide the edit, how tests prove it, and which boundaries must not be crossed.

Fill the template in order: header table and goal first, then acceptance criteria, global constraints, file boundaries, one task brief per executable step, and a final verification section. Do not add a second plan shape or rename the template sections.

## Task Rules

- Classify the plan before writing tasks:
  - **Tiny**: pure docs, names, comments, or no-behavior cleanup. Use file boundaries, completion conditions, and one verification command.
  - **Normal**: ordinary behavior, test, or workflow guidance changes. Use the full task brief.
  - **High-risk**: workflow, runtime, template, spec, hook, state-machine, migration, or security-sensitive changes. Use the full task brief plus code-fact sources and explicit drift boundaries.
- Each task names exact files to create, modify, or test.
- Each task is small enough to execute and verify independently.
- Every Normal or High-risk task fills every required field in the template's task brief: Purpose, Code Fact Sources, File Boundaries, Key Symbols, Implementation Notes, Test Proof, Verification Command, Completion Conditions, Prohibited Drift, and Deviation Conditions.
- For Tiny tasks, keep the brief short but still name exact file boundaries, completion conditions, and verification commands.
- For behavior changes, include a failing test before implementation when behavior can be tested.
- For implementation tasks whose changed files are covered by `.cowork-flow/spec/` requirements, name the covered spec files in the plan and add the clause check to the task's `Verification Command` and the plan's `Final Verification`: run the deciding command when one exists, otherwise check clause by clause and record `pass` / `not_applicable` with reason. This is a strong review reminder, not a separate hard gate.
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

## Fixed-Agent Dispatch

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

Use this path when a task is dispatched to a fixed agent. The plan owns the task boundaries; the runtime context binds the dispatched agent to the current task.

## Plan Approval Gate

A plan can be marked approved only when all conditions hold:

- Every task in the plan has clear acceptance criteria.
- Every task has implementation steps and verification commands.
- Task dependencies are explicit, including whether work is serial or parallelizable.
- The plan uses the installed `.cowork-flow/templates/plan-template.md` shape and the configured output language.

`implement.jsonl` is the current task's context index — the files in scope and
the spec pointers it needs — not the task list. The plan owns the task list.

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
- Each parallel item must name file ownership, dependencies, expected outputs, and verification commands, plus its dispatch: `main` (self-executed) or `cowork-implement` (one child per slice, briefed through the runtime context assignment).
- Use separate sessions, and use a separate `git worktree` when independent tasks may write overlapping project areas.
- Two tasks cannot run in parallel inside one working tree: the file-scope gate reads every working-tree change, so a second task's files fail the first task's review. Cross-task parallelism uses separate worktrees or clones, coordinated through the task board (`--depends-on`, `blockedBy`).
- After parallel items finish, include one final integrated verification step before Check/Finish.

## Self-Review

Before handoff:

1. Confirm every `decision-anchor.md` acceptance criterion maps to a task.
2. Search the plan for placeholders.
3. Confirm every Normal or High-risk task fills every required brief field in the template.
4. Check names, paths, command syntax, and expected outputs.
5. Confirm the plan says to stop and report back when code facts conflict with the plan, a plan-external file becomes necessary, or a test fails for an unplanned reason.
6. Confirm Final Verification carries the applicable `.cowork-flow/spec/<dev_type>/` clause check, or states why no spec file applies.
7. Confirm the plan is written in the configured language and keeps the machine-readable goal line and `AC-NNN` identifiers unchanged.
