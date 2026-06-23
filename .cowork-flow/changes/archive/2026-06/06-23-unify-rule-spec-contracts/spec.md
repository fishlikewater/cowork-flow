# 统一规则规范和整理 spec 目录 Spec

## 目录结构

目标结构：

```text
.cowork-flow/spec/
  index.md
  backend/
  frontend/
  guides/
  contracts/
    index.md
    entry-contract.md
    subagent-dispatch.md
    workflow-state-templates.md
    capabilities.md
    party-mode-v2-board.md
  runtime/
    index.md
    rules.json
    contract-registry.json
  schemas/
    index.md
    adapter.schema.json
    party-mode-v2-actions.schema.json
    rules.schema.json
```

`template/.cowork-flow/spec/` 必须保持同构。

## 规则文件

`runtime/rules.json` 是 workflow rule 元数据单源。每条规则至少包含：

- `id`
- `type`
- `severity`
- `scope`
- `condition`
- `message`
- `fix_hint`
- `source_file`
- `source_anchor` 或 `source_excerpt`
- `enforcement`

禁止新增依赖 `source_line` 的规则元数据。
`enforcement` 必须明确规则由 `validate_rules`、`validate_implementation`、
`tdd_evidence`、`host_contract` 或 `metadata_only` 承接。

## Gate 行为

- lifecycle gate 必须读取 `runtime/rules.json`。
- 规则文件缺失、JSON 无效、schema 不完整时返回 block violation。
- `validate_implementation.py` 可以保留 rule id 到事实检查函数的映射，但 violation 文案和严重级别必须来自 `runtime/rules.json`。
- `forbidden_action` 不再作为“写在 rules.json 但运行时忽略”的假规则存在；若规则在 rules 文件出现，必须有执行路径或显式声明为 metadata-only 并有测试覆盖。

## Contract Registry

`runtime/contract-registry.json` 是宿主注入 contract digest 的注册表。

- doctor 和测试必须验证该文件存在、JSON 有效、引用 path 存在。
- 宿主插件可保留最小 fallback 防止运行时崩溃，但必须在注入内容中暴露 registry 缺失/无效提示。

## TDD Evidence

`tdd.jsonl` 的 `testName` 支持：

- `test_method`
- `ClassName.test_method`
- `module.ClassName.test_method`

`test_intent.py` 如果无法定位测试函数，必须明确 block，不能退化为扫描整份测试文件。
