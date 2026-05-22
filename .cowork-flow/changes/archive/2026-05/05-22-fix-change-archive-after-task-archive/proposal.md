# 修复 task 先归档后 change 无法归档

## 背景

标准收尾流程会先归档 task，再归档对应 change。当前 `change archive` 在归档前会先校验 `change.yaml` 中的 `task` 链接。如果该链接仍指向 `.cowork-flow/tasks/<task>`，而 task 已移动到 `.cowork-flow/tasks/archive/YYYY-MM/<task>`，校验会失败。

另一个相关问题是：当 repo-relative 链接 `.cowork-flow/tasks/<task>` 不存在时，路径解析会继续把它拼到 `.cowork-flow/tasks/` 下，错误信息出现 `.cowork-flow/tasks/.cowork-flow/tasks/...`。

## 目标

让 `change archive` 支持推荐收尾顺序：task 先归档、change 后归档。若 active task 链接已不存在但归档区存在同名 task，应自动规范化到 `archive/YYYY-MM/<task>` 并继续归档。

## 范围

- 修复模板和当前项目的 `change.py`。
- 增加回归测试覆盖 task 先归档后的 change archive。
- 修复 repo-relative 缺失链接的错误路径展示，不再二次拼接 workflow/base 前缀。

## 非目标

- 不放宽真正缺失 task/plan 链接的校验。
- 不改变 task archive 命令行为。
- 不改变 change archive 的归档目录结构。
