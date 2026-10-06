# 更新日志

## [Unreleased]

### Added


## [1.7.3] - 2026-10-06

### Fixed

- ZCode 插件 hook shim 由 `.js` 改为 **`.mjs`**，并修复项目根向上查找只覆盖两层的缺陷（1.7.2 遗留说明的收口）。修前两个缺陷叠加：shim 安装到宿主插件缓存目录后无 `package.json`，`.js` 按 CommonJS 解析，ESM `import` 只靠 Node ≥23 的语法探测兜住——仓库声明最低 Node 20，这些机器上 shim 直接语法错误，SessionStart / UserPromptSubmit / PostToolUse 注入从未发生；同时 `findWorkflowRoot` 在循环外缓存 `dirname(current)`，向上查找只覆盖起始目录与其父，hook 事件的 cwd 在项目根下两级及以上（例如从子目录打开会话）时定位不到项目运行时，注入同样为空。现在对齐 qoder / kimi 先例：`.mjs` 扩展名 + `resolve` 起步 + 逐级向上直到文件系统根，其余传输行为零变化。升级动作：升级 CLI 后运行 `cwf host add zcode --force` 刷新插件缓存，并重启 ZCode。


## [1.7.2] - 2026-10-04

### Added

- GitHub 现在会在收到 `v*` tag 推送时自动发布 npm：`.github/workflows/publish.yml` 新增 `push: tags` 触发器与按 tag 归一的 `concurrency` 锁（同一 tag 的重复触发串行化而非并发抢发），`scripts/release.sh --no-publish` 改为推送分支与 tag 并把发布交给 CI，`gh release create` 降级为可选的 Release 说明入口。推送 tag 即发布，无需再手工建 Release。

### Fixed

- 修复 tag 推送通道的空转：`verify-ubuntu` / `verify-windows` / `publish` 三个 job 的触发条件此前只认 `release` 事件和 `inputs.ref`，`on: push: tags` 触发工作流后三个 job 会被全部跳过——运行显示绿色却不会发布任何内容。三个门禁现在都放行 push 事件；Ubuntu 与 Windows 双平台验证仍是发布的硬前置。新增 `test/package.test.js` 断言锁住这一行为。
- npm 发布改用 **Trusted Publishing**（OIDC）：publish job 声明 `id-token: write`，用 GitHub OIDC token 换取短期 npm 凭据，仓库不再保存长期 token。OIDC 交换需要 npm ≥ 11.5.1，而 Node 20 自带 npm 10，因此仅 publish job 改跑 Node 24（两个验证 job 保持 Node 20，与 `engines` 声明一致）。`setup-node` 保留 `registry-url` 以便 npm 读到 registry 后发起交换，但不提供 `NODE_AUTH_TOKEN`——占位符保持未解析，npm 先试交换、失败才回退。此前用 `NPM_TOKEN` secret 时，账号开启双因素认证会导致 CI 发布以 `EOTP` 失败。
- `package.json` 的 `bin` 路径去掉 `./` 前缀：npm 发布时会自动清理并告警，导致 tarball 里的 package.json 与源码不一致。
- Qoder 插件 hook 不再由宿主解析 `python`：改为 **Node 传输 shim**（`command: "node"` + `hooks/inject-context.mjs`），与 ZCode 插件同形态。修前在没有 `python` 命令的机器上（macOS 12.3+、只装 `python3` 的发行版），hook 以 `spawn python ENOENT` 静默失败，SessionStart / UserPromptSubmit 注入从未发生，日志里只有 `Non-blocking hook error(s) … Continuing execution`；Windows 上则依赖 `python.exe` 恰好在 PATH，商店版 Python 等环境同样哑。新 shim 由宿主必备的 Node 运行，内置 `COWORK_FLOW_PYTHON → python3 → python → py -3` 探测链自行定位项目运行时解释器，探测不到时保持 fail-open（exit 0）。升级动作：`cwf host add qoder --force` 刷新插件缓存后重启 Qoder。ZCode 的 `.js` shim（ESM 语法）在安装目录无 `package.json` 时依赖 Node ≥23 的语法探测，仓库声明的最低 Node 20 上会崩溃，建议后续同样改 `.mjs`——本次未动 ZCode。

## [1.7.1] - 2026-09-30

### Fixed

