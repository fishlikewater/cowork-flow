# Party Mode — Experimental / Research

> **Status:** Experimental / Research。Party Mode 从 workflow.md 主流程移出，归入 reference 层。后续只修 bug，不新增基础设施。

## Party Mode V1

Party Mode 是用户手动触发的 advisory roundtable。主会话可通过当前宿主适配器创建 fresh child contexts，收集真实讨论子代理的证据、分歧、风险和可测验收信号，再由主会话综合结论。

Party Mode 不能推进任务状态，不能满足正式实现或检查完成条件，也不能替代 `cowork-implement` 或 `cowork-check`。轮次上限、继续/停止条件、输出 schema 和可配置默认值由 party-mode skill 定义；正式子代理协议仍以 `.cowork-flow/spec/core/dispatch.md` 为准。

## Party Mode V2

Party Mode V2 是用户手动触发的 runtime board advisory workflow。Python runtime 控制看板、当前轮视图、schema 校验、轮次上限、纠偏事件和最终报告；子代理通过 board API 交流，主持人只监控 runtime status、执行宿主适配器动作和记录偏题纠正。

Party Mode V2 仍不能推进任务状态，不能满足正式实现或检查完成条件，也不能替代 `cowork-implement` 或 `cowork-check`。V2 runtime 只输出 host-neutral next actions，宿主专属原语仍只在 `.cowork-flow/adapters/<host>/adapter.yaml` 和宿主资产中声明。

## 使用率数据（P2-B 决策依据）

| 指标 | 值 |
|---|---|
| Party Mode 相关 task 总数 | 12 |
| 构建/打磨 Party Mode 本身的 task | 12 |
| 使用 Party Mode 做实际决策的 task | 0 |
| 引用率 | 0% |

决策：引用率为零，定位为研究性能力，从主 workflow 移出。
