# cowork-flow

> 多主机 Agent 协作的运行时上下文与协作事实层 — 让任何主机上的任何 agent，在任何会话、任何时刻，从同一份权威事实起步。

## 一句话

**cowork-flow 不写代码，它给 agent 喂状态。** 把 `template/` 复制到目标项目，立刻获得运行时状态注入、任务生命周期、决策记录、规格契约与跨宿主的协作事实一致性。

## 当前能力

| 领域 | 当前能力 |
|---|---|
| 任务流程 | `task next --json` 给出下一步 action，`task next --run` 只执行当前 action。 |
| 事实接入 | `run state [task] --json` 事实视图；`run mcp-state` 无依赖 MCP 只读服务（`task_state` / `task_list` / `task_scope` / `task_specs`）供任何 MCP 客户端查询；`task scope` / `task specs` 为 CLI 同源事实命令。 |
| 规范挂命令 | spec 首部 frontmatter 声明 `checks:` 命令，按编辑期/收口期执行；`run spec-check` 输出三态门禁（pass / violation / unchecked）。 |
| 运行健康 | `doctor` 诊断 runtime、host assets、Skill replica 和任务 hygiene，不推进生命周期。 |
| Host 分发 | Host Asset Manifest 驱动 Codex / OpenCode / Claude Code / ZCode / Kimi Code / DeepSeek Harness 资产和 obsolete 清理。 |
| 批处理与讨论 | Batch 发布 Host action；Party Mode 只输出 advisory final facts。 |
| 发布准备 | `release:check`、`CHANGELOG.md`、`pack:check` 固定发布前证据。 |

## 阅读导航

