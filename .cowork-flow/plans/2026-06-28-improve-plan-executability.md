# 提升开发计划可执行性 Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** 增强 plan 文件可执行性使子代理能按步骤执行，减少理解和执行偏差。

**Architecture:** 纯文档流程改进 — 修改 2 个 agent prompt (cowork-implement / cowork-check) 增加 plan 文件读取，修改 1 个 skill (writing-plans) 的步骤输出格式要求。不改任何代码、协议或状态机。

**Verification:** 验证所有文件修改正确，确认 root/template 同步，运行现有测试确保无退化。

## Execution Strategy

串行执行。原因：所有变更都是文档级别，共享同一批 skill/agent 文件。可以在 writing-plans 变更为稳定版本后与其他两处 agent prompt 变更并行，但最终需要统一检查格式一致性。

## Scope

### In Scope

- writing-plans skill：步骤格式增强（每步 File/Action/Verify/Expected）
- cowork-implement agent prompt：增加计划文件读取
- cowork-check agent prompt：增加计划文件读取
- 所有 host 平台的镜像文件同步（.claude/ + template/ + .codex/ + .opencode/）
- 本 plan 文件本身作为改进后格式的示例

### Out of Scope

- 不创建新文件格式
- 不修改 subagent dispatch 运行时代码
- 不修改 task.py / change.py / 状态机
- 不新增测试

## Acceptance Mapping

| PRD AC | 验证方式 |
|--------|---------|
| AC-01 writing-plans skill 增加步骤格式要求 | 检查 SKILL.md 内容包含 Files/Action/Verify/Expected |
| AC-02 cowork-implement 读取 plan 文件 | 检查 agent prompt 包含 plan 读取指令 |
| AC-03 cowork-check 读取 plan 文件 | 检查 agent prompt 包含 plan 读取指令 |
| AC-04 现有流程不破坏 | 运行现有测试套件 |
| AC-05 模板同步 | 确认 template/ 下对应文件与 root 一致 |

---

## Task: 提升开发计划可执行性

### Step 1: 增强 writing-plans skill 的步骤输出格式

- **Files**: `.claude/skills/writing-plans/SKILL.md`, `template/.claude/skills/writing-plans/SKILL.md`
- **Action**: 在 writing-plans SKILL.md 的 "Task Rules" 部分增加可执行步骤格式要求，要求每步包含 Files、Action、Verify、Expected 四个字段
- **Verify**: `grep -c "Files:" .claude/skills/writing-plans/SKILL.md` → `>= 1`
- **Expected**: skill 文件明确要求每步包含文件列表、操作描述、验证命令、预期结果

### Step 2: cowork-implement agent 增加 plan 文件读取

- **Files**: `.claude/agents/cowork-implement.md`, `template/.claude/agents/cowork-implement.md`
- **Action**: 在 "Load context before editing" 部分增加一项：`Read the plan file from the task's linked plan path (check task.json plan field, or search .cowork-flow/plans/ for plan files referencing this task).`
- **Verify**: `grep -c "plan" .claude/agents/cowork-implement.md` → `>= 1`
- **Expected**: implement agent 在执行前会读取关联的 plan 文件

### Step 3: cowork-check agent 增加 plan 文件读取

- **Files**: `.claude/agents/cowork-check.md`, `template/.claude/agents/cowork-check.md`
- **Action**: 在 check agent 的上下文加载部分增加 plan 文件读取，用于检查执行步骤是否对应计划
- **Verify**: `grep -c "plan" .claude/agents/cowork-check.md` → `>= 1`
- **Expected**: check agent 在检查前会读取关联的 plan 文件，逐项验证

### Step 4: 同步其他 host 平台的镜像文件

- **Files**: `.codex/agents/cowork-implement.toml`, `.codex/agents/cowork-check.toml`, `.opencode/agents/cowork-implement.md`, `.opencode/agents/cowork-check.md`, 以及对应的 template/ 副本
- **Action**: 将 Step 2-3 的 plan 读取变更同步到 codex 和 opencode 的 agent 定义文件
- **Verify**: `grep -rl "plan" .codex/agents/ .opencode/agents/ template/.codex/agents/ template/.opencode/agents/ 2>/dev/null`
- **Expected**: 所有 host 平台的 agent 文件都包含 plan 读取指令

### Step 5: 更新 change.yaml 关联 task

- **Files**: `.cowork-flow/changes/06-28-improve-plan-executability/change.yaml`
- **Action**: 将 change.yaml 的 task 字段指向当前任务目录
- **Verify**: `grep "task:" .cowork-flow/changes/06-28-improve-plan-executability/change.yaml` → `task: .cowork-flow/tasks/06-28-improve-plan-executability`
- **Expected**: change 和 task 建立双向链接

### Step 6: 最终验证 — 内容一致性

- **Files**: 所有修改的文件
- **Action**: 运行 diff 确认 root 和 template 镜像文件一致
- **Verify**: `diff <(grep -v "^#" .claude/skills/writing-plans/SKILL.md | cat -s | sha256sum) <(grep -v "^#" template/.claude/skills/writing-plans/SKILL.md | cat -s | sha256sum)` → 匹配
- **Expected**: root/template 镜像完全一致

### Step 7: 最终验证 — 测试不退化

- **Files**: 现有测试套件
- **Action**: 运行现有测试确认流程不被破坏
- **Verify**: 
  - `npm test` → 全部通过
  - `npm run test:template` → 全部通过
  - `python3 -m unittest discover tests -v` → 全部通过（测试数不减少）
- **Expected**: 所有现有测试通过，无退化
