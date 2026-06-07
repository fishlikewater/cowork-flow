# Proposal: Manual Party Mode

## 背景

用户希望把 BMAD Party Mode 的多代理讨论能力融入 `cowork-flow`，但明确要求不能只是模拟几个人设发言。讨论应由真实子代理独立给出观点，并能持续一到数轮，直到产出有价值、可执行、可验收的结论。

现有 `cowork-flow` 已有 `brainstorming` 闸门、固定 `cowork-*` 叶子代理、runtime-context 派发协议和 host adapter 能力声明。Party Mode 应复用这些边界，而不是引入第二套任务状态或调度器。

## 目标

- 提供用户可手动调用的 Party Mode 入口，优先以 skill 承载真实子代理圆桌流程。
- 让讨论有明确轮次、停止条件和输出 schema，避免一次即止或无止境发散。
- 让每个子代理输出证据、风险、取舍和验收信号，主会话只收敛结论，不替代理由。
- 保持正式实现和检查仍由 `cowork-implement` / `cowork-check` 或等价主会话检查完成。

## 非目标

- 不把 Party Mode 变成正式 implement/check 的完成条件。
- 不允许讨论子代理改代码、提交、归档、启动任务或再派发子代理。
- 不在 `workflow.md` 写入 Codex 专属原语。
- 不照搬 BMAD 的完整运行时、角色库或状态机。
