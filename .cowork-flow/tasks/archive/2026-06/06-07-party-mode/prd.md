# Add Manual Party Mode Workflow

## 背景

`cowork-flow` 已有 `brainstorming`、固定 `cowork-*` 子代理和 runtime-context 派发协议。用户希望新增一个可手动调用的 Party Mode，让真实子代理从不同角度独立讨论，并在有限轮次内产出有价值结论。

## 目标

- 新增 `party-mode` 手动入口，优先作为 skill 使用。
- 定义真子代理圆桌的主持流程、角色选择、默认轮次上限、继续条件和停止条件。
- 区分可配置默认值、安全闸和 schema 核心字段，确保灵活性不破坏治理边界。
- 固化每个子代理和主会话的最小输出 schema，允许扩展字段，但确保讨论有证据、有取舍、有验收信号。
- 保持正式实现/检查边界：Party Mode 只给 advisory 结论，不替代 `cowork-implement` / `cowork-check`。
- 文档表达简洁、可检索；代码改动保持小而清晰。

## 非目标

- 不创建完整 BMAD runtime。
- 不做子代理互相派发或自协调。
- 不改任务生命周期语义。
- 不把 Party Mode 默认插入每个小任务。

## 关键假设

- 用户手动调用 Party Mode，默认不自动插入所有任务。
- Codex host 可以通过 adapter 暴露真实子代理派发、等待、列出和关闭能力。
- 纯 CLI 无法直接调用 Codex host tool，因此 CLI 只能作为报告或状态辅助。
- 真子代理讨论的价值来自独立证据和分歧收敛，而不是角色口吻。
- `max_agents=3` 与 `max_rounds=3` 是默认配置，项目或单次调用可在安全闸内覆盖。

## 范围边界

### In Scope

- root/template 新增 `party-mode` skill。
- 必要时补充 README 或 workflow/spec 中的 host-neutral 说明。
- 如实现 CLI，新增只负责报告/状态的 `party` 命令，不直接绑定 Codex tool。
- 更新测试，覆盖 skill 集合、root/template parity、advisory 边界和轮次/停止条件措辞。

### Out of Scope

- 业务项目特定角色库。
- 长期会话数据库或 Web UI。
- 自动在所有 brainstorming 中启动 Party Mode。

## 验收标准

- 用户可以通过 `party-mode` skill 手动请求真实子代理讨论。
- skill 明确要求第 1 轮使用新鲜子上下文，且不同子代理互不可见。
- skill 明确 `max_agents=3`、`max_rounds=3` 是默认值，并说明配置覆盖优先级。
- skill 明确继续/停止条件可被收紧但不可删除。
- 每个子代理最小输出 schema 包含 `position/evidence/risk/tradeoff/rejected_option/acceptance_signal/what_would_change_my_mind`，允许扩展字段。
- 主会话最小输出 schema 包含 `consensus/disagreements/evidence/decision/rejected_options/acceptance_criteria/open_questions/stop_reason`，允许扩展字段。
- 文档明确 Party Mode 为 advisory，不能推进任务状态，也不能替代 formal implement/check。
- root/template/Claude skill mirror 或同步规则保持一致。
- 相关 Python/Node 测试、`doctor --subagent-safety` 和 `git diff --check` 通过。

## 相关文件

- `.agents/skills/party-mode/SKILL.md`
- `template/.agents/skills/party-mode/SKILL.md`
- `.claude/skills/party-mode/SKILL.md`
- `template/.claude/skills/party-mode/SKILL.md`
- `.cowork-flow/scripts/run.py`
- `.cowork-flow/scripts/party.py`
- `README.md`
- `.cowork-flow/workflow.md`
- `.cowork-flow/spec/subagent-dispatch.md`
- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`

## 验证方式

- `python -m unittest discover -s tests -p "test_cowork_agents.py" -v`
- `python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py" -v`
- `.\.cowork-flow\run.cmd doctor --subagent-safety`
- `npm run test:all`
- `git diff --check`
