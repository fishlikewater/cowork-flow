# cowork-flow

[English](README.en.md) | 中文

给 AI 编码助手加一套项目内的协作流程。

开工前先确认目标、计划和改动范围，完成前按项目自己的规则检查。任务状态保存在仓库里，换个会话也能接着做，不用靠聊天记录回忆进度。

支持 Codex、Claude Code、OpenCode、ZCode、Qoder、Kimi Code 和 DeepSeek Harness。

## 它解决什么

- 把需求、决定、计划和允许修改的范围留在项目里。
- 让助手每次工作前先读取当前任务，不凭印象继续。
- 把实现和检查分开，发现问题后再回到实现阶段修正。
- 在已有项目里保护自定义配置、项目自有规格、任务和计划。

cowork-flow 不绑定技术栈，也不会用脚手架改写现有项目。它只在项目中加入一层协作约定和配套文件。

## 适合哪些项目

- 经常让 AI 处理需要多轮确认的功能或修复。
- 希望每个任务都有明确的范围、完成条件和检查记录。
- 需要在多个会话、多个开发成员之间继续同一项工作。
- 已经使用 AI 编码宿主，但任务状态主要散落在聊天记录里。

如果只是问问题、改一两行代码，或者已经有稳定的任务系统，可以先了解再决定是否接入。

## 开始使用

需要 Node.js 20 或更高版本。

### 1. 安装命令

```bash
npm install -g cowork-flow
cwf --version
```

`cwf` 和 `cowork-flow` 是同一个命令。不想全局安装时，除 `cwf self update` 外，可以把下文的 `cwf` 换成 `npx cowork-flow`。

### 2. 初始化项目

先预览将要写入的文件：

```bash
cwf project init --host codex --developer alice --dry-run
```

确认无误后去掉 `--dry-run`：

```bash
cwf project init --host codex --developer alice --language en-US
```

不传 `--language` 时默认 `zh-CN`；交互终端会询问，非交互环境使用默认值。该选择写入 `.cowork-flow/config.yaml`，只影响任务和计划产物（`decision-anchor.md` 与 `plan-template.md`）。

把 `codex` 换成你正在使用的宿主：

`codex`、`claude-code`、`opencode`、`zcode`、`qoder`、`kimi-code`、`dsh`。

命令默认在当前目录初始化；新项目把目标目录作为位置参数传入，例如 `cwf project init ./my-project --host codex`，再进入该目录。省略 `--host` 时，会先按项目里已有的宿主标记（如 `.codex/`、`.claude/`）自动判定；没有标记的交互终端会让你选择，非交互环境则需要显式传入。只有确实会在多个宿主中使用时，才用 `--host all`。

初始化会加入 `AGENTS.md`、`.cowork-flow/` 和对应的宿主文件，不会修改业务代码。已有 `.developer` 不会被覆盖；首次初始化时显式 `--developer` 优先于 `git config user.name`。git 也没有身份时，交互终端会提示，非交互环境报错（`--dry-run` 只报告 `would-skip`，不失败）。`--platform` / `--platforms` 是 `--host` 的兼容别名。已有 `.cowork-flow/config.yaml` 时其中的 `language` 优先，`--force` 也不会重写它；要切换语言请直接编辑该文件后运行 `cwf project sync .`。已有项目建议始终先跑 `--dry-run`。

### 3. 完成宿主设置

Codex、Claude Code 和 OpenCode 在初始化的项目里就能用；ZCode、Qoder、DeepSeek Harness 和 Kimi Code 还需要安装机器级组件：

```bash
cwf host add <host>
```

每个宿主的准确命令、重启要求和特殊情况见 [宿主接入](docs/hosts.md)。

### 4. 在宿主里开始

回到 AI 编码宿主，打开项目根目录并新开会话。直接描述需求即可，例如：

```text
请用 cowork-flow 完成“订单列表按状态筛选”。先把需求、计划和改动范围说清楚，确认后再改代码。
```

需要手动查看当前进度时，在项目根目录运行：

```bash
./.cowork-flow/run task next
```

## 日常使用

