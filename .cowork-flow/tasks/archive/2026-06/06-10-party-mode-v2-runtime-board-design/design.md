# Party Mode V2 Runtime Board Design

## 1. 摘要

Party Mode V2 是现有 Party Mode 的新增模式，不替换、不改造现有 `party-mode`。

V2 的核心变化是把讨论协议从 skill 文本约束提升为 Python runtime 约束：

- Python runtime 管理讨论状态、看板、轮次、schema 校验、偏题纠正事件、最大轮数和最终报告。
- 子代理不通过主持人转发观点，而是通过共享看板 API 自行读写、反驳和修正立场。
- 主持人只监控 runtime 状态、执行 host primitive、在偏题时写入纠偏事件，不综合、不转发、不裁判观点。
- 方案必须适配 Codex、Claude Code、OpenCode。Python runtime 不直接调用任一宿主专属原语，而是输出 host-neutral next actions，由当前 Host Adapter 或主持人执行。

## 2. 背景与问题

现有 Party Mode 是 skill-first advisory roundtable。它通过真实子代理提供观点，但由主会话协调：

- 第 1 轮子代理互不可见。
- 主会话整理 claim table。
- 主会话把分歧点发回子代理。
- 主会话最终综合结论。

该模式适合轻量 advisory review，但对用户提出的 V2 目标不够硬：

- skill 文本太软，不能稳定防止主持人过度介入。
- 子代理之间不是直接通过看板交流。
- 主持人仍可能转发、改写、提炼观点。
- 子代理可能礼貌性认同，而非被证据真正说服。
- 当前设计若写死 Codex `spawn_agent` / `wait_agent`，无法自然适配 Claude Code 和 OpenCode。

V2 需要成为 runtime-controlled board discussion。

## 3. 设计目标

### 3.1 功能目标

- 支持 3 个及以上子代理参与讨论。
- 子代理通过看板 API 观看本轮观点，并把自己的观点、反驳、修正写回看板。
- 子代理遇到不同意见时必须独立判断：
  - 对方确实更正确时，允许 `concede`。
  - 对方部分正确时，允许 `revise`。
  - 对方错误时，必须 `maintain` 并继续反驳。
- 主持人只监控状态和纠偏，不转发观点、不提炼观点、不做中间综合。
- 达到 `max_rounds` 后仍未收敛时，由 runtime 输出正反意见、证据和未解决分歧。
- 通过 `.cowork-flow/config.yaml` 配置 V2 默认值。

### 3.2 架构目标

- V2 与现有 V1 `party-mode` 并存。
- Runtime 状态、host action 和 board schema 可测试。
- Host-neutral：Codex、Claude Code、OpenCode 共用同一 Python runtime。
- Host-specific 原语只存在于 adapter 或宿主操作层，不进入 V2 runtime 核心。
- 不新增正式 workflow gate；Party Mode V2 仍是 advisory，不能满足 Implement / Check。

## 4. 非目标

- 不改变现有 `party-mode` skill 的行为。
- 不让 Python runtime 直接调用 Codex、Claude Code 或 OpenCode 的子代理 API。
- 不让 Party Mode V2 推进 task status、archive、commit 或替代 `cowork-implement` / `cowork-check`。
- 不在首版实现 OS 级安全隔离。当前同用户权限下，runtime 是 workflow 强约束，不是安全沙箱。
- 不实现投票式 consensus。票数不能替代证据与推理。

## 5. 总体架构

```text
--------------------+
| User / Moderator  |
+---------+----------+
          |
          | run monitor / execute host actions / warn off-topic
          v
+-----------------------------+
| party_mode_v2.py            |
| - config                    |
| - state machine             |
| - board API                 |
| - schema validation         |
| - convergence/max_rounds    |
| - host-neutral next_actions |
+--------------+--------------+
               |
               | read/write UTF-8 JSON/JSONL
               v
+-----------------------------+
| .cowork-flow/.runtime/      |
| party-mode-v2/<discussion>/ |
| - board.json                |
| - agents.json               |
| - public_round.json         |
| - audit.jsonl               |
| - prompts/*.md              |
+--------------+--------------+
               |
               | host-neutral next_actions
               v
+-----------------------------+
| Host Adapter Execution      |
| Codex / Claude / OpenCode   |
+--------------+--------------+
               |
               | child uses board API
               v
+-----------------------------+
| Discussion Children         |
| - view current board        |
| - post position             |
| - respond maintain/revise   |
| - wait / continue           |
+-----------------------------+
```

