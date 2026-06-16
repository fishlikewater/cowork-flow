# Workflow Maturity Roadmap Spec

本 spec 列出 P0-P4 各期涉及的契约变更点。每期 task 落地时，对应契约点进入正式 spec 文件；本文件作为路线图的总契约索引，实际生效以各期 task 完成后更新的 spec 为准。

## 契约版本总览

| 契约 | 当前版本 | 目标版本 | 触发期 |
| --- | --- | --- | --- |
| Entry Contract | `COWORK_ENTRY_CONTRACT_V1` | `COWORK_ENTRY_CONTRACT_V2` | P0-A |
| DB Schema | 无版本 | `schema_migrations` 表 + 编号迁移 | P0-B |
| Runtime Dispatch | `RUNTIME_CONTEXT_DISPATCH_V2` | 不变 | — |
| Host Adapter Schema | `HOST_ADAPTER_SCHEMA_V1` | `HOST_ADAPTER_SCHEMA_V2`（新增 entrySignals） | P0-A |
| Runtime/Agent Run 边界 | 两表重叠 | 单一权威 | P1-A |
| Spec 文档结构 | 扁平 | 三层（Quick Start / Core / Reference） | P1-B |
| Pattern Registry | advisory + select | 视 P2-A 决策 | P2-A |
| Party Mode 归属 | 主 workflow.md 3.2/3.2.1 | 视 P2-B 决策 | P2-B |

---

## P0-A：Entry Contract V2

### 变更点

`COWORK_ENTRY_CONTRACT_V1` 的分类依据从"prompt 文本启发式"改为"宿主结构化信号优先 + 兜底 fail-closed"。

### V2 分类顺序

1. Runtime context binding（不变，强信号）。
2. **宿主结构化 entry 信号**（新增）：`cowork_session_role` / `cowork_invocation` 等 adapter 声明的键。
3. Explicit user main-session request（保留，作为结构化信号的补充）。
4. **兜底**：信号缺失时返回 `UNKNOWN`，不再做关键词猜测。

### V2 Entry Kinds

| Kind | Meaning | May mutate workflow state | 判定来源 |
| --- | --- | --- | --- |
| `MAIN_SESSION` | 用户请求主会话运行 cowork-flow。 | Yes | 结构化信号 `session_role=main` 或显式声明 |
| `READ_ONLY` | 只读问题/检视。 | No | 结构化信号 `invocation_kind=read_only` |
| `COMMAND_ONLY` | 命令包装。 | No | 结构化信号 `invocation_kind=command_wrapper` |
| `UNKNOWN` | 信号不足。 | No | 结构化信号缺失 |

### V2 Fail-closed 规则

- 结构化信号缺失 → `UNKNOWN`，不退化到文本启发式（兼容期 `_legacy_text_fallback` 开关除外）。
- `UNKNOWN` 不得 start/resume/archive/spawn（与 V1 一致）。
- 结构化信号与 prompt 文本冲突时，以结构化信号为准。

### 兼容期

- `_legacy_text_fallback` 函数保留但默认禁用。
- `config.yaml` 新增 `entry.legacy_text_fallback: bool` 开关，默认 false。
- 三宿主适配器全部提供 entrySignals 后，移除兼容期代码。

---

## P0-A：Host Adapter Schema V2

### 变更点

`adapter.yaml` 新增 `entrySignals` 段，声明宿主能稳定提供的 entry 信号键。

### Schema 片段

```yaml
entrySignals:
  sessionRole: cowork_session_role       # main | subagent | command
  invocationKind: cowork_invocation      # interactive | command_wrapper | hook | read_only
```

- 无法稳定提供的宿主，该段省略或字段为空。
- `entry_classifier` 读取 adapter.yaml 的 entrySignals 决定优先信号源。
- claude-code/codex/opencode 三份 adapter.yaml 在 P0-A task 中各自补全。

### 兼容性

- 旧 adapter.yaml 无 entrySignals 段时，`entry_classifier` 视为信号缺失，走 UNKNOWN + 兼容期开关。

---

## P0-B：DB Schema 版本化

### 变更点

新增 `schema_migrations` 表与 `scripts/flow/migrations/` 目录，取代裸 `schema.sql` 幂等创建。

