# 用 SkillOpt 优化模板 skill

## 执行策略

串行执行。当前任务修改 subagent 边界说明本身，不再派发子 agent，避免验证对象和执行机制互相污染。

## 步骤

1. 建立 SkillOpt pilot 评测设计。
   验证：记录 train/val/test 样例、期望分类、训练结果和 gate 判断。

2. 优化 `entry-boundary` / `start` / `writing-plans` skills。
   验证：root/template 内容同步；文本覆盖无硬标记、首屏优先、bootstrap 仅约束、自然语言边界轻量化，以及并行计划边界。

3. 加强回归检查。
   验证：测试能检查新的关键语义，不只是文件存在。

4. 跑验证并收口。
   验证：unit tests、doctor、`git diff --check`、`npm run test:all` 全部通过。
