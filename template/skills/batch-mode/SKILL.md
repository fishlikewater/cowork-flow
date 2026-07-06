---
name: batch-mode
description: Use when user approves a full plan and wants autonomous execution through all tasks without manual stepping. Each task still passes all gates independently.
---

# Batch Mode

## Overview

用户一次审批 plan（`implement.jsonl`），agent 自主完成所有 task。**不是取消验证门**——每个 task 仍然：
- 通过 tdd evidence gate
- 通过 check phase gates
- 独立 commit
- 失败或高风险步骤暂停回用户

仅取消的是 **task 间的手动推进**。

## When to Use

- Plan 已审批（`implement.jsonl` 完整且用户在 writing-plans 结束时说了 "approved" + "auto"）
- 当前 before-dev 状态 = in_progress 或 review
- Task 间低耦合（不同 files/modules，无写冲突）
- L0/L1 任务为主（L2 建议逐 task 确认）

**不适用于**：
- L2 任务（建议逐 task review）
- Task 间有依赖或写冲突
- 首次探索性实现（不确定实现路径）
- 用户未显式请求时

## 启动条件

```
用户: "approved" + "auto"
  -> agent 检查:
     1. before-dev 状态 = in_progress / review
     2. implement.jsonl 存在、非空、每行 valid JSON
     3. 用户明确 approved
```

## 批循环

```
for task in implement.jsonl:
  1. task start <task>  (完整 readiness gate, 包含 L2 doubt-review)
  2. dispatch cowork-implement
  3. dispatch cowork-check
  4. if check pass: git commit + task review + task complete
  5. if check fail: cowork-implement fix (最多 3 次重试)
  6. 遇 5 类安全阀 -> 暂停输出
```

## 5 个安全阀（暂停条件）

以下任一条件触发并**暂停**，不继续下一个 task：

1. **TDD gate 失败**：任何 task 的 tdd.jsonl 证据被 invalid 或 missing
2. **Check gate 失败**：任何 task 的 check.jsonl 有 unresolved blocker（重试 3 次后）
3. **测试构建崩溃**：`git diff` 引入与 R-AG-005 不符的变更
4. **3 次重试仍失败**：同一 task 的 implement + check 循环 3 轮仍未通过
5. **L2 doubt-review blocker**：L2 决策有实质性怀疑发现未被 RECONCILE

暂停时输出：

```
## Batch Mode Paused

Task: <task-name>
Reason: <具体原因>
Current state: <task status + last command output>

Options:
1. Skip this task -> 标记为 skipped，继续下一个
2. Manual takeover -> 退出 batch，用户手动推进
3. Abort -> 退出 batch，所有已 commit 的 task 保持不变
```

## Post-Batch Verification

所有 task 完成后（或跳过/终止后），执行一次：

1. **全量测试**：`python -m pytest` / `npm test` / 项目定义的验证命令
2. **git log 核对**：确认每个 task 有独立 commit，commit message 反映任务
3. **Spec sync 检查**：确认没有遗留的 spec 同步需求
4. **最终报告**：

```
## Batch Mode Report

- 完成 task 数: N
- 跳过 task 数: M（原因: ...）
- 总 commit 数: K
- 发现问题: ...

### Per-Task Summary

| task | commits | duration | issues |
|------|---------|----------|--------|
| ...  | ...     | ...      | ...    |
```

## 与现有系统的关系

- writing-plans → 生成 implement.jsonl（输入）
- task start → 不变（每个 task 单独 readiness gate）
- cowork-implement → 不变（每次 dispatch 一个 task）
- cowork-check → 不变（每次 check 一个 task）
- doubt-review → L2 任务自动触发
- Party Mode → 不参与 batch mode（咨询性质）

## 与 before-dev 门禁的关系

batch mode 在 before-dev 状态为 in_progress 时才能启动。
进入 batch mode 前，主会话确认：
- before-dev 状态 = in_progress / review
- implement.jsonl 存在且非空
- 用户在 writing-plans 结束时明确说 "approved"
