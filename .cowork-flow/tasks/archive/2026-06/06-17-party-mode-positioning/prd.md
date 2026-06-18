# P2-B: Party Mode Positioning

## Goal

将 Party Mode 从生产级 workflow 组件降级为研究性能力。Party Mode V1/V2 的 skill 和 runtime 代码保留，但从 `workflow.md` 主流程中移除，归入 `spec/reference/party-mode/`。

## Background

### 使用率数据

扫描 `.cowork-flow/tasks/archive/2026-06/` 下全部归档任务：

| 指标 | 值 |
|---|---|
| Party Mode 相关 task 总数 | 12 |
| 其中构建/打磨 Party Mode 本身的 task | 12 |
| 使用 Party Mode 做实际决策的 task | 0 |
| 引用率 | 0% |

所有 12 个 task 都是开发 Party Mode 功能本身（V1 创建、V1 规则澄清、V2 设计、V2 实现、V2 加固），没有一个 task 将 Party Mode 用于实际技术或产品决策。

### 决策

design.md P2-B 决策矩阵："如果引用率低，选 A（研究性能力）。"

选 A：Party Mode 定位为 experimental / research，从主 workflow 移出，后续只修 bug。

## Scope

### 代码改动

1. **`workflow.md` 瘦身**：
   - 删除 §3.2（手动 Party Mode，4 行）和 §3.2.1（手动 Party Mode V2，5 行）。
   - workflow.md 从 250 行减少到约 241 行。

2. **`spec/reference/party-mode/` 新建**：
   - 创建 `spec/reference/party-mode/index.md`，包含原 3.2/3.2.1 内容，加 "experimental / research" 标注。
   - 原 `spec/reference/party-mode-v2-board.md` 保持不变（已在 reference 层）。

3. **skill 描述更新**：
   - `party-mode` skill 的 SKILL.md 描述加 "experimental / research" 前缀。
   - `party-mode-v2` skill 的 SKILL.md 描述加 "experimental / research" 前缀。
   - 更新 root 和 template 的 skill 副本。

4. **`registry.json` 降级**：
   - `FLOW_PARTY_MODE_V2_BOARD_V1` contract 的 `path` 保持不变（已在 reference 层）。
   - `readWhen` 从主流程门禁降级为 "when explicitly using Party Mode"。

5. **模板同步**：root ↔ template 一致性。

### Non-Goals

- 不删除 Party Mode skill、runtime 代码或测试。
- 不改变 Party Mode 的 advisory 行为。
- 不新增 Party Mode 的触发条件或产出引用机制（选项 B 不采用）。

## Acceptance Criteria

1. `workflow.md` 不再包含 "Party Mode" 或 "3.2" 相关内容。
2. `spec/reference/party-mode/index.md` 存在且包含原 3.2/3.2.1 内容。
3. party-mode / party-mode-v2 skill 描述包含 "experimental / research"。
4. root ↔ template 一致性。
5. `npm run test:template` 通过（P2-B 相关测试）。

## Verification

- `python -m pytest tests/test_workflow_parallel_sessions.py -v -k party`
- `rtk npm run test:template`
