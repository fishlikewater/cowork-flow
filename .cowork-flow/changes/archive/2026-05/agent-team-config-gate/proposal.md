# Agent Team Config Gate

## 背景

`agent-team` 运行时已经可以生成分派计划、assignment、状态和 metrics，但当前它不读取 `.cowork-flow/config.yaml`。这会导致工作流说明中的 agent-team 能力一旦存在就默认可用，项目无法通过统一配置关闭它。

## 目标

在 `.cowork-flow/config.yaml` 中提供 `agent_team.enabled` 开关，默认禁用，并让该开关实际影响 `agent-team` 运行态命令。

## 范围

- 在当前项目和模板配置中加入默认禁用配置。
- 扩展现有 Python 简单配置读取器，提供 agent-team 启用状态查询。
- 让 `agent-team prepare/next/status/record-result/record-review/retry/complete` 在禁用时拒绝执行并提示启用方式。
- 保留 `agent-team init` 可执行，用于初始化 `.cowork-flow/agent-team/` 配置文件。
- 补充回归测试和必要文档。

## 非目标

- 不新增复杂 YAML 依赖。
- 不改变 agent-team 状态机、分派算法或适配器格式。
- 不为每个子命令增加独立开关。