- 三个机器级 hook shim（Qoder / ZCode / Kimi Code）改为 **fail-open**：项目侧运行时返回非零、无法启动或超时时，shim 把原因写进宿主运行日志并返回 0，只跳过本次注入——不再把宿主的「hook 失败」升级成「拒绝用户输入」。修前在 Qoder 里，只要工作区项目的运行时早于 qoder 适配（本项目 9 个旧项目都是），每次输入都会被拦：`inject.py: error: argument --host: invalid choice: 'qoder'` → `exit code 2` → `Blocking hook failure(s) … for UserPromptSubmit`。项目级写入的 Edit 期规范门禁（Claude Code / Codex）保留阻止语义，它与所调用的运行时同源、不存在版本错配。升级动作：`cwf host add qoder --force`（或对应宿主）刷新机器级载荷后重启宿主；要让旧项目恢复注入，再对该项目运行 `cwf project sync .`。

## [1.7.0] - 2026-09-29

### Added

- 新增 `cwf` 命令名，并把命令整理为 `project`、`host`、`self`、`mcp`、`dev` 五组。`cwf --help` 和各层 `--help` 由同一注册表生成。
- 新增统一的机器级宿主命令：`cwf host add`、`cwf host remove` 和 `cwf host list`。
- 新增 Claude Code 插件安装器。插件写入用户技能目录，只提供 `cowork-flow-bootstrap` 引导技能，项目 hook 和 agents 仍由 `project init` 交付。
- 新增 OpenCode 全局插件安装器。插件自行注册引导技能目录，不修改用户的 `opencode.json`。
- 新增 Qoder 插件适配，提供 hook、三个 fixed subagent 和引导技能；工作区需要受信任，安装后需要重启 Qoder。
- 新增 Kimi Code 插件载荷。`cwf host add kimi-code` 默认准备插件源并打印 TUI 安装指令；工作流注入仍可显式使用 `--component hook`。
- 新增 Codex 插件。安装器准备稳定 marketplace 源并委托 Codex 官方 CLI 注册，不直接修改 `config.toml`。
- 新增 `cowork-flow-bootstrap` 机器级引导技能，用于没有项目运行时的目录。
- 新增 `presets/plugin-meta.json` 作为插件显示名、简介、作者、仓库、许可证和关键词的单一来源，并修正作者名拼写。
- Codex 插件支持 `interface.logo` 和 `interface.brandColor`；ZCode marketplace 支持 HTTPS 图标 URL。
- 新增 `SECURITY.md`、Issue 模板、PR 模板、Dependabot 和编辑器基础配置。
- Qoder 的 hook 注入新增一条用户可见痕迹：hook 输出补顶层 `systemMessage`，`qodercli` 的终端 TUI 会把它显示成 `<hook 名> says: <文案>`，每次 SessionStart / UserPromptSubmit 注入都会显示 `cowork-flow: 工作流状态已注入 · status=… · task=…`（只给人看，模型上下文不受影响；Edit 期的规范自查不带这条），文案与实际注入的状态走同一条解析路径。**Qoder 桌面版不渲染 hook 输出文本**：1.1.64 的桌面客户端里没有 `systemMessage` / `hook_system_message` 的渲染路径，聊天中的 hook 部件被直接跳过，所以桌面端要核对注入是否发生，看回复操作条上的锚点图标 tooltip（列出 `SessionStart`、`UserPromptSubmit` 及状态），或看 `~/.qoder/logs/runs/<最新一次运行>/qodercli.log` 里的 `hook.finished … success=true exit_code=0`。其它六个宿主的输出逐字节不变。升级动作：`cwf host add qoder --force` 刷新插件缓存，并在项目里运行 `cwf project sync .` 更新项目运行时（文案由项目运行时渲染），然后重启 Qoder。

### Changed

