# 更新日志

## [Unreleased]

### Added

## [2.2.0] - 2026-10-20

### Changed

- **计划与任务验证段纳入规范门禁检查**：`task-planning` 的计划 `Final Verification`、任务规则与 Self-Review 要求按 `dev_type` 逐条核对 `.cowork-flow/spec/<dev_type>/` 适用规范与项目门禁——改动被规范覆盖时，把决定命令或 `规范核对:` 行写进计划的 Final Verification 与任务简报的 Verification Command，标 `pass` / `not_applicable` 并写理由；`decision-anchor` 契约的 `## 验证命令` 同步要求该检查行，并明确为 review 强提醒而非 `spec-check` 硬门禁，120 字符/10 行限制不变。
- **模板示例统一展示规范核对行**：`decision-anchor` Schema 的 `## 验证命令` 示例新增 `规范核对:` 行；`task-planning` 任务简报的 `Verification Command` 示例块后补充写法说明，避免新建计划/任务漏写规范检查项。

## [2.1.0] - 2026-10-19

### Added

- **发布前漂移门禁接入 release.sh，测试范围与超时收敛**：发布 pre-flight 在 `source:refresh`（会覆写活副本）之前强制跑 `node scripts/release-gates.js`，自实例漂移即中止并打印修复指引；新增 `pytest.ini`（`testpaths = tests`）把 `python -m pytest -q` 的收集范围钉在 `tests/`，所有 node 测试脚本统一 `--test-timeout=600000`，`test:windows:core` 补上 Windows 全量 `init/sync` 套件（此前只跑两条具名用例）。
- **发布门禁补"活副本资产漂移"verdict**：`release-gates` 新增 `self-instance-asset-drift`——以 `node bin/cowork-flow.js project sync . --dry-run` 的 readiness 为准，`wouldCopy`/`wouldRemoveObsolete` 非空即 fail 并点名文件（`wouldSkipProtected`/`wouldKeep` 只报告不阻断）。覆盖 `.claude/**`、`.codex/**`、skills 等 `dev refresh` 看不到的活副本，避免发布第 5 步 `sync --force` 静默覆写；`scripts/release.sh` 失败提示补 `node bin/cowork-flow.js project sync .` 修复指引。
- **doctor 增补 zcode 插件新鲜度检查**：`check_zcode_plugin` 以 payload 盖章清单 `.zcode-plugin/plugin.json` 的版本对比项目 `.cowork-flow/.version` → `PLUGIN-STALE`（hint `cwf host add zcode --force`）；未声明 zcode 静默，声明未安装报 `PLUGIN-NOT-INSTALLED`，清单不可读报 `PLUGIN-UNKNOWN-VERSION`。与 opencode/qoder 同为 advisory，不进 error 级。

### Changed

- **Python 解释器下限统一 3.10，五个宿主 shim 加解释器探针守卫**：`template/.cowork-flow/run`、`run.cmd` 的版本判据与提示从 3.9 升到 3.10（与运行时协议一致）；`presets/{opencode,zcode,qoder,kimi-code,dsh}` 的注入 shim 逐个候选加同源版本探针（`sys.version_info >= (3, 10)`），不可用即跳过、全不可用则 stderr 一行说明并 fail-open（exit 0），探针超时视为无裁决、不跳过。**迁移**：shim 在宿主载荷内，需 `cwf host add <host> --force` 重装。
- **清理 spec-check 删除后的文档与宿主提示残留**：README（中英）、`docs/{index,hosts,direction}.md`、`context-injection.md` 里"规范检查/规范门禁"的过时措辞改为"同步策略与受保护文件"，并订正机器级 shim 的 fail-open 描述（现为四个机器级 shim；项目级 Edit 期 hook 自 2.0.0 起同样 advisory、恒 exit 0）；15 处宿主 agent 提示（`.claude`/`.codex`/`.kimi-code`/`.opencode` 的 `cowork-*` 与 codex 的 `default`/`explorer`/`worker`）把点名已删子命令的禁令改为"禁止执行任务生命周期转换"。
- **`assetDriftVerdict` 缺键改为 fail-closed**：readiness 少 `wouldCopy`/`wouldRemoveObsolete`（或给非数组）时不再静默判"无漂移"，改判门禁失效并点名缺失键（`cannot judge drift`），并把逐 key 单钉、e2e fail 断言补进测试。
- **dsh 候选可用性映射抽为 `candidateUnavailable` 并恢复 Windows 覆盖**：`ENOENT`/退出码 3 → 换下一个候选；其余非零退出（含超时）→ 候选按"可用但协议失败、不注入"处理（语义不变，仅抽函数加注释）；新增跨平台单测钉住四种输入，`test/dsh-hook.test.js` 两条过期的 Windows skip 移除（取证：node 探测 WindowsApps `python3` 别名得 `ENOENT`、回落到真实 `python` 3.12）。
- **重复工具函数收敛**：`sha256` 只留 `src/lib/asset-plan.js` 的导出，`src/lib/plan-applier.js` 改为复用；`getDshHome` 抽到新增的 `src/lib/dsh-home.js`，两个 dsh 安装器共用。

