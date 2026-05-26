# 05-26-agent-team-review-contract

## 背景

`agent-team` 已经能生成 Codex subagent assignment，并通过 `spawn_agent` / `wait_agent` / `close_agent` 由主 agent 调度。但真实执行中仍出现普遍失败模式：subagent 已经停止，尤其是 `spec-reviewer`，却没有完成对应 review；主 agent 随后缺少可靠状态信号，容易继续等待、误判或手动补救。

现有问题不是单个 prompt 偶发失效，而是运行契约过软：

- reviewer assignment 使用了偏 implementer 的通用 `Your job` 和 `Report format`。
- `record-review` 接受任意 status，且不要求 review payload。
- `record-spawn` 只保存线程名，不把 assignment 标记为已派发。
- 文档说明了要等 worker 结果，但没有把“无有效报告的子线程退出”定义为必须 retry 的 adapter failure。
- 仅靠 worker brief 头部提示不可靠；多轮子线程可能丢失初始语境，最终聊天文本也不能作为完成证据。
- reviewer 使用 `default` host type 时容易继承主 agent 视角，进入 coordinator/start/resume 流程，而不是执行单个 assignment。

## 目标

收紧 agent-team 的 review 与 dispatch 契约，让 subagent 没有真正完成目的时不能被静默当作成功或无限等待。

## 范围

- 为 implementer、spec-reviewer、quality-reviewer 生成角色明确的 assignment prompt。
- 为 result/review 记录增加状态白名单与最小 payload 校验。
- `record-spawn` 将 ready assignment 标记为 `in_progress`，使已派发未产出的状态可见。
- 让 implementer、spec-reviewer、quality-reviewer assignment 的 Codex host `agent_type` 统一为 `worker`，业务职责继续由 `role` 区分。
- 增加 worker-scoped `worker-report` outbox，让 worker 只能为自己的 assignment 写报告，不能直接推进 coordinator 状态。
- 增加 coordinator `collect`，从 persisted outbox 校验 assignment、role、status 和 approved review payload 后再推进状态机。
- 更新 `agent-team-execution` 技能文档，明确子线程停止但无有效报告时按 `adapter_failed` retry。
- 同步 root 与 `template/` 两套运行时和文档。
- 增加回归测试覆盖 prompt、状态机、记录门禁和文档约束。

## 非目标

- 不让 Python 运行时直接调用 Codex subagent 工具。
- 不改变 plan parser、依赖图生成或并行批次策略。
- 不引入新的外部依赖或复杂 schema 校验库。
- 不替代主 agent 对 review 内容的人工/智能判断；本次只保证最小结构和状态契约可靠。
- 不为 outbox 引入复杂 schema 或外部依赖；本次只做最小 JSON payload 和状态门禁。

## 成功标准

- spec reviewer prompt 明确要求审查 proposal/spec/plan/PRD 与 assignment 结果，不再要求它 implement 或报告 changed files。
- quality reviewer prompt 明确要求审查 diff、测试和验证证据。
- `record-review --status approved` 必须带有效 JSON payload，且 payload 中有 `decision: approved` 或 `status: approved`。
- review reject / blocked / needs_context 不会解锁后续 reviewer。
- `record-result` 和 `record-review` 拒绝不属于各自命令的状态。
- `record-spawn` 后 assignment 状态为 `in_progress`，`next` 不再重复输出该 assignment。
- 文档明确：wait 返回但没有有效 worker report 时，主 agent 应记录 retry reason `adapter_failed`，而不是继续等待或记录成功。
- reviewer assignment 的 `agent_type` 为 `worker`，即使 registry 里配置了 `default`、`reviewer` 或自定义 host type，也不能把内建执行链带回 coordinator 视角。
- worker 通过 scoped context 运行 `agent-team worker-report` 时只写 `agent-team/outbox/<assignment-id>.json`，不修改 `status.json` 或 `metrics.json`。
- coordinator 运行 `agent-team collect <task-dir> --assignment <id>` 时必须存在有效 outbox；没有 outbox 时失败，聊天最终答案不能替代 outbox。