## 6. Runtime Controller

新增脚本：

```text
.cowork-flow/scripts/party_mode_v2.py
template/.cowork-flow/scripts/party_mode_v2.py
```

建议在 `.cowork-flow/scripts/run.py` 中注册显式命令：

```text
.cowork-flow/run.cmd party-v2 <command>
```

若暂不注册命令，也可通过脚本名调用：

```powershell
.\.cowork-flow\run.cmd python .cowork-flow\scripts\party_mode_v2.py <command>
```

### 6.1 命令

| 命令 | 调用者 | 作用 |
| --- | --- | --- |
| `init` | 主持人 | 创建 discussion、agents、初始 board 和 prompt 文件。 |
| `view` | 子代理 | 返回当前轮可见看板。 |
| `post` | 子代理 | 提交本轮初始观点。 |
| `respond` | 子代理 | 针对本轮其他观点提交 `maintain` / `revise` / `concede`。 |
| `wait` | 子代理 | 等待本轮进入可执行阶段。 |
| `monitor` | 主持人 | 查看状态、偏题候选、阻塞和 next actions。 |
| `warn` | 主持人 | 写入偏题纠正事件。 |
| `advance` | 主持人或 runtime helper | 尝试推进阶段或轮次。 |
| `finalize` | 主持人或 runtime helper | 生成最终报告。 |
| `close-agent` | 主持人 | 标记 agent 应关闭，并输出 host-neutral close action。 |

### 6.2 Runtime 不直接做的事

Runtime 不调用：

```text
spawn_agent
wait_agent
followup_task
close_agent
Claude Task
OpenCode task primitive
```

Runtime 只输出 `next_actions`，例如：

```json
{
  "next_actions": [
    {
      "type": "dispatch_child",
      "agent_id": "arch",
      "lens": "architecture",
      "prompt_file": ".cowork-flow/.runtime/party-mode-v2/pmv2-001/prompts/arch-r1.md"
    },
    {
      "type": "wait_children",
      "agent_ids": ["arch", "runtime", "test"]
    }
  ]
}
```

主持人或 Host Adapter 将 action 翻译成当前宿主原语。

## 7. 配置模型

新增配置段：

```yaml
party_mode_v2:
  min_agents: 3
  max_agents: 5
  max_rounds: 5
  max_rebuttal_targets_per_agent: 2
  max_drift_warnings: 2
  fresh_context_per_round: "true"
  require_current_round_only: "true"
  moderator_role: "monitor_only"
```

说明：

- 保持一层 section + scalar，适配当前 simple YAML parser。
- 布尔值可先按字符串读取，由 getter 转换。
- `min_agents` 默认不得低于 3，防止退化成双人对话。
- `fresh_context_per_round=true` 是严格 current-round-only 的推荐默认值。

配置优先级：

```text
call arguments
> task/change local config
> .cowork-flow/config.yaml
> party-mode-v2 defaults
```

## 8. 状态文件

状态目录：

```text
.cowork-flow/.runtime/party-mode-v2/<discussion_id>/
```

建议文件：

```text
board.json
agents.json
public_round.json
audit.jsonl
actions.json
prompts/
  <agent_id>-r<round>-publish.md
  <agent_id>-r<round>-respond.md
reports/
  final.md
```

### 8.1 `agents.json`

```json
{
  "schema_version": 1,
  "discussion_id": "pmv2-001",
  "agents": [
    {
      "agent_id": "arch",
      "lens": "architecture",
      "status": "pending|active|closed|closed_off_topic",
      "drift_warnings": 0,
      "host_child_id": null
    }
  ]
}
```

### 8.2 `board.json`

`board.json` 是 runtime 的 canonical state。它可以保存全量历史，但不得直接投喂给子代理。

```json
{
  "schema_version": 1,
  "discussion_id": "pmv2-001",
  "topic": "Party Mode V2 runtime board design",
  "round": {
    "current": 2,
    "max": 5,
    "phase": "publish|respond|advance|closed"
  },
  "rounds": [
    {
      "round": 1,
      "posts": [],
      "responses": [],
      "moderator_events": []
    }
  ],
  "termination": {
    "reason": null
  }
}
```

