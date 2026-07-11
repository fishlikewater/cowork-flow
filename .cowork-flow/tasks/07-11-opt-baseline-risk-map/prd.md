# P0 规划基线与风险盘点

## Goal

在任何运行时重构前，建立 cowork-flow 优化路线图的事实基线、风险排序和验收边界。

## Scope

- 只读盘点当前 `.cowork-flow/scripts/`、`template/.cowork-flow/scripts/`、`src/`、`test/`、`tests/`、宿主资产和 spec 文档。
- 产出 baseline 报告，覆盖状态权威、文件复杂度、root/template 同步候选、测试覆盖缺口和阶段风险。
- 更新本任务上下文或 research 报告。

## Non-Goals

- 不修改 runtime 行为。
- 不删除兼容路径。
- 不重构 Python/Node 源码。
- 不归档当前 change。

## Acceptance Criteria

1. `research/baseline.md` 包含状态权威矩阵，列明每类状态的读入口、写入口、权威来源和风险等级。
2. baseline 报告列出前 20 个最大源文件/测试文件及拆分候选。
3. baseline 报告列出 root/template 应同步文件类别、允许差异类别和当前高风险漂移点。
4. baseline 报告将测试缺口映射到 P1/P2/P3 任务。
5. 报告不包含 TODO/TBD 占位。
6. `git diff --check` 通过。

## Relevant Files

- `.cowork-flow/plans/2026-07-11-workflow-optimization-roadmap.md`
- `.cowork-flow/changes/07-11-2026-07-11-workflow-optimization-roadmap/design.md`
- `.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/flow/store.py`
- `.cowork-flow/scripts/subagent.py`
- `.cowork-flow/scripts/doctor.py`
- `.cowork-flow/scripts/common/active_task.py`
- `.cowork-flow/scripts/common/execution_context.py`
- `template/.cowork-flow/scripts/`
- `src/`
- `test/`
- `tests/`

## Verification

- `git status --short`
- `git diff --check`
- Manual review of `.cowork-flow/tasks/07-11-opt-baseline-risk-map/research/baseline.md`