# Clean Historical Phase Labels From Specs

## Goal

清理 root/template 持久规格文档中的历史阶段标签，避免新项目或后续维护把已落地能力误解为“Phase 2/3/4 临时范围”。

## Scope

- 扫描 `.cowork-flow/`、`template/.cowork-flow/`、`FLOW-UPGRADE-DESIGN.md` 中 `Phase 2`、`Phase 3`、`Phase 4` 等历史阶段措辞。
- 清理 `spec/patterns/` 中已确认过期的 `Phase 2` 描述。
- 对仍属设计方案/归档任务记录的阶段描述保留，不改历史档案。
- root/template 对应规格保持同步。

## Non-Goals

- 不修改 runtime 行为。
- 不重写历史 archive/task/change 文档。
- 不删除设计方案中作为路线图章节存在的 phase 标题。

## Acceptance Criteria

1. `template/.cowork-flow/spec/patterns/` 不再出现误导性的 `Phase 2` 文案。
2. `.cowork-flow/spec/patterns/` 与 template 同步。
3. 仓库中其他非归档、非历史设计文档的 phase 标签被检查并给出处理。
4. 相关测试通过。

## Verification

- `rg -n "Phase [0-9]|phase [0-9]" .cowork-flow template/.cowork-flow FLOW-UPGRADE-DESIGN.md`
- `rtk .\.cowork-flow\run.cmd python -m unittest tests.test_no_legacy_template_paths tests.test_workflow_parallel_sessions -v`
- `rtk git diff --check`