### 8.3 `public_round.json`

`public_round.json` 是子代理唯一可见的看板视图。它只包含当前轮内容。

```json
{
  "schema_version": 1,
  "discussion_id": "pmv2-001",
  "round": 2,
  "phase": "respond",
  "topic": "Party Mode V2 runtime board design",
  "visible_posts": [
    {
      "post_id": "r2-arch-p1",
      "agent_id": "arch",
      "claim": "Runtime must own board state.",
      "evidence": ["party_mode_v2.py can validate schema before accepting submissions."],
      "risk": "If host forwards opinions, moderator remains a hidden coordinator."
    }
  ],
  "visible_responses": [],
  "moderator_events": [
    {
      "type": "off_topic_warning",
      "agent_id": "risk",
      "message": "Respond to current round target_post_id."
    }
  ]
}
```

`public_round.json` 不包含：

- 历史轮次。
- 历史反驳。
- 主持人私有判断。
- final report 草稿。

## 9. 多子代理协议

V2 不是双人辩论，至少 3 个子代理。

### 9.1 Agent roster

示例：

```json
[
  { "agent_id": "arch", "lens": "architecture" },
  { "agent_id": "runtime", "lens": "runtime-control" },
  { "agent_id": "test", "lens": "testing" },
  { "agent_id": "risk", "lens": "risk-review" },
  { "agent_id": "ux", "lens": "operator-experience" }
]
```

Runtime 校验：

- `agent_count >= min_agents`。
- `agent_count <= max_agents`。
- 每个 `agent_id` 唯一。
- 每个 agent 有明确 lens。

### 9.2 轮次阶段

```text
init
  -> publish
  -> respond
  -> advance
  -> publish(next round) | closed
```

#### publish

每个子代理运行 `view` 获取任务和本轮状态，再运行 `post` 提交观点。

`post` 必填：

```json
{
  "agent_id": "arch",
  "round": 1,
  "claim": "...",
  "evidence": ["..."],
  "risk": "...",
  "tradeoff": "...",
  "acceptance_signal": "...",
  "what_would_change_my_mind": "..."
}
```

#### respond

Runtime 生成本轮 `visible_posts` 后，子代理运行 `view` 读取本轮所有观点。

每个子代理需回应 runtime 分配或自己选择的关键不同意见。为避免 N*N 爆炸，使用：

```yaml
max_rebuttal_targets_per_agent: 2
```

`respond` 必填：

```json
{
  "agent_id": "runtime",
  "round": 1,
  "target_post_id": "r1-arch-p1",
  "decision": "maintain|revise|concede",
  "my_current_position": "...",
  "opponent_claim": "...",
  "opponent_evidence_i_checked": ["..."],
  "reasoning": "...",
  "position_delta": "unchanged|narrowed|changed",
  "still_disagree": true,
  "confidence_after_review": "low|medium|high"
}
```

## 10. 防无脑认同规则

子代理不得因礼貌、迎合或为了收敛而无理由改变观点。Runtime 做结构性强制。

### 10.1 `concede`

`decision=concede` 必须包含：

```json
{
  "why_opponent_is_right": "...",
  "accepted_evidence": ["..."],
  "why_my_previous_position_failed": "...",
  "position_delta": "changed",
  "still_disagree": false
}
```

缺失任一字段，runtime 拒收：

```text
error: shallow_concession
```

### 10.2 `revise`

`decision=revise` 必须包含：

```json
{
  "accepted_part": "...",
  "rejected_part": "...",
  "updated_position": "...",
  "position_delta": "narrowed|changed"
}
```

缺失任一字段，runtime 拒收：

```text
error: vague_revision
```

### 10.3 `maintain`

`decision=maintain` 必须包含：

```json
{
  "why_opponent_is_wrong": "...",
  "counter_evidence": ["..."],
  "counter_reasoning": "...",
  "position_delta": "unchanged",
  "still_disagree": true
}
```

缺失反证或反推理，runtime 拒收：

```text
error: unsupported_rebuttal
```

### 10.4 非本轮引用

如果 response 引用非当前 round 的 `target_post_id`：

```text
error: target_not_in_current_round
```

## 11. 主持人职责

主持人是 monitor，不是 coordinator-synthesizer。

允许：