### Fixed

- **dsh 完整协议 stdout 固定 UTF-8，恢复非 CJK 控制台下的工作流注入**：`<workflow-state>` 块含中文文案，Windows 默认 ANSI 代码页（CI runner 为 cp1252）下 `print()` 抛 `UnicodeEncodeError`，调用方按既有语义读作"解释器能跑但协议失败 → 不注入"，dsh 会话静默丢失整块注入——上面移除 Windows skip 后两条用例在 runner 上暴露的正是这个缺陷（原 skip 注释归因于 WindowsApps `python3` 桩，实测不符）。修法对齐同文件 edit-scope 协议与 `inject.py` 的既有写法，在完整协议开头补 `sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="")`；新增回归用例在 `PYTHONIOENCODING=ascii` 下钉住该契约（红证：改动前该用例失败）。顺带把 `newline=""` 的 LF 语义带进来，块字节在 Windows 与 POSIX 上一致。
- **release 编排用例补 `scripts/release-gates.js` 桩**：`0c81b29` 给 `release.sh` 加的首道漂移门禁在 Linux 上必飞——夹具只复制 `release.sh`，`node scripts/release-gates.js` 报 `Cannot find module` 被读作漂移阻断，3 条用例红（was: 该门禁已无任何用例钉住其接线）。夹具补同款 `process.exit(0)` 桩，并在"defaults to patch"用例断言门禁先于 `source:refresh` 运行。

## [2.0.0] - 2026-10-16

### Added

- **编辑期越界警告覆盖 6 宿主（抽共享模块）**：`spec-check` 删除后编辑期只剩 zcode 的 scope 越界提示（其余宿主 `unsupported`），现在把同一语义接到 claude-code / codex / qoder / opencode / dsh——编辑工具落盘后，若活动任务为 `in_progress`/`review` 且被改文件不在其 `implement.jsonl` 白名单内，回**一行** `⚠️ <rel> is outside the task's declared scope. If intended, declare it in the task's `implement.jsonl` (agent-mutable) or revert the edit.`；在范围、无任务、planning/completed、子代理会话、任何异常或超时一律静默——非阻塞、fail-open、全宿主 exit 0。判定逻辑从 `zcode_policy.py` 抽到共享模块 `adapters/host/edit_scope.py`（新增 `extract_edited_paths`：`file_path`/`filePath`/`path` 加 codex `apply_patch` 的 `*** Update File:` 文本，去重保序），zcode 改为引用后对 zcode 实际载荷输出逐字节相同（共享模块语义上是超集：额外识别 `path` 键与 apply_patch 文本路径，zcode 载荷不触发；其既有测试零改动全绿）。**通道**：claude-code / codex / qoder / opencode 走 `inject.py` 的 policy `post_tool_use` 槽（前三个回 `hookSpecificOutput.additionalContext` 信封，opencode 因 `emit_text` 得裸文本并追加到 `tool.execute.after` 的工具输出），dsh 在其 preset 插件的 `tools/post-execute` 里经 Python heredoc 直调共享模块，以 plugin notice 并入 `additionalContexts`。能力声明：`host-assets.json` 六个宿主 `editScopeWarning: plugin`，kimi-code 保持 `unsupported`（宿主丢弃 PostToolUse stdout）；`context-injection.md` 的 Per-edit warning 段同步改写。**迁移**：宿主侧载荷需 `cwf host add <host> --force` 重装（claude-code 的 `.claude/settings.json`、codex 的 `.codex/hooks.json`、qoder 的机器级插件 hooks.json、opencode 与 dsh 的插件文件都在载荷内）。Bash 重定向/tee 写文件仍不在覆盖范围（既有残余缺口）。

### Changed

