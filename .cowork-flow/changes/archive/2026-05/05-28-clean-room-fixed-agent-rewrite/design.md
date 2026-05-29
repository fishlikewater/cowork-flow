# Design: Clean-room Fixed-Agent Rewrite

## Assumptions

- 用户接受大刀阔斧重构。
- 项目继续使用 MIT 授权空间，因此不能复制 external project AGPL 代码。
- 目录命名保留 cowork-flow 风格。
- 旧模型中不符合新主线的代码可以删除。

## Architecture

新架构以 task 文件为中心，固定职责子 agent 为执行单元，主会话为协调者。

```text
main session
  -> task/prd/context
  -> cowork-research  (optional)
  -> cowork-implement
  -> cowork-check
  -> update spec / verify / commit / archive
```

`agent-team` 不再是默认执行引擎。它的旧状态机如果没有新用途，应从脚本、skills、模板和测试中移除。

## Current Task State

新增 session-scoped active task：

```text
.cowork-flow/.runtime/sessions/<context-key>.json
```

文件内容只保存当前 session 必需状态：

```json
{
  "active_task_path": ".cowork-flow/tasks/05-28-example",
  "platform": "codex",
  "last_seen_at": "2026-05-28T00:00:00Z"
}
```

`context-key` 来源：

1. `COWORK_FLOW_CONTEXT_ID`
2. `CODEX_SESSION_ID`
3. `CODEX_THREAD_ID`

没有 key 时，命令失败。系统不猜测、不 fallback 到 `.current-task`。

## Task Lifecycle

### Create

`task create` 创建 task 目录，状态为 `planning`。

它不进入实现阶段，也不自动触发子 agent。

### Plan

主会话写 `prd.md`，必要时写 `info.md` 和 `research/*.md`。

随后维护：

- `implement.jsonl`
- `check.jsonl`

这两个文件只列 spec/research，不列即将修改的代码文件。

### Start

`task start <task>`：

- 校验 `prd.md` 与上下文文件存在
- 写入当前 session pointer
- 将状态置为 `in_progress`

### Execute

主会话默认派发 `cowork-implement`。

派发消息必须以 `Active task: <task>` 开头，并要求子 agent 不再派发其他 agent。

### Check

主会话派发 `cowork-check`。

`cowork-check` 可以修复问题，但不能提交或归档。

### Finish

主会话负责：

- 最终验证
- 判断是否更新 `.cowork-flow/spec/`
- 提交
- 归档 task
- 记录 session

## Context Loading

子 agent 自加载上下文：

1. 从首行解析 `Active task: <task>`
2. 读取 `prd.md`
3. 读取可选 `info.md`
4. 读取对应 JSONL
5. 读取 JSONL 中列出的 spec/research 文件

如果 JSONL 为空或缺失：

- `cowork-implement` / `cowork-check` 不应静默猜测已完整
- 可以读取 `prd.md` 与 spec index 继续，但必须在报告中标记上下文未精确 curated

## Agent Definitions

### cowork-research

职责：研究并持久化结果。

写权限仅限当前任务的 `research/`。

### cowork-implement

职责：实现需求与测试。

禁止：

- `spawn_agent`
- `wait_agent`
- `close_agent`
- `list_agents`
- `task start`
- `task archive`
- git commit

### cowork-check

职责：审查、修复、验证。

禁止项与 implement 相同。

Codex agent 配置应在能力上关闭多 agent 工具。若当前宿主不支持结构性禁用该能力，该宿主模式不得宣称已满足防递归约束；实现计划必须选择可执行的结构约束或禁用对应 agent 模式。

## Workflow and Skill Changes

需要重写：

- `.agent/skills/start/SKILL.md`
- `.agent/skills/finish-work/SKILL.md`
- `.agent/skills/check-cross-layer/SKILL.md` 中旧 agent-team 默认路径
- `template/.agent/skills/**`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`

需要新增或替换：

- `cowork-research` agent 定义
- `cowork-implement` agent 定义
- `cowork-check` agent 定义

需要删除：

- `agent-team-execution` skill
- 只服务旧 agent-team 状态机的 scripts/config/tests/docs

## Testing Plan

先写失败测试，再实现：

1. `task start/current/finish` 只使用 `.runtime/sessions/<context-key>.json`
2. 无 context key 时命令失败
3. `.current-task` 不再生成
4. `resume` 输出 session-scoped 当前任务
5. workflow 不再默认推荐 agent-team
6. 子 agent 文档包含 `Active task:`、leaf executor、禁止再派发
7. 删除 agent-team 后无测试或模板引用旧路径

最终验证：

```bash
npm test
npm run test:template
npm run pack:check
npm run test:all
```

## Migration Notes

这是破坏性重构。旧 `.current-task` 和 agent-team runtime 不做迁移。

已有活跃任务需要手动重新运行：

```bash
set COWORK_FLOW_CONTEXT_ID=<session-name>
.\.cowork-flow\run.cmd task start <task>
```

PowerShell 用户使用：

```powershell
$env:COWORK_FLOW_CONTEXT_ID = "<session-name>"
.\.cowork-flow\run.cmd task start <task>
```
