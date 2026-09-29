# DSH Host Adapter 标记

cowork-flow 用本目录识别项目已接入 DeepSeek Harness（DSH），`sync` 据此自动识别并刷新 DSH 资产（`AGENTS.md`、`.agents/skills/`、`.cowork-flow/adapters/dsh/`）。

DSH 侧无需其它配置：`AGENTS.md` 作为工作区指令、`.agents/skills/` 作为技能目录被自动发现。

## DSH 子代理派发与绑定（实测 2026-08-14）

主会话派发正式固定代理（cowork-implement / cowork-check / cowork-research）的实测路径：

1. 主会话创建 runtime context（runtime 自 0.0.52 起自动识别 `DSH_SESSION_ID`，会话命令无需显式设置上下文键）：
   `./.cowork-flow/run subagent init --title <t> --role cowork-implement --execution-task-dir <task-dir> --host dsh --adapter dsh`
   输出 JSON 含 `cowork_runtime_context_id` 与 `cowork_host_context_key`。
2. 用 DSH `subagent` 工具派发子代理，prompt 携带上述两个字段。
3. 子代理首步执行 `./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>`；结束后执行 `./.cowork-flow/run subagent close <runtime_context_id>`。

实测结论：bind → status → 读取绑定任务目录 → close 全链路在 DSH 子代理上可用；DSH 子代理具备 shell 工具，绑定状态文件语义正确（close 后 session 文件按设计清理）。

平台标注：0.0.51 起 `platform_from_context_key` 已映射 `dsh_` 前缀；0.0.52 起 `DSH_SESSION_ID` 自动解析为 `dsh_<id>` 上下文键（`COWORK_FLOW_CONTEXT_ID` 显式设置仍优先），主会话与子代理绑定无需再手工导出环境变量。

## workflow-state hook（可选，机器级）

`init` / `sync` 只交付项目资产；

```bash
cwf host add dsh --component hook            # 安装到 $DSH_HOME/cordis.patch.yml（默认 ~/.dsh）
cwf host add dsh --component hook --dry-run  # 预览，不写文件
cwf host remove dsh --component hook         # 卸载托管行（插件文件另加 --force）
```

- 组合层面注册（`dsh --dump-config` 可见）；`cordis.patch.yml` 在启动时组合，安装/更新后需**重启 DSH**。
- 无 `.cowork-flow` 根的项目零开销跳过：插件 JS 预检短路，不注入内容、不启动 Python。
- 全局开关（环境变量）：`COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`。
- 使用预设（`cwf host add dsh --component preset`）时无需再运行本命令——预设已内置同一 hook。

**host 层 section 是否进入提示词按版本分线**（本插件的注册方式未变，变的是宿主）：

| DSH | 行为 | 备注 |
| --- | --- | --- |
| 0.1.1-rc.1（实测） | host 层 section 不被 agent 提示组装收集 | 该版本下实时注入只能靠预设 |
| 0.2.0-rc.1（桌面版，按代码取证） | 全局层 section 会进入每次组装，agent 作用域同名覆盖 | `dsh-scope` 的 `layers.merge()` 先取全局层再用作用域链覆盖；`system-prompt` 行本身在 host 层（`dsh-base`） |

## 预设的两条交付线（0.2.0 起）

`cwf host add dsh --component preset` 同时写两个位置，因为桌面版换了通道：

| 位置 | 适用 | 启用方式 |
| --- | --- | --- |
| `$DSH_HOME/.agent-presets/cowork-flow/` | DSH 0.1.x / CLI 线 | 直接出现在会话的预设列表里 |
| `$DSH_HOME/bundles/cowork-flow/` | DSH 0.2.0+（桌面版） | 在桌面版侧边栏的 Plugins 页里填入该目录的绝对路径安装（`plugin_manager` 工具行在桌面宿主的组合里是禁用行，会话中不可用），再开新会话 |

0.2.0 起预设不再是目录，而是 bundle patch 里 `@deepseek-ai/dsh-agent-preset` 的一条声明行；宿主自带技能已注明 legacy 目录 "Nothing reads that directory any more"。bundle 的安装动作由宿主完成（它会跑包安装并写 profile 清单），因此 `cwf` 只产出 bundle 与安装指令，不改写 `~/.dsh/profiles/**`。

两条线的内容只差宿主 API 不同的两处：工作流行（0.1.x 用 `@deepseek-ai/dsh-workflow-worker-thread`，0.2.0 用 `@deepseek-ai/dsh-workflow-ptc`，bundle 生成时替换）和 persona 行的配置键（0.1.x 的 `dsh-persona` 是单个 `text`，0.2.0 要求 `prefix`／可选 `suffix`；bundle 把同一段文字移到 `prefix`）。这两处必须与目标线的包集合和 schema 一致——包解析不到、或配置键不被接受，宿主会把**整个**预设判为不可用（0.1.x 的预设发现会标注 "names a plugin that cannot be resolved"，0.2.0 则在挂载时校验失败并标记 broken），不是只丢那一行。

`$DSH_HOME/bundles/cowork-flow/` 由 `cwf` 管理，请不要改名或手工编辑：目录名、包名与声明行 id 同源于同一个标识，改名会让卸载认不出来、重装另生成一份。要停用请先在 DSH 的插件管理器里 drop 掉 bundle，再运行 `cwf host remove dsh --component preset`。

