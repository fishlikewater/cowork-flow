---
name: before-dev
description: MANDATORY GATE — call before ANY code change, file edit, or subagent dispatch. Checks workflow state and either allows or blocks the action.
---

# Before Dev — 编码前工作流门禁

This skill is the enforcement point for the cowork-flow workflow. You MUST invoke it
before any file edit, code change, or subagent dispatch. It reads the current
`<workflow-state>` block and decides whether to allow or block.

This skill is NOT a checklist or context loader — it is a gate. Do not proceed to
code changes without passing through this gate.

**豁免**: 只读问答、纯查询命令（`git status`、`task next`、`task current`）、
用户明确说"直接改，跳过流程"。

---

## Step 1: 读取当前 workflow 状态

从上下文中读取 `<workflow-state>` 块。关注 `Status` 和 `Source` 字段。

如果上下文中**没有** `<workflow-state>` 块，说明当前平台的 hook/plugin 未向此上下文注入状态。
此时检查用户 prompt 中是否包含 `cowork_runtime_context_id`：

- **有 `cowork_runtime_context_id`** → 你是通过 prompt transport 接收 runtime context 的子代理，但平台 hook 未注入 workflow-state。直接进入下方的 `delegated_subtask` 分支，执行 bind、加载任务、完成叶子工作。
- **无 `cowork_runtime_context_id`** → 无法判断当前上下文身份。

回复：
```
无法从上下文中确定 workflow 状态（无 <workflow-state> 块，无 runtime context ID）。
请运行 resume 恢复任务状态，或运行 task start 创建新任务。
```

这是 fail-closed 回退——只在 Codex/OpenCode hook 正常工作时永不触发。

## Step 2: 按状态执行

### Status = `no_task`

**⛔ 阻断。** 当前没有活动任务。

你必须**拒绝**执行任何代码变更、文件编辑、子代理派发。回复用户：

```
当前没有活动任务。实现、重构或行为变更必须先创建任务。

建议:
1. 新需求方向不明确 → 先 brainstorming 明确方向
2. 需求已明确 → writing-plans → task create → task start
3. 恢复已有任务 → continue

要走哪个方向？
```

只读问答可以直接回答，但不要修改任何文件。

### Status = `delegated_subtask`

你是子代理。按 bound runtime context 执行：
- 运行 `./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>` 绑定
- 加载任务目录和分配内容
- 不要执行 start/resume/task start/task archive/commit/spawn
- 完成分配的叶子工作

### Status = `planning`

**⛔ 阻断实现。** 任务在计划阶段，尚未就绪。

回复用户：

```
任务仍在计划阶段，尚未就绪进入实现。

需要先:
1. 完善 prd.md（目标、范围、验收标准）
2. 整理 implement.jsonl 和 check.jsonl
3. 运行 task next 确认准备状态
4. 运行 task start 进入实现阶段

现在继续计划工作？
```

**例外**: 如果用户明确要求做的是"计划工作"（写 prd.md、整理 jsonl），可以继续，
但只能编辑任务计划文件，不能开始实现代码。

### Status = `in_progress`

**✅ 放行。** 任务正在执行中。

加载任务上下文后继续：
1. 读取 `<task>/prd.md`
2. 读取任务关联的 plan 文件（通过 `<task>/task.json` 的 relatedFiles 查找，或搜索 `.cowork-flow/plans/` 中引用此任务的文件），按 plan 步骤执行
3. 读取 `<task>/implement.jsonl`
4. 读取相关 spec 文件
5. 行为变更任务：确认 `<task>/tdd.jsonl` red evidence 存在
6. 声明确认的假设、成功标准、涉及文件、验证命令
7. 继续实现

  7. 继续实现

**L2 任务进入实现前必须完成 doubt-review：**
- 决策记录在 `<task>/doubt-review.md`
- 每个决策有 CLAIM + ARTIFACT + CONTRACT + RECONCILE 记录
- 无记录的非平凡决策视为"未审查"——check stage 应标记为 blocker
- 参考 skills/doubt-review/SKILL.md 的 5-step cycle

主会话派发固定代理时，必须使用 runtime context dispatch 协议。

### Status = `review`

**⚠️ 任务在检查阶段。** 实现应已完成。

回复用户：

```
任务在检查阶段，实现应已完成。

建议:
1. 运行 cowork-check 验证
2. 检查通过后 task complete
3. 如果需要小修复，在 check 范围内直接修

当前需要执行检查还是修复？
```

不要开始新的实现工作，除非是小修复。

### Status = `completed`

**⛔ 阻断。** 任务已完成。

回复用户：

```
任务已完成。不要针对已完成任务派发新的实现工作。

如果发现遗漏:
1. task archive 归档旧任务
2. 创建新任务
3. 走完整流程

需要创建新任务吗？
```

### Status = `stale` 或 `unknown`

任务状态异常。回复用户：

```
任务状态异常 (<status>)。请运行 task next 和 resume 确认当前状态后再继续。
```
