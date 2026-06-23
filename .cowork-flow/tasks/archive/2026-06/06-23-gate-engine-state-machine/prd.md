# 实现统一 Gate Engine 与状态迁移门禁 PRD

## 目标

把任务生命周期命令收敛到统一 gate/state transition 入口，阻断跳过 review、直接 complete、门禁失败仍推进状态的情况。

## 范围

### In Scope

- 提取统一 GateResult / GateRunner。
- 抽出状态迁移服务。
- 接入 `task review`、`task complete`、`task next` 的 gate 输出。
- 修复现有规则校验中明显的 UTF-8 和运行时错误。

### Out of Scope

- TDD skill 内容本身。
- 测试意图审查逻辑。
- 编码规范扫描增强。

## 验收标准

- AC-001: 任意 gate block 时，生命周期命令返回非 0。
- AC-002: `task complete` 不能绕过 `review`。
- AC-003: `task next` 保持只读。
- AC-004: 旧 validator 仍可通过新 gate 接口工作。
- AC-005: root/template 中新增 runtime common 模块和 `task.py` 调用点保持同步。

## 相关文件

- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/gates.py`
- `.cowork-flow/scripts/common/state_machine.py`
- `.cowork-flow/scripts/common/validate_rules.py`
- `template/.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/common/gates.py`
- `template/.cowork-flow/scripts/common/state_machine.py`
- `tests/test_flow_script_paths.py`
- `tests/test_workflow_parallel_sessions.py`

## 验证方式

```powershell
python -m unittest tests.test_flow_script_paths tests.test_workflow_parallel_sessions -v
git diff --check
```
