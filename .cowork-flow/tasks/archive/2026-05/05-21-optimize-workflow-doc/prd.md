# 优化模板工作流文档

## Goal
优化 `template/.cowork-flow/workflow.md` 的描述与格式，在不改变当前流程逻辑的前提下尽量缩小文件体积。

## Requirements
- 保留当前 L0 / L1 / L2 分级与对应流程。
- 保留 change、task、plan、context、验证、恢复、收尾、禁止事项和完成定义等关键门禁。
- 删除重复表达，压缩长句和冗余示例。
- 不修改与本任务无关的文件。

## Acceptance Criteria
- [x] `template/.cowork-flow/workflow.md` 文件体积小于修改前。
- [x] 关键流程逻辑没有被删改为另一套流程。
- [x] Markdown 结构清晰可读。

## Technical Notes
- 任务类型：L0 / docs。
- 验证方式：对比文件大小、检查关键术语和流程段落、查看 git diff。
