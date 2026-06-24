# TDD 提示回归

## 目标

保持原本流程不变，只在 `task next` 的实现阶段增加 TDD 提示，提醒先写失败测试并记录 red evidence，再改代码。

## 范围

- `task next` 继续允许实现派发。
- `task next` 在实现阶段输出非阻断 TDD reminder。
- review/complete 维持原有 `tdd.jsonl` 验收，不新增 diff 门禁。
- root/template runtime 与 workflow 文档保持同步。

## 非目标

- 不做编辑器级写入拦截。
- 不扫描全仓库无关脏文件。
- 不新增任务状态。

## 验收标准

- AC-001: 行为变更任务缺少 red evidence 时，`task next` 仍输出 `cowork-implement` 派发命令，并打印 TDD reminder。
- AC-002: `task review` 仍只按 `tdd.jsonl` 做验收，不引入 diff 型前置门禁。

## 相关文件

- `.cowork-flow/scripts/commands/task.py`
- `template/.cowork-flow/scripts/commands/task.py`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `tests/test_flow_script_paths.py`

## 验证方式

- `python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.<target> -v`
- `python -m unittest tests.test_flow_script_paths -v`
- `npm run test:all`
