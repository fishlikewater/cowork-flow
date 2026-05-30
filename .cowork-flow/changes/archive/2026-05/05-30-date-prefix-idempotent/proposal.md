# 日期前缀 slug 幂等处理

## 问题

`task create` 和 `change create` 当前无条件把当天 `MM-DD` 拼到 slug 前面。调用方如果传入已经带日期的 slug，会得到重复前缀，例如 `05-30-05-30-auto-install-update`。

## 目标

- slug 已带 `MM-DD-` 前缀时直接使用原值。
- slug 未带日期前缀时保留当前自动补前缀行为。
- `task create` 和 `change create` 使用同一套判断规则。

## 非目标

- 不拒绝已带日期前缀的 slug。
- 不修改已存在任务或 change 目录。
- 不改变 archive、validate、start 的路径解析规则。
