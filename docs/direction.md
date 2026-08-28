# cowork-flow 方向规划：Agent 运行时上下文与协作事实层

> 状态：**已批准（Approved）** · 创建：2026-08-27 · 决策记录：注入格式取舍选**方案 A**（结构化事实头 + 人读摘要体，分级降级）
> 本文档是后续阶段立项的权威输入。任何方向的修订必须先更新本文档再立项。

---

## 0. 状态追踪（防遗忘，后续会话先看这里）

| 阶段 | 状态 | 关联任务 / 提交 | 下一动作 |
|---|---|---|---|
| 阶段 0：定位与协议收敛 | ✅ 完成 | 08-27-stage0-positioning-protocol（0c7ae64） | — |
| 阶段 1：事实层 API 化 + 注入结构化 | ✅ 完成 | 1a: 08-28-stage1a-state-fact-view（60753fa）；1b: 08-28-stage1b-structured-fact-header（5cb25ea） | — |
| 阶段 2：多执行者语义 | ⬜ 未开始 | — | 立项：owner/executor 归属 + 无会话推进 + 多会话协调 |
| 阶段 3：协议生态适配 | ⬜ 未开始（观察期） | — | 依赖阶段 2；观察 MCP/AGNTCY |
| 本规划文档落库 | ✅ 完成 | 08-27-direction-doc | — |

**当前结论**：阶段 0、1 已完成（事实视图 CLI + 属性化注入头 + 决策要点注入，三线一致并有测试锁定）；下一个动作 = 阶段 2 立项。

---

## 1. 定位（一句话）

> **cowork-flow 不约束模型怎么想；它保证任何主机上的任何 agent，在任何会话、任何时刻，从同一份权威事实起步。**

| | 旧定位 | 新定位 |
|---|---|---|
| 叙事 | 帮你建流程（流程模板） | 运行时上下文与协作事实层 |
| 手段 | 任务流、门禁、规格文档 | 状态注入、事实一致性、跨宿主治理 |
| 目的 | 让协作"守规矩" | 让协作"从正确状态起步" |
| 模型能力上升时 | 约束类价值递减（模型自己会守规矩） | 事实类价值递增（状态是模型编不出来的） |

**为什么必须现在调整**：项目的消费方正在从"人"变成"agent"。注入格式还停留在给人看的文本（`<workflow-state>` 的 label:value 行 + 散文，全五宿主一致；唯一严格机器可读的是 fingerprint 属性行）。事实层（task.json+revision、state-snapshot、operations 日志、implement.jsonl、contract-registry、host-assets）已经建起来，但散落成文件约定，没有统一机器出口；决策事实（decision-anchor）完全不在注入体系内。

## 2. 背景：大模型发展对项目的五个冲击

1. **模型能力上升** → "约束模型"价值递减（门禁、防呆、状态机防漂移——模型越强越不需要被管），"喂状态"价值递增（上下文质量成为 agent 质量的第一杠杆）。
2. **人机对话 → agent 集群执行**（远程/后台/并行/批处理/CI 触发）→ 会话模型需支持无会话执行者、多执行者协作、委派与收归。
3. **上下文工程成为学科**（token 预算、注入时机、摘要压缩、状态新鲜度）→ 项目已有的五宿主 hook 注入、digest 指纹、快照单源正是"运行时上下文中枢"，应提升为产品主线。
4. **协议标准化**（MCP 成事实标准、hooks.json 类扩展点演化、agent 间协议涌现）→ 契约格式自持、host 适配保持薄层；不自创跨 agent 协议。
5. **模型质量波动** → 门禁仍是安全网（每个新版本可能有行为回归），保留但不作为卖点投资。

## 3. 现状资产盘点（2026-08-27 探查实录）

### 3.1 注入层

| Host | 注入机制 | 触发时机 | 格式 |
|---|---|---|---|
| zcode | 插件 process hook（JS，inject-context.js） | SessionStart 全量 / 每条消息单行指纹 / PostToolUse 生命周期命令刷新 | stdout JSON，内部文本块 |
| codex | hooks.json 命令（Python） | 仅 UserPromptSubmit | 全量 digest（无 slim） |
| claude-code | settings.json hook（Python） | SessionStart + 每条消息 | 全量 digest（无 slim） |
| opencode | 插件（JS） | 每次 prompt 组装 + shell.env | 全量 digest（无 slim） |
| dsh | 预设插件（内嵌 Python 协议） | session-start / inbox-claimed / 生命周期命令工具结果 | systemPrompt section 文本 |

