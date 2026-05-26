# Harden agent-team review contract

## 目标

修复 agent-team 派发 subagent 后“子线程未完成目的就停止，主 agent 缺少有效状态信号”的普遍问题。重点从 prompt 提示升级为运行时协议：reviewer 也使用 worker host identity，worker 只写自己的 outbox，coordinator 只从 outbox collect 推进状态。

## 背景

真实执行中出现过 `spec-reviewer` 没有 review 就停止的情况。现有 runtime 只要求主 agent 等待和手动记录结果，但没有让 reviewer prompt 足够明确，也没有阻止空 payload 或错误 status 被记录成 `approved`。

用户进一步指出，worker brief 头信息不是根本解法：subagent 多轮执行后可能丢失初始语境，`default` reviewer 也可能被 AGENTS/start 带入主 agent 的 coordinator 视角。因此需要把完成事实写入持久 outbox，而不是信任最终聊天文本。

## 范围

- 区分 implementer / spec-reviewer / quality-reviewer 的 assignment prompt。
- `record-spawn` 将 assignment 标记为 `in_progress`。
- `record-result` / `record-review` 增加 status 白名单。
- `record-review --status approved` 强制要求有效 JSON payload。
- implementer / spec-reviewer / quality-reviewer 的 host `agent_type` 统一为 `worker`。
- 新增 worker-scoped `agent-team worker-report`，只允许 worker 为当前 context assignment 写 outbox。
- 新增 coordinator `agent-team collect`，校验 outbox 后才推进 status、attempts、metrics 和依赖解锁。
- 更新 `agent-team-execution` 技能文档，明确子线程停止但无有效报告时使用 `retry --reason adapter_failed`。
- root 与 template 同步。

## 验收标准

- reviewer prompt 不再包含 `Implement exactly this assignment` 或 `Files changed`。
- spec reviewer prompt 包含 review-only、acceptance/spec/PRD/plan 检查和 `APPROVED | CHANGES_REQUESTED | BLOCKED | NEEDS_CONTEXT` 报告格式。
- quality reviewer prompt 包含 code/test/verification review 语义。
- assignment prompt 以 `<COWORK-FLOW-WORKER>` 标记开头，并明确 `.agent/skills/start` 的 `<SUBAGENT-STOP>` guard 适用于已派发子线程，避免子线程进入主会话恢复流程。
- assignment prompt 包含 completion protocol，明确最终聊天文本不完成 assignment，worker 必须用 scoped context 写 `worker-report`。
- spec-reviewer / quality-reviewer assignment 的 `agent_type` 为 `worker`，registry 不能把内建执行链改回 `default` 或自定义 coordinator-like host type。
- `agent-team-execution` 明确要求 bounded wait；子线程进入 start/resume 或无有效报告时关闭子线程并 `retry --reason adapter_failed`。
- `record-spawn` 后该 assignment 变为 `in_progress`，不会再被 `next` 输出。
- worker context 运行 `agent-team worker-report` 时只写 `agent-team/outbox/<assignment-id>.json`，不改变 `status.json`、`metrics.json`、`results/` 或 `reviews/`。
- worker context 不能运行 `record-result`、`record-review`、`next` 等 coordinator mutation/inspection 命令。
- `agent-team collect` 没有 outbox 时失败；有 outbox 时校验 assignment、role、status、approved review payload 后推进状态。
- `agent-team collect` 拒绝 pending assignment 的 outbox，避免 worker 提前越过依赖链。
- `record-review --status approved` 缺少 `--file` 时失败，不改变状态。
- `record-review --status approved --file` 指向非 approved JSON 时失败，不改变状态。
- `record-review --status approved --file` 指向 approved JSON 时成功并解锁下游。
- 不合法 result/review status 被拒绝。
- agent-team 相关 unittest 和 `npm run test:all` 通过。

## 验证方式

- 先运行新增/修改的 unittest，确认在实现前失败。
- 实现后运行 agent-team 相关 unittest。
- 最后运行 `npm run test:all`。
