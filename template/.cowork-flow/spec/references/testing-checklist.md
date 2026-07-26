# Testing Checklist

> 测试质量快速参考。审查测试文件、编写测试用例或检查行为覆盖时按需加载。

## 测试结构检查

- 测试名称描述行为：`test_<unit>_<scenario>_<expected>`
- AAA 排列（Arrange/Act/Assert 之间有视觉分隔）
- 一个测试只验证一个行为
- 断言行为契约，而非实现细节
- mock 验证行为调用，而非 call-count

## 深度检查

- 不是 `assert True` 通过的测试
- 不是"只检查函数是否存在"的测试
- 不是通过 `unittest.mock` 调用计数代替行为验证的测试
- 不是快照空结构（`assert result == {}`）的测试
- 不依赖测试执行顺序
- 不跳过必要的 setup/teardown
- 断言精确值或行为契约，而非 truthy/falsy
- 异常路径有至少一个测试覆盖

## 反模式

| 反模式 | 问题 | 替代方案 |
|---|---|---|
| 设置期望值为硬编码输出 | 测试与实现耦合，实现变更但行为相同时测试失败 | 验证行为契约：输入 -> 期望输出关系 |
| mock 受测函数的内部调用 | 测试实现而非行为 | mock 留在边界层（API/文件系统/时间） |
| 多个不相关行为塞一个测试 | 失败时不知道是什么坏了 | 每行为独立测试，名称描述行为 |
| 断言 `assert True` | 总是通过 | 改为语义断言（assertEqual/assertGreater 等） |
| 只检查函数存在 `assert module.func` | 不验证行为 | 调用函数验输出或异常 |
| 不清理全局状态 / fixtures | 测试间污染导致顺序依赖 | 使用 setup/teardown 清理 |

## 范围

- 当前修改的函数/模块有直接单元测试
- 下游依赖有集成测试
- 边界条件（空值/极值/并发）有至少一个测试覆盖

## 参见

- `spec/backend/quality-guidelines.md` — 后端测试规范
- `skills/test-first/SKILL.md` — 完整的 TDD 流程
- `references/security-checklist.md` — 测试中的安全边界检查
