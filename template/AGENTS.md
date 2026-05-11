# 协作约定

请与项目自身规范合并使用；如有冲突，以项目规范和用户明确指令为准。

> 本文件是 starter 模板。复制到新项目后，必须先把其中的占位内容替换成项目真实约束。

## 0. 项目定制位

- 项目名称：`<按项目填写>`
- 主要技术栈：`<按项目填写>`
- 主要运行命令：`<按项目填写>`
- 主要测试命令：`<按项目填写>`
- 提交策略：`<由人类提交 / 允许 AI 提交 / 混合>`
- 文档语言：默认 `中文`，如需英文请整体改口径
- Skill 策略：默认不要在项目接入时修改 `.agents/skills/**/SKILL.md`；项目事实写入本文件、`.trellis/workflow.md`、`.trellis/config.yaml` 和 `.trellis/spec/`

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

## 5. 规格与执行协作

**有行为变化的任务，统一采用 `OpenSpec + superpowers + Trellis` 协作流。**

- `L0`：纯文档、测试、重构、工具调整，可直接进入 Trellis 执行。
- `L1/L2`：涉及功能行为、接口契约、规划链路或架构边界变化时，先补齐 OpenSpec。
- 方案讨论使用 `superpowers:brainstorming`，开发计划必须显式使用 `superpowers:writing-plans`。
- Trellis 负责执行过程、上下文同步与 journal 留痕。

### Skill 使用约束

- `SKILL.md` 应描述可复用的流程、判定规则、检查点与项目事实读取方式，不应写成某次任务的临时施工单。
- 接入具体项目时，默认不修改 reusable skills；技术栈、测试命令、提交口径、目录规范等项目事实应写入 `AGENTS.md`、`.trellis/workflow.md`、`.trellis/config.yaml` 或 `.trellis/spec/`。
- 除非该 skill 明确就是当前项目专用能力，否则不要写入具体业务模块名、一次性任务复选项或缺乏泛化价值的文件路径。
- 需要举例时，优先使用目录类型、场景类型或占位路径，而不是直接写某个项目独有文件。
- 只有用户明确要求创建或修改项目专用 skill 时，才编辑 `SKILL.md`；修改时保持原文件语言一致：英文文件追加英文，中文文件追加中文；如需切换语言，应整体统一改写。

### 开发计划状态同步

- 如果任务存在 `docs/superpowers/plans/*.md`，该计划文件视为执行期活文档，而不是静态附件。
- 计划中的任务 / 步骤应使用 checkbox；完成且验证通过后，应及时从 `- [ ]` 改为 `- [x]`。
- 未完成或阻塞步骤保持未勾选，并在 `当前执行状态` 中补充日期、原因、当前批次或下一步。
- 在宣称“已完成”、归档任务、记录 session 或回写 OpenSpec / Trellis 状态前，必须先同步计划勾选状态、当前执行状态与最新验证 / 评审结论。

## 6. 提交与验证口径

- 业务代码由当前会话约定的执行者提交。
- `.trellis/workspace`、`.trellis/tasks` 等元数据优先由脚本自动提交。
- 不要在未验证的情况下声称“已完成”“已通过”“可交付”。

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

Use the `/trellis:start` command when starting a new session to:
- Initialize your developer identity
- Understand current project context
- Read relevant guidelines

Use `@/.trellis/` to learn:
- Development workflow (`workflow.md`)
- Project structure guidelines (`spec/`)
- Developer workspace (`workspace/`)

Keep this managed block so 'trellis update' can refresh the instructions.

<!-- TRELLIS:END -->
