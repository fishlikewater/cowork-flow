# 统一规则规范和整理 spec 目录实施计划

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** 让 workflow 规则、合同注册和 spec 目录结构成为单源、清晰、可验证的产品合同。
**Architecture:** 保留现有 Python gate 入口，但把规则元数据从执行器中抽离到 runtime rules 文件。`spec/` 目录按 `contracts/`、`runtime/`、`schemas/`、`backend/`、`frontend/`、`guides/` 分层，root/template 同步迁移。
**Verification:** focused Python tests -> `npm test` -> `npm run test:template` -> `npm run pack:check` -> `git diff --check`。

**Execution Strategy:** 串行执行。该任务会同时触碰规则文件、运行时脚本、模板、hook/plugin 路径和测试，拆并行会增加合并风险。

## 1. 写红灯测试和 TDD 证据

- 修改 `tests/test_flow_script_paths.py`，覆盖：
  - 缺失 runtime rules 文件时 gate 不静默通过。
  - `validate_implementation.py` 使用 rules 文件中的 R-AG-002 元数据。
  - `test_intent.py` 支持 `ClassName.test_method`，定位失败时给出明确 block。
- 修改 `tests/test_host_adapters.py` / `tests/test_workflow_parallel_sessions.py`，覆盖新的 `spec/` 分层路径和 contract registry 路径。
- 在 `.cowork-flow/tasks/06-23-unify-rule-spec-contracts/tdd.jsonl` 记录 AC-002、AC-003、AC-005 的红灯证据。
- 验证：先运行 focused tests，确认因目标行为尚未实现而失败。

## 2. 迁移 spec 目录结构

- root/template 同步迁移：
  - `.cowork-flow/spec/entry-contract.md` -> `.cowork-flow/spec/contracts/entry-contract.md`
  - `.cowork-flow/spec/subagent-dispatch.md` -> `.cowork-flow/spec/contracts/subagent-dispatch.md`
  - `.cowork-flow/spec/workflow-state-templates.md` -> `.cowork-flow/spec/contracts/workflow-state-templates.md`
  - `.cowork-flow/spec/capabilities.md` -> `.cowork-flow/spec/contracts/capabilities.md`
  - `.cowork-flow/spec/party-mode-v2-board.md` -> `.cowork-flow/spec/contracts/party-mode-v2-board.md`
  - `.cowork-flow/spec/registry.json` -> `.cowork-flow/spec/runtime/contract-registry.json`
  - `.cowork-flow/spec/rules.json` -> `.cowork-flow/spec/runtime/rules.json`
  - `*.schema.json` -> `.cowork-flow/spec/schemas/`
- 更新 README、doctor、hooks、plugins、tests、registry 中所有路径引用。
- 验证：`rg` 确认旧路径只在历史 archive 或兼容说明中出现。

## 3. 统一规则元数据与执行器

- 新增/调整规则加载 helper，让 `validate_rules.py` 和 `validate_implementation.py` 读取同一个 runtime rules 文件。
- 规则文件缺失或 JSON 无效时返回明确 block，不再静默通过。
- `validate_implementation.py` 按 rule id 执行事实检查，violation 的 message/severity/fix_hint 从规则文件生成。
- 把 `source_line` 改成稳定的 `source_anchor` / `source_excerpt`。
- 验证：focused tests 变绿，默认路径仍阻断子代理规格变更，coordinator 仍可审查 meta/spec 变更。

## 4. 修正 TDD evidence/test intent 格式约束

- `test_intent.py` 支持裸函数名、`ClassName.test_method`、`module.ClassName.test_method`。
- 定位不到目标测试时返回明确 block，不扫描整文件造成误判。
- 更新 TDD skill 或相关规范文字，说明 `testName` 支持格式。
- 验证：focused tests 变绿，浅测试阻断用例仍然有效。

## 5. 集成验证与收口

- 运行：
  - `python -m unittest tests.test_flow_script_paths tests.test_host_adapters tests.test_workflow_parallel_sessions tests.test_codex_hooks tests.test_claude_hooks -v`
  - `npm test`
  - `npm run test:template`
  - `npm run pack:check`
  - `git diff --check`
- 运行 `task review`、`task complete`、`task archive`。
- 记录 session 并提交。
