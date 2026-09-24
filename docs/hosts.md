# 宿主接入

本文说明如何把 cowork-flow 接到 AI 编码宿主，以及安装后如何检查、升级和卸载。只想完成首次安装时，先看 [README](../README.md) 的“完成宿主设置”。

## 先分清两类文件

| 类型 | 写入位置 | 安装方式 |
|---|---|---|
| 项目级文件 | 当前项目的 `AGENTS.md`、`.cowork-flow/` 和宿主目录 | `cwf project init` / `cwf project sync` |
| 机器级组件 | 宿主的用户配置目录，如插件、预设或 hook | `cwf host add` / `cwf host remove` |

每个项目至少需要执行一次 `cwf project init`。是否需要 `cwf host add`，取决于宿主：

| 宿主 | 初始化后是否需要机器级组件 | 建议命令 |
|---|---|---|
| Codex | 当前项目可运行；全局引导入口可选 | `cwf host add codex` |
| Claude Code | 当前项目可运行；全局引导入口可选 | `cwf host add claude-code` |
| OpenCode | 当前项目可运行；全局引导入口可选 | `cwf host add opencode` |
| ZCode | 需要 | `cwf host add zcode` |
| Qoder | 需要 | `cwf host add qoder` |
| DeepSeek Harness | 需要 | `cwf host add dsh` |
| Kimi Code | 工作流注入需要 hook；全局插件可选 | `cwf host add kimi-code --component hook` |

## 通用命令

先预览，再安装：

```bash
cwf host add <host> --dry-run
cwf host add <host>
```

检查项目和 CLI 认识的宿主：

```bash
cwf host list .
cwf host list . --json
```

升级或重装：

```bash
cwf host add <host> --force
```

卸载机器级组件：

```bash
cwf host remove <host>
```

`--force` 只在确认需要覆盖已有安装时使用。安装器遇到不属于自己的文件时默认拒绝覆盖或删除；`--dry-run` 会执行同样的归属检查。

## Codex

```bash
cwf host add codex --dry-run
cwf host add codex
cwf host remove codex
```

安装器会：

- 在 `$CODEX_HOME/plugins/marketplaces/cowork-flow-local/` 准备稳定插件源；未设置 `CODEX_HOME` 时使用 `~/.codex`。
- 调用 Codex 官方 CLI 注册 marketplace 和插件，不手写 `config.toml`。
- 找不到 `codex` 命令时仍准备源目录，并打印手动命令。

插件只携带 `cowork-flow-bootstrap` 引导技能；项目 hook 和三个 fixed subagent 仍由项目级文件提供。安装或升级后新开会话。

升级到新版本时运行：

```bash
cwf host add codex --force
```

## Claude Code

```bash
cwf host add claude-code --dry-run
cwf host add claude-code
cwf host remove claude-code
```

插件写入 `$CLAUDE_CONFIG_DIR/skills/cowork-flow`，未设置时为 `~/.claude/skills/cowork-flow`。Claude Code 会把带 `.claude-plugin/plugin.json` 的技能目录识别为插件，不需要额外 marketplace 命令。

插件只提供引导技能。项目 hook 和 agents 已在 `.claude/` 中，避免多源 hook 重复执行。安装后新开会话。

`~/.claude/skills/` 由用户维护：目标目录不是 cowork-flow 插件时，安装和卸载都会拒绝；确认要接管该目录后才使用 `--force`。

## OpenCode

```bash
cwf host add opencode --dry-run
cwf host add opencode
cwf host remove opencode
```

安装位置是 `$XDG_CONFIG_HOME/opencode/`，未设置时为 `~/.config/opencode`。安装器只写 `plugins/cowork-flow.js` 和 `cowork-flow/`，不修改用户的 `opencode.json`。

插件在 `config` hook 中注册随载荷提供的 `cowork-flow-bootstrap` 技能目录，因此没有初始化 cowork-flow 的仓库也能看到启动入口。安装后新开会话。

OpenCode 可能在插件目录中生成 `package.json`、`bun.lock` 和 `node_modules/`。这些是宿主文件，安装器不会修改或清理。多插件加载顺序以及全局与项目同名技能的优先级尚未实测。

## ZCode

