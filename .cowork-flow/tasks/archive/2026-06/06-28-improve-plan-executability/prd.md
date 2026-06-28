# PRD: 提升开发计划可执行性

## 目标

增强 `writing-plans` skill 生成的 plan 文件和 `cowork-implement`/`cowork-check` agent 的上下文读取路径，使子代理能按可执行步骤执行，减少理解和执行偏差。

## 非目标

- 不创建新的文件格式（plan 仍是 markdown）
- 不修改 subagent dispatch 协议
- 不修改状态机 / gate engine
- 不强制 L0 任务使用详细步骤

## 验收标准

| ID | 描述 |
|----|------|
| AC-01 | `writing-plans` skill 的 "Task Rules" 部分增加可执行步骤格式要求（每步: Files, Action, Verify, Expected） |
| AC-02 | `cowork-implement` agent prompt 增加"读取当前任务关联的 plan 文件" |
| AC-03 | `cowork-check` agent prompt 增加"读取当前任务关联的 plan 文件" |
| AC-04 | 现有流程不被破坏 — task create/start/review/complete/archive 路径正常 |
| AC-05 | plan 模板更新为可执行步骤格式 |

## 范围

### In-Scope

- `.claude/skills/writing-plans/SKILL.md` — 步骤格式增强
- `.claude/agents/cowork-implement.md` — 增加 plan 读取
- `.claude/agents/cowork-check.md` — 增加 plan 读取
- `template/.claude/skills/writing-plans/SKILL.md` — 同步
- `template/.claude/agents/cowork-implement.md` — 同步
- `template/.claude/agents/cowork-check.md` — 同步
- 其他 host 平台的 skill/agent 镜像（`.codex/`, `.opencode/`）

### Out-of-Scope

- 不创建新脚本或工具
- 不修改 task.py / change.py
- 不修改 test suite
