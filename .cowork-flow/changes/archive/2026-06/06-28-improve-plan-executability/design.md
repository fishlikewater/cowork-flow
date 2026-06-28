# Design: 纯文档流程改进

## 架构

不改代码，只改流程文档和 agent prompt。三个变更点：

1. `writing-plans` skill — 输出格式增强，步骤从粗颗粒变为可执行颗粒
2. `cowork-implement` agent — 增加 plan 文件读取步骤
3. `cowork-check` agent — 增加 plan 文件读取步骤

## 当前信息流

```
plan 文件（有步骤+验证）
  ↓ 子代理不读 ✗
prd.md（有目标范围）
  ↓ 子代理读 ✓
implement.jsonl（文件列表+原因）
  ↓ 子代理读 ✓
→ subagent 自己推断步骤 → 执行偏差
```

## 改进后信息流

```
plan 文件（可执行步骤+file+action+verify+expected）
  ↓ 子代理读 ✓
prd.md（目标范围+验收标准）
  ↓ 子代理读 ✓
implement.jsonl（文件列表+原因）
  ↓ 子代理读 ✓
→ subagent 按步骤执行 → 执行确定性高
```

## 可执行步骤格式

每个 plan 步骤必须包含：

```markdown
### Step N.M: <简短描述>

- **Files**: <路径列表>
- **Action**: <一句话描述做什么>
- **Verify**: `<命令>` → `<预期输出>`
- **Expected**: <验证通过后的状态描述>
```

行为变更步骤额外包含 TDD 要求：

```markdown
- **TDD**: RED → GREEN
  - redCommand: `<命令>`  
  - redExitCode: 1
  - greenCommand: `<命令>`
  - greenExitCode: 0
  - acceptanceId: AC-001
```