- 执行 `party-v2 monitor`。
- 根据 `next_actions` 派发、等待、列出、关闭子代理。
- 看到偏题后执行 `party-v2 warn`。
- 把 runtime 生成的 status 或 final report 发给用户。
- 在 host 不支持某 primitive 时说明 fallback。

禁止：

- 转发某个子代理的观点给另一个子代理。
- 生成 claim table 给子代理。
- 改写、压缩或润色子代理观点后再投喂。
- 代替子代理判断谁对谁错。
- 用投票决定收敛。

## 12. 偏题纠正

语义偏题无法完全由 Python 静态判断，因此采用 runtime + 主持人双层机制。

### 12.1 Runtime 可自动识别

- 缺少 `target_post_id`。
- 引用非本轮 post。
- 未按 required schema 输出。
- 输出为空或不含 evidence。
- 轮次/agent_id 不匹配。

### 12.2 主持人判断

主持人通过 `monitor` 查看候选偏题。若确认偏题，只写入纠偏事件：

```powershell
.\.cowork-flow\run.cmd party-v2 warn --discussion pmv2-001 --agent risk --reason "未回应当前轮 target_post_id"
```

事件进入 `public_round.json`：

```json
{
  "type": "off_topic_warning",
  "agent_id": "risk",
  "reason": "未回应当前轮 target_post_id",
  "required_action": "重新基于当前轮看板提交 response"
}
```

达到 `max_drift_warnings` 后，runtime 输出：

```json
{
  "next_actions": [
    {
      "type": "close_child",
      "agent_id": "risk",
      "reason": "repeated_off_topic"
    }
  ]
}
```

## 13. 收敛与停止

### 13.1 收敛条件

满足全部条件时可收敛：

- 当前轮所有 material disagreement 都有 response。
- 没有 `shallow_concession`。
- 没有 `unsupported_rebuttal`。
- 没有 blocking risk 未被回应。
- 验收信号可测。
- 连续一轮没有新增 decision-impacting disagreement。

### 13.2 停止条件

任一条件满足即停止：

- 已收敛。
- 达到 `max_rounds`。
- 有子代理连续偏题并关闭后，剩余 agent 数低于 `min_agents`。
- 多次 schema repair 仍失败。
- Host capability 不足，且 fallback 无法继续。

### 13.3 未收敛报告

达到 `max_rounds` 仍未收敛，`finalize` 输出：

```text
支持方:
反对方:
各自核心证据:
已改变观点的 agent 与原因:
坚持原观点的 agent 与原因:
未解决分歧:
用户需要裁决的价值取舍:
stop_reason: max_rounds_unconverged
```

## 14. Host-neutral Actions

V2 action schema 不出现宿主专属工具名。

```json
{
  "schema_version": 1,
  "discussion_id": "pmv2-001",
  "next_actions": [
    {
      "type": "dispatch_child",
      "agent_id": "arch",
      "agent_kind": "advisory",
      "prompt_file": ".cowork-flow/.runtime/party-mode-v2/pmv2-001/prompts/arch-r1-publish.md"
    },
    {
      "type": "send_control_message",
      "agent_id": "arch",
      "message_kind": "continue_board_loop",
      "prompt_file": ".cowork-flow/.runtime/party-mode-v2/pmv2-001/prompts/arch-r1-respond.md"
    },
    {
      "type": "wait_children",
      "agent_ids": ["arch", "runtime", "test"]
    },
    {
      "type": "close_child",
      "agent_id": "risk",
      "reason": "repeated_off_topic"
    }
  ]
}
```

## 15. Host 适配

### 15.1 Codex

Adapter 能力：

- `dispatchSubagent: native`
- `freshChildContext: native`
- `sendFollowup: native`
- `waitChild: native`
- `listChildren: native`
- `cancelChild: native`

动作映射：

| Host-neutral action | Codex primitive |
| --- | --- |
| `dispatch_child` | `spawn_agent` |
| `send_control_message` | `followup_task` 或 `send_message` |
| `wait_children` | `wait_agent` |
| `list_children` | `list_agents` |
| `close_child` | `close_agent` |

### 15.2 Claude Code

Adapter 能力：

- 子代理派发为 `subagent`。
- skills 路径为 `.claude/skills`。
- commands 路径为 `.claude/commands`。
- state injection 由 hooks 外部实现。

动作映射：

