# Workflow Starter

Workflow Starter 是一个用于新项目初始化协作流程的模板仓库。它把项目说明、任务流转、规格治理、开发计划和会话记录放在一套可复制的目录结构里，帮助团队在项目早期就建立清晰的工作闭环。

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
    ├── .agents/
    │   └── skills/
    ├── .trellis/
    │   ├── config.yaml
    │   ├── workflow.md
    │   ├── scripts/
    │   ├── spec/
    │   ├── tasks/
    │   └── workspace/
    ├── docs/
    │   └── superpowers/
    └── openspec/
```

## 模板内容

`template/AGENTS.md`
项目级协作约定入口，包含编码前思考、简单优先、外科手术式改动、验证优先等基础原则。接入项目后，应把项目名称、技术栈、运行命令、测试命令和提交策略补齐。

`template/.trellis/`
Trellis 工作流目录，包含流程说明、任务状态、开发者工作区、项目规范和辅助脚本。`.trellis/config.yaml` 用于填写项目自己的 lint、build、test 等验证命令。

`template/.trellis/spec/`
项目规范目录，预置了 backend、frontend 和 guides 三类说明。接入时应按项目事实保留、改写或删除对应规范。

`template/.agents/skills/`
本地技能入口，覆盖开始工作、收尾验证、记录 session、更新规范、跨层检查等常见协作动作。这里的 skill 应保持通用，不承载某个业务项目的一次性细节。

`template/openspec/`
OpenSpec 目录，用于管理行为变更的 proposal、spec、tasks 和 archive。只有项目实际使用 OpenSpec 时才需要保留并配置。

`template/docs/superpowers/`
设计稿与开发计划输出目录。复杂任务可以在这里沉淀设计说明和可执行计划。

## 快速开始

把模板内容复制到目标项目根目录：

```powershell
$target = "C:\path\to\project"
Get-ChildItem -LiteralPath .\template -Force | Copy-Item -Destination $target -Recurse -Force
```

复制后优先完成这些配置：

1. 更新 `AGENTS.md` 中的项目名称、技术栈、命令和提交策略。
2. 更新 `.trellis/config.yaml` 中的验证命令。
3. 更新 `.trellis/workflow.md` 中与项目流程不一致的门禁、分级和完成定义。
4. 按项目实际情况调整 `.trellis/spec/`，删除不存在的 frontend、backend 或 OpenSpec 场景。
5. 检查 `openspec/config.yaml` 是否符合项目上下文；如果项目不用 OpenSpec，可以删除 `openspec/` 并同步调整流程说明。

## 常用入口

初始化或查看开发者身份：

```bash
python3 ./.trellis/scripts/get_developer.py
python3 ./.trellis/scripts/init_developer.py <developer-name>
```

查看当前上下文：

```bash
python3 ./.trellis/scripts/get_context.py
python3 ./.trellis/scripts/task.py list
```

创建并启动任务：

```bash
python3 ./.trellis/scripts/task.py create "<title>" --slug <task-name>
python3 ./.trellis/scripts/task.py start <task-dir>
```

记录 session：

```bash
python3 ./.trellis/scripts/get_context.py --mode record
python3 ./.trellis/scripts/add_session.py \
  --title "<session-title>" \
  --commit "<commit-or-handoff-ref>" \
  --summary "<summary>"
```

## 接入原则

- 以目标项目事实为准，不把模板内容当成项目事实。
- 保留有价值的流程骨架，删除目标项目不存在的场景。
- 项目差异写入 `AGENTS.md`、`.trellis/workflow.md`、`.trellis/config.yaml` 和 `.trellis/spec/`。
- 不为了替换项目命令或一次性任务而改写通用 skill。
- README 只说明项目定位和使用方式；具体协作规则应沉淀在模板内对应文件中。

## 维护建议

更新模板时，优先确认这几件事：

- `template/` 中的目录结构和 README 描述一致。
- 新增流程规则有明确承载位置，不散落在多个文件里互相冲突。
- 脚本入口和文档中的命令保持一致。
- 通用 skill 保持可复用，项目专用规则不混入 starter 模板。
- 示例命令尽量保持最小可用，避免把模板写成某个具体项目的实现方案。