- **末段裁剪抽成 `_cut_scope_rows`，体积按 Scope 行条数分摊，弱断言用例补强**：`_fit_stage_contract` 回到软预算以内（63 → 45 行），末段裁剪有了独立函数名与边界说明；`room` 由 `budget - len(fixed) - 1` 改为 `(budget - len(fixed) - scope_count) // scope_count`，多条 `Scope:` 前缀行不再"同时被截断又超预算"（单条时与旧式逐字节等价：2050 次逐预算渲染对照、其中 668 次走到末段裁剪，零差异）。复核曾判 `room < len("Scope: ") + 1` 下限与标签守卫行为重叠、可删——实测该结论只对 `0 ≤ room < 8` 成立：`room < 0` 时切片是 `line[:-k]`，从尾部切、前端保留，长条目的标签存活会让守卫放行一个被腰斩且仍超预算的块，下限是唯一拦截者，故保留并补了只能由它单独拦住的红证用例。契约与 docstring 的阈值措辞精确到 `len(fixed) + 9`。测试面：新增多条 Scope 行体积不变量用例，并把 6 条 `shallow_assertion_signal` 软提示一并处置（新用例补 `assertRegex` 钉消费者契约、`SpecEntriesForTaskDevTypeTest` 补 `assertEqual(resolved, …)` 与按 dev-type 所有权过滤后的精确列表），补强后 `review-check` 在该文件零告警。
- **stage-contract 末段裁剪修复：任务身份与编辑策略优先于预算**：预算极小时末段裁剪原先对整块正文做码点截断，会把开标签一起截掉（实测产出 `<` 或 `<stage-contract task="` 这类半截标签，消费者正则匹配不到，块等于消失），或把 `Gates:` 编辑策略行切成半句（预算 400 实测只剩 `Gates: edit`）。现在末段裁剪只缩短 Scope 行：开标签、闭合标签与 Gates 行在任何预算下完整存活，超长部分由 Scope 行承担；截断若会把 Scope 行的 `Scope: ` 标签本身磨掉（切点落在条目首部空白处），则改回返回整块——宁可超预算，也不产出消费者正则匹配不到的 Scope 行。预算小到连这些固定行都装不下时同样返回整块、允许超过预算（保护行与可解析性优先于预算）。出厂 `budget = 3400` 下该末段不可达，对下游零可见变化——字节对比确认现有全部夹具在该预算下逐字节相同；`context-injection.md` 的 Budget 段与 `_fit_stage_contract` docstring 已写明三条不变量与下限，并新增扫预算可解析性用例与下限用例（各带红证）。
- **stage-contract 注入容量放宽（Verify 行 10 条 / 块预算 3400 字）**：`Verify:` 行从"渲染 3 条 / 解析 5 条 / 全块 1200 字"放宽到"渲染 10 条 / 解析 10 条 / 全块 3400 字"，让 `decision-anchor.md` 的 `## 验证命令` 段放得下"先读规范再逐条核对改动"的强提醒加真实校验命令，不再静默丢弃第 4 条之后的命令（单条仍截断在 120 字）。三处预算来源同改并互锁：模板 `spec/runtime/scope-rules.json`、`context_paths.DEFAULT_SCOPE_RULES`、`fact_view.STAGE_CONTRACT_VERIFY_LIMIT`/`STAGE_CONTRACT_BUDGET`，新增"默认值↔常量"一致性测试补上第三条断链。`scope-rules.json` 进 `syncPolicy.safeFiles`，已有项目一次普通 `cwf project sync` 即拿到新默认值；代价是该文件的本地调优会在下次 sync 被覆盖（`context-injection.md` 与 `spec-checks.md` 已写明）。降级测试改为钉住自选预算并额外断言输入确实超预算，不再随生产常量漂移（原先升预算会让它们静默恒真）。
- **kimi-code 裸命令一次装齐（组合组件）**：`kimi-code` 新增组合组件 `all` 并把 default 从 `plugin` 改指它——`cwf host add kimi-code` 一条命令先装上下文注入 hook（config.toml 托管块 + shim + marker），再装插件（sources/managed 两份载荷 + 宿主注册表记录），`cwf host remove kimi-code` 一次卸两者。组合器只做定向旗标剥除：`--force` 自动只达插件段（hook 无该旗标），未知旗标仍原样透传给 installer 报错；显式 `--component plugin` / `--component hook` 的单装语义不变（plugin 单装不写 config.toml）。`host list` 的组件列因此显示 `plugin, hook, all`。`docs/hosts.md` 的宿主表与 Kimi 段改为裸命令主推，升级路径写明 `cwf host add kimi-code --force`。

### Removed

