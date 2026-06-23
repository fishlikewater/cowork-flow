# 清理检测报告

## 已清理

- 删除本地测试残留目录：`.tmp/`、`.tmp-tests/`。
- 清理 root/template 中 `validate_coding_standards.py` 的过期说明：该脚本已经参与生命周期门禁，不再只是提示脚本。
- 删除 root/template 中 `validate_coding_standards.py` 的冗余 `_get_modified_files()` 包装，直接使用 `collect_changed_paths()`。
- 修复 root/template 中 `validate_rules.py` 的旧 scope 说明和 CLI scope 白名单，补入真实运行时 gate 已使用的 `task_review`。
- 修复 root/template 中 `rules.schema.json` 的旧 scope enum，补入 `task_review`。
- 修复 root/template 中 `git_snapshot.py` 和 `validate_implementation.py` 的 Git 变更读取范围，避免嵌套模板项目误读外层仓库变更。
- 修复 root/template 中 `task review` 的过宽实现门禁：显式 coordinator 执行可审查主会话拥有的规格变更，默认路径仍阻断疑似子代理修改规格文件。
- 新增回归测试，确保 rules schema 和 CLI 不再遗漏 `task_review`，并确保 gate 只读取当前项目根目录下的 Git 变更。
- 新增回归测试，确保 coordinator 可完成 meta/spec 清理验收，同时保留默认路径对规格文件变更的阻断。

## 明确保留

- `.cowork-flow/tasks/archive/` 和 `.cowork-flow/changes/archive/`：历史任务和变更记录，不视为死文档。
- `.agents/`、`.claude/`、`.codex/`、`template/` 的镜像资产：多宿主分发合同需要，不视为重复文件。
- `.cowork-flow/spec/frontend/`：被默认任务上下文和固定代理合同引用，即使当前仓库没有前端实现，也不是死文档。
- `scripts/release.sh`、`scripts/run-template-tests.js`、`scripts/pack-check.js`：分别由 `package.json`、测试和打包检查引用。
- `validate_implementation.py` 的 `_get_modified_files()`：当前只读取 tracked diff，语义不同于 coding standards 的 staged/modified/untracked 快照，本次不合并，避免清理变行为改造。