| Host-neutral action | Claude Code route |
| --- | --- |
| `dispatch_child` | Claude subagent / command |
| `send_control_message` | host-supported follow-up 或命令提示 |
| `wait_children` | Claude subagent completion |
| `close_child` | host cancellation；缺失时 runtime 标记 `closed_required` |

V2 skill 必须同步到：

```text
.claude/skills/party-mode-v2/SKILL.md
template/.claude/skills/party-mode-v2/SKILL.md
```

### 15.3 OpenCode

Adapter 能力：

- 子代理派发为 `task`。
- assets 路径为 `.opencode/agents`、`.opencode/commands`、`.opencode/plugins`。
- `sendFollowup` 为 shim。
- `backgroundChild` 为 experimental。

动作映射：

| Host-neutral action | OpenCode route |
| --- | --- |
| `dispatch_child` | `.opencode/commands` + `.opencode/agents` |
| `send_control_message` | follow-up shim 或 command prompt |
| `wait_children` | OpenCode task result collection |
| `close_child` | OpenCode cancel/close primitive |

OpenCode 侧需要同步：

```text
.opencode/commands/party-mode-v2.md
.opencode/agents/<advisory-agent>.md 或复用现有 advisory agent
template/.opencode/...
```

若 OpenCode 当前 host 无法稳定 follow-up，则 runtime 应输出 manual next action，不假装自动化。

## 16. Current-round-only 隔离

### 16.1 默认严格模式

推荐默认：

```yaml
fresh_context_per_round: "true"
```

原因：

- 如果复用同一 live child，即使 `view` 只返回当前轮，模型上下文仍可能记住上一轮。
- Fresh context per round 更符合“只看本轮看板”。

逻辑身份用 `agent_id` 维持，物理 child 可以每轮重建。

### 16.2 连续身份降级模式

如果用户更重视同一 live child 的连续人格，可设置：

```yaml
fresh_context_per_round: "false"
```

风险必须明确：

- board API 不返回历史。
- 但模型上下文可能残留历史。
- 这是 soft guarantee，不是 hard guarantee。

## 17. 安全与边界

当前工作区内所有子代理通常使用同一用户权限。Python runtime 可以强约束协议入口，但不能提供 OS 级安全隔离。

因此：

- 不把 `board.json` 路径写入 child prompt。
- child prompt 只给 board API 命令。
- Runtime 拒收非 API 格式输出。
- 测试确保 child-visible prompt 不包含历史文件内容。

若未来需要真正防止 child 搜索 `.runtime` 文件，需要 host 提供：

- per-child filesystem sandbox。
- scoped attachment。
- read-once metadata。
- 或独立 OS user / process isolation。

这些不是 V2 首版目标。

## 18. 文件落点

### 18.1 Root

```text
.agents/skills/party-mode-v2/SKILL.md
.claude/skills/party-mode-v2/SKILL.md
.cowork-flow/scripts/party_mode_v2.py
.cowork-flow/spec/party-mode-v2-actions.schema.json
.cowork-flow/spec/party-mode-v2-board.md
.cowork-flow/config.yaml
.cowork-flow/workflow.md
.cowork-flow/spec/subagent-dispatch.md
.opencode/commands/party-mode-v2.md
```

### 18.2 Template

```text
template/.agents/skills/party-mode-v2/SKILL.md
template/.claude/skills/party-mode-v2/SKILL.md
template/.cowork-flow/scripts/party_mode_v2.py
template/.cowork-flow/spec/party-mode-v2-actions.schema.json
template/.cowork-flow/spec/party-mode-v2-board.md
template/.cowork-flow/config.yaml
template/.cowork-flow/workflow.md
template/.cowork-flow/spec/subagent-dispatch.md
template/.opencode/commands/party-mode-v2.md
```

### 18.3 不应修改

- 不修改现有 `party-mode` V1 语义。
- 不把 Codex 工具名写入 `workflow.md`。
- 不新增 adapter capability，除非未来实现 Python 直接 host bridge。

## 19. Skill 文本定位

`party-mode-v2/SKILL.md` 应保持薄入口。

它只说明：

- 必须使用 `party-v2 init/monitor/advance/finalize`。
- 主持人不得转发或综合观点。
- 子代理必须通过 board API 读写。
- 当前轮看板由 runtime 提供。
- Runtime 校验失败时不得手动绕过。
- Party Mode V2 仍是 advisory。

