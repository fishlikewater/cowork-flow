
# Post-roadmap hardening design

## 设计原则

1. **历史材料可保留，边界必须清晰**：迁移期设计文档可以记录旧方案和兼容策略，但必须在文档入口声明它不是当前运行时权威。
2. **allowlist 是契约，不是垃圾桶**：sync gate 中的 legacy 例外必须能解释为什么存在，并通过测试证明不会掩盖真实 drift。
3. **状态一致性优先于形式整齐**：基线任务是否归档要遵守当前 lifecycle/archive 规则，不能为了视觉一致性破坏任务/change 关联。
4. **串行执行**：三个 follow-up 任务文件重叠度低，但都触碰流程状态或文档契约；为了避免收口混乱，按顺序执行。

## 任务拆分

### 1. Historical doc boundaries

- 修改 `FLOW-UPGRADE-DESIGN.md`，增加历史/迁移设计说明。
- 说明当前权威文档：`README.md`、`.cowork-flow/workflow.md`、`.cowork-flow/spec/core/dispatch.md`、`.cowork-flow/spec/core/lifecycle.md`。
- 用 focused scan 验证当前权威文档无旧状态权威残留。

### 2. Sync gate legacy allowlist

- 审查 `src/lib/template-sync-gate.js` 中 `legacy flattened` allowlist。
- 检查对应 root/template 路径是否仍存在，以及测试是否覆盖允许差异。
- 删除已不需要的例外；保留的例外补充更具体 reason 或测试断言。
- 验证 `npm test -- test/template-sync-gate.test.js test/sync.test.js` 或实际存在的相关测试集合。

### 3. Baseline archive consistency

- 检查 `07-11-opt-baseline-risk-map` 的当前状态、关联 change 是否已归档、是否存在归档副本。
- 如果 archive 命令可安全执行，则归档该任务；否则在计划/任务记录中说明为何保留 completed。
- 验证 `task list` / `task current` / `git status --short`。

## 风险

- 历史文档文字过度改写会丢失迁移背景：只加边界说明，不重写主体。
- allowlist 收窄可能导致 package/sync 测试失败：先补/运行 focused tests，再做删除。
- 归档 baseline 任务可能影响旧 change 指针：先检查 change 已归档，再执行 archive 或记录保留原因。
