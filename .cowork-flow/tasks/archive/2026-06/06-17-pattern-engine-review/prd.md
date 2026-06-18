# P2-A: Pattern Engine Simplification

## Goal

精简 pattern 引擎：删除 fan_out/pipeline/human_loop 三个零使用率的 pattern，保留 generic + base 数据结构。`PatternRegistry.select` 删除。children 聚合逻辑直接由 task.py 调用 FlowStore，不经过 pattern 类。

## Background

### 使用率数据

扫描 `.cowork-flow/tasks/archive/2026-06/` 下全部 26 个归档任务：

| Pattern | 使用任务数 |
|---|---|
| generic | 0 |
| fan_out | 0 |
| pipeline | 0 |
| human_loop | 0 |
| 无 pattern 字段 | 26 |

### 消费方盘点

- `PatternRegistry.select`：零调用方。仅在 spec 文档和 design.md 中被提及。
- `pattern.next_action()`：唯一消费者是 `scripts/task.py:_pattern_next_action_for_task()`，调用 `PatternRegistry.resolve()`（非 `select`）。由于无任务设置 pattern 字段，`resolve()` 总是返回 generic，其 `next_action()` 永远返回 None。
- `pattern.validate()` / `pattern.can_transition()`：在 `task.py` 的 `cmd_start` / `cmd_review` / `cmd_complete` 中被调用，但始终走 generic 路径，验证永远通过。

### 决策

设计文档 P2-A 决策矩阵第三条："使用率为零且无明确场景 → 精简为 generic + 显式 children 聚合逻辑"。

children 聚合逻辑（`all_children_done` 等）已在 FlowStore 中，task.py 可直接调用，无需 pattern 层。

## Scope

### 代码改动

1. **删除文件**：
   - `patterns/fan_out.py`（50 行）
   - `patterns/pipeline.py`（71 行）
   - `patterns/human_loop.py`（55 行）

2. **精简 `patterns/base.py`**：
   - 保留 `TaskView`、`BlockView`、`TaskContext`、`Action` 数据结构（task.py 仍在使用）。
   - 保留 `StepKind` 枚举（task.py `_print_pattern_action` 使用）。
   - 保留 `Pattern` 抽象基类（generic.py 继承）。
   - 删除 `WAIT_CHILDREN`、`HUMAN_DECISION`、`DISPATCH` 枚举值（仅被删除的 pattern 使用）。
   - 保留 `START`、`REVIEW`、`COMPLETE`、`ARCHIVE`（generic.py 使用）。

3. **精简 `patterns/registry.py`**：
   - 删除 `select()` 方法（dead code）。
   - 删除 `FanOut`、`Pipeline`、`HumanLoop` 导入。
   - `create_registry()` 只注册 `Generic`。
   - `resolve()` 行为不变。

4. **精简 `patterns/__init__.py`**：
   - 删除 `FanOut`、`Pipeline`、`HumanLoop` 导出。

5. **`scripts/task.py` 适配**：
   - `_pattern_next_action_for_task()` 不再返回有意义的 Action（generic 的 `next_action` 永远返回 None），但保留函数签名以防未来扩展。
   - `_pattern_transition_issues()` 和 `_pattern_action` 相关逻辑保留（generic 仍提供 valid_transitions 校验）。
   - `_complete_pipeline_stage()` 函数可简化或删除（pipeline 已不存在）。

6. **spec 文档更新**：
   - `spec/reference/patterns/index.md`：删除 fan_out/pipeline/human_loop 描述，只保留 generic 说明。
   - 删除 `spec/reference/patterns/fan-out.md`、`pipeline.md`、`human-loop.md`。

7. **模板同步**：root ↔ template 一致性。

### Non-Goals

- 不实现 children 聚合的 pattern 替代（children 聚合已由 FlowStore 提供，task.py 可直接调用）。
- 不实现 `PatternRegistry.select` 的替代方案。
- 不改动 `valid_transitions` 的核心校验逻辑（generic 仍作为状态机守卫）。

## Acceptance Criteria

1. `fan_out.py`、`pipeline.py`、`human_loop.py` 已删除。
2. `PatternRegistry.select` 已删除。
3. `create_registry()` 只返回 Generic 注册。
4. `task start` / `task review` / `task complete` 行为不变（generic transitions 仍生效）。
5. `npm run test:template` 通过。
6. root ↔ template 一致性。

## Verification

- `python -m pytest tests/test_flow_script_paths.py -v -k pattern`
- `rtk npm run test:template`

## 关联

- Change: `06-15-workflow-maturity-roadmap`（P2-A）
- Plan: `2026-06-15-workflow-maturity-roadmap.md` P2-A Phase
- 上游依赖：P1-B（spec 三层分层已完成）
