# 决策锚点：root 自举正式版同步

## 目标

- 同步 root 自举文档中的正式版 decision-anchor 术语，清理误导性的 PRD 表述。
- 同步 root 运行时 `tdd_evidence.py` 与 template 副本，避免本仓库自举行为与发布模板漂移。
- 增加 root/template 漂移保护测试，覆盖关键自举文件。

## 非目标

- 不改正式 workflow 语义。
- 不删除合法的历史迁移测试、Party Mode V2 runtime board 名称或 adapter fallback 契约。
- 不扩大到大型文件拆分。

## 验收标准

- AC-001: root workflow/spec 不再残留误导性的 PRD 任务入口表述。
- AC-002: root `tdd_evidence.py` 与 template 运行时副本同步。
- AC-003: 测试覆盖 root/template 关键文件漂移。
- AC-004: 聚焦测试、复杂度门禁与 `npm run test:all` 通过。