```bash
cwf host add zcode --dry-run
cwf host add zcode
cwf host add zcode --force --prune-old
cwf host remove zcode
```

安装器会维护稳定 marketplace 源和当前活动副本，插件缓存位于 `~/.zcode/cli/plugins/cache/`。插件提供 hook、三个 fixed subagent 和引导技能；项目技能仍由 `.agents/skills/` 提供。

默认保留旧版本缓存，避免正在运行的会话突然失去插件。需要清理旧版本时使用 `--prune-old`。升级后重启 ZCode 或新开会话。

## Qoder

```bash
cwf host add qoder --dry-run
cwf host add qoder
cwf host add qoder --force
cwf host remove qoder
```

安装位置由 `QODER_CONFIG_DIR` 决定，未设置时为 `~/.qoder`。插件提供 hook、三个 fixed subagent 和引导技能；项目级 `init` / `sync` 只写适配声明和共享技能。

Qoder 需要先信任工作区，安装或升级后重启 Qoder。Desktop 是否提供项目子代理取决于版本和 edition；没有确认前不要把它当作可用能力。

Qoder 的插件注册表不是稳定的公开接口。cowork-flow 尽量保留未知字段和其他插件条目，相关诊断按 warning 报告，不影响其它检查。

## DeepSeek Harness

默认安装 Cowork Flow 预设：

```bash
cwf host add dsh --component preset --dry-run
cwf host add dsh
cwf host remove dsh --component preset
```

预设安装到 `~/.dsh/.agent-presets/cowork-flow/`，或 `$DSH_HOME` 对应目录。安装或升级后重启 DSH，在新会话中选择 **Cowork Flow** 预设。

预设已经包含 workflow-state hook，不需要再安装 hook 组件。只有调试组合层配置时才使用：

```bash
cwf host add dsh --component hook
cwf host remove dsh --component hook
```

已验证版本中，hook 组合层本身不会进入 agent 提示；实时状态注入依赖预设。新版 DSH 改变这一行为后，应重新验证并更新本文。

## Kimi Code

工作流状态注入使用 hook 组件：

```bash
cwf host add kimi-code --component hook
cwf host remove kimi-code --component hook
```

安装或更新后重载配置或新开会话。该组件总是重写自己的 hook 区块，不接受 `--force`。

如果还需要在未初始化项目中提供全局引导技能，可以另外安装插件：

```bash
cwf host add kimi-code
```

Kimi Code 目前只能通过 TUI 安装插件。命令会把载荷放到稳定源目录 `$KIMI_CODE_HOME/plugins/sources/cowork-flow/`，然后打印需要在 Kimi 中执行的 `/plugins install <绝对路径>` 和 `/reload`。

`cwf host remove kimi-code` 会删除源目录并提示宿主侧残留；托管副本和注册表记录需要在 Kimi 中执行 `/plugins remove cowork-flow`。

## MCP 客户端接入

需要让 MCP 客户端读取任务事实时，推荐全局注册一次：

```bash
cwf mcp serve
```

客户端从当前工作目录向上查找 `.cowork-flow/`，因此同一注册可服务多个项目。常用配置示例：

```toml
# Codex: ~/.codex/config.toml
[mcp_servers.cowork-flow]
command = "cwf"
args = ["mcp", "serve"]
```

```json
// OpenCode: ~/.config/opencode/opencode.json
{
  "mcp": {
    "cowork-flow": {
      "type": "local",
      "command": ["cwf", "mcp", "serve"],
      "enabled": true
    }
  }
}
```

Claude Code 可运行：

```bash
claude mcp add -s user cowork-flow -- cwf mcp serve
```

不全局安装 CLI 时，也可以直接配置项目内入口：

```bash
<project>/.cowork-flow/run mcp-state
```

## 技能发现

项目技能的唯一源码是 `template/skills/`，`init` / `sync` 按下表分发。宿主插件不再携带项目技能的副本。

