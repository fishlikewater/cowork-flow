# 架构与扩展

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

`config.yaml`、`.developer`、规范、任务和计划按同步策略保护。`--force` 会扩大覆盖范围，因此已有项目应先用 `--dry-run` 查看变更。

## 规范挂命令

项目可以在 `.cowork-flow/spec/` 下的规范文件中声明检查命令。执行器只读取声明，不解析规范正文。

```markdown
---
checks:
  - cmd: npm run lint --silent
    files: "src/"
    timeout: 60
    when: both
---
```

可用字段：

| 字段 | 含义 |
|---|---|
| `cmd` | 要执行的命令 |
| `files` | 目录前缀或扩展名，如 `src/`、`*.ts`；多个值用逗号分隔 |
| `timeout` | 秒数，默认 30，最长 120 |
| `when` | `edit`、`lifecycle` 或 `both`，默认 `both` |

唯一执行入口是 `./.cowork-flow/run spec-check`：

| 结果 | 含义 | 是否阻断完成 |
|---|---|---|
| `pass` | 命令执行成功 | 否 |
| `violation` | 命令执行失败且有违规 | 是 |
| `unchecked` | 命令缺失、解释器缺失或超时 | 是，需显式放行 |

`when: edit` 是编辑期提示，超时上限为 2.5 秒，不代替收口检查。收口阶段会执行全部声明，并把结果写入任务记录。

模板不预置生效的项目检查命令，因为模板无法知道目标项目使用什么工具。需要检查时，在项目自己的 `spec/` 文件中声明。完整契约见 `.cowork-flow/spec/contracts/spec-checks.md`。

## 扩展规则

- 宿主特化只能放在 `spec/runtime/host-assets.json`、`scripts/adapters/`、`template/.<host>/` 或明确的宿主命令模块中。
- `scripts/services|runtime|infra` 和 `src/lib/` 的通用计划、拷贝模块不能出现宿主分支。
- 新宿主先更新 Host Asset Manifest 与 schema，再补安装器、doctor 和测试；不要在多个文件各写一份宿主清单。
- 项目差异写入 `AGENTS.md`、`config.yaml`、`spec/` 或项目自有 Skill，不恢复第二套流程文档。
- 修改 Skill 分发路径时，同时更新 `skillReadRoot`、`skillDiscovery` 和对应宿主证据。
- 修改命令名时，一次更新命令注册表、README、doctor 提示、Skill 和相关测试。

## 测试与字节码

Node 测试位于 `test/`，Python 仓库测试位于 `tests/`。`node --test` 会加载 `test/` 下全部 `.js`，辅助模块也必须无副作用；Python 侧按 pytest 或 unittest 的默认发现规则收集。

测试与技能脚本不得在 `template/`、`presets/` 下留下 `__pycache__` 或 `*.pyc`。Node 测试通过 `test/helpers/bytecode-isolation.js` 重定向缓存；技能脚本通过 `runtime_pythonpath_env(cache_bytecode=False)` 关闭字节码写入。`tests/test_no_legacy_template_paths.py` 负责守住这一边界。
