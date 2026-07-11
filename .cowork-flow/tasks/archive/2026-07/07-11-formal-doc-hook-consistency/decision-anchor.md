# 正式版文档与 Hook 一致性清理

## 目标

让正式版文档、ZCode hook、测试命名和 README/workflow 术语与当前运行时行为保持一致，移除会误导维护者或 agent 的兼容期残留。

## 范围

- 更新 `decision-anchor` 合约文档，不再声明 `task start` 自动迁移 `prd.md`。
- 移除 ZCode hook 注入阶段自动 scaffold 项目文件的写入副作用，改为只读诊断。
- 将旧 PRD 测试命名改为 `decision-anchor` 语义。
- 将 README/workflow 中“兼容升级/兼容迁移”措辞收敛为正式版 obsolete cleanup / 读取边界保留。

## 非目标

- 不删除 `obsoleteFiles` 清理能力；它仍负责清理已安装项目里的旧受管资产。
- 不删除状态读取边界对旧 session/task/runtime-context 的兼容保护测试。
- 不改变 ZCode 显式安装或 sync 的模板分发能力。

## 验收标准

- [ ] **AC-001**：`decision-anchor` 合约不再承诺自动迁移 `prd.md`，而是说明正式版缺失 `decision-anchor.md` 时 fail-closed。
- [ ] **AC-002**：ZCode hook 注入不再创建 `.cowork-flow/` 或复制 scaffold 文件；未初始化项目只输出诊断。
- [ ] **AC-003**：任务启动 blocker 测试命名与文案使用 `decision-anchor`，不再把正式 artifact 称为 PRD。
- [ ] **AC-004**：README/workflow 对旧资产处理的措辞表达为 obsolete cleanup / 读取边界保留，而非兼容期入口。
- [ ] **AC-005**：聚焦测试与完整 `npm run test:all` 通过。
