# Fix Windows update and sync

## Goal

修复 Windows 环境下 `cowork-flow update` 无法正常查询 npm 最新版本的问题，并调整 `cowork-flow sync` 对 `.cowork-flow` 目录的保护规则。

## Requirements

- `update` 在 Windows 下调用 npm 时应使用兼容 npm shim 的子进程调用方式。
- `update --global --yes` 在 Windows 下执行全局安装时也应使用相同的兼容调用方式。
- npm 查询真实失败时，继续保留当前降级提示和退出码行为。
- `sync` 对 `.cowork-flow` 目录只保护以下路径：
  - `.cowork-flow/changes/`
  - `.cowork-flow/plans/`
  - `.cowork-flow/spec/`
  - `.cowork-flow/tasks/`
  - `.cowork-flow/workspace/`
  - `.cowork-flow/config.yaml`
- `.cowork-flow/scripts/`、`.cowork-flow/workflow.md`、`.cowork-flow/agent-team/`、`.cowork-flow/run`、`.cowork-flow/run.cmd` 等模板文件应允许被 sync 刷新。
- sync 不删除目标项目中模板不存在的自有文件。

## Acceptance Criteria

- [x] `test/update.test.js` 覆盖 Windows npm 调用选项。
- [x] `test/sync.test.js` 覆盖 `.cowork-flow` 保护白名单与 scripts 刷新行为。
- [x] `node --test --test-isolation=none test/update.test.js` 通过。
- [x] `node --test --test-isolation=none test/sync.test.js` 通过。
- [x] `npm test -- --test-isolation=none` 通过。
- [x] `.\.cowork-flow\run.cmd change validate fix-windows-update-sync` 通过。

## Technical Notes

- 本任务分级为 `L1`，对应 change: `.cowork-flow/changes/fix-windows-update-sync/`。
- 实现计划位于 `.cowork-flow/plans/2026-05-21-fix-windows-update-sync.md`。
- 保持现有 CLI 模块结构，不引入新依赖，不改变 `init` 行为。