- **spec-check 机制整体删除（破坏性）**：下游正式项目不会手写 `checks:` 声明，规范声明命令 / 编辑期提示 / 收口硬门禁 / doctor 体检被判定为冗余设计，整条链删除。**删除面**：`run spec-check` 命令与两个实现文件（573+178 行）、lifecycle 的 `SPEC-CHECK-PARSE-ERROR` / `SPEC-CHECK-EXECUTOR-ERROR` / `SPEC-CHECK-VIOLATION` / `SPEC-CHECK-UNCHECKED` 四个错误码与豁免构造（`meta.specCheckExempt` / `meta.specCheckSummary` 遥测随之消失）、`--allow-unchecked` 与 `allow_unchecked_specs`、全部宿主的编辑期 spec 提示（zcode 合并提示、claude-code / codex / qoder 的 `PostToolUse` 槽与 hooks.json 声明、opencode `tool.execute.after`、dsh `tools/post-execute`）、doctor 的 `specChecks` 体检、契约 `spec/contracts/spec-checks.md` 与 `SPEC_CHECKS_V1` 契约登记。**保留不动**：zcode 编辑期 scope 越界警告（`edit_scope_warning` 原样，PostToolUse 现在只回这条）、stage-contract 的 Specs 行与 h2 digest 注入、`--allow-missing-evidence` 的 AC 证据豁免链（含 `meta.evidenceExempt` 与打印/归档展示）、`allow_spec_file_modifications`，以及 review 结论的 `clause → command → negativeProof` triple（只删依赖 `checks:` 的措辞）。**契约搬迁**：`spec-checks.md` 的 digest 注入附录并入 `context-injection.md` 的 Specs 段，`spec/` 同步保护前缀与 `safeFiles` 具名例外说明并入 `docs/architecture.md`。**迁移**：`.cowork-flow/scripts/services/spec_check.py` 与 `.cowork-flow/scripts/adapters/cli/spec_check.py` 已登记 `obsoleteFiles`，一次普通 `cwf project sync` 即删除；已装项目里的 `spec/contracts/spec-checks.md` 受 `spec/` 保护前缀保护，sync 会明确报告 `Kept … (protected-path); delete manually if unwanted`，需手动清理；宿主侧载荷需 `cwf host add <host> --force` 重装。已声明 `checks:` 的项目从此失去该门禁——替代信号是 review 阶段既有的"逐条核对用户规范"清单项与 stage-contract 的 Specs 行。

### Fixed

- **注入文本与策略提示指向不存在的命令**：`<stage-contract>` 的 Gates 行尾句写 `self-declared via task context add`、zcode 越界编辑提示写 "add it with `task context add`"，但 CLI 只有 `{next, scope, specs}`（实测 `invalid choice: 'context'`）；`plan-binding.md` 与 `task-adopt.md` 同样引用 `task create` / `task create --from-plan`。这些内部适配器是有意不公开的（`test_context_commands_are_not_public_parser_commands` 锁定，`task_context_commands.py` 写明 public workflow 走 `task next` + 直编 JSONL），所以改文字到真实机制而非接线：Gates 尾句改为 `scope is agent-mutable (declare more in implement.jsonl)`，zcode 提示改为 "declare it in the task's `implement.jsonl`"，契约正文改为 `task next --title … --slug …` 与 `task next --from-plan <path>`。`.cowork-flow/scripts/**` 在 `syncPolicy.safePrefixes` 内，下游一次普通 `cwf project sync` 即生效；受 `spec/` 前缀保护的契约正文仍只对新装项目生效（既有取舍）。

## [1.9.2] - 2026-10-14

### Added

