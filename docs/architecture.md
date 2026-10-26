# 架构与扩展

[English](architecture.en.md) | 中文

本文面向维护 cowork-flow 的开发者，说明项目文件如何分层、宿主差异放在哪里，以及新增能力时应遵守的边界。只想安装和使用时，看 [README](../README.md)；排查某个宿主时看 [宿主接入](hosts.md)。

## 先记住三条边界

1. `template/` 只放会写入用户项目的文件。
2. `presets/` 只放由 `cwf host add` 安装到宿主配置目录的机器级载荷。
3. 宿主差异由 `template/.cowork-flow/spec/runtime/host-assets.json` 声明，不写进通用运行时。

## 仓库职责

| 位置 | 职责 |
|---|---|
| `template/` | `project init` 和 `project sync` 的唯一分发源 |
| `presets/` | 插件、预设和机器级 hook 的载荷源 |
| `src/` | Node CLI：命令注册、安装器和文件同步计划 |
| `scripts/` | 构建、测试、打包和发布脚本 |
| `test/` | Node 测试及辅助模块 |
| `tests/` | Python 仓库测试与 fixtures |
| `docs/` | 用户、宿主、架构和维护文档 |
| `.agents/`、`.claude/`、`.codex/`、`.cowork-flow/` | 当前源码仓库的运行副本，不作为分发源 |

### 项目分发源

`template/` 中与用户项目直接相关的内容包括：

- `AGENTS.md`：项目协作入口。
- `template/skills/`：项目技能的唯一源码，由 `init` / `sync` 按宿主分发。
- `template/.cowork-flow/`：项目配置、Python 运行时、规范、计划和任务。
- `template/.<host>/`：需要随项目落盘的宿主配置、hook 或 agents。

`cwf project init` / `cwf project sync` 不应从源码仓库的运行副本读取内容。

### 机器级载荷

`presets/` 保存不属于单个项目的宿主组件：

- Codex、Claude Code、OpenCode、ZCode、Qoder、Kimi Code 插件。
- DeepSeek Harness 预设与 hook。
- 插件品牌资产和引导技能。

机器级安装器只能通过 `cwf host add` / `cwf host remove` 写入宿主配置目录，不应把用户主目录路径硬编码到 `template/`。

机器级安装态的读取同样只有一条路径：各安装器导出 `inspectInstalledState` 描述自己写下的布局，`cwf host inspect` 把它归一化为 `schemaVersion: 1` 的只读行，`doctor` 只消费这份事实。Python 运行时不解析宿主注册表、TOML、设置文件或载荷清单；读取不可用时 doctor 报 `HOST-INSPECT-UNAVAILABLE`，不会把“读不到”误判为“未安装”。契约见 `spec/contracts/host-install-inspection.md`。

## 运行时分层

运行时代码位于 `template/.cowork-flow/scripts/`。仓库根的 `scripts/` 只负责构建和发布。

| 层 | 位置 | 负责什么 |
|---|---|---|
| 命令适配 | `scripts/adapters/cli/` | 参数解析、命令输出和 CLI 返回码 |
| 任务服务 | `scripts/services/` | 任务创建、生命周期、归档、上下文和任务树 |
| 状态存储 | `scripts/infra/storage/` | UTF-8 读写、修订检查、操作日志和可恢复事务 |
| 宿主适配 | `scripts/adapters/host/` | 宿主输入、策略差异和状态注入 |
| Hook 共享核心 | `scripts/adapters/host/workflow_state_hook.py` | 各宿主共用的工作流状态解析 |
| 宿主声明 | `spec/runtime/host-assets.json` | 平台、资产、同步策略、技能根和迁移清单 |

流程内核保持窄职责：kernel 只解析状态事实和 action，Skill 所有权由 manifest loader 注入，硬门禁由 runtime gate 执行。仓库不再维护第二套流程中枢或独立的 Skill 注册控制面。

单个 Skill 需要的脚本放在 `template/skills/<skill-id>/scripts/`，不进入运行时内核。

## init 与 sync

