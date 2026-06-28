# PRD: 补全主会话内联执行 plan 读取路径

## 目标

将 plan 文件读取指引从子代理路径扩展到主会话内联执行路径，确保主会话内联实现和检查时也会读取 plan 文件并按步骤执行。

## 非目标

- 不创建新文件格式
- 不修改子代理 agent prompt（已完成）

## 验收标准

| ID | 描述 |
|----|------|
| AC-01 | `workflow-state-templates.md` 的 `in_progress` 模板增加 plan 读取提示 |
| AC-02 | `workflow-state-templates.md` 的 `review` 模板增加 plan 检查提示 |
| AC-03 | `before-dev` skill 的 `in_progress` 门禁增加 plan 读取步骤 |
| AC-04 | template/ 镜像同步 |
| AC-05 | 现有测试不退化 |
