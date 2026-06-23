# 落地测试意图审查门禁 PRD

## 目标

阻断无意义测试，让 review 能区分“真的保护业务行为”与“只是为了过流程写出来的测试”。

## 范围

### In Scope

- 新增测试意图 validator。
- 识别常见浅层测试反模式。
- 让 `cowork-check` 输出测试意图审查结论。
- 将审查结果接入 review/complete。

### Out of Scope

- TDD evidence 格式定义。
- 编码规范校验。

## 验收标准

- AC-001: `assert True`、import-only、mock-only、函数存在类测试不能满足 gate。
- AC-002: 能识别测试是否映射到 PRD 验收标准或回归行为。
- AC-003: `cowork-check` 必须报告关键测试的意图。
- AC-004: 复杂疑点第一阶段输出 warn，不误阻断非明显无意义测试。

## 相关文件

- `.cowork-flow/scripts/common/test_intent.py`
- `template/.cowork-flow/scripts/common/test_intent.py`
- `.agents/skills/check/SKILL.md`
- `template/.agents/skills/check/SKILL.md`
- `.codex/agents/cowork-check.toml`
- `template/.codex/agents/cowork-check.toml`
- `tests/test_cowork_agents.py`
- `tests/test_flow_script_paths.py`

## 验证方式

```powershell
python -m unittest tests.test_cowork_agents tests.test_flow_script_paths -v
```
