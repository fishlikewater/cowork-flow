# 清理 project-context 未使用入口

## 目标

在确认当前流程不会调用 `project-context` 后，删除 `project-context.md`、`project_context.py` 及其命令、文档和测试残留，让当前架构保持简洁。

## 范围

- 先扫描当前流程入口、hook、runner、模板同步、文档和测试中对 `project-context` / `project_context` / `project-context.md` 的引用。
- 仅在引用证明其不是当前自动流程依赖时，删除对应脚本、生成文件、命令映射和文档描述。
- 同步 root 与 `template/` 下的 runtime 文件。
- 更新会因删除入口而失效的测试。

## 非目标

- 不重排整个 `template/.cowork-flow/scripts/` 目录。
- 不删除 `get_context.py`、`get_developer.py`、`init_developer.py` 等尚未证明无使用的脚本。
- 不引入新的兼容层或迁移框架。

## 验收标准

- AC-001: 新安装项目不再包含 `.cowork-flow/scripts/project_context.py`，也不生成 `.cowork-flow/project-context.md`。
- AC-002: `sync` 会删除下游旧 `.cowork-flow/scripts/project_context.py` 和 `.cowork-flow/project-context.md`。
- AC-003: `project-context` 命令不再出现在 root/template runner、README、workflow 或 Python runner 映射中。
- AC-004: 有可复查的引用扫描证据，证明删除前已检查当前流程中是否使用 `project-context`。
- AC-005: 已删除 root/template 的 `project_context.py`、root 生成文件 `.cowork-flow/project-context.md` 和旧功能测试。
- AC-006: 聚焦测试覆盖初始化、同步和 runner 命令表变化。
- AC-007: `git diff --check` 通过；若全量测试存在已知环境问题，需如实说明。

## 相关文件

- `.cowork-flow/project-context.md`
- `.cowork-flow/scripts/project_context.py`
- `.cowork-flow/scripts/run.py`
- `template/.cowork-flow/scripts/project_context.py`
- `template/.cowork-flow/scripts/run.py`
- `README.md`
- `test/init.test.js`
- `test/sync.test.js`
- `tests/test_project_context.py`
- `tests/test_python_runner.py`
- `src/lib/copy-template.js`
