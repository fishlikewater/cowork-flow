---
name: task-planning
description: Use when requirements are clear enough to turn into an executable multi-step cowork-flow implementation plan.
---

# Task Planning

Create a plan that another agent can execute without guessing.

## Inputs

Before writing a plan, confirm the request has an executable scope, acceptance criteria, and intended behavior. If those are missing, ask for clarification.

Read:

- Active task decision-anchor.md.
- Relevant change spec/design files.
- Relevant `.cowork-flow/spec/` indexes and target specs.
- Files that define the contracts being changed.

## Plan Shape

Save plans to `.cowork-flow/plans/YYYY-MM-DD-<slug>.md` unless the user asks for another path.

Start with:

```markdown
# <Feature> Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

| 项 | 内容 |
|----|------|
| **目标** | <一句话> |
| **架构** | <2-3 句> |
| **验证** | `<命令>` → exit 0；`<命令>` → exit 0 |
| **策略** | 串行 / 并行（文件所有权：A 组 / B 组） |
| **范围** | N 步 / N 文件 / N AC |
| **风险** | 无显著风险 / 见尾部风险表 §高-N |

## 概览

| Step | AC | 标题 | 状态 |
|------|----|------|------|
| 1.1 | AC-001 | <标题> | ⬜ |
| 1.2 | AC-002 | <标题> | ⬜ |
| 2.1 | — | <标题> | ⬜ |
```

Then list acceptance criteria, then steps.

## Task Rules

- Each task names exact files to create, modify, or test.
- Each step is small enough to execute and verify independently.
- **Every step MUST follow the executable format below** so subagents never guess:

  ```markdown
  ### Step N.M [AC-XXX] ⬜: <一句话描述，中文>

  - **改动**: `path/a.py`, `path/b.py`（×2 = template + root 两份）
  - **做了什么**: <一句话具体变更>
  - **验证**: `<命令>` → exit 0（实现前 exit 1 → 实现后 exit 0 | AC-XXX）
  - **回滚**: <一句话或"仅增测试，无回滚成本">
  ```

  For steps covering multiple AC:

  ```markdown
  - **同时覆盖**: AC-002
  ```

  For steps without an AC (e.g. integrated verification):

  ```markdown
  ### Step N.M — ⬜: <一句话描述，中文>
  ```

  In the overview table, fill AC column with `—` for no-AC steps.

- For behavior changes, include concrete verification in Verify parentheses, such as `reproduces before change -> passes after change`. When setup and final verification differ, use two-line form:
  ```
  - **验证**: `red command` → exit 1 | `green command` → exit 0 | AC-XXX
  ```
- Expected/断言 field is retired. Its responsibility moves into Verify parentheses — describe state changes that exit code alone cannot cover:
  ```
  - **验证**: `pytest tests/test_archive.py -q` → exit 0（覆盖：归档成功的 JSONL 自路径规范化 + 失败路径的字节级回滚）
  ```
- Rollback is always local — write recovery directly in the step. No cross-reference to risk table.
- Include commands and expected results in every step.
- Include a failing test before implementation when behavior can be tested.
- Do not add shallow tests just to satisfy process. Avoid tests that only assert existence, mirror implementation details, count mocks without behavior, or snapshot empty structure.
- For complex problems, test depth first: cover invariants, cross-layer contracts, state transitions, error boundaries, and real regression paths before narrow unit cases.
- Map each behavior-changing test to a stable decision-anchor.md acceptance ID when useful; do not create `tdd.jsonl` or TDD evidence records in `check.jsonl`.
- Avoid placeholders such as TODO, TBD, "handle edge cases", or "write tests".
- Keep root/template parity explicit when both copies exist.

### Anti-Rationalization - Planning Phase

| Agent Rationalization | Rebuttal | Alternative |
|---|---|---|
| "This task is too small, let's merge it." | Task granularity is determined by acceptance criteria, not line count. Merge only when AC cannot be split; otherwise keep independent. | Split until each step has a distinct AC; keep them as independent steps even when short. |
| "Write a rough plan first, refine during implementation." | Rough plan = no constraints during implementation. Implementation without constraints = scope creep or rework. | Write the plan to the full executable format (改动 / 做了什么 / 验证 / 回滚) before any code is touched. |
| "Skip the plan and start directly since we have decision-anchor." | decision-anchor.md defines "what to do"; the plan defines "how to do it and in what order." Tasks without a plan incur doubled rework cost when dependency errors surface midway. | Use decision-anchor.md to derive the AC list, then produce plan steps that map each AC to a concrete file + verify command. |
| "This task doesn't need a verify command." | No verify = no completion signal. Every task must have an executable verification command. | Add at least one automated check (typecheck, test, lint, build) as the Verify step so completion is observable. |

## Plan Approval Gate

A plan can be marked as approved only when all conditions hold:
- Every task in implement.jsonl has clear acceptance criteria
- Every task has implement steps and verify commands
- Task dependencies are explicit (parallelizable vs. strictly sequential)

## Post-Approval Options

- **Step-by-task progression** (default path): user runs `task next <task-dir> --run` for the current safe action, completes the task, then runs `task next <next-task-dir> --run` for the next task.
- **Batch mode**: triggered when the user explicitly says "auto" or "batch" (see skills/batch-execution/SKILL.md). Each task is still verified independently.

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

1. Confirm every decision-anchor.md acceptance criterion maps to a plan step.
2. Search the plan for placeholders.
3. Check names, paths, command syntax, and expected outputs.
4. Record remaining risks or blocklers.
