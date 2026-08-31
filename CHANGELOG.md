# Changelog

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

### 方向落地（阶段 0-3，详见 1.0.0 段与 docs/direction.md）

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