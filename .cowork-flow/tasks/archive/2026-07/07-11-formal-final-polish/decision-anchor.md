# 正式版最终术语与结构收口

## 目标

完成正式版提示面和运行时内部命名的最后一轮收口：只在历史迁移说明和回归测试中保留 `prd.md`，其余公共提示、规范参考和内部变量统一使用 `decision-anchor` / acceptance criteria 语义；同时补充模板同步防漂移测试，并降低上下文渲染复杂度 warning 噪音。

## 范围

- 清理 public docs / agent prompts / workflow-state templates 中残余 `PRD` 术语。
- 将 `git_context.py` 内部 `has_prd`、`prd_path`、`include_prd_hint` 等变量重命名为 `decision_anchor` 语义。
- 补充测试，明确 template workflow 与 ZCode scaffold workflow 必须保持一致。
- 拆分 `git_context.py` 中可低风险拆分的 resume/context 渲染 helper，减少稳定复杂度 warning。

## 非目标

- 不删除 `decision-anchor` 合约中关于旧 `prd.md` 不自动迁移的历史说明。
- 不删除 `test_decision_anchor.py` 中验证旧 `prd.md` 不被自动迁移的回归测试。
- 不重构 `party_mode_v2.py` 或 batch runtime；这些属于更高风险的大型结构优化。
- 不删除 `obsoleteFiles`、旧状态读取边界测试或 adapter/digest fail-safe fallback。

## 验收标准

- [ ] **AC-001**：除 `decision-anchor` 合约历史说明和专门回归测试外，正式提示面不再使用 `PRD` 术语。
- [ ] **AC-002**：`git_context.py` 的 decision-anchor 状态和路径变量使用当前术语，用户可见输出保持不变。
- [ ] **AC-003**：template workflow 与 ZCode scaffold workflow 有测试防漂移。
- [ ] **AC-004**：上下文渲染相关复杂度 warning 至少减少本轮触及函数的稳定噪音。
- [ ] **AC-005**：聚焦测试与完整 `npm run test:all` 通过。