- 七个宿主统一通过 `host-assets.json` 声明平台、技能根、载荷和同步策略；机器级组件、doctor 和命令帮助与声明保持一致。
- 项目技能只由 `template/skills/` 分发，插件不再复制项目技能。Codex、OpenCode、ZCode、Qoder、Kimi Code 和 DSH 统一改用 `.agents/skills/`；Claude Code 使用 `.claude/skills/`。
- Kimi Code 默认机器级组件改为插件；hook 保留为显式组件。DSH 默认组件仍为预设。
- `template/.zcode/` 迁到 `presets/zcode/`，机器级载荷与项目级资产分目录维护。
- `host-assets.json` 增加 `payload` 描述符，插件安装器从声明读取载荷位置和清单，不再各自硬编码。
- 插件清单统一由元数据投影并在安装时写入版本；项目级和机器级载荷共用同一份引导技能。
- 文档改为 README 用户指南、`docs/` 详细说明、`CONTRIBUTING.md` 贡献流程和 Keep a Changelog 更新日志，并随 npm 包发布。
- 发布脚本新增 `--dry-run` 和 `--no-publish`。前者会真实刷新自实例并运行前置检查，但停在版本 bump 之前；后者完成版本、提交和 tag 后交给 CI 发布。
- CI 明确记录测试跳过项；Windows 缺少 POSIX 前提时不再把跳过记为通过。
- 核心库做了一轮结构与注释整理（Python 运行时 + Node 核心库），**行为与对外契约零变化，无需升级动作**：`# ====` 横幅 13 处、`del` 占位 7 处、超长函数 14 个（Python 7 + Node 7）、≥60 字符的注释行 626 条（Python 161 + Node 465）、模板化 docstring 18 条全部清零；九个宿主安装器的重复骨架收敛为 `src/lib/install-support.js`；注释与 docstring 改为只写读代码看不出来的约束。按设计保留的例外：1 处 93 行的宿主载荷函数（`presets/dsh` 的 `apply`），以及 6 处属于协议或统一命令签名的参数。
- **升级动作**：升级 CLI 后运行 `cwf project sync .`。已有机器级组件按需重装：Codex、Claude Code、OpenCode、ZCode、Qoder 使用 `cwf host add <host> --force`；DSH 使用 `cwf host add dsh --component preset --force`；Kimi Code 重新运行 `cwf host add kimi-code` 并在 TUI 中安装插件。DSH 桌面版（0.2.0+）还需在 DSH 内执行一次 `plugin_manager { action: "install_bundle", target: "$DSH_HOME/bundles/cowork-flow" }`，命令输出里会打印完整路径。

### Fixed

- 适配 DeepSeek Harness 0.2.0 桌面版。0.2.0 起预设不再是 `$DSH_HOME/.agent-presets/<id>/` 目录（宿主自带技能原文："Nothing reads that directory any more"），而是 bundle patch 里 `@deepseek-ai/dsh-agent-preset` 的一条声明行。`cwf host add dsh --component preset` 现在同时写 legacy 目录（0.1.x / CLI 线）与可安装 bundle（`$DSH_HOME/bundles/cowork-flow/`，含生成的 `cordis.patch.yml`、`package.json` 与插件副本），bundle 由宿主自己的插件管理器安装（桌面版是侧边栏 Plugins 页，填 bundle 目录的绝对路径；`plugin_manager` 工具行在桌面宿主组合里被禁用）。两条交付线只差宿主 API 不同的两处，bundle 生成时替换：工作流行（0.1.x `dsh-workflow-worker-thread` ↔ 0.2.0 `dsh-workflow-ptc`）与 persona 行的配置键（0.1.x `text` ↔ 0.2.0 `prefix`）——包解析不到或配置键不被接受，宿主会把**整个**预设判为不可用，因此两边都只写目标线存在的包与 schema 接受的键；workflow-state 插件补订阅 0.2.0 的 `agent/created` 事件（与旧名 `agent/session-start` 并存，两代都能预热）。
- 修复 `config.yaml` 行内注释剥离把引号内的 `#` 也当作注释起点的问题。`description: "a # b"` 以前被解析成 `a`，以 `#` 开头的引号值（`note: "# keep"`）还会被误判成段落头并吞掉后续缩进行。现在只有引号外、且位于行首或空白之后的 `#` 才开启注释；未加引号的 `v1#beta` 按 YAML 语义保留，列表项与标量使用同一判定。
- 修复 OpenCode 插件模块导出测试 helper 后导致宿主启动崩溃的问题。插件入口现在只导出可调用的插件工厂，逻辑放在独立模块中。
- 修复 Kimi Code 插件清单字段和路径不符合宿主 schema 的问题：技能路径改为 `./` 形式，显示信息移入 `interface`，安装器不再输出宿主拒绝的相对源目录。
- 修复 Qoder 插件清单路径不符合宿主 schema、导致插件被整体丢弃的问题。清单的 `hooks`/`agents`/`skills` 沿用了 zcode 宿主的裸路径写法，而 Qoder 要求路径以 `./` 开头（`hooks` 还要以 `.json` 结尾）、`agents` 只接受 `.md` 文件路径——一处不合法宿主就解析清单失败并丢弃**整个**插件：hook 不注册、agents 与 skills 也不加载，只在 `~/.qoder/logs/qodercli.log` 里留一行 `Failed to load installed plugin`。现在 `hooks`/`skills` 用 `./` 形式，`agents` 交给宿主的目录约定发现。升级动作：`cwf host add qoder --force` 后重启 Qoder。
- 修复 ZCode 技能根声明与宿主实际扫描路径不一致的问题，旧 `.cowork-flow/skills/` 副本在同步时清理。
- 修复测试和技能脚本在 `template/`、`presets/` 下写入 `__pycache__` / `*.pyc` 的问题，并增加交付树纯净性门禁。
- 修复 Windows 全新检出把 JavaScript 和运行器脚本转成 CRLF 的问题；`.gitattributes` 固定相关文件使用 LF。
- 修复 CLI 未知旗标被静默忽略的问题。`cwf` 统一区分用法错误和操作失败，并拒绝多余位置参数。
- 修复 `host list` 与注册表中的过时“无机器级组件”分支；所有已声明宿主都必须有对应组件和测试。
- 七家宿主的项目技能发现通道均完成本机验证，不再登记为未验证假设。