### schema_migrations 表

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL,
    checksum    TEXT NOT NULL
);
```

### 迁移脚本约定

- 目录：`scripts/flow/migrations/`。
- 命名：`NNNN_<slug>.sql`，四位编号，从 `0001` 开始。
- `0001_initial.sql`：把现有 schema.sql 全部内容作为初始迁移。
- 后续演进只加新编号文件，不修改已应用文件。
- checksum = 文件内容 SHA256 前 16 位；已应用迁移 checksum 不匹配则启动报错。

### FlowStore 启动行为

1. 确保 `schema_migrations` 表存在。
2. 读取已应用 version 列表。
3. 按编号顺序应用未执行迁移，每条在独立事务内 + 记录 version/name/checksum。
4. version 跳号或 checksum 不匹配 → 报错，不启动。

### CLI 契约

- `flow migrate`：应用所有待执行迁移。
- `flow migrate --dry-run`：列出待执行迁移，不执行。
- `flow migrate --status`：列出已应用迁移。

### 迁移前备份

- 每次应用迁移前，自动复制 DB 到 `.cowork-flow/.runtime/db-backup-v<version>-<timestamp>.sqlite`。
- 备份保留策略复用 maintenance 的 retention_days。

---

## P1-A：Runtime / Agent Run 边界

### 变更点

消除 `runtime_context` 与 `agent_run` 的字段重叠，list 查询不再两表合并去重。

### 方案 1 契约（推荐，P1-A 启动时最终确认）

- `runtime_context` 是一次派发运行记录的唯一权威。
- `agent_run` 表保留但停止新增写入；读路径只查 `runtime_context`。
- `list_agent_runs_for_parent` / `list_agent_runs_for_task` 变为 `runtime_context` 的薄封装。
- 删除 `_runtime_context_to_agent_run` 投影逻辑。
- `agent_run` 标记 deprecated，在下个大版本删除。

### 方案 2 契约（备选）

- `agent_run`：run 级字段（status / retry_count / error_message / closed_at）。
- `runtime_context`：context 级字段（binding / transport / authority）。
- 正式派发同事务写两表，字段不重叠。
- list 查询按需 join，不做投影合并。

### 不变项

- `RUNTIME_CONTEXT_DISPATCH_V2` 协议不变（init/bind/close 仍由 runtime_context 承载）。
- advisory dispatch 不创建正式 run 记录的语义保留。

---

## P1-B：Spec 文档三层结构

### 变更点

`.cowork-flow/spec/` 重组为三层。

### 目录契约

```
.cowork-flow/spec/
├── quick-start.md
├── core/
│   ├── entry.md
│   ├── dispatch.md
│   ├── lifecycle.md
│   └── state-templates.md
└── reference/
    ├── patterns/
    ├── adapters/
    ├── party-mode/
    └── ...
