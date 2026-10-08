# Task Board Contract

**共享看板：`task next --list --json` 与 MCP `task_list` 是同一份看板事实的两种渲染——第二个执行者不跑 `run state` 就能看出"谁在占用、有没有卡住、证据到哪了"。依赖边把任务的先后关系变成 start 的可裁决门禁。**

单一实现（`services/task_board.py` + `services/task_graph.py`）供两个表面复用，字段值必须同源一致。

## 看板字段（每条任务记录新增）

| 字段 | 含义 | 边界 |
|---|---|---|
| `executor` | 当前归属执行者（`task.json.executor`，无则 `null`） | 由 start / `--takeover` / `--adopt` 写入 |
| `ownerSessionActive` | 是否有会话绑定这条任务（`sessions/` 中 `active_task_path` 指向它） | **提示位，非裁决**：显式传目录工作的会话永不绑定，`false` 只表示"无绑定指向"，不表示任务已成孤儿 |
| `evidenceCoverage` | `{total, withEvidence, missing[]}`；未声明 AC 的任务为 `null` | 与 `run state` / 注入覆盖行同源（`ac_evidence`） |
| `blocked` | 是否存在未完成依赖 | 见下"依赖语义" |
| `blockedBy` | 未完成依赖的任务名列表 | 按声明顺序；缺失目标也算未完成 |

既有字段（`name`/`path`/`status`/`assignee`/`parent`/`children`/`childrenDone`/`childrenTotal`/`depth`/`active`）语义不变。

## 依赖边

**声明**（唯一的运行时入口，创建时一次定下）：

```bash
./.cowork-flow/run task next --run --title "<title>" --slug <slug> \
  --depends-on <task-name> [--depends-on <task-name> ...]
```

- `--depends-on` 取**完整任务目录名**（`task next --list` 的 `name` 列；不猜前缀/后缀），可重复。
- 声明期 fail-closed，任一校验失败则创建失败且不落盘：
  - `TASK-CREATE-DEPENDENCY-001` 目标不存在（在 `tasks/` 与 `tasks/archive/**` 都找不到）；
  - `TASK-CREATE-DEPENDENCY-002` 自依赖（写自己的目录名或 slug）；
  - `TASK-CREATE-DEPENDENCY-003` 环（沿着既有 `dependsOn` 边能回到新任务）。
- 写入 `task.json` 的 `dependsOn`（字符串数组，归一化去重保序）；缺失该字段等价于无依赖——存量任务零影响。
- 跨仓库/跨项目依赖不支持；改写依赖没有运行时命令（1.9.x 候补），修复路径是本地编辑 `task.json`（事实层文件，手改合法；改完环或悬空目标会在 start 处按未完成处理）。

**门禁**（只约束进入 `in_progress` 这一个迁移点）：

- 依赖项状态全部为 `completed` 才允许 start；归档任务保留 `completed`，因此归档的完成依赖仍然有效。
- 未完成时 fail-closed：`LIFECYCLE-DEPENDENCY-001`，blocker 文本 `task depends on unfinished work: <names>`；同一条文本同时出现在 `task next <dir>` 的导航 payload（blockers）与 `--run` 的报错里。
- 已启动的任务不受回溯影响（检查发生在 start 的 preflight；幂等重跑不经过它）。
- `--adopt`、review、complete 不受依赖约束——依赖只回答"能不能开始"，不回答"能不能收尾"。
- 导航形态：planning 状态且存在 blocker（含依赖）时，`task next <dir>` 报的动作是 `edit_planning_artifacts`（与 readiness blocker 既有语义一致：被阻塞期间先做规划工作），blocker 文本是事实来源。

## 交接凭证（adopt 输出）

`task next <dir> --run --adopt` 成功后除归属重绑与基线重置（见 `task-adopt.md`）外，打印 Handover 段：原执行者 → 新执行者、原基线 → 新基线、剩余未勾选 AC 列表与计数、证据覆盖 `n/m`。收养者不需要额外查询即可接手。
