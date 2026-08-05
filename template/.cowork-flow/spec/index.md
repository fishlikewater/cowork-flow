# Cowork Flow Spec Index

本目录只存放项目规范、运行时合同和运行时配置 schema。按职责分层：

| 目录 | 作用 |
| --- | --- |
| `contracts/` | 人读的 workflow、宿主适配器和子代理协议合同。 |
| `runtime/` | runtime 读取的机器配置，包括 contract registry 和 host asset manifest。 |
| `schemas/` | runtime 配置和宿主合同的 JSON Schema。 |
| `backend/` | 后端实现规范；由 review skill 按需读取并逐条审查。 |
| `frontend/` | 前端实现规范；由 review skill 按需读取并逐条审查。 |
| `guides/` | brainstorming/task-planning 阶段的编码前思考、跨层设计和复用判断指引。 |
| `references/` | 按需参考材料（DoD、测试清单、安全清单、协作模式）；不自动加载。加载条件见 contract-registry.json 的 references 数组。 |

流程内核只负责任务状态、文件范围、runtime context、归档一致性等可机器判断的事实。
动作、阶段指导和专属运行时由各 Skill 的 `manifest.json` 声明；不维护集中式
Skill registry。
`backend/`、`frontend/` 中的自然语言规范不注册为 runtime gate；
`task-review` skill 根据当前 diff 和任务范围读取并逐条审查。
`guides/` 属于前置澄清与计划参考；选用后的结论应进入 `decision-anchor.md` 或任务计划。

## references/

> 按需参考材料。**不在主会话中自动加载**——仅当 skill 入口或 agent 判断需要时读取。

reference 文件之作用是：
1. 为 skill 入口提供补充上下文（main skill 是入口，reference 是补充）
2. 减少每次会话需加载的内容（spec/backend/ 等窄域规范只有实际需要时才加载）
3. 在 planning、check 或 review 阶段提供快速对照清单

加载规则：
- contract-registry 中 loadWhen 之一被匹配时读取
- skill 正文中显式引用 reference ID 时读取
- 用户在主会话请求特定检查时
- **不**自动加载——这是与 contracts/ 系列的区别
