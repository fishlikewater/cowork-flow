# 让 agents.yaml 真实驱动 agent-team

## 背景

当前 `template/.cowork-flow/agent-team/agents.yaml` 包含 capabilities、preferred_task_types、file_patterns、risk_limits 等字段，但运行时只读取 `default_adapter` 和 `agent_type/codex_type`。这会让配置文件看起来可定制，实际调度与 assignment prompt 却不受多数配置影响。

用户希望新增 agent 自定义 prompt，并在默认配置中提供一些通用 agent 及配套 prompt。用户也明确不需要旧兼容字段 `codex_type`。

## 目标

让 `agents.yaml` 成为 agent-team 的真实配置来源：运行时读取 agent 的 `agent_type`、`capabilities`、`preferred_task_types`、`file_patterns`、`risk_limits`、`prompt`，并在生成 dispatch plan 与 assignment prompt 时消费这些配置。

## 范围

- 修改模板和当前项目的 agent-team runtime helper。
- 修改模板和当前项目的默认 `agents.yaml`。
- 更新 init 命令内置默认 agents 配置。
- 增加测试覆盖 prompt 渲染、按配置选择 agent、去除 `codex_type` 兼容。

## 非目标

- 不引入外部 YAML 依赖。
- 不实现复杂自然语言任务分类。
- 不改变 agent-team 命令参数。
- 不让不存在于调度链的 agent 自动执行所有场景；本次只做可预测的候选选择和 prompt 注入。
