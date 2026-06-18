# Script Dead Code Cleanup

## Goal

检查 `cowork-flow` 当前脚本层是否存在证据充分的冗余代码、兼容残留和死代码；若存在，在不改变外部行为和工作流契约的前提下最小化清理。

## Scope

- 扫描 `.cowork-flow/scripts/`、`.codex/hooks/`、相关适配器配置，以及需要同步的 `template/.cowork-flow/scripts/`。
- 识别以下类型的问题：
  - 无调用方且无契约用途的函数、分支、文件。
  - 已被新运行时路径取代但仍保留写路径的兼容残留。
  - 重复实现且其中一份已不再被消费。
- 只清理“源码、测试、文档三方都能证明可以删除”的代码。

## Non-Goals

- 不做无证据的大范围重构。
- 不移除仍作为兼容读取路径、模板契约或文档锚点存在的代码。
- 不改变任务流、子代理绑定协议或对外命令语义。

## Acceptance Criteria

1. 输出脚本层冗余/死代码清单，并区分“可删”和“需保留的兼容路径”。
2. 对可删项完成最小清理，root/template 保持一致。
3. 所有改动都有调用链、契约或测试证据支撑。
4. 相关测试或脚本验证通过，且无新的 `git diff --check` 问题。

## Likely Files

- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/common/*.py`
- `.cowork-flow/scripts/flow/store.py`
- `template/.cowork-flow/scripts/**`
- 相关 spec 文档（如需同步）

## Verification

- `rtk python -m unittest discover -s tests -p "test_*" -v`
- `rtk npm run test:template`
- `rtk git diff --check`
