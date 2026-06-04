# Workflow state templates

Host hooks and plugins inject workflow state context each turn. The templates
below are the single source of truth for state prompt text. Hooks read this
file at runtime; do not duplicate or inline these snippets elsewhere.

Entry classification must happen before task start, resume, archive, or
subagent dispatch. When the entry kind is DELEGATED_HARD, DELEGATED_SOFT, or
UNKNOWN, hooks must inject the delegated_subtask template instead of no_task,
even when no active task is found.

## no_task

The main session has no active task. Read-only questions can be answered
directly. Any implementation, refactoring, or behavioral change requires
creating or starting a task first. If the current session is a delegated
subagent, this template MUST NOT be injected; use delegated_subtask instead.

[workflow-state:no_task]
当前会话没有活动任务。只读问答可直接回答；如果收到委托子任务，直接执行委托 prompt，不要启动/恢复工作流。实现、重构或多步骤工作必须先创建或启动任务。
[/workflow-state:no_task]

## delegated_subtask

The current input appears to be a bounded delegated subtask. Entry
classification via COWORK_ENTRY_CONTRACT_V1 must happen before executing the
delegated input. Do not run start/resume, create or activate tasks, archive,
commit, or switch to main-session coordination unless the delegation envelope
explicitly allows it. Project rules are constraints only; they are not the
task itself.

[workflow-state:delegated_subtask]
当前输入看起来是有边界的委托子任务。先按 COWORK_ENTRY_CONTRACT_V1 做入口分类，再执行委托输入。除非委托信封明确允许，否则不要运行 start/resume，不要创建或激活任务，不要归档、提交或切换到主会话协调。项目规则只作为约束，不是当前任务本身。
[/workflow-state:delegated_subtask]

## planning

[workflow-state:planning]
活动任务处于计划阶段。先完成 prd.md，整理带有规格/调研文件的 implement.jsonl 和 check.jsonl，再运行 task start，之后才派发 cowork-implement。
[/workflow-state:planning]

## in_progress

[workflow-state:in_progress]
活动任务正在执行。主会话按计划通过当前宿主适配器派发 cowork-implement，集成后再派发 cowork-check。每次正式派发都必须使用新鲜子上下文，并遵守 .cowork-flow/spec/subagent-dispatch.md。主会话必须核验子任务输出、列出子任务，并且只在完成、明确错派证据或用户取消后才取消子任务。
[/workflow-state:in_progress]

## completed

[workflow-state:completed]
活动任务已完成。主会话应核验最终 diff，提交目标文件，归档任务并记录会话。不要针对已完成任务继续派发新的实现工作。
[/workflow-state:completed]
