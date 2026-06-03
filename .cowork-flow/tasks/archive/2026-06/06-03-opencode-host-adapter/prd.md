# OpenCode host adapter architecture

## 目标

为 cowork-flow 增加可扩展的 Host Adapter 架构，支持 OpenCode 适配，同时保持现有 `Plan -> Implement -> Check -> Finish` 流程语义不变。

## 范围

- 新增 host-neutral adapter/entry/delegation 规格。
- 新增 Codex 与 OpenCode adapter 声明。
- 调整 `workflow.md` 中 host-specific 措辞，使其描述固定执行契约而非 Codex 专属工具。
- 同步模板，包含 OpenCode agents/commands/plugins 的基础契约文件。
- 增加测试，约束 workflow 不出现宿主分支，adapter schema 可校验，OpenCode 资产包含固定派发协议。

## 非目标

- 不实现完整 OpenCode runtime runner。
- 不改变现有 Codex 固定 agent 执行逻辑。
- 不废弃 `COWORK_DISPATCH_V1` / ACK / EXECUTE。
- 不把非结构化 advisory subagent 输出视为正式阶段完成依据。

## 验收标准

- `.cowork-flow/spec/` 与 `template/.cowork-flow/spec/` 存在 entry contract、adapter contract、delegation envelope、capabilities 文档。
- `.cowork-flow/adapters/codex/adapter.yaml` 与 `.cowork-flow/adapters/opencode/adapter.yaml` 存在，schemaVersion、capabilities、formal contract 完整。
- `workflow.md` 保持流程源头地位，但不再把 `spawn_agent` 写成唯一宿主机制。
- OpenCode 模板资产使用 `.opencode/agents`、`.opencode/commands`、`.opencode/plugins`，且包含 leaf executor、ACK、EXECUTE、防 bootstrap 误判约束。
- 测试覆盖 adapter schema、workflow host-neutral、OpenCode 模板契约、sync 安全路径。

## 验证

- `npm test`
- `python -m unittest discover -s tests`
- `git diff --check`
