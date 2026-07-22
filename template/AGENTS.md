# 协作约定

## 核心原则

1. **先思考再编码** — 明确假设，不确定就提问
2. **简单优先** — 用最少的代码解决问题
3. **外科手术式改动** — 只改必须改的
4. **验证驱动** — 先定义成功标准，再循环验证

## 工作流

项目流程以 `.cowork-flow/workflow.md` 为准。

默认执行模型：
```
changes → brainstorming → read spec → plan → tasks → implement → check → complete
```

### 阶段说明

| 阶段 | 说明 | 何时触发 |
|------|------|----------|
| brainstorming | 需求澄清、方案讨论 | 需求不清晰 |
| writing-plans | 编写实现计划 | 多步骤任务 |
| cowork-implement | 按任务范围实现 | 编码 |
| cowork-check | 检查行为和测试 | 验证 |

### 固定代理

| 代理 | 用途 | 禁止 |
|------|------|------|
| cowork-research | 调研、收集信息 | 改代码、改规格 |
| cowork-implement | 实现功能 | 启动其他代理、提交 |
| cowork-check | 检查、验证 | 提交、启动其他代理 |

## 入口

- 开始工作：使用 `start` 技能
- 编码前：使用 `before-dev` 技能
- 需求不清晰：使用 `brainstorming` 技能
- 实现完成后：使用 `check` 技能
- 完成任务：使用 `finish-work` 技能

## 禁止事项

- 不在没有任务上下文时直接修改文件
- 不在没有失败测试时实现行为变化
- 不维护第二套执行状态
- 不把口头状态当成可靠状态

<!-- COWORK-FLOW:START -->
项目规范从 `.cowork-flow/spec/` 按层读取：

- **core 层** — 每次实现必读：`spec/core/`
- **reference 层** — 按需参考：`spec/reference/`
<!-- COWORK-FLOW:END -->
