# cowork-flow

> 让 AI 遵循工作流的协作框架

cowork-flow 是一套可复制的协作流程模板，帮助你在项目中建立 AI 友好的工作闭环。它不涉及具体技术栈，只关注：需求澄清 → 计划 → 实现 → 验证 → 交付。

## 快速开始

```bash
# 1. 安装 CLI
npm install -g cowork-flow

# 2. 在目标项目中初始化
cd your-project
cowork-flow init . --platform codex --developer your-name

# 3. 查看下一步
./.cowork-flow/run task next
```

初始化后会自动生成：
- `AGENTS.md` — AI 协作约定
- `.codex/agents/` — 固定角色定义
- `.cowork-flow/workflow.md` — 工作流说明
- `.cowork-flow/spec/` — 项目规范

## 核心流程

```
changes → brainstorming → read spec → plan → tasks → implement → check → complete
```

| 阶段 | 说明 | 触发时机 |
|------|------|----------|
| **brainstorming** | 需求澄清、方案讨论 | 需求不清晰、多方案取舍 |
| **writing-plans** | 编写实现计划 | 多步骤实现任务 |
| **cowork-research** | 调研 | 需要收集信息 |
| **cowork-implement** | 实现 | 编码任务 |
| **cowork-check** | 检查 | 代码验证 |

## 适用场景

✅ 新项目需要 AI 协作规范  
✅ 已有项目希望补上轻量工作流  
✅ 团队希望 AI 遵循固定的需求→实现→验证闭环  

❌ 只需要语言/框架脚手架（React、Spring Boot 等）  
❌ 已有成熟的协作系统  

## 仓库结构

```
cowork-flow/
├── README.md                 # 当前文件
├── bin/                      # CLI 入口
├── src/                      # CLI 源码
└── template/                 # 初始化模板
    ├── AGENTS.md             # AI 协作约定
    ├── CLAUDE.md             # Claude Code 入口
    ├── .codex/               # Codex 配置
    │   ├── agents/           # 固定角色
    │   ├── hooks/            # 状态注入
    │   └── config.toml       # 项目配置
    ├── .claude/              # Claude Code 配置
    ├── .opencode/            # OpenCode 配置
    ├── .agents/skills/       # 技能定义
    └── .cowork-flow/         # 工作流核心
        ├── workflow.md       # 工作流说明
        ├── config.yaml       # 项目配置
        ├── scripts/          # 辅助脚本
        ├── spec/             # 项目规范
        ├── tasks/            # 任务目录
        └── workspace/        # 开发者工作区
```

## 技能一览

| 技能 | 用途 | 触发时机 |
|------|------|----------|
| `start` | 启动/恢复主会话 | 开始工作前 |
| `brainstorming` | 需求澄清 | 需求不清晰 |
| `writing-plans` | 编写计划 | 多步骤实现 |
| `before-dev` | 编码前准备 | 写代码前 |
| `check` | 检查实现 | 实现完成后 |
| `finish-work` | 完成任务 | 检查通过后 |
| `continue` | 继续会话 | 压缩上下文后 |
| `break-loop` | 打破循环 | 反复失败时 |
| `party-mode` | 圆桌讨论 | 需要多角度建议 |
| `tdd` | 测试驱动开发 | 行为变更 |

## 配置说明

### 项目配置 (.cowork-flow/config.yaml)

```yaml
project:
  name: your-project
  language: Python/Node.js
  test_command: npm test
  lint_command: npm lint

workflow:
  allow_ai_commit: true
  language: zh
```

### 提交策略

- `allow: true` — AI 可以直接提交
- `require_review: true` — 提交前需要人工审核
- `forbid: false` — 禁止 AI 提交

## 进阶用法

### 多平台支持

```bash
# 初始化所有平台
cowork-flow init . --platform all

# 初始化特定平台
cowork-flow init . --platform codex,claude-code
```

### 任务管理

```bash
# 创建任务
./.cowork-flow/run task create

# 查看下一步
./.cowork-flow/run task next

# 开始任务
./.cowork-flow/run task start <task-dir>

# 完成任务
./.cowork-flow/run task complete <task-dir>

# 归档任务
./.cowork-flow/run task archive <task-name>
```

### 自定义规范

将项目规范写入 `.cowork-flow/spec/core/`：
- `backend/` — 后端架构规范
- `frontend/` — 前端架构规范
- `entry.md` — 入口分类规范
- `lifecycle.md` — 生命周期规范

## 开发本框架

```bash
# 运行测试
npm test

# 运行模板测试
npm run test:template

# 检查打包内容
npm run pack:check

# 运行全部验证
npm run test:all
```

## License

MIT
