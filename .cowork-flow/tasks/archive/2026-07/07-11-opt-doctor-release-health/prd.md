# P1 强化 doctor 与发布前健康检查

## Goal

提供一个面向维护者的发布健康检查入口，让编码、模板同步、迁移、宿主适配器和子代理安全问题在发布前可见、可定位、可修复。

## Scope

- 增强 `.cowork-flow/scripts/doctor.py` 与 template 镜像。
- 接入或串联已有 BOM/UTF-8、DB migration、host adapter、subagent safety、root/template sync、package boundary 检查。
- 为健康检查输出增加行为测试。
- 必要时更新 `scripts/pack-check.js`、`package.json` 和相关测试。

## Non-Goals

- 不重构 task lifecycle 或 FlowStore。
- 不改变正式子代理协议。
- 不把所有测试都塞进 doctor；doctor 聚合信号和下一步建议。

## Acceptance Criteria

1. 新增或增强的健康检查命令能输出每个检查项的 OK/WARN/FAIL 状态。
2. 失败输出包含当前状态、阻塞原因、下一条建议命令和涉及文件。
3. UTF-8/BOM、root/template sync、DB migration、host adapter、subagent safety、pack boundary 至少有可执行检查入口。
4. template 侧 doctor 与 root 侧保持同步或差异有测试说明。
5. 相关测试覆盖成功与失败路径。
6. `git diff --check`、相关 Python 测试和 pack check 通过。

## Relevant Files

- `.cowork-flow/scripts/doctor.py`
- `template/.cowork-flow/scripts/doctor.py`
- `scripts/pack-check.js`
- `package.json`
- `tests/test_dashboard.py`
- `tests/test_host_adapters.py`
- `tests/test_subagent_dispatch.py`
- `test/package.test.js`

## Verification

- `.cowork-flow/run.cmd doctor --release-health`
- `.cowork-flow/run.cmd doctor --subagent-safety`
- `.cowork-flow/run.cmd python -m pytest tests/test_dashboard.py tests/test_host_adapters.py tests/test_subagent_dispatch.py -q`
- `npm run pack:check`
- `git diff --check`