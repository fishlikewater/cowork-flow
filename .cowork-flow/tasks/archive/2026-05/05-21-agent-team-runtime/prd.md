# Agent Team Runtime

## Goal

在 cowork-flow 执行 `.cowork-flow/plans/*.md` 的阶段，新增一个平台中立、默认面向 Codex 的 agent team runtime。主 agent 可以据此拆分可独立任务、匹配合适 agent、并行分派、协调执行、记录审阅、处理重试并在上下文恢复后继续工作。

## Scope

- 新增 `./.cowork-flow/run agent-team` 命令组。
- 新增项目级配置：`.cowork-flow/agent-team/agents.yaml`、`adapters.yaml`、`policy.yaml`。
- 新增任务级运行工件：`.cowork-flow/tasks/<task>/agent-team/`。
- 默认适配器为 `codex`，采用主 agent 调度型；`manual` 为兜底适配器。
- 解析现有 writing-plans Markdown，生成依赖图、并行批次和 assignments。
- 每个 plan task 默认生成 `implementer -> spec-reviewer -> quality-reviewer` 链路。
- 支持状态、结果、审阅、阻塞、重试与基础 metrics 落盘。
- 新增 agent team execution skill，并更新 workflow/start/README/template 文档。

## Requirements

- [ ] `agent-team init` 能幂等创建项目级配置，且不覆盖项目自定义内容。
- [ ] `agent-team prepare <task-dir> --plan <plan-file>` 能生成 dispatch plan、status、metrics、assignments 和 Codex adapter 工件。
- [ ] `agent-team next <task-dir>` 能输出下一批可并行执行的 ready assignments。
- [ ] `record-result`、`record-review` 和 `retry` 必须保留 attempt 历史，不覆盖旧结果。
- [ ] `complete` 必须在未完成、阻塞未决、审阅未通过或需要主 agent 决策时失败。
- [ ] 文件范围重叠的 plan tasks 不得进入同一并行批次。
- [ ] 模板同步默认保护 `.cowork-flow/agent-team/` 项目配置。
- [ ] 恢复流程能提示或定位 agent-team 状态。

## Acceptance Criteria

- [ ] `./.cowork-flow/run change validate agent-team-runtime` 通过。
- [ ] `npm test` 通过。
- [ ] `npm run test:template` 通过。
- [ ] `npm run pack:check` 通过。
- [ ] README、workflow、start skill 和新增 skill 都包含 agent team 执行入口。
- [ ] change、plan、task 上下文状态一致。

## Related Artifacts

- Change proposal: `.cowork-flow/changes/agent-team-runtime/proposal.md`
- Behavior spec: `.cowork-flow/changes/agent-team-runtime/spec.md`
- Design: `.cowork-flow/changes/agent-team-runtime/design.md`
- Implementation plan: `.cowork-flow/plans/2026-05-21-agent-team-runtime.md`
