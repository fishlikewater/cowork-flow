# 归档任务时联动归档关联 change

## 目标

修复完成阶段只归档 task、遗漏关联 change 的流程缺口。归档一个 task 时，应同时归档 `change.yaml` 中 `task` 指向该 task 的 active change。

## 范围

- `task archive <task-name>` 在成功移动 task 后，自动归档关联的 active change。
- `task next` 完成阶段提示归档命令会同时处理关联 change。
- 关联判断覆盖 task 的活动路径和归档后的路径。
- 同步 root/template 脚本、工作流文档和测试。

## 非目标

- 不把所有 change 归档合并进 `change archive`。
- 不改变 `change archive <slug>` 独立可用的行为。
- 不自动归档未通过 `change validate` 的 change。

## 验收标准

- 当 active change 的 `task` 指向被归档 task 时，执行 `task archive` 后 task 和 change 都进入各自 archive 目录。
- 已归档 change 的 `change.yaml.status` 为 `archived`，`task` 链接规范化到归档 task 路径。
- 没有关联 change 时，`task archive` 保持原行为。
- `task next` 不再只暗示 task 归档。
- 相关 Python 测试和全量项目验证通过。
