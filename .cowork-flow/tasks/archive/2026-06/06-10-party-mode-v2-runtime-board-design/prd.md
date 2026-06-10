# Party Mode V2 Runtime Board Design Doc PRD

## 背景

现有 Party Mode 是 skill-first advisory roundtable：主会话派发真实子代理、收集观点、提炼 claim table，再由主会话综合结论。用户希望新增 Party Mode V2，且不改变现有 Party Mode。

V2 的关键变化是：讨论约束不能只依赖 skill 文本，而要由 Python runtime 控制；主持人不转发、不综合观点，只监控和纠偏；多个子代理通过共享看板自行交流；子代理只有在证据和推理说服自己时才能认同，否则必须继续反驳；方案需要适配 Codex、Claude Code 和 OpenCode。

## 目标

- 整理一份详细设计文档，描述 Party Mode V2 的 runtime board 架构、状态机、host-neutral action、多人辩论协议和测试方案。
- 明确 V2 与现有 Party Mode V1 的边界，保证 V1 行为与测试不受影响。
- 明确 Codex、Claude Code、OpenCode 三端适配方式。
- 明确 Python runtime 能硬约束的部分，以及当前 host 能力无法硬隔离的边界。

## 非目标

- 本任务不实现 `party_mode_v2.py`。
- 本任务不新增或修改 Party Mode V2 skill。
- 本任务不修改 host adapter schema 或正式子代理派发协议。
- 本任务不提交、归档或发布。

## 范围

- 新增当前任务目录下的详细设计文档：`design.md`。
- 文档需覆盖：
  - runtime controller 职责。
  - board 状态模型与 current-round-only 视图。
  - 多子代理协议。
  - 防无脑认同规则。
  - 主持人最小职责。
  - host-neutral next actions。
  - Codex、Claude Code、OpenCode 适配。
  - 配置、文件落点、测试与验收。

## 验收标准

- `design.md` 能作为后续实现 Party Mode V2 的依据。
- 文档清楚区分 V1 与 V2，不要求改动现有 `party-mode`。
- 文档明确指出 Python runtime 不直接调用 Codex/Claude/OpenCode 原语，而是输出 host-neutral actions。
- 文档包含至少 3 个子代理的多人辩论模型。
- 文档包含 `maintain`、`revise`、`concede` 的校验规则。
- 文档包含三端适配和测试计划。
- 运行 `git diff --check` 无空白错误。

## 验证方式

```powershell
rtk git diff --check
```