- **子代理切片机检与派发工具（派发默认化 M2）**：把"并行切片互不踩"从计划措辞变成运行时事实。① **切片所有权机检**：`subagent init --slice <name> --owns <path>...` 把所有权声明写进 `assignment`；同一任务内，若新 implement 上下文声明的 `owned_paths` 与任一未关闭 implement 上下文的声明相等或互为目录前缀（`\`/`/` 与尾斜杠归一，绝对与相对 `--execution-task-dir` 按同一把钥匙比较），初始化 fail-closed 报 `SUBAGENT-SLICE-001` 且被拒上下文不落盘；关闭（close）即释放路径，未声明 `--owns` 的既有调用不受任何影响。② **派发 prompt 渲染**：`subagent prompt <runtime_context_id>` 输出可直接粘贴的子代理提示——transport 两行原文 + "先读 assignment"指引 + goal/expected_output/切片，保持宿主无关（不写宿主专有协议串）。③ **敞口盘点**：`subagent list [--task <dir>] [--open]` 列上下文 id / status / agent_type / 任务 / slice 与 owns 摘要。④ **卫生提示**：doctor 对"completed 任务仍有未关闭子代理上下文"新增 warning `TASK-HYGIENE-COMPLETED-WITH-OPEN-SUBAGENTS`（只提示不门禁，exit 语义不变；hint 指向 `subagent list --task`）。契约同步：`subagent-dispatch.md` 新增 Implement Slices 段、`error-codes.md` 登记 `SUBAGENT-SLICE-001`、`agent-dispatch` 技能补 owned_paths 编辑边界。
- **派发等待语义转为 converge（异步派发默认化）**：`subagent-dispatch.md` 的 Return Acceptance 首条从"用 wait 原语等待"改为汇合点语义——只要求收敛到子代理结果（wait 原语或宿主完成信号），前台/后台由宿主决定，不再暗示同步阻塞；路由技能 `cowork-flow` 的 Delegation 段新增三条：长任务优先后台派发（完成信号即汇合点、acceptance 在汇合后）；等待期主会话可做安全区工作（只读调查、运行时目录产物、独立 worktree）；汇合前不进子代理的场地（不改 tracked 树与本任务 anchor/计划、不做当前树 git 写与生命周期转换、不新开任务）。

## [1.9.1] - 2026-10-14

### Fixed

- **CI 与发布校验在 Node 20 全红（1.9.0 发布阻断）**：`compliance-e2e` 用例嵌套的 `node --test` 断言写死了 Node 22+ 默认 reporter 的 `✔`/`﹣` 标记，CI 的 Node 20 默认输出 TAP（`ok N -`），断言恒失败——v1.9.0 的 test / windows-core / verify 各环节全红、publish 跳过、npm 未上架。嵌套 spawn 现在显式钉 `--test-reporter=spec`，Node 20 / 24 双绿。
- **Windows 上 Kimi Code hook 重复安装会双注册**：TOML basic string 把安装路径的反斜杠转义成 `\\`，归属比较此前只做单斜杠替换，`\\` 折叠成 `//` 后与单斜杠形式不相等，自身的 `[[hooks]]` 行恒不被识别——第二次安装追加第二行钩子（双次注入）。分隔符归一化改为折叠连续 `[\\/]+`，并新增"无标记旧行被接管而非复制"的回归测试。

## [1.9.0] - 2026-10-14

### Added

- **多执行者协作事实（1.9.0 主线）**：把 executor / evidence / adopt 语义补成团队协调原语，让 `.cowork-flow/tasks/` 在多 agent 场景下当共享看板。① **看板归属可见**：`task next --list --json` 与 MCP `task_list`（同一实现）每条记录新增 `executor` / `ownerSessionActive`（提示位：是否有会话绑定该任务，不裁决孤儿）/ `evidenceCoverage` / `blocked` / `blockedBy`——第二个执行者不跑 `run state` 就能看出谁在占用、有没有卡住、证据到哪了。② **依赖边**：`task next --run --title ... --depends-on <task>`（可重复，完整目录名）在创建时写入 `task.json` 的 `dependsOn`，声明期 fail-closed（目标不存在 / 自依赖 / 环分别报 `TASK-CREATE-DEPENDENCY-001/002/003`，失败不落盘；归档任务按已完成依赖解析）；start 门禁 `LIFECYCLE-DEPENDENCY-001`——依赖未全部 completed 时阻断进入 in_progress，导航 payload 与 `--run` 报同一 blocker 文本，已启动任务不受回溯影响，adopt/review/complete 不受约束。③ **交接凭证**：adopt 成功后打印 Handover 段（原执行者 → 新执行者、原基线 → 新基线、剩余未勾选 AC、证据覆盖 n/m）。契约见 `.cowork-flow/spec/contracts/task-board.md`。
- **严格任务门禁与验收闭环（10 月门禁轮）**：新建任务默认 `strict`——创建期必须声明 dev_type（`backend|frontend|fullstack|test|spec`，报 `TASK-CREATE-DEVTYPE-001`）；完成期重新校验 decision-anchor 与证据：仍有未勾选 AC 报 `LIFECYCLE-AC-001`、已声明 AC 缺 `evidence.jsonl` 记录报 `002`（唯一可被 `--allow-missing-evidence` 豁免的码）、strict 任务读不到 AC 行报 `003`、证据模块不可导入报 `004`。轻量路径 `meta.taskType=tiny`：strict+tiny 免复核凭证与 AC 证据，但只能创建期声明、`task next --list` 与 doctor 可见、不得用于触碰 runtime/门禁/spec 的任务。
- **独立复核凭证与变更指纹**：`subagent check-review` 把 cowork-check 的结论写入 `review.jsonl`，完成门禁消费——无凭证报 `LIFECYCLE-REVIEW-001`、最新一条非 pass 报 `002`、指纹过期报 `003`、来源回查失败报 `004`；接收侧守卫 `REVIEW-RECEIPT-001..007`（上下文形态 / agent 类型 / 任务绑定 / 真实 runtime 绑定回查），`by` 字段不算独立性证据。16 hex 变更指纹的分量 = 变更内容摘要 + anchor 目标与 AC 正文 + plan 摘要 + dev_type + 被引用规范正文 + implement.jsonl 摘要——改代码 / 规范 / AC 即凭证失效，需重跑复核。
- **spec-check 可遵循闭环（spec-check 后续）**：每次运行携带 `summary.classification` 分类事实（`parse-error` / `executor-failure` / `zero-declaration` / `violation` / `unchecked` / `pass` / `empty`，`--json` 可查）；整只执行器损坏单独阻断（executor-failure，`--allow-unchecked` 不豁免）；豁免明细（flag / by）在完成与归档同源打印；零声明处给出下游 AI 的指路，契约 quick-start 示例可从交付文件整段抽用。

