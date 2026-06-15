# Polish Dashboard Database Maintenance View

## Goal

把数据库维护从任务看板主流程中拆出来，改成独立、清晰、中文化的维护视图，避免与任务状态列混在一起导致页面拥挤。

## Scope

- Dashboard 顶部增加视图切换：任务看板 / 数据库维护。
- 任务看板视图只显示任务筛选、看板列、任务详情。
- 数据库维护视图独立展示数据库概览、垃圾扫描、确认清理、checkpoint、vacuum。
- 维护视图视觉上更像工具页：清晰分区、紧凑数据卡、操作区、预览输出区。
- root/template 静态资源保持同步。

## Non-Goals

- 不改变 DB 清理策略。
- 不新增 destructive one-click cleanup。
- 不修改 task/runtime 后端状态语义。

## Acceptance Criteria

1. “数据库维护”不再作为任务看板中的插入面板。
2. 切换到数据库维护视图后，任务列和任务详情不显示。
3. 维护页面有独立标题、状态概览、清理候选、维护操作和预览输出。
4. 页面文案保持简体中文。
5. root/template dashboard 静态资源一致。
6. 相关 Dashboard 测试覆盖视图切换和维护页结构。

## Verification

- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_dashboard -v`
- `rtk npm run test:template`
- `rtk git diff --check`