### Removed

- 任务导航的 `allowedOperations` 不再列出没有实现的操作名（`verify_change`、`apply_review_fix`、`report_result`、`report_needs_context`）。这些 id 既没有状态迁移事实，也没有归属 Skill，永远不会成为下一步动作；路由判定结果不变。
- 删除插件、预设中的项目技能副本。旧安装由 `PLUGIN-SKILLS-LEGACY` 提示重装清理。
- 删除 qoder、zcode 和其他宿主的失效适配器路径声明，以及不再使用的技能路径推测和宿主枚举。
- 删除 `install-kimi-hook` 的无效 `--force` 选项；Kimi hook 始终重写自己的托管区块。

## [1.6.0] - 2026-09-20

### Changed

- PR CI 改为运行与发布相同的 `release:check` 门禁，避免只覆盖部分测试。
- 宿主必需集合改由 Host Asset Manifest 派生，删除 Python、JavaScript 和 schema 中的重复宿主枚举。
- README 保护文件说明、spec-check 超时文案和 schema 索引与实际行为对齐。
- 发布和测试报告保留平台跳过项，不把未执行用例记为通过。

### Fixed

- 修复 `spec-check` 文本模式对规范声明解析错误伪绿的问题：解析错误与 `unchecked` 同样返回退出码 2，并在文本输出中列出出错的规范文件；`--allow-unchecked` 不豁免解析错误。
- 修复 Unit of Work 冲突补偿的两处丢失：回滚会恢复内容为 `{}` 的已删文件，也会把"写入前并不存在"的新文件还原为不存在。
- 修复任务创建重复使用已有目录、失败后留下半成品的问题：创建拒绝任何已存在的任务目录，中途失败只清理本次写入的文件与空目录，同 slug 可以重试。
- 修复 OpenCode 插件绑定运行上下文时两次写入不原子导致的半绑定：会话记录与上下文绑定在同一组锁下定稿，第二次写入失败会撤销已落盘的第一次。
- 修复运行上下文的 `initialize`、`bind`、`close` 在外部回滚后重试被旧记录卡住的问题：每次尝试使用独立操作 id，重试会真正改写文件，正常幂等重放与冲突诊断不变。
- 修复 Codex 插件卸载在 CLI 解绑失败时删除 marketplace 与缓存的问题：现在保留现场并打印可重试的手工步骤。
- 修复 Qoder 插件把"只有载荷、没有注册"的安装当成已安装的问题：判定同时要求注册表条目与启用标记，缺失时自动补齐。
- 修复根目录 `.zcodeignore` 未被忽略而阻塞发布干净工作树门禁和任务复核的问题。
- 修复状态文件含非法 UTF-8 时读取崩溃的问题：现在返回空结果、保留原文件并输出诊断。
- 修复 unittest 收集不到模块级测试函数的问题，并增加测试收集守卫。
- 修复 Windows 专属测试文件在顶层退出时被记为通过的问题；现在明确显示跳过原因。
- 修复宿主适配测试中的恒真断言。
- 修复 JavaScript 文件在 Windows 全新检出后使用 CRLF、导致 shebang 断言失败的问题。
- 补齐 DSH workflow-state 插件的刷新事件、section 注册、降级和工具透传测试。

### Removed

- 删除无调用的技能路径链、孤儿异常处理、恒空校验器和其它只由测试触发的死代码。

## [1.5.0] - 2026-09-18

### Added

