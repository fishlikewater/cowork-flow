# 修复 npm 测试失败

## 目标

修复当前 npm test 的失败，使 Node.js 测试套件稳定通过。

## 范围

- 仅处理 npm test 失败对应的最小测试或实现更新。
- 不改变 CLI 外部行为。
- 不做无关重构。

## 验收标准

- 已复现失败并确认根因。
- 修复后 npm test 退出码为 0。
- sync AGENTS.md 测试继续验证只替换 managed block，且替换内容来自模板。

## 验证方式

运行 npm test。
