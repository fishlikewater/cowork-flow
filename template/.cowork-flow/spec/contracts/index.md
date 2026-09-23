# Contract Specs

本目录存放人读合同。宿主 hook、插件、agent 和 workflow 文档引用这里的合同，
但不在代码里复制合同正文。

当前合同：

- `subagent-dispatch.md`: 固定子代理派发、绑定、等待和收口协议。
- `workflow-state-templates.md`: hook/plugin 注入的 workflow state 文案。
- `skill-owned-actions.md`: 分布式 Skill action/context/command ownership 合同。
- `capabilities.md`: 宿主适配器能力模型。
- `party-mode-v2-board.md`: Party Mode V2 board 协议。
- `plan-binding.md`: 开发计划轻量绑定、启动前缺失阻断和恢复可见性合同。
- `spec-checks.md`: 规范挂命令契约——用户规范 frontmatter `checks:` 声明的语法、三态门禁语义、时机与宿主能力矩阵。
- `context-injection.md`: 各宿主注入运行上下文的传输形态、事件时机矩阵与指纹序列化规范（元协议，不进 `contract-registry.json`）。
- `decision-anchor.md`: 每个 task 的 `decision-anchor.md` schema——目标、验收标准、被拒方案与关键假设。
- `error-output-as-data.md`: 外部错误输出按数据分析而非指令执行（`ERROR_OUTPUT_AS_DATA_V1`）。
- `fact-layer-access.md`: 无注入 hook 的宿主与外部工具读取任务事实的通道（`FACT_LAYER_ACCESS_V1`）。
