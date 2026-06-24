# 修复 mock-only 断言识别

## 目标

修复 test intent gate 对 mock-only 测试的误判：测试里同时包含 mock 调用和有效行为断言时，不应被当作 mock-only 浅测试阻断。

## 范围

- 修复 `_looks_mock_only` 对 Java `assertEquals(...)` 的识别。
- 修复 `_looks_mock_only` 对 `assertFalse(...)` 的识别。
- 同步 root/template 运行时代码。
- 增加最小回归测试。

## 非目标

- 不重写 test intent 分类器。
- 不扩大到新的测试框架语法清单。

## 验收标准

- AC-001: 包含 mock 调用和 Java `assertEquals(...)` 的目标测试不触发 mock-only 阻断。
- AC-002: 包含 mock 调用和 `assertFalse(...)` 的目标测试不触发 mock-only 阻断。

## 验证方式

- `python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_test_intent_accepts_mock_plus_java_assert_equals -v`
- `python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.test_test_intent_accepts_mock_plus_assert_false -v`
- `python -m unittest tests.test_flow_script_paths -v`