### Changed

- **技能面收敛（16→14）**：删除 `decision-audit`（与 `adversarial-review` 是同一段 CLAIM/DOUBT 复核循环的两份文本）与 `game-design`（连同 `spec/game/` 5 个文件）；`cowork-flow-maintenance` 路由收紧为 `template/**` + `presets/**`；固定代理提示统一指向 `adversarial-review`。
- **复核报告三元组**：`subagent check-review --finding` 的每条 finding 必须携带 clause / command / negativeProof（无命令可判的显式给 null），把取证方式写进复核契约。
- **发布门禁覆盖自实例与实例路径**：`release:check` 增加 self-instance-drift（自实例镜像须与 `template/` 一致，`source:refresh` 消除漂移）与 doctor error 级阻断；PR CI 与发布共用同一门禁。
- **文档事实源收敛与契约英文化**：README / AGENTS / docs / spec 四层去重消死、统一称谓、控制面唯一化；契约正文英文化并补英文版 README；新增 `spec/contracts/error-codes.md` 汇总全部 `LIFECYCLE-*` 码（code 是稳定契约、消息文本不承诺稳定）。
- **子代理派发默认化（技能层）**：`cowork-flow` 技能新增 Delegation 段——计划并行切片逐片派发 `cowork-implement`（切片简报走运行时上下文 assignment，协议引用 `subagent-dispatch.md`）、完成前的 `cowork-check` 派发显式写入流程（不再靠撞门禁）、调研型任务可 `cowork-research` 扇出（2–3 个），协议传输细节仍由 `subagent init` 输出与 `subagent-dispatch.md` 承载、路由技能不复刻；`task-planning` 的 Parallel Work 补两条：并行项注明 dispatch（`main` | `cowork-implement`）、同一工作树内不可并行两个任务（范围门禁读取工作树全量变更，跨任务并行走独立 worktree/clone + 看板依赖边）；`agent-dispatch` 绑定步骤改为从运行时上下文读取 assignment（`goal` / `expected_output`）；`orchestration-patterns` 模式 1 使用场景改为可操作触发、模式 2 验证清单补收束与单树约束。零 runtime 代码变更。
- **安装器共享助手收敛（内部）**：9 份 `install-*.js` 的机械重复收进 `src/lib/`，可观测行为（stdout 文案、守卫顺序、退出码）逐字冻结，既有测试零修改通过。① `writeJsonAtomic` 单源化到 `install-support.js`（写前 mkdir 父目录 + 临时文件换名），zcode/qoder/dsh-preset 的本地副本删除。② 新增 `payload-install.js`（含 `pruneEmptyDir`）：claude-code/kimi-code/opencode 三份同构安装器走共享"头部 → 归属守卫 → dry-run → 物化 → 报告"骨架，三家逐字重复的句子只保留一份（守卫拒绝、强制覆盖提示、未安装提示、完成行），各自收敛为 90 行薄壳（原 129/142/169 行；kimi-code 安装器随后因插件直装扩展至 152 行）；marketplace/registry/bundle 等宿主语义留在原模块。③ kimi-hook 与 dsh-hook 的托管块手术（定位/替换/移除）共享 `upsertManagedBlock` / `removeManagedBlock`，各自的块渲染与行尾锚定保留，重复安装幂等与卸载字节复原语义不变。④ 复核收尾删除死配置点与孤儿 import（`13f3b7c`）。
- **OpenCode 插件收敛为 zcode 同形态传输 shim**：插件内 1125 行 JS 手写渲染/绑定（registry 加载、指纹计算、stage-contract、decision-anchor、运行时绑定 JSON-pair 写入）全部删除，`experimental.chat.system.transform` 改为 spawn 项目内 `inject.py --host opencode` 并原样注入其 stdout；`plugin-core.js` 只剩宿主能力胶水（传输、`shell.env` 上下文键导出、edit 期 spec-check 代理、载荷技能目录注册）。配套变化：① `inject.py --host opencode` 成为合法选项，新增 `opencode_policy`（digest 措辞保留 "every plugin transform"；无 SessionStart 事件，digest 形状由会话状态文件探测推导；stdout 即注入故 `emit_text`）。② 行为变化：主会话现在同样收到 `<workflow-state>` 注入（此前仅 delegated 子代理会话有），digest 全量/指纹判定由「进程内 per-session 集合」改为跨进程可靠的「会话激活文件探测」，workflow-state 头按统一规则携带 `session` 属性。③ `DEFAULT_CONTRACT_REGISTRY` 兜底单源化：JS 副本随渲染删除，只剩 Python 一份，`tests/test_contract_registry.py` 把它与 `contract-registry.json` 逐条锁定防漂移。④ 机器级安装载荷新增 `cowork-flow/runtime/scripts` 缓存副本（安装时从 template 刷新，zcode 同形态），项目外渲染 not-initialized 上下文；项目内始终以项目自身运行时副本为准。契约同步见 `.cowork-flow/spec/contracts/context-injection.md`。升级动作：`cwf host add opencode --force` 刷新机器级载荷后重启 OpenCode。
- **Kimi Code 插件直装**：`cwf host add kimi-code` 一步完成插件安装，不再需要 TUI 手工执行 `/plugins install`。命令物化两份载荷（`plugins/sources/` 稳定重装源 + `plugins/managed/` 宿主加载副本）并直接写入宿主注册表 `$KIMI_CODE_HOME/plugins/installed.json`——落盘格式与 Kimi Code 自身安装逻辑逐字段一致（读自宿主源码 `agent-core-v2` 的 plugin store/manifest/manager）：记录含 `id/root/source:"local-path"/enabled/installedAt/updatedAt/originalSource`，按 id 合并、保留其他插件记录与未知顶层字段、首装时间与启用状态在重装时保留、注册表不可解析时 fail-closed 且原文件不动；`--uninstall` 反向移除记录并删除两份目录（外来目录仍受守卫保护，`--force` 才覆盖）。doctor 的半装/陈旧指引与 `docs/hosts.md` 同步为 `cwf host add kimi-code [--force]`。升级动作：`cwf host add kimi-code --force` 后重启 Kimi Code。后续文档收口：`host` 组件自述与 `docs/hosts.md` 不再把 hook 描述成「插件缺位时的 fallback」——hook 即注入唯一路径（`2fa9606`、`3ba305a`）。

