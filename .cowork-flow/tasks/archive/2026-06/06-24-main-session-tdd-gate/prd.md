# 主会话 TDD 前置门禁

## 目标

行为变更任务在进入实现阶段后，如果还没有 TDD red evidence，主会话 `task next` 必须阻断实现入口，避免主会话和固定子代理绕过先红后绿。

## 范围

- 在 task runtime 中增加可复用的 TDD red evidence 检查。
- 让 `task next` 对 `in_progress` 行为变更任务先检查 red evidence。
- 同步 root 与 `template/` runtime 和 workflow 文档。

## 非目标

- 不新增任务状态。
- 不拦截任意编辑器直接改文件。
- 不改变 review/complete 的完整 TDD evidence 门禁。

## 验收标准

- AC-001: 行为变更任务缺少 `tdd.jsonl` 时，`task next` 不输出 implement 派发命令，并提示先记录 TDD red evidence。
- AC-002: 行为变更任务已有有效 red evidence 时，`task next` 恢复当前实现阶段输出。
- AC-003: 纯文档任务仍可使用 TDD exemption，不被 red evidence 前置门禁误挡。

## 相关文件

- `.cowork-flow/scripts/common/gates/tdd_evidence.py`
- `.cowork-flow/scripts/commands/task.py`
- `template/.cowork-flow/scripts/common/gates/tdd_evidence.py`
- `template/.cowork-flow/scripts/commands/task.py`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `tests/test_flow_script_paths.py`

## 验证方式

- `python -m unittest tests.test_flow_script_paths.FlowScriptPathsTest.<target> -v`
- `python -m unittest tests.test_flow_script_paths -v`
- `npm run test:all`
