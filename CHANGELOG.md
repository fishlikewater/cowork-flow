# Changelog

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