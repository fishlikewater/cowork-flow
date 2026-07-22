---
name: writing-plans
description: Use when requirements are clear enough to turn into an executable multi-step implementation plan.
---

# Writing Plans

创建另一个代理可以执行而无需猜测的计划。

## 输入

编写计划前，确认请求具有可执行的范围、验收标准和预期行为。如果这些缺失，请询问。

阅读：
- 活跃任务 PRD
- 相关变更规格/设计文件
- 相关 `.cowork-flow/spec/` 索引和目标规格
- 定义正在更改的契约的文件

## 输出

计划应包含：
1. **目标** — 要交付什么
2. **验收标准** — 如何验证完成
3. **步骤** — 按执行顺序，每步有明确的输入/输出
4. **文件** — 要修改的文件列表
5. **验证** — 每步的验证命令

## 原则

- 步骤应足够小，每步可独立验证
- 避免模糊的描述，使用具体的文件路径和命令
- 考虑回滚策略
