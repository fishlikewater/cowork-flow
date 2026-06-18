# P1-C: registry readWhen 强制化

## Goal

将 `registry.json` 的 `readWhen` 从纯描述性字段升级为"可检查 + 可阻塞"的机制。关键安全 spec（entry/dispatch）在触发点上强制要求确认已读；非安全 spec 给出建议提示但不阻塞。

## Background

P1-B 完成了 spec 三层分层（quick-start / core / reference），`registry.json` 中已有 8 个 `contracts` 项，每个都有 `readWhen` 声明。但当前 `readWhen` 只是描述——hook 注入 digest 时会带上 `read_before` 提示，代码也不会校验。

`inject_workflow_state.py:build_contract_digest` 把 `readWhen` 编译到 prompt digest 中（`read_before: ...`），但这是纯提示性质的，AI 可以完全忽略。

`task.py` 在多个生命周期节点有阻塞检查：
- `cmd_start` → `_task_start_blockers` + `_optional_readiness_blockers`（L2 readiness）
- `cmd_next` → `_task_next_blockers`

但没有任何一个环节检查 registry 的 `readWhen`。

## Scope

### 代码改动

1. **新增 `common/contract_check.py`**：
   - 读取 `registry.json`，按 `readWhen` 触发条件分组。
   - 提供 `check_read_when(repo_root, trigger, task_path)` 函数：
     - `trigger` 值：`task_start` / `task_resume` / `task_archive` / `subagent_dispatch` / `subagent_bind` / `prompt_conflict`
     - 返回阻塞列表（blocking）和建议列表（advisory）。
   - 阻塞判定逻辑：
     - 安全 spec（`id` 包含 `ENTRY` 或 `DISPATCH`）：检查最近的会话记录或 git 工作树中是否引用过对应 spec 文件路径。若未引用 → 阻塞。
     - 非安全 spec：检查是否曾在最近 N 轮被引用过。若未引用 → 建议（不阻塞）。
   - "已引用"判定：扫描 git diff（未提交）和已提交最近的 50 行 commit message + PRD/check 文件内容，确认出现过 spec 文件路径的关键词匹配。

2. **集成到 `task.py` 的 `cmd_start`**：
   - 在现有 `_task_start_blockers` 之后，追加 `check_read_when(repo_root, 'task_start', task_dir)` 的结果作为 blockers。

3. **集成到 `task.py` 的 `cmd_next`**：
   - 在 blockers 输出中追加 `readWhen` 建议（不阻塞）。

4. **集成到 hook 注入流程**：
   - 在 `inject_workflow_state.py` 的 digest 构建中，不只要输出 `read_before`，还应在 hook 执行侧添加一个轻量检查：当 `readWhen` 条件匹配时，扫描当前 prompt 前 N 轮对话（通过 hook_input 的 session 上下文）是否提到了相关 spec。
   - 如果未提到，在 `additionalContext` 中追加显式提示行，而不是仅仅依赖 digest 中的 `read_before`。

5. **模板同步**：root ↔ template 一致性。

### 不改动

- 不改动 `registry.json` 的结构（schema 不变）。
- 不改动 `entry_classifier.py`（P0-A 已改造完成）。
- 不改动 `dispatch.md` 或 `entry.md` 的契约内容。
- 不实现完整的"N 轮对话"扫描（hook 侧用 prompt 前缀内容近似代替）。

### Non-Goals

- 不实现 hook 侧的"会话历史扫描"（受限于 hook_input 不提供完整会话历史，用当前 prompt 的前缀内容近似）。
- 不实现 registry schema 变更。
- 不实现自动"已读确认"写入（如写 ack 文件），仅做运行时检查。

## Acceptance Criteria

1. `task start` 时，若 `entry.md` 或 `dispatch.md` 未被"引用"（git diff 或 PRD 中提到路径关键词），返回阻塞 + 明确提示该读哪些 spec。
2. `task start` 时，非安全 spec（如 `backend/index.md`）未引用时只给建议不阻塞。
3. `task next` 输出中包含 `readWhen` 建议项。
4. `npm run test:template` 通过。
5. root ↔ template 一致性。

## Verification

- `rtk .\.cowork-flow\run.cmd task start <test-task>` （构造一个 PRD 中未引用 entry.md 的测试任务）
- `rtk .\.cowork-flow\run.cmd task next <test-task>`
- `rtk npm run test:template`

## 关联

- Change: `06-15-workflow-maturity-roadmap`（P1-C）
- Plan: `2026-06-15-workflow-maturity-roadmap.md` P1-C Phase
- 上游依赖：P1-B（spec 三层分层已完成）
