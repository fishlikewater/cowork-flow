# 提升开发计划可执行性 — 减少子代理猜测

## 目标

将开发计划(plan)和任务文档从"给人看的大纲"升级为"给 AI 执行的剧本"，提高 `cowork-implement` / `cowork-check` 固定代理的遵循率和执行一致性。

## 非目标

- 不改 subagent dispatch 协议
- 不改状态机 / gate engine
- 不改 host adapter
- 不新增任务文件格式（plan 文件仍是 markdown）
- 不强制所有 plan 步骤必须严格按顺序执行

## 关键假设

1. 子代理遵循率低的主因不是 prompt 质量，而是接收到的文档信息密度和可执行性不足
2. 子代理能读到 plan 文件后，执行质量会显著提升
3. 当前 plan 文件格式已接近可执行，只需增强步骤粒度，不需换格式
4. L1 和 L2 任务需要不同粒度的步骤说明 — 不需要一刀切

## 范围

### In Scope

- `writing-plans` skill 要求输出更细粒度的步骤（每步带 file/action/verify/expected）
- `cowork-implement` agent prompt 增加读取 plan 文件
- `cowork-check` agent prompt 增加读取 plan 文件
- plan 模板和示例更新
- task create 后自动或手动关联 plan 到 task

### Out of Scope

- 不改变 implement.jsonl 格式
- 不创建 steps.jsonl 或新的结构化文件
- 不修改 subagent dispatch 运行时代码
- 不改变 `task next` 导航逻辑
