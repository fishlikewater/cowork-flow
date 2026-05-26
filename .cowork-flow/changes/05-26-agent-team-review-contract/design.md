# Agent-team review contract design

## 根因

这次失败模式发生在 subagent 与 coordinator 的边界上。现有 assignment prompt 已经解决了一部分“子线程误以为自己是 coordinator”的问题，但只靠首条 worker brief 不可靠：子线程多轮执行后可能丢失头部语境，最终聊天文本也无法证明 assignment 已经按 role 完成。

更根本的问题是宿主身份与业务角色混在了一起。`spec-reviewer` / `quality-reviewer` 是业务职责，但如果 host `agent_type` 仍然是 `default`，子线程容易进入主 agent 的 start/resume/coordinator 视角。再加上 `record-review` 不校验状态和 payload，主 agent 没有硬门禁判断“reviewer 已经真正 review”。

## 设计方向

保持当前 runtime 简单结构，只收紧五个边界：

1. **Prompt 边界**：`render_assignment_prompt()` 保留通用 worker 护栏，但把 role-specific job/report 拆成 helper。这样 reviewer prompt 不再出现 implementer 专属语言。
2. **宿主身份边界**：内建执行链的 `agent_type` 强制为 `worker`。`role` 决定 implement/review 业务职责，`agent_type` 只表达 Codex host execution identity。
3. **状态边界**：`record-spawn` 把 assignment 标为 `in_progress`；`next` 只看 `ready`，所以已派发但未回写结果的 assignment 不会被重复派发，也能在 `status --verbose` 中暴露。
4. **outbox 边界**：worker-scoped `worker-report` 只能写自己的 `outbox/<assignment-id>.json`，不能直接修改 coordinator state。
5. **记录边界**：coordinator `collect` 从 outbox 校验 assignment、role、status 和 approved payload 后推进状态；`record-result` / `record-review` 仍保留为 coordinator 直接记录路径，并继续做命令级 status 白名单校验。

## 状态模型

现有终态集合从宽泛的 `{"done", "approved"}` 改为依赖解锁函数显式判断：

- `done` 解锁 implementer 的下游 spec reviewer。
- `approved` 解锁 reviewer 的下游 reviewer。
- 其他状态都保持 assignment 未通过，需要 coordinator retry 或决策。

为了避免引入迁移，`status.json` 仍是普通 JSON 字典，新增 `in_progress` 只是 assignment `status` 的一个字符串值。

`outbox/` 不改变 `status.json` 顶层结构。worker 写 outbox 后，assignment 可仍是 `in_progress`；只有 coordinator `collect` 成功后才会增加 attempts、更新 metrics 并解锁依赖。

## Payload 校验

本次只要求 `record-review --status approved` 与 `collect` approved reviewer outbox 校验 JSON payload 中的 `decision` 或 `status` 是否为 `approved`。这是最小可用门禁：它不能判断 review 质量，但可以阻止“无 review 工件也能 approved”的空跑路径。

后续如果需要更强门禁，可再扩展为 role-specific payload schema，例如 `findings`、`evidence`、`verification` 等字段。本次不提前做复杂 schema，避免过度设计。

## Outbox 协议

worker 通过 scoped context 调用：

```bash
./.cowork-flow/run --context-file <assignment.context.json> agent-team worker-report --status <status> --file <payload.json>
```

runtime 从 context 解析 `taskDir` 和 `assignment`，并拒绝 worker 为其他 assignment 写报告。写出的 outbox 至少包含 `assignment`、`role`、`status` 和 `payload`。

coordinator 调用：

```bash
./.cowork-flow/run agent-team collect <task-dir> --assignment <id>
```

`collect` 是唯一从 worker outbox 推进状态的入口；没有 outbox 时失败。因此子线程最终回复、summary 或口头 `DONE` 都不会自动变成状态机事实。

## 同步范围

需要同步修改：

- `.cowork-flow/scripts/common/agent_team.py`
- `template/.cowork-flow/scripts/common/agent_team.py`
- `.cowork-flow/scripts/agent_team.py`
- `template/.cowork-flow/scripts/agent_team.py`
- `.agent/skills/agent-team-execution/SKILL.md`
- `template/.agent/skills/agent-team-execution/SKILL.md`
- 相关 unittest
