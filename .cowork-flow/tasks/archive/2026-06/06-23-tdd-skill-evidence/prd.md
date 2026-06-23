# 落地 TDD Skill 与 TDD Evidence PRD

## 目标

让行为变更任务默认遵循 red-green-refactor，并通过 `tdd.jsonl` 形成可检查证据。

## 范围

### In Scope

- 新增 `tdd` skill。
- 定义 TDD evidence 数据格式。
- 在 review 阶段阻断缺少 red-green 证据的行为变更。
- 同步 root/template skill。

### Out of Scope

- 测试意图规则实现。
- 编码规范扫描实现。

## 验收标准

- AC-001: 行为变更没有 TDD evidence 时，review 失败。
- AC-002: TDD evidence 包含 red/green 命令、退出码、失败原因和验收标准映射。
- AC-003: 纯文档任务可豁免，但必须记录原因。
- AC-004: `cowork-implement` 固定代理提示要求实现前产出 TDD evidence 或记录豁免。
- AC-005: root/template 中 `tdd` skill 和固定代理提示保持同步。

## 相关文件

- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.codex/agents/cowork-implement.toml`
- `template/.codex/agents/cowork-implement.toml`
- `.cowork-flow/scripts/common/tdd_evidence.py`
- `template/.cowork-flow/scripts/common/tdd_evidence.py`
- `tests/test_flow_script_paths.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_cowork_agents.py`

## 验证方式

```powershell
python -m unittest tests.test_flow_script_paths tests.test_workflow_parallel_sessions tests.test_cowork_agents -v
```
