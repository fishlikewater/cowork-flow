# PRD: 审计问题真实性验证与修复

逐条验证 5 个审计报告的 38+ 个发现，确认真实存在后修复。

## 验收标准

- AC-001: `cowork-flow init --force` 不覆盖已有 `.cowork-flow/.developer`，仍保留既有开发者身份和初始化时间。
- AC-002: root `.cowork-flow` runtime/spec/host assets 与 `template/.cowork-flow`、host template assets 保持同步，发布包不会携带旧模板。
- AC-003: 任务生命周期状态命名收敛到当前约定；测试、workflow-state 模板、hook 输出不再混用已废弃状态。
- AC-004: 标准验证命令 `npm test`、`npm run test:template`、`npm run pack:check` 通过；无法纳入的集成测试依赖有明确说明。

## 修复优先级

逐条走：CRITICAL → HIGH → MEDIUM → LOW
