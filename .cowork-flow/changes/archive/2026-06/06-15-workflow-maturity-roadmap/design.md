# Workflow Maturity Roadmap Design

## Brainstorming Summary

Goal: 把 cowork-flow 从"快速成型的功能集"收敛为"可长期维护的成熟框架"，不改安全模型内核。

Recommended direction: 保留 runtime-context binding + fail-closed + FlowStore 单一写入这套安全内核；对其外的子系统做减法、去歧义、分层。改造分 P0-P4 五期，按"先降风险、再收敛、最后去留"顺序。

Rejected alternatives:

- **推翻 runtime-context 重新设计身份**：rejected。binding 协议是核心资产，重写会让已落地的三宿主适配器全部失效，且解决不了概念密度问题。
- **一次性大重构**：rejected。P0-P4 跨安全链、数据模型、文档、子系统去留，合并成一次改动爆炸半径过大，违背 AGENTS.md 第 3 条外科手术式改动。
- **保留所有子系统只补文档**：rejected。pattern 引擎偏重和 Party Mode 投入产出比是结构问题，文档补不回抽象重量。
- **只做 P0 跳过 P1-P4**：rejected。用户明确要求全覆盖路线图；且 P1 的数据模型收敛和 P2 的去留决策是后续可维护性的前提。

## 分期总览

| 期 | 主题 | 依赖 | 预估 task 数 | 风险等级 |
| --- | --- | --- | --- | --- |
| P0 | 安全链结构化 + schema 版本化 | 无 | 2-3 | 高（触及 fail-closed） |
| P1 | 概念分层 + 数据模型收敛 | P0 schema 版本化 | 2-3 | 中（数据迁移） |
| P2 | pattern 去留 + Party Mode 定位 | P1 文档分层 | 2 | 低（决策为主） |
| P3 | 主会话减负 + 语言统一 | P1 | 2 | 低 |
| P4 | 可观测性 | P0 schema、P1 数据模型 | 1 | 低 |

依赖关系：P1 的数据模型收敛依赖 P0 的 schema 版本化机制；P2 的去留决策依赖 P1 的文档分层（决策结论要落到新文档结构里）；P3/P4 相对独立，但都受益于 P1。

执行顺序硬约束：**不在单期内同时改安全模型和数据模型**（爆炸半径控制）。

---

## P0 — 降低安全链脆弱性

### P0-A：entry 分类从文本猜测迁移到结构化信号

#### 现状

`common/entry_classifier.py` 用 `MAIN_SESSION_TERMS` / `READ_ONLY_TERMS` / `COMMAND_ONLY_TERMS` 三组中英文关键词做子串匹配，confidence 取固定值 0.55/0.6/0.35。这是 fail-closed 的守门人，但判别能力脆弱：

- 中文"分析一下修复方案"同时命中 READ_ONLY 和 MAIN_SESSION，靠 `and not` 兜底。
- "任务：实现" 和 "任务实现" 因分词差异行为不同。
- 新词、复合句式不在词表里就漏判。

#### 目标

把 main/read-only/command 三类弱信号从 prompt 文本迁移到宿主结构化元数据。runtime-context binding 这条强信号不动。

#### 方案

宿主在派发或注入时，已经知道自己是不是子上下文、是不是命令包装。把这条已有的事实显式化：

1. **adapter.yaml 新增声明**：每个 adapter 声明它能稳定提供的 entry 信号键，例如：
   ```yaml
   entrySignals:
     sessionRole: cowork_session_role   # main | subagent | command
     invocationKind: cowork_invocation  # interactive | command_wrapper | hook
   ```
   无法稳定提供的宿主该字段为空或省略。

2. **hook/plugin 注入结构化信号**：宿主钩子在注入 workflow state 前，先注入它已知的 entry 信号（env 或 metadata 形式，与 `cowork_runtime_context_id` 同通道）。

3. **entry_classifier 改造**：
   - 优先读结构化信号；信号存在且合法时直接返回对应 `EntryKind`，confidence 提升到 0.9。
   - 信号缺失时，**不再做关键词猜测**，直接返回 `UNKNOWN`（保持 fail-closed）。
   - 删除 `MAIN_SESSION_TERMS` / `READ_ONLY_TERMS` / `COMMAND_ONLY_TERMS` 三组词表。
   - `TASK_TERMS` 这种纯启发式也删除。

4. **兼容期**：宿主侧未改造完之前，保留一个 `_legacy_text_fallback` 函数（不删除，但默认禁用，通过 config 开关启用），让旧宿主在升级适配器前仍能工作。空窗期 fail-closed 仍生效——结构化信号缺失就 UNKNOWN，不会误判为 MAIN_SESSION。

#### 验证

