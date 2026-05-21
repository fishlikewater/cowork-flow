# Agent Team Config Gate Spec

## 配置契约

`.cowork-flow/config.yaml` 支持以下配置：

```yaml
agent_team:
  enabled: false
```

- 缺省值为 `false`。
- 只有显式设置为布尔值 `true` 或字符串 `true` 时视为启用。
- 当前项目配置和模板配置都必须展示该默认值。

## 行为

当 `agent_team.enabled` 未设置或为 `false` 时：

- `agent-team init` 仍可执行，并继续创建或保留 `.cowork-flow/agent-team/` 下的配置文件。
- `agent-team prepare` 必须返回非 0，并且不得创建任务目录内的 `agent-team/` 运行态工件。
- `agent-team status`、`next`、`record-result`、`record-review`、`retry`、`complete` 必须返回非 0，并输出包含 `agent_team.enabled` 的错误提示。

当 `agent_team.enabled: true` 时：

- 上述运行态命令保持现有行为。
- 既有测试中的分派、状态流转、重试、完成检查语义不变。

## 验收标准

- 禁用配置下，`prepare` 被阻止且不产生运行态目录。
- 启用配置下，`prepare`、`next` 和状态机相关命令通过现有测试。
- 配置读取器有单元测试覆盖默认禁用、显式启用和字符串启用。
- README / workflow / AGENTS 提示使用 agent-team 前需启用配置。