**已知债**：三线零代码共享（zcode JS / opencode JS / python 线）——指纹序列化策略不一致（`JSON.stringify` 不排序 vs `sort_keys` vs `stableStringify`，跨 host 指纹有分叉风险）；slim 指纹形态只有 zcode 有；codex 事件名硬编码丢弃事件维度；state-snapshot 只有 zcode 消费（Python 线仍 TAG_RE 解析 templates.md，是已确认的漂移面）。

### 3.2 事实层（任务状态模型）

- **权威事实（生命周期内不变）**：id/name、title、creator、assignee、createdAt、priority、description；决策事实 decision-anchor.md（目标/AC/被拒方案/假设/范围）；绑定事实 `task.json.meta.planFile`；写入痕迹 `_state.revision`+`operation_id` 与 operations/ 操作日志（追加式）。
- **流程状态（有明确写者）**：status（planning→in_progress→review→completed，单向禁回退）、completedAt、children/parent、会话绑定（sessions/*.json、subagents/*.json）、state-snapshot.json、归档位置。
- **死字段待清理**：`commit`（声明存在、无写入方）、`scope`、`relatedFiles`（已被 implement.jsonl 取代）、`subtasks`（无写入方）。
- **模型**：单主人同步推进（start 必须会话身份；review/complete 已支持无会话）；子代理为受缚叶执行者（authority 五项全 false，证据生产不推进状态）；并发正确性靠 CAS+锁+UoW 恢复，已成熟。
- **机器出口现状**：JSON 有 task.json、snapshot、implement.jsonl、sessions/subagents、operations、`task next --json`、contract-registry、host-assets；**仅人读无解析**：decision-anchor.md（只查章节字符串）、plans/*.md（v1 显式不解析）。

### 3.3 治理层

- 分层哲学已验证：**机器只裁决事实，判断交给 review 双人证**。
- 硬契约：host-assets.json（能力矩阵，doctor 交叉校验）、contract-registry.json（指纹清单）、schemas/、lifecycle 文件范围白名单、plan-binding gate、发布链（release:check + CHANGELOG + 三处版本同步）。
- 软规范：backend/frontend/game（review 强审查、非机器 gate）、references/（loadWhen 驱动）。
- 模型能力上升时：纯防呆类（guides、error-output-as-data 类）价值递减；跨宿主一致性类（host-assets 校验、分布漂移检测、syncPolicy 保护、registry 指纹）价值递增。

## 4. 为什么这是最优方向（候选否决）

| 候选 | 否决理由 |
|---|---|
| AgentOps / 可观测性 | 无运行遥测资产，从头建等于换赛道，与工作流引擎定位断裂 |
| 任务编排引擎 | 与主机自带编排重叠；状态模型翻成分布式系统复杂度爆炸 |
| 纯治理合规层 | 纯门禁价值随模型自觉性上升递减；无独特性 |
| ✅ 事实层 + 注入 | 全仓最厚资产都在这；跨主机一致性是任何单主机工具给不了的**结构性差异**；与上下文工程趋势同向且落在可执行的事实层 |

## 5. 三支柱

| 支柱 | 内涵 | 已有资产 | 缺口 |
|---|---|---|---|
| **事实层** | 权威状态与决策的可查询存储 | task.json+revision、snapshot、operations、implement.jsonl、registry、host-assets | 无统一机器出口；decision-anchor 无解析；死字段 |
| **注入协议** | 按时机/角色/token 预算把事实注入任意 host | 五宿主注入齐备、digest 指纹、快照信任链、会话隔离 | 人读文本格式；三线拷贝；slim 不对称；决策事实不注入 |
| **一致性治理** | 跨宿主/跨会话/跨模型的事实一致性 | doctor 交叉校验、同步保护、文件范围门禁、发布链 | 指纹序列化不一致；快照单宿主消费；无跨 host 注入行为断言 |

## 6. 演进路线

### 阶段 0：定位与协议收敛（低风险、高杠杆）
- 交付：README 定位改写；新增 `spec/contracts/context-injection.md`（冻结块结构、事件时机矩阵、slim 策略、序列化规范，三线按规范对齐）；修一致性债（指纹序列化统一 sort_keys、Python 线补 slim、codex 补事件名）。
- 验收：新增跨 host 注入行为测试——同一仓库五宿主指纹一致、slim 触发一致。

### 阶段 1：事实层 API 化 + 注入结构化
- 交付：`cowork-flow state <task> --json`（task.json+snapshot+sessions+plan 绑定+registry 汇总为一份事实视图）；workflow-state 块升级为**结构化事实头 + 紧凑人读体**（协议允许分级降级，纯文本通道退化为属性行）；决策事实条件注入（planning/in_progress 时注入 decision-anchor 要点，完成后收缩）。
- 验收：任何 host 的 agent 可经上下文与 CLI 拿到"任务是什么、为什么、边界在哪"，且机器可解析。

### 阶段 2：多执行者语义
- 交付：owner/executor 归属字段；无会话推进放开（CLI/CI 触发）；多会话协作同一任务的协调（任务级锁/合并协议，复用 CAS+UoW）；子代理证据位独立于状态位。
- 验收：两会话可显式接管同一任务不踩踏；子代理证据可独立推进"证据位"。

### 阶段 3：协议生态适配（观察期，不承诺）
- 交付：MCP 服务暴露事实层（只读查询先行，`state --json` 的薄壳）；观察 AGNTCY 等，不自创协议；保持 adapter 薄。
- 验收：任何 MCP 客户端可查任务状态；生态协议出现时 2 天内可接入。

## 7. 已拍板取舍

- **注入格式（已决策：方案 A）**：结构化事实头 + 人读摘要体双格式，分级降级——结构化优先，通道不允许时退化为属性行/纯摘要。
  - 否决 B（全 JSON 注入）：dsh/codex 纯文本通道浪费 token，破坏现有紧凑散文面包屑可读性。
  - 否决 C（保持文本只加 --json 出口）：核心价值主张落不到注入本身。
- **事实层出口（推荐）**：CLI + JSON 协议先行（零依赖），MCP 为阶段 3 的薄适配，不先建。
- **三线收敛（推荐）**：先"协议规范单源 + 三线按规范实现"，代码级共享后议（成本高、收益在协议一致性先兑现）。

## 8. 明确不做什么

1. 不做"更聪明的提示词/AGENTS.md 写作术"——模型能力会追平，且无数据资产。
2. 不自创跨 agent 通信标准——协议博弈期，等收敛。
3. 不做任务执行引擎——不替代 agent 干活，只保证它从正确状态起步。
4. 不深化纯流程门禁——保留为安全网，停止投资。

## 9. 度量指标

1. **跨宿主行为一致**：五宿主指纹/slim 触发有测试断言，0 漂移。
2. **新 host 接入成本**：从数天降到小时级（协议规范完备度直接度量）。
3. **注入 token 成本**：长会话注入体积不随消息数线性增长（slim 全覆盖）。
4. **事实新鲜度事故**：多会话任务污染/踩踏事故率趋零。

## 10. 修订记录

- 2026-08-27：创建。基于三路只读探查（注入层/状态模型/治理层）+ 大模型趋势分析；用户拍板方案 A；落库任务 08-27-direction-doc。
- 2026-08-27：阶段 0 完成并更新状态追踪。交付：README 定位改写、`spec/contracts/context-injection.md` 协议契约、指纹序列化三线统一（跨 host 一致性测试锁定）、Python 线/opencode/dsh slim、codex 事件名。任务 08-27-stage0-positioning-protocol（0c7ae64）。
- 2026-08-28：阶段 1 完成并更新状态追踪。1a：`run state [task] --json` 事实视图（60753fa）。1b：`<workflow-state>` 属性事实头 + `<decision-anchor>` 决策要点注入，三线一致，协议契约同步（5cb25ea）。