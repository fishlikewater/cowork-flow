# 06-05-runtime-binding-shim

## 背景

`cowork-flow` 已经把正式子代理身份切到 runtime context：
`cowork_runtime_context_id` 指向 `.cowork-flow/.runtime/subagents/<id>.json`，
hook/plugin 在工作流状态注入前绑定该 context。

最新真实烟测发现：Codex Desktop 的 `spawn_agent` 子线程没有产生
`UserPromptSubmit hook -> bind_runtime_context -> status=bound` 的副作用。
直接运行 Codex hook 可以绑定，但真实 `spawn_agent(cowork-check)` 后 runtime
文件仍保持 `status=pending`、`bound_context_key=null`。

## 目标

为 Codex、Claude Code、OpenCode 增加 runtime context binding shim 模式：

- 当宿主不能保证子线程启动前自动 hook/plugin 绑定时，正式子代理第一步通过
  显式命令完成绑定。
- 三个宿主 adapter 都声明真实能力，不把未验证的自动绑定标为 `native`。
- 主会话把“绑定成功”作为正式子代理接受事件，未绑定则 fail closed。

## 非目标

- 不改变 runtime context 文件 schema 的核心字段。
- 不引入新的 agent runtime、后台服务或跨进程守护进程。
- 不恢复旧的 prompt ACK/EXECUTE 协议。
- 不把通用 `worker` 提升为正式 `cowork-*` 完成条件。

## 推荐方向

正式子代理派发采用统一握手：

1. 主会话运行 `subagent init` 生成 runtime context。
2. 主会话派发子代理时把以下信息放进子代理首条 prompt：
   - `cowork_runtime_context_id: <id>`
   - `cowork_host_context_key: <adapter-stable-key>`
   - 必须先执行的 `subagent bind` 命令。
3. 子代理第一步运行：
   - Codex/Windows: `.\.cowork-flow\run.cmd subagent bind <id> <context-key>`
   - POSIX hosts: `./.cowork-flow/run subagent bind <id> <context-key>`
4. 主会话 wait/list 后验证 runtime context 已变成：
   - `status=bound`
   - `bound_context_key=<context-key>`
5. 未绑定、绑定错 agent type、绑定错 task dir、或 context closed 时，主会话关闭子代理并记录 adapter failure。

## 影响范围

- `.cowork-flow/spec/subagent-dispatch.md`
- `.cowork-flow/spec/capabilities.md`
- `.cowork-flow/spec/adapter.schema.json`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/adapters/{codex,claude-code,opencode}/adapter.yaml`
- `.codex/agents/*.toml`
- `.claude/agents/*.md`
- `.opencode/agents/*.md`
- `.codex/hooks/`, `.claude/hooks/`, `.opencode/plugins/`
- `template/` mirrors
- runtime/adapter/host tests

## 验收

- Codex、Claude Code、OpenCode adapter 均能表达 `runtimeContextBinding: shim`
  或更具体的 verified capability。
- 固定子代理 prompt 明确要求第一步显式 bind，并禁止未绑定继续执行。
- `subagent bind` 支持三宿主稳定 context key，且重复绑定/错绑有确定行为。
- 主会话验收路径检查 runtime 文件，而不是只信子代理最终文本。
- 测试覆盖直接 hook/plugin bind 与 shim bind 两条路径。
