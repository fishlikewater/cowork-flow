# 清理冗余死代码和文档 PRD

## 目标

检测当前项目中的活跃脚本、代码和文档，删除确认无引用、无运行入口、无打包价值或已被新实现取代的冗余内容。

## 非目标

- 不删除 `.cowork-flow/tasks/archive/` 和 `.cowork-flow/changes/archive/` 中的历史记录。
- 不删除 root/template/.claude/.agents/.codex 之间为了多宿主分发而保留的镜像文件。
- 不做大规模架构重写。
- 不改变用户可观察的 CLI、workflow、模板安装或测试行为。

## 关键假设

- “死代码/死文档”必须有静态引用、打包路径、测试覆盖或运行入口证据支撑，不能只凭文件看起来少用就删除。
- 如果某个文件是模板、宿主资产、规格索引或历史记录的一部分，即使直接引用较少，也不视为死文件。
- 清理优先删除明显临时、过时、重复、无法被任何入口使用的活跃文件或代码分支。

## 范围

### In Scope

- 活跃 `.cowork-flow/scripts/`、`src/`、`scripts/`、`test/`、`tests/` 中确认无用的脚本或代码。
- 活跃 `.agents/`、`.claude/`、`.codex/`、`.cowork-flow/spec/`、`template/` 中确认无效或重复的文档。
- 对应的 root/template 镜像同步。
- 删除后保持测试、模板和打包路径通过。

### Out of Scope

- 历史 archive 内容。
- 仅因命名包含 legacy/deprecated 而仍被兼容测试覆盖的代码。
- 发布版本号、CHANGELOG 或 npm metadata 更新。

## 验收标准

- AC-001: 输出清理候选检查结论，说明删除与保留的依据。
- AC-002: 删除的文件或代码必须是无入口、无引用或已被现有实现替代的活跃内容。
- AC-003: 删除后 root/template 仍保持一致。
- AC-004: 删除后关键验证通过，至少包括 Python 单测、Node 单测、模板测试、打包检查和 `git diff --check`。

## 相关文件

- `AGENTS.md`
- `.cowork-flow/workflow.md`
- `.cowork-flow/spec/backend/index.md`
- `.cowork-flow/spec/guides/index.md`
- `.cowork-flow/scripts/`
- `template/.cowork-flow/scripts/`
- `src/`
- `scripts/`
- `test/`
- `tests/`

## 验证方式

```powershell
python -m unittest discover tests -v
npm test
npm run test:template
npm run pack:check
git diff --check
```
