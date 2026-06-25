# PRD: 流程验证问题根因修复 + 模板同步

## 目标

根因修复上一轮流程验证暴露的 3 个问题，并将 `game-design` skill 同步到模板目录。

## 验收标准

| ID | 描述 |
|----|------|
| AC-01 | `init-context` 不再覆写已有的 `implement.jsonl`/`check.jsonl`/`debug.jsonl` |
| AC-02 | `init-context` 的 `dev_type` 支持 `spec`，添加 spec 目录引用 |
| AC-03 | TDD gate 在缺失证据文件时给出包含豁免记录示例的提示 |
| AC-04 | `template/.agents/skills/game-design/SKILL.md` 存在且与 live skill 一致 |
| AC-05 | `template/.claude/skills/game-design/SKILL.md` 存在且与 live skill 一致 |

## 范围

### In-Scope

- `.cowork-flow/scripts/commands/task.py`（init-context 覆写 + dev_type 扩展）
- `.cowork-flow/scripts/common/gates/tdd_evidence.py`（错误信息改进）
- `template/.agents/skills/game-design/SKILL.md`（新文件）
- `template/.claude/skills/game-design/SKILL.md`（新文件）

### Out-of-Scope

- 不改其他 gate 或流程
- 不改验收/完成状态机
- 不改 agent 派发协议
