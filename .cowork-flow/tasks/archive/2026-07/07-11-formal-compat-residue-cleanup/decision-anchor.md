# 正式版残留兼容清理

## 目标

删除正式版收敛后仍残留的兼容期行为和旧入口提示噪音，让运行时、提示面和测试语义一致表达当前正式版模型。

## 范围

- 删除 `prd.md` 到 `decision-anchor.md` 的自动迁移逻辑；正式版任务启动缺少 `decision-anchor.md` 时应 fail-closed。
- 清理 Codex agent 模板中对已删除 `.agents/skills/start` 的防御性提示。
- 收敛相关测试命名，避免继续把已删除正式入口称作仍可兼容的 legacy lifecycle。

## 非目标

- 不删除 `party-v2` runtime、board schema、contract 或 host command；它们是正式 Party Mode runtime 实现，不是公开 Skill 兼容入口。
- 不删除 Host Asset Manifest 的 `obsoleteFiles` 清单；它仍负责清理已安装项目里的旧受管资产。
- 不重构 Skill Registry 的 Python / Node 双端实现。

## 验收标准

- [ ] **AC-001**：`task start` 不再迁移旧 `prd.md`；缺少 `decision-anchor.md` 时保持 blocker。
- [ ] **AC-002**：Codex agent 模板不再引用 `.agents/skills/start` 或 `start skill`。
- [ ] **AC-003**：相关测试仍覆盖已删除入口和 obsolete 清理，但命名表达为 removed/obsolete，而非兼容期生命周期。
- [ ] **AC-004**：聚焦测试通过；模板/runtime 行为变更后完整测试通过。
