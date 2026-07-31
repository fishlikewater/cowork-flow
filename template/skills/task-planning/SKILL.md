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

### Plan Style: Task Briefs, Not Design Docs

Plans exist to 防止后续实现漂移. They must guide implementation by
pinning the task order, file boundaries, symbols, core patch shape, test
proof, completion conditions, and prohibited drift. They are not architecture
essays and must not explain every possible option.

Do not write option-comparison tables unless the user explicitly asks. Do not
copy complete implementations into the plan. The plan should expose the core
patch shape: where to change, what behavior changes, what key branch or
pseudocode should guide the edit, how tests prove it, and which boundaries
must not be crossed.

Start with a concise brief:

```markdown
# <Feature> Implementation Plan

> 执行规则：本计划用于防止实现漂移。执行者必须按 Task 顺序推进。
> 如果发现计划与当前代码事实冲突、必须修改计划外文件、或测试失败原因不是计划预期，应停止并回报，不自行扩大范围。
>
> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

| 项 | 内容 |
|----|------|
| **目标** | <一句话说明要改变的可观察行为> |
| **任务类型** | Tiny / Normal / High-risk：<原因> |
| **策略** | 串行 / 并行：<为什么> |
| **成功标准** | AC-001 / AC-002 / AC-003 |
| **最终验证** | `<命令>` -> exit 0；`<命令>` -> exit 0 |
| **主要风险** | 低 / 中 / 高：<一句话> |

## 目标

<1-3 句话：期望改变的可观察行为。>

## 验收标准

- AC-001: <可观察行为>
- AC-002: <可观察行为>

## 全局约束

- <必须保留的架构边界、兼容性、命令、输出字段>
- <明确禁止事项，防止范围膨胀>

## 文件边界

- `path/a.py`: <职责；本次只允许改哪个函数/区域>
- `tests/test_a.py`: <职责；本次只允许新增/修改哪些测试>

## Tasks
```

Then list Task briefs, then integrated verification and completion checks.

## Task Rules

- Classify the plan before writing tasks:
  - **Tiny**: pure docs, names, comments, or no-behavior cleanup. Use file boundaries, completion conditions, and one verification command.
  - **Normal**: ordinary behavior, test, or workflow guidance changes. Use the full Task brief below.
  - **High-risk**: workflow/runtime/template/spec/hook/state-machine/migration/security-sensitive changes. Use the full Task brief plus code-fact sources and explicit drift boundaries.
- Each Task names exact files to create, modify, or test.
- Each Task is small enough to execute and verify independently.
- Every Normal or High-risk Task MUST follow this brief format:

  ```markdown
  ### Task N: <小目标>

  **目的**
  - <该 Task 完成后的可观察行为>

  **代码事实来源**
  - 已读: `path/a.py::function_name`
  - 已读: `tests/test_a.py::test_existing_behavior`

  **文件边界**
  - Create / Modify / Test: `path/a.py`（只改 <函数/区域>）
  - Test: `tests/test_a.py`（只改 <测试名/区域>）

  **关键符号**
  - 改: `function_name()`, `ClassName.method()`, `<config-key>`
  - 保持: `existing_helper()`, 输出字段 `<field>`

  **实施要点**
  ```python
  # 核心控制流草案，按现有代码命名调整；不复制完整实现
  ...
  ```

  **测试证明**
  - `tests/test_a.py::test_x`: 证明 <具体行为>
  - 核心断言: <一句话描述 assertion，而不是只列测试名>

  **验证命令**
  ```bash
  <command>
  ```

  **完成条件**
  - <2-4 条可检查条件>

  **禁止漂移**
  - <2-5 条明确禁止事项>

  **偏离条件**
  - 如果需要修改 <计划外文件/层级>，must stop and report back because the file boundary is wrong.
  ```

- For Tiny tasks, keep the brief short but still name exact file boundaries, completion conditions, and verification commands.
- For behavior changes, include a failing test before implementation when behavior can be tested.
- Do not add shallow tests just to satisfy process. Avoid tests that only assert existence, mirror implementation details, count mocks without behavior, or snapshot empty structure.
- For complex problems, test depth first: cover invariants, cross-layer contracts, state transitions, error boundaries, and real regression paths before narrow unit cases.
- Map each behavior-changing test to a stable decision-anchor.md acceptance ID when useful; do not create `tdd.jsonl` or TDD evidence records in `check.jsonl`.
- Avoid placeholders such as TODO, TBD, "handle edge cases", or "write tests".
- Keep root/template parity explicit when both copies exist.
- If a Task needs more than about 15 lines of implementation pseudocode, split it or narrow the scope. Plans should guide the edit, not replace the implementation.

### Anti-Rationalization - Planning Phase

| Agent Rationalization | Rebuttal | Alternative |
|---|---|---|
| "This task is too small, let's merge it." | Task granularity is determined by acceptance criteria, not line count. Merge only when AC cannot be split; otherwise keep independent. | Split until each step has a distinct AC; keep them as independent steps even when short. |
| "Write a rough plan first, refine during implementation." | Rough plan = no constraints during implementation. Implementation without constraints = scope creep or rework. | Write Task Briefs with file boundaries, key symbols, implementation notes, test proof, completion conditions, and prohibited drift before code is touched. |
| "Skip the plan and start directly since we have decision-anchor." | decision-anchor.md defines "what to do"; the plan defines "how to do it and in what order." Tasks without a plan incur doubled rework cost when dependency errors surface midway. | Use decision-anchor.md to derive the AC list, then produce plan steps that map each AC to a concrete file + verify command. |
| "This task doesn't need a verify command." | No verify = no completion signal. Every task must have an executable verification command. | Add at least one automated check (typecheck, test, lint, build) as the Verify step so completion is observable. |
| "The plan should explore every alternative." | Heavy option analysis makes routine implementation slower and hides the path to execute. | State the chosen path and the drift boundaries. Add option analysis only when the user asks or the decision is genuinely architectural. |

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

1. Confirm every decision-anchor.md acceptance criterion maps to a Task.
2. Search the plan for placeholders.
3. Confirm every Normal/High-risk Task has file boundaries, key symbols, implementation notes, test proof, completion conditions, and prohibited drift.
4. Check names, paths, command syntax, and expected outputs.
5. Confirm the plan says to stop and report back when code facts conflict with the plan, a plan-external file becomes necessary, or a test fails for an unplanned reason.
