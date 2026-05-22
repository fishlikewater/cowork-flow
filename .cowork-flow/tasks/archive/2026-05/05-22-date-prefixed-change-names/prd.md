# Date prefixed change names

## Goal

让新建 change 目录名和 task 目录名保持类似，都带 `MM-DD-` 日期前缀。

## Requirements

- `change create <slug>` 的输入仍使用裸 slug。
- 成功创建的 active change 目录名为 `MM-DD-<slug>`。
- `change.yaml` 中的 `slug` 与实际目录名一致，便于 validate/archive/list 继续按目录名操作。
- 既有裸 slug change 目录继续可校验、可归档，不做迁移。
- 模板脚本和当前仓库脚本保持一致。

## Acceptance Criteria

- [x] 回归测试证明 `change create replace-auth` 创建 `MM-DD-replace-auth`。
- [x] `python3 -m unittest tests.test_change_script` 通过。
- [x] `./.cowork-flow/run change validate date-prefixed-change-names` 通过。

## Technical Notes

- 本任务分级为 L1。
- Change: `.cowork-flow/changes/date-prefixed-change-names/`。
- Plan: `.cowork-flow/plans/2026-05-22-date-prefixed-change-names.md`。