| 宿主 | 项目技能读取根 | 宿主发现方式 |
|---|---|---|
| Codex | `.agents/skills/` | 原生扫描 `.agents/skills/` |
| Claude Code | `.claude/skills/` | 原生扫描项目 `.claude/skills/` |
| OpenCode | `.agents/skills/` | 扫描 `.agents/skills/` 和 `.opencode/skills/`；cowork-flow 只交付前者 |
| ZCode | `.agents/skills/` | 扫描项目 `.zcode/skills/` 与 `.agents/skills/`；同名时前者优先 |
| Qoder | `.agents/skills/` | `loadFromAgentsDirectory` 默认开启 |
| Kimi Code | `.agents/skills/` | `PROJECT_GENERIC_DIRS` 包含 `.agents/skills` |
| DeepSeek Harness | `.agents/skills/` | `skill-filesystem` 将其作为项目技能根 |

这些通道在 Host Asset Manifest 中以 `verified:` 记录。宿主升级后，如果发现行为变化，应更新证据和测试，不要只改文档。

## 诊断

先运行：

```bash
./.cowork-flow/run doctor --all
./.cowork-flow/run doctor --all --json
```

<details>
<summary>常见诊断码</summary>

| 范围 | 诊断码 | 含义 |
|---|---|---|
| 通用技能 | `SKILL-READROOT-MISSING` | 项目缺少声明的技能读取根 |
| 通用技能 | `PLUGIN-SKILLS-LEGACY` | 旧插件仍携带项目技能副本，需要重装插件 |
| 通用技能 | `SKILL-DISCOVERY-GATED` | 宿主需要信任目录或重启后才加载技能 |
| Codex | `PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-DISABLED` | 插件未注册、载荷缺失或未启用 |
| Claude Code / OpenCode | `PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-STALE` | 插件未安装、载荷不完整或版本落后 |
| Qoder | `PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-DISABLED` / `PLUGIN-STALE` | 插件安装、启用、载荷或版本异常 |
| DSH 预设 | `PRESET-UNKNOWN-VERSION` / `PRESET-STALE` | 预设缺少版本标记或版本落后 |
| DSH / Kimi hook | `HOOK-NOT-INSTALLED` / `HOOK-SHIM-MISSING` / `HOOK-UNKNOWN-VERSION` / `HOOK-STALE` | hook 区块、脚本、版本标记或版本不匹配 |
| Kimi 插件 | `PLUGIN-NOT-INSTALLED` / `PLUGIN-DISABLED` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-STALE` / `PLUGIN-SOURCES-MISSING` | 尚未完成 TUI 安装、插件被禁用、载荷不完整、版本落后或源目录丢失 |

Kimi Code 刚运行 `cwf host add kimi-code`、但还没在 TUI 执行 `/plugins install` 时，`PLUGIN-NOT-INSTALLED` 属于正常中间状态。

</details>

## 插件图标字段

不同宿主支持的清单字段不同，不要给所有清单复制同一组字段。

| 宿主 | 支持字段 | 要求 |
|---|---|---|
| Codex | `interface.logo`、`interface.brandColor` | logo 必须是载荷内相对路径 |
| ZCode | marketplace 条目的 `icon` | 必须是 `https://` URL |
| Claude Code、OpenCode、Qoder、DSH、Kimi Code | 无 | 不要写图标键 |

`assets/icon.svg` 是品牌图标的唯一源，`presets/plugin-meta.json` 保存品牌色。发布时运行 `npm run icons:export` 重新导出栅格。

## 环境变量

| 变量 | 用途 |
|---|---|
| `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1` | 关闭所有宿主的 hook 注入 |
| `COWORK_FLOW_CONTEXT_ID` | 显式指定会话身份；宿主不提供会话变量时使用 |
| `COWORK_FLOW_HOST` | 显式指定宿主 id |
| `COWORK_FLOW_CODEX` | 指定 Codex CLI 可执行文件 |
| `DSH_HOME` | 覆盖 DeepSeek Harness 配置根目录 |
| `KIMI_CODE_HOME` | 覆盖 Kimi Code 配置根目录 |
| `CODEX_HOME` | 覆盖 Codex 配置根目录 |
| `QODER_CONFIG_DIR` | 覆盖 Qoder 配置根目录 |
| `CLAUDE_CONFIG_DIR` | 覆盖 Claude Code 配置根目录 |
| `COWORK_FLOW_BROWSER` | `icons:export` 使用的浏览器可执行文件 |
