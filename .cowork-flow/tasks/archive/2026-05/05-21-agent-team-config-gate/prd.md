# Agent Team Config Gate

## Goal

在 `.cowork-flow/config.yaml` 中添加 agent-team 启用开关，默认禁用，并让该配置实际控制 agent-team 运行态命令。

## Requirements

- 当前项目和模板配置都包含 `agent_team.enabled: false`。
- 未显式启用时，`agent-team prepare/status/next/record-result/record-review/retry/complete` 必须拒绝执行。
- 未显式启用时，`agent-team init` 仍可执行，用于初始化项目级 agent-team 配置。
- 显式设置 `agent_team.enabled: true` 时，现有 agent-team 运行时行为保持不变。
- README、AGENTS、workflow 文档说明启用要求。

## Acceptance Criteria

- [x] 默认禁用时，`agent-team prepare` 返回非 0 且不生成任务内 `agent-team/` 工件。
- [x] 启用后，现有 plan parser 和 state machine 测试通过。
- [x] 配置读取器覆盖默认禁用、布尔 true、字符串 true。
- [x] 模板配置和文档测试覆盖默认禁用说明。

## Technical Notes

本任务是 L1 行为变更，范围限定在 agent-team runtime、配置读取器、模板配置和相关文档/测试。保持现有简单 YAML 解析器，不引入第三方依赖。
