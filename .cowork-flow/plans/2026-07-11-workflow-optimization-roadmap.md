# Workflow Optimization Roadmap Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** 分阶段降低 cowork-flow 的运行时复杂度、状态漂移风险和新用户上手成本，同时保持 runtime-context binding、fail-closed 与固定代理叶子边界不变。
**Architecture:** 先建立 P0 基线和风险地图，再做 P1 诊断/同步门禁，之后推进 P1/P2 状态权威与核心脚本拆分，最后重构文档闭环。所有 root/template 相关任务都显式同步，所有行为变化任务先补回归测试。
**Verification:** 每个任务执行局部测试；每个阶段收口运行 `git diff --check`、相关 Python/Node 测试、`npm run test:template` 或 `npm run test:all`；最终运行发布健康检查。

## 用户价值

- 维护者获得可排序、可验证、可并行评估的优化任务，而不是一次性大重构。
- 使用者获得更可靠的 doctor、模板同步门禁、子代理契约和文档闭环。
- 后续每个任务都有独立 PRD、上下文和验证命令，可以按风险逐步推进。

Execution strategy: serial by default. P1 doctor health 与 template sync gate 可在独立会话/独立 worktree 中并行；P2 的生命周期拆分、FlowStore 拆分和子代理契约测试必须错峰合并，避免同时触碰同一状态链。所有并行切片合并后必须执行最终集成验证。

## 关键假设

- 当前运行时状态权威继续收敛到 DB，不新增第二套状态。
- P1 门禁任务优先于 P2 结构拆分。
- P2 拆分默认行为保持，任何用户可见语义变化都必须另列验收标准。
- 每个任务开始前都要重新检查工作区未提交改动，避免纳入无关修改。

## 关联

- Change: `.cowork-flow/changes/07-11-2026-07-11-workflow-optimization-roadmap/`
- Proposal: `.cowork-flow/changes/07-11-2026-07-11-workflow-optimization-roadmap/proposal.md`
- Design: `.cowork-flow/changes/07-11-2026-07-11-workflow-optimization-roadmap/design.md`
- Spec: `.cowork-flow/changes/07-11-2026-07-11-workflow-optimization-roadmap/spec.md`

## 阶段总览

| Phase | Task slug | Priority | Level | Strategy |
| --- | --- | --- | --- | --- |
| P0 | `07-11-opt-baseline-risk-map` | P0 | L2 | 串行，先做只读基线 |
| P1-A | `07-11-opt-doctor-release-health` | P1 | L1 | 可与 P1-B 并行 |
| P1-B | `07-11-opt-template-sync-gate` | P1 | L1 | 可与 P1-A 并行 |
| P1-C | `07-11-opt-runtime-state-authority` | P1 | L2 | 串行，依赖 P0/P1 门禁 |
| P2-A | `07-11-opt-task-lifecycle-service` | P2 | L2 | 串行拆分，行为保持 |
| P2-B | `07-11-opt-flowstore-boundaries` | P2 | L2 | 串行拆分，避免与 P2-A 同时合并 |
| P2-C | `07-11-opt-subagent-contract-tests` | P2 | L2 | 可先补测试，合并前全量验证 |
| P3 | `07-11-opt-docs-onboarding-loop` | P3 | L1 | 依赖命令/边界稳定 |

## P0 — 规划基线与风险盘点

- [ ] Task: `07-11-opt-baseline-risk-map`
- 目标：形成后续优化的事实基线，避免在未确认状态权威、文件复杂度和测试缺口前直接重构。
- 修改文件：
  - `.cowork-flow/tasks/07-11-opt-baseline-risk-map/prd.md`
  - 可新增 `.cowork-flow/tasks/07-11-opt-baseline-risk-map/research/baseline.md`
- 执行步骤：
  1. 运行 `git status --short`，记录现有未提交改动，标注本任务不纳入的文件。
  2. 扫描 `.cowork-flow/scripts/`、`template/.cowork-flow/scripts/`、`src/`、`test/`、`tests/` 的文件行数和职责。
  3. 产出状态权威矩阵：active task、runtime context、runtime session、task lifecycle、archive、journal、dashboard。
  4. 产出 root/template 同步候选清单与允许差异清单初稿。
  5. 产出测试覆盖/缺口表，映射到后续 P1/P2 任务。
- 验证：
  - `git diff --check`
  - 人工检查 baseline 报告不含 TODO/TBD 占位。
  - `task next 07-11-opt-baseline-risk-map` 不显示 readiness blocker。

## P1-A — 强化 doctor 与发布前健康检查

- [ ] Task: `07-11-opt-doctor-release-health`
- 目标：让维护者用一个健康检查入口发现编码、同步、迁移、宿主契约和发布边界问题。
- 主要文件：
  - `.cowork-flow/scripts/doctor.py`
  - `template/.cowork-flow/scripts/doctor.py`
  - `scripts/pack-check.js`
  - `package.json`
  - `tests/test_*doctor*.py` 或现有 doctor/host/subagent 测试