不在 skill 内复制完整状态机，防止 skill 和 Python runtime 成为两套协议。

## 20. 测试计划

### 20.1 新增 `tests/test_party_mode_v2.py`

覆盖：

- `party_mode_v2.max_rounds` 从 config 读取。
- `min_agents >= 3`。
- `view` 只返回 current round。
- 非当前 round `target_post_id` 被拒。
- 无证据 `concede` 被拒为 `shallow_concession`。
- 无反证 `maintain` 被拒为 `unsupported_rebuttal`。
- `revise` 缺少 accepted/rejected part 被拒。
- `max_rounds` 后未收敛输出正反意见。
- `monitor` 不输出主持人综合观点。
- `next_actions` 不含 Codex/Claude/OpenCode 专属工具名。

### 20.2 扩展现有测试

`tests/test_cowork_agents.py`：

- 增加 `party-mode-v2` 四份 skill mirror 断言。
- 保留 V1 Party Mode markers 不变。

`tests/test_workflow_parallel_sessions.py`：

- 增加 V2 advisory / host-neutral workflow markers。
- 继续禁止 workflow 出现宿主专属工具名。

`tests/test_host_adapters.py`：

- 确认 Codex、Claude Code、OpenCode adapter 具备 V2 需要的通用能力或 fallback。
- 不要求新增 capability。

OpenCode / Claude asset tests：

- 确认 template mirror 同步。
- 确认 `.claude/skills` 与 `.opencode/commands` 有 V2 入口。

### 20.3 验证命令

```powershell
rtk pytest tests/test_party_mode_v2.py tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py
rtk git diff --check
```

若当前项目仍使用 unittest 聚合，也需执行对应的现有 test runner。

## 21. 迁移策略

1. 新增 V2 文档与 runtime，不触碰 V1。
2. 新增 V2 skill mirrors 和 host assets。
3. 加入 config defaults。
4. 加入 runtime tests。
5. 加入 host-neutral tests。
6. 文档标明 V1 与 V2 选择方式：
   - `$party-mode`：轻量 skill-first advisory roundtable。
   - `$party-mode-v2`：runtime board-controlled multi-agent debate。

## 22. 被拒方案

### 22.1 直接改现有 Party Mode

拒绝。V1 已被测试和文档锁定，且用户明确要求不改变当前模式。

### 22.2 主持人继续 claim table 转发

拒绝。这会让主持人成为观点中转和综合者，违背 V2 “只监控和纠偏”。

### 22.3 子代理直接读写 `board.json`

拒绝。会暴露历史轮次，也绕过 runtime schema validation。

### 22.4 投票式收敛

拒绝。子代理数量不能代表正确性，收敛必须基于证据、分歧处理和验收信号。

### 22.5 新增 adapter capability 作为首版依赖

拒绝。当前 Codex、Claude Code、OpenCode 已有足够通用 primitive 支持 host-mediated execution。新增 capability 会扩大影响面。

## 23. 开放问题

- 是否需要在 `party_mode_v2.py` 首版就注册到 `run.py`，还是先允许脚本名调用？
- OpenCode `sendFollowup` 是 shim，是否需要为 V2 单独定义更明确的 manual follow-up path？
- Claude Code 的 close/cancel 能力在不同版本下是否稳定？若不稳定，是否统一用 `closed_required` 状态提示主持人手动关闭？
- 是否需要在 `.cowork-flow/spec/capabilities.md` 中增加 Party Mode V2 的非正式 advisory capability 说明，还是只在 V2 spec 中说明？
- 若用户要求无人主持全自动调度，是否另开 host bridge 设计？

## 24. 首版验收

Party Mode V2 首版完成时，应满足：

- V1 `party-mode` 所有测试继续通过。
- `$party-mode-v2` 入口存在于 Codex/Claude/OpenCode 相关资产。
- Python runtime 能创建 discussion、agent roster、current round board。
- 至少 3 个 agent 的 publish/respond 流程可被测试模拟。
- Runtime 拒绝无理由认同、无证据反驳和非本轮引用。
- Runtime 输出 host-neutral next actions。
- 主持人监控输出不包含观点综合。
- `max_rounds` 未收敛时生成正反意见报告。
- 文档清楚说明当前权限模型下的非安全沙箱边界。
