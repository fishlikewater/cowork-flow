# 清理 entry contract 残留

## 目标

删除不再有运行时实现消费的 `entry-contract.md` / `COWORK_ENTRY_CONTRACT_V1`，把仍有效的入口边界规则并入现有 runtime-context / workflow-state 契约，并扫描当前架构下是否还有同类残留。

## 范围

- 删除 root/template `entry-contract.md`。
- 从 contract registry、hook/plugin fallback digest、adapter schema/yaml、doctor 和测试中移除 `COWORK_ENTRY_CONTRACT_V1`。
- 保留并迁移有效规则：formal subagent 只能由 runtime context 识别；未知入口不得执行工作流突变。
- 扫描活跃文档、脚本、测试中的旧契约名、旧分类对象和类似未消费残留。

## 非目标

- 不重建 entry classifier。
- 不新增替代 contract。
- 不清理历史 archive、plans、workspace journal 中的记录。

## 验收标准

- AC-001: 活跃 root/template 代码与文档不再引用 `entry-contract.md` 或 `COWORK_ENTRY_CONTRACT_V1`。
- AC-002: adapter schema/yaml、hook/plugin digest、doctor 和测试仍能表达 runtime-context 边界。
- AC-003: 扫描确认没有同类“只有契约名/对象、无实现消费”的活跃残留；若有则同步删除或明确保留理由。
- AC-004: focused tests、`git diff --check` 和 `npm run test:all` 通过。
