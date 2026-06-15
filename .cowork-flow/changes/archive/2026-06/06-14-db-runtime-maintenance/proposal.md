# DB Runtime State And Maintenance

## Goal

Unify runtime state into SQLite as the single source of truth, keep documents as files, and add safe Dashboard/CLI maintenance entrypoints for DB growth control.

## User Value

- 用户能避免 runtime json 与 DB 投影不一致导致 Dashboard 状态漂移。
- 用户能通过 Dashboard 看到 DB 健康、垃圾数据、WAL/DB 大小。
- 用户能先 dry-run 再确认清理，避免长期使用后 DB 膨胀。
- 子代理绑定、任务会话、Dashboard 后台进程状态有统一查询面。

## Key Assumptions

- DB 统一范围是运行状态，不包括 PRD、plan、change、spec、implement/check JSONL 等审阅资产。
- 迁移必须兼容现有 `.cowork-flow/.runtime/` 文件一段时间，避免旧 hook/adapter 直接失效。
- runtime context identity 仍由 `cowork_runtime_context_id` 标识。
- Dashboard 默认仍以只读为主；维护动作必须显式进入维护区、先预览、再确认。
- SQLite WAL/事务能力足够承载当前项目级 runtime 状态。

## Problem

当前 runtime 状态分散在：

- `.cowork-flow/.runtime/subagents/*.json`
- `.cowork-flow/.runtime/sessions/*.json`
- `.cowork-flow/.runtime/dashboard.json`
- DB `agent_run`

这导致状态有双写和漂移风险。近期已修复 `agent_run` 重复写入，但真实 runtime context 与 Dashboard 投影仍是两套状态。随着正式子代理、dashboard 后台进程、维护事件增多，DB 与 runtime 文件都会增长，需要明确清理边界。

## Scope

- 新增 DB runtime 表，承载 runtime context、runtime session、dashboard process、maintenance event。
- 将 `active_task.py`、`subagent.py`、Dashboard server 的 runtime 状态读写迁到 DB。
- 保留文档文件作为 Git 可审阅资产。
- 提供 DB 维护统计、dry-run 清理、确认清理、checkpoint/vacuum。
- 同步 root/template 实现与规格。
- 增加迁移、兼容、回归测试。

## Non-Goals

- 不把 PRD/plan/change/spec 文档塞进 DB。
- 不删除任务历史、audit 历史或归档任务记录作为默认清理动作。
- 不引入全局后台 daemon。
- 不绕过 fixed-agent runtime-context 绑定协议。

## Acceptance Criteria

1. runtime context/session/dashboard process 的事实状态存在 DB 中。
2. `subagent init/bind/close/status` 可以只依赖 DB 完成正式 runtime 生命周期。
3. `task current/start/finish` 的会话状态可通过 DB session 读写。
4. Dashboard 任务详情的代理运行来自 DB runtime 源，不依赖 runtime json。
5. 兼容期旧 runtime json 可被导入 DB，且不会生成重复 runtime 记录。
6. Dashboard 提供 DB 维护页：统计、dry-run、确认清理、checkpoint/vacuum。
7. 清理默认不删除活跃任务、未关闭 runtime、未归档任务关联数据。
8. CLI 提供等价维护命令，便于无浏览器环境使用。