- 执行步骤：
  1. 先补失败测试，定义 `doctor --release-health` 或等价命令的输出契约。
  2. 实现 BOM/UTF-8、DB migration、host adapter、subagent safety、root/template sync、pack boundary 的聚合检查。
  3. 统一失败输出为“当前状态 / 阻塞原因 / 下一条命令 / 涉及文件”。
  4. 将必要检查接入 `npm run pack:check` 或新增 package script。
  5. 同步 root/template doctor。
- 验证：
  - `.cowork-flow/run.cmd doctor --release-health`
  - `.cowork-flow/run.cmd doctor --subagent-safety`
  - `.cowork-flow/run.cmd python -m pytest tests/test_dashboard.py tests/test_host_adapters.py tests/test_subagent_dispatch.py -q`
  - `npm run pack:check`
  - `git diff --check`

## P1-B — 建立 root/template 同步强门禁

- [ ] Task: `07-11-opt-template-sync-gate`
- 目标：把 root/template 漂移从人工审查问题变成可测试、可阻断的问题。
- 主要文件：
  - `test/sync.test.js`
  - `scripts/pack-check.js`
  - `src/lib/copy-template.js`
  - `.cowork-flow/spec/registry.json`
  - root/template 对应脚本与 spec
- 执行步骤：
  1. 先补失败测试：构造一个 root/template 应同步文件差异，期望 sync check fail。
  2. 建立同步清单和允许差异清单；明确 archive、runtime、pycache、生成文件排除规则。
  3. 扩展现有 sync 测试或 pack check，输出具体漂移文件。
  4. 确认 package files 不包含 runtime 本地状态。
- 验证：
  - `npm test -- test/sync.test.js`
  - `npm run test:template`
  - `npm run pack:check`
  - `git diff --check`

## P1-C — 收敛运行时状态权威

- [ ] Task: `07-11-opt-runtime-state-authority`
- 目标：明确并收敛 active task、runtime context、runtime session、archive、journal 的读写入口，减少历史文件态和兼容路径。
- 主要文件：
  - `.cowork-flow/scripts/common/active_task.py`
  - `.cowork-flow/scripts/common/execution_context.py`
  - `.cowork-flow/scripts/subagent.py`
  - `.cowork-flow/scripts/task.py`
  - `.cowork-flow/scripts/flow/store.py`
  - `.cowork-flow/spec/core/dispatch.md`
  - `.cowork-flow/spec/core/lifecycle.md`
  - 宿主插件/agent/skill 资产及 template 镜像
- 执行步骤：
  1. 基于 P0 矩阵补状态权威回归测试。
  2. 标注仍存在的文件态读写：保留、迁移、删除。
  3. 先删除或隔离最安全的兼容读写点。
  4. 更新 spec 和宿主资产中的状态权威表述。
  5. 同步 template 并运行 sync gate。
- 验证：
  - `.cowork-flow/run.cmd python -m pytest tests/test_active_task_runtime.py tests/test_subagent_dispatch.py tests/test_host_adapters.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q`
  - `.cowork-flow/run.cmd doctor --subagent-safety`
  - `npm run test:template`
  - `git diff --check`

## P2-A — 拆分任务生命周期运行时服务层

- [ ] Task: `07-11-opt-task-lifecycle-service`
- 目标：把 `task.py` 从“命令解析 + 状态机 + pattern + 输出”拆成可测试服务层，保持 CLI 行为兼容。
- 主要文件：
  - `.cowork-flow/scripts/task.py`
  - `.cowork-flow/scripts/common/lifecycle.py`
  - 可新增 `.cowork-flow/scripts/task_lifecycle/` 或 `.cowork-flow/scripts/common/task_lifecycle.py`
  - `tests/test_lifecycle.py`
  - `tests/test_patterns.py`
  - template 镜像
- 执行步骤：
  1. 先补 lifecycle 行为测试，覆盖 start/review/complete/archive/block/unblock 与重复迁移拒绝。
  2. 提取纯服务：resolve task、pattern context、transition validation、state mutation、human output model。
  3. CLI 只保留 argparse、调用 service、格式化输出和退出码。
  4. 保持现有命令文本和退出码兼容；如有输出变化，PRD 中单独列出。
  5. 同步 template。
- 验证：
  - `.cowork-flow/run.cmd python -m pytest tests/test_lifecycle.py tests/test_patterns.py tests/test_flow_store.py -q`
  - `.cowork-flow/run.cmd task next 07-11-opt-task-lifecycle-service`
  - `npm run test:template`
  - `git diff --check`

## P2-B — 拆分 FlowStore 存储与迁移边界

- [ ] Task: `07-11-opt-flowstore-boundaries`
- 目标：把 `flow/store.py` 的 schema/migration、task repository、runtime repository、dashboard repository 职责拆清，保持 SQLite 行为兼容。
- 主要文件：
  - `.cowork-flow/scripts/flow/store.py`
  - `.cowork-flow/scripts/flow/migrate.py`
  - `.cowork-flow/scripts/flow/migrations/*.sql`
  - `tests/test_flow_store.py`
  - `tests/test_flow_migrate.py`
  - `tests/test_flow_migration.py`
  - template 镜像
