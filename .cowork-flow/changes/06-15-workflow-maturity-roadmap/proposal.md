# Workflow Maturity Roadmap

## Goal

在保持 cowork-flow 现有安全边界（runtime-context binding + fail-closed + 单一写入路径）的前提下，收敛概念密度、消除重叠数据模型、降低安全链脆弱性，并对低使用率子系统做去留决策，使框架进入可长期维护的成熟期。

## User Value

- 新用户能在 1 页 Quick Start 内理解 cowork-flow 的主流程，不被 entry/runtime/pattern/agent_run 等概念淹没。
- 主会话/子代理身份识别不再依赖关键词子串匹配，避免中文/变体措辞误判导致的 fail-closed 漏判或误判。
- DB schema 演进有版本化迁移机制，旧库升级不依赖手工修补。
- runtime_context / agent_run / runtime_session 三表语义边界清晰，不再出现两表合并去重的脆弱查询。
- pattern 引擎和 Party Mode 的存在各自有明确依据，没有"为完备而存在"的子系统持续消耗基础设施成本。

## Key Assumptions

- 现有 DB runtime 表（runtime_context/runtime_session/dashboard_process/maintenance_event/agent_run）已经稳定运行，本 change 不推翻已落地的 DB 统一成果，而是做减法和边界厘清。
- runtime-context binding 作为子代理身份源的设计保留；被改造的是 entry classifier 这条 main/read-only 弱信号链，而非 binding 强信号。
- pattern 决策层"纯函数 + FlowStore 单一写入"的职责切分保留；可被精简的是 pattern 的数量和 registry 的 advisory 路径。
- 宿主结构化信号（如会话类型、是否命令包装）宿主侧可获取；无法获取的宿主仍走兜底分类。
- 中文/英文混用问题随 spec 统一语言收敛，但 AGENTS.md / workflow.md 的中文摘要保留（面向开发者）。
- 本 change 是 P0-P4 路线图容器，实际落地拆成多个 task；proposal/design/spec 描述整体方向与分期，单个 task 再有自己的 PRD。

## Problem

经过 10 天的快速迭代（party-mode → flow 重构 → pattern 引擎 → dashboard → 发布验证），cowork-flow 暴露了五类成熟期问题：

1. **安全链脆弱**：`entry_classifier.py` 用中英文关键词子串匹配判定 MAIN_SESSION/READ_ONLY/COMMAND_ONLY，confidence 取固定值。这是 fail-closed 的守门人，但判别能力低于它守护的系统所需；中文措辞变体、复合句式、新词都会漏判或误判。

2. **数据模型重叠**：`runtime_context` / `agent_run` / `runtime_session` 三表语义边界模糊。`list_agent_runs_for_parent`/`list_agent_runs_for_task` 要合并两表结果并去重，说明 agent_run 的信息和 runtime_context 高度重叠；`subagent-dispatch.md` 自承"advisory dispatch 不创建 agent_run 行"，进一步说明两表语义不一致。同时 schema 无版本管理，演进靠 `CREATE IF NOT EXISTS` 幂等 + 一次性 migrate.py，旧库升级有隐患。

