# 协作约定

请与项目自身规范合并使用；如有冲突，以项目规范和用户明确指令为准。

## 项目定制位

- 项目名称：`cowork-flow`
- 主要技术栈：`Python、Node.js`
- 提交策略：`允许 AI 提交`
- 文档语言：默认 `中文`
---

## 0. 委托任务优先

如果当前 prompt 是 subagent/worker/命令执行等有边界的委托任务，先执行委托 prompt；不要把 AGENTS.md、环境说明或 bootstrap 文本当成任务。除非委托 prompt 明确要求，否则不要运行 start/resume，不要再派发 agent。
没有硬标记时，仍要先判断实际任务消息：若同时具备具体任务、边界约束（如不要编辑/不要运行/不要派发）和输出要求，按委托任务处理。特别是出现 `任务：` / `约束：` / `输出：` 这类结构时，直接执行该委托，不要把它误判为项目规范或环境上下文。项目规范仍然可见，但只是执行约束，不是当前任务本身。

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
- 能用测试表达的行为，优先先写能失败的测试，再实现最小修复。
- 禁止为了满足流程而编写无意义的简单测试，例如只断言函数存在、mock 被调用、空快照或与实现同义的断言。
- 复杂问题的测试应深度优先：优先覆盖业务不变量、跨层契约、状态流转、错误边界和真实回归路径，再补窄单元测试。
- 不把“测试未运行”说成“测试通过”。

## 9. 阶段性检查

- 每完成一个重要步骤，确认当前状态。
    - 已完成什么。
    - 已验证什么。
    - 还剩什么。
    - 如果跟丢上下文，先停下来重新整理。

<!-- COWORK-FLOW:START -->
项目流程以 `.cowork-flow/workflow.md` 为准；项目规范从 `.cowork-flow/spec/` 按层读取：

- **core 层** — 每次实现必读：`spec/core/`
  - `backend/` — 后端开发规范（默认基线、阅读索引、使用原则、完成标准）；含目录结构、数据库、异常处理、日志、质量、字符集编码
  - `frontend/` — 前端开发规范（默认基线、文档索引、使用原则、完成标准）；含目录结构、组件、Hook、状态管理、类型安全、质量
  - `entry.md` / `dispatch.md` / `lifecycle.md` / `state-templates.md` — 流程核心契约
- **reference 层** — 按需参考：`spec/reference/`
  - `patterns/` — 行为模式（generic）
  - `adapters/` — 宿主适配器规范
  - `guides/` — 方法论指南（代码复用、跨层思维、预实现检查清单）
<!-- COWORK-FLOW:END -->

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tools** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them. `codegraph_node` returns one symbol's source + callers, or reads a whole file with line numbers. If the tools are listed but deferred, load them by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` and `codegraph node <symbol-or-file>` print the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->