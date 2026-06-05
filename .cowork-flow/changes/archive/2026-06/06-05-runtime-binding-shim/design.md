# Runtime Binding Shim Design

## 问题

runtime-context 派发的安全边界分两层：

- **身份发现**：子代理能看到 `cowork_runtime_context_id`。
- **绑定确认**：runtime 文件记录某个宿主子会话已经绑定该 id。

Codex 真实 `spawn_agent` 证明第一层成立，第二层不成立。直接运行 hook 会绑定，
但通过 `spawn_agent(cowork-check)` 启动的子线程不会自动触发绑定副作用。这样会出现
“子代理按 prompt 没迷失，但 runtime contract 没完成”的状态。

Claude Code 与 OpenCode 已分别有 hook/plugin 绑定能力，但不同宿主对 hook 触发时机、
session id 暴露、后台子任务行为的保证不同。workflow 不能把这些差异隐藏成统一的
`native` 能力。

## 方案

引入 **runtime binding shim**：正式 `cowork-*` 子代理在执行任务前必须完成显式绑定。

### 绑定 key

主会话派发时生成 host context key：

```text
<host>_<dispatch-id>
```

约束：

- 只允许 `[A-Za-z0-9._-]` 经现有 `_sanitize()` 规范化后的值。
- 同一次派发内稳定；重试必须使用新的 key 或显式覆盖旧 context。
- 子代理 prompt 必须同时包含 runtime id 与 host context key。

示例：

```text
cowork_runtime_context_id: rtx_20260605_101500_check
cowork_host_context_key: codex_formal_check_001
```

### 子代理第一步

子代理必须先运行绑定命令：

```bash
./.cowork-flow/run subagent bind <runtime_context_id> <cowork_host_context_key>
```

Windows prompt 同时给出：

```powershell
.\.cowork-flow\run.cmd subagent bind <runtime_context_id> <cowork_host_context_key>
```

绑定成功后，runtime 文件必须满足：

- `status == "bound"`
- `bound_context_key == <cowork_host_context_key>`
- `scope == "subagent"`
- `agent_type` 与被派发 agent 一致
- `task_dir` 与本次任务一致

### 主会话验收

主会话派发后不能直接把 child final text 当作成功。必须检查：

1. runtime context 已绑定。
2. 子代理未继续派发、等待、列出或关闭其他 agent。
3. 子代理产物/命令输出满足 role-specific 验收。
4. 收尾调用 `subagent close <runtime_context_id>` 并关闭宿主 child。

绑定失败的处理：

- 关闭宿主 child。
- `subagent close <runtime_context_id>`。
- 记录 `adapter_failed` 或 `needs_context`，不推进 task 阶段。

### 与 hook/plugin 的关系

hook/plugin 自动绑定仍保留，作为更早、更强的绑定路径：

- 如果 hook/plugin 已经绑定，显式 bind 命令应幂等成功，或返回“已绑定同一 key”。
- 如果 hook/plugin 未触发，显式 bind 成为正式接受事件。
- 如果已绑定到不同 key，显式 bind 必须失败，避免错绑覆盖。

## 三宿主策略

### Codex

当前真实能力：

- `dispatchSubagent: native`
- `freshChildContext: native`
- `runtimeContextDispatch: native`
- `runtimeContextBinding: shim`

原因：Codex `spawn_agent` 能创建子线程，但当前 Desktop 子线程不会自动运行项目
`UserPromptSubmit` hook 完成绑定。

### Claude Code

Claude Code 保留 hook 绑定，同时支持 shim 命令：

- hook 可在 `UserPromptSubmit` / `SessionStart` 注入 delegated state。
- 子代理 prompt 仍必须包含显式 bind 命令作为统一 fail-closed 起点。
- adapter 可声明 `runtimeContextBinding: external` 或 `shim`，取决于实现验证结果；
  本任务优先统一为可测试的 shim。

### OpenCode

OpenCode 保留 plugin 绑定，同时支持 shim 命令：

- plugin 可从 prompt/session input 绑定。
- 后台 task 或实验子任务不能假定 plugin 一定先于模型执行。
- adapter 可声明 `runtimeContextBinding: plugin` 加 shim fallback，或统一声明 `shim`。

## 需要调整的产物

- adapter capability：Codex 从 `native` 改为 `shim`。
- 固定 agent 定义：Codex/Claude/OpenCode 都加入“第一步 bind”。
- command 文档：生成 dispatch prompt 时展示 runtime id、host context key、bind 命令。
- subagent runtime：增加幂等 bind 与错绑保护测试。
- tests：覆盖直接 hook/plugin bind、显式 shim bind、错绑失败、adapter capability。

## 风险与取舍

- 显式 bind 多一条命令，牺牲一点 ergonomics，换来可验证安全边界。
- 不能真正做到“模型执行前绑定”；但能做到“正式工作执行前绑定”。
- 对 Codex 是必要修正；对 Claude/OpenCode 是统一防线，避免宿主差异泄漏进 workflow。
