# 调整模板工作流文档可读性

## Goal
根据反馈调整 `template/.cowork-flow/workflow.md`，不要为了压缩而牺牲阅读和再次编辑体验。

## Requirements
- 保留 L0 / L1 / L2、change、task context、验证、恢复、收尾、禁止事项和完成定义等流程逻辑。
- 恢复必要的 Markdown 结构，例如子标题、代码块、短列表和表格。
- 避免上一版过度内联导致的长行和编辑困难。
- 文件仍应明显小于原始版本，但文件大小不是唯一目标。

## Acceptance Criteria
- [x] 文档比上一版更适合阅读和再次编辑。
- [x] 关键流程逻辑和命令仍可检索。
- [x] 文件体积仍小于原始 tracked 版本。

## Technical Notes
- 任务类型：L0 / docs。
- 原始 tracked 文件大小参考：`git cat-file -s HEAD~1:template/.cowork-flow/workflow.md` 或当前历史中的原版本。
- 验证方式：查看文件内容、关键术语检索、文件大小对比、`git diff --check`。