### Fixed

- **测试自身两处不可信缺陷（P0）**：hook 用例被 shell 会话变量干扰造成的环境假红（改为整体清空宿主环境键的隔离夹具）；删除一条在 gitignore 目录写文件的空转断言（无论规则是否生效都不可能失败），替换为可被定点破坏变红的用例。
- **`review-check` 非单调位置崩溃**：多行非 ASCII 字符串的字面量剥离保留了错误的字节偏移，导致工具整条崩溃（`73627d7`）。

## [1.8.1] - 2026-10-08

### Added

- **任务收养 `task next --run --adopt`（1.9.0 多执行者协作前置）**：为孤儿/滞留任务提供受支持的接管路径，替代手改 task.json meta。收养是独立动作（不与 review/complete/archive 链式同发）：把 `in_progress`/`review` 状态、由另一执行者占有的任务重绑到收养者（`executor`），把评审基线**重置**到收养时 HEAD（原值记入 `meta.previousBaseline`），保留状态并写审计字段 `meta.previousExecutor` / `meta.previousBaseline` / `meta.adoptedAt`，结果 code `LIFECYCLE-EXECUTOR-ADOPTED`。误用 fail-closed（`LIFECYCLE-ADOPT-001`）：planning/completed、无 executor、自我收养、process-fallback 身份、delegated 上下文、携带 create/plan 或批启动旗标全部拒绝且不改状态。start 路径"基线永不覆盖"不变量原样保留（既有测试零改动），收养是唯一经审计的显式重置路径；成功后 CLI 把会话绑定到该任务。契约见 `.cowork-flow/spec/contracts/task-adopt.md`。