- 失败回归测试：构造一个"看起来像主会话但没有结构化信号"的输入，断言返回 UNKNOWN（而非旧逻辑的 MAIN_SESSION）。
- 构造一个"有结构化信号但 prompt 像子任务"的输入，断言按结构化信号判定。
- 三宿主（claude-code/codex/opencode）各跑一次端到端，确认信号注入正常。
- root/template 一致性测试。

#### 风险与回滚

- 风险：某宿主短期内拿不到结构化信号，导致所有请求变 UNKNOWN，工作流卡死。
- 回滚：打开 `_legacy_text_fallback` 开关恢复旧行为；开关默认值由 config.yaml 控制。
- 缓解：兼容期内旧 classifier 不删，只是降优先级。

### P0-B：DB schema 版本化迁移

#### 现状

`scripts/flow/schema.sql` 是单文件 `CREATE IF NOT EXISTS` 幂等。`store.py:_ensure_schema` 每次连接都 executescript 整份。无版本号、无顺序迁移。`migrate.py` 是一次性脚本，处理 task.json → SQLite，不是 schema 演进机制。

#### 目标

引入 `schema_version` 表 + 顺序迁移脚本，让 schema 演进可追溯、可回滚、可 dry-run。

#### 方案

1. **新增 `schema_migrations` 表**：
   ```sql
   CREATE TABLE IF NOT EXISTS schema_migrations (
       version     INTEGER PRIMARY KEY,
       name        TEXT NOT NULL,
       applied_at  TEXT NOT NULL,
       checksum    TEXT NOT NULL
   );
   ```

2. **迁移脚本目录**：`scripts/flow/migrations/0001_initial.sql`、`0002_xxx.sql`……每个文件是一次原子 schema 变更。把现有 schema.sql 拆成 `0001_initial.sql`（当前全部表），后续演进只加新编号文件。

3. **FlowStore 启动逻辑**：
   - 读取 `schema_migrations` 表当前最大 version。
   - 按编号顺序应用未执行的迁移，每条迁移在一个事务内 + 记录 version/name/checksum。
   - checksum 用文件内容 SHA256 前 16 位，防止已应用迁移被篡改。

4. **dry-run 支持**：`flow migrate --dry-run` 输出待执行的迁移列表但不执行，供 CI 预览。

5. **回滚**：迁移本身只做前向（forward-only，业界惯例）。回滚靠"写下一个迁移撤销上一个的副作用"。设计上不承诺自动 down，但在 design.md 里记录每条迁移的撤销策略。

#### 验证

- 失败回归测试：构造一个"checksum 不匹配的已应用迁移"，断言启动报错而非静默继续。
- 构造一个"version 跳号"的迁移目录，断言报错。
- 在一个旧库样本上跑迁移，断言行数和关键约束不变。
- dry-run 输出与实际执行列表一致。

#### 风险与回滚

- 风险：迁移脚本本身有 bug 导致旧库数据丢失。
- 回滚：每次迁移前自动备份 DB 文件到 `.cowork-flow/.runtime/db-backup-<version>.sqlite`；迁移失败事务回滚，备份仍在。
- 缓解：CI 跑全量历史库样本（从 changes/archive 各个时期的 .runtime 取样）。

---

## P1 — 收敛概念，分层文档

### P1-A：agent_run / runtime_context 收敛

#### 现状

`store.py:list_agent_runs_for_parent`（行 599）和 `list_agent_runs_for_task`（行 617）都要先从 `runtime_context` 取数、再从 `agent_run` 取数、然后按 id 去重合并。`_runtime_context_to_agent_run` 把 runtime_context 投影成 agent_run 形状。`subagent-dispatch.md` 自承 advisory dispatch 不创建 agent_run 行。两表语义边界模糊。

#### 目标

消除两表重叠，让"一次派发的运行记录"只有一个权威位置。

#### 方案（二选一，P1 启动时定）

**方案 1（推荐）：runtime_context 作为唯一权威，agent_run 降级为兼容视图。**
- `agent_run` 表保留但停止新增写入（除遗留路径）。
- 所有读路径改为只查 `runtime_context`。
- `list_agent_runs_*` 变成 `runtime_context` 的薄封装，不再两表合并。
- 兼容期：旧代码读 agent_run 时，由 runtime_context 实时投影填充。
- 最终：agent_run 表标记 deprecated，下个大版本删除。

**方案 2：明确硬边界，agent_run 专管"正式派发的执行记录"，runtime_context 专管"上下文生命周期"。**
- 正式派发同时写两表，但字段不重叠：agent_run 只放 run 级字段（status/retry/error/closed_at），runtime_context 只放 context 级字段（binding/transport/authority）。
- 删除 `_runtime_context_to_agent_run` 投影，list 查询不再合并。

