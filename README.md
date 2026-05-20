# cowork-flow

cowork-flow 是一个用于新项目初始化协作流程的模板仓库。它把项目说明、任务流转、规格治理、开发计划和会话记录放在一套可复制的目录结构里，帮助团队在项目早期就建立清晰的工作闭环。

这个仓库本身不绑定具体技术栈，也不提供业务代码脚手架。它提供的是协作与治理基础设施：你可以把 `template/` 复制到目标项目中，再按目标项目的真实情况补充技术栈、验证命令、目录规范和提交策略。

## 适用场景

- 新项目需要建立 `AGENTS.md`、任务流、规格文档和开发记录。
- 已有项目希望补上一套轻量的协作流程，但不想引入完整工程脚手架。
- 团队希望把需求澄清、规格变更、实现计划、验证和会话记录串成闭环。

## 不适用场景

- 只需要一个语言或框架脚手架，例如 React、Spring Boot、Rust crate 模板。
- 项目已经有成熟且完整的任务、规格和协作系统，并且不希望引入新的目录约定。
- 只想复制某一段提示词，而不需要维护项目级流程文件。

## 仓库结构

```text
.
├── README.md
└── template/
    ├── AGENTS.md
    ├── .agent/
    │   └── skills/
    └── .cowork-flow/
        ├── config.yaml
        ├── workflow.md
        ├── scripts/
        ├── spec/
        ├── changes/
        ├── plans/
        ├── tasks/
        └── workspace/
```

## 模板内容

`template/AGENTS.md`
项目级协作入口，包含编码前思考、简单优先、外科手术式改动、验证优先等基础原则。接入项目后，应把项目名称、技术栈、运行命令、测试命令和提交策略补齐。

`template/.agent/skills/`
本地技能入口，覆盖开始工作、收尾验证、记录 session、更新规范、跨层检查等常见协作动作。这里的 skill 应保持通用，不承载某个业务项目的一次性细节。

`template/.cowork-flow/`
工作流目录，包含流程说明、任务状态、开发者工作区、项目规范、行为变更规格、实现计划和辅助脚本。`.cowork-flow/config.yaml` 用于填写项目自己的 lint、build、test 等验证命令。

`template/.cowork-flow/spec/`
项目规范目录，预置了 backend、frontend 和 guides 三类说明。接入时应按项目事实保留、改写或删除对应规范。

`template/.cowork-flow/changes/`
由 `change.py` 管理 proposal、design、behavior specs 和归档，不维护实现 checklist。

`template/.cowork-flow/plans/`
保存可执行步骤、验证方式和执行状态。

## 快速开始

使用 CLI 把模板内容安装到目标项目根目录：

```bash
npx cowork-flow init ./my-project
```

也可以先全局安装：

```bash
npm install -g cowork-flow
cowork-flow init ./my-project
```

初始化后优先完成这些配置：

1. 更新 `AGENTS.md` 中的项目名称、技术栈、命令和提交策略。
2. 更新 `.cowork-flow/config.yaml` 中的验证命令。
3. 更新 `.cowork-flow/workflow.md` 中与项目流程不一致的门禁、分级和完成定义。
4. 按项目实际情况调整 `.cowork-flow/spec/`，删除不存在的 frontend、backend 或行为变更场景。
5. 按团队实践使用 `.cowork-flow/changes/` 管理规格变更，使用 `.cowork-flow/plans/` 管理实现计划和验证状态。

## CLI 使用

查看命令：

```bash
npx cowork-flow --help
```

初始化到新项目：

```bash
cowork-flow init ./my-project
```

`init` 会询问你是否已经安装了 Superpowers skills。选择未安装时，会把内置的 `.superpowers/` 技能复制到目标项目的 `.agent/skills/` 下。
在非交互环境里，这一步会自动跳过询问并默认视为已安装。

初始化到当前项目：

```bash
cowork-flow init .
```

默认不会覆盖已有文件。需要预览时使用：

```bash
cowork-flow init ./my-project --dry-run
```

需要明确覆盖已有文件时使用：

```bash
cowork-flow init ./my-project --force
```

升级 CLI 本身：

```bash
cowork-flow update
npm install -g cowork-flow@latest
```

同步已初始化项目中的模板脚本和本地技能：

```bash
cowork-flow sync .
cowork-flow sync . --dry-run
```

`sync` 默认刷新 `.agent/skills/`、`.cowork-flow/scripts/` 和 `AGENTS.md` 中的 `<!-- COWORK-FLOW:START --> ... <!-- COWORK-FLOW:END -->` 托管块，保留 `AGENTS.md` 托管块之外的项目自定义内容。`.cowork-flow/config.yaml`、`.cowork-flow/workflow.md`、`.cowork-flow/spec/`、任务、计划、变更和 workspace 记录默认受保护。只有明确传入 `--force` 时才整文件覆盖保护文件。

## 常用入口

模板内置统一入口来运行 Python 工作流脚本：

- macOS / Linux / Git Bash / WSL：`./.cowork-flow/run`
- Windows cmd / PowerShell：`.\.cowork-flow\run.cmd`

入口会按 `COWORK_FLOW_PYTHON`、`PYTHON`、`python3`、`python`、`py -3`
的顺序查找 Python 3.8+ 解释器，避免不同环境中 `python` / `python3`
命令不一致的问题。

下面示例使用 macOS / Linux 写法；Windows 原生命令行中把
`./.cowork-flow/run` 替换为 `.\.cowork-flow\run.cmd`。

初始化或查看开发者身份：

```bash
./.cowork-flow/run get-developer
./.cowork-flow/run init-developer <developer-name>
```

查看当前上下文：

```bash
./.cowork-flow/run get-context
./.cowork-flow/run task list
```

创建并验证行为变更：

```bash
./.cowork-flow/run change create <slug>
./.cowork-flow/run change validate <slug>
```

创建并启动任务：

```bash
./.cowork-flow/run task create "<title>" --slug <task-name>
./.cowork-flow/run task start <task-dir>
```

记录 session：

```bash
./.cowork-flow/run get-context --mode record
./.cowork-flow/run add-session \
  --title "<session-title>" \
  --commit "<commit-or-handoff-ref>" \
  --summary "<summary>"
```

## 接入原则

- 以目标项目事实为准，不把模板内容当成项目事实。
- 保留有价值的流程骨架，删除目标项目不存在的场景。
- 项目差异写入 `AGENTS.md`、`.cowork-flow/workflow.md`、`.cowork-flow/config.yaml` 和 `.cowork-flow/spec/`。
- 不为了替换项目命令或一次性任务而改写通用 skill。
- README 只说明项目定位和使用方式；具体协作规则应沉淀在模板内对应文件中。

## 维护建议

更新模板时，优先确认这几件事：

- `template/` 中的目录结构和 README 描述一致。
- 新增流程规则有明确承载位置，不散落在多个文件里互相冲突。
- 脚本入口和文档中的命令保持一致。
- 通用 skill 保持可复用，项目专用规则不混入 starter 模板。
- 示例命令尽量保持最小可用，避免把模板写成某个具体项目的实现方案。

## 发布流程

CI 会运行 Node CLI 测试、npm pack 内容检查和现有 Python 模板测试。发布到 npm 通过 GitHub Actions 的 `Publish npm Package` workflow 完成，需要在仓库 secrets 中配置 `NPM_TOKEN`。
