# Fix change archive after task archive

## Goal

修复 task 先归档后，`change archive` 因 `change.yaml task` 仍指向 active task 路径而失败的问题。

## Requirements

- 当 `change.yaml task` 指向 `.cowork-flow/tasks/<task>`，active task 不存在但归档区存在同名 task 时，`change archive` 应成功。
- 归档后的 change metadata 应把 task 链接规范化为 `archive/YYYY-MM/<task>`。
- repo-relative 缺失链接的错误信息不应出现 `.cowork-flow/tasks/.cowork-flow/tasks/...` 双重前缀。
- 真正不存在的 task/plan 链接仍应失败。
- 当前项目脚本与模板脚本保持一致。

## Acceptance Criteria

- [x] 新增回归测试先复现 task 先归档导致 change archive 失败。
- [x] 新增回归测试覆盖缺失 repo-relative task 链接错误路径不双重前缀。
- [x] `python3 -m unittest tests.test_change_script` 通过。
- [x] `python3 -m unittest tests.test_template_convergence tests.test_flow_script_paths` 通过。
- [x] `./.cowork-flow/run change validate 05-22-fix-change-archive-after-task-archive` 通过。

## Technical Notes

- 分级：L1 bugfix。
- Change: `.cowork-flow/changes/05-22-fix-change-archive-after-task-archive/`。
- Plan: `.cowork-flow/plans/2026-05-22-fix-change-archive-after-task-archive.md`。