P1 启动前先做一次基线调研：列出所有读 agent_run 的调用方，判断它们实际需要的是 run 级还是 context 级字段。根据调研结果选方案。

#### 验证

- **基线测试（AGENTS.md 第 4 条）**：改造前录一份"给定 DB 状态 → list_agent_runs_* 输出"的快照；改造后跑同样输入，断言输出一致。
- dashboard 任务详情页的代理运行来源只查一张表。
- 失败回归测试：删除 agent_run 表的写入，断言 dashboard 仍能显示运行记录（方案 1）。

### P1-B：规范三层分层

#### 现状

核心规范 workflow.md（250 行）+ subagent-dispatch.md + entry-contract.md + patterns/* + workflow-state-templates.md 超过 1000 行，概念密度高，新接触者无处入手。

#### 目标

分三层，每层服务不同读者，同一条规则只有一个权威位置。

#### 方案

```
.cowork-flow/spec/
├── quick-start.md          # 新读者 1 页入门：最小流程 + 索引
├── core/                   # Core Protocol：规则正文
│   ├── entry.md            # entry contract（从 spec 根迁入）
│   ├── dispatch.md         # subagent dispatch（从 spec 根迁入）
│   ├── lifecycle.md        # 任务生命周期 + 状态机
│   └── state-templates.md  # workflow state 注入模板
└── reference/              # Reference：细节
    ├── patterns/           # pattern 引擎契约
    ├── adapters/           # 宿主适配器能力
    ├── party-mode/         # Party Mode（视 P2 决策）
    └── ...
```

- Quick Start 只放索引 + 最小流程图 + "何时读哪份"导航；不放规则正文。
- Core Protocol 放必须遵守的规则，是 AI 和人类都要读的权威。
- Reference 放细节契约，按需读。
- registry.json 的 `readWhen` 升级为强制：代码在对应阶段必须确认已读相关 spec。

#### 验证

- 文档唯一性检查：写一个脚本扫描三层文档，断言没有同一条规则出现在两个权威位置（允许 Quick Start 引用 Core 的标题）。
- 新读者走查：用一个未接触过项目的人（或模拟）按 Quick Start 完成 L1 任务，记录卡点。

### P1-C：registry readWhen 强制化

#### 现状

`registry.json` 的 `readWhen` 是描述性字段，无强制力。

#### 方案

- `task next` 在进入对应阶段前，检查 registry 中该阶段 readWhen 命中的 spec 是否在最近 N 轮对话被引用（通过会话记录或显式 ack）。
- 未命中则提示"建议先读 X"，但不阻塞（避免过度流程）。
- 阻塞仅对安全相关 spec（entry/dispatch）生效。

---

## P2 — 子系统去留决策

### P2-A：pattern 引擎盘点

#### 现状

四份 pattern + registry + TaskContext + Action + StepKind。`generic.next_action` 返回 None，`fan_out.py` 50 行。`PatternRegistry.select` 是 advisory。

#### 决策流程（必须基于数据）

1. **使用率盘点**：扫描 `tasks/archive/` 所有任务的 `task.pattern` 字段（或 task.json/meta），统计 generic/fan_out/pipeline/human_loop 各被多少任务用。
2. **消费方盘点**：grep `PatternRegistry.select` 的调用方；grep `next_action` 在 task.py/dashboard 的实际消费。
3. **决策矩阵**：

   | 场景 | 决策 |
   | --- | --- |
   | fan_out/pipeline/human_loop 使用率 > 阈值 | 保留，补足 registry advisory 的消费方 |
   | 使用率极低但有明确未来场景 | 保留但标注 experimental，移出 Core 文档 |
   | 使用率为零且无明确场景 | 精简为 generic + 显式 children 聚合逻辑（children 聚合下沉到 FlowStore，不依赖 pattern 类） |

4. **精简方案（若触发）**：
   - 删除 `patterns/fan_out.py` / `pipeline.py` / `human_loop.py`。
   - 保留 `generic.py` + `base.py`（TaskContext/Action/StepKind 作为数据结构保留）。
   - children 聚合逻辑（`all_children_done` 已在 FlowStore）直接被 task.py 调用，不经 pattern。
   - `PatternRegistry.select` 删除或改为纯标记。

#### 验证

- 决策结论 + 数据写入 design.md 本节（P2 task 完成时回填）。
- 若精简：失败回归测试断言"fan_out 任务的状态流转行为不变"（用 FlowStore 直接驱动，不经 pattern 类）。
- 若保留：补足 select 的消费方测试。

### P2-B：Party Mode 定位

#### 现状

至少 8 个 task 投入，纯 advisory，不能推进任务状态。消耗 runtime/看板/schema 校验/纠偏一整套基础设施。

#### 决策（二选一）

**选项 A：研究性能力。**
- 移出主 workflow.md（3.2/3.2.1 节移到 reference/party-mode/）。
- 停止基础设施扩张；后续只修 bug。
- 明确标注"experimental / research"。

**选项 B：生产特性。**
- 定义触发条件：任务规模阈值（如 L2 + 跨 N 层）才启用。
- 定义产出强制引用：Party Mode 报告的分歧/风险必须在 check.jsonl 里被显式回应（采纳/拒绝 + 理由）。
- 给 ROI 度量：统计启用 Party Mode 的任务 vs 未启用的，check 阶段返工率差异。

#### 决策依据

统计过去 10 天的 task：哪些用了 Party Mode？产出在后续决策中实际被引用了几次？如果引用率低，选 A；如果有可度量收益，选 B。

#### 验证

- 决策 + 数据写入 design.md 本节。
- 若选 A：workflow.md 瘦身测试（断言 3.2 节移除后主流程文档不超过 N 行）。
- 若选 B：新增"Party Mode 产出引用率"统计。

---

## P3 — 主会话减负 + 语言统一

### P3-A：机械协调下沉

#### 现状

`workflow.md:131` 主会话"派发所有子代理后逐个等待，核对汇报，再用适配器收口"。这套机械流程依赖主会话"自觉"，上下文压缩易漏步。`spawn-family`/`check-family` 已经迈出下沉第一步，但仅限 fan-out 父任务。

#### 方案

- 推广 `spawn-family`/`check-family` 模式到单任务派发：主会话只 `subagent init` + 派发，runtime 负责等待汇总、孤儿清理、超时收口。
- 主会话只发起 + 验收结果，不再手动 list/cancel。
- 适配器取消原语仍保留，但由 runtime 在收口时调用，不由主会话逐个调用。

#### 验证

- 失败回归测试：构造"子代理崩溃留孤儿"场景，断言 runtime 能自动清理（不经主会话手动 cancel）。
- 主会话派发步骤数减少的走查记录。

### P3-B：统一文档语言

#### 方案

- spec 工作语言定为全英文（Quick Start / Core / Reference）。
- AGENTS.md / workflow.md 保留中文摘要（面向中文开发者），但英文 spec 是权威，冲突以英文为准。
- entry classifier 的中英词表随 P0-A 结构化信号改造自然消解，无需单独删词表。
- 翻译分期进行：每期 task 顺手翻译触动的 spec，不做一次性全量翻译（避免大 diff）。

---

## P4 — 可观测性

### 现状

dashboard 有看板（board_view），audit 表有状态流转记录，但缺前端呈现：派发→binding→完成时间线、失败归因、readiness gate 通过率。

### 方案

- **时间线回放**：基于 audit + runtime_context 的时间戳，渲染一次任务从 planning → archived 的完整事件流。
- **失败归因聚类**：block 表的 reason 字段 + agent_run 的 error_message，按 reason 模式聚类，展示 top 失败原因。
- **readiness gate 通过率**：统计 task start 时 readiness 检查的通过/失败比，辅助判断 readiness 标准是否过严或过松。

### 验证

- dashboard 新页面只读，不引入新的写路径（与 06-14-db-runtime-maintenance 一致）。
- 数据全部来自现有表，不新增表。

---

## 横向约束

- **root/template 一致性**：每期 task 的 prd.md 必须列"模板同步项"，`npm run test:template` 在每期收口时必须通过。
- **失败回归测试优先**：每期先写会失败的测试，再实现（AGENTS.md 第 8 条）。
- **不静默删除已投入功能**：P2 去留决策必须基于数据，并在 design.md 记录被拒方案。
- **分期独立归档**：每期 task 完成后独立 archive；容器 change 在所有分期验收通过后 archive。

## 分期 task 拆分（P0-P4 各自的 task）

> 具体 task slug 在各期启动时由 `task create` 生成，以下为预期清单。

- P0-A: `entry-structured-signals`
- P0-B: `db-schema-versioning`
- P1-A: `runtime-agent-run-convergence`
- P1-B: `spec-three-layer`
- P1-C: `registry-readwhen-enforcement`
- P2-A: `pattern-engine-review`
- P2-B: `party-mode-positioning`
- P3-A: `runtime-coordination-sink`
- P3-B: `doc-language-unification`
- P4: `dashboard-observability`

## 开放问题

- P0-A 的结构化信号在三个宿主各自怎么获取？需要逐宿主调研（claude-code 的 hook 能不能拿到 session role？codex 的 thread 元数据？opencode 的 session context？）。这决定 P0-A 的实际工作量。
- P1-A 选方案 1 还是方案 2，取决于基线调研结果。P1-A task 启动时先做调研再定。
- P2 的使用率阈值怎么定？建议先出原始数据，阈值在 design review 时定。
