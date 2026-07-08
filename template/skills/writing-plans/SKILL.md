---
name: writing-plans
description: Use when requirements are clear enough to turn into an executable multi-step cowork-flow implementation plan.
---

# Writing Plans

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

**Goal:** <one sentence>
**Architecture:** <2-3 sentences>
**Verification:** <commands or checks>
```

## Task Rules

- Each task names exact files to create, modify, or test.
- Each step is small enough to execute and verify independently.
- **Every step MUST follow the executable format below** so subagents never guess:

  ```markdown
  ### Step N.M: <short description>

  - **Files**: <exact file paths, one per line or comma-separated>
  - **Action**: <one sentence describing the concrete change>
  - **Verify**: `<command>` → `<expected output or exit code>`
  - **Expected**: <what the file/state/system looks like after the step succeeds>
  ```

  For behavior-change steps, add TDD evidence:

  ```markdown
  - **TDD**: RED → GREEN
    - redCommand: `<command>`
    - redExitCode: 1
    - greenCommand: `<command>`
    - greenExitCode: 0
    - acceptanceId: AC-001
  ```

- Include commands and expected results in every step.
- Include a failing test before implementation when behavior can be tested.
- Do not add shallow tests just to satisfy process. Avoid tests that only assert existence, mirror implementation details, count mocks without behavior, or snapshot empty structure.
- For complex problems, test depth first: cover invariants, cross-layer contracts, state transitions, error boundaries, and real regression paths before narrow unit cases.
- Map each behavior-changing test to a stable decision-anchor.md acceptance ID and note where `tdd.jsonl` will record the red-green evidence.
- Avoid placeholders such as TODO, TBD, "handle edge cases", or "write tests".
- Keep root/template parity explicit when both copies exist.

### Anti-Rationalization - 计划阶段

| Agent 心理 | 反驳 |
|---|---|
| "这个 task 太小了，可以合并" | task 粒度由 acceptance criteria 决定，不由行数决定。AC 不可拆分时应合并，否则独立。 |
| "先写个粗 plan，实现时再细化" | 粗 plan = 实现时没有约束。没有约束的实现 = 范围蔓延或返工。 |
| "跳过 plan 直接开始反正有了 decision-anchor" | decision-anchor.md 定义"做什么"，plan 定义"怎么做和按什么顺序做"。缺少 plan 的任务在 midway 发现依赖错误时返工成本翻倍。 |
| "这个 task 不需要 verify 命令" | 没有 verify = 没有完成信号。每个 task 必须有可运行的验证命令。 |

## Plan Approval Gate

plan 必须满足以下条件才能被标记为 approved：
- implement.jsonl 中的所有 task 有清晰的 acceptance criteria
- 每个 task 有 implement 步骤和 verify 命令
- task 间依赖关系明确（是否可以并行/必须顺序）

## 批准后选项

- **逐 task 推进**（默认路径）：用户 task start 一个 task，完成后再 task start 下一个。
- **批模式**：用户明确说 "auto" 或 "batch" 后触发 batch skill（参见 skills/batch-mode/SKILL.md）。每个 task 仍然独立验证。

> **默认逐 task 推进。** 当用户没有显式说 "auto" 时，不进入批模式。

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
4. Record remaining risks or blockers.
