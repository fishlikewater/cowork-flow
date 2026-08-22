# Changelog

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