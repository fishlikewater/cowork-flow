# 统一规则规范和整理 spec 目录 Design

## 总体设计

本次采用“路径分层 + 规则元数据单源 + 执行器按 id 调度”的最小架构调整。

不引入通用规则 DSL。现有 Python 检查函数继续负责事实判断，避免把复杂行为检查塞进 JSON 表达式；但规则的文案、严重级别、修复提示和来源只从 `runtime/rules.json` 读取。

## 模块变化

### Spec 路径

新增子目录：

- `contracts/`: 人读/宿主注入合同。
- `runtime/`: workflow runtime 读取的规则和合同注册。
- `schemas/`: JSON schema。

保留：

- `backend/`
- `frontend/`
- `guides/`

### 规则加载

新增 helper 或扩展 `validate_rules.py`：

- `RULES_RELATIVE_PATH = ".cowork-flow/spec/runtime/rules.json"`
- `load_rules(repo_root) -> tuple[list[dict], list[dict]]`
- 缺失/解析失败返回 `RULES-CONFIG-*` block violation。
- `rule_by_id(rules, rule_id)` 为其他 validator 提供规则元数据。

### Implementation Gate

`validate_implementation.py` 改为：

- 加载 rules。
- 对 R-AG-002、R-AG-005、R-AG-006 等已有检查使用规则元数据构造 violation。
- coordinator 豁免仍只作用于 R-AG-002 的事实检查，不绕过规则加载。

### Test Intent

`test_intent.py` 改为：

- 标准化 `testName`，提取最后一个函数名片段。
- 在 AST 中定位对应函数。
- 定位失败时返回 `TEST-INTENT-005` block。

## 兼容性

历史 archive 保留旧路径。运行时、模板、README、doctor、hook/plugin 和测试全部迁移到新路径。

OpenCode plugin 保留内置 fallback，但 digest 中输出 registry warning，避免宿主运行时因单文件缺失崩溃。

## 验证设计

测试优先覆盖真实回归：

- rules 文件缺失不应静默通过。
- R-AG-002 violation 文案来自 rules 文件。
- contract registry path 迁移后 plugin/doctor 仍能生成 digest。
- TDD evidence 支持 class-qualified testName。
- root/template spec 结构一致。
