# DSH 上游能力提案：agent-scope patch 与 workspace 级组合

> 状态：提案草稿。本文件只记录事实与设想的衔接点，不代表已实现或已获上游承诺。
> 对应实现：`install-dsh-hook`（cowork-flow 0.0.52+）当前把 workflow-state 插件注册到 `$DSH_HOME/cordis.patch.yml`，组合可验证但注入不可达。

## 背景

cowork-flow 希望在 DeepSeek Harness（DSH）中为项目会话注入实时的 `<workflow-state>` 状态块（与 Codex / Claude Code 的 hook 同构），且**不要求用户切换到专门的 agent preset**（preset 是整套 agent 组成的替换，成本高）。

现状两条路径：

1. **agent preset**（已生效）：`agent.cordis.yml` 挂载到每个会话的 agent scope，行内插件（systemPrompt section）可被提示组装收集。
2. **home patch**（组合可达、注入不可达）：`$DSH_HOME/cordis.patch.yml` 的 `insert:` patch 在启动时组合进 host 树（`dsh --dump-config` 可见），但实测 agent 提示装配**不收集 host 层 section**。

## 实测结论（DSH 0.1.1-rc.1）

- `cordis.patch.yml` 是 patch 语义：不带 id 的 `insert:` 列表项在顶层插入新行；普通 `- id: x` 会被当作“修改既有 entry”，未知 id 报 `entry not found`。
- 组合后的顶行（host scope）不会出现在 agent 系统提示尾部；预设行（agent scope）会出现。
- 会话记录（持久化 JSONL 头部）固定 `agentPreset`；作用域链为 host → standing(per preset) → agent。

## 提案：两个可选能力（任一落地即可解锁）

### P1. agent-scope patch（推荐，最小）

- 允许 `cordis.patch.yml`（或新增 `agent.patch.yml`）中的行目标为 agent scope：例如支持 `scope: agent` 字段，使插入行对所有预设的 agent 生效。
- 验收信号：home patch 插入 `scope: agent` 的 systemPrompt section 后，新会话提示尾部出现该 section；`dsh --dump-config` 展示 scope 标注。

### P2. workspace（项目级）组合发现

- 在 `--patch` overlays 与 home patch 之外，支持按工作区自动加载组合文件，例如 `<workspace>/.dsh/cordis.patch.yml` 或 `agent.cordis.yml` 项目标记。
- 价值：cowork-flow `init --platform dsh` 可直接把 hook 行写入项目（随库提交/同步），机器无关、按项目开关、天然满足“未安装即忽略”。
- 验收信号：新会话在含该文件的 cwd 中注入对应 section，缺文件时静默无感。

## 附带建议

- 为系统提示 section 提供 scope 维度（host / standing / agent）的文档化语义，并让 `--dump-config` 输出 scope 归属，降低未来集成方试错成本。
- 可选 per-project 开关：插件行可检查项目标记（如 `.dsh/hook.off`），把机器级注册变成按项目可关的默认静默。

## 相关材料

- cowork-flow：`install-dsh-hook` 命令（`src/commands/install-dsh-hook.js`）、`presets/dsh/plugins/workflow-state.js`、`README.md` DSH 接入小节。
- 验证命令：`dsh --profile web --dump-config`（组合可见性）；新会话询问系统提示是否含 `cowork-flow-workflow-state` 段（注入可见性）。

## 影响面

- 不改动既有的 preset 替换模型；P1/P2 都是可选叠加能力，低风险。
- 对 cowork-flow：落 P1 后 host patch 路径直接生效；落 P2 后可把 hook 随项目交付，机器级安装降级为可选。
