# Changelog

## Unreleased

### CLI 命令面改为名词分组（`cwf` 短名 + 命令注册表）

- **11 个平铺命令收进 5 个名词组**：`project init` / `project sync`、`host add` / `host remove` / `host list`、`self update`、`dev refresh`、`mcp serve`。主二进制新增 `cwf`，与 `cowork-flow` 是同一入口（`package.json` 的 `bin` 两键同值）。帮助文本由 `src/commands/registry.js` 的命令注册表生成，`src/cli.js` 只剩解析与派发——此前帮助常量与 `if (command === ...)` 链是第二份事实源，已经漂移（帮助里写死 3 个平台，实际 7 个）。
- **旧名全部保留，分两类**：`init` / `sync` / `mcp-state` 是**永久别名**（`mcp-state` 已写进大量 MCP 客户端配置，仓库外固化，硬改名会让已注册客户端静默失联）；其余 8 个是 **shim**，stdout 不变，只在 stderr 多一行迁移提示，两个 minor 版本后移除。shim 只做 argv 前缀重写（`install-dsh-hook` → `host add dsh --component hook`），不做参数改写之外的事。
- **新增 `host add` / `host remove` / `host list`**：`host add <host> [--component <name>]` 按宿主的机器级组件表派发到对应安装器（codex / zcode / qoder 只有 `plugin`；dsh 有 `preset` 与 `hook`，默认 `preset`；kimi-code 只有 `hook`）；`host remove <host>` 是幂等卸载；`host list [--json]` 输出声明宿主、机器级组件与本项目是否选中（看 adapter 是否落盘）。`host add --uninstall` 与 `host remove` 同路径，保留只为让旧名能被原样重写。
- **补齐两条卸载路径**：`install-zcode-plugin --uninstall`（删缓存目录与 per-marketplace 缓存根、两个 marketplace 副本目录、`known_marketplaces.json` 里属于 cowork-flow 的条目，不动用户自己的 marketplace）与 `install-dsh-preset --uninstall`（删预设目录，不动 `.agent-presets/` 下别人的预设）。两条都幂等，未安装时报明并成功。dsh 的 hook 组件沿用既有 `--uninstall` 语义：移除托管行，插件文件需再加 `--force`（README 已写明）；qoder / codex / kimi 各自的卸载语义不变。
- **退出码契约 0/1/2**：`2` = 用法错误（未知命令、未知旗标、多余的位置参数、缺参数、未知宿主/组件/平台），`1` = 操作失败，`0` = 成功。所有命令的旗标解析都改走同一个 `src/lib/cli-flags.js`（无新依赖），因此"叫错了"和"做失败了"在全命令面一致：六个安装器此前用 `args.includes(...)` 扫描已知旗标、静默忽略其余（`--forcee` 会让命令"照常执行"，现在报 `Unknown option`）；`init` / `sync` / `dev refresh` 此前是"最后一个位置参数胜出"（`init a b` 会静默以 `b` 为目标），现在报 `Unexpected argument`；`self update` 的未知参数从 `Unknown update option` 改为统一的 `Unknown option`。
- **全层 `--help`**：`cwf --help`、`cwf <组> --help`、`cwf <组> <命令> --help`、`cwf help [路径]` 都打印该层用法且不执行命令；`--help` 优先于其它旗标。裸组名（`cwf host`）打印该组命令。
- **新增门禁** `test/cli-registry.test.js`：注册表里每个命令/别名都能解析；帮助由注册表渲染（改注册表即改帮助）；宿主的机器级组件表与 `host-assets.json` **双向绑定**（组件表只出现在声明宿主上，"有 `payload` 的宿主"与"有 `plugin` 组件的宿主"必须是同一集合）；`host add` 的帮助覆盖所有安装器声明的旗标；仓库内不再出现指向 shim 的提示（两个托管块标记串按"wire format"豁免，并有独立用例钉住它们逐字节未变——它们已写进用户机器文件，改了会让既有安装的托管块不再被识别）。
- **全仓命令名同步**：doctor 的 20 余条 `commandHint`、README 命令表与各宿主小节、`spec/contracts/fact-layer-access.md` 的 MCP 注册矩阵、`presets/dsh/agent.cordis.yml` 注释、三份 bootstrap 技能正文（保持逐字节一致）、`template/.dsh/README.md`、npm scripts（`source:refresh` 改用 `dev refresh`）。`npx cowork-flow <子命令>` 保留包名形式：`npx cwf` 会被 npx 当成另一个包名。
- **不改的东西**：工作流内核语义与门禁、技能正文的协作规则、`./.cowork-flow/run mcp-state`（项目级 runner 的键，与 npm CLI 命名空间无关）、两个托管块标记串、各命令的业务行为（目录布局、幂等策略、`--dry-run` 输出行）。

### 宿主载荷声明与适配统一

- **`host-assets.json` 新增 `payload` 描述符**：每个平台条目声明"这个宿主有没有机器级插件载荷、载荷在包内哪里、清单叫什么"（codex / zcode / qoder 为 `{source, manifest}`，其余四家为 `null`）。此前这些事实只散落在三个安装器与 doctor 里，新增宿主要动哪些地方只能通读代码。描述符**不放机器级安装路径**（`$ZCODE_HOME/...`、注册表名、marker 名）：这个文件随 init 交付进项目，项目侧解析不了 npm 包与用户 home 的布局。schema、JS `PLATFORM_KEYS`、Python `PLATFORM_KEYS` 三处校验面与全部 fixture 同步；既有的"字段一致性门禁"先红后绿，确认新字段被覆盖。
- **`payload` 必填键的两侧语义对齐**：显式 `null` 的 `manifest` 在 JS 与 Python 都按"非法值"拒绝（只有缺键才表示"无 manifest"）——否则一份清单会被 doctor 判合法、却让所有 JS 命令在导入期崩溃。
- **三个插件安装器改读描述符**：`install-{codex,zcode,qoder}-plugin` 不再硬编码 `presets/<host>` 与清单名，改由 `src/lib/plugin-payload.js` 的 `pluginPayload(host)` 解析；新增门禁断言三个安装器源码里不再出现 `presets` 路径字面量（负向验证：还原旧写法即红）。
- **安装期版本盖章对齐**：此前只有 qoder 与 codex 给已装载荷的清单盖章版本，zcode 不盖——从 checkout 安装的 zcode 载荷会保留源清单里的发布版本号。现在三家统一走 `stampPayloadManifest()`（保留键顺序、两空格缩进、尾换行，与 `scripts/release.sh` 同形，写临时文件后 rename）。`test/plugin-payload.test.js` 覆盖版本改写、键序、字节形状与无 `.tmp` 残留，并断言三个安装器确实调用共享助手——只靠"已装版本等于包版本"是假通过，因为源清单版本本来就等于包版本。
- **doctor 改读描述符**：qoder 与 codex 插件检查的清单相对路径取自声明，不再硬编码；声明读不到时退回原字面量（`doctor` 的告警码集合不变）。两条路径各有测试，负向验证：把 doctor 改回硬编码即红。
- **失效路径清理**：删除 `src/lib/platforms.js` 的三个零消费者导出与 `src/lib/host-assets.js` 的 `isKnownPlatformAsset`；删除 `install-kimi-hook` 解析后从不使用的 `--force`（README、CLI 帮助文本与 doctor 的修复提示同步）；`.gitattributes` 把 POSIX 运行器行尾钉到交付副本——`.cowork-flow/run` 这个含 `/` 的模式被锚定在仓库根，只匹配 gitignored 的自实例副本，`template/.cowork-flow/run` 一直是 `eol: unspecified`，Windows checkout 会materialize 成 CRLF 并被 `init` 写进用户项目；两个工作树副本已转为纯 LF，并删掉重复的 `*.toml` 行。
- **文档与残留**：`spec/runtime/index.md` 的 `host-assets.json` 职责补上 `payload` 声明；`spec/contracts/index.md` 补齐 4 份现存合同（`context-injection` / `decision-anchor` / `error-output-as-data` / `fact-layer-access`）；`config.yaml` 的 hook 示例不再指向并不存在的 `scripts/on_task_event.py`，改为注明"用你自己的脚本路径"；`obsoleteFiles` 去重（123 → 121）；删除零引用的一次性样本 `test-rules-demo/` 与空目录 `data/`；README 的 Host 分发表补上漏掉的 Qoder。
- 升级动作：升级 cowork-flow 后重跑 `install-<host>-plugin --force` 即让已装载荷带上盖章版本；本批不改任何命令名、安装布局与退出码。

### 插件身份元数据单一来源（作者名订正 + 三家清单字段补齐）

