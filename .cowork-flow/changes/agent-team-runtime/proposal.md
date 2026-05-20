# Agent Team Runtime

## 背景

cowork-flow 当前已经具备任务、change、plan、context 和 session 记录闭环，也内置了 `subagent-driven-development` 等协作型 skill。但在执行 `.cowork-flow/plans/*.md` 时，多个 agent 如何分工、并行、审阅、重试和恢复，仍主要依赖主 agent 的即时判断与聊天上下文。

这会带来几个问题：

- 可并行任务没有稳定的落盘调度图，恢复后容易丢失“谁在做什么”。
- agent 选择、任务边界、审阅结果和失败重试缺少结构化记录。
- 现有 skill 能指导执行方式，但不能提供可验证、可恢复的 runtime 工件。
- 不同项目想定制 agent 能力时，没有统一的 registry、策略和适配器入口。

## 目标

新增一个平台中立、默认面向 Codex 的 agent team runtime。它在执行 plan 阶段帮助主 agent 解析计划、拆分可独立任务、生成依赖图和并行批次，匹配合适 agent，记录执行、审阅、阻塞、重试与统计信息。

## 范围

本次变更包含：

- 新增独立命令组：`./.cowork-flow/run agent-team ...`。
- 新增项目级 agent team 配置目录：`.cowork-flow/agent-team/`。
- 新增任务级执行工件目录：`.cowork-flow/tasks/<task>/agent-team/`。
- 默认提供 `codex` 适配器，采用“主 agent 调度型”执行模型。
- 保留 `manual` 兜底适配器。
- 新增 agent team execution skill，用于指导主 agent 在执行 plan 时使用 runtime。
- 更新 workflow、start skill、README 和模板文档，使 agent team 成为计划执行阶段的可选能力。
- 增加脚本、模板同步和恢复能力测试。

不在本次变更中直接实现：

- 由 Python 脚本直接调用 Codex runtime 或其他 AI 平台 API。
- 绑定特定商业平台的鉴权、网络调用或后台执行服务。

## 成功标准

- 标准 writing-plans Markdown 能被解析成可审阅的 dispatch plan。
- 主 agent 能通过 `agent-team next` 获取下一批可并行 assignments。
- 每个 plan task 默认生成实现、规格审阅、质量审阅链路。
- agent registry 支持内置角色和项目覆盖。
- `codex` 适配器能生成 Codex-ready 分派工件，主 agent 可据此调用子 agent。
- 执行结果、审阅结果、阻塞和重试都能落盘并可恢复。
- 未完成、审阅未通过或失败未决时，`complete` 必须失败。
- 模板安装与同步不会覆盖项目自定义 agent registry / policy。
