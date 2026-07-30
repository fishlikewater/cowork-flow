# cowork-flow

> 项目协作流程模板 — 把需求、计划、实现、验证串成闭环。

## 一句话

**cowork-flow 不写代码，它帮你建流程。** 把 `template/` 复制到目标项目，立刻获得任务流、规格治理、开发计划和会话记录骨架。

## 适用 / 不适用

| ✅ 适用 | ❌ 不适用 |
|---|---|
| 新项目需要 `AGENTS.md` + 任务流 + 规格文档 | 只需要 React / Spring Boot / Rust 脚手架 |
| 已有项目想补轻量协作流程 | 已有成熟任务/规格/协作系统 |
| 需要需求澄清 → 计划 → 实现 → 验证闭环 | 只想复制某一段提示词 |

## 快速开始

```bash
# 初始化到新项目
npx cowork-flow init ./my-project --platform codex --developer <your-name>

# 安装 ZCode 插件
cowork-flow install-zcode-plugin

# 同步已初始化项目
cowork-flow sync .
```

平台选项：`codex` / `opencode` / `claude-code` / `all`（逗号分隔）

## 仓库结构

```
template/
├── AGENTS.md                  # 协作入口（编码原则、流程约定）
├── CLAUDE.md                  # Claude Code 入口
├── skills/                    # ⭐ 唯一源码，init 时按平台分发
├── .codex/                    # Codex agents / hooks / config
├── .claude/                   # Claude Code settings / agents / hooks
├── .opencode/                 # OpenCode agents / commands / plugins
├── .zcode/                    # ⭐ ZCode 插件（hooks + skills + agents + scaffold instructions）
└── .cowork-flow/
    ├── config.yaml            # 项目配置
    ├── scripts/               # Python 运行时
    ├── spec/                  # 规范文档（contracts / schemas / guides）
    ├── changes/               # 行为变更管理
    ├── plans/                 # 实现计划
    ├── tasks/                 # 任务目录
    └── workspace/             # 开发者工作区
```

## 架构与扩展点

- **应用服务层**：任务创建、生命周期、归档、上下文、任务树和 runtime context 编排位于 `scripts/application/`；命令层只负责参数和输出适配。
- **状态存储层**：`scripts/common/storage/` 提供显式 UTF-8、修订检查、操作日志和可恢复 Unit of Work；任务与会话写入不再直接散落在命令函数中。
- **Host Asset Manifest**：`spec/runtime/host-assets.json` 是宿主资产、平台识别、同步策略和 obsolete 迁移清单的权威来源。新增平台或资产时更新 Manifest 与 schema，不在 CLI 中新增硬编码集合。
- **事务式 init/sync**：CLI 先构建不可变 Asset Plan，在同文件系统 staging 中校验 hash/权限，再按备份清单提交；失败时逆序回滚，`.cowork-flow/.version` 最后更新。
- **共享 Hook 核心**：Codex 与 Claude Code Hook 只做宿主输入适配，工作流状态解析由 `scripts/common/host/workflow_state_hook.py` 统一实现。
- **流程内核**：公开任务入口只有 `task next`；阶段动作由内核动作表推荐对应 Skill，硬门禁由 runtime gate 执行，不再分发独立流程中枢文件或 Skill 注册控制面。
- **Skill 自带脚本**：只服务单个 Skill 的控制器或辅助脚本放在 `template/skills/<skill-id>/scripts/`，由 `.cowork-flow/run` 薄分发；`scripts/` 内核只保留任务导航、生命周期、gate、host/runtime、存储和分发所需代码。

## Skills 分发机制

Skills 维护在 `template/skills/` 唯一源码，`init` / `sync` 时按目录分发到对应平台；`SKILL.md`、可选的 command `manifest.json` 和 `scripts/` 一起归属该 Skill：

| 平台 | 目标目录 |
|---|---|
| `codex` / `opencode` | `.agents/skills/` |
| `claude-code` | `.claude/skills/` |

分发动作：`adversarial-review`、`agent-dispatch`、`batch-execution`、`brainstorming`、`cowork-flow`、`cowork-flow-maintenance`、`decision-audit`、`failure-analysis`、`game-design`、`party-mode`、`python-runtime-design`、`runtime-health`、`spec-sync`、`task-planning`、`task-review`、`test-first`

## CLI 命令

| 命令 | 说明 |
|---|---|
| `init <path>` | 初始化项目模板 |
| `sync <path>` | 同步已初始化项目的模板和技能 |
| `install-zcode-plugin` | 安装 ZCode 插件到全局缓存 |
| `update` | 升级 CLI 本身 |

### init 选项

| 选项 | 说明 |
|---|---|
| `--platform <p>` | 平台：`codex` / `opencode` / `claude-code` / `all` |
| `--developer <n>` | 开发者名称 |
| `--force` | 覆盖已有文件 |
| `--dry-run` | 预览不写入 |

### sync 行为

- **自动识别**已安装 host 目录，只同步对应平台资产
- **Skills** 从 `template/skills/` 按平台分发
- **保护文件**：`config.yaml`、`spec/`（除 `workflow-state-templates.md`）、任务、计划、变更、workspace
- **正式版旧资产清理**：旧脚本位置、旧 adapter 资产和已废弃文件按 Host Asset Manifest 的 `obsoleteFiles` 清理；用户保护文件保持不变
- **事务恢复**：上次未完成事务会在新一轮 sync 前恢复；事务元数据缺失或损坏时 fail-closed，不在未知状态上继续写入
- `--force` 整文件覆盖保护文件

## ZCode 插件

