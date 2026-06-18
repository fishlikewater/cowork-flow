# Host Structured Signal Feasibility Report

**Task:** `06-16-entry-structured-signals-research`
**Change:** `06-15-workflow-maturity-roadmap` (P0-A)
**Date:** 2026-06-16
**Type:** Research only — no code/spec/adapter modifications made.

---

## 1. Capability Matrix

| Host | `session_role` (main/subagent/command) | `invocation_kind` (interactive/command_wrapper/hook/read_only) | Transport Channel |
| --- | --- | --- | --- |
| **claude-code** | 部分（仅 subagent 可稳定获取 via runtime_context_id；main vs command 无法区分） | 部分（hook 事件名 `UserPromptSubmit`/`SessionStart` 可推断 invocation_kind，但 interactive 无事件名区分） | env / metadata / prompt |
| **codex** | 部分（仅 subagent 可稳定获取 via runtime_context_id；main vs command 无法区分） | 部分（dispatch_mode `<codex-dispatch-mode>` 标签可区分 sub-agent 模式，但 interactive 无标签） | env / metadata / prompt |
| **opencode** | 部分（仅 subagent 可稳定获取 via runtime_context_id；main vs command 无法区分） | 部分（`shell.env` transform 可注入环境变量；但 main vs command 无区分字段） | env / metadata / prompt |

**结论：三宿主均无法稳定提供 `session_role`（main vs command）和 `invocation_kind`（interactive vs command_wrapper）。** 唯一可稳定获取的信号是 subagent 身份（通过 runtime_context_id 绑定），但这是 P0 不打算改的强信号。

---

## 2. Evidence by Host

### 2.1 claude-code

**文件:** `.claude/hooks/inject-workflow-state.py`

- **Hook 输入结构**（行 35-41）：`read_hook_input()` 从 stdin 读 JSON，标准化 `session_id` 为 `claude_session_id`。
- **事件名**（行 44-48）：`hook_event_name()` 从 `hook_event_name` 或 `hookEventName` 读取，默认 `"UserPromptSubmit"`。
- **Hook 注册**：`_build_host_block`（行 51-58）声明 `"hooks: UserPromptSubmit, SessionStart"`。
  - `UserPromptSubmit` = 用户发送消息（interactive）
  - `SessionStart` = 会话启动
  - **无 `CommandInvoke` 或等效事件名**，无法区分"主会话交互式"和"命令包装"。
- **session_role**：claude-code 无 `session.role` 或 `invocation.kind` 字段。`claude_session_id` 仅标识会话，不区分角色。
- **invocation_kind**：`hook_event_name` 可推断 `UserPromptSubmit` = interactive，但无法区分 interactive 和 command_wrapper（两者都走 `UserPromptSubmit`）。

**结论**：claude-code hook 可提供 `hook_event_name` 作为 invocation_kind 的近似信号，但 main vs command 无法区分。

### 2.2 codex

**文件:** `.codex/hooks/inject-workflow-state.py`

- **Hook 输入结构**（行 66-67）：`read_hook_input()` 从 stdin 读 JSON。
- **dispatch_mode**（行 35-43）：`_get_dispatch_mode()` 从 config 读取 dispatch mode，默认 `"sub-agent"`。
- **host block**（行 46-59）：`<codex-dispatch-mode>` 标签输出 dispatch_mode，`<codex-runtime>` 声明 `"runtime_context_identity: formal subagent sessions bind before workflow-state injection"`。
- **session_role**：codex 的 `CODEX_SESSION_ID` / `CODEX_THREAD_ID` 环境变量仅标识会话，不携带 role 信息。
- **invocation_kind**：dispatch_mode 可区分 sub-agent 模式，但 interactive 和 command_wrapper 都走同一 dispatch_mode。无独立 invocation_kind 字段。

**结论**：codex hook 可提供 `dispatch_mode` 作为 sub-agent 身份的间接信号，但无法区分 main/session 和 command_wrapper。

### 2.3 opencode

**文件:** `.opencode/plugins/cowork-flow.js`

- **Plugin 注册**（行 343-352）：两个 transform：
  - `"shell.env"`：注入 `COWORK_FLOW_CONTEXT_ID` 和 `OPENCODE_SESSION_ID` 到环境变量。
  - `"experimental.chat.system.transform"`：向 system prompt 注入 contract digest + runtime workflow state。
