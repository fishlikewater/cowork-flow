# 宿主接入

cowork-flow 的资产分两层：**项目级**由 `cwf project init` / `cwf project sync` 写进项目（`AGENTS.md`、`.cowork-flow/`、各宿主的项目目录、技能），**机器级**由 `cwf host add` 装进宿主自己的配置目录（插件、预设、hook）。本文按宿主说明机器级接入，并给出每个宿主的项目技能发现路径。

命令面的完整参考在 [README 的 CLI 命令一节](../README.md#cli-命令)。

## 宿主与机器级组件

每个宿主有哪些机器级组件、`host add` 默认装哪个，见 [README 的「宿主支持」表](../README.md#宿主支持)——那张表是组件归属的唯一一份，本文只补充各宿主的安装落点与前提。

每个声明的宿主都有一个机器级组件；不装则只用项目级资产。宿主别名同样可用（如 `claude`、`kimi`、`qoder-cli`，见 Host Asset Manifest 的 `aliases`）。

`host add <host> --uninstall` 与 `host remove <host>` 是同一条路径，保留前者只为让旧命令名能被原样重写。`host list` 只报「声明与项目选中」；机器安装是否健康（载荷缺失、版本过期、技能重复）由 `./.cowork-flow/run doctor` 负责。

## 项目技能如何分发到各宿主

Skills 维护在 `template/skills/` 唯一源码，`init` / `sync` 时按目录分发到对应平台；`SKILL.md`、可选的 command `manifest.json` 和 `scripts/` 一起归属该 Skill：

| 平台 | 读取根 / 目标目录 | 宿主原生发现 |
|---|---|---|
| `codex` | `.agents/skills/` | `.agents/skills/`（verified：探针任务 `09-23-codex-plugin-probe` 的 `codex debug prompt-input` skill roots 表列出 `<cwd>/.agents/skills`） |
| `opencode` / `dsh` / `kimi-code` | `.agents/skills/` | 声明为 `.agents/skills/`（assumed，未逐一本机验证） |
| `claude-code` | `.claude/skills/` | 声明为 `.claude/skills/`（assumed） |
| `qoder` | `.agents/skills/` | `.agents/skills/`（verified：SDK 默认开启；受信任目录 + 重启门禁） |
| `zcode` | `.agents/skills/` | `.agents/skills/` 与 `.zcode/skills/`（verified：宿主 bundle 的 `SkillService.list` 枚举 `<workspace>/.zcode/skills`、`<workspace>/.agents/skills`，含祖先目录向上探测，同名时 `.zcode/skills` 优先；我们只交付共享的 `.agents/skills/`） |

每个平台在 `host-assets.json` 里用两格声明这件事：`skillReadRoot`（我们运行时渲染与 fixed subagent 读取的仓库内路径）与 `skillDiscovery[]`（宿主自己发现该路径的通道，带 `scope` / `gates` / `evidence`）。读取与发现同址时项目里只有一份副本，且机器级载荷（插件、preset）不再携带项目技能副本——插件只额外携带一个新名引导技能 `cowork-flow-bootstrap`；`evidence` 以 `verified:` / `assumed:` 前缀区分「本机验证过」与「沿用约定未验证」，后者由门禁测试逐项登记——声明写错会在 CI 变红，而不是静默生效。`./.cowork-flow/run doctor` 按同一份声明检查交付偏差：`SKILL-READROOT-MISSING`（声明的读取根不在项目里）、`PLUGIN-SKILLS-LEGACY`（插件载荷仍带与项目同名的技能副本，重装即清理）、`SKILL-DISCOVERY-GATED`（发现通道有宿主侧门禁，如信任目录 / 重启），三项均为 warning，不计入 errors。

分发动作：`adversarial-review`、`agent-dispatch`、`batch-execution`、`brainstorming`、`cowork-flow`、`cowork-flow-maintenance`、`decision-audit`、`failure-analysis`、`game-design`、`party-mode`、`python-runtime-design`、`runtime-health`、`spec-sync`、`task-planning`、`task-review`、`test-first`

## 宿主图标字段

插件清单里的图标不是「哪家都支持」——每家能读的字段不同，写错的表现也不同，所以只对查证过的字段接线：

| 宿主 | 字段 | 取值形式 | 写错的后果 |
|---|---|---|---|
| `codex` | `interface.logo`、`interface.brandColor` | 载荷内相对路径（`./assets/logo.svg`）与十六进制色 | 路径不在载荷内则显示破图，且**任何一层都不报错**——载荷会被整目录拷进 `$CODEX_HOME`，所以文件必须落在 `presets/codex/` 里 |
| `zcode` | marketplace 条目的 `icon`（**插件清单没有图标键**） | 绝对 `https://` URL | 非 `https://` 开头一律**静默丢弃**并回退默认图标：客户端判定为 `typeof icon === 'string' && icon.startsWith('https://')`，不匹配就当没有图标，不警告 |
| `opencode` | 无 | — | 插件就是一段被宿主 import 的 JS 模块，**没有清单**，因此没有可写图标的字段 |
| `claude-code` | 无 | — | skills 目录插件清单只认 `name` / `version` / `description` / `author` / `homepage` / `repository` / `license` / `keywords` / `skills` 这类字段，没有图标位；`claude plugin validate` 对未知键不做校验，写了只是死重量 |
| `qoder` | 无 | — | agent 插件清单没有图标位（组件发现清单只有 `commands` / `skills` / `agents` / `hooks` / `output-styles` / `workflows` / `bin` / `.mcp.json` / `mcp.json`）；写未知键等于给宿主不支持的字段塞值 |

品牌资产本身：`assets/icon.svg` 是唯一源（24×24 网格、`currentColor`、无外部引用），品牌色只写在 `presets/plugin-meta.json` 的 `brandColor`；`npm run icons:export` 从源导出 `assets/icon.png`（512×512 透明底）并同步 codex 载荷内的副本。zcode 的图标 URL 由 `repository` + `defaultBranch` + `icon.raster` 推导，不写死。三条都有门禁守着（见 `test/plugin-metadata.test.js`）。

## MCP 客户端接入

事实层以只读 MCP 服务（工具 `task_state` / `task_list`）提供给任意客户端。两种入口：

- **全局（推荐）**：`cwf mcp serve`（npm 全局 CLI 透传）。注册一次，所有 cowork-flow 项目通用——项目根由客户端启动时的 cwd 向上解析。
- **项目级**：`<project>/.cowork-flow/run mcp-state`（不依赖全局安装，每项目一份配置）。

stdio 注册样例（`cwf` 与 `cowork-flow` 是同一个入口；旧的 `cowork-flow mcp-state` 拼写仍然有效，已写进配置的用户无需改动）：

```toml
# Codex（~/.codex/config.toml）
[mcp_servers.cowork-flow]
command = "cwf"
args = ["mcp", "serve"]
```

```json
// OpenCode（~/.config/opencode/opencode.json）
{"mcp": {"cowork-flow": {"type": "local", "command": ["cwf", "mcp", "serve"], "enabled": true}}}
```

- **Claude Code**：`claude mcp add -s user cowork-flow -- cwf mcp serve`（项目级 `.mcp.json` 写同构条目）。
- **ZCode**：客户端设置的 MCP 服务器中添加同构 stdio 条目（命令 `cwf`、参数 `mcp serve`；旧拼写 `cowork-flow mcp-state` 仍然有效）。

项目级注册的健康检查由 `./.cowork-flow/run doctor` 报告。

## OpenCode

项目级资产（`.opencode/` 下的 `agents/`、`commands/`、`plugins/`）由 `project init` / `project sync` 交付。机器级接入是 `cwf host add opencode`：写 `$XDG_CONFIG_HOME/opencode/`（未设置时 `~/.config/opencode`），不调用 `opencode` CLI，也不改用户的 `opencode.json`。

```bash
cwf host add opencode              # 写 ~/.config/opencode/plugins/cowork-flow.js 与 cowork-flow/
cwf host add opencode --dry-run    # 预览落点，不写文件
cwf host add opencode --force      # 覆盖同名外来文件
cwf host remove opencode           # 删这两处；plugins/ 被我们清空则一并删掉
```

**插件自己注册技能目录（方案 D）。** 载荷在 `config` hook 里用 `import.meta.url` 自定位，把自带的 `cowork-flow/skills/` 追加进 `config.skills.paths`；宿主随后照常发现并加载其中的引导技能。这样全局插件在**没有 cowork-flow runtime 的仓库**里也能交付引导技能——这正是机器级接入存在的理由。安装器不写用户配置：`opencode.json` 是用户资产。

这条路径建立在**三条非 prose 文档化的契约**上，全部在 opencode 1.1.53 上实证（探针任务归档 `09-23-opencode-skills-probe`，脚本可复跑）：

| 契约 | 取证 | 写错的后果 |
|---|---|---|
| `config` hook 被调用，且 `Config.get()` 返回**缓存**对象，改动对后续技能扫描可见 | 二进制内嵌 JS：`Plugin.init` 内 `for (const hook of hooks) await hook.config?.(config)`；`Plugin.init` 是 `InstanceBootstrap()` 第一步，`Skill.state` 惰性求值 | 技能目录注册了但不会被扫描到 |
| `skills.paths` 是公开 JSON schema 字段（prose 配置文档未提） | `https://opencode.ai/config.json` → `$defs/Config/properties/skills.paths` | 字段名写错 → 静默无效 |
| 插件模块的**每一个导出**都被当插件工厂调用 | 二进制内嵌 JS：`for (const [_name, fn3] of Object.entries(mod2)) { hooks.push(await fn3(input)) }` | 任何非函数导出或返回 `null` 的工厂 → 宿主 bootstrap 整进程崩溃 |

宿主升级后这三条若变化，用探针脚本复核：`bash .cowork-flow/tasks/archive/2026-09/09-23-opencode-skills-probe/run-probe.sh`（全程 XDG 隔离，不触碰真实配置）。


**插件模块只能导出插件函数。** opencode 加载插件时遍历模块的**每一个导出**并逐个当插件工厂调用，随后遍历每个工厂返回的 hooks 对象。任何被导出的常量、helper，或返回 `null`/`undefined` 的工厂，都会让宿主在 bootstrap 阶段整进程崩溃（1.1.53 实测：`project init` 过的项目启动即退出码 1）。cowork-flow 因此把逻辑与适配分开：

| 路径 | 角色 |
|---|---|
| `.opencode/plugins/cowork-flow.js` | 宿主加载的适配层，只导出 `CoworkFlowPlugin` |
| `.opencode/cowork-flow/plugin-core.js` | 契约摘要、阶段契约、scope 规则、runtime context 绑定、编辑期 spec-check |

`plugin-core.js` 所在的命名空间目录不在宿主任何扫描面内（插件发现 glob 为 `{plugin,plugins}/*.{ts,js}` 且不递归）；把它放在插件文件同级目录之外，也让项目安装（`.opencode/`）与机器级安装（`~/.config/opencode/`）的载荷结构自相似，适配层的相对导入在两处都成立。`test/opencode-plugin.test.js` 钉住「每个导出都是函数且调用后返回对象」这条契约。

状态注入走 `experimental.chat.system.transform`（`stateInjection: plugin`），编辑期 spec-check 走 `tool.execute.after`。`.cowork-flow/` 流程文件仍由显式 `cwf project init` / `cwf project sync` 在项目根目录管理。

**元数据上限**：opencode 没有任何插件元数据面——不展示插件名、描述、图标，也没有清单文件。`cwf host add opencode` 的 stdout 是唯一的「安装信息面」，这也是这个载荷只声明 `source`、不声明清单的原因。升级信息只能靠 doctor 的 `PLUGIN-STALE`。

OpenCode 侧插件检查（warning，不进 errors）：`PLUGIN-NOT-INSTALLED`（配置目录里没有插件文件）、`PLUGIN-PAYLOAD-INCOMPLETE`（缺 `plugin-core.js` 或引导技能，插件会注册一个不存在的技能目录）、`PLUGIN-STALE`（**与项目自己的 `.opencode/` 副本比对内容**——两者是同一份源交付两次，不一致就说明只更新了一边；没有清单可携带版本，所以只能比内容）。文件里不含 `CoworkFlowPlugin` 标记的同名文件被当作别人的插件，不报也不删。项目尚未生成自己的 `.opencode/` 副本时跳过陈旧检查。

**未验证项**（诚实边界）：多插件共存时的加载顺序，以及全局插件技能与项目同名技能同时存在时的优先级——两者都未实测，不做承诺。

外部前提：`plugins/` 是用户放自己插件的目录，安装器只在文件里带 `CoworkFlowPlugin` 标记时才删除或覆盖，其余情况需要显式 `--force`。插件 Skills 需**新会话**才加载。实测观察：opencode 加载插件时会在自己的配置目录里生成 `package.json` / `bun.lock` / `node_modules/`（宿主为插件作者物化 `@opencode-ai/plugin`），这些是宿主的产物，安装器不碰也不清理。

## ZCode

```bash
cwf host add zcode     # 安装
cwf host add zcode --force  # 覆盖已安装
cwf host add zcode --force --prune-old  # 覆盖并清理旧版本缓存
cwf host remove zcode  # 卸载：删缓存目录、两个 marketplace 副本与 known_marketplaces 条目
```

安装到 `~/.zcode/cli/plugins/cache/cowork-flow-local/cowork-flow/<version>/`。安装器会同时写入稳定 marketplace source：`~/.zcode/cli/plugins/cache/marketplaces/cowork-flow-local/marketplace.json`，以及 ZCode 当前使用的活动副本：`~/.zcode/cli/plugins/marketplaces/cowork-flow-local/marketplace.json`。`known_marketplaces.json` 指向稳定 source 目录，避免 ZCode 刷新活动副本时删除自己的 source。

安装新版本时，marketplace 中只保留一个 `cowork-flow` entry 并指向最新版本目录；旧版本缓存默认保留，避免正在运行的 ZCode session 仍引用旧插件根目录。需要清理旧版本时显式传 `--prune-old`。

ZCode 插件安装 hook、agents 和一个引导技能；`.cowork-flow/` 流程文件仍由显式 `cwf project init` / `cwf project sync` 在项目根目录管理。插件不会通过 scaffold 创建 `.cowork-flow/`，因此不会在多模块项目的模块目录重复落盘流程文件。

**项目技能走项目通道，插件只带引导技能**：16 个项目技能由 `init` / `sync` 写到 `.agents/skills/`，这正是 ZCode 自己枚举的路径之一（另一条是 `.zcode/skills/`，同名优先，我们不交付），fixed subagent 也从同一路径读取。插件载荷另带 `skills/cowork-flow-bootstrap/`——一个只在仓库没有 `.cowork-flow/` 时引导 `npx cowork-flow project init` 的新名技能，让插件在未初始化目录里也能给出入口。载荷技能名必须与项目技能名零交集：ZCode 同时枚举项目根与插件根且不按技能名去重，同名技能会以两份身份进入技能列表、并在激活时双份注入正文（两家插件测试把这条固化为门禁）。

载荷里出现**与项目同名**的技能副本时，`./.cowork-flow/run doctor` 以 `PLUGIN-SKILLS-LEGACY` 报出（warning，不进 errors），提示用 `--force` 重装清理；只带 bootstrap 的载荷不告警。

**Hook 注入内容：**
- `workflow-state` — 当前任务状态
- `contract-digest` — 合同摘要：SessionStart 注入完整块，后续消息仅重复 SHA256 fingerprint
- `delegated_subtask` — 子代理运行时上下文

**插件子代理：**
- `cowork-implement` — 绑定 runtime context 后执行计划内实现
- `cowork-check` — 绑定 runtime context 后做独立检查
- `cowork-research` — 绑定 runtime context 后做只读调研

## Qoder

Qoder 的宿主集成面（hooks、三个 fixed subagent、命令面说明）打包成一个 Qoder 插件；`init` / `sync` 只写 `.cowork-flow/adapters/qoder/adapter.yaml` 这一份声明，不生成 `.qoder/` 目录（`.qoder/` 在 `excludedPrefixes` 里）。

**项目技能只走项目通道，插件只带引导技能**：`init` / `sync` 把技能写到 `.agents/skills/`，这正是 Qoder 自己扫描的路径（`loadFromAgentsDirectory` 默认开启），因此模型能原生发现并调用，fixed subagent 也从同一路径读取——项目里只有一份副本，随 `.cowork-flow/.version` 钉版本。前提是**工作区已信任**且技能设置生效需**重启**。插件载荷另带 `skills/cowork-flow-bootstrap/`——一个只在仓库没有 `.cowork-flow/` 时引导 `npx cowork-flow project init` 的新名技能，让未 `init` 的仓库也有入口；载荷技能名与项目技能名零交集，同名副本由 doctor 报 `PLUGIN-SKILLS-LEGACY`。

```bash
cwf host add qoder              # 安装并启用（已存在时不覆盖）
cwf host add qoder --dry-run    # 预览将写入的载荷、注册表条目与开关
cwf host add qoder --force      # 覆盖重装（重写插件缓存内容）
cwf host remove qoder           # 卸载：只回收 cowork-flow 自己的条目与缓存目录
```

两个频次边界，缺一不可：

- **插件每机一次**：换机器或升级 cowork-flow 后要重装。
- **`init` 每项目一次**：未 `init` 的项目里装了插件也不会注入——hook 入口按载荷 `cwd` 向上找不到 `.cowork-flow` 时直接 exit 0（静默）。同事克隆仓库后需要各自执行一次 `cwf host add qoder`。

安装写入 `$QODER_CONFIG_DIR`（未设置时 `~/.qoder`）：插件载荷 `plugins/cache/cowork-flow-local/cowork-flow/<version>/`（含 `.qoder-plugin/plugin.json`、`hooks/`、`agents/`）、注册表 `plugins/installed_plugins_v2.json` 的 `cowork-flow@cowork-flow-local` 条目、`settings.json` 的 `enabledPlugins` 开关。写入一律保留未知键与其他插件条目。

> 该注册表文件不在 Qoder 公开文档里，格式可能随版本变化。`./.cowork-flow/run doctor` 把它作为 warning 级项报告（`PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-DISABLED` / `PLUGIN-STALE`），不计入 errors；官方等价路径是 `qoder plugins install <目录>`，临时验证也可用 `--plugin-dir <目录>`。

Qoder 侧的三条外部前提：hook 载荷需**重启 Qoder** 才加载（IDE 无热重载）；**未信任的工作区**不加载项目 hooks/agents/`AGENTS.md`；Desktop 的 Custom Agents 文档标注需 Business 版，因此 `.cowork-flow/run` 之外不要假设插件子代理在桌面端一定可用。`PostToolUse` 在 Qoder 不是可阻断事件，编辑期规范告警以 `additionalContext` 随 exit 0 返回。

## Claude Code

Claude Code 的插件通道和另外三家都不一样：**没有 marketplace，也没有安装记录**。任意技能目录下的文件夹只要带 `.claude-plugin/plugin.json`，就被识别为 `<name>@skills-dir` 插件，装上即可用。所以这里的安装器只做一件事——把一个目录写进 `$CLAUDE_CONFIG_DIR/skills/cowork-flow`（未设置时 `~/.claude`）。

```bash
cwf host add claude-code              # 写 $CLAUDE_CONFIG_DIR/skills/cowork-flow
cwf host add claude-code --dry-run    # 预览落点，不写文件
cwf host add claude-code --force      # 同版本也重写
cwf host remove claude-code           # 删该目录
```

载荷只有清单和引导技能（`skills/cowork-flow-bootstrap/`，与 codex / zcode / qoder 载荷逐字一致）。**hook 与 agents 都留在项目级**：Claude Code 的 hook 是**多源叠加**——`~/.claude/settings.json`、项目 `.claude/settings.json`、插件 hook 会一起执行，插件再带一份 hook 就是双份注入（codex 上同一个坑已经踩过）；项目级 `.claude/agents/` 已经把三个 fixed subagent 交付到位，插件再带一份只会让同一件事有两个名字。`claude plugin details` 的组件清单就是这条设计的现场证据：`Skills (1) cowork-flow-bootstrap`、`Agents (0)`、`Hooks (0)`。

本机实测（claude 2.1.202，隔离 `CLAUDE_CONFIG_DIR`）：装完 `claude plugin list` 显示 `cowork-flow@skills-dir`、`Version: 1.6.0`、`Scope: user`、`Status: ✔ loaded`；`claude plugin validate` 通过；卸载后列表回到 `No plugins installed`。

Claude Code 侧插件检查（warning，不进 errors）：`PLUGIN-NOT-INSTALLED`（技能目录下没有 cowork-flow 插件，或清单不可读）、`PLUGIN-PAYLOAD-INCOMPLETE`（清单在但缺引导技能，等于什么都不贡献）、`PLUGIN-STALE`（清单版本与 `.cowork-flow/.version` 不一致——这个插件不随 `sync` / npm 升级，只能重装）。清单里 `name` 不是 `cowork-flow` 的目录被当作别人的技能，一律不报也不删。

外部前提：`~/.claude/skills/` 是用户手工维护的目录，安装器只在清单 `name` 为 `cowork-flow` 时才删除或覆盖；其余情况**覆盖与删除都默认拒绝**，`--force` 是唯一的显式放行。`--dry-run` 会跑同一套归属检查，所以预览不会承诺一次真跑会拒绝的安装。插件 Skills 需**新会话**才加载。


## Codex

Codex 的插件格式只有 skills / hooks / mcp / assets 四类组件，**没有 agents**：同样一份语法错误的 agent 定义放在项目级 `.codex/agents/` 会被 `codex doctor` 报 `Ignoring malformed agent role definition`，放进插件根则零报错（探针任务 `09-23-codex-plugin-probe`，双向对照）。因此三个 fixed subagent（`.codex/agents/*.toml`）与 hook（`.codex/hooks.json`）**继续由项目级 `init` / `sync` 交付**，插件只承担引导技能。

```bash
cwf host add codex              # 写 marketplace 源并委托 codex CLI 注册 / 启用
cwf host add codex --dry-run    # 预览源目录与将执行的 CLI 命令
cwf host add codex --force      # 同版本也重新注册（重物化插件缓存）
cwf host remove codex           # 卸载：remove 插件与 marketplace，再删源目录
```

安装器把载荷写进稳定 marketplace 源 `$CODEX_HOME/plugins/marketplaces/cowork-flow-local/`（未设置 `CODEX_HOME` 时 `~/.codex`）：`.agents/plugins/marketplace.json` + `plugins/cowork-flow/`。**`config.toml` 始终由 codex CLI 自己写**——安装器只执行 `codex plugin marketplace add <源目录>` 与 `codex plugin add cowork-flow@cowork-flow-local`，不手拼 TOML（写坏了用户无法回退）。CLI 探测顺序：`COWORK_FLOW_CODEX` → `PATH` 上的 `codex` → `<CODEX_HOME>/plugins/.plugin-appserver/codex(.exe)`；都没找到时仍准备好源目录并打印两条手动命令。

源目录被**就地引用**（`plugin list --json` 的 `marketplaceSource.source` 指向它），所以位置长期稳定；`plugin add` 把载荷整目录拷进 `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/`，重复执行幂等，版本变化时重物化并清掉旧版本目录——这也是升级路径。

**项目技能只走项目通道，插件只带引导技能**：`init` / `sync` 把 16 个技能写到 `.agents/skills/`，这是 Codex 枚举的项目级技能根（本机 `debug prompt-input` 的 skill roots 表实证）；插件载荷另带 `skills/cowork-flow-bootstrap/`，与 zcode / qoder 载荷逐字一致——`test/codex-plugin.test.js` 把「三家字节一致」和「载荷技能名与项目技能名零交集」固化为门禁，并断言载荷根不长出 `agents/`。

Codex 侧插件检查（warning，不进 errors）：`PLUGIN-NOT-INSTALLED`（未在 `config.toml` 注册 marketplace）、`PLUGIN-PAYLOAD-MISSING`（注册的源目录里没有插件清单）、`PLUGIN-DISABLED`（缺 `[plugins."cowork-flow@cowork-flow-local"] enabled = true`）；载荷仍带与项目同名的技能副本时复用 `PLUGIN-SKILLS-LEGACY`。

> doctor 只解析 `config.toml` 里 `[marketplaces.cowork-flow-local]` 与 `[plugins."cowork-flow@cowork-flow-local"]` 两个平坦段，其余内容原样不读——CI 的 Python 3.10 没有 `tomllib`，为两格引入 TOML 依赖不划算。

外部前提：插件 Skills 需**新会话**才加载；`codex plugin add` 之后由 codex 自动启用（无需另设开关）。

## DeepSeek Harness（DSH）

```bash
cwf project init ./my-project --platform dsh   # 项目资产：AGENTS.md + .agents/skills/ + .dsh 标记
cwf host add dsh --component hook                   # 机器级：注册 hook 组合行（实时注入见下方说明）
```

`cwf host add dsh --component hook` 把 `workflow-state.js` 插件作为 `insert:` patch 注册到 `$DSH_HOME/cordis.patch.yml`（未设置 `DSH_HOME` 时默认 `~/.dsh`），组合层面可被 `dsh --dump-config` 验证。经实测（DSH 0.1.1-rc.1），**agent 提示组装不收集 host 层 section**：该组合行不会在会话系统提示中产生 `<workflow-state>` 块。当前 DSH 版本下实时注入仍需预设方式（`cwf host add dsh --component preset`）；本命令保留为组合层面的幂等注册能力（卸载见下），待 DSH 支持 agent-scope patch / workspace 级组合后可直接生效。

在未安装 cowork-flow 的项目里 hook 完全无感：JS 侧根目录预检直接短路——不注入内容、不启动 Python 进程。全局开关（环境变量）：`COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`。卸载：`cwf host remove dsh --component hook`（`--force` 同时删除插件文件）。

> 安装或更新后需要**重启 DSH**（`cordis.patch.yml` 在启动时组合，新增/变更不会被热加载）。

> 使用预设（`cwf host add dsh --component preset`）时无需再运行 `cwf host add dsh --component hook`——预设已内置同一 hook。

### DSH 预设

```bash
cwf host add dsh --component preset            # 安装
cwf host add dsh --component preset --force    # 覆盖已安装
cwf host add dsh --component preset --dry-run  # 预览不写入
cwf host remove dsh --component preset         # 卸载（幂等）
```

安装到 `~/.dsh/.agent-presets/cowork-flow/`（`DSH_HOME` 存在时以其为准）：`agent.cordis.yml` + `preset.yml` + `plugins/`。安装后在 DeepSeek Harness 中新建会话并选择 **Cowork Flow** 预设即可使用：persona 携带流程门禁规则，技能由项目级 `.agents/skills/` 提供（`skill-filesystem` 的工作区根，rank 200），预设不再携带技能副本。

预设是**一次性安装的机器级资产**：它不随 `sync` 或 npm 更新。升级 cowork-flow 后需要重跑 `cwf host add dsh --component preset --force` 才会刷新（不带 `--force` 的重复执行是空操作，安装器会在版本不同时给出提示）。安装时会在预设目录写入 `.cowork-flow-preset.json` 版本标记；`./.cowork-flow/run doctor` 比对标记与项目 runtime 版本，过期或缺失时输出 warning 与更新命令。

预设组合是部署 `standard` 预设的拷贝 + 最小改动（persona 流程规则；`skill-filesystem` 组件保持默认根，从工作区 `.agents/skills/` 发现技能）；`cwf project init --platform dsh` 仍负责项目级资产（`AGENTS.md`、`.agents/skills/`、`.dsh/` 标记）。

预设内置 **workflow-state hook**（`plugins/workflow-state.js`）：DSH 原生等效于 Codex/Claude hook，向系统提示末尾注入与其它宿主同构的 `<workflow-state>` 块，每条用户消息刷新一次，并在生命周期命令（`task`/`subagent`/`resume`）执行完成后立即轮内刷新（替换语义，不累积）。项目无 `.cowork-flow` 根、缺少 Python 或设 `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1` 时静默降级，由 AGENTS.md 门禁的运行导航器兜底。

## Kimi Code

Kimi Code 有两个机器级组件，默认装插件；`hook` 是不装插件时的兜底。

```bash
cwf host add kimi-code                        # 默认：物化插件源目录并打印安装指令
cwf host add kimi-code --dry-run              # 预览落点与将打印的指令，不写文件
cwf host add kimi-code --force                # 覆盖同名外来目录
cwf host remove kimi-code                     # 删插件源目录
cwf host add kimi-code --component hook       # 兜底：只装 context 注入 hook
cwf host remove kimi-code --component hook    # 拆掉 hook
```

### 插件组件（默认）

Kimi Code 的插件安装**只有 TUI**——`kimi` 命令没有 plugins 子命令（子命令只有 login/acp/web/install-desktop/doctor/export/migrate/upgrade/vis/provider），只能 `/plugins install <本地目录|zip URL|GitHub URL>`。所以安装器做它唯一能可靠做完的事：把载荷物化到一个**稳定源目录** `$KIMI_CODE_HOME/plugins/sources/cowork-flow/`，然后打印

```
/plugins install <该目录绝对路径>
```

让用户在 Kimi 里执行一次并 `/reload`。源目录位置必须长期稳定：注册表记录的是"从哪里装的"，宿主每次重装都回读它。

**为什么打印指令而不是直写注册表。** 本次从宿主自己的代码里把记录形状取证到位了（桌面版 1.0.3 的 `resources/app.asar` 内含 `packages/agent-core-v2/src/app/plugin/store.ts`）：

| 事实 | 取证函数 |
|---|---|
| 源解析只认 GitHub URL / `http(s)` zip / **绝对路径**（相对路径直接报 `Plugin root must be an absolute path`） | `resolveInstallSource` |
| 本地源先 `realpath` 且必须是目录，再**整目录拷进** `$KIMI_CODE_HOME/plugins/managed/<id>/`（staging + rename，旧目录移走再删） | `normalizeInstallRoot` / `copyPluginToManagedRoot` |
| `id = manifest.name.toLowerCase()` | `normalizePluginId` |
| 注册表 `plugins/installed.json`（`version: 1`）每条记录只落 `{id, root, source, enabled, installedAt, updatedAt, originalSource, capabilities, github}`；本地首次安装 `capabilities`/`github` 为 `undefined` 不落盘，`source` 为 `"local-path"`；`state`/`skillCount`/`manifest`/`diagnostics` 不落盘、`load()` 时重算 | `persist` / `recordFrom` / `materialize` |

形状已知，但宿主的 `install()` 同时承担 realpath 校验、清单解析与 diagnostics、以及 staging + rename 的原子替换。在安装器里重实现这三步等于把宿主私有逻辑抄第二份且没有兼容性承诺——与 codex 侧"不手写 `config.toml`、委托官方 CLI"是同一条理由。取证结果记在这里，将来宿主开放 CLI 子命令时直写有据可循。

**清单只声明 skills。** `skills: "./skills/"` 与 `sessionStart.skill: cowork-flow-bootstrap`——后者是插件在**没有 cowork-flow runtime 的仓库**里唯一有用的部分（会话启动时加载引导技能）。不带 `hooks`：宿主把插件 hook 的 cwd 钉死在插件根（`PluginService.enabledHooks()` 以 `cwd: record.root` 注入，且 hook schema 是 `.strict()`、插件无法自己指定 cwd），而 shim 靠 cwd 向上找项目根，在插件根下必然找不到、直接 `exit 0` 静默空转；注入继续由 config.toml 那条链路交付。不带 `agents`：插件 agent 优先级**最低**（用户级/extra/项目级/`--agent-file` 都赢它），项目级 `.kimi-code/agents/` 已交付三个 fixed subagent，插件再带一份必被盖过。清单 schema 也没有图标字段。

物化后的源目录里还带着 hook 组件的 shim（`hooks/cowork-flow-inject.mjs`，与 `--component hook` 共用同一份 `presets/kimi-code/`）：宿主会把整个目录拷进 `managed/`，但清单不引用它，插件侧不会执行它。

**清单字段（已取证）。** 同一份宿主代码（`packages/agent-core-v2/src/app/plugin/manifest.ts`）把清单 schema 也取证到位了，安装器写的每个键都对得上：

| 规则 | 取证函数 |
|---|---|
| 只有 `name` 必填，须匹配 `/^[a-z0-9][a-z0-9_-]{0,63}$/` | `parseManifest` |
| `skills`/`agents` 每项必须以 `./` 开头、落在插件目录内、且是目录；否则记 error，插件在宿主里呈 `state: "error"`、技能数为 0 | `resolveDirListField` |
| 显示名只从 `interface` 读（`displayName`/`shortDescription`/`longDescription`/`developerName`/`websiteURL`）；列表用 `interface.displayName ?? id` 渲染 | `readInterface` / `recordToSummary` |
| `sessionStart` 只读 `{skill}`；`author` 只读 `{name, email}` | `readSessionStart` / `readAuthor` |
| 其余键（如 `repository`）解析器既不读也不报错，静默丢弃——因此不写 | `parseManifest` |
| 明确报"不支持"的键：`tools`/`apps`/`inject`/`configFile`/`config_file`/`bootstrap` | `recordUnsupportedRuntimeFields` |

**卸载语义照抄宿主**：`/plugins remove cowork-flow` 只删注册表记录，托管副本与源目录都留在盘上。`cwf host remove kimi-code` 删我们物化的源目录，并打印"宿主侧还要你自己清"的提示——不假装清干净了。

Kimi Code 侧插件检查（warning，不进 errors）：`PLUGIN-NOT-INSTALLED`（注册表里没有 cowork-flow 记录——**刚 `host add` 完还没跑 `/plugins install` 就是这个状态**，属正常中间态）、`PLUGIN-DISABLED`、`PLUGIN-PAYLOAD-INCOMPLETE`（记录在但托管副本缺清单或引导技能）、`PLUGIN-STALE`（副本清单版本 ≠ 本项目 `.cowork-flow/.version`）、`PLUGIN-SOURCES-MISSING`（已注册但源目录不在，重装会失败）。项目未声明 kimi-code 宿主时静默。

未验证项（诚实边界）：清单 schema 与记录形状取自桌面版 1.0.3 的内置代码，CLI 侧是否同一份实现未交叉验证（本机无 CLI）；`sessionStart.skill` 的实际注入效果（同样无法脚本化验证）；插件与项目级同名技能的优先级。

### hook 组件（兜底）

这个 hook 没有 `--force`：安装总是重写 shim 与托管块，一个只会重跑同样写入的旗标是空操作，因此被移除而不是留成静默忽略（`cwf host add kimi-code --component hook --force` 会以用法错误退出）。

安装写入用户级 Kimi Code home（`KIMI_CODE_HOME`，未设置时默认 `~/.kimi-code/`）：hook 脚本 `hooks/cowork-flow-inject.mjs`、版本标记 `hooks/.cowork-flow-kimi-hook.json`，并在 `config.toml` 追加一段由注释标记包裹的托管块——一条 `[[hooks]]`，`event = "UserPromptSubmit"`、`command`、`timeout = 30`，不写 `matcher`（即匹配每条提交的提示）。配置文件按文本编辑、不做 TOML 重排，托管块以外的用户内容原样保留；卸载只移除这段托管块和上面两个文件，`config.toml` 因此变空时一并删除。

Kimi Code 只注册 `UserPromptSubmit` 一个事件：`SessionStart` / `PostToolUse` 等观察型事件的 stdout 会被宿主丢弃，无法注入内容。hook 的 stdout 就是注入正文，宿主把它追加进提示上下文；shim 在项目根目录预检失败（非 cowork-flow 项目）时直接短路，不启动 Python 进程，全局开关为 `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`。

> 安装或更新后需要**重启 Kimi Code 会话**（或重新加载配置）才会加载 hook。

Kimi Code 的 Bash 工具不导出会话标识环境变量，CLI 侧身份只能取自注入头里的 `session="kimi_<id>"`，需要显式传 `COWORK_FLOW_CONTEXT_ID`（或 `COWORK_FLOW_HOST=kimi-code`）。`./.cowork-flow/run doctor` 把该 hook 的注册情况作为 warning 级项报告（`HOOK-NOT-INSTALLED` / `HOOK-SHIM-MISSING` / `HOOK-UNKNOWN-VERSION` / `HOOK-STALE`），不计入 errors；这些提示给的修复命令是 `cwf host add kimi-code --component hook`——默认组件是插件，不带 `--component hook` 只会物化插件源目录、注册不了 hook。

## 环境变量

| 变量 | 作用 |
|---|---|
| `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1` | 全局关闭 hook 注入（所有宿主） |
| `COWORK_FLOW_CONTEXT_ID` | 显式指定运行上下文身份（宿主不导出会话标识时使用，如 Kimi Code） |
| `COWORK_FLOW_HOST` | 显式指定宿主 id |
| `DSH_HOME` / `KIMI_CODE_HOME` / `CODEX_HOME` / `QODER_CONFIG_DIR` | 覆盖各宿主的配置根目录 |
| `COWORK_FLOW_CODEX` | 显式指定 codex CLI 可执行文件 |
| `COWORK_FLOW_BROWSER` | 仅供 `npm run icons:export`：显式指定用于导出品牌栅格的 Chromium |
