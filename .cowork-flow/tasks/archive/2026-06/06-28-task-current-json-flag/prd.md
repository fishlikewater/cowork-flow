# PRD: task current 增加 --json 输出格式

## 目标

`.cowork-flow/run task current` 命令增加 `--json` 参数，输出当前活动任务信息的 JSON 格式，便于脚本集成。

## 非目标

- 不修改其他 task 子命令的输出格式

## 验收标准

| ID | 描述 |
|----|------|
| AC-01 | `task current --json` 输出当前任务的 JSON 对象（含 taskPath, status, name 字段） |
| AC-02 | 无任务时输出 `{"taskPath": null, "status": "no_task"}` |
| AC-03 | 不带 --json 时行为不变 |
