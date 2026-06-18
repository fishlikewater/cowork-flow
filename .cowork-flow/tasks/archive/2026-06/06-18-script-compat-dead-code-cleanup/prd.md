# Script Compatibility And Dead Code Cleanup

## Goal

继续清理 `cowork-flow` 脚本层的冗余代码，范围扩大到：

- 仅被测试覆盖、但已不参与当前运行流程的旧接口；
- 仅承担兼容读取/展示职责、删除后不影响当前流程的回退路径与输出字段。

## Scope

- `.cowork-flow/scripts/common/active_task.py`
- `.cowork-flow/scripts/dashboard/server.py`
- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/subagent.py`
- 对应 `template/.cowork-flow/scripts/**`
- 相关 spec / tests

## Non-Goals

- 不改变 formal runtime-context dispatch、bind、close 的当前主流程。
- 不修改当前仍被实际命令路径消费的 DB 查询接口。
- 不做与本次兼容/死代码清理无关的结构性重构。

## Acceptance Criteria

1. 删除只被测试保活的旧接口及对应测试。
2. 删除不影响当前流程的兼容读取/展示回退及对应测试/文档。
3. root/template/spec/test 同步更新，不留下失真说明。
4. 相关验证通过。

## Verification

- `rtk python -m pytest tests/test_active_task_runtime.py tests/test_flow_store.py tests/test_dashboard.py tests/test_subagent_dispatch.py -v`
- `rtk npm run test:template`
- `rtk git diff --check`