- **新增 `presets/plugin-meta.json`（唯一身份来源）与 `src/lib/plugin-metadata.js`（投影模块）**：displayName、简介/长简介、作者、homepage、repository、license、keywords、category 只写一份，投影出 codex / zcode / qoder 三份 `plugin.json` 与两家 marketplace 条目字段。此前同样的信息散落在三份清单、两个安装器与 `package.json` 里，改一处就会漂移。
- **清单一致性由测试守，不靠生成脚本**：`test/plugin-metadata.test.js` 断言三份清单**逐字节等于**投影结果（手改清单即红）。实测：把 codex 清单的 `interface.displayName` 改成 `CoworkFlow` 会让门禁由 6 passed 变 4 passed / 2 failed，还原即绿。`scripts/release.sh` 盖章版本用 `JSON.parse` + `JSON.stringify(j, null, 2) + '\n'`，与投影序列化同形且保留键顺序，所以发布后门禁仍成立。
- **作者名错拼订正**：作者名此前在两处被写错（`LICENSE` 与 `install-zcode-plugin` 硬编码的 marketplace 条目作者兜底），现统一为 `fishlikewater`。新增仓库级错拼门禁扫描 `git ls-files`；索引覆盖不到身份源文件时（源码导出没有自己的 `.git`，或新文件尚未 `git add`）回退到 npm 白名单遍历，避免"看起来跑过、实际什么都没扫"。实测该门禁实现中途即为红，报出这两处遗留点，修掉才转绿。
- **codex 清单补 `interface`**（displayName / shortDescription / longDescription / developerName / category / websiteURL），marketplace 条目补 `policy: {installation: "AVAILABLE", authentication: "ON_INSTALL"}` 与 `category`，marketplace 顶层补 `interface.displayName`。策略枚举取自 codex 自身的插件编写指南，且本机重装后 `codex plugin list --json` 回读出 `installPolicy: "AVAILABLE"` / `authPolicy: "ON_INSTALL"`——是宿主接受并回写的值，不是猜的。
- **zcode marketplace 条目补 `displayName` / `category` / `author{name,url}` / `license`**（此前只有英文 description 与错拼作者名）；qoder 清单补 `displayName` / `homepage` / `repository` / `keywords` / `author{name,email,url}`。qoder 的清单 schema 没有 `icon`/`logo` 键，不写死键——图标按各宿主真实支持的字段接（见后续批次）。
- **`package.json` 补 `author` / `keywords` / `repository` / `bugs` / `homepage`**，与元数据源逐项相等；`LICENSE` 年份作者订正。新增 `test/plugin-metadata.test.js` 到 `test:fast`，`test/package.test.js` 断言 `presets/plugin-meta.json` 进入 npm 包内容。
- 本批不改任何命令行为与载荷内容：`install-codex-plugin` / `install-zcode-plugin` 的输出与安装位置不变，只是清单字段改由元数据源生成。

### Codex 插件接入（只带引导技能，agents 与 hook 留在项目级）

