# 修复测试裸 python 调用

## 目标

让普通 `npm run test:all` 在当前环境中无需临时 wrapper 也能通过。测试入口不得假设系统存在可用的裸 `python` 命令，应复用项目已有 Python runner 或显式选择可用解释器。

## 范围

- 修复 `test/coding-standards.test.js` 中裸调用 `python` 导致的失败。
- 检查并修复 `scripts/run-template-tests.js` 中同类裸 `python` 调用。
- 记录红绿验证证据。

## 非目标

- 不改变 coding standards validator 的业务规则。
- 不修改无关未跟踪目录或既有 06-21 任务内容。
- 不回退上一提交的 `entry_classifier.py` 清理。

## 验收标准

- AC-001: `npm run test:all` 直接运行通过，不需要手动创建 `python -> python3` wrapper。
- AC-002: `test/coding-standards.test.js` 仍然验证模板 validator 能报告隐式 Python 编码违规。
- AC-003: 模板 Python 单测入口不再依赖裸 `python` 命令。

## 红灯记录

- `npm run test:all` 当前失败于 `test/coding-standards.test.js`，`failure.stdout` 为空，未匹配到 `CS-UTF8-PY-001`。
