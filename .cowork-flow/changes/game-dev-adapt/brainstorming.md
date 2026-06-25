# Brainstorming: 游戏开发流程适配

## Goal

在现有 cowork-flow 基础上，通过 skill + spec 的方式补充游戏开发领域的知识覆盖，让现有固定代理（cowork-research / cowork-implement / cowork-check）能处理游戏开发场景下的编码、资产管线、引擎配置和性能分析任务。

## Non-Goals

- 不创建新的固定代理（cowork-gamedev）。
- 不修改现有的 3 固定代理派发协议。
- 不修改 workflow.md 核心流程。
- 不含实际游戏引擎集成（Unity/Unreal/Godot 的 API 绑定）。
- 不包含 3D 建模、贴图绘制、音频制作等非代码岗位的工作流。

## Key Assumptions

1. 游戏开发的核心迭代路径仍是"调研 → 实现 → 检查"，与现有流程一致。
2. 游戏开发与 CRUD/API 开发的差异在于知识域（资产管线、引擎模式、性能压点），而非执行模型。
3. Skill 是 cowork-flow 装载领域知识的标准方式（参考 tdd、python-design、writing-plans 等 skill）。
4. `.cowork-flow/spec/` 已有 backend/、frontend/、guides/ 分层，游戏规范自然接入。

## Scope Boundary

### In-Scope

- 创建 `.claude/skills/game-design/SKILL.md` — 游戏设计技能，在游戏相关任务前触发
- 创建 `.cowork-flow/spec/game/` — 游戏开发规范目录，至少包含：
  - `index.md` — 概述和目录
  - `engine-guidelines.md` — 引擎选型与架构约定（ECS vs OOP、帧同步 vs 状态同步）
  - `asset-pipeline.md` — 资产管线约定（文件组织、构建流程、LOD 策略）
  - `performance-guidelines.md` — 性能分析 checklist（帧率、内存、GC、渲染批次）
  - `multiplayer-guidelines.md` — 多人游戏基础约定（网络模型、同步策略、权威服务器）
- 注册新 skill 到 AGENTS.md（如需要）
- 创建 `.cowork-flow/plans/game-dev-adapt.md` — 实施计划

### Out-of-Scope

- 具体游戏项目或引擎绑定
- 非代码工具集成（Blender、Photosheet、FMOD）
- 修改固定代理行为
- 修改 workflow.md 状态机

## Recommended Direction

**`game-design` skill + `spec/game/` 规范目录**，而非新 agent。

为什么是 skill 而非 agent：
- 现有 3 固定代理的工具集（读/写/搜索/bash/skill 调用）完全覆盖游戏编码需求
- skill 在入口处注入领域知识和 checklists，比 agent 在远端点更轻、更即时
- 游戏开发的"上下文知识"是项目级（这个项目用 Unity/ECS），不是功能级
- 参考 `tdd` skill — 它不替换 implement agent，但确保实现前补测试证据

为什么 spec 而非只放在 skill：
- spec 是多人协作的持久规范基线，skill 是 AI 行为指南
- backend/ 和 frontend/ 就放在 spec/ 下，game/ 同层自然

## Rejected Alternatives

| 方案 | 拒因 |
|------|------|
| 新固定代理 `cowork-gamedev` | 工具集与 `cowork-implement` 无本质差异，增加维护成本 |
| 单独 game 工具链（asset pipeline scripts） | 偏离 cowork-flow "只存状态和契约"的定位 |
| 所有内容塞进一个 SKILL.md | 规范内容过多时 skill 会变臃肿，拆分到 spec/ 更可持续 |

## Acceptance Criteria

- AC-01: `game-design` skill 可从 IDE / CLI 调用，内容覆盖游戏架构、资产、性能、多人领域
- AC-02: `.cowork-flow/spec/game/` 目录至少 4 个指南文件
- AC-03: 现有流程中运行游戏任务时能触发 game-design skill 读取（纳入 before-dev 或 writing-plans 的读取范围）
- AC-04: 不破坏现有 spec 结构和 contract digest

## Open Questions / Risks

| 问题 | 影响 | 决策时机 |
|------|------|----------|
| 是否需要在 `before-dev` skill 中添加游戏相关分支？ | 可能需要在游戏任务中优先读取 spec/game/ | writing-plans 阶段 |
| 是否与 engine specific（UE/Unity/Godot）分享规范？ | 当前抽象层是否足够通用 | 首个真实游戏项目验证后 |
| spec/game/ 中的约定与具体项目规范冲突时谁优先？ | 继承现有规则"项目规范优先" | 已在 AGENTS.md 中定义 |

---

方向明确后进入 `writing-plans`。