| 想做什么 | 建议先看 |
|---|---|
| 快速安装或同步 | [快速开始](#快速开始)、[CLI 命令](#cli-命令) |
| 理解任务如何流转 | [任务流程](#任务流程) |
| 处理故障或漂移 | [支持与故障诊断](#支持与故障诊断) |
| 做发布前检查 | [发布](#发布)、[`CHANGELOG.md`](CHANGELOG.md) |
| 了解项目演进与版本内容 | [`CHANGELOG.md`](CHANGELOG.md) |
| 接入到自己项目 | [接入原则](#接入原则) |

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

# 预览同步计划（不写文件）
cowork-flow sync ./my-project --dry-run

# 同步已初始化项目
cowork-flow sync ./my-project

# 维护者：预览本仓库 source checkout live runtime / Skill replica 刷新
npm run source:refresh:dry-run

# 维护者：刷新 ignored root .cowork-flow、.agents/skills、.claude/skills
npm run source:refresh

# 预览 CLI 更新（不安装）
cowork-flow update --dry-run

# 安装 ZCode 插件（可选）
cowork-flow install-zcode-plugin

# 安装 DSH 预设（可选，整套 agent）
cowork-flow install-dsh-preset

# 机器级安装实时 workflow-state 注入（推荐：不换预设，任意 DSH 会话生效）
cowork-flow install-dsh-hook

# MCP 客户端接入（可选）：全局注册一次，任意项目查询任务事实；
# 项目级 opt-in（如 claude-code 的 .mcp.json）与注册健康检测见
# `run doctor`；各客户端配置样例见下方「MCP 客户端接入」一节
cowork-flow mcp-state

# 维护者发布前检查
npm run release:check
```

平台选项：`codex` / `opencode` / `claude-code` / `dsh` / `zcode` / `kimi-code` / `qoder` / `all`（逗号分隔）

## 仓库结构

```
template/
├── AGENTS.md                  # 协作入口（编码原则、流程约定）
├── CLAUDE.md                  # Claude Code 入口
├── skills/                    # ⭐ 唯一源码，init 时按平台分发
├── .codex/                    # Codex agents / hooks / config
├── .claude/                   # Claude Code settings / agents / hooks
├── .opencode/                 # OpenCode agents / commands / plugins
├── .dsh/                      # DeepSeek Harness 标记（sync 检测 + 说明）
├── .kimi-code/                # Kimi Code fixed agents（cowork-implement / check / research）
└── .cowork-flow/
    ├── config.yaml            # 项目配置
    ├── scripts/               # Python 运行时
    ├── spec/                  # 规范文档（contracts / schemas / guides）
    ├── plans/                 # 实现计划
    └── tasks/                 # 任务目录

presets/                       # ⭐ 机器级插件载荷：安装器拷进宿主配置目录，不落项目
├── zcode/                     # ZCode 插件（hooks + agents + .zcode-plugin/plugin.json）
├── qoder/                     # Qoder 插件（hooks + agents + .qoder-plugin/plugin.json）
├── kimi-code/                 # Kimi Code hook shim
└── dsh/                       # DSH agent 预设
```

仓库自身的目录（不参与分发）：

```
src/                           # 分发层（Node CLI）：commands/ 子命令 + lib/ 计划与模板拷贝
scripts/                       # 构建与发布：pack-check、release、模板测试运行器
test/                          # Node 测试（node --test 收集本目录所有 .js），*.test.js 为主
tests/                         # Python 测试（pytest / unittest），test_*.py + fixtures/
.agents/ .claude/ .codex/ .cowork-flow/   # 源 checkout 的活实例（gitignored，由 npm run source:refresh 维护）
```

测试按语言分目录：`test/` 归 Node，`tests/` 归 Python。`node --test` 会收集 `test/` 下**所有** `.js`（不限 `*.test.js`，`test/helpers/` 里的辅助模块同样会被加载）；Python 侧按各自默认模式收集——pytest 收 `test_*.py` / `*_test.py`，unittest `discover` 收 `test*.py`。放在这些目录里的辅助文件必须保持无副作用。

字节码隔离：`tests/__init__.py`（pytest 与 unittest 都会先导入的包）把 Python 字节码前缀指到 gitignored 的 `.tmp/pycache`——本进程设 `sys.pycache_prefix`，并通过 `PYTHONPYCACHEPREFIX` 传给子进程；Node 测试由 `test/helpers/bytecode-isolation.js` 做同一件事。技能脚本的子进程走另一条规则：`runtime_pythonpath_env(cache_bytecode=False)` 关掉字节码写入，`run.py` 与批处理入口（`batch_mode.py`）共用这一条——技能脚本低频、缓存收益可忽略，而它留下的 `__pycache__` 会落在脚本解析到的 runtime（源 checkout 里就是交付树）。`tests/test_no_legacy_template_paths.py` 有门禁断言钉住 `template/`、`presets/` 的零字节码状态。

## 架构与扩展点

- **服务层**：任务创建、生命周期、归档、上下文、任务树和 runtime context 编排位于 `scripts/services/`；命令层只负责参数和输出适配。
- **状态存储层**：`scripts/infra/storage/` 提供显式 UTF-8、修订检查、操作日志和可恢复 Unit of Work；任务与会话写入不再直接散落在命令函数中。
- **Host Asset Manifest**：`spec/runtime/host-assets.json` 是宿主资产、平台识别、同步策略和 obsolete 迁移清单的权威来源。新增平台或资产时更新 Manifest 与 schema，不在 CLI 中新增硬编码集合。
- **事务式 init/sync**：CLI 先构建不可变 Asset Plan，在同文件系统 staging 中校验 hash/权限，再按备份清单提交；失败时逆序回滚，`.cowork-flow/.version` 最后更新。
- **共享 Hook 核心**：Codex 与 Claude Code Hook 只做宿主输入适配，工作流状态解析由 `scripts/adapters/host/workflow_state_hook.py` 统一实现。
- **流程内核**：公开任务入口只有 `task next`；kernel 只解析状态事实和 action，Skill 所有权由 manifest loader 注入，硬门禁由 runtime gate 执行，不再分发独立流程中枢文件或 Skill 注册控制面。
- **Skill 自带脚本**：只服务单个 Skill 的控制器或辅助脚本放在 `template/skills/<skill-id>/scripts/`，由 `.cowork-flow/run` 薄分发；`scripts/` 内核只保留任务导航、生命周期、gate、host/runtime、存储和分发所需代码。

## Skills 分发机制

Skills 维护在 `template/skills/` 唯一源码，`init` / `sync` 时按目录分发到对应平台；`SKILL.md`、可选的 command `manifest.json` 和 `scripts/` 一起归属该 Skill：

| 平台 | 读取根 / 目标目录 | 宿主原生发现 |
|---|---|---|
| `codex` / `opencode` / `dsh` / `kimi-code` | `.agents/skills/` | 声明为 `.agents/skills/`（assumed，未逐一本机验证） |
| `claude-code` | `.claude/skills/` | 声明为 `.claude/skills/`（assumed） |
| `qoder` | `.agents/skills/` | `.agents/skills/`（verified：SDK 默认开启；受信任目录 + 重启门禁） |
| `zcode` | `.agents/skills/` | `.agents/skills/` 与 `.zcode/skills/`（verified：宿主 bundle 的 `SkillService.list` 枚举 `<workspace>/.zcode/skills`、`<workspace>/.agents/skills`，含祖先目录向上探测，同名时 `.zcode/skills` 优先；我们只交付共享的 `.agents/skills/`） |

每个平台在 `host-assets.json` 里用两格声明这件事：`skillReadRoot`（我们运行时渲染与 fixed subagent 读取的仓库内路径）与 `skillDiscovery[]`（宿主自己发现该路径的通道，带 `scope` / `gates` / `evidence`）。读取与发现同址时项目里只有一份副本，且机器级载荷（插件、preset）一律不再携带技能副本；`evidence` 以 `verified:` / `assumed:` 前缀区分"本机验证过"与"沿用约定未验证"，后者由门禁测试逐项登记——声明写错会在 CI 变红，而不是静默生效。`./.cowork-flow/run doctor` 按同一份声明检查交付偏差：`SKILL-READROOT-MISSING`（声明的读取根不在项目里）、`PLUGIN-SKILLS-LEGACY`（插件载荷仍带旧技能副本，重装即清理）、`SKILL-DISCOVERY-GATED`（发现通道有宿主侧门禁，如信任目录 / 重启），三项均为 warning，不计入 errors。

分发动作：`adversarial-review`、`agent-dispatch`、`batch-execution`、`brainstorming`、`cowork-flow`、`cowork-flow-maintenance`、`decision-audit`、`failure-analysis`、`game-design`、`party-mode`、`python-runtime-design`、`runtime-health`、`spec-sync`、`task-planning`、`task-review`、`test-first`

## CLI 命令

| 命令 | 说明 |
|---|---|
| `init <path>` | 初始化项目模板 |
| `sync <path> [--dry-run]` | 同步已初始化项目的模板和技能 |
| `source-refresh [path] [--dry-run]` | 维护者刷新 source checkout 的 ignored live runtime 与 Host Skill replica |
| `install-zcode-plugin` | 安装 ZCode 插件到全局缓存 |
| `install-qoder-plugin [--dry-run] [--force] [--uninstall]` | 机器级安装 cowork-flow Qoder 插件到 `~/.qoder/plugins/cache/`，注册 `installed_plugins_v2.json` 并置 `enabledPlugins` 开关 |
| `install-dsh-preset` | 安装 DSH agent 预设到 `~/.dsh/.agent-presets/cowork-flow/`（整套 agent，可选） |
| `install-dsh-hook` | 机器级注册 workflow-state hook 组合行到 `$DSH_HOME/cordis.patch.yml`（当前 DSH 的 agent 提示不收集 host 层 section，实时注入请用预设方式） |
| `install-kimi-hook [--dry-run] [--force] [--uninstall]` | 机器级注册 UserPromptSubmit hook 到 `$KIMI_CODE_HOME/config.toml`（默认 `~/.kimi-code/`），向每个 Kimi Code 会话实时注入工作流上下文 |
| `update [--dry-run]` | 升级 CLI 本身 |
| `mcp-state` | 全局 MCP 事实入口：从 cwd 向上定位项目运行时并透传 `run mcp-state`（全局注册一次，所有 cowork-flow 项目通用） |

### init 选项

| 选项 | 说明 |
|---|---|
| `--platform <p>` | 平台：`codex` / `opencode` / `claude-code` / `dsh` / `zcode` / `kimi-code` / `qoder` / `all` |
| `--developer <n>` | 开发者名称 |
| `--force` | 覆盖已有文件 |
| `--dry-run` | 预览不写入 |

### sync 行为

- **自动识别**已安装 host 目录，只同步对应平台资产
- **Skills** 从 `template/skills/` 按平台分发
- **保护文件**：`config.yaml`、`.developer`、`spec/`（例外：`spec/contracts/workflow-state-templates.md` 与 `spec/contracts/spec-checks.md` 两个契约文件）、任务、计划
- **正式版旧资产清理**：旧脚本位置、旧 adapter 资产和已废弃文件按 Host Asset Manifest 的 `obsoleteFiles` 清理；用户保护文件保持不变
- **事务恢复**：上次未完成事务会在新一轮 sync 前恢复；事务元数据缺失或损坏时 fail-closed，不在未知状态上继续写入
- **Dry-run readiness**：`sync --dry-run` 只构建计划并输出 `readiness=<json>`，不写文件或事务状态；字段包含 `wouldCopy`、`wouldSkipProtected`、`wouldRemoveObsolete`、`hostAssetRefresh`、`pendingRecovery`、`warnings`
- `--force` 整文件覆盖保护文件

### source-refresh 行为

- **用途**：仅面向 cowork-flow 源码 checkout 维护者；以 `template/.cowork-flow/` 和 `template/skills/` 为唯一 tracked 分发源，刷新 ignored 的根 `.cowork-flow/`、`.agents/skills/`、`.claude/skills/` 受管副本
- **保护边界**：不覆盖 `.cowork-flow/tasks/`、`.cowork-flow/plans/`、`.cowork-flow/.runtime/`、`.cowork-flow/.developer`、`.cowork-flow/config.yaml` 和自定义 Skill
- **事务语义**：复用 Asset Plan / plan applier，失败时回滚；`.cowork-flow/.version` 保持 version-last，并复制 template 版本文件的原始内容
- **常用命令**：`npm run source:refresh:dry-run` 只预览；`npm run source:refresh` 应用后再运行 `./.cowork-flow/run doctor --all --json`

### update 行为

- 默认查询 npm latest，发现新版本时执行 `npm install -g cowork-flow@latest`
- `--dry-run` 只输出当前版本、最新版本和 `readiness=<json>`，其中 `update.wouldInstall` 表示是否会执行全局安装，不调用安装命令

## MCP 客户端接入

事实层以只读 MCP 服务（工具 `task_state` / `task_list`）提供给任意客户端。两种入口：

- **全局（推荐）**：`cowork-flow mcp-state`（npm 全局 CLI 透传）。注册一次，所有 cowork-flow 项目通用——项目根由客户端启动时的 cwd 向上解析。
- **项目级**：`<project>/.cowork-flow/run mcp-state`（不依赖全局安装，每项目一份配置）。

stdio 注册样例：

```toml
# Codex（~/.codex/config.toml）
[mcp_servers.cowork-flow]
command = "cowork-flow"
args = ["mcp-state"]
```

```json
// OpenCode（~/.config/opencode/opencode.json）
{"mcp": {"cowork-flow": {"type": "local", "command": ["cowork-flow", "mcp-state"], "enabled": true}}}
```

- **Claude Code**：`claude mcp add -s user cowork-flow -- cowork-flow mcp-state`（项目级 `.mcp.json` 写同构条目）。
- **ZCode**：客户端设置的 MCP 服务器中添加同构 stdio 条目（命令 `cowork-flow`、参数 `mcp-state`）。

项目级注册的健康检查由 `./.cowork-flow/run doctor` 报告。

## ZCode 插件

```bash
cowork-flow install-zcode-plugin     # 安装
cowork-flow install-zcode-plugin --force  # 覆盖已安装
cowork-flow install-zcode-plugin --force --prune-old  # 覆盖并清理旧版本缓存
```

安装到 `~/.zcode/cli/plugins/cache/cowork-flow-local/cowork-flow/<version>/`。安装器会同时写入稳定 marketplace source：`~/.zcode/cli/plugins/cache/marketplaces/cowork-flow-local/marketplace.json`，以及 ZCode 当前使用的活动副本：`~/.zcode/cli/plugins/marketplaces/cowork-flow-local/marketplace.json`。`known_marketplaces.json` 指向稳定 source 目录，避免 ZCode 刷新活动副本时删除自己的 source。

安装新版本时，marketplace 中只保留一个 `cowork-flow` entry 并指向最新版本目录；旧版本缓存默认保留，避免正在运行的 ZCode session 仍引用旧插件根目录。需要清理旧版本时显式传 `--prune-old`。

ZCode 插件只安装 hook、agents 和轻量说明文件；`.cowork-flow/` 流程文件仍由显式 `cowork-flow init` / `cowork-flow sync` 在项目根目录管理。插件不会通过 scaffold 创建 `.cowork-flow/`，因此不会在多模块项目的模块目录重复落盘流程文件。

**技能只走项目通道**：`init` / `sync` 写到 `.agents/skills/`，这正是 ZCode 自己枚举的路径之一（另一条是 `.zcode/skills/`，同名优先，我们不交付），fixed subagent 也从同一路径读取。插件载荷不再携带 `skills/`：ZCode 同时枚举项目根与插件根且不按技能名去重，载荷里再放一份会让同名技能以两份身份进入技能列表、并在激活时双份注入正文。

旧版本插件载荷残留的 `skills/` 副本由 `./.cowork-flow/run doctor` 以 `PLUGIN-SKILLS-LEGACY` 报出（warning，不进 errors），提示用 `--force` 重装清理。

**Hook 注入内容：**
- `workflow-state` — 当前任务状态
- `contract-digest` — 合同摘要：SessionStart 注入完整块，后续消息仅重复 SHA256 fingerprint
- `delegated_subtask` — 子代理运行时上下文

**插件子代理：**
- `cowork-implement` — 绑定 runtime context 后执行计划内实现
- `cowork-check` — 绑定 runtime context 后做独立检查
- `cowork-research` — 绑定 runtime context 后做只读调研

## DSH 接入

```bash
cowork-flow init ./my-project --platform dsh   # 项目资产：AGENTS.md + .agents/skills/ + .dsh 标记
cowork-flow install-dsh-hook                   # 机器级：注册 hook 组合行（实时注入见下方说明）
```

`install-dsh-hook` 把 `workflow-state.js` 插件作为 `insert:` patch 注册到 `$DSH_HOME/cordis.patch.yml`（未设置 `DSH_HOME` 时默认 `~/.dsh`），组合层面可被 `dsh --dump-config` 验证。经实测（DSH 0.1.1-rc.1），**agent 提示组装不收集 host 层 section**：该组合行不会在会话系统提示中产生 `<workflow-state>` 块。当前 DSH 版本下实时注入仍需预设方式（`install-dsh-preset`）；本命令保留为组合层面的幂等注册能力（卸载见下），待 DSH 支持 agent-scope patch / workspace 级组合后可直接生效。

在未安装 cowork-flow 的项目里 hook 完全无感：JS 侧根目录预检直接短路——不注入内容、不启动 Python 进程。全局开关（环境变量）：`COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`。卸载：`cowork-flow install-dsh-hook --uninstall`（`--force` 同时删除插件文件）。

> 安装或更新后需要**重启 DSH**（`cordis.patch.yml` 在启动时组合，新增/变更不会被热加载）。

> 使用预设（`install-dsh-preset`）时无需再运行 `install-dsh-hook`——预设已内置同一 hook。

## DSH 预设

```bash
cowork-flow install-dsh-preset            # 安装
cowork-flow install-dsh-preset --force    # 覆盖已安装
cowork-flow install-dsh-preset --dry-run  # 预览不写入
```

安装到 `~/.dsh/.agent-presets/cowork-flow/`（`DSH_HOME` 存在时以其为准）：`agent.cordis.yml` + `preset.yml` + `plugins/`。安装后在 DeepSeek Harness 中新建会话并选择 **Cowork Flow** 预设即可使用：persona 携带流程门禁规则，技能由项目级 `.agents/skills/` 提供（`skill-filesystem` 的工作区根，rank 200），预设不再携带技能副本。

预设是**一次性安装的机器级资产**：它不随 `sync` 或 npm 更新。升级 cowork-flow 后需要重跑 `cowork-flow install-dsh-preset --force` 才会刷新（不带 `--force` 的重复执行是空操作，安装器会在版本不同时给出提示）。安装时会在预设目录写入 `.cowork-flow-preset.json` 版本标记；`./.cowork-flow/run doctor` 比对标记与项目 runtime 版本，过期或缺失时输出 warning 与更新命令。

预设组合是部署 `standard` 预设的拷贝 + 最小改动（persona 流程规则；`skill-filesystem` 组件保持默认根，从工作区 `.agents/skills/` 发现技能）；`cowork-flow init --platform dsh` 仍负责项目级资产（`AGENTS.md`、`.agents/skills/`、`.dsh/` 标记）。

预设内置 **workflow-state hook**（`plugins/workflow-state.js`）：DSH 原生等效于 Codex/Claude hook，向系统提示末尾注入与其它宿主同构的 `<workflow-state>` 块，每条用户消息刷新一次，并在生命周期命令（`task`/`subagent`/`resume`）执行完成后立即轮内刷新（替换语义，不累积）。项目无 `.cowork-flow` 根、缺少 Python 或设 `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1` 时静默降级，由 AGENTS.md 门禁的运行导航器兜底。

## Kimi Code hook

```bash
cowork-flow install-kimi-hook             # 安装（无条件覆盖）；--force 与不带旗标同义
cowork-flow install-kimi-hook --dry-run   # 预览将写入的托管块，不写文件
cowork-flow install-kimi-hook --uninstall # 卸载托管块、shim 与版本标记
```

安装写入用户级 Kimi Code home（`KIMI_CODE_HOME`，未设置时默认 `~/.kimi-code/`）：hook 脚本 `hooks/cowork-flow-inject.mjs`、版本标记 `hooks/.cowork-flow-kimi-hook.json`，并在 `config.toml` 追加一段由注释标记包裹的托管块——一条 `[[hooks]]`，`event = "UserPromptSubmit"`、`command`、`timeout = 30`，不写 `matcher`（即匹配每条提交的提示）。配置文件按文本编辑、不做 TOML 重排，托管块以外的用户内容原样保留；卸载只移除这段托管块和上面两个文件，`config.toml` 因此变空时一并删除。

Kimi Code 只注册 `UserPromptSubmit` 一个事件：`SessionStart` / `PostToolUse` 等观察型事件的 stdout 会被宿主丢弃，无法注入内容。hook 的 stdout 就是注入正文，宿主把它追加进提示上下文；shim 在项目根目录预检失败（非 cowork-flow 项目）时直接短路，不启动 Python 进程，全局开关为 `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`。

> 安装或更新后需要**重启 Kimi Code 会话**（或重新加载配置）才会加载 hook。

Kimi Code 的 Bash 工具不导出会话标识环境变量，CLI 侧身份只能取自注入头里的 `session="kimi_<id>"`，需要显式传 `COWORK_FLOW_CONTEXT_ID`（或 `COWORK_FLOW_HOST=kimi-code`）。`./.cowork-flow/run doctor` 把该 hook 的注册情况作为 warning 级项报告（`HOOK-NOT-INSTALLED` / `HOOK-SHIM-MISSING` / `HOOK-UNKNOWN-VERSION` / `HOOK-STALE`），不计入 errors。

## Qoder（插件形态）

Qoder 的宿主集成面（hooks、三个 fixed subagent、命令面说明）打包成一个 Qoder 插件；`init` / `sync` 只写 `.cowork-flow/adapters/qoder/adapter.yaml` 这一份声明，不生成 `.qoder/` 目录（`.qoder/` 在 `excludedPrefixes` 里）。

**技能只走项目通道**：`init` / `sync` 把技能写到 `.agents/skills/`，这正是 Qoder 自己扫描的路径（`loadFromAgentsDirectory` 默认开启），因此模型能原生发现并调用，fixed subagent 也从同一路径读取——项目里只有一份副本，随 `.cowork-flow/.version` 钉版本。前提是**工作区已信任**且技能设置生效需**重启**；插件载荷不再携带 `skills/`，未 `init` 或未受信任的项目因此看不到 cowork-flow 技能。

```bash
cowork-flow install-qoder-plugin              # 安装并启用（已存在时不覆盖）
cowork-flow install-qoder-plugin --dry-run    # 预览将写入的载荷、注册表条目与开关
cowork-flow install-qoder-plugin --force      # 覆盖重装（重写插件缓存内容）
cowork-flow install-qoder-plugin --uninstall  # 卸载：只回收 cowork-flow 自己的条目与缓存目录
```

两个频次边界，缺一不可：

- **插件每机一次**：换机器或升级 cowork-flow 后要重装。
- **`init` 每项目一次**：未 `init` 的项目里装了插件也不会注入——hook 入口按载荷 `cwd` 向上找不到 `.cowork-flow` 时直接 exit 0（静默）。同事克隆仓库后需要各自执行一次 `install-qoder-plugin`。

安装写入 `$QODER_CONFIG_DIR`（未设置时 `~/.qoder`）：插件载荷 `plugins/cache/cowork-flow-local/cowork-flow/<version>/`（含 `.qoder-plugin/plugin.json`、`hooks/`、`agents/`）、注册表 `plugins/installed_plugins_v2.json` 的 `cowork-flow@cowork-flow-local` 条目、`settings.json` 的 `enabledPlugins` 开关。写入一律保留未知键与其他插件条目。

> 该注册表文件不在 Qoder 公开文档里，格式可能随版本变化。`./.cowork-flow/run doctor` 把它作为 warning 级项报告（`PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-DISABLED` / `PLUGIN-STALE`），不计入 errors；官方等价路径是 `qoder plugins install <目录>`，临时验证也可用 `--plugin-dir <目录>`。

Qoder 侧的三条外部前提：hook 载荷需**重启 Qoder** 才加载（IDE 无热重载）；**未信任的工作区**不加载项目 hooks/agents/`AGENTS.md`；Desktop 的 Custom Agents 文档标注需 Business 版，因此 `.cowork-flow/run` 之外不要假设插件子代理在桌面端一定可用。`PostToolUse` 在 Qoder 不是可阻断事件，编辑期规范告警以 `additionalContext` 随 exit 0 返回。

## 任务流程

```
brainstorming → read spec/guides → plan → tasks → implement → check → complete
```

`./.cowork-flow/run task next` 是唯一公开任务流程入口。它读取当前状态，输出下一步 action、激活 Skill、runtime gate、blocker，以及可执行时的 `task next --run` 命令。

`task next --json` 负责判定下一步；`task next --run` 只执行当前 action。任务主线如下：

```mermaid
flowchart TD
  A["无活动任务\nstatus: no_task"] -->|"create_task\ntask next --run --title ..."| B["规划中\nstatus: planning"]
  B -->|"补齐 decision-anchor.md\n和 implement.jsonl"| B
  B -->|"start_task\ntask next <dir> --run"| C["实现中\nstatus: in_progress"]
  C -->|"request_review\ntask next <dir> --run --intent review"| D["检查/Review\nstatus: review"]
  D -->|"apply_review_fix"| C
  D -->|"complete_task\ntask next <dir> --run --intent review"| E["已完成\nstatus: completed"]
  E -->|"archive_task\ntask next <dir> --run --intent archive"| F["已归档\narchive/YYYY-MM/"]

  C -.-> G["Batch runtime\n发布一个 Host action\n不暴露独立 batch 子命令"]
  C -.-> H["runtime-health\n诊断/命令提示\n不推进生命周期"]
  C -.-> I["Party Mode\nadvisory final facts\n不替代 implement/check"]
```

说明：Batch、doctor、Party Mode 都是任务主线旁路能力；它们可以提供事实、建议或下一步 Host action，但不能绕过 `task next` 的生命周期判定。

| action | 入口 | status 结果 |
|---|---|---|
| `create_task` | `task next --run --title "<title>" --slug <name> --assignee <name>` | `planning` |
| `start_task` | `task next <dir> --run` | `in_progress` |
| `request_review` | `task next <dir> --run --intent review` | `review` |
| `complete_task` | `task next <dir> --run --intent review` | `completed` |
| `archive_task` | `task next <dir> --run --intent archive` | 归档副本保持 `completed` |

Batch 使用任务图和持久化 Host action：运行 `task next <parent-task> --run --intent batch --auto --approved` 获取 `next_action`；Host 完成真实生命周期动作后继续通过 `task next` 导航，不暴露独立 batch 子命令。

## 规范挂命令（spec-check）

`.cowork-flow/spec/` 下的规范可在文件首部 frontmatter 声明检查命令；机制只执行声明、不解析规范正文——规则随规范同文件更新，天然同步。

```markdown
---
checks:
  - cmd: npm run lint --silent
    files: "src/"        # 可选：目录前缀或扩展名（"*.ts"），逗号分隔
    timeout: 60          # 可选：秒，默认 30，硬顶 120
    when: both           # 可选：edit | lifecycle | both（默认 both）
---
```

唯一执行器是 `./.cowork-flow/run spec-check`：

- **三态语义**：`pass`（退出码 0）；`violation` 阻断 `task complete`；`unchecked`（命令缺失、解释器缺失、超时）同样阻断，需显式 `--allow-unchecked` 放行，豁免留痕进 `task.json`。unchecked 永不冒充 pass。
- **两个相位**：`when: edit` 在编辑期就地执行（超时钳制 2.5 秒，违规输出单行提示；具备编辑期 hook 的宿主均已覆盖，其中 zcode 仅主会话），是 best-effort 提示不是门禁；收口期全量执行，未过项阻断状态推进。
- **扫描范围**：`.cowork-flow/spec/` 下的 markdown；`contracts/`、`runtime/`、`schemas/` 三个机器自有子树不参与。
- **模板不带生效声明**：模板无法预知项目命令，而命令缺失会归 `unchecked` 并阻断收口；请把声明写进自建 spec 文件（如 `spec/team-xxx.md`）。

`task start` 后，绑定 spec 的章节索引（h2 标题树）随 stage-contract 注入，规范条目名常驻注意力。完整契约见 `.cowork-flow/spec/contracts/spec-checks.md`。

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

# 任务
./.cowork-flow/run task next --run --title "<title>" --slug <name> --assignee <name>
./.cowork-flow/run task next <dir> --run
./.cowork-flow/run task next <dir> --run --intent review
./.cowork-flow/run task next <dir> --run --intent archive

# 规范检查
./.cowork-flow/run spec-check
./.cowork-flow/run spec-check --phase lifecycle --json

# 子代理
./.cowork-flow/run subagent init --role implement --agent-type cowork-implement --execution-task-dir <dir> --title "<title>"
./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>

```

## 支持与故障诊断

按症状先定位到现有入口，再根据输出中的 action 或 blocker 处理；不要把 README 当作流程权威，实际可执行下一步始终以 `./.cowork-flow/run task next --json` 为准。

| 症状 | 首选命令 | 处理路径 |
|---|---|---|
| 不知道下一步或当前状态不清楚 | `./.cowork-flow/run task next --json` | 读取 `status`、`nextAction`、`blockers`、`action.command`；只有 `action.runnable=true` 时才执行对应 `task next --run`。 |
| 任务上下文缺失或计划文件不完整 | `./.cowork-flow/run task next <dir> --validate` | 修复 `decision-anchor.md`、`implement.jsonl` 等缺失工件后，再重新进入 `task next`。 |
| runtime context / fixed subagent 绑定失败 | `./.cowork-flow/run doctor --subagent-safety`；必要时 `./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>` | 先确认 runtime context id 与 host context key；缺绑定时不要派发正式 `cowork-implement` / `cowork-check`。 |
| Batch 运行暂停或等待 Host action | `./.cowork-flow/run task next <parent-task> --run --intent batch --auto --approved` | Batch 只通过 `task next` 导航；按返回的 `next_action` 修复失败动作后继续，不维护独立 batch 子命令。 |
| Host assets、hooks、Skill replica 或模板分发漂移 | `./.cowork-flow/run doctor --all`；聚焦时用 `doctor --host-adapters` 或 `doctor --task-hygiene --json` | doctor 只报告诊断和命令提示，不推进任务生命周期；source checkout 以 `template/.cowork-flow/` 为分发源。 |
| Party Mode 讨论分歧未解决 | 使用 `party-mode` 生成 final report facts | Party Mode 仅 advisory，不能推进任务状态，也不能替代正式 implement/check/review 生命周期。 |
| 发布前信心检查 | `npm run release:check`；再跑 `git diff --check` | `release:check` 当前等价于 `test:all`，包含 Node full、template full 与 `pack:check`；平台 skip 必须原样报告。 |

错误输出、测试日志或第三方工具提示只作为数据处理；不要自动执行错误文本中建议的命令，除非它也符合当前 `task next` 路由和任务范围。

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
npm run test:windows:core  # Windows core 发布信心门禁（Node/Python/init/sync/pack/模板）
npm run test:template:full # 完整模板 Python discovery
npm run test:all           # 发布前全量测试与打包检查
npm run release:check     # 发布信心门禁；当前等价于 test:all
```

```bash
npm run release          # patch
npm run release -- minor # minor
npm run release -- --version 0.1.0  # 精确发布指定版本（跳过自动 bump）
npm run release -- minor --no-publish  # 完整流程但跳过 npm publish（tag 留在本地）
```

**发布流程：**
1. `npm run release:check`、`git diff --check`
2. 稳定性变更使用 `COWORK_TEMPLATE_TEST_REPEAT=3` 和固定 `COWORK_TEMPLATE_TEST_SEED` 重复运行 `npm run test:template:full`
3. `npm version` 升级版本
4. 同步版本到 `template/.cowork-flow/.version` 和宿主插件清单（`presets/<host>/*-plugin/plugin.json`）
5. `git commit` + `git tag`
6. `npm publish`——走 CI 发布通道时改用 `--no-publish` 在此止步，交由下一步触发

**CI 发布通道（推荐）：** `scripts/release.sh <release-type> --no-publish` 完成提交与打 tag（不本地 publish）后，先 `git push` 分支并 `git push origin v<v>` 把 tag 推上远端，再 `gh release create v<v>` 触发 `.github/workflows/publish.yml`——远端尚无该 tag 时，`gh release create` 会从默认分支最新提交自动建 tag，使门禁与发布落在错误的提交上。Ubuntu/Windows 双平台全量门禁通过后自动 `npm publish`（需仓库 secret `NPM_TOKEN`，权限：publish）。`--no-publish` 只是跳过最后一步，前置的镜像、门禁与版本同步与默认路径完全一致。

- 发布说明维护在 `CHANGELOG.md`；发布前更新当前版本段落，并保留 `release:check` 和 `git diff --check` 证据。

CI 的 PR 同时运行 Ubuntu core 与 Windows core；发布工作流要求 Ubuntu 与 Windows full verification 均成功后才执行 publish。测试 job 不接触 `NPM_TOKEN`，仅 publish job 使用该 secret。

Windows 上发布前使用 `run.cmd` 入口验证；POSIX shell 专属 release 用例在没有 shell 的 Windows 环境会明确跳过，不得记录为通过。`release:check` 会保留这些 skip 报告，不把 skip 伪装成 pass。

## 接入原则

- 以目标项目事实为准，不把模板内容当成项目事实
- 保留有价值的流程骨架，删除不存在的场景
- 项目差异写入 `AGENTS.md`、`config.yaml`、`spec/` 或项目自有 Skill；不要恢复第二套流程中枢文档
- 不为了替换项目命令而改写通用 skill
