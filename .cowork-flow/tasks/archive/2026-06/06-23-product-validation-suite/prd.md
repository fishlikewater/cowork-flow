# 产品级验收套件与模板同步 PRD

## 目标

补齐覆盖 workflow 跳步、TDD、测试意图、编码规范、模板同步和 Windows 路径的产品级验收套件。

## 范围

### In Scope

- happy path 端到端任务流。
- 跳步失败路径。
- TDD 缺失失败路径。
- 无意义测试失败路径。
- 编码违规失败路径。
- fresh install / template parity / Windows `run.cmd` 路径。

### Out of Scope

- 门禁引擎本身的实现。
- skill 内容本身。

## 验收标准

- AC-001: 所有关键流程都能被测试驱动地证明。
- AC-002: root/template 资产保持同步。
- AC-003: 安装和模板打包路径不回退。
- AC-004: 本任务补齐跨任务端到端验收，但不替代前四个实现任务的 focused failing tests。

## 相关文件

- `tests/test_flow_script_paths.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_cowork_agents.py`
- `tests/test_host_adapters.py`
- `test/*.test.js`
- `scripts/run-template-tests.js`
- `scripts/pack-check.js`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.agents/skills/before-dev/SKILL.md`
- `template/.agents/skills/before-dev/SKILL.md`
- `.agents/skills/writing-plans/SKILL.md`
- `template/.agents/skills/writing-plans/SKILL.md`
- `.agents/skills/check/SKILL.md`
- `template/.agents/skills/check/SKILL.md`
- `.codex/agents/cowork-implement.toml`
- `template/.codex/agents/cowork-implement.toml`
- `.codex/agents/cowork-check.toml`
- `template/.codex/agents/cowork-check.toml`

## 验证方式

```powershell
python -m unittest discover tests -v
npm test
npm run test:template
npm run pack:check
git diff --check
```
