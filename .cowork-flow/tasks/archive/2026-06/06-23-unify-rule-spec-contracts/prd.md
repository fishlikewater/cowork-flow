# 统一规则规范和整理 spec 目录 PRD

## 目标

把当前分散在 `rules.json`、`validate_implementation.py`、`validate_rules.py`、`registry.json` 和宿主资产中的 workflow 规则/合同收敛为清晰、可验证、可分发的结构。

## 非目标

- 不重写整个 gate 引擎。
- 不改变固定代理派发协议本身。
- 不删除 backend/frontend/guides 现有规范内容。
- 不为了目录好看而破坏模板安装、hook 注入或 package 内容。

## 关键假设

- `spec/` 可以包含人读规范、机器读 runtime 配置和 schema，但必须通过子目录表达用途。
- 规则的 id、message、severity、fix_hint、source 等元数据应由一个规则文件提供，执行器只负责按 rule id 检查事实。
- 缺失关键规则/合同注册文件不应静默通过；允许宿主插件为了不崩溃做降级提示，但 doctor/test/gate 必须能发现。
- 本任务修改 workflow runtime 和模板，必须 root/template 同步。

## 范围

### In Scope

- 整理 root/template 的 `.cowork-flow/spec/` 结构。
- 统一 workflow rule 元数据来源，消除禁止规则 message/fix_hint 多处硬编码。
- 修正 `rules.json` 的 `source_line` 易腐元数据，改为更稳定的锚点/摘录。
- 明确 `registry.json` 的运行时用途与缺失行为。
- 修正 TDD evidence/test intent 对 `testName` 的格式约束，避免等 review 才发现格式不对。
- 更新测试、doctor、README、package/template 检查。

## 范围边界

- 只改 cowork-flow 的规则定义、规范目录和相关运行时校验。
- 不重写 host adapter 协议，不新增新的执行入口。
- 不迁移历史 archive 内容，不改用户已有任务数据结构。

### Out of Scope

- 不新增外部依赖。
- 不改变用户现有 CLI 命令名称。
- 不迁移历史 archive 内旧任务文档。

## 验收标准

- AC-001: `spec/` 目录按职责分层，root/template 结构一致，所有引用路径同步更新。
- AC-002: workflow 规则元数据由单一规则文件提供，implementation/coding/rules validators 不再重复维护同一条规则的 message/fix_hint/severity。
- AC-003: 缺失 rules registry 或 contract registry 不再静默弱化关键约束；doctor/test/gate 能给出明确失败或警告。
- AC-004: `rules.json` 不再依赖易腐 `source_line`，改用稳定 source anchor 或 excerpt。
- AC-005: TDD evidence 在实现前创建；validator 支持并校验 `ClassName.test_method` 与裸函数名，定位失败时给出明确错误。
- AC-006: 关键验证通过：focused Python tests、template tests、Node tests、pack check、`git diff --check`。

## 相关文件

- `.cowork-flow/spec/`
- `template/.cowork-flow/spec/`
- `.cowork-flow/scripts/common/validate_rules.py`
- `.cowork-flow/scripts/common/validate_implementation.py`
- `.cowork-flow/scripts/common/test_intent.py`
- `.cowork-flow/scripts/doctor.py`
- `template/.opencode/plugins/cowork-flow.js`
- `tests/`
- `README.md`

## 验证方式

```powershell
python -m unittest tests.test_flow_script_paths tests.test_host_adapters tests.test_workflow_parallel_sessions tests.test_codex_hooks tests.test_claude_hooks -v
npm test
npm run test:template
npm run pack:check
git diff --check
```
