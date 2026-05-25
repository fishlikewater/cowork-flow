# Simplify start skill template

## Goal
精简 `template/.agent/skills/start/SKILL.md`，减少与 `template/.cowork-flow/workflow.md` 的重复，同时不改变 AI agent 的既有执行流程和门禁要求。

## Requirements
- 保留 `start` 作为会话入口技能。
- 保留仓库文件修改必须先进入 `L0` / `L1` / `L2` 分级流程的硬门禁。
- 将完整流程规范的权威来源明确指向 `.cowork-flow/workflow.md`。
- 删除或压缩与 `workflow.md` 重复的阶段说明、完成定义、技能/脚本大表。
- 补充开发者身份未初始化时的处理。
- 保留 resume / context compression 的最小恢复说明。

## Acceptance Criteria
- [x] `template/.agent/skills/start/SKILL.md` 明显短于当前版本。
- [x] 文档中不再维护第二套完整开发流程，仅保留入口和路由说明。
- [x] 明确引用 `workflow.md` 的 L0 / L1 / L2 对应流程。
- [x] 不修改 `template/.cowork-flow/workflow.md`。

## Technical Notes
- 本次任务按 L0 处理。
- 仅修改模板 skill 文档，不改变命令语义。
- `skill-creator` 的 `quick_validate.py` 已尝试运行，但本机 Python 缺少 `yaml` 模块；改用标准库静态检查 frontmatter、必需路由和行数。
