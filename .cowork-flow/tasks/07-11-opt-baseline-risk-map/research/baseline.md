# Workflow Optimization Baseline

## 目标

本报告为 `2026-07-11-workflow-optimization-roadmap` 的 P0 基线，固定后续 P1/P2/P3 的排序依据、验收边界和风险口径。它只盘点当前状态，不修改运行时行为。

## 当前状态

- 当前分支：`dev-gof`。
- 当前任务：`.cowork-flow/tasks/07-11-opt-baseline-risk-map`。
- 启动状态：`task next` 显示 `Status: in_progress` 且 `Blockers: none`。
- 提交基线：`75cfbd1 chore(flow): add workflow optimization roadmap`。
- 工作区基线盘点前为 clean；P0 只新增本报告。

## 状态权威矩阵

| 状态域 | 当前权威 | 主要写入口 | 主要读入口 | 风险等级 | 优化方向 |
| --- | --- | --- | --- | --- | --- |
| 当前会话任务 | DB `runtime_session` | `common/active_task.py:set_active_task` -> `FlowStore.upsert_runtime_session` | `task current`、hook 状态注入、`common/active_task.py:get_active_task` | 高 | P1-C 固定 session key 解析、清理旧兼容读法、补 fail-closed 测试 |
| formal 子代理 runtime context | DB `runtime_context` | `subagent.py`、`common/active_task.py:resolve_runtime_context` 绑定更新 | Codex/Claude/OpenCode hook、`subagent check/close`、doctor | 高 | P1-C/P2-C 强化 missing/closed/mismatched/duplicate bind 测试 |
| formal 子代理 runtime session | DB `runtime_session`，scope=`subagent` | `active_task.py`、OpenCode plugin DB/历史兼容路径 | hook/plugin 注入、dashboard、subagent close | 高 | P1-C 明确 DB 权威，避免插件/历史文件态继续成为写入口 |
| task lifecycle | DB task 表 + task artifact | `task.py` -> `FlowStore` + pattern transition | `task next/list/current/review/complete/archive` | 高 | P2-A 拆出 lifecycle service，CLI 变薄，保持状态机兼容 |
| task/archive | 文件归档 + task 状态 | `task.py archive`、`change.py archive`、`archive_utils.py` | `task list-archive`、resume、finish-work | 中 | P1-A doctor 检查归档/状态冲突，P3 文档补状态图 |
| session journal | `.cowork-flow/workspace/<developer>/journal-*.md` | `add_session.py` | resume、人工审计 | 中 | P3 文档说明 closeout 顺序，P1-A doctor 检查 journal/任务状态冲突 |
| dashboard process | DB `dashboard_process` | `dashboard/server.py`、`FlowStore.upsert_dashboard_process` | dashboard UI、maintenance cleanup | 中 | P1-A doctor/release-health 汇总 stale dashboard process |
| DB migration | `schema_migrations` + migrations SQL | `FlowStore` 初始化、`flow migrate` | `flow migrate --status/--dry-run` | 高 | P2-B 拆分 migration 边界，补旧库/事务/checksum 测试 |
| root/template 分发状态 | root + `template/` 文件树 | `sync`、手动镜像、测试 | `test/sync.test.js`、`pack-check` | 高 | P1-B 建立强同步清单、允许差异清单和发布阻断 |

## 文件复杂度基线