3. **概念密度过高**：entry contract / runtime context / runtime session / agent_run / binding gate / pattern / TaskContext / host adapter / capabilities / skills / JSONL 上下文 / changes / plans / readiness gate 共 13+ 概念。核心规范（workflow.md + subagent-dispatch.md + entry-contract.md + patterns/* + workflow-state-templates.md）超过 1000 行。新接触者认知负担接近成熟 CI/CD 系统。

4. **pattern 引擎偏重**：四份 pattern（generic/fan_out/pipeline/human_loop）+ registry + TaskContext + Action + StepKind 是完整 state machine 框架，但 `generic.next_action` 直接返回 None，`fan_out.py` 全文 50 行。`PatternRegistry.select` 是 advisory，但若结果无人采用则是死代码。当前抽象重量超过实际产出。

5. **Party Mode 投入产出比存疑**：party-mode / party-mode-v2 / debate-rules / interaction-rules / live-child-timeout / round-intent / runtime-board / runtime-hardening 至少 8 个 task 已投在 Party Mode 上，但它"不能推进任务状态、不能满足实现或检查完成条件、不能替代固定代理"。需要诚实判断它是研究价值还是工程价值。

此外还有两个次要问题：skill 与 spec/workflow 内容重叠导致漂移风险（已有 `06-15-spec-phase-label-cleanup` 任务在做类似清理）；主会话机械协调（派发后逐个等待 + 收口）依赖"自觉"，上下文压缩易漏步。

## Scope

按优先级分期，本 change 作为路线图容器覆盖全部 P0-P4：

### P0 — 降低安全链脆弱性
- 将 main/read-only/command 分类从 prompt 文本迁移到宿主结构化信号。
- entry classifier 退化为"校验结构化信号 + 兜底"，不再做关键词猜测。
- 新增 DB schema 版本表与顺序迁移机制。

### P1 — 收敛概念，分层文档
- 规范分三层：Quick Start / Core Protocol / Reference。
- 合并 agent_run 进 runtime_context，或明确二者硬边界，干掉两表合并去重查询。
- registry.json 的 readWhen 做成强制加载路径。

### P2 — pattern 引擎去留
- 盘点 generic 之外三种 pattern 的实际使用率。
- 据使用率决定：精简为 generic + 显式 children 聚合，或保留并补足 registry advisory 的实际消费方。

### P2 — Party Mode 定位决策
- 明确二选一：研究性能力（移出主 workflow.md）或生产特性（定义触发规模 + 强制引用产出）。

### P3 — 主会话减负
- 把"派发后逐个等待 + 收口"下沉到 runtime，推广 spawn-family/check-family 模式到单任务派发。

### P3 — 统一文档语言
- 选定 spec 工作语言（建议全英文），AGENTS.md / workflow.md 保留中文摘要。
- entry classifier 中英词表随语言统一自然消解。

### P4 — 可观测性
- 在 dashboard 补：派发→binding→完成时间线回放、失败归因聚类、readiness gate 通过率。

### 横向
- root/template 实现保持一致（项目惯例）。
- 每期 task 必须含失败回归测试，符合 AGENTS.md 第 8 条。
- 不在单期内同时改安全模型和数据模型，避免爆炸半径过大。

## Non-Goals

- 不重写 runtime-context binding 协议（它是核心资产）。
- 不把 PRD/plan/change/spec 文档塞进 DB（已在 06-14-db-runtime-maintenance 中明确）。
- 不在本 change 内完成所有 P0-P4 实现；本 change 是方向容器，单期 task 各自有 PRD 和验收。
- 不为一次性代码做提前抽象（AGENTS.md 第 2 条）。
- 不引入全局后台 daemon（与 06-14-db-runtime-maintenance Non-Goals 一致）。
- 不删除 pattern 引擎或 Party Mode 作为隐藏动作；去留决策必须基于使用率数据并写入 design.md。
- 不改动宿主适配器的能力声明结构（adapter.yaml schema），只改其消费方式。

## Acceptance Criteria

本 change 作为路线图容器，整体验收以"各期 task 完成 + 总体目标达成"为准。分期验收标准见 design.md。以下为容器级验收：

1. 存在分期 task 列表，覆盖 P0-P4 所有方向，每期有明确 PRD、范围边界和验收命令。
2. P0 两项（entry 结构化信号、schema 版本迁移）有失败回归测试，且测试在安全链被破坏时能失败。
3. P1 的 agent_run/runtime_context 收敛方案有"改前改后查询结果一致"的基线测试（AGENTS.md 第 4 条）。
4. P2 的 pattern 与 Party Mode 去留决策有使用率数据支撑，并写入 design.md。
5. design.md 给出分期顺序、依赖关系、风险与回滚策略。
6. spec.md 列出涉及的所有契约变更点（entry contract 版本、schema version、runtime table 边界等）。
7. root/template 一致性测试在分期落地后仍通过。
8. 不存在"为完备而存在"的子系统在无决策记录的情况下继续扩张。

## Risks

- **分期跨度大，中途漂移**：本 change 覆盖 P0-P4，跨多期 task。缓解：每期 task 独立 PRD + 独立验收；容器 change 只在所有分期验收通过后 archive。
- **安全链改造期间出现保护空窗**：entry classifier 改造若分阶段，可能出现"旧文本分类已下线、新结构化信号尚未在所有宿主落地"的空窗。缓解：保留旧 classifier 作为 fallback，新信号优先但兜底；空窗期 fail-closed 仍生效。
- **DB schema 迁移破坏旧库**：版本化迁移若脚本顺序错或幂等性不足，旧库升级会丢数据。缓解：每步迁移可 dry-run、有回滚、在 CI 跑全量旧库样本。
- **pattern/Party Mode 去留引发争议**：去留决策涉及已投入功能，可能被视为推翻前序工作。缓解：决策基于使用率数据，design.md 显式记录被拒方案与理由（AGENTS.md 第 7 条）。
- **概念分层导致文档重复**：三层文档若不严格区分读者，会出现同一段内容复制三份。缓解：Quick Start 只放索引和最小流程，Core Protocol 放规则正文，Reference 放细节；同一条规则只有一个权威位置。
- **root/template 同步成本**：每期改动需双写。缓解：靠 `npm run test:template` 约束，单期不破例。