- **开始新需求**：直接说明想做什么。助手会先确认目标、计划和允许修改的文件。
- **继续已有任务**：新开会话后说“继续当前任务”。状态和上下文从项目中读取，不依赖上一段聊天。
- **暂停任务**：结束会话即可。任务状态仍保存在项目里，下次继续。
- **更新项目**：升级 CLI 后先预览同步内容，再应用更新。

```bash
cwf self update
cwf project sync . --dry-run
cwf project sync .
```

`project sync` 只更新 cowork-flow 管理的文件。已有配置、`spec/backend|frontend|guides|references`、任务和计划默认保留；框架维护的 `spec/contracts|runtime|schemas` 与 `spec/index.md` 随 sync 更新。`.cowork-flow/config.yaml` 是项目配置，`sync --force` 也不会覆盖它。sync 会读取其中的 `language`，只分发对应语言的 `decision-anchor.md` 合同与 `plan-template.md`；任务和计划默认跟随该语言，用户明确要求时可以覆盖。**正式版旧资产清理** 会按发布清单删除已废弃的 cowork-flow 文件，不触碰其它内容。机器级宿主组件的升级方式见 [宿主接入](docs/hosts.md)。

## 遇到问题

| 情况 | 先做什么 |
|---|---|
| 不知道当前该做什么 | 运行 `./.cowork-flow/run task next` |
| 担心初始化或同步会改错文件 | 给命令加上 `--dry-run` |
| 确认项目选择了哪些宿主 | 运行 `cwf host list .` |
| 技能、插件、hook 或项目文件状态异常 | 运行 `./.cowork-flow/run doctor --all` |
| 不确定命令或参数怎么写 | 运行 `cwf --help` 或 `cwf <group> <command> --help` |

宿主相关问题优先查 [宿主接入](docs/hosts.md)。需要了解工作原理时再看 [架构与扩展](docs/architecture.md)。

<details>
<summary>命令速查</summary>

| 命令 | 用途 |
|---|---|
| `cwf project init [target] --host <host> [--developer <name>] [--language zh-CN|en-US] [--dry-run] [--force]` | 初始化项目 |
| `cwf project sync [target] [--dry-run] [--force]` | 更新项目内由 cowork-flow 管理的文件 |
| `cwf host add <host> [--component <name>] [--dry-run] [--force] [--prune-old] [--uninstall]` | 安装机器级宿主组件 |
| `cwf host remove <host> [--component <name>] [--dry-run] [--force]` | 卸载机器级宿主组件 |
| `cwf host list [target] [--json]` | 查看支持的宿主和项目选择情况 |
| `cwf self update [--dry-run]` | 更新全局安装的 CLI |
| `cwf dev refresh [target] [--dry-run]` | 维护 cowork-flow 仓库时刷新自实例 |
| `cwf mcp serve [args...]` | 向 MCP 客户端提供任务事实 |

旧命令仍可使用；新脚本请使用右侧的新名称。

| 旧名 | 新名 |
|---|---|
| `init` | `cwf project init` |
| `sync` | `cwf project sync` |
| `mcp-state` | `cwf mcp serve` |
| `update` | `cwf self update` |
| `source-refresh` | `cwf dev refresh` |
| `install-zcode-plugin` | `cwf host add zcode` |
| `install-qoder-plugin` | `cwf host add qoder` |
| `install-codex-plugin` | `cwf host add codex` |
| `install-dsh-preset` | `cwf host add dsh --component preset` |
| `install-dsh-hook` | `cwf host add dsh --component hook` |
| `install-kimi-hook` | `cwf host add kimi-code --component hook` |

</details>

## 文档

| 文档 | 内容 |
|---|---|
| [文档索引](docs/index.md) | 全部文档入口 |
| [架构与扩展](docs/architecture.md) | 项目文件如何组织、同步策略与受保护文件 |
| [宿主接入](docs/hosts.md) | 各宿主的安装、重启、排障和卸载方式 |
| [发布与维护](docs/release.md) | 测试、CI 和维护者命令 |
| [参与开发](CONTRIBUTING.md) | 本地开发、提交和 PR 检查 |
| [更新日志](CHANGELOG.md) | 版本变化 |

## 许可

[MIT](LICENSE)
