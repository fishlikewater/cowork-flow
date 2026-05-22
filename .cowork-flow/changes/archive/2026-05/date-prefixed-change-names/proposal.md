# 为 change 目录增加日期前缀

## 背景

当前 `task create` 会在 `.cowork-flow/tasks/` 下创建 `MM-DD-<slug>` 形式的任务目录，便于按时间排序和辨认。`change create` 目前在 `.cowork-flow/changes/` 下直接创建 `<slug>`，和任务目录命名不一致。

## 目标

让后续通过 `change create <slug>` 新建的 change 目录也带 `MM-DD-` 日期前缀，与任务目录命名风格一致。

## 范围

- 修改模板内 change 管理脚本，以及当前仓库对应脚本。
- 保持输入参数仍为裸 slug，例如 `replace-auth`。
- 只影响新建 active change 目录，不迁移历史 change，也不改变 archive 的年月分层。
- 增加回归测试证明新建目录名包含日期前缀。

## 非目标

- 不修改 task 创建逻辑。
- 不批量重命名已有 `.cowork-flow/changes/*` 目录。
- 不改变 `change.yaml` 中 `slug` 字段的语义。