### Fixed

- **`--allow-missing-evidence` 恢复独立解析**（1.8.0 遗留缺陷）：该旗标此前被误注册为 `--allow-unchecked` 的解析别名（同一 `add_argument`、dest 相同），造成两个后果——AC 证据豁免（`LIFECYCLE-AC-002` 的可豁免路径）从 CLI 不可达（`cmd_complete` 读取的属性 argparse 从不创建，恒为 False）；且传入 `--allow-missing-evidence` 会静默获得 spec-check 未检查豁免（语义错误、方向危险：本意只豁免 AC 证据，却放开了缺失/超时的 spec-check 命令）。现在两个旗标各自独立解析，parser 级与命令贯通级回归测试锁定（既有测试手工构造 Namespace 绕过 parser，正是此缺陷漏网原因）。

## [1.8.0] - 2026-10-08

### Added

- **spec-check 采纳闭环（1.8.x 主线）**：让 spec-check 机制从"存在但沉默"变为可遵循。① 零声明可见性：仓库无生效声明时 `spec-check` 文本模式输出显式事实行 `spec-check: no checks declared (<N> spec files scanned)`（与"有声明且全过"可区分），`--json` 顶层新增 `specFiles`、summary 新增 `declarations`——"没挂声明"不再与"干净通过"同形（零声明保持退出码 0：不挂命令是合法状态，但必须被看见）。② 注入契约 `SPEC_CHECKS_V1`：`contract-registry.json` 新增第 10 条（digest 2 条 + readWhen 3 条），python/zcode/opencode 三线渲染在 digest 块输出 `- SPEC_CHECKS_V1: .cowork-flow/spec/contracts/spec-checks.md`。③ `spec-checks.md` 重排为使用者核心区（何时挂 / 语法含 UTF-8 无 BOM 注意点 / 三态与门禁含零声明语义 / 时机与输出 / 归属）+ 维护者附录（宿主能力矩阵 / delegated 缺口与补偿 / digest 注入 / 开放决策），零信息丢失由独立复核逐项清点确认。④ AI 挂命令职责三处一致：契约归属段、`task-review`（User specs 逐条问"可机检吗、已挂吗" + `user_spec_review` 列「条款 → 命令」清单）、`spec-sync`（同次维护挂/刷新声明）；质量纪律四条（干净树跑出 pass / 反例能报错 / `files` 限定 / 挂后跑 spec-check 确认解析）获测试锁（`test_review_contract.py` markers）。不新增硬门禁——放权语义：主会话 AI 主动挂声明，review 报告留痕。
- **证据化完成（1.8.0 主线）**：任务完成从"流程走完"升级为"证据齐全"。decision-anchor 的验收标准（AC）成为机器可查询事实——`services/ac_evidence.py` 解析 `## 验收标准` 的勾选状态并读取任务目录 `evidence.jsonl`（追加式，`{ac, kind: test|command|manual, ref, note?, recordedAt, by}`）；完成动作新增两条稳定门禁 code：存在未勾选 AC 阻断（`LIFECYCLE-AC-001`）、已声明 AC 缺有效证据记录阻断（`LIFECYCLE-AC-002`），新旗标 `--allow-missing-evidence` 豁免后者并把 `meta.evidenceExempt`（含 `at` 与 `missing`）留在任务记录；decision-anchor 注入块在 `Acceptance:` 行后追加 `AC evidence: n/m`（缺失时附 `missing=` 列表），三线（Python / zcode shim / opencode 插件）逐字节同格式并由矩阵测试锁定；`run state --json` 与 MCP 事实视图新增 `evidenceCoverage`。无 AC 的存量任务零影响（兼容路径有测试锁定），契约见 `.cowork-flow/spec/contracts/evidence-completion.md`。

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

[Unreleased]: https://github.com/fishlikewater/cowork-flow/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/fishlikewater/cowork-flow/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/fishlikewater/cowork-flow/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.9.2...v2.0.0
[1.9.2]: https://github.com/fishlikewater/cowork-flow/compare/v1.9.1...v1.9.2
[1.9.1]: https://github.com/fishlikewater/cowork-flow/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.8.1...v1.9.0
[1.8.1]: https://github.com/fishlikewater/cowork-flow/compare/v1.8.0...v1.8.1
[1.8.0]: https://github.com/fishlikewater/cowork-flow/compare/v1.7.3...v1.8.0
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
