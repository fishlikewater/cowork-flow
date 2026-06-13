# Dashboard Runtime Control

## Goal

Make the Dashboard reflect real formal subagent runtime state, fix archived-task browsing, and add project-local CLI lifecycle commands for the Dashboard server.

## User Value

- 用户能在任务详情里看到真实 `cowork-*` 子代理运行状态，而不是只有空白区域。
- 用户能以历史列表方式查看归档任务，减少看板空白和扫描成本。
- 用户能通过 CLI 开启/关闭当前项目 Dashboard，不误控其他项目。

## Key Assumptions

- Dashboard 仍是只读观察面，生命周期修改继续走 CLI。
- `agent_run` 表是正式代理运行状态的唯一持久化来源。
- 当前项目和模板项目需要保持行为一致。
- 后台 Dashboard 进程状态只需要保存到当前 repo 的 `.cowork-flow/.runtime/`。

## Problem

1. Task detail has an agent run area, but direct formal `subagent init` does not create `agent_run`; only `spawn-family` does. Real child runs therefore have no visible Dashboard change until a family helper is used.
2. Archived tasks render as a normal left-aligned board column. When the archived filter is selected, the right side is mostly empty and the list is hard to scan.
3. Selecting the archived status tab mutates the `showArchived` checkbox. Switching back to another tab leaves archived tasks visible through stale checkbox state.
4. The Dashboard server can be run in the foreground, but there is no project-scoped `dashboard start/status/stop` command. Users need a simple way to open and close the current project's Dashboard without starting a global service.

## Scope

- Record `agent_run` rows for direct formal `subagent init --execution-task-dir ...`.
- Keep existing bind/update/close status propagation.
- Redesign archived rendering as a full-width history view instead of a narrow board column.
- Decouple status tabs from the archived checkbox.
- Add `dashboard serve/start/status/stop` while preserving the current foreground `dashboard` behavior.
- Keep root/template script and static resources synchronized.
- Add tests for subagent runtime recording, Dashboard CLI lifecycle, static UI contracts, and template parity.

## Non-Goals

- No Dashboard mutation controls for task lifecycle.
- No global daemon or cross-project Dashboard process manager.
- No replacement of `agent_run` schema.
- No host-specific browser opening behavior.

## Acceptance Criteria

1. Direct formal `subagent init` for an existing task creates one `agent_run` row keyed by runtime context id.
2. `subagent bind` and `subagent close` update that run to `bound` and `closed`.
3. Task detail API continues exposing real `agentRuns` for the selected task.
4. The archived tab displays archived tasks in a full-width history layout.
5. Selecting the archived tab does not check `显示归档`; switching away does not keep archived visible unless the checkbox was explicitly selected.
6. `dashboard start`, `dashboard status`, and `dashboard stop` manage only the current repository's `.cowork-flow/.runtime/dashboard.json`.
