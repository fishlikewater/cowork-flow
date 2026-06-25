# 游戏开发流程适配实施计划

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** 在 cowork-flow 中补充游戏开发领域知识覆盖，创建 `game-design` skill + `.cowork-flow/spec/game/` 规范目录。
**Architecture:** 纯内容任务。skill 在 IDE/CLI 中可调用（与现有 `tdd`、`python-design` skill 同级）；spec 加在 `.cowork-flow/spec/game/` 下，与 `backend/`、`frontend/` 同层，不修改现有流程或代码。
**Verification:** `ls` 确认文件存在，`head` 确认内容完整，`cat` 确认 frontmatter 正确。
**Execution Strategy:** 串行。skill 和 spec 应该内容一致，不存在并行收益。无行为变更，无需 TDD。

## 1. 创建 `game-design` skill

- 创建 `.claude/skills/game-design/SKILL.md`。
- 内容覆盖：什么时候触发、如何用于游戏开发任务、调用 spec/game/ 指南的建议。
- 验证：确认 frontmatter（name, description）符合现有 skill 模板，可被 skill 工具识别。

## 2. 创建 `.cowork-flow/spec/game/` 规范目录

创建以下 4 个指南文件，风格匹配 `.cowork-flow/spec/backend/` 的同级文件：

### 2.1 `index.md` — 游戏开发规范概述

- 说明 spec/game/ 目录职责
- 列举引擎选型参考、资产约定、性能基线、多人约定
- 引用 spec 目录索引

### 2.2 `engine-guidelines.md` — 引擎与架构约定

- ECS vs OOP 选型考量
- 帧同步 vs 状态同步
- 场景/关卡组织约定
- 插件与第三方库取舍原则

### 2.3 `asset-pipeline.md` — 资产管线约定

- 资产文件组织结构（Assets/ 下的目录布局推荐）
- 构建管线阶段（原始资产 → 烘焙 → 运行时格式）
- LOD 策略基础
- 资产版本控制策略（Git LFS 或等同方案）

### 2.4 `performance-guidelines.md` — 性能分析约定

- 帧率目标基线（30/60/120fps）
- 内存预算与监控
- GC 压点与对象池
- 渲染批次与 Draw Call 基础
- 性能分析工作流（profiling → 定位热点 → 优化 → 回归验证）

### 2.5 `multiplayer-guidelines.md` — 多人游戏约定

- 网络模型（P2P vs 权威服务器）
- 同步策略（状态同步 vs 帧同步 vs 预测回滚）
- 延迟补偿策略
- 房间/匹配服务基础约定

- 验证：每个文件有 frontmatter（如有）或有清晰的标题结构，内容与现有 spec 风格一致。

## 3. 集成验证

- 确认 `.claude/skills/game-design/SKILL.md` 可读
- 确认 `.cowork-flow/spec/game/` 至少 5 个文件（index + 4 指南）
- 确认无现有文件被修改，无新依赖引入
- 运行 `git diff --stat` 确认新增范围
- 运行 `task review`（如流程允许）

## 验收映射

| AC | 覆盖步骤 |
|----|---------|
| AC-01: game-design skill 可调用，覆盖架构/资产/性能/多人 | 步骤 1 |
| AC-02: spec/game/ 至少 4 个指南 | 步骤 2.1–2.5 |
| AC-03: 现有流程不破坏 | 步骤 3 |
| AC-04: 不破坏 spec 结构和 contract digest | 步骤 3 |

## 风险

- `game-design` skill 注册后需 Claude Code 重新加载 skill 列表才可见（启动新 session）。
- 暂不影响 before-dev 门禁流程，首个游戏项目落地后再评估是否需要联动。