```bash
cowork-flow install-zcode-plugin     # 安装
cowork-flow install-zcode-plugin --force  # 覆盖已安装
cowork-flow install-zcode-plugin --force --prune-old  # 覆盖并清理旧版本缓存
```

安装到 `~/.zcode/cli/plugins/cache/cowork-flow-local/cowork-flow/<version>/`。安装器会同时写入稳定 marketplace source：`~/.zcode/cli/plugins/cache/marketplaces/cowork-flow-local/marketplace.json`，以及 ZCode 当前使用的活动副本：`~/.zcode/cli/plugins/marketplaces/cowork-flow-local/marketplace.json`。`known_marketplaces.json` 指向稳定 source 目录，避免 ZCode 刷新活动副本时删除自己的 source。

安装新版本时，marketplace 中只保留一个 `cowork-flow` entry 并指向最新版本目录；旧版本缓存默认保留，避免正在运行的 ZCode session 仍引用旧插件根目录。需要清理旧版本时显式传 `--prune-old`。

ZCode 插件只安装 hook、skills、agents 和轻量说明文件；`.cowork-flow/` 流程文件仍由显式 `cowork-flow init` / `cowork-flow sync` 在项目根目录管理。插件不会通过 scaffold 创建 `.cowork-flow/`，因此不会在多模块项目的模块目录重复落盘流程文件。

**Hook 注入内容：**
- `workflow-state` — 当前任务状态
- `contract-digest` — 合同摘要（SHA256 fingerprint）
- `delegated_subtask` — 子代理运行时上下文

**插件子代理：**
- `cowork-implement` — 绑定 runtime context 后执行计划内实现
- `cowork-check` — 绑定 runtime context 后做独立检查
- `cowork-research` — 绑定 runtime context 后做只读调研

## 任务流程

```
changes → brainstorming → read spec → plan → tasks → implement → check → complete
```

`./.cowork-flow/run task next` 是唯一公开任务流程入口。它读取当前状态，输出下一步 action、激活 Skill、runtime gate、blocker，以及可执行时的 `task next --run` 命令。

| action | 入口 | status 结果 |
|---|---|---|
| `create_task` | `task next --run --title "<title>" --slug <name> --assignee <name>` | `planning` |
| `start_task` | `task next <dir> --run` | `in_progress` |
| `request_review` | `task next <dir> --run --intent review` | `review` |
| `complete_task` | `task next <dir> --run --intent review` | `completed` |
| `archive_task` | `task next <dir> --run --intent archive` | 归档副本保持 `completed` |

Batch 使用任务图和持久化 Host action：运行 `task next <parent-task> --run --intent batch --auto --approved` 获取 `next_action`；Host 完成真实生命周期动作后继续通过 `task next` 导航，不暴露独立 batch 子命令。

## 常用命令

```bash
# 身份
./.cowork-flow/run get-developer
./.cowork-flow/run init-developer <name>

# 上下文
./.cowork-flow/run get-context
./.cowork-flow/run task next
./.cowork-flow/run task next --json
./.cowork-flow/run task next --list
./.cowork-flow/run task next <dir> --validate

# 变更
./.cowork-flow/run change create <slug>
./.cowork-flow/run change validate <slug>

# 任务
./.cowork-flow/run task next --run --title "<title>" --slug <name> --assignee <name>
./.cowork-flow/run task next <dir> --run
./.cowork-flow/run task next <dir> --run --intent review
./.cowork-flow/run task next <dir> --run --intent archive

# 子代理
./.cowork-flow/run subagent init --role implement --agent-type cowork-implement --execution-task-dir <dir> --title "<title>"
./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>

# Session
./.cowork-flow/run get-context --mode record
./.cowork-flow/run add-session --title "<title>" --commit "<ref>" --summary "<summary>"
```

## Party Mode

`party-mode` 是唯一公开的 advisory roundtable 入口。它默认使用
runtime board controlled workflow：子代理通过 Board API 交流，主持人只执行
runtime 发出的 host-neutral action、记录执行结果并纠偏漂移。

> Party Mode 只产出建议，不能推进任务状态，也不能替代 `cowork-implement` / `cowork-check`。

## 发布

测试按反馈速度和覆盖范围分层：

```bash
npm run test:fast          # 快速 Node 测试，等价于 npm test
npm run test:integration   # init/sync 关键集成路径
npm run test:node:full     # 完整 Node 测试
npm run test:template      # 核心模板集成测试
npm run test:template:full # 完整模板 Python discovery
npm run test:all           # 发布前全量测试与打包检查
```

```bash
npm run release          # patch
npm run release -- minor # minor
```

**发布流程：**
1. `npm run test:all`、`git diff --check`
2. 稳定性变更使用 `COWORK_TEMPLATE_TEST_REPEAT=3` 和固定 `COWORK_TEMPLATE_TEST_SEED` 重复运行 `npm run test:template:full`
3. `npm version` 升级版本
4. 同步版本到 `template/.cowork-flow/.version` 和 `template/.zcode/.zcode-plugin/plugin.json`
5. `git commit` + `git tag`
6. `npm publish`

CI 需要 `NPM_TOKEN` secret。

Windows 上发布前使用 `run.cmd` 入口验证；POSIX shell 专属 release 用例在没有 shell 的 Windows 环境会明确跳过，不得记录为通过。

## 接入原则

- 以目标项目事实为准，不把模板内容当成项目事实
- 保留有价值的流程骨架，删除不存在的场景
- 项目差异写入 `AGENTS.md`、`config.yaml`、`spec/` 或项目自有 Skill；不要恢复第二套流程中枢文档
- 不为了替换项目命令而改写通用 skill
