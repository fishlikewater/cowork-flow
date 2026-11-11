# 团队协作

[English](team.en.md) | 中文

多人、多分支、多 worktree 使用 cowork-flow 时，任务状态保存在仓库里，运行时状态保存在本地。本篇说明哪些文件该提交、切换分支后绑定为什么会失效、executor 和 assignee 各自代表什么，以及出现冲突时怎么修。

## 提交什么、忽略什么

- 提交：`.cowork-flow/tasks/`、`.cowork-flow/plans/`、`.cowork-flow/spec/` 中的项目自有目录（`backend/`、`frontend/`、`guides/`、`references/`）、`.cowork-flow/config.yaml` 与 `AGENTS.md`。
- 忽略：`.cowork-flow/.runtime/`。首次写入运行时状态时，cowork-flow 会自动创建 `.runtime/.gitignore`（内容为 `*` 与 `!.gitignore`），锁、会话绑定、操作日志与状态快照不会进入 git。
- 不要手工提交 `.runtime`；如果早期版本已经提交过，见文末清理。
- `project sync` 只更新框架管理的文件；任务、计划和项目自有 spec 默认保留。

## 分支与 worktree

- 任务和计划随分支走。切换到不包含当前任务的分支后，会话绑定仍指向原路径，但目录不存在；hook 与 CLI 会报告“任务目录不存在”，并提示切回原分支或显式重新绑定，而不是让你创建重复任务。
- 重新绑定：回到包含任务的分支后运行 `./.cowork-flow/run task next <task-dir>`；或用 `task next --list` 选一个已存在的任务。
- 每个 worktree 有独立的 `.runtime/`，会话绑定、锁与状态快照不共享；任务文件随各 worktree 的检出分支变化。
- 同一任务不要在多个 worktree 并行推进：不同检出的 `task.json` 是不同副本，运行时锁只保护单个工作区。
- 需要并行推进多个任务时，用任务看板（`task next --list --json`）和依赖（`--depends-on`）协调，合并后再统一推进。

## executor 与 assignee

- `assignee` 是人：任务创建时的 `--assignee`，用于看板归属和筛选（`task next --list --mine`）。
- `executor` 是当前持有任务的会话身份：`task next <dir> --run` 启动时写入；跨机器或跨会话续做时通过 `--adopt` 显式接管，接管会重置 review 基线并保留前任 executor 的审计字段。
- `ownerSessionActive` 只是绑定提示：`false` 不代表任务无人负责，显式目录工作或另一个工作区的会话不会出现在这里的绑定中。
- 所有权交接用 `--adopt`；`--takeover` 只在 start 时生效，不重置基线。

## 跨机器交接

1. 原执行者提交并推送任务目录（`task.json`、`decision-anchor.md`、`implement.jsonl` 等）。
2. 新执行者拉取分支后运行 `./.cowork-flow/run task next <task-dir> --run --adopt`。
3. 接手输出包含前任 executor、原基线、未完成 AC 和证据覆盖，可直接继续。

## 合并冲突与手工修复

- `task.json` 是事实文件，手工编辑是合法修复路径；合并冲突解决后，`task next --validate` 与 `doctor --all` 应无新增错误。
- 循环依赖、指向不存在任务的依赖、空 executor 等异常由 start / review 门禁失败关闭处理，不会静默通过。
- 不要手工修改 `_state`：`revision` 与 `operation_id` 是并发控制和幂等元数据。
- 合并后先跑 `./.cowork-flow/run doctor --all`，再继续推进。

## 已提交 .runtime 的清理

- `doctor --all` 会报告 `RUNTIME-GIT-HYGIENE-UNIGNORED`（运行时文件未被忽略）或 `RUNTIME-GIT-HYGIENE-TRACKED`（运行时文件已被跟踪）。
- 清理：`git rm -r --cached .cowork-flow/.runtime`，提交后由下一次状态写入自动生成 `.runtime/.gitignore`。
- 清理不会删除本地文件；锁、绑定和快照仍保留在工作区。