- **新增 `cowork-flow install-codex-plugin [--dry-run] [--force] [--uninstall]`**：把 `presets/codex/` 写进稳定 marketplace 源 `$CODEX_HOME/plugins/marketplaces/cowork-flow-local/`（`.agents/plugins/marketplace.json` + `plugins/cowork-flow/`），再委托官方 CLI 执行 `codex plugin marketplace add` + `codex plugin add cowork-flow@cowork-flow-local` 完成注册与启用。**不手写 `config.toml`**：注册状态属于 codex，安装器只生成纯 JSON + 目录拷贝的源；CLI 探测顺序 `COWORK_FLOW_CODEX` → `PATH` → `<CODEX_HOME>/plugins/.plugin-appserver/codex(.exe)`，都没找到时仍备好源目录并打印两条手动命令；npm 全局安装的 `codex.cmd` 走 shell 调用时按 token 加引号（用户目录含空格也可用），真实可执行文件不走 shell。已注册的 marketplace 根与安装器计算值比较时做路径归一化（剥 `\\?\` 前缀、大小写不敏感）——codex 会回写自己规范化的拼写，原始字符串比较会让每次重跑都误报冲突。`--uninstall` 走 `plugin remove` + `marketplace remove`（未注册时该命令返回 1，按幂等卸载容忍）再删源目录。
- **agents 不可插件化（运行时实证）**：探针任务 `09-23-codex-plugin-probe` 用双向坏文件对照证明 Codex 不解析插件根 `agents/`——同一份未闭合 TOML 放项目级 `.codex/agents/` 被 `codex doctor --json` 报 `Ignoring malformed agent role definition`，放插件根则零报错；辅证是官方文档布局与概念页的组件清单均无 agents、官方插件实例无 `agents/` 目录、官方脚手架 `create_basic_plugin.py` 无 `--with-agents`。因此三个 fixed subagent 与 hook 保持项目级交付，插件只带技能。
- **载荷**：`presets/codex/.codex-plugin/plugin.json`（`"skills": "./skills/"`）+ `presets/codex/skills/cowork-flow-bootstrap/SKILL.md`，与 zcode / qoder 载荷字节一致（三家 sha256 相同）。`scripts/release.sh` 的 `PLUGIN_MANIFEST_FILES` 加入 codex 清单，`test/package.test.js` 的宿主清单表同步覆盖版本同步与发布脚本覆盖。
- **doctor 新增 `check_codex_plugin`**：`PLUGIN-NOT-INSTALLED`（项目声明 codex 宿主但 `config.toml` 没有 cowork-flow marketplace）、`PLUGIN-PAYLOAD-MISSING`（注册的源目录缺 `.codex-plugin/plugin.json`）、`PLUGIN-DISABLED`（缺 `[plugins."cowork-flow@cowork-flow-local"] enabled = true`），全部 warning 不进 errors；`_machine_plugin_payload` 增加 codex 分支，载荷仍带与项目同名技能副本时复用 `PLUGIN-SKILLS-LEGACY`。
- **受限 TOML 解析**：`_codex_config_sections` 只读 `[marketplaces.cowork-flow-local]` 与 `[plugins."cowork-flow@cowork-flow-local"]` 两个平坦段（引号可选、其余 section 与键一律不读）。CI 的 Python 下限是 3.10（`.github/workflows/ci.yml`），没有 `tomllib`，为两格声明引入 TOML 依赖不划算；这是本任务 plan 的 Deviation Condition 分支，已记录在任务 decision-anchor。
- **声明订正**：`host-assets.json` 里 codex 的 `skillDiscovery` 证据由 `assumed:` 升为 `verified:`（探针任务的 `codex debug prompt-input` skill roots 表列出 `<cwd>/.agents/skills`）；`tests/test_host_skills_gate.py` 的 `ASSUMED_DISCOVERY` 门禁同步移除 codex 条目，README 技能分发表随之拆分。
- **幂等性实测**（决定安装器策略）：`marketplace add` 重复执行返回 0（"already added"）；`plugin add` 重复执行返回 0；源目录版本从 0.0.1 升到 0.0.2 后再次 `plugin add` 会物化新版本并删除旧版本目录（`ls` 只剩 `0.0.2`）；`plugin list --json -m <未注册的 marketplace>` 返回空列表且退出码 0。安装器据此按"注册状态 + 已装版本"决定是否重跑 add。
- 升级动作：`cowork-flow install-codex-plugin` 一次即完成接入；升级 cowork-flow 后重跑同一命令（版本变化会自动重物化），要强制刷新加 `--force`。

### 插件携带 bootstrap 引导技能（zcode / qoder）

- **两家插件载荷各带一个新名技能**：`presets/{zcode,qoder}/skills/cowork-flow-bootstrap/SKILL.md`，两份 `plugin.json` 声明 `"skills": "skills"`。该技能只在仓库没有 `.cowork-flow/` 时引导 `npx cowork-flow init`，检测到项目 runtime 时退让给项目级 `cowork-flow` 技能；它不带 `manifest.json`，不进入 runtime 的 action / command / context 路由，也不参与技能副本 parity。项目级 16 个技能的交付、`skillReadRoot`、init 分发与 fixed subagent 的技能路径全部不变。
- **载荷技能名必须与项目技能名零交集**：ZCode 与 Qoder 都按技能文件 realpath 去重、不按技能名，同名副本会双份进入技能列表；两家插件测试新增门禁——遍历载荷技能目录名逐个断言 `template/skills/<name>` 不存在（负向验证：把项目技能塞回载荷即红）。
- **doctor 语义收窄**：`PLUGIN-SKILLS-LEGACY` 从"载荷有 `skills/` 即告警"改为"载荷含**与项目同名**的技能副本才告警"，消息列出副本名；只带 bootstrap 的载荷静默（新增用例覆盖）。`SKILL-READROOT-MISSING` / `SKILL-DISCOVERY-GATED` 不变。
- **qoder 清单字段实证**：Qoder 0.3.4 的 `@qoder-ai/qoder-agent-sdk` worker bundle 里，插件清单 schema 声明 `skills` 字段（`qoder-worker-runtime.obf.mjs` 的 `nza` shape，类型为路径或路径数组），组件发现另有 `skills/` 目录约定；ZCode 3.14.3 的 `SkillService.list` 同样支持"manifest 声明或 `<pluginRoot>/skills` 回退"。
- 升级动作：重跑 `cowork-flow install-zcode-plugin --force` / `install-qoder-plugin --force` 即带上引导技能。

### 交付树字节码隔离（测试与技能命令不再写 __pycache__）

- 交付树（`template/**`、`presets/**`）此前持续被 Python 字节码污染，累积了 16 个 `__pycache__` 目录 / 90 个 `.pyc`。两条来源：`python -m pytest`（本地直跑与 CI 的 Python 段）无任何防护；技能命令（如 `doctor`）在源 checkout 里解析到 `template/.cowork-flow/scripts` 并 import 它。`scripts/template-test-runner.js` 的 `PYTHONDONTWRITEBYTECODE` 只覆盖 npm 入口。
- 测试侧：`tests/__init__.py`（pytest 与 unittest 都会先导入的包）把字节码前缀指到 gitignored 的 `.tmp/pycache`——本进程设 `sys.pycache_prefix`，并通过 `PYTHONPYCACHEPREFIX` 传给子进程；Node 测试由 `test/helpers/bytecode-isolation.js` 做同一件事（进程级环境变量，覆盖它 spawn 的 hook/python 子进程）。只设解释器内变量不够：子进程不继承，实测交付树仍被写入 89 项。
- 运行时侧：技能脚本子进程统一关掉字节码写入——`runtime_pythonpath_env(cache_bytecode=False)` 由 `run.py` 的 `run_skill_script` 与批处理入口 `batch_mode.py` 共用（两条 spawn 路径由独立检查各发现一次）。技能命令是低频入口，缓存收益可忽略（实测 `doctor` 冷/热启动差约 90ms），而它留下的 `__pycache__` 会落在技能脚本解析到的 runtime——源 checkout 里就是交付树。高频命令（`task`、`spec-check`、`mcp-state`）仍走默认分支，缓存行为不变。
- 门禁：`tests/test_no_legacy_template_paths.py` 新增断言，`template/`、`presets/` 下出现 `__pycache__` 或 `*.pyc` 即失败（负向验证：放回一个 `.pyc` 变红）；现存污染已清理。
- README「仓库结构」补仓库自身布局，以及 `node --test` 收集 `test/**` 全部 `.js`（含辅助模块）、Python 侧按 pytest `test_*.py` / unittest `test*.py` 收集的目录约定。

### 技能单一来源：移除全部机器级技能副本

- **三处载荷不再交付技能**：`install-zcode-plugin` / `install-qoder-plugin` / `install-dsh-preset` 删除把 `template/skills` 拷进载荷的路径（含 dry-run 输出行与存在性检查），两份 `plugin.json` 去掉 `skills` 组件，dsh 的 `agent.cordis.yml` 移除 `skill-filesystem` 的 `customSkillDirs`（组件行保留——它提供按 rank 的工作区发现：`<projectRoot>/.dsh/skills` 100、`<projectRoot>/.agents/skills` 200、用户根 400/500，依据 `@deepseek-ai/dsh-skill-filesystem` 的默认根表），`preset.yml` 描述同步订正。技能自此只由项目级 `init` / `sync` 交付。
- **动机（实测）**：ZCode 按技能文件 realpath 去重、**不按技能名**，项目 `.agents/skills` 与插件载荷 `skills/` 的同名技能会并列进入技能列表，并在 `buildPromptContext` 按名激活时**双份注入正文**；dsh 的技能注册表则按名与 scope 分层遮蔽（"最近层直接赢得重名"、"项目提供方可覆盖运行时技能"），preset 副本只作未 init 项目的兜底。技能与项目 runtime 强耦合（16 个技能中 12 个正文引用 `./.cowork-flow/run ...` / `COWORK_FLOW_*` / `.cowork-flow/spec`），故机器级不能承担权威来源。
- **machine discovery 语义收口**：zcode 的 `plugin:skills` 条目删除后该语义零消费者，按"不留死代码"纪律一并删除——schema 的 `skillDiscoveryEntry` 收敛为"仓库内路径 + 必填 `path`"，Python / JS 校验面同步去掉 `channel` 与 machine 分支，坏声明负向用例覆盖 machine scope 与 `channel` 字段（均被拒）。
- **doctor 迁移提示**：`check_skill_delivery` 的 `PLUGIN-SKILLS-STALE`（版本偏斜）改为 `PLUGIN-SKILLS-LEGACY`——检测到载荷仍带 `skills/` 即提示 `cowork-flow install-<host>-plugin --force`（重装先 `rm -rf` 再拷，顺带清理），不再比较版本；`SKILL-READROOT-MISSING` 与 `SKILL-DISCOVERY-GATED` 语义不变。
- **升级动作**：已装旧插件的机器重跑 `cowork-flow install-zcode-plugin --force` / `install-qoder-plugin --force` 即清掉载荷里的技能副本（doctor 以 `PLUGIN-SKILLS-LEGACY` 报出时按提示执行）；dsh 预设不随 npm / `sync` 更新，且预设版本标记相同时 doctor 不会告警，请直接重跑 `cowork-flow install-dsh-preset --force`。
- 已知代价（有意接受）：未 `init` 的项目不再有任何 cowork-flow 技能（后由插件引导技能 `cowork-flow-bootstrap` 部分补上，见本文件 Unreleased 顶部条目）；qoder 在未受信任目录中看不到技能（其发现门禁未变）。

### 宿主声明基址统一、技能候选根派生与 zcode 技能根订正

- **适配器路径声明**：`adapter.yaml` 的 `dispatch.*Path` 统一为"项目相对 + 存在性守卫"——删除 qoder 的 `presets/qoder/*`（包内相对，且 `skillsPath`/`commandsPath` 指向包内不存在的目录）、zcode 的 `.zcode/agents` 与 `.zcode/.zcode-plugin/plugin.json`（项目与包内都不存在），以及与 `host-assets.json` 的 `skillReadRoot` 重复的 `skillsPath`（claude-code / dsh / kimi-code）。新增守卫测试逐项断言 `template/<path>` 存在、拒绝 `presets/` 前缀与 `skillsPath` 键（负向验证：塞回旧值即红）。
- **技能候选根**：`skill_roots()` / `_replica_precedence()` 的宿主副本根改由 manifest 的 `skillReadRoot` 按平台顺序去重派生，新增宿主 readRoot 自动纳入（合成 manifest 用例证明）；manifest 不可读时回退旧字面量；对当前 manifest 的派生顺序与旧行为逐项相等（测试钉住）。
- **zcode 技能根订正**：ZCode 3.14.3 宿主 bundle（`app.asar` 的 `out/host/index.js`）实证 `SkillService.list` 枚举 `<workspace>/.zcode/skills` 与 `<workspace>/.agents/skills`（含祖先目录向上探测）、用户级 `~/.zcode/skills` 与 `~/.agents/skills`（仅桌面运行时）、插件载荷的 `skills` 组件（manifest 声明或 `<pluginRoot>/skills` 回退），且整个 bundle 内 `.cowork-flow` 0 命中——原 readRoot `.cowork-flow/skills` 属"声明已交付、宿主不可见"。readRoot 改为共享的 `.agents/skills`，discovery 补 project 通道（`.zcode/skills` 的同名优先与"我们不交付"记入证据），三个 fixed subagent 正文同步改址；`assetPrefixes` 去掉 `.cowork-flow/skills/`，`obsoleteFiles` 增加 16 条迁移项（旧项目 `sync` 时清理，实测删除且保留非 cowork-flow 目录）。
- 门禁与分发：`tests/test_host_skills_gate.py` 删除 zcode 的 machine-scope 白名单例外（每个宿主的正文都必须指向自己的 readRoot）；`--platform zcode` 产出 `.agents/skills`（16 技能）且不再产出 `.cowork-flow/skills`；source checkout 的 live replica 由 3 份降为 2 份。

### 技能声明模型（readRoot + discovery）与防复发门禁

- `host-assets.json` 的平台条目把含混的 `skillTarget` 拆成 `skillReadRoot`（我们读取的仓库内路径）与 `skillDiscovery[]`（宿主原生发现通道，带 `scope` / `gates` / `evidence`）。JSON schema、Python 与 JS 三个校验面同步，缺证据、scope 非法、project 条目与 `skillReadRoot` 不一致、machine 条目缺 `channel`、空 `skillDiscovery` 一律被拒。
- **qoder 修正**：`skillReadRoot` 从 `.cowork-flow/skills` 改为 `.agents/skills`——后者才是 Qoder 自己扫描的路径（`SkillCommandHandler.enumerate` 第 6 项，`loadFromAgentsDirectory` 默认 `true`；本机 `~/.agents/skills` 的技能在会话中可见可证）。因此读取与发现同址、项目里只有一份副本，三个 fixed subagent 的技能路径同步改址。旧值在宿主 SDK 里 0 命中，属于"声明看起来已交付、宿主侧零发现"。
- `_skill_path` 不再用 `.claude/skills` → `.agents/skills` → `.cowork-flow/skills` 的硬编码启发式：改由 manifest 驱动，先取活动宿主（`COWORK_FLOW_HOST` 或宿主 session env）的 `skillReadRoot`，否则取 manifest 顺序中首个真实存在的根。`inject.py` 渲染前把 `--host` 写进 `COWORK_FLOW_HOST`。
- 文档订正：README 技能分发表改为"读取根 / 宿主原生发现"两列并说明 `verified:` / `assumed:` 证据约定；Qoder 小节改为**双通道**（项目级 `.agents/skills` 为主、插件 `skills/` 为 bootstrap），删除"插件是模型可见技能层唯一来源"的表述。
- 防复发：`tests/test_host_skills_gate.py` 断言每个宿主 fixed subagent 正文的技能路径必须落在该宿主 `skillReadRoot` 下，并逐项登记 `assumed:` 声明；`tests/test_host_asset_manifest.py` 新增 schema/校验器/数据三面键集一致断言与六个坏声明用例。
- doctor 新增 `check_skill_delivery`（warning 级，不进 errors）：`SKILL-READROOT-MISSING`（选中平台声明的读取根不在项目里）、`PLUGIN-SKILLS-STALE`（机器级插件载荷的 `skills/` 副本版本与项目 `.cowork-flow/.version` 偏斜；有专属插件检查的宿主如 qoder 由 `PLUGIN-STALE` 承担，不重复报）、`SKILL-DISCOVERY-GATED`（发现通道带宿主侧门禁，如 qoder 的信任目录 / 重启提醒）。

### 宿主插件载荷落点统一（zcode 迁出模板树）

- `template/.zcode/` → `presets/zcode/`：机器级插件载荷统一落在 `presets/<host>/`（dsh、kimi-code hook、qoder 已在此），`template/` 只保留会落盘到生成项目的资产。`template/.zcode/` 本就进 `excludedPrefixes`、不进任何生成项目，搬移后 `package.json` 的 `files` 少一条冗余项，release 脚本的两份清单同址。
- 安装等价性实测：搬迁前后各在隔离 `ZCODE_HOME` 执行 `install-zcode-plugin --force`，产物树 226 条 `sha256` 指纹逐行相等（仅 `known_marketplaces.json` 的 `addedAt`/`lastUpdated` 墙钟字段掩码）；1 字节负向对照可被检出。
- 计划外引用面修正：Python 测试用 `ROOT / "template" / ".zcode"` 拼接、README 结构图写作裸 `.zcode/`，字符串 grep 均不可见。前者改为指向真实载荷并升级为可失败的守卫（`presets/zcode` 下出现 `AGENTS.md`/`CLAUDE.md`/`.cowork-flow`/`scaffold` 即红，已负向验证），后者删除并补上此前缺失的 `presets/` 目录树。

### Qoder 宿主适配（插件形态）

- 新增平台 `qoder`：`host-assets.json` 平台条目 + `capabilityMatrix` 行 + `.cowork-flow/adapters/qoder/adapter.yaml`，宿主身份在 `runtime/host_identity.py` 登记一行（prefix `qoder`、adapter `qoder.hooks`、`QODER_SESSION_ID`）。注入信封与 claude-code 同形，因此 `inject.py::_emit` 与 `HostPolicy` 零改动。
- `adapters/host/qoder_policy.py`：Qoder 的 `PostToolUse` 不是可阻断事件，编辑期告警改走 exit 0 + `additionalContext`（claude-code/codex 用 stderr + exit 2）。
- 宿主资产以 Qoder 插件交付：`presets/qoder/`（`.qoder-plugin/plugin.json` + `hooks/hooks.json` + `hooks/inject-context.py` shim + 三个 fixed agent）。`.qoder/` 进入 `excludedPrefixes`，`init`/`sync` 不向项目写任何 Qoder 文件；平台检测改用 `.cowork-flow/adapters/qoder`。shim 按载荷 `cwd` 定位项目根后调用**项目自己的** `.cowork-flow/run`，不在插件缓存里留第二份注入逻辑。
- 新命令 `cowork-flow install-qoder-plugin [--dry-run] [--force] [--uninstall]`：写插件缓存载荷（含安装时拷入的 `skills/` 与戳好的 manifest 版本）、幂等 upsert `plugins/installed_plugins_v2.json`、置 `settings.json` 的 `enabledPlugins`；未知键与他人条目一律保留。
- doctor 新增 `check_qoder_plugin`（warning 级，五态诊断）；契约同步 `context-injection.md` 传输表、`spec-checks.md` 宿主矩阵（编辑期快跑六家）、`fact-layer-access.md` 注册表；README 增补「Qoder（插件形态）」小节与两频次边界。
- `scripts/release.sh` 的插件清单戳版本从「zcode 单文件 if」改为遍历所有随包清单（zcode + qoder）并逐个加入 `git add`；`test/package.test.js` 断言每份清单版本等于包版本、且其路径出现在发布脚本里，防止新宿主清单在发布后与包版本漂移。
- 能力声明按未实测项保持诚实：`stateInjection=plugin`、`runtimeContextBinding=shim`、`sendFollowup/listChildren/cancelChild=shim`、`editScopeWarning=unsupported`；Desktop/IDE 侧支持在文档标 unknown。

## 1.6.0 - 2026-09-20

### 门禁诚实化（收集一致 / 平台 skip / CI 同门禁）

- **收集一致**：`tests/test_agents_managed_block.py` 的两条断言原为模块级函数，`python -m unittest`（发布门禁与 `test:template` 用的收集器）收集不到它们（实测 `Ran 0 tests`），只有 pytest 能看到。现移入 `unittest.TestCase`，并进入 `CORE_TEMPLATE_TEST_MODULES`（core 套件 176 → 178）。新增 `tests/test_test_collection.py` 守卫：`tests/` 下再出现对 unittest 不可见的模块级 `def test_*` 即失败。
- **Windows 静默通过**：`test/dsh-home-patch.test.js` 此前在 win32 顶层 `process.exit(0)`，`node --test` 把整个文件记为**通过文件**（不进 skipped、不进 fail）。现改为 7 个用例带 `{ skip: <具体原因> }`，Windows 上如实计入 skipped。
- **恒真断言**：`tests/test_host_adapters.py` 三处「断言自己刚写死的字面量长度」（`assertEqual(2, len(surfaces))` 等）改为非空断言——不再恒真，也不引入需要同步维护的数字。
- **CI 与发布同门禁**：ubuntu job 不再分步跑 fast / integration / core，合并为一步 `npm run release:check`（与 publish.yml 完全相同的命令，`setup-python` 前置到它之前）；`test/package.test.js` 新增断言锁定该一致性。此前 `test:node:full` 与 `test:template:full` 两层只在发布时首次执行，PR 侧从不运行。

### 宿主必需集合单源化

- 删除 Python `host_manifest.REQUIRED_CAPABILITY_MATRIX_HOSTS` 与 JS 镜像常量：`capabilityMatrix.hosts` 的必需宿主集合改由 manifest 的 `platforms` 派生（`set(platform_ids)` / `new Set([...platformIds])`）。
- 删除 `host-assets.schema.json` 中第三处宿主名枚举——它处于漂移状态（要求 5 家、含 `dsh`、缺 `kimi-code`，而数据是 6 家）。schema 只约束结构，宿主覆盖由运行时按数据校验。
- 新增共享 fixture `tests/fixtures/host-manifest/invalid-missing-matrix-host.json`（平台已声明但矩阵缺条目），Python 与 JS 两侧都拒绝（`capability matrix missing host: codex`），证明常量删除后该规则仍生效。
- `spec/runtime/index.md` 记录派生规则。

### 死代码与文档漂移清理

- 删除仅测试可达的 skill-path 链：`context_discovery` 的 `detect_installed_platforms`（手写 3 宿主）、`SKILL_REPLICA_DIR_BY_PLATFORM`、`skill_root`、`skill_path`，以及 `adapters/cli/task.py` 的三个未调用别名。该链在生产代码零调用，真实契约由 `infra/skill_manifest` 与 manifest 的 `skillTarget` 承担。
- 删除 `infra/paths.py` 中 `return` 之后的孤儿 try 块（引用未定义的 `file_path`，为 2026-08-05 移除 journal 流程时遗留）。
- 删除 `fact_view.STAGE_CONTRACT_STATES`（文件内零引用；活定义在 `workflow_state_hook`）、`lifecycle_checks` 两个零调用的 `*_blockers` 包装、`adapters/review/test_intent` 的恒空校验器 `validate_test_intent` 与三个未被读取的常量，以及断言其返回空的同义用例。
- 文档对齐：README 保护文件描述与 `syncPolicy` 实际一致（两个 spec 例外文件 + `.developer`）；两处 spec-check 文案 3s → 2.5s；`spec/schemas/index.md` 补列 `host-assets.schema.json`；清理指向已 untrack `docs/` 的历史死链。

### DSH 注入接线覆盖

- `presets/dsh/plugins/workflow-state.js` 的 `apply(ctx)` 此前零测试。新增用例覆盖：四个刷新事件的接线、section 注册（name/order）、无缓存时返回空文本、非编辑调用下 `tools/post-execute` 原样透传 downstream、非 cowork-flow 根目录静默降级——全部在 Windows 上真实执行。「刷新替换而非累积」用例按既有惯例在 Windows skip（宿主解释器限制）。

### Windows 检出与行尾契约

- 根因：`presets/kimi-code/hooks/cowork-flow-inject.mjs` 落在 `* text=auto` 下且未被 `.gitattributes` 钉行尾，Windows 全新检出（Git for Windows 默认 `core.autocrlf=true`，与 `windows-latest` 一致）把它写成 CRLF；`install-kimi-hook` 原样拷贝为全局 hook shim，于是 `test/kimi-hook.test.js` 的 `/^#!\/usr\/bin\/env node\n/` 断言失败，`test:fast` → `windows-core` 确定性红。
- 修复：`.gitattributes` 为 `*.js`/`*.mjs` 声明 `text eol=lf`（与已钉的 `.py`/`.md`/`.json` 等一致）；`test/package.test.js` 新增行尾契约断言锁定该声明。
- 为什么只在 Windows CI 可见：开发者工作区与 ubuntu 检出都是 LF，只有 Windows 全新检出是 CRLF。断言保持严格——CRLF shebang 的脚本在 POSIX 上无法直接执行，要修的是检出契约而不是判据。
- 证据：全新检出实测踩中同一断言失败（`test:fast`）；仅把该文件规范化为 LF → 整条 `npm run test:windows:core` exit 0；Node 20.12.0 / 20.20.2 / 24.14.1 结果一致，与 Node 版本无关。

### 净变化

- 运行时代码（`template/.cowork-flow/scripts` + `src`）：**+4 / −114，净 −110 行**；runtime 模块数 80 不变（行尾修复不涉及运行时代码）。
- 本次门禁工作：`e262196` **+365 / −200**（含 2 个新文件 +162 行）、`7fa3f8b` +3 / −2，行尾修复为小改动（行尾声明 + 契约守卫 + 记账）；新增集中在 `tests/` 与 `test/`。**AC-006「净行数 ≤ 0」未达成**——三条口径都是新增大于删除。
- 版本口径参考：自 1.5.0 发版提交 `a4b0bfc` 起，1.6.0 全部提交的净变化由本版本更早的宿主特性主导，不属本次门禁工作。
- 契约指纹：registry 登记的契约文件与 `spec/runtime/host-assets.json` 均未改动，指纹不变。

### 平台差异与远端确认

- Windows 上 `test:node:full` 的 skipped 明细新增 `dsh-home-patch` 的 7 条；这些用例在 ubuntu 发布门禁中真实执行。
- POSIX-only：`a session refresh replaces the cached block instead of accumulating` 与既有 DSH 内容用例在本机（Windows）skip，未在本机执行。
- 远端确认（提交 `e262196`，CI run 35503939861）：ubuntu job 首次执行 `release:check` **通过**——17 条此前只在发布时运行的 `release.test.js` POSIX 用例在 CI 上真实执行并全部通过。
- 同一 run 的 `windows-core` 失败（步骤 `Run Windows core verification`，exit 1）。该 job 在改动前的 `aa0e34e` 上即为同样的失败，不是本版本的功能改动引入；根因是行尾契约缺失，已在本版本修复（见「Windows 检出与行尾契约」），远端日志无需仓库权限即可复现——全新 `git clone` 即可稳定踩中。

## 1.5.0 - 2026-09-18

### 发版开关 `--no-publish`

- `scripts/release.sh` 新增 `--no-publish`：刷新、self-instance 镜像、双套测试门禁、版本 bump、changelog 校验、提交、tag 全部照常执行，只跳过最后的 `npm publish`，并提示 tag 仍是本地（后续走 `npm publish` 或 `gh release create v<v>` 触发 CI 通道）。不带该 flag 时行为逐项不变。
- 参数解析改为逐个消费：`--no-publish` 位置无关且可重复；release-type 与 `--version` 仍互斥、最多出现一次，重复被拒。
- 动机是既有的 CI 发布通道——tag 落地后由 `gh release create` 触发 publish.yml，而脚本此前只能一路 publish 到底。

### 编辑期覆盖扩展（codex / opencode / dsh）

- **codex**：`hooks.json` 注册 `PostToolUse`（matcher `apply_patch|Write|Edit`），编辑后违规经既有 `spec_only_post_tool_use` 通道（stderr + exit 2）反馈；运行时无需新增分支。
- **opencode**：插件新增 `tool.execute.after` 钩子——`edit`/`write` 命中时调用 `run spec-check --phase edit --file <path> --throttled`，把非空单行结果追加到工具结果文本；2.5 秒超时，运行时不存在的静默且不阻断编辑。
- **dsh**：预设插件注册 `tools/post-execute` waterfall——`write`/`edit` 命中时调同一 Python 协议（`run_edit_checks`），把单行告警作为 `additionalContexts` 附件送入下一轮请求；2.5 秒超时，无根/无解释器/协议异常一律静默。DSH 的 `tools/result` 只能观察不能回写，故走 post-execute 而非复用刷新监听。
- **路径提取多形态**：PostToolUse 的路径提取兼容 `file_path`/`filePath`/`path` 与 codex `apply_patch` 补丁文本（`*** Update/Add/Delete File:` 行）；同一路径去重，避免重复消耗节流窗口。
- **契约诚实化**：`spec-checks.md` 矩阵与 README 从"opencode 降级：无"改为准确表述——五个宿主全部覆盖，其中 zcode 仅主会话、dsh 经预设注入；此前的"降级"是项目未接线，不是宿主能力缺失。
- **实弹验收项（未在本地执行）**：codex 会话编辑后 stderr 反馈可见（需宿主 hook 信任批准）；opencode 会话 edit 后工具结果含单行警告；dsh 会话编辑后下一轮上下文含 spec-check 通知。

### DSH 预设过期检测

- **版本标记**：`install-dsh-preset` 安装后在预设目录写入 `.cowork-flow-preset.json`（`version` + `installedAt`）；已安装且版本不同时，不带 `--force` 的重复执行输出过期提示与更新命令，而不是仅报 "already installed"。
- **doctor 检测**：新增只读 advisory 检查 `check_dsh_preset`——预设缺失时不报告；无标记或标记不可读 → `PRESET-UNKNOWN-VERSION`；与项目 `.cowork-flow/.version` 不一致 → `PRESET-STALE`；两者都附 `install-dsh-preset --force` 提示，且不进入 doctor 的 error 集合（`ok` 不受影响）。
- **背景**：预设不随 `sync`/npm 更新，此前升级路径只存在于 README 散文，用户可能长期停留在旧注入逻辑且没有任何提示；协议失败时该宿主的注入会静默降级为空输出。

### 下游可发现性与文档权威性（spec-check）

- **发现路径补齐**：`run` 帮助列出 `spec-check`；`AGENTS.md` 的 managed block（模板与根同块）加指针行；README 新增「规范挂命令」与「MCP 客户端接入」两节，能力表与常用命令同步。
- **契约修正**：`spec/contracts/spec-checks.md` 的「归属与 sync 策略」改为与实际一致——`spec/` 是 sync 保护前缀，已安装项目不会被同步改写；具名例外是 `syncPolicy.safeFiles` 中的契约文件。该文件加入 `safeFiles`（同 `workflow-state-templates.md` 先例），使契约修正能到达已安装下游。
- **fallback 自救路径**：`FALLBACK_BINDING_BLOCKER` 与两处 lifecycle 拒绝文案改为指向 workflow-state 头部的 `session` 属性（`COWORK_FLOW_CONTEXT_ID`），不再给出无任务可传的 `pass <task-dir>` 单一出路。
- **悬空引用清理**：README 与模板脚本/spec 中指向已 untrack 的 `docs/` 的引用全部改写或内联（MCP 客户端配置要点保留在 README）。
- **测试**：新增根/模板 managed block 字节相等与指针断言、fallback blocker 文案可执行性断言。
- **已知合法副作用**：contract fingerprint 由 `d1d0e2536e8fa150` 更新为 `2dc34375d28f8103`（内容派生；`host-assets.json` 的 `safeFiles` 条目变更）。

## 1.4.0 - 2026-09-14

### Hook 会话身份绑定（fix(runtime)）

实弹暴露的多窗口交叉读取问题：zcode hook 会话携带对话自身的 session id，而任务激活发生在 Bash CLI 的显式身份下，导致未绑定的 hook 会话回退到 newest-session 时可能**读到另一个窗口的任务**。本版把绑定与回退语义一起收紧：

- **激活即认领**：PostToolUse 在激活类命令（`task start` / `task next <dir> --run` / `resume <dir>`）之后，把 hook 会话自己的 `zcode_<sessionId>` 绑定认领下来（`session_state.claim_active_task`）；查询类命令与不可信身份（process-fallback/缺失）永不认领。
- **回退语义收紧**：`fallback_for_unbound` 仅在**恰好存在一个** main-session 绑定时跟随最新的那个；存在多个绑定时，未绑定 hook 会话渲染 no_task + rebind 提示，绝不交叉读取其他窗口。
- **会话身份显式化**：workflow-state 头部新增 `session=<contextKey>` 属性，模型可将其作为 `COWORK_FLOW_CONTEXT_ID` 传给后续 CLI 调用，打通 hook 会话与 CLI 身份。
- **MCP 拒绝隐式冒认**：`task_state` / `task_scope` / `task_list` 在不可信身份下拒绝隐式解析（`identity-untrusted`），不再冒认 process-fallback 任务；CLI `FALLBACK_BINDING_BLOCKER` 语义不变（回归护栏锁定）。
- 契约文档 context-injection.md 同步记录 session 属性与回退语义；新增 pytest 396 行覆盖（active_task_runtime / inject_entry / mcp_state_server / workflow_state_hook）。

## 1.3.0 - 2026-09-09

### 跨宿主适配通用化（注入单源化 + MCP 重定位）

注入事实逻辑收拢到单一 Python 源，MCP 定位收口为"外部/无 hook 宿主的通用 pull 通道"：

- **宿主中立入口 `inject.py`**：zcode shim、claude-code、codex 全部走同一入口（`--host` 选择信封与形状），wrapper 瘦身为 ≤20 行委托。digest policy 措辞、registry-warning 抑制（zcode）、preamble、信封缩进全部按 host 参数化，仍由 context-injection.md 契约锁定。
- **zcode shim 化**：`inject-context.js` 从 ~1000 行事实镜像降为 ~140 行传输层——事件路由、PostToolUse(Bash) 廉价过滤（非生命周期命令零 spawn）、解释器定位（项目 runtime 优先、插件缓存副本兜底）、stdin/stdout 转发。删除 `inject-context.selfcheck.mjs`。matrix 逐字相等测试中的 zcode 线改为经 shim 驱动单源。
- **每宿主策略模块**：`adapters/host` 拆出 zcode/claude_code/codex policy（digest 措辞、警告静默、rebind 提示、essential-files、PostToolUse 传输、emit 格式化），共享层与入口零 `host ==` 分支；无模块宿主（dsh）走中立默认。字节级契约不变（fingerprint、stage-contract matrix 绿）。
- **JS-only 行为移植进 Python 单源**：`formatRebindHints`（zcode 无任务体补活动任务列表）、`editScopeWarning`（逐文件 scope 白名单警告，与 spec 警告合并进同一载荷）、missing-task 统一文案（原 "stale" 通用回退改为明确指向任务目录不存在 + 建任务指引，全宿主生效）、`checkEssentialFiles` 缺文件警告（zcode）、无会话身份时的 newest-session 显示回退（zcode，仅显示不改写绑定语义）。
- **MCP 重定位**：`task_scope` / `task_specs` 补 CLI 同源事实命令（`task scope` / `task specs`），MCP 不再有独占能力；contract-registry 注册 `FACT_LAYER_ACCESS_V1` 契约（digest 行注入"MCP 优先查询事实，CLI 兜底"）；doctor 新增 MCP 注册健康项（项目级 .mcp.json 存在性 / 全局+项目双重注册提示 / 缺失提示），只读 advisory 不阻断；README 增加两档注册说明（全局受支持默认 + 项目 opt-in 地图）。
- **修复（1.2.0 遗留，Windows）**：`spec_check._run_command` 三处——含引号命令经 list2cmdline 转义后 cmd.exe 解析失败；`text=True` 未显式 `encoding="utf-8", errors="replace"`，中文 Windows cmd GBK 输出致解码线程崩溃、输出丢失；命令入口缺失在 Windows 被误分类为 violation（现经 `shutil.which` 归 unchecked，契约三态语义恢复一致）。
- **修复**：legacy runtime context 文件（缺 `runtime_context_id` 字段）注入显示回退到检测到的 id。

**行为变更**：delegated 绑定写语义统一为 Python（zcode 注入时新增 bind 写，原 JS 为只读）；zcode missing-task 文案与全宿主统一；digest/fingerprint 因注册 `FACT_LAYER_ACCESS_V1` 而变化（预期内，change guard 允许）。

### 实弹修正与 delegated 自检协议化（fix）

实弹验证（zcode 插件 live proof）暴露四个缺陷并修复：

- **未绑定会话的编辑期警告可达**：zcode hook 会话携带对话自身 id、从不绑定（激活发生在 Bash CLI 的显式身份下），empty-session 此前跳过 newest-session 回退——主会话的编辑期 spec/scope 警告完全静默。回退现覆盖 empty-session，`spec_edit_warning` 的 zcode 路由经它放行（claude-code/codex 保持严格身份）。
- **scope 路径相对化**：`edit_scope_warning` 此前拿原始绝对路径与仓库相对白名单比对，所有编辑都被误标越界；现与 spec 路径同样归一为仓库相对，警告行显示相对路径。
- **编辑期预算与节流加固**：edit 钳制 3s→2.5s（子进程预算余量）；节流只在跑完一次后写入（执行器崩溃不再吞掉节流窗口）；`files` 多值列表逐 token 剥引号。
- **delegated 子代理收到 spec 反馈**：编辑期 spec 警告的静默范围此前在 Python/JS 两侧不一致，现统一为 delegated 会话可达（scope 警告保持仅主会话）。

配套协议化（文档与 skill）：实弹两轮证实宿主 PostToolUse 只覆盖主会话流——Agent 子代理收不到编辑期反馈。按已验证的 CLI 拉取路径固化：子代理报告前跑 `run spec-check` 自检修复（subagent-dispatch.md、agent-dispatch SKILL）；父侧验收把 violation 作为验收阻断项（task-review SKILL，delegated 工作最早的可靠检查点）；task-planning 的实现 Verify 命令默认含 spec-check 自检；spec-checks.md 记录缺口、四部分补偿与治理方向（向宿主请求；原生的那一环降级为冗余保险）。

**已知合法副作用**：contract fingerprint 更新为 `d1d0e2536e8fa150`（内容派生；Python 与 JS 镜像重算一致）。

### 发布门禁加固（release.sh）

- 同步 `--force` 自实例镜像时带 AGENTS.md 定制守卫（脏树预检、sync 后从 HEAD 还原）；pytest services 门禁前置到 `test:all` 之前；`.gitattributes` 将 `*.version` 钉为 LF（fingerprint 字节比对前提）。

## 1.2.0 - 2026-09-08

### 规范挂命令（spec 约束前移）

用户在 `.cowork-flow/spec/` 定义的行为规范，从"review 才发现"前移为"编码时即约束"：

- **spec frontmatter `checks:` 声明**：每条规范可声明检查命令（`cmd`/`files`/`timeout`/`when`），由唯一执行器 `./.cowork-flow/run spec-check` 按相位执行；机制只消费声明、不解析规范正文，规则变化随 spec 同文件天然同步。`files` 只支持目录前缀与扩展名两种形式（完整 glob 解析为错误且声明不执行，doctor 报告）。契约文档见 `spec/contracts/spec-checks.md`。
- **三态门禁语义**：`pass` / `violation`（complete 阻断、状态不推进）/ `unchecked`（命令缺失、解释器缺失、超时——阻断并要求显式 `--allow-unchecked`，豁免留痕进 `task.json` `meta.specCheckExempt` 供 review 可见）。unchecked 永不冒充 pass。
- **收口遥测**：complete 时全量结果写 `meta.specCheckSummary`，为"返工前移"效果提供可对比基线。
- **三线 digest 注入**：进入 in_progress 后，stage-contract 的 Specs 行升级为 h2 标题树索引（每 spec 最多 6 条、每条截断 24 字符），规范条目名随契约常驻注意力；spec 正文改动不影响 digest，超预算整行让位（Scope/Gates 永不丢）。python/zcode/opencode 输出由 matrix 用例锁定逐字相等，claude 线经 Python 单源自动获得。
- **编辑期快跑**：zcode（PostToolUse 短路径，spawn 单源 CLI、3.8s 上限）与 claude（PostToolUse 新增 hook 资产，exit 2 单行 stderr 反馈）在编辑命中 `files` 的声明时就地执行，违规单行警告、同文件 10 秒节流（状态在 `.cowork-flow/.runtime/`）、执行器缺失静默不阻断编辑流；opencode 降级为仅 digest + 收口。
- **doctor 健康项**：`specChecks` 报告声明解析错误与命令入口不存在——"跑不了的声明"在收口前暴露。

配套：spec-check CLI（`--phase/--file/--json/--verbose/--throttled`）、`--allow-unchecked` 收口旗标、架构拓扑保持 services 层无 CLI 关注点。

## 1.1.4 - 2026-08-31

### 修复

- **Windows 启动修复**：`mcp-state` 子进程在 Windows 平台改为经 `cmd.exe` 启动（`shell: true`），与 npm shims 的启动方式保持一致——绕过 Node 24+ 直接 spawn `.cmd` 文件（如 `cowork-flow.cmd` 的 shell 入口）时抛出的 EINVAL 错误。

## 1.1.3 - 2026-08-30

> **版本内容载体说明**：1.1.1（守卫修复批次）与 1.1.2（Review 基线 diff）章节内容随本 1.1.3 首次进入 npm 分发——三个批次同属一个发布周期，章节按批次序号记录，包内容以最新版本号为载体（与 1.1.0 承载 1.0.0 章节内容同一惯例）。

### 规则表数据化（scope-rules 单源）

- 新增 `.cowork-flow/spec/runtime/scope-rules.json`：scope 过滤规则（allowedTypes/wildcardChars/rejectedSegments/driveLetterPattern/trailingSlashRejectedTypes）与 stage-contract 限制（budget/scopeLimit/specLimit/verifyLimit）从三份复制实现下沉为单一数据文件。
- Python（context_paths/fact_view）与 zcode/opencode JS 镜像运行时消费同一文件；文件缺失/畸形降级到与默认内容逐字一致的内嵌默认（默认等价由 tests/test_scope_rules.py 与 selfcheck 锁定）。
- 规则可真实改变行为：wildcardChars 置空 → 通配条目进入 Scope；budget 调小 → 预算降级路径触发。
- 修复预算兜底 1 字节超限：裁剪切分与闭标签间的换行预留。
- **CI 修复（delegated 注入崩溃）**：zcode delegated 分支不再以空输入对象重新发现项目根（`findProjectRoot({})`），改为复用 main 已解析的工作流根——在无 `.cowork-flow/` 的目录（干净 checkout、非项目目录）触发 delegated prompt 不再 `join(null)` 崩溃；对应的注入测试显式指定 spawn 工作目录，消除对测试运行 cwd 的隐式依赖（干净 checkout 下此前必红，实测 dev 推送 CI 双平台失败）。
- **CI 修复（Windows git 降级）**：`git` 二进制不可用（PATH 缺失/未安装）时 `_run_git_command` 捕获 OSError 按 rc!=0 降级——`current_head` 视为无头（不写 baseline）、变更集收集降级 status-only，`task start` 不再崩溃（Windows 的 CreateProcess 在 PATH 缺失时不回退，清空环境的会话测试此前必红；macOS execvp 有默认 PATH 兜底故本地绿）。

## 1.1.2 - 2026-08-30

### Review 基线 diff（堵住提交绕行面）

- **基线记录**：`task start`（进入 in_progress）在 task.json `meta.baselineCommit` 记录当前 HEAD，且永不滑动（重复/幂等 start 不覆盖）——任务期间的审查窗口从激活时刻起固定。
- **变更集合并**：review 门禁以 `baseline..HEAD` diff 与 working-tree status 的并集去重作为变更集——agent 中途 `git commit` 越界文件后，review 的 `unlisted_changed_file` 仍会触发（此前提交即从 status 消失，形成无痕通道）。
- **降级语义**：无 git 仓库 / HEAD 不存在 / 基线缺失 / diff 失败（如 rebase 孤儿化）→ 降级 status-only，与旧行为一致，不产生错误 blocker。
- **契约重开**：task-review SKILL 输入语义写明基线变更集与降级行为；已审查任务的增量重审聚焦自基线以来的变化，证据要求不变。

## 1.1.1 - 2026-08-30

### 守卫修复批次（对抗评审后落地）

- **hook 崩溃修复**：implement.jsonl 含 `./` 前缀条目时 zcode/opencode 双宿主 hook 从 `TypeError: Assignment to constant variable` 崩溃（整个上下文注入丢失）改为正常输出——`const`→`let` 两处 + 回归 fixture。
- **stage-contract 预算降级**：超限输入不再产出未闭合的畸形块；按 Verify → Specs → Scope 条目（至少 1 条）逐级降级，收尾标签与 Gates 行恒在；三线同构算法。
- **MCP 路径隔离**：`task_scope`/`task_specs` 拒绝仓库外路径（`../`、绝对路径）返回 `task-outside-repo`；无 id 的 JSON-RPC 通知（含 initialize/ping/tools/list）不再响应。
- **JS 白名单语义对齐**：zcode/opencode 过滤规则与 Python `normalize_context_file_scope_entry` 一致（非法 type、`../`、绝对路径、盘符、通配符一律丢弃）——editScopeWarning 与 Scope 行不再对 gate 会标记越界的文件静默放行；spec 指针同规则过滤。
- **delegated 只读 scope**：子代理注入包删除 `Scope: subagent` 行；stage-contract 以父任务 scope `[read-only]` 变体呈现，Gates 话术同步（不再暗示子代理可自声明 scope）。
- **异常降级可诊断**：锚点文件非法 UTF-8 时 stage-contract 保留 Scope/Gates 仅丢 Verify（此前整块静默消失）；非例行异常在 stderr 留痕。
- **review 门禁补洞**：implement.jsonl 缺失时 review 产生 `missing_implement_jsonl_file_scope` blocker（此前静默放行，删除 manifest 即绕过白名单）。
- **矩阵化跨端测试**：`test/fixtures/stage-contract-matrix.json` 单一数据文件驱动三线（python/zcode/opencode）逐字节相等断言，覆盖规范/`./` 前缀/非法边界/超限/emoji/缺锚点/空 scope/delegated 8 类用例；zcode hooks.json matcher（Bash|Edit|Write|MultiEdit）由模板测试锁定；新增 Python 侧矩阵断言。
- dev_type 畸形值（非字符串）在 task_specs 中按缺省降级；spec 指针忽略 directory 条目；normalizeScopePath 带 trim；zcode 生命周期刷新正则对齐 dsh（task|subagent|resume）。
- 契约文档如实化：context-injection.md 不再声称三线结构恒等/always emitted，改为差异表 + 矩阵锁定范围 + 残余缺口清单（matcher 依赖 ZCode 运行时工具名、JS 过滤为规则移植）。

## 1.1.0 - 2026-08-29

> **版本内容错位说明**：npm registry 上的 1.0.0 tarball 发布于 2026-08-26（仅含发版脚本修复之前的代码）。1.0.0 段下述的里程碑描述以本 1.1.0 为其实际发布载体——阶段 0-3 的全部内容自本版本起进入 npm 分发。

### 方向落地（阶段 0-3，详见 1.0.0 段）

- 阶段 0：README 定位改写为「运行时上下文与协作事实层」；注入协议契约 `spec/contracts/context-injection.md`；契约指纹序列化三线统一 + slim 全覆盖 + 跨 host 一致性测试。
- 阶段 1：`run state [task] --json` 事实视图；`<workflow-state>` 属性事实头 + `<decision-anchor>` 决策要点注入（三线一致）。
- 阶段 2：`executor` 归属、冲突拦截与 `--takeover`、无会话 CI start、`subagent evidence` 证据位。
- 阶段 3：`run mcp-state` 无依赖 MCP stdio 只读服务（`task_state` / `task_list`）+ `spec/contracts/fact-layer-access.md` 接入契约。
- MCP 全局入口：`cowork-flow mcp-state` 透传命令——MCP 客户端全局注册一次即可服务所有 cowork-flow 项目。

## 1.0.0 - 2026-08-26

首个稳定主线发布：核心流程契约、会话模型与宿主矩阵在此版本冻结，后续改动进入语义化版本约束。

### 稳定性声明

- **宿主矩阵冻结**：`codex` / `opencode` / `claude-code` / `dsh` / `zcode` 五宿主经 host-assets 注册、adapter 一致性校验与 doctor 全链路覆盖；zcode 插件资产与工作区流程资产均为单源分发（`.zcode/` 走插件市场，技能落盘 `.cowork-flow/skills/` 供内核解析且不进入提示层）。
- **状态注入协议冻结**：`<workflow-state>` 块 + contract-digest（SessionStart 全量 / 逐消息指纹行）+ 生命周期快照（`.runtime/state-snapshot.json`，与状态转换同单元原子提交）构成宿主 hook 的标准输入；`build_hook_context` 共享协议具备直接单测覆盖。
- **会话模型冻结**：按会话身份（host session id / 显式 context id / hook sessionId）绑定；显式身份无绑定时判 `no_task` 并列可改绑任务，无身份请求才走全局最新有效兜底；进程级 fallback 绑定不再自动跟随。

### 自 0.0.52 以来的变更

- 会话绑定安全加固：进程 fallback 会话键（`ZCODE_PROCESS_LABEL`）带 provenance 标记，导航、`--run` 派发、review/complete 目标解析与命令行收尾拒绝自动跟随 fallback 绑定，要求显式任务目录；trusted 身份（显式 env、宿主 session env、hook sessionId）保持完整绑定语义。
- 对抗性审查修正批次：显式 `COWORK_FLOW_CONTEXT_ID` 按裸键解析与 CLI 对齐；PostToolUse 刷新过滤支持 `cd` + 裸 `run` 与 Windows `run.cmd` 命令形态；legacy cursor 宿主保留完整 contract-digest；改绑提示排除已完成的终态任务；doctor 会话卫生检查对无时区时间戳降级为告警而非崩溃。
- 交互式平台选择器与平台检测断言随五宿主矩阵更新。
- release.sh 容错：`--version` 精确模式在版本文件已全部就位（干净工作树）时，`git commit` 的 no-op 空提交不再中止脚本，继续 tag 与 publish；其余 commit 失败仍立即中止。新增回归测试覆盖两条路径。
- release.sh 容错：目标发布 tag 已存在且指向当前 HEAD 时跳过创建并继续 publish（上次运行 tag 后 publish 未完成的重跑场景）；指向其它提交则中止报错。新增回归测试覆盖两条路径。
- 方向收敛（阶段 0）：README 定位改为「运行时上下文与协作事实层」；新增注入协议契约 `spec/contracts/context-injection.md`（事件时机矩阵、digest 形态规则、序列化规范）；契约指纹序列化三线统一（zcode/opencode 稳定排序 + Python 紧凑分隔符，跨 host 指纹一致性测试锁定）；Python 线补 slim（SessionStart 全量 / 后续单行指纹，无事件 host 按会话文件首次判定）；codex 事件名读取；opencode 首次全量后续单行；dsh 会话开始全量、生命周期命令后单行刷新。
- 事实层 API 化（阶段 1a）：新增 `./.cowork-flow/run state [task] --json` 事实视图——聚合 task.json（含 `_state` 修订）、decision-anchor 结构化要点（目标/验收项/被拒方案名）、plan 绑定、绑定会话与受信快照；无绑定输出 `task: null` 供机器分支。
- 注入结构化（阶段 1b）：`<workflow-state>` 升级为属性事实头（`task`/`status`/`source` 进开标签，body 保留人读面包屑），三线一致并在协议契约冻结；planning/in_progress/review 状态下三线注入紧凑 `<decision-anchor>` 决策要点块（Python 复用 fact_view 解析单源），completed 终态与缺文件不注入。
- 多执行者语义（阶段 2）：task.json 增加 `executor` 归属（start 写入会话 key 或显式 `--executor`）；执行者冲突 fail-closed（`LIFECYCLE-EXECUTOR-001`，幂等重跑同样拦截），`--takeover` 显式接管并覆写归属（含已激活任务的幂等接管）；`--executor` 允许无会话 CI/无头 start（不建会话绑定）；子代理运行时上下文新增 `evidence` 证据位（`subagent evidence <id> --note [--artifact]`，CAS 保护、closed 可补记、不影响任务状态机）；`run state` 人读摘要透出 Executor。
- 生态适配（阶段 3）：新增 `./.cowork-flow/run mcp-state`——无依赖 MCP stdio 只读服务（newline-delimited JSON-RPC 2.0），工具 `task_state`（事实视图）与 `task_list`（活动任务概览）；接入契约 `spec/contracts/fact-layer-access.md` 冻结只读保证与"不自创跨 agent 协议、adapter 保持薄"立场，写路径仍独占于 CLI 门禁链。
- 实现阶段守卫三件套：MCP `task_scope`/`task_specs` 只读工具（越界判定与规范清单，宿主无关、Python 单源）；`<stage-contract>` 实现契约块三线注入（编辑白名单/规范入口/门禁预告/任务自声明验证命令，≤1200 字符，跨宿主逐字相等测试锁定）；zcode 编辑越界实时警告（PostToolUse Edit/Write/MultiEdit 短路径，能力矩阵声明 `editScopeWarning`，其余宿主 fallback 到静态预告）。
- MCP 全局入口：npm CLI 新增 `cowork-flow mcp-state` 透传命令——从 cwd 向上定位最近 `.cowork-flow/` 并以继承 stdio exec 该项目的 `run mcp-state`；MCP 客户端全局注册一次（`cowork-flow mcp-state`）即可服务所有 cowork-flow 项目，无需逐项目配置。

## 0.0.52 - 2026-08-26

### ZCode 宿主与 hook 体验

- 修复 hook 过期会话污染：按会话身份选取活动任务，全局兜底跳过失效绑定与 subagent 会话；显式身份无绑定时对齐 CLI 判 `no_task` 并列出可改绑活动任务。
- 注册 zcode 为一等宿主平台：`host-assets.json` platforms 条目 + `adapters/zcode/adapter.yaml`，alias 解析、平台检测、adapter 一致性校验与 doctor 全链路覆盖；`.zcode/` 维持插件分发不落工程。
- 纯 zcode 工程生命周期可用：技能落盘 `.cowork-flow/skills/`（宿主提示层仍由插件单源提供），内核 `skill_roots()` 解析 action owner；`detectAny` 增加 adapter 标记修复 sync 静默失养。
- contract digest 注入瘦身：SessionStart（含 compact/clear）注入完整块，UserPromptSubmit 仅重复指纹行。
- 新增 PostToolUse(Bash) 轮内刷新：生命周期命令落定后立即注入最新 workflow-state 与指纹行，无关命令零输出。

### 运行时与诊断

- 生命周期转换在提交单元内原子写 `.runtime/state-snapshot.json`；hook 在快照与所选任务一致时采用快照面包屑键，缺失或不一致回退 status 推导。Python 共享 hook 协议（build_hook_context）补直接单测。
- doctor 新增会话卫生检查：报告失效任务绑定、超龄未活跃、不可读的运行时会话文件。

### 文档

- AGENTS.md 0.1 明确注入块优先、勿重复运行导航器；README 平台清单与技能分发表同步 zcode。

## 0.0.51 - 2026-08-15

### DSH host 接入

- 注册 DeepSeek Harness（dsh）host adapter 与平台标签映射（dsh_ context keys）。
- 新增 `install-dsh-preset` 分发 DSH agent 预设；预设内置 workflow-state hook 插件，向系统提示注入与其它宿主同构的 `<workflow-state>` 块，每条用户消息刷新，生命周期命令落定后轮内刷新。
- 补齐协议失败静默降级边界测试；记录 DSH 子代理绑定 field-test 路径（subagent init/bind/close）。

### 计划绑定

- `--from-plan` 支持绑定计划到 planning 任务（plan binding lite 收口），补 --from-plan help 与实际行为一致。
- 归档任务快照绑定计划（snapshot bound plan into archived task）。

### 运行时与发布

- `platform_from_context_key` 单源化并修复 zcode 平台漂移；zcode 会话上下文确定性解析；slug 前缀与任务 id/name 归一。
- 共享 PYTHONPATH bootstrap；批量动作与 codex hook 在 Windows 通过 cmd wrapper 运行。
- CI 在 Ubuntu/Windows 双平台跑全量 pytest；发布流程先同步 Skill replicas 再过全量门禁。

## 0.0.50 - 2026-08-10

### 文档

- task-review 技能把用户自定义 spec 明确为绑定义务（binding obligations）。

## 0.0.49 - 2026-08-08

### 计划与任务

- 引入 plan binding lite：任务元数据绑定计划文件，Normal/High-risk 任务启动前校验计划与 decision anchor 就绪。
- `task next` 暴露实现优先读上下文（implement read-first）；test-first 技能强化 red-green 指引。

### 运行时与架构

- 新增源码检出 source-refresh 命令；任务上下文服务模块化，lifecycle CLI adapter 瘦身；架构护栏测试固化边界。
- 状态恢复诊断增强；host manifest 契约对齐；批量与 party 编排器模块化。
- 保持 python 3.9 runner 兼容。

### CI / 发布

- 增加 Windows 发布信心门禁；发布验证测试稳定化。

## 0.0.48 - 2026-08-05

### 运行时与流程

- 拆分 lifecycle 命令；route 契约收紧；runtime context 生命周期硬化，恢复元数据错误 fail-closed；subagent 运行错误码透出。
- 移除 legacy changes control plane 与 add-session journal 工作流；guides 指引归入规划阶段。

### Party Mode 与 Batch

- 抽取 Party board 存储层；final report facts 丰富；host action fallback 对齐 capability matrix。
- Batch 增加 inspect facts 与 host action 结果校验；恢复契约文档化。

### Host 资产与健康

- 新增 host capability matrix 契约；host-assets sync 策略集中；防止 ZCode scaffold 向模块目录泄漏流程文件。
- task-review issue 与 runtime-health envelope 归一，review/health 输出更易消费。

### 文档

- README 项目概览刷新、任务流程图；产品故障排查 playbook；changelog 发布就绪说明。

## 0.0.47 - 2026-08-05