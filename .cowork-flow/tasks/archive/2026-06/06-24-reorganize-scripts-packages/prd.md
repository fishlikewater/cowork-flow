# 重组 scripts 包结构

## 目标

按已确认方向重组 `.cowork-flow/scripts/`：`run.py` 留在根目录，命令脚本移入 `commands/`，共享库保留 `common/` 边界并拆成 `core/`、`task/`、`git/`、`gates/` 四包。

## 范围

- 同步调整 root 与 `template/` 的 `.cowork-flow/scripts/` 文件布局。
- 更新 `run.py` 命令映射，让现有命令继续调度到新路径。
- 更新 Python import 路径和测试引用。
- 更新 init/sync/package 相关测试，确保模板安装与打包包含新结构。

## 非目标

- 不改变任何命令的 CLI 参数、输出语义或任务状态流转。
- 不拆 `commands/` 内部子包。
- 不给旧路径保留兼容 wrapper。
- 不重构脚本内部业务逻辑。

## 验收标准

- AC-001: root/template 中命令脚本位于 `.cowork-flow/scripts/commands/`。
- AC-002: root/template 中共享库按 `common/core`、`common/task`、`common/git`、`common/gates` 分包。
- AC-003: `run.py` 能继续调度现有命令，Windows runner 仍指向根 `scripts/run.py`。
- AC-004: 活跃代码和模板不再引用旧的顶层命令脚本路径或旧 `common.<module>` 路径。
- AC-005: 聚焦测试和 `npm run test:all` 通过。

## 相关文件

- `.cowork-flow/scripts/`
- `template/.cowork-flow/scripts/`
- `test/init.test.js`
- `test/sync.test.js`
- `tests/test_python_runner.py`
- `tests/test_flow_script_paths.py`
- `tests/test_party_mode_v2.py`
- `src/lib/copy-template.js`