| Lines | Path | 职责 | 拆分建议 |
| ---: | --- | --- | --- |
| 1893 | `.cowork-flow/scripts/task.py` | task CLI、生命周期、pattern、上下文、输出 | P2-A 优先拆 lifecycle service、pattern adapter、输出模型 |
| 1862 | `template/.cowork-flow/scripts/task.py` | template 镜像 | 跟随 P2-A 同步拆分 |
| 1325 | `tests/test_flow_script_paths.py` | 脚本路径/模板路径回归 | 可保持，P1-B sync gate 后考虑按主题拆分 |
| 1088 | `.cowork-flow/scripts/flow/store.py` | SQLite schema、migration、task/runtime/dashboard repository | P2-B 拆 migration 和 repository 边界 |
| 1088 | `template/.cowork-flow/scripts/flow/store.py` | template 镜像 | 跟随 P2-B 同步拆分 |
| 1037 | `.cowork-flow/scripts/party_mode_v2.py` | runtime board、schema、命令输出 | 暂不新增基础设施，只修 bug；保留为 reference 能力 |
| 1037 | `template/.cowork-flow/scripts/party_mode_v2.py` | template 镜像 | 同上 |
| 1008 | `tests/test_party_mode_v2.py` | Party Mode V2 行为测试 | 暂不拆，避免研究性能力扩大维护面 |
| 752 | `tests/test_subagent_dispatch.py` | formal subagent 契约测试 | P2-C 增强安全不变量，可后续按 init/bind/family 拆 |
| 733 | `.cowork-flow/scripts/common/git_context.py` | git diff、变更范围、任务快照 | P1-A doctor 可复用，不优先拆 |
| 635 | `.cowork-flow/scripts/subagent.py` | runtime context init/bind/check/close/family | P2-C 先补测试，再考虑服务化 |
| 617 | `tests/test_quality_gate.py` | 质量门禁测试 | 保持，避免浅测试回归 |
| 546 | `tests/test_codex_hooks.py` | Codex hook 状态注入 | P2-C 增强 formal dispatch 场景 |
| 541 | `.cowork-flow/scripts/doctor.py` | 安全/健康诊断 | P1-A 聚合 release health |
| 495 | `tests/test_claude_hooks.py` | Claude hook 状态注入 | P2-C 增强宿主矩阵 |
| 469 | `.cowork-flow/scripts/dashboard/static/app.js` | dashboard UI | P1-A 只读健康摘要，不优先改 UI |
| 440 | `.cowork-flow/scripts/dashboard/server.py` | dashboard API/server | P1-A stale process 检查可复用 |
| 393 | `tests/test_dashboard.py` | dashboard 回归 | P1-A doctor/dashboard 相关测试复用 |
| 376 | `tests/test_cowork_agents.py` | fixed agent 文本契约 | P2-C 增强禁止事项扫描 |
| 348 | `.opencode/plugins/cowork-flow.js` | OpenCode env/system 注入、runtime bind | P2-C 明确插件只是传输/注入层 |

## root/template 同步基线

### 应同步类别

- `.cowork-flow/scripts/**`：runtime 脚本和 helper，除 runtime 本地状态、archive、pycache 外应同步。
- `.cowork-flow/spec/**`：分发规范，活体契约应同步；项目本地追加规范需显式列入允许差异。
- `.agents/skills/**` 与 `template/.agents/skills/**`：Codex/OpenCode 通用技能分发面。
- `.codex/agents/**`、`.claude/skills/**`、`.opencode/plugins/**`：宿主资产，按平台同步。
- `src/**`、`scripts/**`、`test/**`、`tests/**`：仓库自身实现和验证，不直接镜像到目标项目，但必须保护分发行为。

### 允许差异类别

- `.cowork-flow/workspace/**`、`.cowork-flow/tasks/archive/**`、`.cowork-flow/changes/archive/**`、`.cowork-flow/.runtime/**`。
- `__pycache__`、`.pyc`、本地 dashboard/runtime 产物。
- 项目本地 `AGENTS.md` / `CLAUDE.md` 的 managed block 外用户内容。
- 目标项目本地 `.cowork-flow/config.yaml`，除 `--force` 或明确迁移任务外不覆盖。
- 分发模板中按宿主存在的资产差异，例如 Claude-only `.claude/**` 与 Codex-only `.codex/**`。

### 当前高风险漂移点

当前 hash 不一致的镜像文件：

- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/task.py`
- `.cowork-flow/spec/core/state-templates.md`
- `.claude/skills/continue/SKILL.md`
- `.claude/skills/finish-work/SKILL.md`
- `.claude/skills/start/SKILL.md`
- `.claude/skills/writing-plans/SKILL.md`

这些差异不一定都是错误；其中一部分可能是 root/template 对宿主或当前项目的刻意差异。P1-B 必须把“应同步”和“允许差异”变成机器可读清单，避免继续靠人工判断。

## 测试覆盖基线

### Node 测试

- `test/init.test.js`：初始化、平台过滤、技能安装。
- `test/sync.test.js`：模板同步、managed block、宿主资产刷新。
- `test/package.test.js`：包内容边界。
- `test/opencode-plugin.test.js`：OpenCode 插件注入。
- `test/release.test.js`、`test/update.test.js`、`test/cli.test.js`：发布、更新、CLI 基线。

### Python 测试

- lifecycle/state：`tests/test_lifecycle.py`、`tests/test_active_task_runtime.py`、`tests/test_change_script.py`。
- DB/migration：`tests/test_flow_store.py`、`tests/test_flow_migrate.py`、`tests/test_flow_migration.py`、`tests/test_flow_script_paths.py`。
- formal subagent/hooks：`tests/test_subagent_dispatch.py`、`tests/test_codex_hooks.py`、`tests/test_claude_hooks.py`、`tests/test_host_adapters.py`、`tests/test_cowork_agents.py`。
- quality gates：`tests/test_quality_gate.py`、`tests/test_rules_engine.py`、`tests/integration/test_spec_coding_gate.py`、`tests/integration/test_tdd_evidence.py`。
- docs/workflow contracts：`tests/test_workflow_parallel_sessions.py`、`tests/test_no_legacy_template_paths.py`。
- dashboard/party mode：`tests/test_dashboard.py`、`tests/test_party_mode_v2.py`。

### 测试缺口到任务映射

| 缺口 | 风险 | 对应任务 |
| --- | --- | --- |
| release health 没有单一聚合入口 | 维护者需要记多条命令，遗漏编码/同步/迁移问题 | P1-A doctor-release-health |
| root/template 允许差异没有机器清单 | 合法差异和真实漂移混在一起 | P1-B template-sync-gate |
| DB 权威与旧文件态兼容路径仍需矩阵化 | 子代理状态可能被误解为文件态或宿主态 | P1-C runtime-state-authority |
| `task.py` 生命周期逻辑过于集中 | 小改容易误伤状态机 | P2-A task-lifecycle-service |
| `FlowStore` 同时承担 schema/migration/repository | DB 迁移和 runtime 状态修改耦合 | P2-B flowstore-boundaries |
| formal subagent 宿主契约仍偏分散 | 宿主资产文案或插件逻辑漂移时不易定位 | P2-C subagent-contract-tests |
| README/文档缺少最小闭环和状态图 | 新用户需要读大量流程文档才能跑通 | P3 docs-onboarding-loop |

## 风险排序

| Priority | 风险 | 原因 | 先手动作 |
| --- | --- | --- | --- |
| P0 | 未确认基线就重构 | 容易把当前历史改动和新任务目标混在一起 | 本报告固定基线 |
| P1 | root/template 漂移 | 分发面质量直接影响用户安装/同步 | 先做 P1-B 门禁 |
| P1 | 缺少 release health 聚合 | 维护者靠记忆运行检查，容易漏项 | 先做 P1-A doctor |
| P1 | 状态权威误解 | formal subagent 安全链依赖 DB 权威 | P1-C 收敛状态矩阵和测试 |
| P2 | 大文件行为回归 | `task.py`、`FlowStore` 是核心状态链 | P2 前先有 P1 门禁保护 |
| P2 | 宿主契约漂移 | Codex/Claude/OpenCode 注入路径不同 | P2-C 固化跨宿主测试 |
| P3 | 文档与 runtime 不一致 | 用户照文档执行会失败或误解状态 | 等 P1/P2 稳定后重构文档 |

## 建议执行顺序

1. `07-11-opt-doctor-release-health` 与 `07-11-opt-template-sync-gate` 优先，二者低风险且能保护后续重构。
2. `07-11-opt-runtime-state-authority` 在 P1 门禁后执行，先清状态权威语义。
3. `07-11-opt-subagent-contract-tests` 可先补保护测试，再合并 P2 拆分。
4. `07-11-opt-task-lifecycle-service` 和 `07-11-opt-flowstore-boundaries` 错峰串行，避免同时触碰状态机和存储层。
5. `07-11-opt-docs-onboarding-loop` 最后做，确保文档写的是稳定后的真实命令和边界。

## 验收映射

- AC1 状态权威矩阵：已覆盖。
- AC2 前 20 个最大文件和拆分候选：已覆盖。
- AC3 root/template 同步类别、允许差异和高风险漂移点：已覆盖。
- AC4 测试缺口映射到 P1/P2/P3：已覆盖。
- AC5 无未完成占位语：报告未使用待补内容标记。
- AC6 `git diff --check`：在任务收口时执行。