- 执行步骤：
  1. 先补迁移和旧库兼容测试，固定 checksum、dry-run/status、事务失败行为。
  2. 提取 migration helper，保持 `FlowStore` public API 不变。
  3. 提取 task/runtime/dashboard repository 或等价内部模块。
  4. 保持 schema 兼容；如需新增 migration，必须补 dry-run/status 预期。
  5. 同步 template。
- 验证：
  - `.cowork-flow/run.cmd python -m pytest tests/test_flow_store.py tests/test_flow_migrate.py tests/test_flow_migration.py tests/test_flow_script_paths.py -q`
  - `.cowork-flow/run.cmd flow migrate --dry-run`
  - `.cowork-flow/run.cmd flow migrate --status`
  - `npm run test:template`
  - `git diff --check`

## P2-C — 强化正式子代理宿主契约测试

- [ ] Task: `07-11-opt-subagent-contract-tests`
- 目标：把 formal subagent 的宿主差异、绑定门禁和 fail-closed 安全边界固定为回归测试。
- 主要文件：
  - `.cowork-flow/scripts/subagent.py`
  - `.cowork-flow/scripts/common/entry_classifier.py`
  - `.cowork-flow/scripts/common/inject_workflow_state.py`
  - `.codex/agents/*.toml`
  - `.claude/skills/*/SKILL.md`
  - `.opencode/plugins/cowork-flow.js`
  - `tests/test_subagent_dispatch.py`
  - `tests/test_host_adapters.py`
  - `tests/test_codex_hooks.py`
  - `tests/test_claude_hooks.py`
  - `test/opencode-plugin.test.js`
- 执行步骤：
  1. 补 failing tests：missing/closed/mismatched runtime context 必须 fail-closed。
  2. 覆盖 duplicate bind 幂等和 different key bind 拒绝。
  3. 覆盖 host adapter payload 中的 `cowork_runtime_context_id` 与 `cowork_host_context_key`。
  4. 覆盖 fixed agent 文本禁止 start/resume/archive/commit/spawn。
  5. 覆盖主会话验收：dispatch payload 不等于 child accepted，必须 check/bind/close。
- 验证：
  - `.cowork-flow/run.cmd python -m pytest tests/test_subagent_dispatch.py tests/test_host_adapters.py tests/test_codex_hooks.py tests/test_claude_hooks.py -q`
  - `npm test -- test/opencode-plugin.test.js`
  - `.cowork-flow/run.cmd doctor --subagent-safety`
  - `git diff --check`

## P3 — 文档与新用户闭环体验重构

- [ ] Task: `07-11-opt-docs-onboarding-loop`
- 目标：让新用户能在 5 分钟内跑完最小闭环，让维护者能理解状态模型和宿主适配边界。
- 主要文件：
  - `README.md`
  - `.cowork-flow/workflow.md`
  - `.cowork-flow/spec/core/*.md`
  - `.cowork-flow/spec/reference/adapters/*.md`
  - `.agents/skills/start/SKILL.md`
  - `.agents/skills/writing-plans/SKILL.md`
  - template 镜像文档
- 执行步骤：
  1. README 收缩成入口页，拆出 quickstart、maintainer guide、runtime contract、adapter guide。
  2. 增加最小闭环 demo：初始化、创建 L0、上下文、start、review/check、complete/archive、add-session。
  3. 增加 Mermaid 状态图：change/plan/task/runtime_session/runtime_context/journal/archive。
  4. 校验文档命令仍存在，避免引用旧 `.runtime` 文件权威。
  5. 同步 template 文档和 skills。
- 验证：
  - `npm test -- test/sync.test.js test/package.test.js`
  - `.cowork-flow/run.cmd doctor --release-health`
  - 文档命令 smoke：`task --help`、`change --help`、`subagent --help`、`flow migrate --help`
  - `git diff --check`

## 最终集成验证

- [ ] `git status --short` 确认只纳入计划内文件。
- [ ] `git diff --check`。
- [ ] `npm run test:all`。
- [ ] `.cowork-flow/run.cmd python -m unittest discover -s tests -p "test_*.py"`。
- [ ] `.cowork-flow/run.cmd doctor --release-health`。
- [ ] `.cowork-flow/run.cmd doctor --subagent-safety`。
- [ ] `task next` 对所有任务不显示 readiness blocker。
- [ ] change validate 通过后归档。

## 风险与缓解

- 工作区已有未提交改动：每个任务开始前必须重新确认 diff，避免覆盖用户或其他任务改动。
- 大文件拆分容易扩大范围：P2 只做行为保持拆分，不顺手改 UX 或状态语义。
- root/template 同步容易漏：每个任务 PRD 都要求说明同步边界，并运行 sync gate。
- 子代理契约易受宿主差异影响：以 runtime context binding 和 fail-closed 为不变量，宿主适配只做传输层。