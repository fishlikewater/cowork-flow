# 正式版语义与提示面收口

## 目标

让正式版 workflow、agent 提示、运行时上下文提示和测试断言统一使用 `decision-anchor` / acceptance criteria 语义，移除会让维护者或 agent 误以为仍存在 PRD 兼容期、废弃别名重定向或 workflow fallback 的提示。

## 范围

- 清理模板、脚手架、agent 提示和运行时输出中把正式 artifact 称为 PRD 的措辞。
- 更新 `cowork-flow` 公共 Skill 文案，不再暗示废弃别名仍可作为入口重定向。
- 补充防回归测试，防止正式版提示面再次出现 `Read task PRD`、`PRD acceptance` 等混合术语。
- 明确保留必要的旧状态读取边界、obsolete cleanup、adapter/digest fail-safe fallback。

## 非目标

- 不恢复 `prd.md` 自动迁移或任何旧 lifecycle 入口。
- 不删除 `obsoleteFiles`，它仍负责清理已安装项目中的旧受管资产。
- 不删除持久化读取边界相关的 legacy fixture / migration 测试。
- 不批量改名所有 `fallback`，只限制 workflow/prompt 语义中的兼容式 fallback。

## 验收标准

- [ ] **AC-001**：用户/agent/workflow 提示面不再把 `decision-anchor.md` 称为 PRD。
- [ ] **AC-002**：运行时上下文和归档输出使用 `decision-anchor` 文案，不再输出 `Read task PRD`。
- [ ] **AC-003**：TDD evidence 提示使用 acceptance criteria / decision-anchor 语义，不再输出 `PRD acceptance`。
- [ ] **AC-004**：`template/skills/cowork-flow/SKILL.md` 不再暗示 deprecated aliases 仍可重定向。
- [ ] **AC-005**：测试覆盖正式版提示面术语约束，同时保留旧状态读取边界、obsolete cleanup、adapter fail-safe fallback。
- [ ] **AC-006**：聚焦测试与完整 `npm run test:all` 通过。
