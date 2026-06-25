# Brainstorming: 流程验证问题根因修复 + 模板同步

## Goal

1. 根因修复上一轮验证发现的问题
2. 将 `game-design` skill 同步到模板目录

## 根因分析

### 问题 1: `init-context` 的 `dev_type` 不支持 `spec`

- 根因：`init-context` 的 argparse 只声明 `backend|frontend|fullstack|test|docs`
- 范围：新增 `spec` 类型，自动添加 `.cowork-flow/spec/` 引用到 implement.jsonl

### 问题 2: `init-context` 覆写已有 jsonl

- 根因：`cmd_init_context` 无条件调用 `_write_jsonl` 覆盖，不检查已有内容
- 影响：用户自己写的 implement.jsonl 被覆盖销毁
- 修复：检测文件已存在时询问或追加，不直接覆盖

### 问题 3: TDD gate 对纯文档任务的交互不够友好

- 根因：PRD 不含 `NON_BEHAVIOR_MARKERS`（如 "纯文档"、"docs-only"）时强制要求 TDD，但首次失败信息只提示缺 tdd.jsonl 文件，不提示可以加豁免
- 修复：失败信息中增加 "或添加 type=exemption 的豁免记录" 的提示

### 问题 4: 中文 JSON 在 Windows git bash 编码异常

- 根因：`cat` / `echo` 管道 JSON 到 Python 时，bash 的 UTF-8 编码与 Windows 控制台不兼容
- 范围：非代码 bug，避免在 shell 命令中内联中文 JSON
- 修复：无——这是 terminal 环境问题，通过 `Write` 工具写入不受影响

### 问题 5: 游戏 skill 未同步到模板

- 根因：模板目录不在 `init-context` / `writing-plans` 等流程覆盖范围内
- 修复：`.cowork-flow/template/` 或等效的模板目录同步一份
