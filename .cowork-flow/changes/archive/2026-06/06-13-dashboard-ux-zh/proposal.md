# 06-13-dashboard-ux-zh

## Goal

优化只读 Dashboard 的信息架构、任务详情和响应式体验，并将页面文案切换为简体中文。

## User Value

用户打开 Dashboard 后应能快速判断当前工作是否有进行中、待检查或阻塞事项；查看历史任务时不被 Archived 长列表淹没；点击任务后能直接看到审计链、子任务和代理运行摘要。

## Current Problems

- 当前无活动任务时，Archived 列占满首屏，空列和历史列权重失衡。
- 窄屏下详情区位于页面底部，点击任务后反馈弱。
- 任务卡片使用 `G/F/P/H` 缩写，含义不直观。
- `/api/task/<id>` 已返回 audit、children、agentRuns，但 UI 只显示数量。

## Scope

- 改造 Dashboard 静态前端布局、交互和中文文案。
- 保持 Dashboard 只读，不新增任何写 API。
- 同步 root 与 template 的 Dashboard 静态资源。
- 增加 focused 静态资源回归测试，覆盖中文 UI、过滤控件、详情内容和模板同步。

## Non-Goals

- 不改 FlowStore 写入模型。
- 不新增任务生命周期操作按钮。
- 不改 Dashboard API 数据结构，除非验证发现前端无法满足最低展示要求。

## Acceptance

1. 页面主要文案为简体中文。
2. 任务列表默认突出非 archived 工作，Archived 可切换查看，不压垮首屏。
3. 点击任务后详情在当前视口可见，窄屏可作为 drawer/面板展示。
4. 详情展示基本信息、审计时间线、子任务摘要、代理运行摘要和阻塞状态。
5. UI 保持只读；现有 read-only API 测试继续通过。
