# Task Adopt Contract

**收养（adopt）是显式的归属修复动作：把一个由其它执行者占有、且已激活未完成的任务接管过来——重绑 executor、把评审基线重置到收养时 HEAD、保留状态、留下审计字段。**

收养不是生命周期迁移：它不推进 status、不豁免任何检查，也不与其它动作链式同发。它是 1.9.0 多执行者协作就绪的前置（多执行者生命周期领地），承载 2026-10-06 归档两个滞留任务时只能手改 task.json meta 的操作。

## 入口与动作边界

```bash
./.cowork-flow/run task next <task-dir> --run --adopt
```

- `--adopt` 由 `task next --run` 的投递层（`task_next_runner`）在动作解析前拦截，直接执行收养动作；不进入导航默认动作序列，也不与 review/complete/archive 迁移同发（下一步由使用者显式发起）。
- 无 `--run` 时 `--adopt` 与其它执行旗标一致：只读导航，不产生副作用。
- 组合拒绝（fail-closed，退出码 1，不改状态）：携带 create/plan 输入（`--title`/`--slug`/`--assignee`/`--priority`/`--description`/`--parent`/`--from-plan`）或批启动旗标（`--auto`/`--approved`）——收养与创建/批启动语义不同，需分两步。

## 前置条件（`LIFECYCLE-ADOPT-001`）

| 事实 | 要求 |
|---|---|
| 任务状态 | `in_progress` 或 `review`（已激活未完成；planning/completed/stale 拒绝） |
| 任务 executor | 已记录且非空（无归属的任务没有可收养对象） |
| 收养者身份 | 可解析且 ≠ 当前 executor；显式 `--executor <label>` 优先，否则取会话身份 |
| 身份来源 | process-fallback（共享进程标签）拒绝收养——归属必须来自真实会话身份或显式 label |
| 执行上下文 | delegated（worker/subagent）拒绝收养（`TASK-EXECUTION-001`，与其它生命周期变更一致） |

拒绝时不写 task.json、不改状态、不动会话绑定；blockers 说明具体原因。

## 收养写入（单次 UnitOfWork）

| 字段 | 写入 |
|---|---|
| `executor` | 收养者身份 |
| `meta.previousExecutor` | 原 executor（审计：原执行者） |
| `meta.previousBaseline` | 原 `meta.baselineCommit`（无则 `null`） |
| `meta.adoptedAt` | UTC 时间戳 `YYYY-MM-DDTHH:MM:SSZ` |
| `meta.baselineCommit` | **重置**为收养时 HEAD；无 git/无 HEAD 时写 `null`（降级 status-only） |
| `status` | 不变 |
| `_state.revision` / `_state.operation_id` | 修订递增，operation_id 含 `adopt` 标记（审计可追溯） |

结果 code `LIFECYCLE-EXECUTOR-ADOPTED`；`transition.changed=false`（不推进状态的事实位）；`check_result` 为 `null`（不豁免检查）。

## 基线与"永不覆盖"不变量的关系

- start 路径的写一次逻辑不变：**重复 start 永不覆盖已有 `meta.baselineCommit`**，既有测试零改动锁定该不变量。
- 收养是唯一经审计的显式重置路径：重置前把原值记入 `meta.previousBaseline`。
- 重置后的评审窗口 = 收养时未提交改动 + 收养之后的提交。收养前**已提交**的改动不进入本任务窗口（它们在 git 历史中，需由提交记录单独追溯）——这是收养的已知边界。
- 收养后基线再次回到"写一次"语义：后续 start 不会再次滑动。

## 会话绑定

收养成功后 CLI 把收养者会话绑定到该任务（与 `task next <dir>` 改绑、`task create` 创建后绑定同型），使后续 `task next <dir> --run` 可省略目录继续 review/complete/archive 链。

## 与 `--takeover` 的区别

| | `--takeover` | `--adopt` |
|---|---|---|
| 适用动作 | start_task（含幂等重跑） | 独立动作（本契约） |
| 状态要求 | 任意（只在 start 激活点生效） | `in_progress` / `review` |
| 基线 | 不动 | 重置到 HEAD（审计保留原值） |
| 审计字段 | 无 | `previousExecutor` / `previousBaseline` / `adoptedAt` |
| 结果 code | `LIFECYCLE-EXECUTOR-TAKEN-OVER` | `LIFECYCLE-EXECUTOR-ADOPTED` |

`--takeover` 语义保持原样；`--adopt` 是超集动作但不改写 takeover 路径（不变量与既有测试零改动）。