- **输入结构**（行 38-50）：`inputCwd(input)` 从 `input.session.cwd` / `input.context.cwd` / `input.workspace.cwd` 取 cwd。
- **session ID**（行 205-218）：`resolveOpenCodeSessionId(input)` 从 `input.session.id` / `input.sessionID` / `input.sessionId` / `input.session_id` 取会话 ID。
- **session_role**：opencode 的 input 结构中无 `session.role`、`invocation.kind` 或等效字段。`input.session.id` 仅标识会话。
- **invocation_kind**：无区分 interactive vs command_wrapper 的字段。`shell.env` transform 可注入环境变量，但注入的是 context_key，不是 invocation_kind。

**结论**：opencode 的 plugin transform 无法提供 session_role 或 invocation_kind。唯一的结构化信号是 `OPENCODE_SESSION_ID`（会话标识），与 claude-code 的 `CLAUDE_SESSION_ID` 和 codex 的 `CODEX_SESSION_ID` 类似，仅标识会话，不携带角色。

---

## 3. P0-A 实现方案选型建议

### 选型结论：结构化信号优先 + 兼容期文本回退（全宿主）

基于以上调研，三宿主均**无法稳定提供** `session_role`（main vs command）和 `invocation_kind`（interactive vs command_wrapper）。因此：

**推荐方案**：

1. **adapter.yaml 加 entrySignals 段**（设计文档要求的契约变更保留）：
   - claude-code：声明 `invocationKind: hook_event_name`（从 `hook_event_name` 字段读取，值为 `"UserPromptSubmit"` 或 `"SessionStart"`）。
   - codex：声明 `invocationKind: dispatch_mode`（从 `_get_dispatch_mode()` 返回值读取，值为 `"sub-agent"` 或其他）。
   - opencode：无稳定信号，entrySignals 为空。

2. **entry_classifier 改造**：
   - 读结构化信号 → 若信号存在且合法 → 返回对应 EntryKind，confidence 0.9。
   - 信号缺失或不合法 → **保留 `_legacy_text_fallback` 作为兼容期兜底**，默认禁用，通过 config 开关启用。
   - 兼容期开关默认值由 `config.yaml` 控制，三宿主全部改造完成后再永久关闭。

3. **空窗期 fail-closed 保障**：
   - 结构化信号缺失时，即使 `_legacy_text_fallback` 禁用，也返回 `UNKNOWN`（fail-closed）。
   - 这意味着：三宿主在改造完成前，所有请求都会被分类为 `UNKNOWN`（因为 `session_role` 和 `invocation_kind` 都无法稳定获取）。
   - **缓解措施**：兼容期内 `_legacy_text_fallback` 必须默认启用，直到三宿主 adapter.yaml 声明了可用的结构化信号。

### 风险评估

| 风险 | 严重度 | 缓解 |
| --- | --- | --- |
| 改造期间所有请求变 UNKNOWN，工作流卡死 | **高** | 兼容期 `_legacy_text_fallback` 默认启用；空窗期不阻塞 |
| claude-code 的 `hook_event_name` 不是稳定的 invocation_kind 信号 | 中 | 仅作为"部分信号"，fallback 到文本分类 |
| codex 的 `dispatch_mode` 只在 sub-agent 模式下有意义 | 中 | 仅用于 sub-agent 场景，main-session 仍走 fallback |
| opencode 完全无法提供结构化信号 | 高 | opencode 在兼容期内必须依赖 fallback；后续需 opencode 侧改造 |

### 对 P0-A 实现的影响

- P0-A 的实现不能假设三宿主都能提供结构化信号。
- 设计文档中的"方案 1（结构化信号优先）"需要修正为 **"方案 1 + 兼容期 fallback"**。
- opencode 可能需要额外改造（在 plugin 中注入 `invocation_kind` 字段），但这超出了 P0-A 的范围，应推迟到 P3-B（语言统一 + 适配器增强）或单独 task。

---

## 4. 不稳定场景识别（用于失败回归测试设计）

1. **空 session_context 场景**：hook/plugin 收到空 `hook_input` 或 `input`，结构化信号缺失，应返回 UNKNOWN。
2. **信号冲突场景**：结构化信号声明为 `MAIN_SESSION`，但 prompt 文本像 subagent（有 `cowork_runtime_context_id`），应以结构化信号为准还是 prompt 为准？—— 设计文档规定结构化信号优先，此场景应断言按结构化信号分类。
3. **兼容期开关关闭场景**：`_legacy_text_fallback` 禁用时，无结构化信号的输入应返回 UNKNOWN（而非 MAIN_SESSION）。
4. **opencode 无信号场景**：opencode 的 `entrySignals` 为空，所有请求都应走 fallback 或 UNKNOWN。

---

## 5. 未改动文件清单

本次调研仅执行了只读操作，未修改任何文件：

- 代码：无
- spec：无
- adapter.yaml：无
- config.yaml：无
- task 目录：仅创建了 `research/` 目录（用于存放本报告），未写入任何内容。
