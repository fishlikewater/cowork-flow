# 协作约定

请与项目自身规范合并使用；如有冲突，以项目规范和用户明确指令为准。

## 0. 项目定制位

- 项目名称：`<按项目填写>`
- 主要技术栈：`<按项目填写>`
- 主要运行命令：`<按项目填写>`
- 主要测试命令：`<按项目填写>`
- 提交策略：`<由人类提交 / 允许 AI 提交 / 混合>`
- 文档语言：默认 `中文`，如需英文请整体改口径
---

## 1. 编码前先思考

**不要想当然，不要掩饰困惑，要把假设和取舍摆到台面上。**

- 先明确写出自己的假设；不确定时就提问。
- 如果需求存在多种解释，先把几种理解列出来，不要静默替用户做决定。
- 如果存在更简单的做法，要主动指出。
- 需要时可以温和地提出异议，不盲从执行。
- 一旦发现信息不清、边界模糊或描述矛盾，先停下来，说明困惑点并澄清。

## 2. 简单优先

**用最少的代码解决问题，不做投机式设计。**

- 不添加用户没有要求的功能。
- 不为一次性代码提前做抽象。
- 不加入未被要求的“灵活性”“可配置化”“通用化”。
- 不为明显不可能发生的场景堆砌错误处理。
- 如果写了很多代码，但更少代码能清楚解决问题，就应继续简化。

## 3. 外科手术式改动

**只改必须改的地方，只清理由自己改动带来的问题。**

- 不顺手重构无关模块。
- 不为“顺便优化”扩大改动面。
- 尽量贴合项目现有结构、命名和风格。
- 只删除因为本次修改而成为孤儿的代码。

## 4. 以目标驱动执行

**先定义成功标准，再循环验证直到目标达成。**

把任务改写成可验证目标：

- “修 bug” -> “先复现，再补回归验证，再修复”
- “加能力” -> “先明确输入输出，再实现，再验证”
- “重构” -> “先确认行为基线，再保证改前改后一致”

多步骤任务建议使用：

```text
1. [步骤] -> 验证：[检查项]
2. [步骤] -> 验证：[检查项]
3. [步骤] -> 验证：[检查项]
```
## 5. 先读再写

- 修改前先理解相关上下文。
- 阅读导出、直接调用方和共享工具。
- 不因为代码“看起来无关”就跳过检查。
- 如果不理解现有结构原因，先澄清或保守处理。

## 6. 遵守项目惯例

- 项目一致性高于个人偏好。
- 匹配现有代码风格、命名和组织方式。
- 不静默引入另一套风格。
- 如果认为现有惯例有害，要明确说明，而不是私自分叉。

## 7. 暴露冲突
   
- 如果发现两种模式、约定或需求互相矛盾，不要折中混合。
- 选择更近期、更稳定或测试覆盖更好的模式。
- 简要说明选择原因。
- 标记另一个冲突点，必要时建议后续清理。

## 8. 测试验证意图

- 测试应表达行为背后的业务意图，而不只是覆盖表面输出。
- 新增或修改测试时，确保它能在关键逻辑被破坏时失败。
- 修 bug 时，优先补回归验证。
- 不把“测试未运行”说成“测试通过”。

## 9. 阶段性检查

- 每完成一个重要步骤，确认当前状态。
    - 已完成什么。
    - 已验证什么。
    - 还剩什么。
    - 如果跟丢上下文，先停下来重新整理。

<!-- COWORK-FLOW:START -->
# cowork-flow 强门禁

若与项目自定义说明冲突，以项目说明和用户明确指令为准。

命令示例默认使用 macOS / Linux / Git Bash / WSL 写法；Windows cmd / PowerShell 中使用 `.\.cowork-flow\run.cmd <command>` 替代 `./.cowork-flow/run <command>`。

1. 每次新会话、重新接手任务、或上下文明显丢失时，先执行 `./.cowork-flow/run resume`，再进入 `.agent/skills/start`。
2. 执行 `start` 时，先读 `AGENTS.md`、`.cowork-flow/workflow.md` 和 `resume.py` 的输出，不要直接编码。
3. 任何会修改仓库文件的请求，都必须先分级为 `L0` / `L1` / `L2`，再进入对应流程；不要把“很小”当成可以绕过流程的理由。
4. `L1` / `L2` 行为变更必须先有 `change -> spec -> plan`；`L2` 还必须有 `design.md`，然后才能进入实现。
5. 实现前必须把任务上下文写入 `.cowork-flow/tasks/<task>/implement.jsonl`、`check.jsonl`、`debug.jsonl`，并在 `start` 之后再改代码。
6. 执行 plan 时，如存在可独立并行任务，且 `.cowork-flow/config.yaml` 中已设置 `agent_team.enabled: true`，可使用 `./.cowork-flow/run agent-team prepare <task-dir> --plan <plan-file>` 与 `agent-team next` 生成并执行 agent-team 调度；主 agent 仍负责协调、审阅和状态回写。
7. 收尾前必须跑验证、同步 plan / task / change 状态，完成 `finish-work` 检查，再按项目策略记录 session。
8. 多轮对话、长任务恢复或上下文压缩后，先运行 `./.cowork-flow/run resume` 并查看 `RESUME CHECKLIST`；只读取清单列出的 PRD、当前 plan 和 jsonl 引用，不要全量重读 `.cowork-flow/spec/` 或历史 journal。

Use the `.agent/skills/start` skill when starting a new session to:
- Initialize your developer identity
- Understand current project context
- Enforce the task workflow gates before any implementation

Use `@/.cowork-flow/` to learn:
- Development workflow (`workflow.md`)
- Project structure guidelines (`spec/`)
- Developer workspace (`workspace/`)

Use `@/.agent/skills/` for reusable local skills.

Keep this managed block so cowork-flow updates can refresh the instructions.

<!-- COWORK-FLOW:END -->
