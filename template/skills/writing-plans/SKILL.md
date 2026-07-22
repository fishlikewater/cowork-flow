---
name: writing-plans
description: Use when requirements are clear enough to turn into an executable multi-step implementation plan.
---

# Writing Plans

创建另一个代理可以执行而无需猜测的计划。

## 输入

编写计划前，确认请求具有可执行的范围、验收标准和预期行为。缺失则询问。

阅读：活跃任务 PRD、相关变更规格、`.cowork-flow/spec/` 索引、定义契约的文件

## 输出

保存到 `.cowork-flow/plans/YYYY-MM-DD-<slug>.md`

```markdown
# <功能> 实现计划

> 正式固定代理工作：创建 runtime context，传递 `cowork_runtime_context_id`，派发 `cowork-implement`/`cowork-check`，验证后关闭。

**目标：** <一句话>
**架构：** <2-3 句>
**验证：** <命令或检查>
```

## 规则

- 每个任务指定要创建/修改/测试的确切文件
- 每个步骤足够小，可独立执行和验证
- 包含命令和预期结果
- 行为可测试时，实现前先写失败测试
- 禁止浅层测试（仅断言存在、镜像实现、空快照）
- 复杂问题先深度测试：不变量、跨层契约、状态转换、错误边界
- 避免占位符：TODO、TBD、"处理边缘情况"、"编写测试"
- 根/模板副本存在时保持显式一致

## 并行工作

- 共享文件/辅助工具/测试/行为链时使用串行
- 仅当文件所有权清晰且每片有独立验证时使用并行
- 独立任务可能触及包元数据/生成资产/构建输出时使用 worktree
- 每项并行工作必须声明：文件所有权、依赖、预期输出、验证命令
- 并行项完成后，Check/Finish 前包含最终集成验证

## 自检

1. 确认每个 PRD 验收标准映射到计划步骤
2. 搜索计划中的占位符
3. 检查名称、路径、命令语法、预期输出
4. 记录剩余风险或阻塞
