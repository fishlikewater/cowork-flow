# Cowork Flow Spec Index

本目录只存放项目规范、运行时规则定义和规范校验 schema。按职责分层：

| 目录 | 作用 |
| --- | --- |
| `contracts/` | 人读的 workflow、宿主适配器和子代理协议合同。 |
| `runtime/` | runtime 读取的机器配置，包括规则元数据和 contract registry。 |
| `schemas/` | runtime 配置和宿主合同的 JSON Schema。 |
| `backend/` | Python/runtime 后端实现规范。 |
| `frontend/` | 前端实现规范。 |
| `guides/` | 编码前思考、跨层设计和复用判断指引。 |

规则执行器只负责事实判断；规则的 `id`、`message`、`severity`、`fix_hint`
和来源元数据必须来自 `runtime/rules.json`。