```

### 唯一权威规则

- 同一条规则只有一个权威位置。
- Quick Start 可引用 Core 的标题，但不复制规则正文。
- 文档唯一性检查脚本（P1-B task 交付）扫描三层，报告重复。

### 迁移映射

| 旧位置 | 新位置 |
| --- | --- |
| `spec/entry-contract.md` | `spec/core/entry.md` |
| `spec/subagent-dispatch.md` | `spec/core/dispatch.md` |
| `spec/workflow-state-templates.md` | `spec/core/state-templates.md` |
| `spec/patterns/*` | `spec/reference/patterns/*` |
| `spec/capabilities.md` | `spec/reference/adapters/capabilities.md` |
| `spec/adapter.schema.json` | `spec/reference/adapters/adapter.schema.json` |

### registry.json 更新

- contracts 数组的 `path` 字段全部更新到新位置。
- 新增 `layer` 字段：`quick_start` / `core` / `reference`。
- `readWhen` 升级为强制（见 P1-C）。

---

## P1-C：Registry readWhen 强制化

### 变更点

`registry.json` 的 `readWhen` 从描述性升级为部分强制。

### 强制级别

| spec | 强制级别 | 行为 |
| --- | --- | --- |
| `core/entry.md` | 阻塞 | task start/resume/archive 前未读则报错 |
| `core/dispatch.md` | 阻塞 | subagent init 前未读则报错 |
| 其他 core | 提示 | `task next` 提示"建议先读 X"，不阻塞 |
| reference | 不强制 | 按需读 |

### 读确认机制

- 主会话在对应阶段显式 ack（通过 `task ack-spec <contract-id>` 命令）。
- ack 记录在 `runtime_session.payload_json` 的 `acks` 数组，带 contract_id + 时间戳。
- 阻塞级 spec 未 ack 时，对应命令拒绝执行并提示。

---

## P2-A：Pattern Registry（视决策）

### 决策后契约（二选一）

**若精简：**
- 删除 `patterns/fan_out.py` / `pipeline.py` / `human_loop.py`。
- 保留 `patterns/generic.py` + `patterns/base.py`（数据结构）。
- `PatternRegistry.select` 删除；`resolve` 保留但只剩 generic。
- children 聚合逻辑由 `FlowStore.all_children_done` 直接驱动，不经 pattern 类。
- `FLOW_PATTERN_CONTRACTS_V1` 契约更新为"仅 generic + 显式 children 聚合"。

**若保留：**
- 补足 `PatternRegistry.select` 的实际消费方（task next / dashboard）。
- `FLOW_PATTERN_CONTRACTS_V1` 不变，但新增使用率统计字段。

### 不变项

- pattern 纯函数 + FlowStore 单一写入的职责切分保留。
- `TaskContext` / `Action` / `StepKind` 数据结构保留。

---

## P2-B：Party Mode 归属（视决策）

### 决策后契约（二选一）

**选项 A（研究性）：**
- `workflow.md` 3.2 / 3.2.1 节移除，内容迁入 `spec/reference/party-mode/`。
- party-mode / party-mode-v2 skill 描述加 "experimental / research" 前缀。
- 不新增基础设施；后续只修 bug。
- registry.json 的 party-mode 相关 contract 降级为 reference 层。

**选项 B（生产特性）：**
- 新增触发条件契约：L2 + 跨 N 层（具体阈值 P2-B task 定）才启用。
- 新增产出强制引用契约：Party Mode 报告项必须在 check.jsonl 被 `accepted` / `rejected` + 理由回应。
- 新增 ROI 度量：启用 vs 未启用任务的 check 返工率统计。
- 保留在 workflow.md，但明确触发门槛。

---

## P3-A：Runtime 协调下沉

### 变更点

单任务派发也采用 spawn-family/check-family 模式，主会话不再手动 list/cancel。

### 契约

- `subagent init` + 派发后，runtime 负责等待汇总、孤儿清理、超时收口。
- 主会话只发起 + 验收结果。
- 适配器取消原语由 runtime 在收口时调用，不经主会话。
- `RUNTIME_CONTEXT_DISPATCH_V2` 的 closeout 步骤语义不变，但执行者从主会话改为 runtime。

### 新增 CLI

- `subagent wait <runtime_context_id> [--timeout <s>]`：阻塞等待单个子代理完成，runtime 内部处理孤儿清理。
- `subagent collect <parent-task>`：聚合所有子代理结果，返回 JSON。

---

## P3-B：文档语言统一

### 变更点

spec 工作语言定为全英文；中文摘要保留在 AGENTS.md / workflow.md。

### 契约

- `spec/quick-start.md` / `spec/core/*` / `spec/reference/*`：全英文，权威。
- `AGENTS.md`：中文，项目协作约定。
- `.cowork-flow/workflow.md`：中文摘要 + 英文 spec 引用；冲突以英文 spec 为准。
- entry classifier 中英词表随 P0-A 结构化信号改造删除，不单独处理。

### 翻译策略

- 不做一次性全量翻译（避免大 diff）。
- 每期 task 顺手翻译触动的 spec。
- 新增 spec 默认英文。

---

## P4：Dashboard 可观测性

### 变更点

dashboard 新增三个只读视图，数据全部来自现有表。

### 视图契约

- **时间线回放**：`GET /api/tasks/<id>/timeline` 返回 audit + runtime_context 时间戳排序的事件流。
- **失败归因聚类**：`GET /api/insights/failures` 返回 block.reason + agent_run.error_message 的 top-N 聚类。
- **Readiness 通过率**：`GET /api/insights/readiness` 返回 task start 时 readiness 检查的通过/失败统计。

### 约束

- 只读，不引入新写路径（与 06-14-db-runtime-maintenance 一致）。
- 不新增表；数据来自 audit / block / runtime_context / agent_run。
- dashboard_process 进程模型不变。

---

## 横向契约

### root/template 一致性

- 每期 task 的改动同步到 `template/.cowork-flow/`。
- `npm run test:template` 在每期收口时必须通过。
- 契约文件（adapter.yaml / registry.json / schema.sql / patterns）双写。

### 失败回归测试

- 每期 task 先写会失败的测试，再实现（AGENTS.md 第 8 条）。
- 安全链相关（P0）测试必须能 fail-closed：构造非法输入断言拒绝。

### 分期归档

- 每期 task 完成后独立 archive。
- 容器 change `06-15-workflow-maturity-roadmap` 在所有分期验收通过后 archive。
- 容器 change 的 `change.yaml.task` 不指向单个 task，而是由分期 task 各自反向链接到本 change。
