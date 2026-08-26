# Normalize Source Checkout Runtime Health and Task Recovery Signals

## 目标

把上一轮流程分析结论落成一次可执行优化：先补牢 source checkout runtime 健康与任务恢复信号，再让 review 诊断更可发现，最后做一刀低风险 CLI delivery 瘦身。

## 背景

- 当前 `task next --json` 显示 `no_task`，但 `task next --list` 仍能发现未归档或未收口任务，容易在“继续/恢复”场景误导 agent。
- 当前 `doctor --all` 报 root/template runtime drift：`subagent.py` 与 `session_state.py` 的 root live runtime 缺少 template 中的 ZCode session/adapter 识别。
- 最近 CI 修复暴露了 root `.cowork-flow/` 被 ignore、但部分 source bootstrap 文件又需要 clean checkout 可见的边界问题。
- 当前架构方向正确：kernel 保留状态事实、持久化、runtime context binding 和 lifecycle fact checks；具体阶段指导、诊断和模式运行时归聚焦 Skill。

## 非目标

- 不恢复 GateRegistry、`quality-review.jsonl`、自然语言规范硬门禁或 self-authored evidence。
- 不 force-track 整个 `.cowork-flow/` 目录。
- 不把多个职责合并成一个 mega Skill。
- 不引入 `obra/superpowers` 作为运行时依赖或复制其流程权威；只吸收适合本框架的 Skill 设计模式。
- 不迁出 task state machine、UnitOfWork、runtime context binding、generic lifecycle fact checks。
- 不在本任务中直接收口历史遗留任务；只提供恢复/诊断信号。

## 假设

- `template/.cowork-flow/` 是分发源；root `.cowork-flow/` 是本仓库 live runtime，其中只有明确列入 bootstrap contract 的文件应被强制跟踪。
- `task next` 是唯一流程路由入口；runtime-health 和 review-check 只读辅助，不改变生命周期状态。
- ZCode 适配已经是当前正式能力，root/template runtime 不应对 ZCode session key 或 adapter 名称产生分叉。
- `obra/superpowers` 只作为 Skill 设计参考：精准上下文、severity 分级、完成前验证、反自证/反合理化等模式需要适配到 cowork-flow 的 Skill + runtime gate 边界。

## 验收标准

- **AC-001**: source checkout 明确区分必须跟踪的 root bootstrap 文件、ignored local live runtime、template distribution source；不得 force-track 整个 `.cowork-flow/`。
- **AC-002**: 当前 `subagent.py` 与 `session_state.py` 的 root/template 漂移被处理；ZCode host/session 识别在 root/template 一致；`doctor --all` 在当前 source checkout 下通过。
- **AC-003**: `task next --json` 在会话 `no_task` 但仓库存在 active/completed-unarchived 任务时输出结构化恢复信号；`task next --list --json` 输出机器可读 JSON。
- **AC-004**: runtime-health 能只读报告 stale tasks，例如 completed 未归档、in_progress 但当前会话未绑定；报告提供下一步命令提示但不 mutate。
- **AC-005**: review 路由能发现 `review-check <task-dir> --json` advisory diagnostics；helper 继续不写 review evidence，不输出 pass/fail completion verdict。
- **AC-006**: `task.py` 的 `task next --run` delivery dispatch 抽到独立 CLI 模块，状态机与 lifecycle service 不迁出内核。
- **AC-007**: root/template/Skill replica 保持一致；focused tests、doctor、full suite 全部通过；无 `quality-review.jsonl`、GateRegistry 或自然语言硬门禁回流。
- **AC-008**: `task-review` 与 `adversarial-review` 明确吸收适配后的 Skill 经验：精准上下文、severity 分级、verification-before-completion、反自证/反合理化；review-check 仍保持 advisory，不变成 runtime gate。

## 计划

执行计划见 `.cowork-flow/plans/2026-07-30-normalize-runtime-health-task-recovery.md`。
