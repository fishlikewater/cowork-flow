# 05-26-agent-team-subagent-recursion Proposal

## 背景

真实 Codex 调度中，主 agent 目前会发送类似下面的混合 prompt：

`Spawn one worker agent for ready assignment ... Use this assignment file as the complete worker prompt ...`

这段文本同时包含两层含义：

- 协调器层：要求宿主或主 agent 再派发一个 worker。
- worker 层：assignment 的实际工作内容。

一旦宿主把这段混合文本整体或部分传给子线程，子 agent 就可能先执行“继续派发”语义，误把自己当成主 agent，随后重新加载上下文并再次派发 subagent，形成递归循环。

## 目标

- 把 Codex 的协调器调度指令和 worker brief 明确拆层。
- 让 `agent-team prepare` 产出可测试的结构化 Codex spawn 元数据，避免主 agent 每次手写或拼接自然语言 dispatch prompt。
- 强化 assignment brief，使 worker 即使看到了外层运输文本，也知道必须忽略它并只执行 assignment 本体。
- 给 worker 一套正式的 cowork-flow 子协议，让它在需要恢复上下文时走 assignment-scoped context，而不是重新进入 coordinator 流程。

## 非目标

- 不重写 agent-team 状态机。
- 不改动任务依赖推断算法。
- 不要求 Python CLI 直接启动 Codex 子 agent。

## 方案摘要

- Codex 环境下，主 agent 应使用结构化 `spawn_agent` 调用，`message` 仅包含 assignment 文件正文。
- `agent_type` 仍来自 assignment；`recommended_agent` 仍只表示 registry 匹配结果。
- 通过 `fork_turns: none` 避免子线程继承主线程历史，减少把自己误判成协调器的机会。
- `prepare` 生成的 `adapters/codex.json` 应暴露这些默认值和 assignment prompt 路径，供主 agent 直接消费。
- `prepare` 还应为每个 assignment 生成 `.context.json`，供 worker 通过 `./.cowork-flow/run --context-file <...>` 进入 worker-scoped `resume`，并在脚本层阻止 `task start` / `agent-team next` 这类 coordinator 命令。