- 发布脚本新增 `--no-publish`，可完成版本、提交和 tag 后交给 CI 执行 npm 发布。
- Codex、OpenCode 和 DSH 增加编辑期规范检查，违规以单行提示返回，不阻断编辑动作。
- DSH 预设写入版本标记；doctor 可报告 `PRESET-UNKNOWN-VERSION` 和 `PRESET-STALE`。
- 修复上下文后补齐 MCP 注册、运行帮助和相关文档入口。

### Fixed

- 修复 PostToolUse 对 `file_path`、`filePath`、`path` 和 Codex 补丁文本的路径提取差异。
- 修复 DSH 预设升级后没有提示的问题。
- 修复无可信会话身份时 fallback 文案无法指导用户重新绑定的问题。

## [1.4.0] - 2026-09-14

### Fixed

- 修复多窗口下未绑定 hook 会话可能读取其它会话任务的问题。激活命令会认领当前会话；只有一个可信绑定时才允许回退跟随，多个绑定时保持 `no_task` 并提示重新绑定。
- MCP 任务查询不再用不可信的进程级身份冒认任务。
- 工作流状态新增 `session` 属性，供 hook 与后续 CLI 调用共享会话身份。

## [1.3.0] - 2026-09-09

### Changed

- 状态注入逻辑收拢到 Python 单一入口，宿主适配层只负责事件和传输差异。
- `task_scope`、`task_specs` 增加与 MCP 同源的 CLI 查询命令；MCP 主要作为无 hook 宿主的只读查询通道。
- ZCode 注入脚本缩减为传输层，编辑期检查使用节流和统一预算。
- 子代理无法收到宿主编辑期反馈时，改为在报告前显式运行 `spec-check` 自检。

### Fixed

- 修复 Windows 下带引号命令、中文输出解码和命令缺失分类不一致的问题。
- 修复未绑定 ZCode 会话的编辑期 scope/spec 警告完全静默。
- 修复 scope 使用绝对路径比较导致所有编辑都被误报越界。
- 修复缺少 git 时任务启动崩溃；无 HEAD 时降级为 working-tree 状态。

## [1.2.0] - 2026-09-08

### Added

- 新增规范挂命令：项目规范可在 frontmatter 中声明 `cmd`、`files`、`timeout` 和 `when`。
- 新增 `./.cowork-flow/run spec-check`，结果分为 `pass`、`violation` 和 `unchecked`；后两者阻断完成。
- 编辑期检查提供单行提示，收口检查把结果写入任务记录。
- doctor 报告无法解析或无法执行的规范检查声明。

## [1.1.4] - 2026-08-31

### Fixed

- 修复 Windows 下 Node 直接启动 npm `.cmd` shim 时出现 `EINVAL` 的问题；`mcp-state` 改用与 npm 一致的 shell 启动方式。

## [1.1.3] - 2026-08-30

> 1.1.1 和 1.1.2 的变更首次随 1.1.3 一起发布；本版本同时承载前两个版本的代码。

### Changed

- scope 规则和阶段契约预算移入 `spec/runtime/scope-rules.json`，Python 与 JavaScript 运行时共用同一份数据。
- 缺少或损坏规则文件时使用与原行为一致的默认值。

### Fixed

- 修复 delegated 注入在非项目目录中因空项目根崩溃。
- 修复 Windows 缺少 git 时任务上下文收集失败。
- 修复 scope 预算裁剪少保留一个换行，导致闭标签不完整的问题。

## [1.1.2] - 2026-08-30

### Added

- 任务进入实现阶段时记录固定 review 基线。审查范围合并基线后的提交和当前 working tree，避免中途提交让越界文件从检查中消失。
- 无 git、HEAD 或基线时降级为 working-tree 状态，不产生虚假阻断。

## [1.1.1] - 2026-08-30

### Fixed

- 修复带 `./` 前缀的 scope 条目导致 ZCode/OpenCode hook 崩溃。
- 修复超预算阶段契约产生未闭合文本的问题。
- MCP 拒绝仓库外路径和没有工具调用的 JSON-RPC 通知。
- JavaScript 与 Python 使用一致的 scope 过滤规则，delegated 子代理只读呈现父任务范围。
- 非法 UTF-8 锚点不再让整个阶段契约静默消失。
- review 缺少 `implement.jsonl` 时明确阻断。

## [1.1.0] - 2026-08-29

> npm 上的 1.0.0 包早于最终发版修复；下文阶段 0-3 的完整能力从 1.1.0 起实际发布。

### Added

