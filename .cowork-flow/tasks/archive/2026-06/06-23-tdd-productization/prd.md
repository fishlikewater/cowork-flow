# TDD 产品化与门禁改造 PRD

## 目标

将 `cowork-flow` 的 TDD、测试意图、编码规范和流程状态推进升级为可执行、可验证、可阻断的产品能力。

## 用户价值

- AI 不能跳过实现、检查和完成阶段的关键流程。
- 行为变更必须先证明测试会失败，再实现并证明测试变绿。
- Review 必须检查测试是否真的保护业务行为。
- 编码规范违规不能被带入完成阶段。

## 非目标

- 不重写 Node CLI。
- 不替换 host adapter 协议。
- 不强制纯文档和格式化任务使用 TDD。

## 关键假设

- 本任务为父任务，实际实现由子任务分阶段完成。
- L2 change 为 `.cowork-flow/changes/06-23-tdd-productization`。
- 开发计划为 `.cowork-flow/plans/2026-06-23-tdd-productization.md`。

## 范围边界

范围内：

- Gate Engine 与状态迁移。
- TDD evidence 与 `tdd` skill。
- 测试意图审查。
- 编码规范强约束。
- 产品级验收套件。

范围外：

- 一次性重写全部 runtime。
- 修改 adapter 协议核心语义。

## 子任务

- `.cowork-flow/tasks/06-23-gate-engine-state-machine`
- `.cowork-flow/tasks/06-23-tdd-skill-evidence`
- `.cowork-flow/tasks/06-23-test-intent-review-gate`
- `.cowork-flow/tasks/06-23-coding-standards-gate`
- `.cowork-flow/tasks/06-23-product-validation-suite`

## 验收标准

- AC-001: 所有子任务完成并通过各自 PRD 验收。
- AC-002: `task review` 能阻断缺少 TDD evidence 的行为变更。
- AC-003: `task review` / `task complete` 能阻断编码规范 blocker。
- AC-004: 无意义测试不能满足 gate。
- AC-005: root/template 资产保持同步。
- AC-006: 端到端验收覆盖 happy path、跳步失败、TDD 缺失、无意义测试、编码违规、fresh install 和 Windows `run.cmd`。

## 验证方式

```powershell
.\.cowork-flow\run.cmd change validate 06-23-tdd-productization
.\.cowork-flow\run.cmd task validate .cowork-flow/tasks/06-23-tdd-productization
python -m unittest discover tests -v
npm test
npm run test:template
npm run pack:check
git diff --check
```