安装器和同步器不直接边读边写，而是按以下顺序执行：

1. 读取 Host Asset Manifest 和同步策略。
2. 构建不可变 Asset Plan。
3. 在同一文件系统 staging，并校验文件 hash 与权限。
4. 按备份清单提交；失败时逆序回滚。
5. 最后更新 `.cowork-flow/.version`。

`config.yaml`、`.developer`、规范、任务和计划按同步策略保护。`--force` 会扩大覆盖范围，但 `.cowork-flow/config.yaml` 是 `forceProtectedFiles`：首次创建后 `init --force` 和 `sync --force` 都不再覆盖它。已有项目应先用 `--dry-run` 查看变更。

安装语言写在 `config.yaml` 的 `language`（`zh-CN` 默认，或 `en-US`）。Host Asset Manifest 的 `localization` 声明哪些资产存在语言变体，源文件位于 `template/locales/<language>/<canonical-path>`；`init`、`sync` 与 `dev refresh` 通过 `localizedSource()` 选择源文件，目标路径始终是 canonical path，`locales/` 被 `excludedPrefixes` 排除，不会进入项目。当前只有 `spec/contracts/decision-anchor.md` 与 `.cowork-flow/templates/plan-template.md` 本地化；前者决定新 anchor 的标题语言，后者决定计划产物语言，解析器始终同时接受中英两套标题。strict 非 Tiny 任务的 start 门禁另外要求计划与 anchor 使用配置语言的模板形状，并要求 `规范核对：` 行填写实际 `pass` / `not_applicable` 结果；模板占位符会被阻断，Tiny 与 legacy 任务不受影响。

`.cowork-flow/spec/` 按归属拆分同步策略。框架维护的 `spec/contracts/`、`spec/runtime/`、`spec/schemas/` 与 `spec/index.md` 随 `sync` 更新：契约勘误、`contract-registry.json`、`host-assets.json`、`scope-rules.json` 和 schema 因此能与脚本同代际到达已装项目，`obsoleteFiles` 中登记的过期框架 spec 文件也会被删除。项目维护的 `spec/backend/`、`spec/frontend/`、`spec/guides/`、`spec/references/` 保持保护，普通 `sync` 不会覆盖或删除其中的文件。代价是本地修改过框架契约或 `scope-rules.json` 的项目会在下一次 `sync` 丢掉这些改动；需要保留的定制应写入四个项目目录、`AGENTS.md`、`config.yaml` 或项目自有 Skill。

## 扩展规则

- 宿主特化只能放在 `spec/runtime/host-assets.json`、`scripts/adapters/`、`template/.<host>/` 或明确的宿主命令模块中。
- 插件只提供宿主确实支持的字段，不复制未知或无效键。
- 项目技能只由 `template/skills/` 分发；机器级载荷不复制同名项目技能。
- `scripts/services|runtime|infra` 和 `src/lib/` 的通用计划、拷贝模块不能出现宿主分支。
- 新宿主先更新 Host Asset Manifest 与 schema，再补安装器、doctor 和测试；不要在多个文件各写一份宿主清单。
- 项目差异写入 `AGENTS.md`、`config.yaml`、`spec/backend|frontend|guides|references` 或项目自有 Skill，不恢复第二套流程文档。
- 修改 Skill 分发路径时，同时更新 `skillReadRoot`、`skillDiscovery` 和对应宿主证据。
- 修改命令名时，一次更新命令注册表、README、doctor 提示、Skill 和相关测试。

## 测试与字节码

测试与技能脚本不得在 `template/`、`presets/` 下留下 `__pycache__` 或 `*.pyc`。Node 测试通过 `test/helpers/bytecode-isolation.js` 重定向缓存；技能脚本通过 `runtime_pythonpath_env(cache_bytecode=False)` 关闭字节码写入。`tests/test_no_legacy_template_paths.py` 负责守住这一边界。

`node --test` 会加载 `test/` 下全部 `.js`，辅助模块也必须无副作用；Python 侧按 pytest 或 unittest 的默认发现规则收集。