- 新增统一的工作流状态注入、contract digest 和 decision anchor 摘要。
- 新增 `run state [task] --json` 事实视图，汇总任务、计划、会话和规范绑定。
- 新增 executor 归属、冲突阻断、显式接管和无会话 CI 启动。
- 新增子代理 evidence 记录。
- 新增无第三方依赖的只读 MCP 服务，提供 `task_state` 和 `task_list`。
- 新增全局 `cowork-flow mcp-state` 透传入口。

## [1.0.0] - 2026-08-26

首个稳定主线版本，冻结任务状态、会话身份和宿主注入协议。

### Added

- 支持 Codex、OpenCode、Claude Code、DSH 和 ZCode 五个宿主。
- 新增 `<workflow-state>`、contract digest 和状态快照协议。
- 新增任务事实视图、executor 归属、stage contract、MCP 只读查询和全局 MCP 入口。
- 新增计划绑定、任务树、Party Mode 与 Batch 基础能力。
- 新增发布脚本、跨平台测试和主机资产同步。

### Changed

- 会话绑定区分宿主 session id、显式 context id 和进程 fallback；不可信身份不再自动跟随其它会话。
- 状态转换与运行快照在同一事务单元内提交。

## [0.0.52] - 2026-08-26

### Added

- 接入 ZCode 宿主、插件、hook、会话身份和项目技能。
- 生命周期命令后立即刷新工作流状态，无需等待下一条用户消息。
- doctor 新增会话卫生检查。

### Fixed

- 全局回退不再选择失效绑定或子代理会话。
- contract digest 在会话开始时输出完整内容，后续消息只输出指纹。

## [0.0.51] - 2026-08-15

### Added

- 接入 DeepSeek Harness 预设和 workflow-state hook。
- 任务可绑定计划，归档时保留计划快照。
- CI 在 Ubuntu 和 Windows 上运行 Python 测试。

### Fixed

- 统一平台和 ZCode 会话上下文解析。
- Windows 通过 cmd wrapper 启动批处理和 hook。

## [0.0.50] - 2026-08-10

### Changed

- task-review 明确把用户绑定的 spec 视为必须完成的检查项。

## [0.0.49] - 2026-08-08

### Added

- 新增源码仓库 `source-refresh` 命令。
- 计划绑定 lite 在高风险任务启动前检查计划和 decision anchor。

### Changed

- 拆分任务上下文服务，精简 lifecycle CLI 适配层。
- 状态恢复、host manifest、Batch 和 Party Mode 使用明确模块边界。
- CI 增加 Windows 发布信心门禁。

## [0.0.48] - 2026-08-05

### Changed

- 拆分 lifecycle 命令并收紧路由和 runtime context 恢复规则。
- 移除旧 changes control plane 和 session journal 工作流。
- Party Mode 使用独立 board 存储；Batch 增加事实检查和 host action 结果校验。
- 新增 host capability matrix、集中同步策略和健康检查输出。
- README 增加任务流程图与故障排查说明。

## [0.0.47] - 2026-08-05

此版本未保留本地条目正文，详情见 [GitHub Release](https://github.com/fishlikewater/cowork-flow/releases/tag/v0.0.47)。

[Unreleased]: https://github.com/fishlikewater/cowork-flow/compare/v1.7.3...HEAD
[1.7.3]: https://github.com/fishlikewater/cowork-flow/compare/v1.7.2...v1.7.3
[1.7.2]: https://github.com/fishlikewater/cowork-flow/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/fishlikewater/cowork-flow/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.1.4...v1.2.0
[1.1.4]: https://github.com/fishlikewater/cowork-flow/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/fishlikewater/cowork-flow/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/fishlikewater/cowork-flow/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/fishlikewater/cowork-flow/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/fishlikewater/cowork-flow/compare/v0.0.52...v1.0.0
[0.0.52]: https://github.com/fishlikewater/cowork-flow/compare/v0.0.51...v0.0.52
[0.0.51]: https://github.com/fishlikewater/cowork-flow/compare/v0.0.50...v0.0.51
[0.0.50]: https://github.com/fishlikewater/cowork-flow/compare/v0.0.49...v0.0.50
[0.0.49]: https://github.com/fishlikewater/cowork-flow/compare/v0.0.48...v0.0.49
[0.0.48]: https://github.com/fishlikewater/cowork-flow/compare/v0.0.47...v0.0.48
[0.0.47]: https://github.com/fishlikewater/cowork-flow/releases/tag/v0.0.47
