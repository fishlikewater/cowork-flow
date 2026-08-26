# Workflow state templates

Host hooks inject only observable workflow state, the actions that must not be
performed in the current context, and one navigation entrypoint. Detailed
stage procedure belongs to the Skill that owns the selected action.

Entry classification happens before lifecycle mutation or subagent dispatch.
Formal delegated state requires a runtime context id and binding; UNKNOWN is
not delegated state. UNKNOWN is not a delegated subtask.

## no_task

[workflow-state:no_task]
当前会话没有活动任务。只读问答可以直接回复；涉及写入、实现、派发、归档或提交时，先通过统一导航入口解析任务状态。
MUST NOT 编辑文件、实现代码、重构代码、派发子代理。
禁止根据提示词猜测任务或子代理身份。
导航：`./.cowork-flow/run task next --json`
[/workflow-state:no_task]

## delegated_subtask

[workflow-state:delegated_subtask]
当前线程具有已绑定或 fail-closed 的 runtime context。不要启动、恢复、创建、激活、归档、提交任务，也不要切换到主会话协调。
Runtime context 是唯一身份事实；无效 context 只允许报告需要上下文。
导航：`./.cowork-flow/run task next --json`
[/workflow-state:delegated_subtask]

## planning

[workflow-state:planning]
活动任务处于 planning。状态转换由 runtime 事实和任务上下文决定；具体规划、澄清和实现步骤由对应 Skill 提供。
禁止在缺少必需任务事实时直接执行生命周期变更。
导航：`./.cowork-flow/run task next --json`
[/workflow-state:planning]

## in_progress

[workflow-state:in_progress]
活动任务处于 in_progress。只依据当前 task、change、plan、diff 和测试事实推进；具体实现与检查步骤由 action owner Skill 提供。
导航：`./.cowork-flow/run task next --json`
[/workflow-state:in_progress]

## review

[workflow-state:review]
活动任务处于 review。只依据当前 diff、测试、规格和生命周期事实判断是否可完成；复核动作由 owner Skill 提供。
导航：`./.cowork-flow/run task next --json`
[/workflow-state:review]

## completed

[workflow-state:completed]
活动任务已 completed。不要继续修改该任务的生命周期状态；需要后续工作时创建或导航到新的活动任务。
导航：`./.cowork-flow/run task next --json`
[/workflow-state:completed]
